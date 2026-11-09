"""What the validity flag catches, and what each tolerance costs. Sandbox reference for FACTS M13.

    python evidence/measure_validity.py [draws_per_part]

Compares validity rules on the same flows: fixed tolerance 0.5 / 0.75 / 1.0 px and the adaptive rule of
Sundaram, Brox and Keutzer (ECCV 2010): |f + b|^2 <= 0.01 (|f|^2 + |b|^2) + 0.5.
Part 1: 200 seeds x 5 kinds of the ranged fixtures -> good pixels thrown away, wrong pixels trusted.
Part 2: 240 two-region draws with relative motion 4 to 20 px -> share of occluded pixels caught, by band."""
import json, time
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evolve", "flow_recipe"))
import numpy as np, cv2
import fixtures as fx
def med(a, b): return cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM).calc(a, b, None)
def fb(f, bwd):
    h, w = f.shape[:2]; ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    bw = cv2.remap(bwd, xs + f[..., 0], ys + f[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=1e6)
    inb = (xs + f[..., 0] >= 0) & (xs + f[..., 0] <= w - 1) & (ys + f[..., 1] >= 0) & (ys + f[..., 1] <= h - 1)
    d2 = ((f + bw) ** 2).sum(-1); n2 = (f ** 2).sum(-1) + (bw ** 2).sum(-1)
    return d2, n2, inb
RULES = {"0.5 px": lambda d2, n2: d2 <= 0.25, "0.75 px": lambda d2, n2: d2 <= 0.5625, "1.0 px": lambda d2, n2: d2 <= 1.0,
         "adaptive": lambda d2, n2: d2 <= 0.01 * n2 + 0.5}
m = 24; t0 = time.time()
N1 = int(sys.argv[1]) if len(sys.argv) > 1 else 200; N2 = int(sys.argv[1]) if len(sys.argv) > 1 else 240
rng0 = np.random.default_rng(20261109); seeds = [int(s) for s in rng0.integers(1, 2**31 - 1, size=N1)]
acc = {r: {"false": [], "trusted_wrong": [], "kind": []} for r in RULES}
for s in seeds:
    for k, (kind, fn) in enumerate(fx.SUITE.items()):
        sd = s + 17 * k
        a, b, gt, v = fn(540, 960, sd, **fx.draw(kind, np.random.default_rng(sd)))
        f = med(a, b); bwd = med(b, a); d2, n2, inb = fb(f, bwd)
        e = np.sqrt(((f - gt) ** 2).sum(-1))[m:-m, m:-m]; gv = v[m:-m, m:-m]
        for r, rule in RULES.items():
            pv = (rule(d2, n2) & inb)[m:-m, m:-m]
            acc[r]["false"].append(float((~pv & gv).sum() / gv.sum()))
            acc[r]["trusted_wrong"].append(float((pv & (e > 1.0)).sum() / max(pv.sum(), 1)))
            acc[r]["kind"].append(kind)
print("part 1 done", round(time.time() - t0), "s", flush=True)
out = {"part1": {}, "part2": {}}
print(f"\nPart 1: {5 * N1} ranged fixtures. Good pixels flagged invalid, and flagged-valid pixels that are off by more than 1 px")
print(f"{'rule':<10}{'false: mean':>12}{'p99':>8}{'max':>8}{'  worst kind':<14}{'trusted wrong: mean':>20}{'max':>8}")
for r in RULES:
    fa = np.array(acc[r]["false"]); tw = np.array(acc[r]["trusted_wrong"]); wk = acc[r]["kind"][int(fa.argmax())]
    out["part1"][r] = {"false_mean": float(fa.mean()), "false_p99": float(np.percentile(fa, 99)), "false_max": float(fa.max()), "worst_kind": wk, "tw_mean": float(tw.mean()), "tw_max": float(tw.max()),
                       "false_max_by_kind": {k: float(max(x for x, kk in zip(acc[r]["false"], acc[r]["kind"]) if kk == k)) for k in fx.SUITE}}
    print(f"{r:<10}{fa.mean()*100:>11.3f}%{np.percentile(fa,99)*100:>7.2f}%{fa.max()*100:>7.2f}%  {wk:<12}{tw.mean()*100:>19.3f}%{tw.max()*100:>7.2f}%")
rng = np.random.default_rng(77); rows = []
for i in range(N2):
    sd = int(rng.integers(1, 2**31 - 1)); r_ = np.random.default_rng(sd); u = lambda lo, hi: float(r_.uniform(lo, hi))
    tb = (u(-2, 2), u(-2, 2)); mag = u(4, 20); ang = u(0, 2 * np.pi); tf = (tb[0] + mag * np.cos(ang), tb[1] + mag * np.sin(ang)); R = int(u(45, 120))
    a, b, gt, v = fx.layered(540, 960, sd, t_bg=tb, t_fg=tf, radius=R)
    f = med(a, b); bwd = med(b, a); d2, n2, inb = fb(f, bwd); gv = v[m:-m, m:-m]
    row = {"mag": mag}
    for r, rule in RULES.items():
        pv = (rule(d2, n2) & inb)[m:-m, m:-m]
        row[r] = float((~pv & ~gv).sum() / max((~gv).sum(), 1)); row[r + " false"] = float((~pv & gv).sum() / gv.sum())
    rows.append(row)
print(f"\nPart 2: occluded pixels caught (min / median), two-region draws by relative motion")
print(f"{'band':<12}{'n':>4}" + "".join(f"{r:>18}" for r in RULES))
for lo, hi in [(4, 6), (6, 8), (8, 10), (10, 12), (12, 16), (16, 20)]:
    b_ = [x for x in rows if lo <= x["mag"] < hi]
    if not b_: continue
    line = f"{lo:>2} to {hi:<2} px  {len(b_):>4}"
    out["part2"][f"{lo}-{hi}"] = {"n": len(b_)}
    for r in RULES:
        vals = np.array([x[r] for x in b_]); line += f"{vals.min():>9.3f} /{np.median(vals):>6.3f}"
        out["part2"][f"{lo}-{hi}"][r] = [float(vals.min()), float(np.median(vals))]
    print(line)
print("false-invalid max in part 2: " + ", ".join(f"{r}: {max(x[r + ' false'] for x in rows)*100:.2f}%" for r in RULES))
print("seconds", round(time.time() - t0))
