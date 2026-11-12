"""The two-region example's frames: a textured background and a textured disc moving differently (M3.cop.example).

    uv run python examples/two_region/make_frames.py

Writes examples/two_region/out/frames/two_region.1001.exr to .1025.exr (OD-16): 1920 by 1080, RGB float32, scene
values between 0 and 1. Per frame the background moves (2.5, -1.5) px and a disc of radius 220 moves (-6.0, 3.5) px,
in OpenCV pixels (x right, y down), the motions of the two_region threshold rows. The disc starts at (0.55 w, 0.5 h).
Also writes truth.json beside the frames, which houdini/examples/build_scene.py --check reads.
Runs in the worker's environment (numpy, cv2, OpenEXR); the output folder is git-ignored.
"""
import argparse
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import OpenEXR

ROOT = Path(__file__).resolve().parents[2]
W, H = 1920, 1080
FIRST, LAST = 1001, 1025
T_BG = (2.5, -1.5)
T_FG = (-6.0, 3.5)
RADIUS = 220
CENTER = (W * 0.55, H * 0.5)
PAD = 256                           # more than the 24 frames of motion, so sampling never leaves the canvas
TINT_BG = (1.0, 0.93, 0.84)
TINT_FG = (0.78, 0.9, 1.0)
MARK_COLOUR = (1.0, 0.45, 0.05)      # Joe's OD-21 look: saturated orange
MARK_RADIUS = 40.0                    # px
MARK_SOFT = 10.0                      # px of soft edge
KEY_FRAME = 1024
CARRY_STEPS = 8                       # 1016 to 1023


