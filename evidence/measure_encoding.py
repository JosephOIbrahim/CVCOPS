"""What does the analysis encoding cost? Sandbox reference for FACTS M15.

    python evidence/measure_encoding.py

 Scene-linear frames quantised to 8 bits with and without gain and gamma.
DIS MEDIUM, 960x540, exact ground truth. Sandbox, OpenCV 5.0.0."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evolve", "flow_recipe"))
import numpy as np, cv2
import fixtures as fx

fx._u8 = lambda img: np.asarray(img, np.float32)          # keep the float frames: we quantise ourselves
def q8(x): return np.clip(np.rint(x * 255.0), 0, 255).astype(np.uint8)
def med(a, b): return cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM).calc(a, b, None)

def encodings(A, B):
    """A, B are display-referred in [0,1]. L is the scene-linear version a renderer or camera pipeline would hand over."""
    A, B = np.clip(A, 0, 1), np.clip(B, 0, 1)      # cubic resampling overshoots slightly below 0 and above 1
    LA, LB = A ** 2.2, B ** 2.2
    out = {}
    out["display-referred (reference)"] = (q8(A), q8(B))
    out["linear, straight to 8 bits"] = (q8(LA), q8(LB))
    out["linear, 3 stops under, straight to 8 bits"] = (q8(LA / 8), q8(LB / 8))
    out["linear, 5 stops under, straight to 8 bits"] = (q8(LA / 32), q8(LB / 32))
    out["linear, 3 stops over, straight to 8 bits"] = (q8(LA * 8), q8(LB * 8))
    g = 1.0 / max(float(np.percentile(LA / 32, 99.5)), 1e-9)   # one gain for the shot, from frame A
    out["linear, 5 stops under, gain then gamma 2.2"] = (q8(np.clip(g * LA / 32, 0, None) ** (1 / 2.2)), q8(np.clip(g * LB / 32, 0, None) ** (1 / 2.2)))
    g = 1.0 / max(float(np.percentile(LA * 8, 99.5)), 1e-9)
    out["linear, 3 stops over, gain then gamma 2.2"] = (q8(np.clip(g * LA * 8, 0, None) ** (1 / 2.2)), q8(np.clip(g * LB * 8, 0, None) ** (1 / 2.2)))
    return out

N = 20
rows = {}
for kind in ("translation", "layered", "jelly"):
    for i in range(N):
        sd = 4000 + 31 * i + {"translation": 0, "layered": 7, "jelly": 13}[kind]
        A, B, gt, v = fx.SUITE[kind](540, 960, sd, **fx.draw(kind, np.random.default_rng(sd)))
        for name, (a8, b8) in encodings(A, B).items():
            e = fx.epe_metrics(med(a8, b8), gt, v)["mean"]
            clip = float(((a8 == 0) | (a8 == 255)).mean()); levels = int(len(np.unique(a8)))
            r = rows.setdefault(name, {"epe": [], "clip": [], "levels": []})
            r["epe"].append(e); r["clip"].append(clip); r["levels"].append(levels)
print(f"{'encoding of the analysis image':<46}{'mean EPE px':>12}{'worst':>8}{'clipped':>9}{'grey levels':>12}")
for name, r in rows.items():
    print(f"{name:<46}{np.mean(r['epe']):>12.3f}{np.max(r['epe']):>8.3f}{np.mean(r['clip'])*100:>8.1f}%{int(np.median(r['levels'])):>12}")
