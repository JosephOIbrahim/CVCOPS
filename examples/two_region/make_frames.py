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
    args = ap.parse_args(argv)
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


if __name__ == "__main__":
    sys.exit(main())