def texture(h, w, seed):
    """Smooth multi-octave noise with soft blobs, normalised to 0 to 1: enough detail at every scale for DIS."""
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w), np.float32)
    for octave, amp in [(4, 1.0), (8, 0.7), (16, 0.5), (32, 0.35), (64, 0.25)]:
        n = rng.random((h // octave + 3, w // octave + 3)).astype(np.float32)
        img += amp * cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC)
    for _ in range(400):
        c = (int(rng.integers(0, w)), int(rng.integers(0, h)))
        cv2.circle(img, c, int(rng.integers(5, 36)), float(rng.random() * 1.6), -1, lineType=cv2.LINE_AA)
    img = cv2.GaussianBlur(img, (0, 0), 0.8)
    return (img - img.min()) / (img.max() - img.min())


def sample(canvas, x, y):
    return cv2.remap(canvas, (x + PAD).astype(np.float32), (y + PAD).astype(np.float32), cv2.INTER_CUBIC,
                     borderMode=cv2.BORDER_REFLECT)


def frame(t, tb, tf, xs, ys):
    """Frame number FIRST + t: both layers sampled where their content came from."""
    cx, cy = CENTER[0] + t * T_FG[0], CENTER[1] + t * T_FG[1]
    disc = (xs - cx) ** 2 + (ys - cy) ** 2 <= RADIUS ** 2
    bg = sample(tb, xs - t * T_BG[0], ys - t * T_BG[1])
    fg = sample(tf, xs - t * T_FG[0], ys - t * T_FG[1])
    grey = np.clip(np.where(disc, fg, bg), 0.0, 1.0)
    return [np.ascontiguousarray(np.where(disc, grey * TINT_FG[c], grey * TINT_BG[c]), dtype=np.float32)
            for c in range(3)]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "examples" / "two_region" / "out" / "frames"))
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--fix", action="store_true", help="paint the OD-21 mark on the disc at the key frame")
    ap.add_argument("--check-carry", metavar="RENDERS", nargs="?", const="", default=None,
                    help="check the carried mark's centroid against the disc's true motion")
    args = ap.parse_args(argv)
    if args.check_carry is not None:
        return check_carry(args.out, args.check_carry or os.path.join(ROOT, "examples", "two_region", "out",
                                                                     "renders"))
    if args.fix:
        return write_fix(args.out)
    os.makedirs(args.out, exist_ok=True)
    tb = texture(H + 2 * PAD, W + 2 * PAD, args.seed)
    tf = texture(H + 2 * PAD, W + 2 * PAD, args.seed + 1000)
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    header = {"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage}
    for t, number in enumerate(range(FIRST, LAST + 1)):
        r, g, b = frame(t, tb, tf, xs, ys)
        path = os.path.join(args.out, f"two_region.{number}.exr")
        tmp = os.path.join(args.out, f".cvcops-two_region.{number}.exr")
        with OpenEXR.File(header, {"R": r, "G": g, "B": b}) as f:
            f.write(tmp)
        os.replace(tmp, path)
    truth = {"size": [W, H], "frames": [FIRST, LAST], "t_bg": list(T_BG), "t_fg": list(T_FG), "radius": RADIUS,
             "center_at_first": list(CENTER), "convention": "opencv_px: x right, y down, per frame", "seed": args.seed}
    with open(os.path.join(args.out, "truth.json"), "w", encoding="utf-8") as f:
        json.dump(truth, f, indent=2)
    print(f"wrote {LAST - FIRST + 1} frames {FIRST}-{LAST} at {W}x{H} and truth.json")
    return 0


def disc_centre(number):
    """The disc's centre at a frame, in opencv pixels."""
    t = number - FIRST
    return CENTER[0] + t * T_FG[0], CENTER[1] + t * T_FG[1]


def write_fix(frames_dir):
    """Paint the mark: a premultiplied RGBA EXR at the key frame, transparent except on the disc."""
    import numpy as np
    import OpenEXR
    out = os.path.join(os.path.dirname(frames_dir.rstrip("/\\")), "fix")
    os.makedirs(out, exist_ok=True)
    ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = disc_centre(KEY_FRAME)
    d = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2)
    alpha = np.clip((MARK_RADIUS + MARK_SOFT - d) / MARK_SOFT, 0.0, 1.0).astype(np.float32)
    header = {"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage}
    path = os.path.join(out, f"fix.{KEY_FRAME}.exr")
    with OpenEXR.File(header, {"R": np.ascontiguousarray(alpha * MARK_COLOUR[0]),
                              "G": np.ascontiguousarray(alpha * MARK_COLOUR[1]),
                              "B": np.ascontiguousarray(alpha * MARK_COLOUR[2]),
                              "A": np.ascontiguousarray(alpha)}) as f:
        f.write(path)
    with open(os.path.join(out, "mark.json"), "w", encoding="utf-8") as f:
        json.dump({"key_frame": KEY_FRAME, "centre": [cx, cy], "radius": MARK_RADIUS, "soft": MARK_SOFT,
                   "colour": list(MARK_COLOUR), "steps": CARRY_STEPS}, f, indent=2)
    print(f"wrote {path}: radius {MARK_RADIUS} px, soft {MARK_SOFT} px, centred ({cx:.1f}, {cy:.1f}) at {KEY_FRAME}")
    return 0


def check_carry(frames_dir, renders_dir):
    """The carried mark's centroid against the disc's true centre, in full-resolution pixels."""
    import numpy as np
    import OpenEXR
    worst, rows = 0.0, []
    for number in range(KEY_FRAME - CARRY_STEPS, KEY_FRAME + 1):
        path = os.path.join(renders_dir, f"carry.{number}.exr")
        if not os.path.isfile(path):
            print(f"missing {path}", file=sys.stderr)
            return 1
        with OpenEXR.File(path, separate_channels=True) as f:
            ch = {k: v.pixels for k, v in f.channels().items()}
        r, g, b = (np.asarray(ch[k], np.float32) for k in "RGB")
        mark = (r - b > 0.25) & (r > 0.25)          # the orange against the cool plate
        if not mark.any():
            print(f"{number}: no mark found", file=sys.stderr)
            return 1
        ys, xs = np.nonzero(mark)
        cx, cy = float(xs.mean()), float(ys.mean())
        tx, ty = disc_centre(number)
        err = float(np.hypot(cx - tx, cy - ty))
        worst = max(worst, err)
        rows.append({"frame": number, "centroid": [cx, cy], "truth": [tx, ty], "error_px": err})
        print(f"{number}: centroid ({cx:7.2f}, {cy:7.2f}) truth ({tx:7.2f}, {ty:7.2f}) error {err:5.2f} px"
              + ("  (key: the mark as painted)" if number == KEY_FRAME else ""))
    after = os.path.join(renders_dir, f"carry.{KEY_FRAME + 1}.exr")
    if os.path.isfile(after):
        with OpenEXR.File(after, separate_channels=True) as f:
            ch = {k: v.pixels for k, v in f.channels().items()}
        r, b = (np.asarray(ch[k], np.float32) for k in ("R", "B"))
        found = int(((r - b > 0.25) & (r > 0.25)).sum())
        print(f"{KEY_FRAME + 1}: {found} mark pixels (the fix must stop at the key: only forward flow is baked)")
        if found:
            return 1
    print(f"worst {worst:.2f} px over {len(rows)} frames")
    return 0 if worst <= 0.5 else 1


if __name__ == "__main__":
    sys.exit(main())
