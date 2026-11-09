"""The objects the threshold tests grade. A judge file, locked with the tests.

Every row grades an object with five methods: flow(a, b, preset, scale), valid(a, b, tau), pull(a, b),
write_exr(path, rgb) and read_exr(path) (evidence/thresholds_reference.py). This file builds them:

    product      rung 1. Calls the engine's own code in src/cvcops. Grades the M1 and M2 rows.
    houdini      rung 2. Drives the asset through hython (houdini/tests/bake_once.py). Grades the M3 and M4 rows.
    reference    the self-test: stock DIS, which every row must pass.
    fault:N      the self-test: the reference with one thing broken, which some row must fail.

The adapters live here, not in src/, so the product cannot hand the tests the reference instead of its own code.
"""
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evidence"))
sys.path.insert(0, str(ROOT / "src"))
import thresholds_reference as ref  # noqa: E402

ROWS, METRICS, verdict = ref.ROWS, ref.METRICS, ref.verdict
RUNG = {"M1": 1, "M2": 1, "M3": 2, "M4": 2}
KNOWN_MISSIONS = ("M0", "M1", "M2", "M3", "M4", "ME", "M5", "M6", "MN", "MU")
PRESET_TO_RECIPE = {"MEDIUM": "dis_medium", "FAST": "dis_fast"}
HYTHON_LIMIT_S = 600                                    # one hython call (FACTS, chosen numbers)


class EnvironmentProblem(RuntimeError):
    """A broken environment, not a failing test. check.py exits 3 on it, and the agent writes BLOCKED:."""


# ---- what is being judged ---------------------------------------------------------------------------------------
def missions(root=ROOT):
    """The missions started so far, one per line of tests/thresholds/mission.txt."""
    path = Path(root) / "tests" / "thresholds" / "mission.txt"
    listed = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    unknown = [m for m in listed if m not in KNOWN_MISSIONS]
    if unknown:
        raise ValueError(f"mission.txt lists unknown missions: {', '.join(unknown)}")
    return listed


def rows_for(listed, rung):
    return [r for r in ROWS if r["mission"] in listed and RUNG[r["mission"]] == rung]


def local_config(root=ROOT):
    """Machine paths from the untracked local.toml: hython, opencv_prep, cuda_python."""
    path = Path(root) / "local.toml"
    if not path.is_file():
        return {}
    with open(path, "rb") as f:
        return tomllib.load(f)


def names(root=ROOT):
    with open(Path(root) / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["tool"]["cvcops"]["names"]


# ---- rung 1: the engine's own code ----------------------------------------------------------------------------------
class ProductImpl:
    name = "product (src/cvcops)"

    def flow(self, a, b, preset="MEDIUM", scale=1.0):
        if scale != 1.0:
            raise AssertionError("the worker never sees analysis scale; rows at another scale run through Houdini")
        from cvcops.contract import check_flow
        from cvcops.ops.flow import estimate_flow
        f = estimate_flow(a, b, recipe=PRESET_TO_RECIPE[preset])
        check_flow(f, a.shape)
        return f

    def valid(self, a, b, tau=ref.TAU):
        from cvcops.ops.validity import validity
        v = validity(a, b, tolerance_px=tau)
        if not (isinstance(v, np.ndarray) and v.dtype == bool and v.shape == a.shape):
            raise AssertionError(f"validity must be bool with shape {a.shape}")
        return v

    def pull(self, a, b):
        raise AssertionError("pulling B onto A is the asset's job (M4); no rung-1 row uses it")

    def write_exr(self, path, rgb):
        from cvcops.io_exr import write_flow_exr
        write_flow_exr(path, rgb)

    def read_exr(self, path):
        from cvcops.io_exr import read_flow_exr
        return read_flow_exr(path)


# ---- rung 2: the asset, through hython ----------------------------------------------------------------------------
def houdini_units(root=ROOT):
    return json.loads((Path(root) / "tests" / "thresholds" / "houdini_units.json").read_text(encoding="utf-8"))


def px_per_unit(space, w, h):
    """Pixels per Houdini unit along u and v for a w by h image."""
    if space == "pixel":
        return 1.0, 1.0
    if space == "texture":
        return float(w), float(h)
    if space == "image":                                # -1 to 1 across the longer side (FACTS H15)
        s = max(w, h) / 2.0
        return s, s
    raise EnvironmentProblem(f"houdini_units.json names an unknown space {space!r}")


def to_opencv_px(flow_h, w, h, units):
    su, sv = px_per_unit(units["space"], w, h)
    out = np.empty(flow_h.shape[:2] + (2,), np.float32)
    out[..., 0] = flow_h[..., 0] * su
    out[..., 1] = flow_h[..., 1] * sv * units["v_sign"]
    return out


def hython_env(root=ROOT):
    """hython with nothing of the user's: an empty preferences folder and only this package (FACTS H20).

    HOUDINI_USER_PREF_DIR must contain __HVER__. Houdini reads package files directly in HOUDINI_PACKAGE_DIR, so
    the judge writes its own package file there. HSITE and the worker's Python variables are removed.
    """
    n = names(root)
    prefs = Path(root) / "houdini" / "test_prefs"
    packages = prefs / "packages"
    packages.mkdir(parents=True, exist_ok=True)
    package = {
        "load_package_once": True,
        "hpath": f"{Path(root).resolve().as_posix()}/houdini",
        "env": [{f"{n['env_prefix']}_ROOT": Path(root).resolve().as_posix()},
                {f"{n['env_prefix']}_WORKER_PYTHON": Path(sys.executable).as_posix()}],
    }
    (packages / f"{n['package']}.json").write_text(json.dumps(package, indent=2) + "\n", encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "HSITE", "HOUDINI_PATH", "HOUDINI_PACKAGE_DIR")}
    env["HOUDINI_USER_PREF_DIR"] = (prefs / "houdini__HVER__").as_posix()
    env["HOUDINI_PACKAGE_DIR"] = packages.as_posix()
    env["HOUDINI_NO_ENV_FILE"] = "1"
    return env


