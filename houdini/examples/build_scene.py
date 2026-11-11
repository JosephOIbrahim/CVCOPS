"""The two-region example scene: frames -> cvcops::flow::1.0 -> arrows, baked and optionally saved (M3.cop.example).

    uv run python examples/two_region/make_frames.py
    uv run python probes/hython.py houdini/examples/build_scene.py --check --save

Runs in hython and never imports cv2. The scene file sits in examples/two_region/out/ (git-ignored), so every path in
it is relative to $HIP: frames from $HIP/frames/two_region.$F4.exr, the cache at the asset's default
$HIP/cvcops/$OS. The scene range is 1001 to 1025 at 24 fps, so the asset's default Frame Range ($FSTART to $FEND-1)
bakes 1001 to 1024.

    example_network(parent, frames)  the File COP (Raw, 32-bit, Report Message) -> the asset -> Visualize Velocity
                                     (Quiver Plot), plus UV to RGB of the flow; returns the nodes by name.
                                     houdini/tests/bake_timing.py builds the same network in memory.

It reports the source File COP's colour-space menu, bakes through cvcops_houdini.bake.bake (the Bake button's
function), renders the arrows and the flow as RGB to EXR at 1001, 1012 and 1024 under out/renders/, and with --check
reads the cached flow and requires the median motion of the background and of the disc in every pair to be within
0.1 px of the truth make_frames.py wrote. --save saves the scene (Joe's go-ahead, 11 Nov, OD-16) and prints the
file name, extension included. Exit 0 done, 1 a failed check or step, 3 without hou or the asset.
"""
import argparse
import json
import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "examples" / "two_region" / "out"
FIRST, LAST = 1001, 1025
RENDER_FRAMES = (1001, 1012, 1024)
TOLERANCE_PX = 0.1
EDGE_PX = 8


def names():
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["tool"]["cvcops"]["names"]


def raw_file(net, name, pattern, colorspace="raw"):
    """A File COP the way the asset expects its source: Raw (or the given colour space), 32-bit, Report Message."""
    f = net.createNode("file", name)
    f.parm("filename").set(pattern)
    f.parm("colorspace").set(colorspace)
    f.parm("missingdata").set("error")
    f.parm("aovs").set(1)
    f.parm("aov1").set("C")
    f.parm("type1").set("vector")
    f.parm("precision1").set("b32")
    f.parm("raw1").set(1)
    return f


def example_network(hou, parent, frames, colorspace="raw", name="two_region"):
    """Build the example network under parent; frames is a File COP pattern. Returns {name: node}."""
    n = names()
    tname = f"{n['hda_namespace']}::{n['hda_flow']}::1.0"
    if hou.nodeType(hou.copNodeTypeCategory(), tname) is None:
        raise LookupError(f"{tname} is not installed; build it with houdini/build/build_hdas.py")
    net = parent.createNode("copnet", name)
    src = raw_file(net, "frames", frames, colorspace)
    flow = net.createNode(tname, "flow1")
    flow.setInput(0, src, 0)
    arrows = net.createNode("visualizevelocity", "arrows")
    arrows.setInput(0, flow, 0)
    arrows.parm("method").set("quiver")
    arrows.parm("quiver_visbyspeed").set(0)     # the example moves a few px, a few thousandths of a unit: by speed
                                                # the arrows would render nearly black (H36)
    rgb =net.createNode("uvtorgb", "flow_rgb")
    rgb.setInput(0, flow, 0)
    rgb.setInput(1, flow, 1)
    net.layoutChildren()
    return {"net": net, "frames": src, "flow": flow, "arrows": arrows, "flow_rgb": rgb}


def render(hou, net, source, path, frame):
    rop = net.node(f"render_{source.name()}") or net.createNode("rop_image", f"render_{source.name()}")
    rop.setInput(0, source, 0)
    rop.parm("copoutput").set(path)
    rop.parm("trange").set("off")
    rop.parm("colorconversion").set("raw")
    rop.parm("savebackground").set(0)
    rop.parm("exportattribs").set(0)
    hou.setFrame(frame)
    rop.parm("execute").pressButton()
    if rop.errors() or not os.path.isfile(hou.text.expandString(path)):
        raise RuntimeError(f"rendering {path} at {frame} failed: {rop.errors()}")


def set_scene_range(hou, first, last, fps=24.0):
    hou.setFps(fps)
    hou.hscript(f"tset {(first - 1) / fps} {last / fps}")
    hou.playbar.setPlaybackRange(first, last)
    got = (int(hou.hscriptExpression("$FSTART")), int(hou.hscriptExpression("$FEND")))
    if got != (first, last):
        raise RuntimeError(f"the scene range is {got}, not {(first, last)}")


