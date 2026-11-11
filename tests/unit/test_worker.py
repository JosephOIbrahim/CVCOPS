"""Mission 2's end-to-end tests: a CLI round trip, an interrupted write, stale on a changed build, backend refusal.

No GPU and no Houdini: frames are 64 x 96, the device probes are stood in, and every subprocess has a timeout.
"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import jsonschema
import numpy as np
import OpenEXR
import pytest

from cvcops import cli, contract, io_exr, receipt
from cvcops.io_exr import read_analysis_exr, read_flow_exr
from cvcops.ops.flow import estimate_flow, recipe_source_sha256
from cvcops.ops.validity import forward_backward_valid

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = jsonschema.Draft202012Validator(
    json.loads((ROOT / "docs" / "contracts" / "receipt.schema.json").read_text(encoding="utf-8")))
H, W = 64, 96


def _texture(seed=5):
    rng = np.random.default_rng(seed)
    spec = rng.normal(size=(H, W)) + 1j * rng.normal(size=(H, W))
    f = np.sqrt(np.fft.fftfreq(H)[:, None] ** 2 + np.fft.fftfreq(W)[None, :] ** 2)
    img = np.fft.ifft2(spec * np.exp(-(f / 0.1) ** 2)).real
    return (img - img.min()) / (img.max() - img.min())


def _write_frame(path, k):
    x = (k / 255.0).astype(np.float32)
    with OpenEXR.File({"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage},
                      {"R": x, "G": x.copy(), "B": x.copy()}) as f:
        f.write(str(path))


def make_frames(folder, first=1001, count=3, seed=5):
    """Analysis frames as RGB float32 k/255, the content moving 2 px right per frame. Returns pattern, uint8 frames."""
    folder.mkdir(parents=True, exist_ok=True)
    base = _texture(seed)
    frames = {}
    for i in range(count):
        k = np.clip(np.rint(np.roll(base, 2 * i, axis=1) * 255.0), 0, 255).astype(np.uint8)
        _write_frame(folder / f"analysis.{first + i}.exr", k)
        frames[first + i] = k
    return str(folder / "analysis.####.exr"), frames


def _snapshot(folder):
    return {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in sorted(Path(folder).iterdir())}


def _flow(pattern, out, frames="1001-1002", *extra):
    return cli.main(["flow", "--in", pattern, "--out", str(out), "--frames", frames, *extra])


def _verify_json(pattern, out, capsys, frames="1001-1002", *extra):
    capsys.readouterr()
    code = cli.main(["verify", "--in", pattern, "--out", str(out), "--frames", frames, "--json", *extra])
    return code, json.loads(capsys.readouterr().out)


# ---- (1) the round trip -------------------------------------------------------------------------------------
def test_cli_round_trip(tmp_path, capsys):
    pattern, frames = make_frames(tmp_path / "bake")
    out = tmp_path / "bake"
    assert _flow(pattern, out) == 0
    lines = capsys.readouterr().out.splitlines()
    assert [ln.split()[:3] for ln in lines] == [["flow", "1001-1002", "ok"], ["flow", "1002-1003", "ok"]]
    identity = receipt.cv2_identity()
    for a in (1001, 1002):
        b = a + 1
        assert np.array_equal(read_analysis_exr(receipt.frame_path(pattern, a)), frames[a])
        fwd, bwd = estimate_flow(frames[a], frames[b]), estimate_flow(frames[b], frames[a])
        valid = forward_backward_valid(fwd, bwd, 1.0)
        got = read_flow_exr(out / f"flow.{a}.exr")
        assert got[..., :2].tobytes() == fwd.tobytes() and np.array_equal(got[..., 2], valid.astype(np.float32))
        data = json.loads((out / f"flow.{a}.json").read_text(encoding="utf-8"))
        VALIDATOR.validate(data)
        digests = [contract.sha256_file(receipt.frame_path(pattern, f)) for f in (a, b)]
        assert data["cache_key"] == receipt.expected_cache_key(digests, "dis_medium", "cpu", 1.0, identity)
        assert data["backend"]["requested"] == data["backend"]["ran"] == "cpu" and not data["backend"]["opencl_in_use"]
        assert data["recipe"] == {"name": "dis_medium", "source_sha256": recipe_source_sha256("dis_medium")}
        stats = [contract.analysis_stats(frames[f]) for f in (a, b)]
        assert data["analysis"]["clipped_share"] == max(s[0] for s in stats)
        assert data["analysis"]["grey_levels"] == min(s[1] for s in stats)
        assert data["analysis"]["scale"] == 1.0 and data["frame"] == {"a": a, "b": b, "fps": None, "interval": 1.0}
        assert set(data["timings_s"]) == set(receipt.TIMING_KEYS) and min(data["timings_s"].values()) >= 0
        assert data["output"]["sha256"] == contract.sha256_file(out / f"flow.{a}.exr")
        assert data["summary"]["valid_share"] == pytest.approx(float(valid.mean()))
    code, report = _verify_json(pattern, out, capsys)
    assert code == 0 and report["counts"] == {"fresh": 2, "stale": 0, "missing": 0}
    before = _snapshot(out)
    assert _flow(pattern, out) == 0
    assert "skip fresh" in capsys.readouterr().out and _snapshot(out) == before
    assert not [n for n in os.listdir(out) if n.startswith(".")]


def test_progress_lines_reach_a_pipe_before_the_worker_exits(tmp_path):
    pattern, _ = make_frames(tmp_path, count=2)
    code = ("import sys, time; from cvcops import cli; real = cli._flow_pair\n"
            "def slow(*a, **k):\n    r = real(*a, **k); time.sleep(1.5); return r\n"
            "cli._flow_pair = slow; sys.exit(cli.main(sys.argv[1:]))")
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    proc = subprocess.Popen([sys.executable, "-c", code, "flow", "--in", pattern, "--out", str(tmp_path),
                             "--frames", "1001-1001"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        first = proc.stdout.readline()
        still_running = proc.poll() is None
        rest, err = proc.communicate(timeout=60)
    finally:
        proc.kill()
    assert first.startswith("flow 1001-1002 ok") and still_running, (first, err)
    assert proc.returncode == 0


def test_the_module_entry_point_runs(tmp_path):
    pattern, _ = make_frames(tmp_path, count=2)
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    p = subprocess.run([sys.executable, "-m", "cvcops", "flow", "--in", pattern, "--out", str(tmp_path),
                        "--frames", "1001-1001"], capture_output=True, text=True, timeout=60, env=env)
    assert p.returncode == 0 and p.stdout.startswith("flow 1001-1002 ok"), p.stderr


# ---- (2) interrupted writes -----------------------------------------------------------------------------------
def _interrupt_on(monkeypatch, name):
    real = os.replace

    def replace(src, dst):
        if os.path.basename(dst) == name:
            raise KeyboardInterrupt
        real(src, dst)

    monkeypatch.setattr(io_exr.os, "replace", replace)


def test_an_interrupted_receipt_leaves_the_earlier_pair_whole(tmp_path, monkeypatch, capsys):
    pattern, _ = make_frames(tmp_path)
    _interrupt_on(monkeypatch, "flow.1002.json")
    with pytest.raises(KeyboardInterrupt):
        _flow(pattern, tmp_path)
    monkeypatch.undo()
    names = sorted(os.listdir(tmp_path))
    assert "flow.1001.exr" in names and "flow.1001.json" in names and "flow.1002.json" not in names
    assert not [n for n in names if n.startswith(".")]
    code, report = _verify_json(pattern, tmp_path, capsys)
    assert code == 1 and [p["state"] for p in report["pairs"]] == ["fresh", "missing"]
    first = {n: v for n, v in _snapshot(tmp_path).items() if n.startswith("flow.1001")}
    assert _flow(pattern, tmp_path) == 0
    assert {n: v for n, v in _snapshot(tmp_path).items() if n.startswith("flow.1001")} == first
    assert _verify_json(pattern, tmp_path, capsys)[0] == 0


def test_an_interrupted_flow_file_leaves_nothing_half_written(tmp_path, monkeypatch):
    pattern, _ = make_frames(tmp_path)
    _interrupt_on(monkeypatch, "flow.1002.exr")
    with pytest.raises(KeyboardInterrupt):
        _flow(pattern, tmp_path)
    names = sorted(os.listdir(tmp_path))
    assert "flow.1002.exr" not in names and "flow.1002.json" not in names
    assert not [n for n in names if n.startswith(".")]


def test_a_failure_after_reading_writes_an_error_receipt_and_goes_on(tmp_path, monkeypatch, capsys):
    pattern, _ = make_frames(tmp_path)
    assert _flow(pattern, tmp_path, "1001-1001") == 0
    from cvcops.ops import flow as flow_mod
    calls = []

    def flaky(a, b, recipe="dis_medium"):
        calls.append(1)
        if len(calls) == 1:                 # pair 1001's forward flow fails; pair 1002 runs normally
            raise RuntimeError("DIS fell over")
        return estimate_flow(a, b, recipe)

    monkeypatch.setattr(flow_mod, "estimate_flow", flaky)
    _write_frame(tmp_path / "analysis.1002.exr", np.full((H, W), 128, np.uint8))   # pair 1001 is no longer fresh
    assert _flow(pattern, tmp_path) == 1
    err = json.loads((tmp_path / "flow.1001.json").read_text(encoding="utf-8"))
    VALIDATOR.validate(err)
    assert err["status"] == "error" and "DIS fell over" in err["error"] and not (tmp_path / "flow.1001.exr").exists()
    assert json.loads((tmp_path / "flow.1002.json").read_text(encoding="utf-8"))["status"] == "ok"
    assert "DIS fell over" in capsys.readouterr().err


def test_preflight_refuses_missing_frames_and_writes_nothing(tmp_path, capsys):
    pattern, _ = make_frames(tmp_path / "in", count=2)
    out = tmp_path / "out"
    assert _flow(pattern, out, "1001-1002") == 1
    assert "analysis.1003.exr" in capsys.readouterr().err and not out.exists()
    assert _flow(str(tmp_path / "in" / "analysis.exr"), out, "1001-1001") == 1 and not out.exists()
    assert _flow(pattern, out, "1002-1001") == 1 and not out.exists()


# ---- (3) stale on a changed build or input ---------------------------------------------------------------------
@pytest.mark.parametrize("change", ["version", "build", "frame"])
def test_verify_goes_stale_when_the_build_or_an_input_changes(tmp_path, monkeypatch, capsys, change):
    pattern, frames = make_frames(tmp_path)
    assert _flow(pattern, tmp_path) == 0
    version, build = receipt.cv2_identity()
    if change == "version":
        monkeypatch.setattr(receipt, "cv2_identity", lambda: ("5.0.1", build))
    elif change == "build":
        monkeypatch.setattr(receipt, "cv2_identity", lambda: (version, "f" * 64))
    else:
        _write_frame(tmp_path / "analysis.1002.exr", np.roll(frames[1002], 1, axis=0))
    code, report = _verify_json(pattern, tmp_path, capsys)
    assert code == 1 and report["counts"]["stale"] == 2
    assert all("cache key" in p["reason"] for p in report["pairs"])
    assert _flow(pattern, tmp_path) == 0
    assert _verify_json(pattern, tmp_path, capsys)[0] == 0


def test_verify_requests_and_missing_files(tmp_path, capsys):
    pattern, _ = make_frames(tmp_path)
    assert _flow(pattern, tmp_path) == 0
    assert _verify_json(pattern, tmp_path, capsys, "1001-1002", "--tolerance", "1.0", "--recipe", "dis_medium",
                        "--backend", "cpu")[0] == 0
    code, report = _verify_json(pattern, tmp_path, capsys, "1001-1002", "--tolerance", "2")
    assert code == 1 and report["counts"]["stale"] == 2
    code, report = _verify_json(pattern, tmp_path, capsys, "1001-1002", "--recipe", "dis_fast")
    assert code == 1 and report["counts"]["stale"] == 2
    before = _snapshot(tmp_path)
    os.remove(tmp_path / "flow.1001.exr")
    os.remove(tmp_path / "flow.1002.json")
    code, report = _verify_json(pattern, tmp_path, capsys)
    assert code == 1 and [p["reason"] for p in report["pairs"]] == ["no flow file", "no receipt"]
    assert set(_snapshot(tmp_path)) == set(before) - {"flow.1001.exr", "flow.1002.json"}


def test_verify_on_a_missing_folder_reports_every_pair_missing(tmp_path, capsys):
    code, report = _verify_json(str(tmp_path / "nowhere" / "analysis.####.exr"), tmp_path / "nowhere", capsys)
    assert code == 1 and report["counts"] == {"fresh": 0, "stale": 0, "missing": 2}
    assert not (tmp_path / "nowhere").exists()


def test_source_hashes_ignore_line_endings(tmp_path):
    body = "def f(x):\n    return x + 1\n"
    hashes = []
    for name, text in (("lf_mod", body), ("crlf_mod", body.replace("\n", "\r\n"))):
        path = tmp_path / f"{name}.py"
        path.write_bytes(text.encode())
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        hashes.append(receipt._source_sha256(mod.f))
    assert hashes[0] == hashes[1]


# ---- (4) backends ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("backend, probe, value, code", [
    ("cuda", "cuda_device_count", 0, 3),
    ("cuda", "cuda_device_count", 1, 1),
    ("opencl", "opencl_device", None, 3),
    ("opencl", "opencl_device", "Stand-in GPU", 1),
])
def test_gpu_backends_are_refused_and_nothing_is_written(tmp_path, monkeypatch, capsys, backend, probe, value, code):
    pattern, _ = make_frames(tmp_path / "in", count=2)
    monkeypatch.setattr(cli, probe, lambda: value)
    out = tmp_path / "out"
    assert _flow(pattern, out, "1001-1001", "--backend", backend) == code
    err = capsys.readouterr().err
    assert "not substituted" in err if code == 3 else "Mission 6" in err
    assert not out.exists()


def test_a_broken_runtime_exits_3(tmp_path, monkeypatch, capsys):
    pattern, _ = make_frames(tmp_path, count=2)

    def broken():
        raise cli.Broken("cannot import the worker's runtime: ImportError: no cv2")

    monkeypatch.setattr(cli, "_import_runtime", broken)
    assert _flow(pattern, tmp_path, "1001-1001") == 3
    assert cli.main(["verify", "--in", pattern, "--out", str(tmp_path), "--frames", "1001-1001"]) == 3
    assert not (tmp_path / "flow.1001.json").exists()


# ---- reviewer gaps --------------------------------------------------------------------------------------------
def test_a_locked_flow_file_still_gets_an_error_receipt(tmp_path, monkeypatch, capsys):
    """OD-11: a File COP holding flow.1002.exr on Windows fails that pair with a receipt naming the lock."""
    pattern, _ = make_frames(tmp_path)
    assert _flow(pattern, tmp_path) == 0
    _write_frame(tmp_path / "analysis.1003.exr", np.full((H, W), 90, np.uint8))     # pair 1002 must re-run
    real_replace, real_remove = os.replace, os.remove

    def replace(src, dst):
        if os.path.basename(dst) == "flow.1002.exr":
            raise PermissionError("held by a File COP")
        real_replace(src, dst)

    def remove(path):
        if os.path.basename(str(path)) == "flow.1002.exr":
            raise PermissionError("held by a File COP")
        real_remove(path)

    monkeypatch.setattr(io_exr.os, "replace", replace)
    monkeypatch.setattr(io_exr, "REPLACE_RETRY_S", 0.1)
    monkeypatch.setattr(cli.os, "remove", remove)
    assert _flow(pattern, tmp_path) == 1
    monkeypatch.undo()
    data = json.loads((tmp_path / "flow.1002.json").read_text(encoding="utf-8"))
    VALIDATOR.validate(data)
    assert data["status"] == "error" and "PermissionError" in data["error"] and "could not remove" in data["error"]
    assert not [n for n in os.listdir(tmp_path) if n.startswith(".")]
    assert _verify_json(pattern, tmp_path, capsys)[1]["pairs"][1]["state"] == "stale"


def test_a_corrupt_frame_fails_its_pairs_and_the_run_goes_on(tmp_path, capsys):
    pattern, _ = make_frames(tmp_path, count=4)
    (tmp_path / "analysis.1002.exr").write_bytes(b"not an exr at all")
    assert _flow(pattern, tmp_path, "1001-1003") == 1
    out = capsys.readouterr().out.splitlines()
    assert out[:2] == ["flow 1001-1002 error", "flow 1002-1003 error"] and out[2].startswith("flow 1003-1004 ok")
    assert not (tmp_path / "flow.1001.json").exists() and (tmp_path / "flow.1003.json").exists()


def test_bad_arguments_exit_1_not_2(tmp_path, capsys):
    assert cli.main(["flow", "--in", "a.####.exr", "--out", str(tmp_path), "--frames", "ten"]) == 1
    assert cli.main(["flow", "--in", "a.####.exr", "--out", str(tmp_path), "--frames", "1-2", "--tolerance", "0"]) == 1
    assert cli.main(["verify", "--in", "a.####.exr", "--out", str(tmp_path), "--frames", "1-2", "--backend", "x"]) == 1
    capsys.readouterr()


def test_a_crop_note_follows_the_frame_into_the_next_pair(tmp_path):
    pattern, frames = make_frames(tmp_path)
    big = np.zeros((H + 2, W + 4), np.float32)
    big[1:-1, 2:-2] = frames[1002] / 255.0
    header = {"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage,
              "dataWindow": (np.array([-2, -1], np.int32), np.array([W + 1, H], np.int32)),
              "displayWindow": (np.array([0, 0], np.int32), np.array([W - 1, H - 1], np.int32))}
    with OpenEXR.File(header, {"Y": big}) as f:
        f.write(str(tmp_path / "analysis.1002.exr"))
    assert _flow(pattern, tmp_path) == 0
    for a in (1001, 1002):
        notes = json.loads((tmp_path / f"flow.{a}.json").read_text(encoding="utf-8"))["analysis"]["warnings"]
        assert any("cropped" in n for n in notes), a
