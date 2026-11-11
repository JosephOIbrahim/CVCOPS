"""Mission 2: the analysis sidecar, Houdini's prep values beside the frames (decision 0004)."""
import json
from pathlib import Path

import pytest

from cvcops import receipt
from cvcops.contract import ContractError

ROOT = Path(__file__).resolve().parents[2]
CONTROLS = json.loads((ROOT / "houdini" / "build" / "controls.json").read_text(encoding="utf-8"))


def _write(tmp_path, data):
    (tmp_path / "analysis.json").write_text(json.dumps(data) if not isinstance(data, str) else data, encoding="utf-8")
    return str(tmp_path / "analysis.####.exr")


def test_schema_id_and_fields_are_fixed():
    assert receipt.SIDECAR_SCHEMA == "cvcops.analysis_sidecar.v1" != "cvcops.receipt.v1"
    assert receipt.SIDECAR_FIELDS == ("analysis.luminance_weights", "analysis.gain", "analysis.gamma",
                                      "analysis.scale", "analysis.color_space", "frame.fps")


@pytest.mark.parametrize("pattern, want", [("bake/analysis.####.exr", "bake/analysis.json"),
                                           ("analysis.####.exr", "analysis.json"),
                                           ("C:/a b/plate_####.exr", "C:/a b/plate.json")])
def test_the_sidecar_sits_beside_the_frames(pattern, want):
    assert receipt.sidecar_path(pattern).replace("\\", "/") == want


def test_no_sidecar_means_the_source_as_given(tmp_path):
    got = receipt.read_analysis_sidecar(str(tmp_path / "analysis.####.exr"))
    assert got == {"analysis": {"luminance_weights": None, "gain": None, "gamma": None, "scale": 1.0,
                                "color_space": None}, "frame": {"fps": None}}


def test_a_sidecar_sets_what_it_names_and_leaves_the_rest(tmp_path):
    pattern = _write(tmp_path, {"schema": receipt.SIDECAR_SCHEMA,
                                "analysis": {"luminance_weights": [0.2126, 0.7152, 0.0722], "gain": 1.5,
                                             "gamma": 2.2, "scale": 0.5},
                                "frame": {"fps": 24.0}})
    got = receipt.read_analysis_sidecar(pattern)
    assert got["analysis"] == {"luminance_weights": [0.2126, 0.7152, 0.0722], "gain": 1.5, "gamma": 2.2,
                               "scale": 0.5, "color_space": None}
    assert got["frame"] == {"fps": 24.0}


@pytest.mark.parametrize("data", [
    {"schema": "cvcops.receipt.v1"},
    "{not json",
    ["a list"],
    {"schema": receipt.SIDECAR_SCHEMA, "extra": 1},
    {"schema": receipt.SIDECAR_SCHEMA, "analysis": {"clipped_share": 0.1}},
    {"schema": receipt.SIDECAR_SCHEMA, "analysis": {"grey_levels": 200}},
    {"schema": receipt.SIDECAR_SCHEMA, "analysis": {"warnings": []}},
    {"schema": receipt.SIDECAR_SCHEMA, "analysis": {"image": {}}},
    {"schema": receipt.SIDECAR_SCHEMA, "analysis": {"blur": 2}},
    {"schema": receipt.SIDECAR_SCHEMA, "frame": {"a": 1001}},
    {"schema": receipt.SIDECAR_SCHEMA, "analysis": {"scale": 0}},
    {"schema": receipt.SIDECAR_SCHEMA, "analysis": {"scale": 1.5}},
    {"schema": receipt.SIDECAR_SCHEMA, "analysis": {"scale": None}},
    {"schema": receipt.SIDECAR_SCHEMA, "analysis": {"luminance_weights": [1, 2]}},
    {"schema": receipt.SIDECAR_SCHEMA, "analysis": {"gain": "2"}},
    {"schema": receipt.SIDECAR_SCHEMA, "analysis": {"gain": True}},
    {"schema": receipt.SIDECAR_SCHEMA, "frame": {"fps": float("nan")}},
    {"schema": receipt.SIDECAR_SCHEMA, "analysis": "half"},
])
def test_a_bad_sidecar_is_refused_never_half_read(tmp_path, data):
    with pytest.raises(ContractError):
        receipt.read_analysis_sidecar(_write(tmp_path, data))


def test_every_prep_control_reaches_the_receipt_through_the_sidecar(tmp_path):
    """Binds the reader to controls.json without editing it: each v0.1 prep control names a sidecar field."""
    prep = [c for c in CONTROLS["controls"] if c["status"] == "v0.1" and "prep" in c["maps_to"]]
    assert {c["name"] for c in prep} == {"luma_weights", "gain", "gamma", "analysis_scale"}
    sample = {"analysis.luminance_weights": [0.3, 0.6, 0.1], "analysis.gain": 2.0, "analysis.gamma": 2.2,
              "analysis.scale": 0.25}
    for c in prep:
        field = c["maps_to"]["receipt"]
        assert field.startswith("analysis.") and field in receipt.SIDECAR_FIELDS, c["name"]
        section, key = field.split(".")
        got = receipt.read_analysis_sidecar(_write(tmp_path, {"schema": receipt.SIDECAR_SCHEMA,
                                                              section: {key: sample[field]}}))
        assert got[section][key] == sample[field]
