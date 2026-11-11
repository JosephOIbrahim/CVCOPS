"""The Bake button's path through cvcops::flow::1.0, case by case, in hython (M3.hom.bake).

    uv run python probes/hython.py houdini/tests/bake_smoke.py probe_out/m3_bake_smoke

Each run works in a new folder <out>/run_<n>. It writes three small textured RGB frames (1001 to 1003, the scene
moving 2 px right and 1 px down per frame) with the OpenEXR in Houdini's Python, wires them into the installed asset
(loaded through the package file alone) and drives the same functions the buttons call:

  three_frame_bake      a bake of 1001-1002 writes flow and receipts for both pairs, and bake.json last
  button_resolves       the Bake button's callback reaches cvcops_houdini.bake.bake with this node
  worker_identity       the worker the glue starts is CPython 3.13.14 with numpy, cv2 and OpenEXR from the worker
                        venv, nothing under $HFS
  check_cache_fresh     Check Cache reports 2 fresh
  rebake_keeps_fresh    a re-bake of 1001 alone keeps every analysis frame (pixels identical, OD-13) and pair 1002
                        stays fresh
  missing_flow          after deleting flow.1002.exr, Check Cache reports 1 missing and a cook at 1002 errors
  rebake_scene_loaded   with the outputs cooked, a re-bake that rewrites both flow files: records whether
                        os.replace succeeded beside the loaded File COP (informational, OD-11)
  missing_worker        an unset worker interpreter is a broken environment and leaves the cache untouched
  cancel_slow_worker    a cancel during a slow stand-in worker stops it within 5 s and leaves no flow file under a
                        final name

Writes <out>/run_<n>/smoke.json. Exit 0 when every case passes, 1 otherwise, 3 without hou or the asset.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
W, H = 128, 96
SHIFT = (2, 1)                     # x right, y down, per frame


def write_frames(folder):
    """Three RGB float32 frames of smooth noise, each shifted by SHIFT from the one before."""
    import numpy as np
    import OpenEXR
    rng = np.random.default_rng(7)
    base = rng.random((H + 64, W + 64)).astype(np.float32)
    for _ in range(3):                                  # a cheap blur, so DIS has texture to follow
        base = (base + np.roll(base, 1, 0) + np.roll(base, -1, 0) + np.roll(base, 1, 1) + np.roll(base, -1, 1)) / 5
    base = (base - base.min()) / (base.max() - base.min())
    header = {"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage}
    for i, frame in enumerate((1001, 1002, 1003)):
        dx, dy = SHIFT[0] * i, SHIFT[1] * i
        img = np.ascontiguousarray(base[32 - dy:32 - dy + H, 32 - dx:32 - dx + W], dtype=np.float32)
        with OpenEXR.File(header, {"R": img.copy(), "G": img.copy(), "B": img.copy()}) as f:
            f.write(os.path.join(folder, f"frame.{frame}.exr"))


def listing(folder):
    """Name -> (size, mtime_ns) for every file under folder."""
    out = {}
    for dirpath, _, files in os.walk(folder):
        for name in files:
            p = os.path.join(dirpath, name)
            st = os.stat(p)
            out[os.path.relpath(p, folder)] = (st.st_size, st.st_mtime_ns)
    return out


class Smoke:
    def __init__(self, hou, folder, node, bake_mod, worker_mod, prefix):
        self.hou, self.dir, self.node, self.bake, self.worker, self.prefix = hou, folder, node, bake_mod, worker_mod, prefix
        self.cache = os.path.join(folder, "cache")
        self.results = []

    def record(self, name, ok, detail):
        self.results.append({"case": name, "pass": bool(ok), "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}", flush=True)

    def run(self, name, fn):
        try:
            ok, detail = fn()
        except Exception as e:  # noqa: BLE001 - every case reports, none stops the others
            ok, detail = False, f"{type(e).__name__}: {e}"
        self.record(name, ok, detail)

    def frange(self, first, last):
        self.node.parmTuple("frange").deleteAllKeyframes()
        self.node.parmTuple("frange").set((first, last))

    def counts(self):
        return self.bake.check_cache(self.node, self.prefix)["counts"]

    # ---- cases --------------------------------------------------------------------------------------------------
    def three_frame_bake(self):
        self.frange(1001, 1002)
        times = self.bake.bake(self.node, self.prefix)
        names = [f"flow.{f}.{ext}" for f in (1001, 1002) for ext in ("exr", "json")]
        missing = [n for n in names if not os.path.isfile(os.path.join(self.cache, n))]
        if missing:
            return False, f"missing {missing}"
        files = listing(self.cache)
        last = files["bake.json"][1]
        later = [n for n, (_, m) in files.items() if m > last and not n.startswith(".export")]
        return not later, (f"flow and receipts for 1001 and 1002; bake.json last; total {times['total']:.2f} s"
                           if not later else f"written after bake.json: {later}")

    def button_resolves(self):
        script = self.node.parm("bake").parmTemplate().scriptCallback()
        if "hou.phm().on_bake" not in script:
            return False, f"the button's callback is {script!r}"
        calls, real = [], self.bake.bake
        self.bake.bake = lambda node, prefix="CVCOPS": calls.append((node.path(), prefix)) or {"total": 0.0}
        try:
            self.node.hdaModule().on_bake(self.node)
        finally:
            self.bake.bake = real
        where = Path(self.bake.__file__).resolve()
        ok = calls == [(self.node.path(), self.prefix)] and ROOT / "houdini" / "python3.13libs" in where.parents
        return ok, f"hou.phm().on_bake -> cvcops_houdini.bake.bake{calls}, module {where.relative_to(ROOT).as_posix()}"

    def worker_identity(self):
        python = self.worker.worker_python(self.prefix)
        code = ("import json, sys, numpy, cv2, OpenEXR; print(json.dumps({'version': sys.version.split()[0], "
                "'files': [numpy.__file__, cv2.__file__, OpenEXR.__file__, sys.executable], "
                "'numpy': numpy.__version__, 'cv2': cv2.__version__, 'OpenEXR': getattr(OpenEXR, '__version__', '?')}))")
        rc, lines, tail = self.worker.run_worker([python, "-I", "-u", "-c", code], self.worker.scrubbed_env(), self.dir)
        if rc != 0:
            return False, f"exit {rc}: {tail}"
        info = json.loads(lines[-1])
        hfs = os.path.normcase(os.path.abspath(self.hou.getenv("HFS") or "\0"))
        under = [f for f in info["files"] if os.path.normcase(os.path.abspath(f)).startswith(hfs)]
        ok = info["version"] == "3.13.14" and not under
        return ok, (f"CPython {info['version']}, numpy {info['numpy']}, cv2 {info['cv2']}, OpenEXR {info['OpenEXR']}; "
                    + ("nothing under $HFS" if not under else f"under $HFS: {under}"))

    def check_cache_fresh(self):
        self.frange(1001, 1002)
        c = self.counts()
        return c == {"fresh": 2, "stale": 0, "missing": 0}, f"Check Cache: {c}"

    def rebake_keeps_fresh(self):
        before = listing(self.cache)
        self.frange(1001, 1001)
        self.bake.bake(self.node, self.prefix)
        with open(os.path.join(self.cache, "bake.json"), encoding="utf-8") as f:
            placed = json.load(f)["analysis_frames"]
        after = listing(self.cache)
        same = all(after[n] == before[n] for n in ("analysis.1001.exr", "analysis.1002.exr", "flow.1002.exr", "flow.1002.json"))
        self.frange(1001, 1002)
        c = self.counts()
        ok = placed == {"kept": 2, "replaced": 0} and same and c["fresh"] == 2
        return ok, f"analysis frames {placed}; 1002's files untouched: {same}; Check Cache {c}"

    def missing_flow(self):
        os.remove(os.path.join(self.cache, "flow.1002.exr"))
        self.frange(1001, 1002)
        c = self.counts()
        self.hou.setFrame(1002)
        load = self.node.node("load")
        try:
            load.cook(force=True)
            errors = load.errors()
        except self.hou.OperationFailed as e:
            errors = [str(e)]
        finally:
            self.hou.setFrame(1001)
        ok = c["missing"] == 1 and c["fresh"] == 1 and bool(errors)
        return ok, f"Check Cache {c}; the cook at 1002 errors: {bool(errors)}"

    def rebake_scene_loaded(self):
        self.frange(1001, 1002)
        self.bake.bake(self.node, self.prefix)          # puts back the flow file missing_flow deleted
        for frame in (1001, 1002):
            self.hou.setFrame(frame)
            self.node.node("convert").cook(force=True)
        self.hou.setFrame(1001)
        tol = self.node.parm("tolerance")
        old = tol.eval()
        tol.set(old * 2)                                # a new cache key: both pairs are rewritten
        try:
            self.bake.bake(self.node, self.prefix)
            outcome = "os.replace succeeded beside the loaded File COP"
        except self.bake.BakeError as e:
            outcome = f"the bake failed: {str(e).splitlines()[0]}"
        finally:
            tol.set(old)
        self.bake.bake(self.node, self.prefix)          # back to the default key for the cases after this one
        c = self.counts()
        return c["fresh"] == 2, f"{outcome}; after restoring the tolerance, Check Cache {c}"

    def missing_worker(self):
        var = f"{self.prefix}_WORKER_PYTHON"
        before = listing(self.cache)
        saved = os.environ.get(var)
        os.environ[var] = os.path.join(self.dir, "no_such_python.exe")
        try:
            self.bake.bake(self.node, self.prefix)
            raised = None
        except self.worker.WorkerEnvironmentError as e:
            raised = ("WorkerEnvironmentError", 3, str(e))
        except self.bake.BakeError as e:
            raised = ("BakeError", e.code, str(e))
        finally:
            os.environ[var] = saved
        untouched = listing(self.cache) == before
        ok = raised is not None and raised[1] == 3 and untouched
        return ok, f"raised {raised[:2] if raised else None}; cache untouched: {untouched}"

    def cancel_slow_worker(self):
        cache = os.path.join(self.dir, "cache_cancel")
        stub = os.path.join(self.dir, "slow_worker.py")
        Path(stub).write_text("import os, sys, time\n"
                              "out = sys.argv[1]\n"
                              "open(os.path.join(out, '.cvcops-stub.exr'), 'wb').write(b'partial')\n"
                              "print('flow 1001-1002 start', flush=True)\n"
                              "time.sleep(120)\n"
                              "os.replace(os.path.join(out, '.cvcops-stub.exr'), os.path.join(out, 'flow.1001.exr'))\n",
                              encoding="utf-8")
        hou, real_argv, real_op = self.hou, self.worker.flow_argv, self.hou.InterruptableOperation

        class Cancel(Exception):
            pass

        class TimedOperation:
            """InterruptableOperation that cancels 2 s after the worker starts, as Esc would."""

            def __init__(self, *a, **k):
                self.start = time.monotonic()

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def updateLongProgress(self, fraction=0.0, text=""):
                if time.monotonic() - self.start > 2.0:
                    raise Cancel("cancelled")

        self.worker.flow_argv = lambda python, pattern, out, *rest: [python, "-I", "-u", stub, out]
        hou.InterruptableOperation = TimedOperation
        self.node.parm("cache_dir").set(cache.replace("\\", "/"))
        t0 = time.monotonic()
        try:
            self.bake.bake(self.node, self.prefix)
            outcome = "the bake finished; it should have been cancelled"
        except Cancel:
            outcome = "cancelled"
        finally:
            self.worker.flow_argv, hou.InterruptableOperation = real_argv, real_op
            self.node.parm("cache_dir").set(self.cache.replace("\\", "/"))
        took = time.monotonic() - t0
        finals = sorted(n for n in os.listdir(cache) if n.startswith("flow.") and n.endswith((".exr", ".json")))
        ok = outcome == "cancelled" and took < 2.0 + 5.0 + 30.0 and not finals
        return ok, f"{outcome} after {took:.1f} s (export included); flow files under final names: {finals or 'none'}"


def main():
    try:
        import hou
    except ImportError:
        print("bake_smoke.py: no hou; run it with probes/hython.py", file=sys.stderr)
        return 3
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 1
    base = os.path.abspath(sys.argv[1])
    os.makedirs(base, exist_ok=True)
    n = 1
    while os.path.exists(os.path.join(base, f"run_{n}")):
        n += 1
    folder = os.path.join(base, f"run_{n}")
    os.makedirs(folder)

    sys.path.insert(0, str(ROOT / "houdini" / "tests"))
    import bake_once
    names = bake_once.names()
    tname = f"{names['hda_namespace']}::{names['hda_flow']}::1.0"
    if hou.nodeType(hou.copNodeTypeCategory(), tname) is None:
        print(f"bake_smoke.py: {tname} is not installed", file=sys.stderr)
        return 3
    from cvcops_houdini import bake as bake_mod, worker as worker_mod

    write_frames(folder)
    hou.setFrame(1001)
    net = hou.node("/obj").createNode("copnet", "bake_smoke")
    src = bake_once._raw_file(net, "frames", os.path.join(folder, "frame.$F4.exr"), "vector")
    node = net.createNode(tname, "flow1")
    node.setInput(0, src, 0)
    node.parm("cache_dir").set(os.path.join(folder, "cache").replace("\\", "/"))

    s = Smoke(hou, folder, node, bake_mod, worker_mod, names["env_prefix"])
    for case in ("three_frame_bake", "button_resolves", "worker_identity", "check_cache_fresh", "rebake_keeps_fresh",
                 "missing_flow", "rebake_scene_loaded", "missing_worker", "cancel_slow_worker"):
        s.run(case, getattr(s, case))
    with open(os.path.join(folder, "smoke.json"), "w", encoding="utf-8") as f:
        json.dump({"houdini": hou.applicationVersionString(), "results": s.results}, f, indent=2)
    failed = [r["case"] for r in s.results if not r["pass"]]
    print(f"bake_smoke: {len(s.results) - len(failed)} of {len(s.results)} cases pass"
          + (f"; failed: {', '.join(failed)}" if failed else "") + f" ({Path(folder).name})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
