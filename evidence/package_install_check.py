"""Prove the shipped package file alone makes the asset load (FACTS A11, REL.contract.release package check).

    uv run python evidence/package_install_check.py

Two halves. The driver, in the worker's environment, writes `src/cvcops/package.py`'s own file into a fresh empty
folder and starts hython with the judge's isolated environment (empty preferences, this package only) but
`HOUDINI_PACKAGE_DIR` pointed at that folder, so the package file is the only thing that can make the asset reachable.
The inner half runs inside that hython and reports three facts as JSON:

- the asset type resolves through the package's `hpath`, with nothing installed,
- `<prefix>_WORKER_PYTHON` holds the worker's interpreter,
- `cv2` never entered the process.

Exit 0 only when all three hold; 1 when one fails; 3 without hython or without a built asset.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "thresholds"))
sys.path.insert(0, str(ROOT / "src"))


def inner():
    """Run inside hython: report what the package file achieved."""
    import hou
    from cvcops import package

    names = package.names()
    type_name = f"{names['hda_namespace']}::{names['hda_flow']}::1.0"
    # compare against what the package file itself says, not against a fresh package_dict(): inside hython
    # sys.executable is hython, so recomputing would name the wrong interpreter
    pkg_dir = Path(os.environ.get("HOUDINI_PACKAGE_DIR", "."))
    with open(pkg_dir / f"{names['package']}.json", encoding="utf-8") as f:
        written = json.load(f)
    expected_worker = next(v[f"{names['env_prefix']}_WORKER_PYTHON"] for v in written["env"]
                           if f"{names['env_prefix']}_WORKER_PYTHON" in v)
    worker = hou.getenv(f"{names['env_prefix']}_WORKER_PYTHON") or ""
    report = {
        "houdini": hou.applicationVersionString(),
        "type": type_name,
        "resolves": hou.nodeType(hou.copNodeTypeCategory(), type_name) is not None,
        "worker": worker,
        "worker_expected": expected_worker,
        "worker_matches": Path(worker).as_posix().lower() == Path(expected_worker).as_posix().lower() if worker else False,
        "cv2_in_process": "cv2" in sys.modules,
        "package_dir": os.environ.get("HOUDINI_PACKAGE_DIR", ""),
    }
    print(json.dumps(report))
    return 0 if (report["resolves"] and report["worker_matches"] and not report["cv2_in_process"]) else 1


def driver():
    import tempfile
    from cvcops import package
    import impls

    asset = ROOT / "houdini" / "otls" / (
        f"{package.names()['hda_namespace']}_{package.names()['hda_flow']}.hda")
    if not asset.is_file():
        print(f"package_install_check.py: no asset at {asset}", file=sys.stderr)
        return 3
    hython = impls.local_config().get("hython")
    if not hython or not Path(hython).is_file():
        print("package_install_check.py: no hython in local.toml", file=sys.stderr)
        return 3
    with tempfile.TemporaryDirectory(prefix="cvcops_pkg_") as folder:
        written = package.write_package(folder)
        env = dict(impls.hython_env())
        env["HOUDINI_PACKAGE_DIR"] = str(Path(folder).resolve())
        try:
            out = subprocess.run([hython, str(Path(__file__).resolve()), "--inner"], env=env, cwd=str(ROOT),
                                 capture_output=True, text=True, timeout=300)
        except (OSError, subprocess.TimeoutExpired) as e:
            print(f"package_install_check.py: hython did not run: {e}", file=sys.stderr)
            return 3
    lines = [ln for ln in out.stdout.splitlines() if ln.startswith("{")]
    if not lines:
        print("package_install_check.py: no report from hython:\n" + out.stdout[-800:] + out.stderr[-800:],
              file=sys.stderr)
        return 1
    report = json.loads(lines[-1])
    ok = bool(report["resolves"] and report["worker_matches"] and not report["cv2_in_process"])
    print(f"package file      {written}")
    print(f"HOUDINI_PACKAGE_DIR {report['package_dir']}")
    print(f"Houdini           {report['houdini']}")
    print(f"{report['type']:<24} resolves: {report['resolves']}")
    print(f"worker            {report['worker'] or '(unset)'}")
    print(f"                  matches the package: {report['worker_matches']}")
    print(f"cv2 in process    {report['cv2_in_process']}")
    print("CHECK: the package file alone loads the asset and names the worker" if ok
          else "CHECK: the package file did not do its job")
    return 0 if ok else 1


def main():
    return inner() if "--inner" in sys.argv else driver()


if __name__ == "__main__":
    sys.exit(main())
