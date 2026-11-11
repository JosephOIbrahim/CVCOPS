"""Render the reader-pin frame: one 32 by 32 analysis frame through the asset's own export (M3.io.reader_pin).

    uv run python probes/hython.py probes/m3_reader_pin.py probe_out/m3_reader_pin

Writes two 32 by 32 RGB float32 source frames with R = G = B = k / 255, k = (7x + 3y) mod 256, feeds them to
cvcops::flow::1.0 at the default settings (Rec. 709 weights, gain 1, gamma 1, Analysis Scale 1.0) and presses only
the internal export ROP, so <out>/cache/.export/analysis.1001.exr is exactly what ROP Image writes for a bake.
That file is copied byte for byte to tests/unit/fixtures/rop_image_analysis.exr; it is never rewritten.
Exit 0 done, 1 failure, 3 no hou or no asset.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIZE = 32


def levels():
    import numpy as np
    ys, xs = np.mgrid[0:SIZE, 0:SIZE]
    return ((7 * xs + 3 * ys) % 256).astype(np.uint8)


def write_source(path):
    import numpy as np
    import OpenEXR
    v = (levels().astype(np.float32) / np.float32(255.0)).astype(np.float32)
    header = {"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage}
    with OpenEXR.File(header, {"R": v.copy(), "G": v.copy(), "B": v.copy()}) as f:
        f.write(str(path))


def main():
    try:
        import hou
    except ImportError:
        print("m3_reader_pin.py: no hou; run it with probes/hython.py", file=sys.stderr)
        return 3
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 1
    out = os.path.abspath(sys.argv[1])
    os.makedirs(out, exist_ok=True)
    for frame in (1001, 1002):
        write_source(os.path.join(out, f"frame.{frame}.exr"))

    sys.path.insert(0, str(ROOT / "houdini" / "tests"))
    import bake_once
    n = bake_once.names()
    tname = f"{n['hda_namespace']}::{n['hda_flow']}::1.0"
    if hou.nodeType(hou.copNodeTypeCategory(), tname) is None:
        print(f"m3_reader_pin.py: {tname} is not installed", file=sys.stderr)
        return 3
    hou.setFrame(1001)
    net = hou.node("/obj").createNode("copnet", "reader_pin")
    src = bake_once._raw_file(net, "frames", os.path.join(out, "frame.$F4.exr"), "vector")
    node = net.createNode(tname, "flow1")
    node.setInput(0, src, 0)
    node.parmTuple("frange").deleteAllKeyframes()
    node.parmTuple("frange").set((1001, 1001))
    cache = os.path.join(out, "cache")
    node.parm("cache_dir").set(cache.replace("\\", "/"))
    os.makedirs(os.path.join(cache, ".export"), exist_ok=True)
    export = node.node("export")
    export.parm("execute").pressButton()
    frame = os.path.join(cache, ".export", "analysis.1001.exr")
    if export.errors() or not os.path.isfile(frame):
        print("m3_reader_pin.py: the export failed:\n" + "\n".join(export.errors()), file=sys.stderr)
        return 1
    print(f"wrote {frame} ({os.path.getsize(frame)} bytes); Houdini {hou.applicationVersionString()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
