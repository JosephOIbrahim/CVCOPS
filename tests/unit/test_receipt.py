"""Mission 2: receipts against the locked schema, the cache key, the atomic write and the freshness rule."""
import copy
import json
import os
from pathlib import Path

import jsonschema
import pytest

from cvcops import contract, receipt
from cvcops.contract import ContractError

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "docs" / "contracts" / "receipt.schema.json").read_text(encoding="utf-8"))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
SHA = "a" * 64
IDENTITY = ("5.0.0", "b" * 64)


def _receipt(tmp_path, status="ok", sidecar=None, **over):
    a, b = tmp_path / "analysis.1001.exr", tmp_path / "analysis.1002.exr"
    for p in (a, b):
        p.write_bytes(b"frame " + p.name.encode())
    flow = tmp_path / "flow.1001.exr"
    flow.write_bytes(b"flow")
    digests = [contract.sha256_file(a), contract.sha256_file(b)]
    args = dict(status=status, a=1001, b=1002, inputs={"a": (a, digests[0]), "b": (b, digests[1])},
                image=(64, 96), analysis={"clipped_share": 0.01, "grey_levels": 200, "warnings": []},
                sidecar=sidecar or receipt.read_analysis_sidecar(str(tmp_path / "analysis.####.exr")),
                recipe="dis_medium", backend="cpu", tolerance_px=1.0,
                cache_key=receipt.expected_cache_key(digests, "dis_medium", "cpu", 1.0, IDENTITY),
                identity=IDENTITY, threads=8, opencl_in_use=False,
                timings=dict.fromkeys(receipt.TIMING_KEYS, 0.01))
    if status == "ok":
        args.update(output=(flow, contract.sha256_file(flow)),
                    summary={"valid_share": 0.9, "median_motion_px": 1.0, "p99_motion_px": 3.0})
    else:
        args.update(error="ValueError: something")
    args.update(over)
    return receipt.build_receipt(**args), digests, flow


@pytest.mark.parametrize("status", ["ok", "error"])
def test_receipts_validate_against_the_locked_schema(tmp_path, status):
    data, _, _ = _receipt(tmp_path, status)
    VALIDATOR.validate(data)
    receipt.check_receipt(data)
    assert set(data["timings_s"]) == set(receipt.TIMING_KEYS)
    assert data["inputs"]["a"]["path"].startswith(str(tmp_path).replace("\\", "/")) and "\\" not in data["inputs"]["a"]["path"]
    assert data["engine"] == {"package": "cvcops", "version": __import__("cvcops").__version__}


def test_a_sidecar_receipt_validates_and_carries_the_prep_values(tmp_path):
    sidecar = {"analysis": {"luminance_weights": [0.2126, 0.7152, 0.0722], "gain": 1.0, "gamma": 2.2, "scale": 0.5,
                            "color_space": None}, "frame": {"fps": 24.0}}
    data, _, _ = _receipt(tmp_path, sidecar=sidecar)
    VALIDATOR.validate(data)
    assert data["analysis"]["scale"] == 0.5 and data["frame"]["fps"] == 24.0 and data["analysis"]["grey_levels"] == 200


@pytest.mark.parametrize("break_it", [
    lambda d: d.pop("cache_key"),
    lambda d: d.update(status="maybe"),
    lambda d: d.pop("output"),
    lambda d: d["backend"].update(ran="opencl"),
    lambda d: d.update(cache_key="XYZ"),
    lambda d: d.update(surprise=1),
    lambda d: d["analysis"].update(scale=0),
    lambda d: d["analysis"].update(grey_levels=300),
    lambda d: d.update(threads=0),
])
def test_the_hand_check_refuses_what_the_schema_refuses(tmp_path, break_it):
    data, _, _ = _receipt(tmp_path)
    bad = copy.deepcopy(data)
    break_it(bad)
    with pytest.raises(jsonschema.ValidationError):
        VALIDATOR.validate(bad)
    with pytest.raises(ContractError):
        receipt.check_receipt(bad)
    with pytest.raises(ContractError):
        receipt.write_receipt(tmp_path / "flow.1001.json", bad)
    assert not (tmp_path / "flow.1001.json").exists()


def test_the_cache_key_follows_what_changes_the_result(tmp_path, monkeypatch):
    digests = ["1" * 64, "2" * 64]
    key = receipt.expected_cache_key(digests, "dis_medium", "cpu", 1.0, IDENTITY)
    assert key == receipt.expected_cache_key(digests, "dis_medium", "cpu", 1.0, IDENTITY)
    assert key != receipt.expected_cache_key(digests, "dis_medium", "cpu", 1.0, ("5.0.1", IDENTITY[1]))
    assert key != receipt.expected_cache_key(digests, "dis_medium", "cpu", 1.0, (IDENTITY[0], "c" * 64))
    assert key != receipt.expected_cache_key(digests, "dis_medium", "cpu", 2.0, IDENTITY)
    assert key != receipt.expected_cache_key(digests, "dis_fast", "cpu", 1.0, IDENTITY)
    assert key != receipt.expected_cache_key(["1" * 64, "3" * 64], "dis_medium", "cpu", 1.0, IDENTITY)
    real = receipt.code_hashes()
    monkeypatch.setattr(receipt, "code_hashes", lambda: {**real, "validity": "0" * 64})
    assert key != receipt.expected_cache_key(digests, "dis_medium", "cpu", 1.0, IDENTITY)
    monkeypatch.setattr(receipt, "code_hashes", lambda: real)
    from cvcops.ops import flow
    monkeypatch.setattr(flow, "recipe_source_sha256", lambda name: "9" * 64)
    assert key != receipt.expected_cache_key(digests, "dis_medium", "cpu", 1.0, IDENTITY)


