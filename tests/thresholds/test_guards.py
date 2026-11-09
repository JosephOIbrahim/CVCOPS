"""Rules the product must keep at every rung. Locked; tools/check.py runs these every time.

- Nothing under src/ imports hou, SYNAPSE, the evidence scripts or the tests (principle 3, decision 0001).
- Nothing under houdini/ imports OpenCV: the worker is a separate process (principle 1).
- The capability manifest and the example receipt satisfy their schemas, and the names agree (decision 0002).
- mission.txt and houdini_units.json are well formed.
"""
import ast
import json
import tomllib
from pathlib import Path

import jsonschema

import impls

ROOT = impls.ROOT
FORBIDDEN = {"hou", "hdefereval", "synapse", "thresholds_reference", "impls", "fixtures", "evaluator", "evidence", "tests", "conftest"}


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0], node.lineno
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module.split(".")[0], node.lineno
        elif isinstance(node, ast.Call) and getattr(node.func, "attr", getattr(node.func, "id", "")) in ("import_module", "__import__"):
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                yield node.args[0].value.split(".")[0], node.lineno


def test_src_stays_pure():
    bad = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        for name, line in _imports(path):
            if name.lower() in FORBIDDEN:
                bad.append(f"{path.relative_to(ROOT)}:{line} imports {name}")
    assert not bad, "the engine must not import these:\n" + "\n".join(bad)


def test_houdini_side_never_loads_opencv():
    bad = []
    for path in sorted((ROOT / "houdini").rglob("*.py")):
        if "test_prefs" in path.parts:
            continue
        for name, line in _imports(path):
            if name == "cv2":
                bad.append(f"{path.relative_to(ROOT)}:{line} imports cv2")
    assert not bad, "Houdini's process must not load OpenCV:\n" + "\n".join(bad)


def _load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def _check(schema_rel, doc):
    schema = _load(schema_rel)
    jsonschema.Draft202012Validator.check_schema(schema)
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(doc), key=lambda e: list(e.path))
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors[:10])


def test_manifest_matches_schema():
    _check("docs/contracts/capabilities.schema.json", _load("src/cvcops/capabilities.json"))


def test_example_receipt_matches_schema():
    _check("docs/contracts/receipt.schema.json", _load("docs/contracts/receipt.example.json"))


def test_names_agree():
    with open(ROOT / "pyproject.toml", "rb") as f:
        project = tomllib.load(f)
    n = project["tool"]["cvcops"]["names"]
    manifest = _load("src/cvcops/capabilities.json")
    assert project["project"]["name"] == n["package"], "pyproject's project name and names.package differ"
    assert manifest["engine"]["package"] == n["package"], "the manifest names another package"
    assert manifest["engine"]["invoke"]["module"] == n["package"], "the manifest invokes another module"
    assert manifest["engine"]["invoke"]["interpreter_env"] == f"{n['env_prefix']}_WORKER_PYTHON"
    assert manifest["engine"]["version"] == project["project"]["version"], "the manifest and pyproject versions differ"


def test_mission_list_is_well_formed():
    listed = impls.missions()
    assert listed, "mission.txt lists no mission"
    assert len(listed) == len(set(listed)), "mission.txt lists a mission twice"


def test_houdini_units_are_well_formed():
    units = impls.houdini_units()
    assert units.get("space") in (None, "pixel", "texture", "image")
    assert units.get("v_sign") in (None, 1, -1)
    assert (units["space"] is None) == (units["v_sign"] is None), "probe P4 records both or neither"
