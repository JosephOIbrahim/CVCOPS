"""M4's Distort probe: do its step modes pull like cv2.remap, and does a large field hit the step cap?

    uv run python probes/m4_distort.py make probe_out/m4
    uv run python probes/hython.py probes/m4_distort.py cook probe_out/m4
    uv run python probes/m4_distort.py judge probe_out/m4

`make` writes thirteen cases with the worker's cv2 and numpy: the twelve non-exposure pairs of the dev suite at
540x960, plus one smooth zoom-and-rotate field reaching about 150 px on a 1920x1080 textured frame. Each case is
A, B as RGB float32 EXR and the ground-truth forward flow as `flow.exr` (R = u, G = v) in the asset's image space
(half the longer side per unit, v up), the units houdini_units.json records.

`cook` runs in hython and imports no cv2. It prints Distort's parm tokens, then for each case and for Pixels per Step
off and on, wires file_b -> distort(dir from flow.exr, Scale -1, Bilinear) -> ROP Image raw float32, and writes
<case>_pps<off|on>.exr. One hython call for the whole run.

`judge` compares each cooked frame with cv2.remap(B, p + f, INTER_LINEAR, BORDER_REPLICATE) on the 24 px interior, in
8-bit levels, and reports the pull_warp metric against A as well. It prints one line per case and mode, a verdict on
which step mode matches remap within 0.1 level, whether the large field was capped, and exits 0 when every case has at
least one mode within 1.5 levels of A.
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITE_EXCLUDE = ("exposure",)
BIG = dict(h=1080, w=1920, deg=5.0, scale=1.10, cx=0.5, cy=0.5)
INTERIOR = 24


def image_units(px_flow, h, w):
    """opencv pixel flow to the asset's image space: half the longer side per unit, v up."""
    s = max(h, w) / 2.0
    out = px_flow.astype("float32").copy()
    out[..., 0] /= s
    out[..., 1] = -out[..., 1] / s
    return out


# ---- make --------------------------------------------------------------------------------------------------------
def make(out):
    import cv2
    import numpy as np
    import OpenEXR
    sys.path.insert(0, os.path.join(ROOT, "evolve", "flow_recipe"))
    import fixtures as fx

    os.makedirs(out, exist_ok=True)
    cases = {}
    suite = fx.make_suite()
    for name in sorted(suite):
        if any(x in name for x in SUITE_EXCLUDE):
            continue
        a, b, gt, valid = suite[name]
        a = np.asarray(a, np.float32) / 255.0      # the suite is uint8; the probe works in 0 to 1
        b = np.asarray(b, np.float32) / 255.0
        cases[name] = (a, b, gt, valid)
    # one smooth zoom-and-rotate field reaching about 150 px on a textured 1920x1080 frame
    h, w = BIG["h"], BIG["w"]
    t = fx.texture(h + 2 * 96, w + 2 * 96, 909)
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    cx, cy = w * BIG["cx"], h * BIG["cy"]
    th = np.deg2rad(BIG["deg"])
    c, s = np.cos(th) * BIG["scale"], np.sin(th) * BIG["scale"]
    qx, qy = xs - cx, ys - cy
    Ax = cx + c * qx - s * qy
    Ay = cy + s * qx + c * qy
    fx_ = Ax - xs
    fy_ = Ay - ys
    a = cv2.remap(t, (xs + 96).astype(np.float32), (ys + 96).astype(np.float32), cv2.INTER_CUBIC,
                  borderMode=cv2.BORDER_REFLECT)
    b = cv2.remap(t, (xs - fx_ + 96).astype(np.float32), (ys - fy_ + 96).astype(np.float32), cv2.INTER_CUBIC,
                  borderMode=cv2.BORDER_REFLECT)   # B(x) = A(x - f), the fixture convention
    valid = np.ones((h, w), bool)
    cases["big_field"] = (a, b, np.dstack([fx_, fy_]).astype(np.float32), valid)

    hdr = lambda: {"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage}
    manifest = {}
    for name, (a, b, gt, valid) in cases.items():
        d = os.path.join(out, name)
        os.makedirs(d, exist_ok=True)
        h, w = a.shape[:2]
        for tag, img in (("A", a), ("B", b)):
            rgb = np.ascontiguousarray(np.dstack([img, img, img]).astype(np.float32))
            with OpenEXR.File(hdr(), {"R": np.ascontiguousarray(rgb[..., 0]),
                              "G": np.ascontiguousarray(rgb[..., 1]),
                              "B": np.ascontiguousarray(rgb[..., 2])}) as f:
                f.write(os.path.join(d, f"{tag}.exr"))
        uv = image_units(gt, h, w)
        with OpenEXR.File(hdr(), {"R": np.ascontiguousarray(uv[..., 0]), "G": np.ascontiguousarray(uv[..., 1])}) as f:
            f.write(os.path.join(d, "flow.exr"))
        np.save(os.path.join(d, "a.npy"), a.astype(np.float32))
        np.save(os.path.join(d, "b.npy"), b.astype(np.float32))
        np.save(os.path.join(d, "gt.npy"), gt.astype(np.float32))
        np.save(os.path.join(d, "valid.npy"), valid.astype(bool))
        manifest[name] = {"h": int(h), "w": int(w),
                          "max_px": float(np.hypot(gt[..., 0], gt[..., 1]).max()),
                          "mean_px": float(np.hypot(gt[..., 0], gt[..., 1]).mean())}
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)
    print(f"wrote {len(manifest)} cases to {out}")
    for name, m in sorted(manifest.items()):
        print(f"  {name:<22} {m['w']}x{m['h']}  motion mean {m['mean_px']:.1f} px, max {m['max_px']:.1f} px")
    return 0


