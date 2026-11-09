"""Two questions about bits. Sandbox reference for FACTS M16 and M17.

    python evidence/measure_threads.py

1. Is DIS output identical bytes whatever the thread count? Decides whether threads belong in the cache key.
2. What would a half-float layer cost on flow vectors? Decides the precision the File COP must load at."""
import hashlib
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "evolve", "flow_recipe"))
import numpy as np, cv2
import fixtures as fx

def run(preset, a, b, vr=None):
    d = cv2.DISOpticalFlow_create(preset)
    if vr is not None: d.setVariationalRefinementIterations(vr)
    return d.calc(a, b, None)

pairs = {
    "layered 960x540": fx.layered(540, 960, 5, **fx.draw("layered", np.random.default_rng(5))),
    "jelly 960x540": fx.jelly(540, 960, 9, **fx.draw("jelly", np.random.default_rng(9))),
    "similarity 1920x1080": fx.similarity(1080, 1920, 3, **fx.draw("similarity", np.random.default_rng(3))),
    "odd size 1001x563": fx.layered(563, 1001, 8, **fx.draw("layered", np.random.default_rng(8))),
}
recipes = {"MEDIUM": (cv2.DISOPTICAL_FLOW_PRESET_MEDIUM, None), "FAST": (cv2.DISOPTICAL_FLOW_PRESET_FAST, None),
           "ULTRAFAST": (cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST, None), "MEDIUM vr=2 (swept)": (cv2.DISOPTICAL_FLOW_PRESET_MEDIUM, 2)}
threads = [1, 2, 3, 4, 7, 8, 12, 16, 24, 32, 48]
print("cv2", cv2.__version__, "cpus", cv2.getNumberOfCPUs())
allsame = True
for pname, (a, b, gt, v) in pairs.items():
    for rname, (preset, vr) in recipes.items():
        digests = {}
        for n in threads:
            cv2.setNumThreads(n)
            assert cv2.getNumThreads() == n, (cv2.getNumThreads(), n)
            f = run(preset, a, b, vr)
            digests[n] = hashlib.sha256(f.tobytes()).hexdigest()[:12]
        uniq = sorted(set(digests.values()))
        same = len(uniq) == 1
        allsame &= same
        extra = "" if same else "  " + str({n: d for n, d in digests.items()})
        print(f"{pname:<22} {rname:<20} {'IDENTICAL' if same else 'DIFFERS'} across threads {threads}{extra}")
        if not same:
            cv2.setNumThreads(1); f1 = run(preset, a, b, vr)
            for n in threads[1:]:
                cv2.setNumThreads(n); fn = run(preset, a, b, vr)
                d = np.abs(fn - f1); print(f"    threads {n:>2} vs 1: max abs diff {d.max():.6f} px, mean {d.mean():.8f}, differing pixels {(d.max(-1) > 0).mean()*100:.3f}%")
print("ALL IDENTICAL" if allsame else "NOT ALL IDENTICAL")

print()
print("Half-float rounding error on one flow component, by magnitude (1e6 samples in each band)")
rng = np.random.default_rng(0)
for lo, hi in [(0, 8), (8, 64), (64, 128), (128, 256), (256, 512), (512, 1024), (1024, 2048)]:
    x = rng.uniform(lo, hi, 1_000_000).astype(np.float32)
    e = np.abs(x.astype(np.float16).astype(np.float32) - x)
    print(f"  {lo:>5} to {hi:<5} px: worst {e.max():.4f} px, mean {e.mean():.4f} px")
