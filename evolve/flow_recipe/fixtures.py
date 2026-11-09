"""Deterministic optical-flow fixtures with exact ground truth. numpy + cv2 only.

Every fixture returns (A_u8, B_u8, gt_flow, gt_valid):
  A_u8, B_u8 : uint8 HxW analysis images
  gt_flow    : float32 HxWx2, forward flow on A's grid, OpenCV pixel convention (x right, y down)
  gt_valid   : bool HxW, False where the pixel is occluded in B or leaves the frame
The evaluator owns this file. Candidates never see it.
"""
import numpy as np, cv2

PAD = 96

def texture(h, w, seed):
    rng = np.random.default_rng(seed)
    img = np.zeros((h, w), np.float32)
    for octave, amp in [(4, 1.0), (8, 0.7), (16, 0.5), (32, 0.35), (64, 0.25)]:
        n = rng.random((h // octave + 3, w // octave + 3)).astype(np.float32)
        img += amp * cv2.resize(n, (w, h), interpolation=cv2.INTER_CUBIC)
    for _ in range(60):
        c = (int(rng.integers(0, w)), int(rng.integers(0, h)))
        cv2.circle(img, c, int(rng.integers(5, 36)), float(rng.random() * 1.6), -1, lineType=cv2.LINE_AA)
    img = cv2.GaussianBlur(img, (0, 0), 0.8)
    return (img - img.min()) / (img.max() - img.min())

def _grid(h, w):
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    return xs, ys

def _sample(canvas, x, y):
    return cv2.remap(canvas, (x + PAD).astype(np.float32), (y + PAD).astype(np.float32), cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)

def _u8(img):
    return np.clip(np.rint(img * 255.0), 0, 255).astype(np.uint8)

def _finish(h, w, A, B, fx, fy, valid=None):
    xs, ys = _grid(h, w)
    inb = (xs + fx >= 0) & (xs + fx <= w - 1) & (ys + fy >= 0) & (ys + fy <= h - 1)
    valid = inb if valid is None else (valid & inb)
    return _u8(A), _u8(B), np.dstack([fx, fy]).astype(np.float32), valid

def translation(h, w, seed, t=(3.4, -2.2)):
    T = texture(h + 2 * PAD, w + 2 * PAD, seed); xs, ys = _grid(h, w)
    A = _sample(T, xs, ys); B = _sample(T, xs - t[0], ys - t[1])
    return _finish(h, w, A, B, np.full((h, w), t[0], np.float32), np.full((h, w), t[1], np.float32))

def similarity(h, w, seed, deg=1.6, scale=1.02, t=(1.5, 0.8)):
    T = texture(h + 2 * PAD, w + 2 * PAD, seed); xs, ys = _grid(h, w)
    cx, cy = (w - 1) / 2, (h - 1) / 2; th = np.deg2rad(deg); c, s = np.cos(th) * scale, np.sin(th) * scale
    Fx = cx + c * (xs - cx) - s * (ys - cy) + t[0]; Fy = cy + s * (xs - cx) + c * (ys - cy) + t[1]   # forward map on A grid
    qx, qy = xs - cx - t[0], ys - cy - t[1]; d = c * c + s * s                                       # analytic inverse on B grid
    px = cx + (c * qx + s * qy) / d; py = cy + (-s * qx + c * qy) / d
    return _finish(h, w, _sample(T, xs, ys), _sample(T, px, py), Fx - xs, Fy - ys)

def jelly(h, w, seed, amp=5.0, lam=(210.0, 170.0)):
    T = texture(h + 2 * PAD, w + 2 * PAD, seed); xs, ys = _grid(h, w)
    def d(x, y):
        return amp * np.sin(2 * np.pi * y / lam[0] + 0.7), amp * np.sin(2 * np.pi * x / lam[1] + 1.9)
    fx, fy = d(xs, ys)
    px, py = xs.copy(), ys.copy()                       # invert q = p + d(p) by fixed point (|grad d| < 1)
    for _ in range(40):
        dx, dy = d(px, py); px, py = xs - dx, ys - dy
    return _finish(h, w, _sample(T, xs, ys), _sample(T, px, py), fx.astype(np.float32), fy.astype(np.float32))

def layered(h, w, seed, t_bg=(1.2, 0.6), t_fg=(-9.0, 4.0), radius=70):
    Tb = texture(h + 2 * PAD, w + 2 * PAD, seed); Tf = texture(h + 2 * PAD, w + 2 * PAD, seed + 1000); xs, ys = _grid(h, w)
    cx, cy = w * 0.55, h * 0.5
    def M(x, y): return (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2            # foreground disc in A coordinates
    A = np.where(M(xs, ys), _sample(Tf, xs, ys), _sample(Tb, xs, ys))
    fgB = M(xs - t_fg[0], ys - t_fg[1])                                         # disc as seen in B
    B = np.where(fgB, _sample(Tf, xs - t_fg[0], ys - t_fg[1]), _sample(Tb, xs - t_bg[0], ys - t_bg[1]))
    inA = M(xs, ys)
    fx = np.where(inA, t_fg[0], t_bg[0]).astype(np.float32); fy = np.where(inA, t_fg[1], t_bg[1]).astype(np.float32)
    occluded = (~inA) & M(xs + t_bg[0] - t_fg[0], ys + t_bg[1] - t_fg[1])       # background pixel covered by the disc in B
    return _finish(h, w, A, B, fx, fy, ~occluded)

def exposure(h, w, seed, t=(-2.6, 1.4), gain=1.25, offset=0.04, noise=0.01):
    T = texture(h + 2 * PAD, w + 2 * PAD, seed); xs, ys = _grid(h, w)
    A = _sample(T, xs, ys); B = _sample(T, xs - t[0], ys - t[1])
    rng = np.random.default_rng(seed + 7)
    B = np.clip(gain * B + offset + rng.normal(0, noise, B.shape).astype(np.float32), 0, 1)
    return _finish(h, w, A, B, np.full((h, w), t[0], np.float32), np.full((h, w), t[1], np.float32))

SUITE = {"translation": translation, "similarity": similarity, "jelly": jelly, "layered": layered, "exposure": exposure}


def draw(kind, rng):
    """Motion parameters for one fixture, drawn from fixed ranges. Dev and holdout share these ranges."""
    u = lambda lo, hi: float(rng.uniform(lo, hi))
    if kind == "translation":
        return dict(t=(u(-8, 8), u(-8, 8)))
    if kind == "similarity":
        return dict(deg=u(-3, 3), scale=u(0.97, 1.03), t=(u(-3, 3), u(-3, 3)))
    if kind == "jelly":
        return dict(amp=u(3, 6), lam=(u(140, 260), u(140, 260)))
    if kind == "layered":
        tb = (u(-2, 2), u(-2, 2))
        while True:
            tf = (u(-10, 10), u(-10, 10))
            if np.hypot(tf[0] - tb[0], tf[1] - tb[1]) >= 4:
                break
        return dict(t_bg=tb, t_fg=tf, radius=int(u(45, 80)))
    if kind == "exposure":
        return dict(t=(u(-6, 6), u(-6, 6)), gain=u(0.75, 1.3), offset=u(0, 0.08), noise=u(0.005, 0.02))
    raise ValueError(kind)


def make_suite(base=11, n=3, h=540, w=960):
    """n pairs of every motion kind. Texture and motion both come from the seed."""
    s = {}
    for i in range(n):
        for k, (kind, fn) in enumerate(SUITE.items()):
            seed = base + 1000 * i + 17 * k
            s[f"{kind}#{i}"] = fn(h, w, seed, **draw(kind, np.random.default_rng(seed)))
    return s


def make_holdout(base=90001, n=5, h=540, w=960):
    """Same distribution, seeds never used during a run. Only promote.py reads it."""
    return make_suite(base, n, h, w)


def epe_metrics(flow, gt_flow, gt_valid, margin=24, block=32):
    """Mean, p95 and worst-block endpoint error over valid interior pixels."""
    e = np.sqrt(((flow - gt_flow) ** 2).sum(-1))
    v = gt_valid.copy(); v[:margin] = v[-margin:] = False; v[:, :margin] = v[:, -margin:] = False
    h, w = e.shape; hb, wb = h // block, w // block
    eb = np.where(v, e, 0.0)[:hb * block, :wb * block].reshape(hb, block, wb, block).sum((1, 3))
    nb = v[:hb * block, :wb * block].reshape(hb, block, wb, block).sum((1, 3))
    ok = nb >= (block * block) // 2
    worst = float((eb[ok] / nb[ok]).max()) if ok.any() else float("inf")
    return {"mean": float(e[v].mean()), "p95": float(np.percentile(e[v], 95)), "worst_block": worst}