def test_the_key_ignores_threads_the_engine_version_and_the_folder(tmp_path, monkeypatch):
    for name in "xyz":
        (tmp_path / name).mkdir()
    first, digests, _ = _receipt(tmp_path / "x")
    moved, digests2, _ = _receipt(tmp_path / "y", threads=2)
    assert digests == digests2 and first["cache_key"] == moved["cache_key"] and first["threads"] != moved["threads"]
    assert first["inputs"]["a"]["path"] != moved["inputs"]["a"]["path"]
    import cvcops
    monkeypatch.setattr(cvcops, "__version__", "9.9.9")
    later, _, _ = _receipt(tmp_path / "z")
    assert later["engine"]["version"] == "9.9.9" and later["cache_key"] == first["cache_key"]


def test_the_build_identity_is_read_at_call_time():
    version, build = receipt.cv2_identity()
    import cv2
    assert version == cv2.__version__ and len(build) == 64
    assert receipt.cv2_identity() == (version, build)


def test_a_fault_before_the_replace_leaves_no_receipt_and_no_temp(tmp_path, monkeypatch):
    data, _, _ = _receipt(tmp_path)
    from cvcops import io_exr
    before = sorted(os.listdir(tmp_path))
    monkeypatch.setattr(io_exr.os, "replace", lambda s, d: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        receipt.write_receipt(tmp_path / "flow.1001.json", data)
    assert sorted(os.listdir(tmp_path)) == before


# ---- freshness ------------------------------------------------------------------------------------------------
def _fresh_setup(tmp_path):
    data, digests, flow = _receipt(tmp_path)
    path = tmp_path / "flow.1001.json"
    receipt.write_receipt(path, data)
    return path, data["cache_key"], flow


def test_freshness_says_fresh_when_everything_matches(tmp_path):
    path, key, flow = _fresh_setup(tmp_path)
    assert receipt.freshness(path, key, flow)[0] == "fresh"


def test_freshness_names_every_cause(tmp_path):
    path, key, flow = _fresh_setup(tmp_path)
    assert receipt.freshness(path, "c" * 64, flow) == ("stale", receipt.freshness(path, "c" * 64, flow)[1])
    assert "cache key" in receipt.freshness(path, "c" * 64, flow)[1]
    assert receipt.freshness(path, None, flow)[0] == "stale"
    flow.write_bytes(b"changed")
    assert "flow file differs" in receipt.freshness(path, key, flow)[1]
    os.remove(flow)
    assert receipt.freshness(path, key, flow) == ("missing", "no flow file")
    flow.write_bytes(b"flow")
    os.remove(tmp_path / "analysis.1002.exr")
    state, reason = receipt.freshness(path, key, flow)
    assert state == "stale" and "gone" in reason
    os.remove(path)
    assert receipt.freshness(path, key, flow) == ("missing", "no receipt")


def test_freshness_calls_unreadable_malformed_and_failed_receipts_stale(tmp_path):
    path, key, flow = _fresh_setup(tmp_path)
    path.write_text("{half", encoding="utf-8")
    assert receipt.freshness(path, key, flow)[0] == "stale"
    path.write_text(json.dumps({"schema": "cvcops.receipt.v1"}), encoding="utf-8")
    assert receipt.freshness(path, key, flow)[0] == "stale"
    data, _, _ = _receipt(tmp_path, status="error")
    receipt.write_receipt(path, data)
    state, reason = receipt.freshness(path, data["cache_key"], flow)
    assert state == "stale" and "failed" in reason


def test_verify_report_shape():
    rep = receipt.verify_report(1001, 1002, [(1001, 1002, "fresh", "ok"), (1002, 1003, "missing", "no receipt")])
    assert rep == {"frames": {"first": 1001, "last": 1002}, "counts": {"fresh": 1, "stale": 0, "missing": 1},
                   "pairs": [{"a": 1001, "b": 1002, "state": "fresh", "reason": "ok"},
                             {"a": 1002, "b": 1003, "state": "missing", "reason": "no receipt"}]}


@pytest.mark.parametrize("pattern, frame, want", [("bake/analysis.####.exr", 1001, "bake/analysis.1001.exr"),
                                                  ("a.##.exr", 7, "a.07.exr"),
                                                  ("C:/x y/analysis.#####.exr", 42, "C:/x y/analysis.00042.exr")])
def test_frame_patterns_expand(pattern, frame, want):
    assert receipt.frame_path(pattern, frame).replace("\\", "/") == want


@pytest.mark.parametrize("pattern", ["analysis.exr", "a.##.b.##.exr"])
def test_a_pattern_needs_one_run_of_hashes(pattern):
    with pytest.raises(ContractError):
        receipt.frame_path(pattern, 1)


@pytest.mark.parametrize("break_it", [
    lambda d: d.update(recipe="dis_medium"),
    lambda d: d.update(inputs=[]),
    lambda d: d.update(backend=None),
    lambda d: d["inputs"].pop("b"),
])
def test_freshness_calls_structurally_broken_receipts_stale(tmp_path, break_it):
    path, key, flow = _fresh_setup(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    break_it(data)
    path.write_text(json.dumps(data), encoding="utf-8")
    state, reason = receipt.freshness(path, key, flow)
    assert state == "stale" and "malformed" in reason


def test_the_alpha_pattern_is_in_the_readers_hash(monkeypatch):
    import re as re_mod

    from cvcops import io_exr
    before = receipt.code_hashes()["read_analysis_exr"]
    monkeypatch.setattr(io_exr, "_ALPHA", re_mod.compile(r"(^|.*\.)(A|a|alpha)$"))
    assert receipt.code_hashes()["read_analysis_exr"] != before
