"""Probe P3, the worker's half: write the transport pattern, and judge what Houdini sends back.

    uv run python probes/p3_transport.py write probe_out/          writes probe_out/transport.1001.exr
    ... in Houdini: File COP reads it, ROP Image writes it again (Mission 0 finds the settings) ...
    uv run python probes/p3_transport.py compare probe_out/transport.1001.exr probe_out/returned.1001.exr

The pattern (evidence/thresholds_reference.py, transport_pattern) has negative values, values far above 1, values
half float cannot hold, a 0 and 1 channel and corner markers. compare exits 0 only for identical bits, and
otherwise names what went wrong: half float, clamping, a vertical flip, other channel names, a size change.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evidence"))
import thresholds_reference as ref  # noqa: E402


def read_any(path):
    import OpenEXR
    with OpenEXR.File(str(path), separate_channels=True) as f:
        ch = f.channels()
        names = sorted(ch)
        for trio in (("R", "G", "B"), ("C.r", "C.g", "C.b"), ("C.R", "C.G", "C.B")):
            if all(n in ch for n in trio):
                return np.dstack([ch[n].pixels for n in trio]), names
    return None, names


def compare(original, returned):
    a, _ = read_any(original)
    b, names = read_any(returned)
    if b is None:
        print(f"MISMATCH: no R, G, B channels in the returned file; it has {names}")
        return 1
    print(f"returned channels {names}, dtype {b.dtype}, shape {b.shape}")
    if b.shape != a.shape:
        print(f"MISMATCH: size {b.shape[:2]}, sent {a.shape[:2]}")
        return 1
    if b.dtype == np.float32 and np.array_equal(a, b):
        print("BIT-EXACT: these settings carry the pattern through Houdini unchanged")
        return 0
    bf = b.astype(np.float32)
    diff = np.abs(bf - a)
    print(f"MISMATCH: largest difference {diff.max():.6g}, mean {diff.mean():.6g}")
    if np.array_equal(bf, a.astype(np.float16).astype(np.float32)):
        print("  the values were rounded to half float: set 32-bit on the File COP and the ROP Image")
    if np.array_equal(bf, a[::-1]):
        print("  the rows arrived upside down: a vertical flip somewhere on the path")
    if bf.min() >= 0 and a.min() < 0 or bf.max() <= 1 and a.max() > 1:
        print("  the values were clamped to 0 to 1: a colour conversion is still on; set Raw")
    if bf[0, -1, 0] != a[0, -1, 0]:
        print("  the tiny top-right marker did not survive")
    return 1


def main(argv):
    if len(argv) == 2 and argv[0] == "write":
        out = Path(argv[1])
        out.mkdir(parents=True, exist_ok=True)
        path = out / "transport.1001.exr"
        ref.Reference().write_exr(str(path), ref.transport_pattern())
        print(path)
        return 0
    if len(argv) == 3 and argv[0] == "compare":
        return compare(argv[1], argv[2])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