def _tail(text, n=25):
    return "\n".join(text.strip().splitlines()[-n:])


class HoudiniImpl:
    """Runs houdini/tests/bake_once.py in hython. Its contract, which Mission 3 implements:

    bake_once.py --mode flow --dir DIR --preset MEDIUM --scale S
        reads DIR/frame.1001.exr and DIR/frame.1002.exr (RGB float32, equal channels, grey in 0 to 1), bakes them
        through the asset with that preset and analysis scale, and writes DIR/flow.1001.exr: the asset's converted
        output through ROP Image, R and G the flow in Houdini's units, B validity, at the frames' full size.
    bake_once.py --mode pull --dir DIR
        reads the same frames and writes DIR/pulled.1001.exr: frame B pulled onto A's grid by the asset's forward
        flow through native Distort, grey in 0 to 1 in R.
    Exit 0 on success, 3 for a broken environment (no licence, no asset), anything else for a failure.
    """
    name = "houdini (the asset through hython)"

    def __init__(self, root=ROOT):
        self.root = Path(root)
        hython = local_config(root).get("hython")
        if not hython or not Path(hython).is_file():
            raise EnvironmentProblem("no hython: put its path in local.toml (probe P1)")
        self.hython = hython
        self.units = houdini_units(root)
        if self.units.get("space") is None or self.units.get("v_sign") not in (1, -1):
            raise EnvironmentProblem("probe P4 has not recorded Houdini's flow units in tests/thresholds/houdini_units.json")
        self.script = self.root / "houdini" / "tests" / "bake_once.py"

    def _run(self, *args):
        cmd = [self.hython, str(self.script), *args]
        try:
            p = subprocess.run(cmd, env=hython_env(self.root), capture_output=True, text=True, timeout=HYTHON_LIMIT_S)
        except FileNotFoundError as e:
            raise EnvironmentProblem(f"hython could not start: {e}")
        except subprocess.TimeoutExpired:
            raise EnvironmentProblem(f"hython ran past {HYTHON_LIMIT_S} s")
        if p.returncode == 3:
            raise EnvironmentProblem("bake_once.py reported a broken environment:\n" + _tail(p.stderr))
        if p.returncode != 0:
            raise AssertionError(f"bake_once.py {' '.join(args[:2])} exited {p.returncode}:\n" + _tail(p.stderr + p.stdout))

    @staticmethod
    def _write_frames(d, a, b):
        for frame, img in ((1001, a), (1002, b)):
            grey = (img.astype(np.float32) / 255.0)[..., None].repeat(3, axis=2)
            ref.Reference().write_exr(os.path.join(d, f"frame.{frame}.exr"), grey)

    def flow(self, a, b, preset="MEDIUM", scale=1.0):
        h, w = a.shape
        with tempfile.TemporaryDirectory(prefix="cvcops_bake_") as d:
            self._write_frames(d, a, b)
            self._run("--mode", "flow", "--dir", d, "--preset", preset, "--scale", repr(float(scale)))
            out = np.asarray(ref.Reference().read_exr(os.path.join(d, "flow.1001.exr")), np.float32)
        if out.shape[:2] != (h, w):
            raise AssertionError(f"the asset wrote flow at {out.shape[:2]}, not the frames' {(h, w)}")
        return to_opencv_px(out[..., :2], w, h, self.units)

    def pull(self, a, b):
        h, w = a.shape
        with tempfile.TemporaryDirectory(prefix="cvcops_pull_") as d:
            self._write_frames(d, a, b)
            self._run("--mode", "pull", "--dir", d)
            out = np.asarray(ref.Reference().read_exr(os.path.join(d, "pulled.1001.exr")), np.float32)
        if out.shape[:2] != (h, w):
            raise AssertionError(f"the asset wrote the pulled frame at {out.shape[:2]}, not {(h, w)}")
        return out[..., 0] * 255.0

    def valid(self, a, b, tau=ref.TAU):
        raise AssertionError("validity is graded at rung 1, not through Houdini")

    def write_exr(self, path, rgb):
        raise AssertionError("EXR transport is graded at rung 1 and by probe P3, not here")

    read_exr = write_exr


# ---- choosing one ---------------------------------------------------------------------------------------------------
def make_impl(name):
    if name == "product":
        return ProductImpl()
    if name == "houdini":
        return HoudiniImpl()
    if name == "reference":
        return ref.Reference()
    if name.startswith("fault:"):
        return ref.FAULTS[int(name.split(":", 1)[1])]
    raise ValueError(f"unknown implementation {name!r}")
