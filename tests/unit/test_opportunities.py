"""The opportunity register stays well formed and tied to the capability manifest (docs/OPPORTUNITIES.md)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REG = json.loads((ROOT / "docs" / "opportunities.json").read_text(encoding="utf-8"))
MANIFEST = json.loads((ROOT / "src" / "cvcops" / "capabilities.json").read_text(encoding="utf-8"))
OPS = {op["name"]: op for op in MANIFEST["operations"]}
FIELDS = {"id", "title", "zone", "where", "status", "needs", "operation", "ml", "evidence", "first_step"}


def test_register_is_well_formed():
    ids = [i["id"] for i in REG["items"]]
    assert len(ids) == len(set(ids)), "an opportunity id is used twice"
    for i in REG["items"]:
        assert set(i) == FIELDS, f"{i['id']}: fields differ from the register's"
        assert i["zone"] in REG["zones"], f"{i['id']}: unknown zone"
        assert i["where"] in ("engine", "houdini", "outside"), f"{i['id']}: unknown home"
        assert i["status"] in ("v0.1", "next", "parked", "idea"), f"{i['id']}: unknown status"
        assert i["evidence"] and i["first_step"], f"{i['id']}: say what is known and what comes first"
        known = set(ids) | {"flow", "valid", "pull", "receipts"}
        assert set(i["needs"]) <= known, f"{i['id']}: needs something the register does not know"


def test_named_operations_are_in_the_manifest():
    for i in REG["items"]:
        if i["operation"]:
            assert i["operation"] in OPS, f"{i['id']} names operation {i['operation']}, which the manifest lacks"
            assert i["where"] == "engine", f"{i['id']}: only an engine opportunity names an operation"


def test_parked_operations_are_in_the_register():
    named = {i["operation"] for i in REG["items"]}
    for name, op in OPS.items():
        if op["status"] == "parked":
            assert name in named, f"the manifest parks {name}, but no opportunity explains it"


def test_one_pick():
    assert [i["id"] for i in REG["items"] if i["status"] == "next"] == ["temporal_check"], "one opportunity is next (decision 0003)"
