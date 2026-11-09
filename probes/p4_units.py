"""Probe P4: which units and which v sign native Distort reads a direction in, measured, not assumed.

    uv run python probes/p4_units.py make probe_out/p4                 worker: the source blob and the direction files
    uv run python probes/hython.py probes/p4_units.py distort probe_out/p4     hython: Distort every case, write results
    uv run python probes/p4_units.py judge probe_out/p4                 worker: measure, fit, print the verdict

Two sources, 480 by 270 and 270 by 480 (not square, so pixel, texture and image space give different answers, and the
portrait one separates the longer side from the width), each holding one Gaussian blob. Each case gives Distort a
constant direction (du, dv) with du != dv, both non-zero, at Scale 1 or -1 (the pull M4 will use), either
as the Direction parameter (Direction Type: Coordinates) or as a UV layer on the `dir` input loaded by File COP from
an EXR, which is how the asset will feed it flow. Every image crosses the boundary with P3's settings (Raw, 32-bit).

The blob's centre in the output minus its centre in the source is m, the motion Distort gave the content, in
opencv_px (x right, y down). Dividing m by Scale times the direction gives pixels per unit along u and v with their signs. The
verdict names Distort's space (pixel: 1, 1; texture: w, h; image: max(w, h) / 2 on both axes, as
tests/thresholds/impls.py defines it), whether content moves along the direction or against it, and which way v
points. From that it derives houdini_units.json for a converted flow that is content motion, the way a motion-vector
AOV is: Houdini (u, v) = the forward flow in Distort's units with v flipped if v points up. The pull of M4 then
feeds Distort the converted flow at Scale -1 when content moves along the direction. MISFIT, exit 1, if the cases
disagree, the large case is capped, or no single space fits every case ("width", W / 2 on both axes, is a candidate
too, so the portrait source can rule it out).
"""
import json
import os
import sys
from pathlib import Path

SOURCES = {"land": (480, 270), "port": (270, 480)}          # w, h
SIGMA = 10.0
CASES = [  # name, source, how the direction arrives, (du, dv), Distort Scale
    ("parm_a", "land", "parm", (0.05, 0.03), 1.0),
    ("parm_b", "land", "parm", (-0.04, 0.06), 1.0),
    ("input_a", "land", "input", (0.05, 0.03), 1.0),
    ("input_b", "land", "input", (-0.04, 0.06), 1.0),
    ("input_big", "land", "input", (0.75, -0.4), 1.0),       # 180 px and 96 px: past 100 steps of 1 px, if it caps
    ("port_a", "port", "input", (0.05, 0.03), 1.0),          # longer side 480: 240 px per unit if max(w, h) / 2
    ("port_pull", "port", "input", (0.05, -0.03), -1.0),     # Scale -1, as M4's pull
]


# ---- worker half ------------------------------------------------------------------------------------------------
def _ref():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "evidence"))
    import thresholds_reference as ref
    return ref


def make(d):
    import numpy as np
    ref = _ref()
    d.mkdir(parents=True, exist_ok=True)
    for key, (W, H) in SOURCES.items():
        y, x = np.mgrid[0:H, 0:W].astype(np.float64)
        blob = np.exp(-((x - W / 2) ** 2 + (y - H / 2) ** 2) / (2 * SIGMA ** 2)).astype(np.float32)
        ref.Reference().write_exr(str(d / f"source_{key}.1001.exr"), np.dstack([blob, blob, blob]))
    for name, key, how, (du, dv), scale in CASES:
        W, H = SOURCES[key]
        if how == "input":
            img = np.zeros((H, W, 3), np.float32)
            img[..., 0], img[..., 1] = du, dv
            ref.Reference().write_exr(str(d / f"dir_{name}.1001.exr"), img)
    (d / "cases.json").write_text(json.dumps(CASES), encoding="utf-8")
    print("wrote", d)
    return 0


def centroid(img):
    import numpy as np
    g = img[..., 0].astype(np.float64)
    g = np.where(g > 0.05, g, 0.0)
    y, x = np.mgrid[0:g.shape[0], 0:g.shape[1]]
    s = g.sum()
    return float((g * x).sum() / s), float((g * y).sum() / s)


