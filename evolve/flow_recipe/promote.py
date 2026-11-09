"""Promotion check for an evolved recipe. Run on an idle machine.

    python promote.py path/to/best_program.py

The candidate is promoted only if, on the 25-pair holdout it was never scored on:
  1. it passes the same quality gate on every pair, and
  2. it is MARGIN faster than the fastest contender that also passes: the stock presets
     and, if sweep.py has run, the swept program.
The dev-suite score from the run is not evidence: the search optimised against it.
"""
import os, sys, time
import cv2, numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import evaluator as ev                          # noqa: E402
from fixtures import epe_metrics, make_holdout  # noqa: E402

MARGIN = 1.15   # floor. Raise it if the workstation's timing spread for identical code is wider.
REPS = 5


def stock(preset):
    return lambda a, b: cv2.DISOpticalFlow_create(preset).calc(a, b, None)


def preconditions():
    """The verdict is only meaningful if the judge still rejects cheats and the sweep has set the bar."""
    import unittest
    import test_gaming
    result = unittest.TextTestRunner(verbosity=0).run(unittest.defaultTestLoader.loadTestsFromModule(test_gaming))
    if not result.wasSuccessful():
        print("REFUSED: test_gaming.py fails, so the evaluator cannot be trusted. Fix the judge first.")
        return False
    if not os.path.exists(os.path.join(HERE, "swept_program.py")):
        print("REFUSED: run sweep.py first; the swept program is the bar to beat.")
        return False
    return True


def main(path):
    if not preconditions():
        return 2
    hold = make_holdout(); ref = ev.reference_metrics(hold, key="holdout")
    fns = {"stock MEDIUM": stock(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM), "stock FAST": stock(cv2.DISOPTICAL_FLOW_PRESET_FAST),
           "stock ULTRAFAST": stock(cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST)}
    swept = os.path.join(HERE, "swept_program.py")
    if os.path.exists(swept):
        fns["swept program"] = ev._load(swept)
    fns["candidate"] = ev._load(path)
    q = {}
    for k, fn in fns.items():
        per = {n: epe_metrics(fn(a, b), gt, v) for n, (a, b, gt, v) in hold.items()}
        q[k] = (ev.gate(per, ref), float(np.mean([m["mean"] for m in per.values()])))
    pairs = [(a, b) for a, b, _, _ in hold.values()]
    for fn in fns.values():
        fn(*pairs[0])
    best = {k: float("inf") for k in fns}
    for _ in range(REPS):                       # all contenders interleaved in every repetition
        for k, fn in fns.items():
            t0 = time.perf_counter()
            for a, b in pairs:
                fn(a, b)
            best[k] = min(best[k], (time.perf_counter() - t0) / len(pairs))
    base = best["stock MEDIUM"]
    print(f"{'holdout, ' + str(len(hold)) + ' pairs':<20}{'gate':>6}{'mean EPE':>10}{'ms/pair':>9}{'speedup':>9}")
    for k in fns:
        print(f"{k:<20}{'FAIL' if q[k][0] else 'pass':>6}{q[k][1]:>10.3f}{best[k]*1000:>9.1f}{base/best[k]:>8.2f}x")
    for problem in q["candidate"][0][:5]:
        print("   candidate:", problem[:150])
    rivals = [k for k in fns if k != "candidate" and not q[k][0]]
    bar_name = min(rivals, key=lambda k: best[k]); bar = base / best[bar_name]
    cand = base / best["candidate"]
    verdict = not q["candidate"][0] and cand >= MARGIN * bar
    print(f"\nbar to beat: {bar_name} at {bar:.2f}x -> candidate needs a clean gate and >= {MARGIN * bar:.2f}x")
    print("VERDICT:", "PROMOTE" if verdict else "DO NOT PROMOTE")
    return 0 if verdict else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python promote.py path/to/best_program.py")
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
