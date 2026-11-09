"""Step 1 of the evolve lane: a plain parameter sweep over DIS. Evolution starts where this ends.

    python sweep.py            # writes swept_program.py and prints the table

Numeric knobs are a sweep's job, not an LLM's. The search is for structure the sweep cannot express.
"""
import itertools, os, sys, time
import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import evaluator as ev                       # noqa: E402
from fixtures import epe_metrics, make_holdout  # noqa: E402

GRID = {"finest": (1, 2), "stride": (3, 4), "gd": (8, 12, 16, 25), "vr": (0, 2, 5)}
TEMPLATE = '''"""
Dense optical flow recipe, seeded from sweep.py's winner. Same contract as initial_program.py.
"""
import cv2
import numpy as np


# EVOLVE-BLOCK-START
def estimate_flow(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    dis.setFinestScale({finest})
    dis.setPatchStride({stride})
    dis.setGradientDescentIterations({gd})
    dis.setVariationalRefinementIterations({vr})
    return dis.calc(a, b, None)


# EVOLVE-BLOCK-END
'''


def make(finest, stride, gd, vr):
    def f(a, b):
        d = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
        d.setFinestScale(finest); d.setPatchStride(stride)
        d.setGradientDescentIterations(gd); d.setVariationalRefinementIterations(vr)
        return d.calc(a, b, None)
    return f


def main():
    dev = ev._suite(); ref = ev.reference_metrics(dev)
    hold = make_holdout(); ref_h = ev.reference_metrics(hold, key="holdout")
    passing = []
    for finest, stride, gd, vr in itertools.product(*GRID.values()):
        fn = make(finest, stride, gd, vr)
        per = {k: epe_metrics(fn(a, b), gt, v) for k, (a, b, gt, v) in dev.items()}
        if ev.gate(per, ref):
            continue
        ref_s, cand_s = ev._benchmark(fn)
        perh = {k: epe_metrics(fn(a, b), gt, v) for k, (a, b, gt, v) in hold.items()}
        passing.append((ref_s / cand_s, not ev.gate(perh, ref_h), dict(finest=finest, stride=stride, gd=gd, vr=vr)))
    passing.sort(key=lambda r: r[0], reverse=True)
    n = 1
    for k in GRID.values():
        n *= len(k)
    print(f"{len(passing)} of {n} configs pass the dev gate")
    for sp, hold_ok, cfg in passing:
        print(f"  {sp:5.2f}x  holdout {'pass' if hold_ok else 'FAIL'}  {cfg}")
    best = next((r for r in passing if r[1]), None)
    if best is None:
        print("No swept config passes both gates. Seed the run from initial_program.py.")
        return 1
    with open(os.path.join(HERE, "swept_program.py"), "w") as f:
        f.write(TEMPLATE.format(**best[2]))
    print(f"wrote swept_program.py: {best[2]} at {best[0]:.2f}x")
    return 0


if __name__ == "__main__":
    sys.exit(main())
