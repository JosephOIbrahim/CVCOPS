"""Sandbox references for the M3 and M4 thresholds. Run from any directory.
M3: two regions moving differently (dx != dy, both non-zero), flow estimated at analysis scale 1.0 and 0.5,
    error in full-resolution pixels over valid pixels at least 8 px from the region boundary.
M4: frame B pulled onto A's grid with the stored forward flow, compared with frame A, 8-bit levels."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evolve", "flow_recipe"))
import numpy as np, cv2
import fixtures as fx

def med(a, b): return cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM).calc(a, b, None)

def at_scale(a, b, s):
    if s == 1.0: return med(a, b)
    h, w = a.shape; sa = cv2.resize(a, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA); sb = cv2.resize(b, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return cv2.resize(med(sa, sb), (w, h), interpolation=cv2.INTER_LINEAR) / s

print("M3: two-region fixture, 1920x1080 full resolution, MEDIUM, mean EPE in full-resolution px (valid, >= 8 px from boundary)")
for seed in (5, 6, 7):
    h, w = 1080, 1920
    a, b, gt, valid = fx.layered(h, w, seed, t_bg=(2.5, -1.5), t_fg=(-6.0, 3.5), radius=220)
    ys, xs = np.mgrid[0:h, 0:w]; d = np.sqrt((xs - w * 0.55) ** 2 + (ys - h * 0.5) ** 2)
    keep = valid & (np.abs(d - 220) >= 8); keep[:24] = keep[-24:] = False; keep[:, :24] = keep[:, -24:] = False
    row = []
    for s in (1.0, 0.5):
        f = at_scale(a, b, s); e = np.sqrt(((f - gt) ** 2).sum(-1))
        row.append(f"scale {s}: {e[keep].mean():.3f} (all valid: {e[valid].mean():.3f})")
    print(f"  seed {seed}: " + " | ".join(row))

print("M4: B pulled onto A's grid by forward flow vs A, mean abs error in 8-bit levels, interior valid pixels")
suite = fx.make_suite()
errs = []
for name, (a, b, gt, v) in suite.items():
    if name.startswith("exposure"): continue
    h, w = a.shape; ys, xs = np.mgrid[0:h, 0:w].astype(np.float32); f = med(a, b)
    ah = cv2.remap(b.astype(np.float32), xs + f[..., 0], ys + f[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    m = v.copy(); m[:24] = m[-24:] = False; m[:, :24] = m[:, -24:] = False
    errs.append(float(np.abs(ah - a.astype(np.float32))[m].mean()))
print(f"  12 non-exposure pairs: min {min(errs):.2f}, median {np.median(errs):.2f}, max {max(errs):.2f}")
