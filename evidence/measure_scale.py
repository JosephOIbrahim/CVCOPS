"""What does analysis scale 0.5 buy and cost, timed on the same frames? Sandbox reference for FACTS M18.

    python evidence/measure_scale.py

The two-region fixture at 1920x1080, DIS MEDIUM. Each scale is timed end to end: the downscale of both frames,
the flow, and the upscale of the vectors. Runs are interleaved and the minimum of several is kept."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evolve", "flow_recipe"))
import numpy as np, cv2
import fixtures as fx

def med(a, b): return cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM).calc(a, b, None)
def at_scale(a, b, s):
    if s == 1.0: return med(a, b)
    h, w = a.shape
    sa = cv2.resize(a, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA); sb = cv2.resize(b, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return cv2.resize(med(sa, sb), (w, h), interpolation=cv2.INTER_LINEAR) / s

h, w, R = 1080, 1920, 220
rows = []
for seed in (5, 6, 7):
    a, b, gt, valid = fx.layered(h, w, seed, t_bg=(2.5, -1.5), t_fg=(-6.0, 3.5), radius=R)
    ys, xs = np.mgrid[0:h, 0:w]; d = np.sqrt((xs - w * 0.55) ** 2 + (ys - h * 0.5) ** 2)
    keep = valid & (np.abs(d - R) >= 8); keep[:24] = keep[-24:] = False; keep[:, :24] = keep[:, -24:] = False
    best = {1.0: 1e9, 0.5: 1e9, 0.25: 1e9}; err = {}
    for s in best: at_scale(a, b, s)                                   # warm-up
    for _ in range(7):
        for s in best:                                                 # interleaved
            t0 = time.perf_counter(); f = at_scale(a, b, s); best[s] = min(best[s], time.perf_counter() - t0)
            err[s] = float(np.sqrt(((f - gt) ** 2).sum(-1))[keep].mean())
    rows.append((seed, best, err))
    print(f"seed {seed}: " + " | ".join(f"scale {s}: {best[s]*1000:6.1f} ms, {err[s]:.3f} px" for s in best))
for s in (0.5, 0.25):
    sp = [r[1][1.0] / r[1][s] for r in rows]; de = [r[2][s] - r[2][1.0] for r in rows]
    print(f"scale {s} against 1.0: {min(sp):.1f} to {max(sp):.1f} times faster, {min(de):.3f} to {max(de):.3f} px more error")
print(f"threads {cv2.getNumThreads()}, OpenCV {cv2.__version__}")
