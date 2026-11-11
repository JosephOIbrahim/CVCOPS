"""Mission 2: the flow EXR writer and reader, and the analysis reader's accepted layouts and refusals."""
import os

import numpy as np
import OpenEXR
import pytest

from cvcops import io_exr
from cvcops.contract import ContractError
from cvcops.io_exr import read_analysis_exr, read_flow_exr, write_flow_exr

HDR = {"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage}


def _pattern(h=24, w=40):
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    img = np.dstack([(xs - w / 2) * 7.123456 + 0.000123, (h / 2 - ys) * 9.876543 - 1000.3,
                     ((xs.astype(int) // 4 + ys.astype(int) // 4) % 2)]).astype(np.float32)
    img[0, -1] = (1e-3, -1e-3, 0.0)
    return img


def _write(path, channels, header=None):
    with OpenEXR.File(dict(HDR, **(header or {})), {k: np.ascontiguousarray(v) for k, v in channels.items()}) as f:
        f.write(str(path))
    return path


def _grey(h=6, w=8):
    return (np.arange(h * w).reshape(h, w) % 256).astype(np.uint8)


# ---- flow files -----------------------------------------------------------------------------------------------
def test_flow_round_trip_is_bit_exact(tmp_path):
    img = _pattern()
    write_flow_exr(tmp_path / "flow.1001.exr", img)
    back = read_flow_exr(tmp_path / "flow.1001.exr")
    assert back.dtype == np.float32 and back.shape == img.shape and np.array_equal(back, img)
    assert os.listdir(tmp_path) == ["flow.1001.exr"]


@pytest.mark.parametrize("bad", [np.zeros((4, 4, 3), np.float64), np.zeros((4, 4, 3), np.float16),
                                 np.zeros((4, 4, 2), np.float32), np.zeros((4, 4), np.float32), [[0.0]]])
def test_flow_writer_refuses_the_wrong_type_or_shape(tmp_path, bad):
    with pytest.raises(ContractError):
        write_flow_exr(tmp_path / "flow.1001.exr", bad)
    assert os.listdir(tmp_path) == []


def test_a_failed_replace_leaves_no_temp_and_the_old_file_intact(tmp_path, monkeypatch):
    target = tmp_path / "flow.1001.exr"
    old = _pattern()
    write_flow_exr(target, old)
    before = target.read_bytes()

    def boom(src, dst):
        raise KeyboardInterrupt

    monkeypatch.setattr(io_exr.os, "replace", boom)
    with pytest.raises(KeyboardInterrupt):
        write_flow_exr(target, _pattern() + 1)
    assert os.listdir(tmp_path) == ["flow.1001.exr"] and target.read_bytes() == before


def test_a_failed_first_write_leaves_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(io_exr.os, "replace", lambda s, d: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        write_flow_exr(tmp_path / "flow.1001.exr", _pattern())
    assert os.listdir(tmp_path) == []


def test_replace_retries_a_locked_file_then_gives_up(tmp_path, monkeypatch):
    calls = []
    real = os.replace

    def locked_twice(src, dst):
        calls.append(1)
        if len(calls) < 3:
            raise PermissionError("held by a File COP")
        real(src, dst)

    monkeypatch.setattr(io_exr.os, "replace", locked_twice)
    write_flow_exr(tmp_path / "flow.1001.exr", _pattern())
    assert len(calls) == 3 and os.listdir(tmp_path) == ["flow.1001.exr"]

    monkeypatch.setattr(io_exr.os, "replace", lambda s, d: (_ for _ in ()).throw(PermissionError("held")))
    with pytest.raises(PermissionError):
        io_exr.write_atomic(tmp_path / "x.exr", lambda tmp: open(tmp, "wb").close())
    assert sorted(os.listdir(tmp_path)) == ["flow.1001.exr"]


def test_temp_names_never_look_like_outputs(tmp_path):
    tmp = io_exr._temp_beside(tmp_path / "flow.1001.exr", ".exr")
    name = os.path.basename(tmp)
    assert name.startswith(".") and not name.startswith("flow.") and name.endswith(".tmp")
    assert os.path.dirname(tmp) == str(tmp_path)


def test_flow_reader_refuses_half_and_missing_channels(tmp_path):
    g = np.zeros((4, 4), np.float32)
    _write(tmp_path / "half.exr", {"R": g.astype(np.float16), "G": g, "B": g})
    with pytest.raises(ContractError, match="32-bit"):
        read_flow_exr(tmp_path / "half.exr")
    _write(tmp_path / "rg.exr", {"R": g, "G": g})
    with pytest.raises(ContractError, match="R, G and B"):
        read_flow_exr(tmp_path / "rg.exr")


# ---- analysis frames ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("layout", ["Y", "C", "analysis.Y", "RGB", "RGBA", "C.rgb", "C.RGB", "rgb_lower"])
def test_analysis_reader_accepts_every_grey_layout(tmp_path, layout):
    k = _grey()
    x = (k / 255.0).astype(np.float32)
    channels = {"Y": {"Y": x}, "C": {"C": x}, "analysis.Y": {"analysis.Y": x},
                "RGB": {"R": x, "G": x, "B": x}, "RGBA": {"R": x, "G": x, "B": x, "A": np.ones_like(x)},
                "C.rgb": {"C.r": x, "C.g": x, "C.b": x, "C.a": np.ones_like(x)},
                "C.RGB": {"C.R": x, "C.G": x, "C.B": x}, "rgb_lower": {"r": x, "g": x, "b": x}}[layout]
    path = _write(tmp_path / "analysis.1001.exr", channels)
    got = read_analysis_exr(path)
    assert got.dtype == np.uint8 and np.array_equal(got, k)


def test_analysis_reader_reads_half_and_quantises_like_the_reference(tmp_path):
    x = np.array([[0.0, 0.5 / 255, 1.49 / 255, 1.51 / 255, 1.0, 1.7, -0.2]], np.float32)
    want = np.clip(np.rint(x.astype(np.float64) * 255.0), 0, 255).astype(np.uint8)
    assert np.array_equal(read_analysis_exr(_write(tmp_path / "f.exr", {"Y": x})), want)
    k = _grey()
    h = (k / 255.0).astype(np.float16)
    got = read_analysis_exr(_write(tmp_path / "h.exr", {"Y": h}))
    assert np.array_equal(got, np.clip(np.rint(h.astype(np.float64) * 255.0), 0, 255).astype(np.uint8))


def test_analysis_reader_crops_a_data_window_wider_than_the_display(tmp_path):
    big = (np.arange(8 * 10).reshape(8, 10) / 255.0).astype(np.float32)
    header = {"dataWindow": (np.array([-2, -1], np.int32), np.array([7, 6], np.int32)),
              "displayWindow": (np.array([0, 0], np.int32), np.array([5, 4], np.int32))}
    report = []
    got = read_analysis_exr(_write(tmp_path / "w.exr", {"Y": big}, header), report=report)
    want = np.clip(np.rint(big[1:6, 2:8].astype(np.float64) * 255), 0, 255).astype(np.uint8)
    assert got.shape == (5, 6) and np.array_equal(got, want) and len(report) == 1 and "cropped" in report[0]


@pytest.mark.parametrize("case", ["unequal_rgb", "two_channels", "uint", "nan", "inf", "short_window", "only_alpha"])
def test_analysis_reader_refuses_by_name(tmp_path, case):
    x = (_grey() / 255.0).astype(np.float32)
    header = None
    if case == "unequal_rgb":
        channels = {"R": x, "G": x, "B": x + np.float32(1 / 255)}
    elif case == "two_channels":
        channels = {"Y": x, "Z": x}
    elif case == "uint":
        channels = {"Y": _grey().astype(np.uint32)}
    elif case in ("nan", "inf"):
        y = x.copy()
        y[1, 1] = np.nan if case == "nan" else np.inf
        channels = {"Y": y}
    elif case == "short_window":
        channels = {"Y": x}
        h, w = x.shape
        header = {"dataWindow": (np.array([0, 0], np.int32), np.array([w - 1, h - 1], np.int32)),
                  "displayWindow": (np.array([0, 0], np.int32), np.array([w, h], np.int32))}
    else:
        channels = {"A": x}
    path = _write(tmp_path / "bad.exr", channels, header)
    with pytest.raises(ContractError):
        read_analysis_exr(path)


def test_analysis_reader_refuses_a_multi_part_file(tmp_path):
    g = np.zeros((4, 4), np.float32)
    parts = [OpenEXR.Part(dict(HDR, name="a"), {"Y": g}), OpenEXR.Part(dict(HDR, name="b"), {"Y": g})]
    path = tmp_path / "two.exr"
    with OpenEXR.File(parts) as f:
        f.write(str(path))
    with pytest.raises(ContractError, match="multi-part"):
        read_analysis_exr(path)


ROP_IMAGE_FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "rop_image_analysis.exr")


def test_rop_image_analysis_export_reads_to_the_expected_levels():
    """M3.io.reader_pin: a 32x32 frame ROP Image wrote through cvcops::flow::1.0's own export on 22.0.492
    (probes/m3_reader_pin.py), committed byte for byte. The source was R = G = B = k / 255 with k = (7x + 3y) mod 256,
    at the asset's defaults (Rec. 709 weights, gain 1, gamma 1, scale 1.0), so the reader must return k exactly."""
    report = []
    got = read_analysis_exr(ROP_IMAGE_FIXTURE, report)
    ys, xs = np.mgrid[0:32, 0:32]
    assert got.dtype == np.uint8 and np.array_equal(got, ((7 * xs + 3 * ys) % 256).astype(np.uint8))
    assert report == []


def test_rop_image_analysis_export_layout_is_pinned():
    """What ROP Image wrote (FACTS H34): one part, scanline, ZIP, R, G and B as FLOAT, equal windows of 32x32."""
    with OpenEXR.File(ROP_IMAGE_FIXTURE, separate_channels=True) as f:
        header = {k: f.header()[k] for k in ("dataWindow", "displayWindow", "compression", "type")}
        channels = {name: c.pixels.copy() for name, c in f.channels().items()}
        assert len(f.parts) == 1
    assert sorted(channels) == ["B", "G", "R"]
    assert all(c.dtype == np.float32 and c.shape == (32, 32) for c in channels.values())
    assert np.array_equal(channels["R"], channels["G"]) and np.array_equal(channels["R"], channels["B"])
    for window in ("dataWindow", "displayWindow"):
        assert [list(map(int, v)) for v in header[window]] == [[0, 0], [31, 31]]
    assert header["compression"] == OpenEXR.ZIP_COMPRESSION and header["type"] == OpenEXR.scanlineimage
