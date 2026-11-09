"""Reference demos for three motion opportunities, on synthetic frames where the right answer is known.

    uv run python evidence/opportunities_reference.py

Each demo uses only the five-method seam the threshold tests grade (flow, valid, pull), through the stock
reference in thresholds_reference.py, so the same code can later grade the product. These are demonstrations,
not locked thresholds: when an opportunity becomes a mission, its rows are chosen from fresh draws, added to
the blueprint's table, and locked by Joe like every other row (docs/OPPORTUNITIES.md).

  temporal   Rank frames by change the flow cannot explain. Two problems are planted in 16 frames.
  carry      Paint a mark on frame A and pull it onto frame B with the flow from B back to A.
  emit       Seed points only where something moves and the flow is trusted.
"""
import sys

import cv2
import numpy as np

import thresholds_reference as tr
import fixtures as fx


def temporal(impl, n=16, pop=6, flick=11, h=360, w=640):
    """Frame scores in 8-bit levels: the smaller of a frame's two neighbour residuals, on trusted pixels."""
    bg = fx.texture(h + 2 * fx.PAD, w + 2 * fx.PAD, 31)
    fg = fx.texture(h + 2 * fx.PAD, w + 2 * fx.PAD, 1031)
    xs, ys = fx._grid(h, w)
    cx, cy, r, tb, tf = w * 0.35, h * 0.5, 60, (1.0, 0.4), (5.0, -1.5)
    frames = []
    for k in range(n):
        disc = (xs - k * tf[0] - cx) ** 2 + (ys - k * tf[1] - cy) ** 2 <= r ** 2
        img = np.where(disc, fx._sample(fg, xs - k * tf[0], ys - k * tf[1]), fx._sample(bg, xs - k * tb[0], ys - k * tb[1]))
        frames.append(img.astype(np.float32))
    blotch = np.exp(-(((xs - 470) ** 2 + (ys - 110) ** 2) / (2 * 26.0 ** 2))).astype(np.float32)
    frames[pop] = frames[pop] + 0.45 * blotch            # a local pop on one frame
    frames[flick] = frames[flick] * 1.08                 # the whole frame 8% brighter for one frame
    frames = [fx._u8(np.clip(f, 0, 1)) for f in frames]
    pair = []
    for a, b in zip(frames, frames[1:]):
        ok = impl.valid(a, b)
        pair.append(float(np.abs(a.astype(np.float32) - impl.pull(a, b))[ok].mean()))
    return [min(pair[max(k - 1, 0):k + 1]) for k in range(n)]


def carry(impl, motion=(22.0, 9.0)):
    """Where a painted mark lands on frame B, minus where it was painted on A, in pixels."""
    a, b, _, _ = fx.layered(540, 960, seed=44, t_bg=(1.5, 0.5), t_fg=motion, radius=110)
    paint = np.zeros((540, 960), np.float32)
    cv2.circle(paint, (int(960 * 0.55) + 28, 270 - 22), 20, 1.0, -1, lineType=cv2.LINE_AA)
    back = impl.flow(b, a)                                # where each pixel of B came from in A
    yy, xx = np.mgrid[0:540, 0:960].astype(np.float32)
    carried = cv2.remap(paint, xx + back[..., 0], yy + back[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    centre = lambda m: np.array([(m * xx).sum(), (m * yy).sum()]) / m.sum()
    return centre(carried) - centre(paint)


def emit(impl, n=9000, threshold_px=4.0, motion=(12.0, -7.0), radius=120):
    """Seeds kept, and the share of them that lie on the moving disc."""
    a, b, _, _ = fx.layered(540, 960, seed=57, t_bg=(0.4, 0.2), t_fg=motion, radius=radius)
    f, ok = impl.flow(a, b), impl.valid(a, b)
    mag = np.hypot(f[..., 0], f[..., 1])
    pts = np.random.default_rng(5).uniform([0, 0], [959, 539], size=(n, 2))
    kept = np.array([(x, y) for x, y in pts if mag[int(y), int(x)] > threshold_px and ok[int(y), int(x)]])
    on_disc = np.hypot(kept[:, 0] - 960 * 0.55, kept[:, 1] - 270) <= radius + 2
    return len(kept), float(on_disc.mean())


def main():
    impl, failed = tr.Reference(), 0

    def row(ok, text):
        nonlocal failed
        failed += not ok
        print(("  PASS  " if ok else "  FAIL  ") + text)

    scores = temporal(impl)
    order = sorted(range(len(scores)), key=lambda k: -scores[k])
    median, rest = float(np.median(scores)), max(s for k, s in enumerate(scores) if k not in (6, 11))
    print("temporal: frame scores in 8-bit levels, 16 frames, a pop planted on frame 7 and a flicker on frame 12")
    row(sorted(order[:2]) == [6, 11], f"the two planted frames rank first: {scores[6]:.2f} and {scores[11]:.2f}; the next frame scores {rest:.2f}")
    row(min(scores[6], scores[11]) >= 2.0 * median, f"each is at least twice the median of {median:.2f}")

    moved = carry(impl)
    print("carry: a mark painted on frame A, pulled onto frame B; the disc under it moved (22, 9) px")
    row(float(np.abs(moved - (22.0, 9.0)).max()) <= 0.5, f"the mark moved ({moved[0]:.2f}, {moved[1]:.2f}) px")

    kept, share = emit(impl)
    print("emit: 9,000 random seeds, kept where the motion exceeds 4 px and the flow is trusted")
    row(kept > 0 and share >= 0.95, f"{kept} seeds kept, {share:.1%} of them on the moving disc")

    print("CHECK: " + ("every demo holds" if not failed else f"{failed} demo row(s) failed"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
