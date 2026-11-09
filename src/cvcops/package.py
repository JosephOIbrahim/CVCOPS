"""The Houdini package file. Install is one file: this writes it (blueprint section 5, FACTS H12, H20).

A package is a JSON file Houdini reads at start-up from $HOUDINI_USER_PREF_DIR/packages, among other places. This
one adds the repository's houdini/ folder to the Houdini path, so the asset and its Python load, and names the
worker's interpreter in an environment variable the Bake button reads. Paths are written with forward slashes,
as SideFX's own Windows examples are.
"""
import json
import os
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NAMES = {"package": "cvcops", "command": "cvcops", "hda_namespace": "cvcops", "hda_flow": "flow", "env_prefix": "CVCOPS"}


def names(root=ROOT):
    """The [tool.cvcops.names] table of pyproject.toml (decision 0002), or the working-title defaults."""
    path = Path(root) / "pyproject.toml"
    if not path.is_file():
        return dict(DEFAULT_NAMES)
    with open(path, "rb") as f:
        table = tomllib.load(f).get("tool", {}).get("cvcops", {}).get("names", {})
    return {**DEFAULT_NAMES, **table}


def package_dict(root=ROOT, worker_python=None, n=None):
    root = Path(root).resolve()
    n = n or names(root)
    worker_python = Path(worker_python or sys.executable)
    prefix = n["env_prefix"]
    return {
        "load_package_once": True,
        "hpath": f"{root.as_posix()}/houdini",
        "env": [
            {f"{prefix}_ROOT": root.as_posix()},
            {f"{prefix}_WORKER_PYTHON": worker_python.as_posix()},
        ],
    }


def write_package(dest_dir, root=ROOT, worker_python=None):
    """Write <package>.json into dest_dir, atomically. Returns its path."""
    n = names(root)
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f"{n['package']}.json"
    fd, tmp = tempfile.mkstemp(dir=dest_dir, prefix=".tmp_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(package_dict(root, worker_python, n), f, indent=2)
        f.write("\n")
    os.replace(tmp, target)
    return target