# ---- cook (hython) -----------------------------------------------------------------------------------------------
def cook(out):
    try:
        import hou
    except ImportError:
        print("m4_distort.py cook: no hou; run it with probes/hython.py", file=sys.stderr)
        return 3
    manifest = json.load(open(os.path.join(out, "manifest.json")))
    hou.setFrame(1001)
    net = hou.node("/obj").createNode("copnet", "m4_distort")

    probe = net.createNode("distort", "tokens")
    parms = []
    for t in probe.type().parmTemplates():
        if t.type() in (hou.parmTemplateType.Menu, hou.parmTemplateType.Toggle, hou.parmTemplateType.Int,
                        hou.parmTemplateType.Float):
            items = t.menuItems() if t.type() == hou.parmTemplateType.Menu else ()
            parms.append({"name": t.name(), "label": t.label(), "type": str(t.type()).split(".")[-1],
                          "menu": [list(x)[:2] if isinstance(x, (tuple, list)) else [x, x] for x in items],
                          "default": str(t.defaultValue())})
    with open(os.path.join(out, "distort_parms.json"), "w") as f:
        json.dump(parms, f, indent=1)
    pps = [p for p in parms if "pixels" in p["label"].lower() or "step" in p["label"].lower()]
    print("Distort parms matching step or pixels:", [(p["name"], p["label"], p["menu"]) for p in pps])
    probe.destroy()

    results = {}
    for name, m in sorted(manifest.items()):
        d = os.path.join(out, name)
        safe = name.replace("#", "_").replace("-", "_")
        b = net.createNode("file", f"b_{safe}")
        b.parm("filename").set(os.path.join(d, "B.exr").replace("\\", "/"))
        b.parm("colorspace").set("raw")
        b.parm("missingdata").set("error")
        b.parm("aovs").set(1)
        b.parm("aov1").set("C")
        b.parm("type1").set("vector")
        b.parm("precision1").set("b32")
        b.parm("raw1").set(1)
        flow = net.createNode("file", f"f_{safe}")
        flow.parm("filename").set(os.path.join(d, "flow.exr").replace("\\", "/"))
        flow.parm("colorspace").set("raw")
        flow.parm("missingdata").set("error")
        flow.parm("aovs").set(1)
        flow.parm("aov1").set("C")
        flow.parm("type1").set("vector2")
        flow.parm("precision1").set("b32")
        flow.parm("raw1").set(1)
        for mode in ("off", "on"):
            ds = net.createNode("distort", f"d_{safe}_{mode}")
            ds.setInput(0, b, 0)
            ds.setInput(1, flow, 0)
            ds.parm("scale").set(-1.0)
            ds.parm("filter").set("bilinear")
            ds.parm("scalebytimeinc").set(0)
            ds.parm("usecfl").set(1 if mode == "on" else 0)   # Pixels per Step; the 22.0.492 default is on

            rop = net.createNode("rop_image", f"r_{safe}_{mode}")
            rop.setInput(0, ds, 0)
            rop.parm("copoutput").set(os.path.join(d, f"pps{mode}.exr").replace("\\", "/"))
            rop.parm("trange").set("off")
            rop.parm("colorconversion").set("raw")
            rop.parm("savebackground").set(0)
            rop.parm("exportattribs").set(0)
            rop.parm("setprecision").set(1)
            rop.parm("precision").set("b32")
            rop.parm("aov1").set("C")
            rop.parm("size1").set("float32")
            rop.parm("raw1").set(1)
            rop.parm("execute").pressButton()
            errs = rop.errors()
            if errs:
                print(f"cook {name} {mode}: {errs}", file=sys.stderr)
                results[f"{name}_{mode}"] = "error"
            else:
                results[f"{name}_{mode}"] = "ok"
        print(f"cooked {name}", flush=True)
    print(json.dumps({"cases": len(manifest), "parms": [p["name"] for p in pps]}))
    return 0


