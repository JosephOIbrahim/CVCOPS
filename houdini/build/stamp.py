"""The build stamp: one SHA-256 over everything that shapes the built asset. Standard library only.

Covers every file under houdini/build/ and houdini/python3.13libs/ (no __pycache__), the [tool.cvcops.names] table
and src/cvcops/contract.py, each with CRLF normalised to LF, so a CRLF checkout and an LF one agree. build_hdas.py
writes it into the asset and beside it; the self-test recomputes it from the tree on disk.
"""
import hashlib
import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TREES = ("houdini/build", "houdini/python3.13libs")


def files(root=ROOT):
    root = Path(root)
    out = []
    for tree in TREES:
        out += [p for p in sorted((root / tree).rglob("*")) if p.is_file() and "__pycache__" not in p.parts]
    out.append(root / "src" / "cvcops" / "contract.py")
    return out


def stamp(root=ROOT):
    root = Path(root)
    h = hashlib.sha256()
    for p in files(root):
        h.update(p.relative_to(root).as_posix().encode() + b"\0")
        h.update(p.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    with open(root / "pyproject.toml", "rb") as f:
        names = tomllib.load(f)["tool"]["cvcops"]["names"]
    h.update(json.dumps(names, sort_keys=True).encode())
    return h.hexdigest()