def judge(d):
    ref = _ref()
    rows, readings, spaces = [], set(), None
    for name, key, how, (du, dv), scale in CASES:
        W, H = SOURCES[key]
        c0 = centroid(ref.Reference().read_exr(str(d / f"source_{key}.1001.exr")))
        candidates = {"pixel": (1.0, 1.0), "texture": (float(W), float(H)), "image": (max(W, H) / 2.0, max(W, H) / 2.0),
                      "width": (W / 2.0, W / 2.0)}
        out = ref.Reference().read_exr(str(d / f"out_{name}.1001.exr"))
        if out.shape[:2] != (H, W):
            print(f"MISFIT: {name} came back {out.shape[:2]}, sent {(H, W)}")
            return 1
        c1 = centroid(out)
        m = (c1[0] - c0[0], c1[1] - c0[1])
        ku, kv = m[0] / (scale * du), m[1] / (scale * dv)
        hit = tuple(sp for sp, (su, sv) in candidates.items()
                    if abs(abs(ku) - su) <= 0.01 * su and abs(abs(kv) - sv) <= 0.01 * sv)
        readings.add((ku > 0, kv > 0))
        spaces = set(hit) if spaces is None else spaces & set(hit)
        rows.append({"case": name, "source_wh": [W, H], "via": how, "dir": [du, dv], "scale": scale, "content_motion_opencv_px": [round(m[0], 4), round(m[1], 4)],
                     "px_per_unit_u": round(ku, 3), "px_per_unit_v": round(kv, 3), "space_fit": list(hit)})
        print(f"{name:9} {W}x{H} via {how:5} dir ({du:+.3f}, {dv:+.3f}) scale {scale:+.0f}  content moved ({m[0]:+9.3f}, {m[1]:+9.3f}) px  "
              f"px/unit u {ku:+9.3f}  v {kv:+9.3f}  fits {list(hit)}")
    if len(readings) != 1:
        print("MISFIT: the cases disagree:", readings)
        return 1
    (u_along, v_down), = readings
    hit = sorted(spaces)
    if len(hit) != 1:
        print(f"MISFIT: no single space fits every case: {hit}")
        return 1
    distort = {"space": hit[0], "content_moves": "along the direction" if u_along else "against the direction",
               "v_points": "down" if v_down == u_along else "up"}
    # converted flow = content motion in Distort's space; opencv v (down) = v_sign * Houdini v
    units = {"space": hit[0], "v_sign": 1 if distort["v_points"] == "down" else -1}
    pull_scale = -1 if u_along else 1
    (d / "verdict.json").write_text(json.dumps({"distort": distort, "houdini_units": units,
                                                "pull_distort_scale": pull_scale, "cases": rows}, indent=1), encoding="utf-8")
    print("DISTORT:", json.dumps(distort))
    print("VERDICT houdini_units:", json.dumps(units), f"| M4 pull: Distort Scale {pull_scale} on the converted flow")
    return 0


# ---- hython half ------------------------------------------------------------------------------------------------
def distort(d):
    import hou
    hou.setFrame(1001)
    print("build", hou.applicationVersionString())
    net = hou.node("/obj").createNode("copnet", "p4")

    def read(path, uv=False):
        f = net.createNode("file")
        f.parm("filename").set(str(path).replace("\\", "/"))
        f.parm("colorspace").set("raw")
        f.parm("missingdata").set("error")
        f.parm("addaovs").pressButton()
        f.parm("precision1").set("b32")
        f.parm("raw1").set(1)
        if uv:
            f.parm("type1").set("vector2")
        return f

    srcs = {key: read(d / f"source_{key}.1001.exr") for key in SOURCES}
    cases = json.loads((d / "cases.json").read_text(encoding="utf-8"))
    for name, key, how, (du, dv), scale in cases:
        dist = net.createNode("distort", f"distort_{name}")
        dist.setInput(0, srcs[key])
        dist.parm("scale").set(scale)
        dist.parm("scalebytimeinc").set(0)
        if how == "parm":
            dist.parm("dirtype").set("coord")
            dist.parm("dirx").set(du)
            dist.parm("diry").set(dv)
        else:
            dist.setInput(1, read(d / f"dir_{name}.1001.exr", uv=True))
        rop = net.createNode("rop_image", f"write_{name}")
        rop.setInput(0, dist)
        rop.parm("copoutput").set(str(d / f"out_{name}.1001.exr").replace("\\", "/"))
        rop.parm("colorconversion").set("raw")
        rop.parm("setprecision").set(1)
        rop.parm("precision").set("b32")
        rop.parm("addaovs").pressButton()
        for i in range(1, rop.parm("aov1").parentMultiParm().eval() + 1):
            rop.parm(f"size{i}").set("float32")
            rop.parm(f"raw{i}").set(1)
        rop.parm("execute").pressButton()
        for n in (dist, rop):
            if n.errors():
                print(n.path(), "errors:", n.errors(), file=sys.stderr)
                return 1
        print(name, "distort", {p: dist.parm(p).evalAsString() for p in ("dirtype", "dirx", "diry", "scale", "filter", "border", "usecfl", "cfl", "maxsteps")},
              "dir input:", dist.input(1).type().name() if dist.input(1) else None)
    return 0


def main(argv):
    if len(argv) != 2 or argv[0] not in ("make", "distort", "judge"):
        print(__doc__, file=sys.stderr)
        return 2
    d = Path(os.path.abspath(argv[1]))
    return {"make": make, "distort": distort, "judge": judge}[argv[0]](d)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
