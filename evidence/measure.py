"""Reference numbers the first review asked for. Sandbox only (2 threads).
The threshold table is now measured by thresholds_reference.py; this script is kept for the history it produced
(FACTS M8 to M10 and E9). Part 3 uses backward flow, which measure_m3_m4.py later replaced with the forward pull."""
import sys, time, json
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evolve", "flow_recipe"))
import numpy as np, cv2
import fixtures as fx
import evaluator as ev

def med(a, b): return cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM).calc(a, b, None)
def fast(a, b): return cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST).calc(a, b, None)
def half(a, b):
    h, w = a.shape
    sa = cv2.resize(a, (w // 2, h // 2), interpolation=cv2.INTER_AREA); sb = cv2.resize(b, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    return cv2.resize(med(sa, sb), (w, h), interpolation=cv2.INTER_LINEAR) * 2.0

out = {}
# 1) time of one full cascade evaluation (seed), current 15-pair dev suite
t0 = time.perf_counter(); r = ev.evaluate(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evolve", "flow_recipe", "initial_program.py")); t1 = time.perf_counter()
out["one full evaluation, 15-pair dev suite (s)"] = round(t1 - t0, 2)

# 2) validity by forward-backward check, vs ground truth, on the dev suite
def fb_valid(a, b, tau):
    f = med(a, b); bwd = med(b, a); h, w = a.shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    bw = cv2.remap(bwd, xs + f[..., 0], ys + f[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=1e6)
    err = np.sqrt(((f + bw) ** 2).sum(-1))
    inb = (xs + f[..., 0] >= 0) & (xs + f[..., 0] <= w - 1) & (ys + f[..., 1] >= 0) & (ys + f[..., 1] <= h - 1)
    return (err <= tau) & inb
suite = fx.make_suite()
m = 24
for tau in (0.5, 1.0, 2.0):
    occ_recall, false_inv = [], []
    for name, (a, b, gt, v) in suite.items():
        pv = fb_valid(a, b, tau)[m:-m, m:-m]; gv = v[m:-m, m:-m]
        false_inv.append(float((~pv & gv).sum() / gv.sum()))
        if (~gv).sum() > 500:
            occ_recall.append((name, float((~pv & ~gv).sum() / (~gv).sum())))
    out[f"validity tau={tau}px: false-invalid rate per fixture"] = [round(x, 4) for x in false_inv]
    out[f"validity tau={tau}px: invalid-region recall"] = [(n, round(x, 3)) for n, x in occ_recall]

# 3) warp: rebuild B from A with backward flow (pull), error on valid pixels, 8-bit levels
errs = {}
for name, (a, b, gt, v) in suite.items():
    h, w = a.shape; ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    fba = med(b, a)
    bh = cv2.remap(a.astype(np.float32), xs + fba[..., 0], ys + fba[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    d = np.abs(bh - b.astype(np.float32))[m:-m, m:-m]
    errs[name] = round(float(d.mean()), 2)
out["pull-warp A->B with DIS MEDIUM backward flow: mean abs error, 8-bit levels"] = errs

# 4) does a bigger dev suite reject FAST and half-res, which the holdout rejects?
def dev_suite(seeds):
    s = {}
    for i, sd in enumerate(seeds):
        for k, (name, fn) in enumerate(fx.SUITE.items()):
            s[f"{name}#{i}"] = fn(540, 960, sd + k * 17)
    return s
for seeds in ((11,), (11, 300), (11, 300, 600)):
    s = dev_suite(seeds); ref = {n: fx.epe_metrics(med(a, b), gt, v) for n, (a, b, gt, v) in s.items()}
    row = {}
    for label, fn in (("FAST", fast), ("half_MEDIUM", half)):
        per = {n: fx.epe_metrics(fn(a, b), gt, v) for n, (a, b, gt, v) in s.items()}
        p = ev.gate(per, ref); row[label] = "FAIL" if p else "pass"
    out[f"dev suite with {len(seeds)} seed(s) per motion type ({5*len(seeds)} pairs)"] = row
print(json.dumps(out, indent=1))
