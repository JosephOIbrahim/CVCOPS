"""One bake through the asset, for the M3 and M4 threshold rows. Runs in hython.

The judge calls it through tests/thresholds/impls.py (HoudiniImpl), whose docstring is the contract:

    --mode flow --dir DIR --preset MEDIUM --scale S
        read DIR/frame.1001.exr and DIR/frame.1002.exr (RGB float32, equal channels, grey in 0 to 1), bake them
        through the asset at that preset and analysis scale, and write DIR/flow.1001.exr: the conversion node's
        output through ROP Image, R and G the flow in Houdini's units, B validity, at the frames' full size.
    --mode pull --dir DIR
        write DIR/pulled.1001.exr: frame B pulled onto A's grid by the asset's forward flow through native
        Distort, grey in 0 to 1 in R. (Mission 4.)

Exit 0 on success, 3 for a broken environment (no licence, the asset missing), anything else for a failure. It
builds the network from the installed asset, loaded through the package file alone, and calls the same bake
function as the Bake button (cvcops_houdini.bake.bake), so the test grades what an artist would run.
"""
import argparse
import json
import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRESETS = {"MEDIUM": "dis_medium", "FAST": "dis_fast"}


def names():
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["tool"]["cvcops"]["names"]


def _raw_file(net, name, path, layer_type):
    f = net.createNode("file", name)
    f.parm("filename").set(path.replace("\\", "/"))
    f.parm("colorspace").set("raw")
    f.parm("missingdata").set("error")
    f.parm("aovs").set(1)
    f.parm("aov1").set("C")
    f.parm("type1").set(layer_type)
    f.parm("precision1").set("b32")
    f.parm("raw1").set(1)
    return f


def flow(hou, d, preset, scale):
    n = names()
    if preset not in PRESETS:
        print(f"bake_once.py: unknown preset {preset!r}; one of {sorted(PRESETS)}", file=sys.stderr)
        return 1
    tname = f"{n['hda_namespace']}::{n['hda_flow']}::1.0"
    if hou.nodeType(hou.copNodeTypeCategory(), tname) is None:
        print(f"bake_once.py: {tname} is not installed; build it with houdini/build/build_hdas.py", file=sys.stderr)
        return 3
    hou.setFrame(1001)
    net = hou.node("/obj").createNode("copnet", "bake_once")
    src = _raw_file(net, "frames", os.path.join(d, "frame.$F4.exr"), "vector")
    node = net.createNode(tname, "flow1")
    node.setInput(0, src, 0)
    tokens = [t for t in node.parm("analysis_scale").menuItems()]
    token = next((t for t in tokens if float(t) == scale), None)
    if token is None:
        print(f"bake_once.py: scale {scale} is not on the Analysis Scale menu {tokens}", file=sys.stderr)
        return 1
    node.parm("analysis_scale").set(token)
    node.parm("recipe").set(PRESETS[preset])
    node.parmTuple("frange").deleteAllKeyframes()
    node.parmTuple("frange").set((1001, 1001))
    node.parm("cache_dir").set(os.path.join(d, "cache").replace("\\", "/"))

    sys.path.insert(0, str(ROOT / "houdini" / "python3.13libs"))
    from cvcops_houdini import bake as bake_mod
    try:
        bake_mod.bake(node, n["env_prefix"])
    except bake_mod.BakeError as e:
        print(f"bake_once.py: {e}", file=sys.stderr)
        return 3 if e.code == 3 else 1

    with open(os.path.join(d, "cache", "flow.1001.json"), encoding="utf-8") as f:
        receipt = json.load(f)
    h, w = _source_size(os.path.join(d, "frame.1001.exr"))
    want = (int(w * scale), int(h * scale))
    got = (receipt["image"]["width"], receipt["image"]["height"])
    if receipt["analysis"]["scale"] != scale or got != want:
        print(f"bake_once.py: the receipt says scale {receipt['analysis']['scale']} at {got}; asked for {scale} at {want}",
              file=sys.stderr)
        return 1

    rgb = net.createNode("uvtorgb", "flow_rgb")
    rgb.setInput(0, node, 0)
    rgb.setInput(1, node, 1)
    rop = net.createNode("rop_image", "write_flow")
    rop.setInput(0, rgb, 0)
    rop.parm("copoutput").set(os.path.join(d, "flow.1001.exr").replace("\\", "/"))
    rop.parm("trange").set("off")
    rop.parm("colorconversion").set("raw")
    rop.parm("setprecision").set(1)
    rop.parm("precision").set("b32")
    rop.parm("savebackground").set(0)
    rop.parm("exportattribs").set(0)
    rop.parm("aov1").set("C")
    rop.parm("size1").set("float32")
    rop.parm("raw1").set(1)
    rop.parm("execute").pressButton()
    if rop.errors() or not os.path.isfile(os.path.join(d, "flow.1001.exr")):
        print("bake_once.py: writing flow.1001.exr failed:\n" + "\n".join(rop.errors()), file=sys.stderr)
        return 1
    return 0


def _source_size(path):
    """(height, width) of a source frame, read with the OpenEXR bundled in Houdini's Python (FACTS P1)."""
    import OpenEXR
    with OpenEXR.File(path, separate_channels=True) as f:
        return next(iter(f.channels().values())).pixels.shape[:2]


def main():
    try:
        import hou
    except ImportError:
        print("bake_once.py: no hou; the judge runs it in hython", file=sys.stderr)
        return 3
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("flow", "pull"), required=True)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--preset", default="MEDIUM")
    ap.add_argument("--scale", type=float, default=1.0)
    args = ap.parse_args()
    if args.mode == "pull":
        print("bake_once.py --mode pull: not built yet. It is Mission 4's work.", file=sys.stderr)
        return 1
    return flow(hou, os.path.abspath(args.dir), args.preset, args.scale)


if __name__ == "__main__":
    sys.exit(main())
