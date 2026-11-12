"""The engine version lives in three places and must agree (REL.release.version)."""
import json
import tomllib
from pathlib import Path

import cvcops

ROOT = Path(__file__).resolve().parents[2]


def test_every_version_place_reads_the_release():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    manifest = json.loads((ROOT / "src" / "cvcops" / "capabilities.json").read_text(encoding="utf-8"))
    assert pyproject == "0.1.0"
    assert cvcops.__version__ == pyproject
    assert manifest["engine"]["version"] == pyproject


def test_the_engine_version_is_not_in_the_cache_key(monkeypatch):
    """The brief's promise: moving to 0.1.0 does not stale a cache. Same request, different version, same key."""
    from cvcops import receipt

    identity = ("5.0.0", "ab" * 32)
    before = receipt.expected_cache_key(["1" * 64, "2" * 64], "dis_medium", "cpu", 1.0, identity=identity)
    monkeypatch.setattr(cvcops, "__version__", "9.9.9")
    after = receipt.expected_cache_key(["1" * 64, "2" * 64], "dis_medium", "cpu", 1.0, identity=identity)
    assert before == after