def check_medians(flow_dir, truth):
    """The median cached flow (opencv_px) of the background and of the disc in each pair, against the truth."""
    import numpy as np
    import OpenEXR
    w, h = truth["size"]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float64)
    tb, tf, radius = truth["t_bg"], truth["t_fg"], truth["radius"]
    cx0, cy0 = truth["center_at_first"]
    worst, rows = 0.0, []
    for t, frame in enumerate(range(truth["frames"][0], truth["frames"][1])):
        with OpenEXR.File(os.path.join(flow_dir, f"flow.{frame}.exr"), separate_channels=True) as f:
            ch = {k: v.pixels.astype(np.float64) for k, v in f.channels().items()}
        u, v, valid = ch["R"], ch["G"], ch["B"] >= 0.5
        cx, cy = cx0 + t * tf[0], cy0 + t * tf[1]
        d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
        inner = (xs >= EDGE_PX) & (xs < w - EDGE_PX) & (ys >= EDGE_PX) & (ys < h - EDGE_PX) & valid
        disc = inner & (d <= radius - EDGE_PX)
        bg = inner & (d >= radius + EDGE_PX + np.hypot(tf[0] - tb[0], tf[1] - tb[1]))
        got = {"bg": (float(np.median(u[bg])), float(np.median(v[bg]))),
               "disc": (float(np.median(u[disc])), float(np.median(v[disc])))}
        err = max(abs(got["bg"][0] - tb[0]), abs(got["bg"][1] - tb[1]),
                  abs(got["disc"][0] - tf[0]), abs(got["disc"][1] - tf[1]))
        worst = max(worst, err)
        rows.append({"pair": frame, "bg": got["bg"], "disc": got["disc"], "error_px": err})
    return worst, rows


def main():
    try:
        import hou
    except ImportError:
        print("build_scene.py: no hou; run it with probes/hython.py", file=sys.stderr)
        return 3
    ap = argparse.ArgumentParser(description="Build, bake and render the two-region example scene.")
    ap.add_argument("--out", default=str(OUT), help="the scene folder ($HIP); frames are read from <out>/frames")
    ap.add_argument("--check", action="store_true", help="require the median motions within 0.1 px of the truth")
    ap.add_argument("--save", action="store_true", help="save the scene into --out (Joe's go-ahead, OD-16)")
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    frames_dir = os.path.join(out, "frames")
    with open(os.path.join(frames_dir, "truth.json"), encoding="utf-8") as f:
        truth = json.load(f)

    hou.hipFile.clear(suppress_save_prompt=True)
    hou.hipFile.setName(os.path.join(out, "two_region.hip").replace("\\", "/"))
    set_scene_range(hou, FIRST, LAST)
    hou.setFrame(FIRST)
    try:
        nodes = example_network(hou, hou.node("/obj"), "$HIP/frames/two_region.$F4.exr")
    except LookupError as e:
        print(f"build_scene.py: {e}", file=sys.stderr)
        return 3
    menu = nodes["frames"].parm("colorspace").menuItems()
    print(f"source File COP colorspace: set to {nodes['frames'].parm('colorspace').evalAsString()!r}; "
          f"{len(menu)} menu items, 'raw' {'present' if 'raw' in menu else 'MISSING'}; first items {list(menu[:6])}")
    if "raw" not in menu:
        return 1

    flow = nodes["flow"]
    frange = tuple(int(v) for v in flow.parmTuple("frange").eval())
    cache = flow.parm("cache_dir").evalAsString()
    print(f"Frame Range from the asset's default: {frange}; cache {os.path.relpath(cache, out)}")
    from cvcops_houdini import bake as bake_mod
    try:
        times = bake_mod.bake(flow, names()["env_prefix"])
    except bake_mod.BakeError as e:
        print(f"build_scene.py: the bake failed: {e}", file=sys.stderr)
        return 3 if e.code == 3 else 1
    print("bake: " + ", ".join(f"{k} {v:.2f} s" for k, v in times.items()))

    renders = os.path.join(out, "renders")
    os.makedirs(renders, exist_ok=True)
    for frame in RENDER_FRAMES:
        for key in ("arrows", "flow_rgb"):
            render(hou, nodes["net"], nodes[key], f"$HIP/renders/{key}.{frame}.exr", frame)
    hou.setFrame(FIRST)
    print(f"rendered arrows and flow_rgb at {RENDER_FRAMES} into {os.path.relpath(renders, out)}")

    code = 0
    if args.check:
        worst, rows = check_medians(cache, truth)
        with open(os.path.join(out, "check.json"), "w", encoding="utf-8") as f:
            json.dump({"worst_px": worst, "tolerance_px": TOLERANCE_PX, "pairs": rows}, f, indent=2)
        first = rows[0]
        print(f"check: worst median error {worst:.4f} px over {len(rows)} pairs (limit {TOLERANCE_PX}); pair "
              f"{first['pair']}: background ({first['bg'][0]:.3f}, {first['bg'][1]:.3f}) against {tuple(truth['t_bg'])}, "
              f"disc ({first['disc'][0]:.3f}, {first['disc'][1]:.3f}) against {tuple(truth['t_fg'])}")
        code = 0 if worst <= TOLERANCE_PX else 1
    if args.save:
        hou.hipFile.save(save_to_recent_files=False)
        saved = hou.hipFile.path()
        print(f"saved {os.path.relpath(saved, out)} (extension {os.path.splitext(saved)[1]})")
    return code


if __name__ == "__main__":
    sys.exit(main())
