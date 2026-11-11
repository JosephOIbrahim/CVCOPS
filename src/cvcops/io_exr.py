"""EXR in and out, through the OpenEXR package (OpenCV 5 wheels have none).

Flow files are written whole or not at all: a temporary name in the target's folder, then os.replace. The analysis
reader accepts the layouts a grey export can plausibly arrive in and refuses everything else by name (decision 0004).
"""
import os
import re
import tempfile
import time

import numpy as np

from .contract import ContractError

REPLACE_RETRY_S = 1.0           # a File COP can hold the old file open on Windows (decision 0004, OD-11)
REPLACE_STEP_S = 0.05


def _openexr():
    import OpenEXR
    return OpenEXR


def _temp_beside(path, suffix):
    """A temporary file in path's folder whose name starts with a dot and never matches flow.####.exr or .json."""
    folder = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".cvcops-", suffix=suffix + ".tmp", dir=folder)
    os.close(fd)
    return tmp


def replace_with_retry(src, dst, retry_s=None, step_s=REPLACE_STEP_S):
    """os.replace, retried for about a second on PermissionError, then the error is raised."""
    deadline = time.monotonic() + (REPLACE_RETRY_S if retry_s is None else retry_s)
    while True:
        try:
            os.replace(src, dst)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(step_s)


def write_atomic(path, write_temp, suffix=""):
    """Call write_temp(tmp_path), then move the result onto path. On any failure, interrupts included, the
    temporary file is removed and an earlier file at path is left as it was."""
    tmp = _temp_beside(path, suffix)
    try:
        write_temp(tmp)
        replace_with_retry(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def write_flow_exr(path, rgb):
    """Write float32 (H, W, 3), channels R=u, G=v, B=valid, as 32-bit float with ZIP compression.

    Write to a temporary name in the same folder, then os.replace onto path, so a reader never sees half a file.
    Only the type and shape are checked: the values pass through untouched, which the M2 row demands bit for bit.
    """
    if not isinstance(rgb, np.ndarray) or rgb.dtype != np.float32 or rgb.ndim != 3 or rgb.shape[2] != 3:
        got = (getattr(rgb, "dtype", type(rgb).__name__), getattr(rgb, "shape", None))
        raise ContractError(f"a flow file holds float32 (H, W, 3): u, v, valid; got {got}")
    OpenEXR = _openexr()
    header = {"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage}
    channels = {name: np.ascontiguousarray(rgb[..., i]) for i, name in enumerate("RGB")}

    def write(tmp):
        with OpenEXR.File(header, channels) as f:
            f.write(tmp)

    write_atomic(path, write, suffix=".exr")


def read_flow_exr(path):
    """Return float32 (H, W, 3) exactly as written: R, G, B as u, v, valid."""
    OpenEXR = _openexr()
    with OpenEXR.File(str(path), separate_channels=True) as f:
        if len(f.parts) != 1:
            raise ContractError(f"{path}: a flow file has one part, not {len(f.parts)}")
        ch = f.channels()
        missing = [n for n in "RGB" if n not in ch]
        if missing:
            raise ContractError(f"{path}: a flow file needs channels R, G and B; it has {sorted(ch)}")
        bad = [n for n in "RGB" if ch[n].type() != OpenEXR.FLOAT]
        if bad:
            raise ContractError(f"{path}: channels {bad} are not 32-bit float")
        return np.ascontiguousarray(np.dstack([ch[n].pixels for n in "RGB"]), dtype=np.float32)


_ALPHA = re.compile(r"(^|.*\.)(A|a)$")


def _grey_channel(names, path):
    """Pick the channel that carries the grey value: one channel of any name, or an R, G, B trio, bare or under one
    common layer prefix in either case. Returns (channel names to compare, the one to use)."""
    if len(names) == 1:
        return names, names[0]
    if len(names) == 3:
        prefixes = {n.rsplit(".", 1)[0] if "." in n else "" for n in names}
        last = sorted(n.rsplit(".", 1)[-1] for n in names)
        if len(prefixes) == 1 and last in (["B", "G", "R"], ["b", "g", "r"]):
            red = next(n for n in names if n.rsplit(".", 1)[-1] in ("R", "r"))
            trio = sorted(names, key=lambda n: "RGBrgb".index(n.rsplit(".", 1)[-1]) % 3)
            return trio, red
    raise ContractError(f"{path}: cannot tell which channel is the grey analysis image among {sorted(names)}; "
                        "write one channel, or R, G and B with equal values")


def read_analysis_exr(path, report=None):
    """Read a grey analysis frame and return uint8 (H, W): np.clip(np.rint(x * 255), 0, 255).

    Alpha is set aside. Then exactly one channel of any name, or a bit-equal R, G, B trio (bare or under one layer
    prefix), FLOAT or HALF. A data window strictly containing the display window is cropped to it; when report is a
    list, a note is appended. Anything else is a ContractError naming the channels (decision 0004, OD-10).
    """
    OpenEXR = _openexr()
    with OpenEXR.File(str(path), separate_channels=True) as f:
        if len(f.parts) != 1:
            raise ContractError(f"{path}: a multi-part file ({len(f.parts)} parts); the analysis frame is one part")
        header = f.header()
        (dx0, dy0), (dx1, dy1) = (tuple(int(v) for v in w) for w in header["dataWindow"])
        (vx0, vy0), (vx1, vy1) = (tuple(int(v) for v in w) for w in header["displayWindow"])
        ch = f.channels()
        names = [n for n in ch if not _ALPHA.match(n)]
        if not names:
            raise ContractError(f"{path}: only alpha channels {sorted(ch)}; no grey image")
        compare, use = _grey_channel(names, path)
        for n in compare:
            if ch[n].type() not in (OpenEXR.FLOAT, OpenEXR.HALF):
                raise ContractError(f"{path}: channel {n} is {ch[n].type()}; the analysis frame is FLOAT or HALF")
        pixels = {n: np.asarray(ch[n].pixels) for n in compare}
    grey = pixels[use]
    for n in compare:
        if not np.array_equal(pixels[n], grey):
            raise ContractError(f"{path}: channels {compare} differ; a grey frame has R = G = B")
    if not np.isfinite(grey).all():
        raise ContractError(f"{path}: channel {use} holds NaN or infinity")
    if (dx0, dy0, dx1, dy1) != (vx0, vy0, vx1, vy1):
        if dx0 > vx0 or dy0 > vy0 or dx1 < vx1 or dy1 < vy1:
            raise ContractError(f"{path}: the data window {(dx0, dy0, dx1, dy1)} does not cover the display window "
                                f"{(vx0, vy0, vx1, vy1)}")
        grey = grey[vy0 - dy0:vy1 - dy0 + 1, vx0 - dx0:vx1 - dx0 + 1]
        if report is not None:
            report.append(f"analysis frame data window {(dx0, dy0, dx1, dy1)} cropped to the display window "
                          f"{(vx0, vy0, vx1, vy1)}")
    return np.clip(np.rint(grey.astype(np.float64) * 255.0), 0, 255).astype(np.uint8)
