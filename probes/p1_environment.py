"""Probe P1: what is installed, measured rather than assumed. Runs in hython and in the worker; unknowns stay null.

Mission 0 runs it three times and commits the records:

    uv run python probes/hython.py probes/p1_environment.py --record docs/facts/p1_houdini.json
    uv run python probes/p1_environment.py --record docs/facts/p1_worker.json
    uv run python probes/hython.py probes/p1_environment.py --site-packages > docs/facts/p1_site_packages.json

The last file is what `check.py --houdini` compares Houdini's Python against, so nothing gets installed into it
unnoticed. It lists packages with importlib.metadata, never with pip.
"""
import argparse
import importlib.metadata as md
import json
import os
import platform
import shutil
import sys


def site_packages():
    found = {}
    for dist in md.distributions():
        name = (dist.metadata["Name"] or "").lower()
        if name:
            found[name] = dist.version
    return dict(sorted(found.items()))


def _try(fn):
    try:
        return fn()
    except Exception as e:                                      # record why a value is unknown, never invent it
        return {"unknown": f"{type(e).__name__}: {e}"}


def houdini():
    try:
        import hou
    except ImportError:
        return None
    return {
        "version": _try(hou.applicationVersionString),
        "licence_category": _try(lambda: str(hou.licenseCategory())),
        "hfs": os.environ.get("HFS"),
        "user_pref_dir": os.environ.get("HOUDINI_USER_PREF_DIR"),
        "package_dir": os.environ.get("HOUDINI_PACKAGE_DIR"),
    }


def opencv():
    try:
        import cv2
    except ImportError:
        return None
    info = cv2.getBuildInformation()
    keep = [line.strip() for line in info.splitlines() if any(k in line for k in ("OpenCL:", "OpenEXR:", "CUDA", "NVIDIA", "Parallel framework"))]
    return {
        "version": cv2.__version__,
        "build_lines": keep,
        "have_opencl": _try(cv2.ocl.haveOpenCL),
        "use_opencl": _try(lambda: (cv2.ocl.setUseOpenCL(True), cv2.ocl.useOpenCL())[1]),
        "opencl_device": _try(lambda: cv2.ocl.Device.getDefault().name()),
        "threads": _try(cv2.getNumThreads),
    }


def record():
    def version_of(module):
        try:
            return getattr(__import__(module), "__version__", "imported, no __version__")
        except Exception as e:
            return {"unknown": f"{type(e).__name__}: {e}"}
    return {
        "python": sys.version,
        "executable": sys.executable,
        "platform": platform.platform(),
        "numpy": version_of("numpy"),
        "openexr": version_of("OpenEXR"),
        "houdini": houdini(),
        "opencv": opencv(),
        "tools": {name: shutil.which(name) for name in ("git", "bash", "uv")},
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--record", metavar="PATH")
    group.add_argument("--site-packages", action="store_true")
    a = ap.parse_args()
    if a.site_packages:
        print(json.dumps(site_packages(), indent=1))
        return 0
    data = record()
    os.makedirs(os.path.dirname(os.path.abspath(a.record)), exist_ok=True)
    with open(a.record, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1, default=str)
        f.write("\n")
    print(json.dumps(data, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
