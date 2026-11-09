"""The flow asset's controls stay in step with the worker's command line, the contract and the receipt schema.

houdini/build/controls.json is the one source for the node's parameters (docs/CONTROLS.md). A control marked
v0.1 that names a command-line option must name a real one with the same default and choices, and every
option of `cvcops flow` must have a control, so the node and the worker cannot drift apart.
"""
import json
import re
from pathlib import Path

from cvcops import contract
from cvcops.cli import build_parser

ROOT = Path(__file__).resolve().parents[2]
SPEC = json.loads((ROOT / "houdini" / "build" / "controls.json").read_text(encoding="utf-8"))
RECEIPT = json.loads((ROOT / "docs" / "contracts" / "receipt.schema.json").read_text(encoding="utf-8"))
TYPES = {"float", "float3", "int2", "menu", "toggle", "button", "directory", "label"}
LAYER_TYPES = {"RGBA", "RGB", "UV", "Mono"}
FROM_CONTRACT = {"contract.RECIPES": contract.RECIPES, "contract.BACKENDS": contract.BACKENDS}


def _flow_options():
    """Option string -> argparse action, for `cvcops flow`."""
    sub = next(a for a in build_parser()._actions if getattr(a, "choices", None) and "flow" in a.choices)
    return {opt: act for act in sub.choices["flow"]._actions for opt in act.option_strings if opt.startswith("--")}


def _live(items):
    return [c for c in items if c["status"] == "v0.1"]


def test_spec_is_well_formed():
    assert SPEC["schema"] == "cvcops.controls.v1"
    names = [c["name"] for c in SPEC["controls"]] + [p["name"] for p in SPEC["inputs"] + SPEC["outputs"]]
    assert len(names) == len(set(names)), "a control, input or output name is used twice"
    for c in SPEC["controls"]:
        assert re.fullmatch(r"[a-z][a-z0-9_]*", c["name"]), f"{c['name']} is not a Houdini parameter name"
        assert c["type"] in TYPES, f"{c['name']} has an unknown type {c['type']}"
        assert c["folder"] in SPEC["folders"], f"{c['name']} sits in an unknown folder"
        assert c["status"] in ("v0.1", "planned"), f"{c['name']} has an unknown status"
        assert c.get("help"), f"{c['name']} has no help text"
        assert c.get("maps_to"), f"{c['name']} maps to nothing: a control that changes nothing is noise"
    for p in SPEC["inputs"] + SPEC["outputs"]:
        assert p["type"] in LAYER_TYPES and p["status"] in ("v0.1", "planned") and p.get("help")


def test_the_node_outputs_what_the_contract_promises():
    live = {p["name"]: p["type"] for p in _live(SPEC["outputs"])}
    assert live == {"flow": "UV", "valid": "Mono"}, "v0.1 outputs are flow as UV and valid as Mono (blueprint, section 5)"


def test_controls_match_the_command_line():
    options = _flow_options()
    for c in _live(SPEC["controls"]):
        opt = c["maps_to"].get("cli")
        if not opt:
            continue
        assert opt in options, f"{c['name']} maps to {opt}, which `cvcops flow` does not have"
        act = options[opt]
        if act.choices:
            assert tuple(FROM_CONTRACT[c["choices_from"]]) == tuple(act.choices), f"{c['name']}: choices differ from {opt}"
        if act.default is not None and not act.required:
            assert c["default"] == act.default, f"{c['name']}: default {c['default']!r} differs from {opt}'s {act.default!r}"


def test_every_flow_option_has_a_control():
    mapped = {c["maps_to"].get("cli") for c in _live(SPEC["controls"])}
    derived = {"--help", "--in"}          # --in is the cache folder plus the analysis file pattern
    missing = sorted(set(_flow_options()) - mapped - derived)
    assert not missing, f"`cvcops flow` has options no control sets: {missing}"


def test_menus_come_from_the_contract():
    for c in SPEC["controls"]:
        if c["type"] != "menu":
            continue
        assert ("choices" in c) != ("choices_from" in c), f"{c['name']}: give choices or choices_from, not both"
        choices = c.get("choices") or list(FROM_CONTRACT[c["choices_from"]])
        if c["status"] == "v0.1":
            assert c["default"] in choices, f"{c['name']}: default is not one of its choices"
    tol = next(c for c in SPEC["controls"] if c["name"] == "tolerance")
    assert tol["default"] == contract.DEFAULT_TOLERANCE_PX


def test_receipt_fields_exist():
    for c in SPEC["controls"] + SPEC["inputs"]:
        field = c.get("maps_to", {}).get("receipt")
        if not field:
            continue
        node = RECEIPT
        for part in field.split("."):
            assert part in node.get("properties", {}), f"{c['name']} maps to receipt field {field}, which the schema lacks"
            node = node["properties"][part]