# ---- judge -------------------------------------------------------------------------------------------------------
def judge(out):
    import cv2
    import numpy as np
    import OpenEXR
    manifest = json.load(open(os.path.join(out, "manifest.json")))

    def read(path):
        with OpenEXR.File(path, separate_channels=True) as f:
            ch = {k: v.pixels for k, v in f.channels().items()}
        return np.asarray(ch["R"], np.float32)

    rows, ok = {}, True
    print(f"{'case':<22} {'mode':<4} {'vs remap':>9} {'vs A':>7}")
    for name, m in sorted(manifest.items()):
        d = os.path.join(out, name)
        b = np.load(os.path.join(d, "b.npy"))
        gt = np.load(os.path.join(d, "gt.npy"))
        ys, xs = np.mgrid[0:b.shape[0], 0:b.shape[1]].astype(np.float32)
        ref = cv2.remap(b, xs + gt[..., 0], ys + gt[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        keep = np.zeros(b.shape, bool)
        keep[INTERIOR:-INTERIOR, INTERIOR:-INTERIOR] = True
        a = np.load(os.path.join(d, "a.npy"))
        for mode in ("off", "on"):
            path = os.path.join(d, f"pps{mode}.exr")
            if not os.path.isfile(path):
                print(f"{name:<22} {mode:<4} {'missing':>9}")
                rows[f"{name}_{mode}"] = None
                ok = False
                continue
            got = read(path)
            vs_remap = float(np.abs(got - ref)[keep].mean() * 255.0)
            vs_a = float(np.abs(got - a)[keep].mean() * 255.0)
            rows[f"{name}_{mode}"] = {"vs_remap": vs_remap, "vs_a": vs_a}
            print(f"{name:<22} {mode:<4} {vs_remap:9.3f} {vs_a:7.3f}")
        best = min(v["vs_a"] for k, v in rows.items() if k.startswith(name + "_") and v)
        if best > 1.5 and name != "big_field":
            ok = False
            print(f"  {name}: best mode misses 1.5 levels against A ({best:.2f})")
    suite = {k: v for k, v in rows.items() if v and not k.startswith("big_field")}
    off = [v["vs_remap"] for k, v in suite.items() if k.endswith("_off")]
    on = [v["vs_remap"] for k, v in suite.items() if k.endswith("_on")]
    big = rows.get("big_field_off"), rows.get("big_field_on")   # the step-cap case, graded separately
    best_mode = "off" if (off and max(off) <= 0.1 and (not on or max(on) > max(off))) else (
        "on" if (on and max(on) <= 0.1) else "neither")
    verdict = {"step_mode": best_mode, "max_vs_remap_off": max(off) if off else None,
               "max_vs_remap_on": max(on) if on else None,
               "big_field": {k: v for k, v in (("off", big[0]), ("on", big[1])) if v},
               "large_field_capped": bool(big[1] and big[1]["vs_a"] > (big[0]["vs_a"] if big[0] else 0) + 1.0)}
    with open(os.path.join(out, "verdict.json"), "w") as f:
        json.dump({"rows": rows, "verdict": verdict}, f, indent=1, sort_keys=True)
    print("VERDICT " + json.dumps(verdict, sort_keys=True))
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="M4 Distort probe.")
    ap.add_argument("step", choices=("make", "cook", "judge"))
    ap.add_argument("dir")
    a = ap.parse_args()
    return {"make": make, "cook": cook, "judge": judge}[a.step](os.path.abspath(a.dir))


if __name__ == "__main__":
    sys.exit(main())
