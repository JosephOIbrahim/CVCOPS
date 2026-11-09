"""
Evaluator for the flow recipe. Quality is a GATE, speed is the score.

    speedup = reference_time / candidate_time          (reference = DIS MEDIUM, owned here)

The gate is RELATIVE to the reference on each fixture, because fixtures differ in
difficulty (a motion boundary is hard for every method). An absolute gate tuned on one
suite rejected the reference itself on another. On every fixture a candidate may be at most

    mean EPE          <= reference mean EPE + MEAN_SLACK            (px)
    worst-block EPE   <= WB_FACTOR * reference worst block + WB_SLACK   (32x32 blocks)

and over the suite     mean of means <= reference mean of means + SUITE_SLACK.
It must also be pure: the same pair gives the same answer whatever was called before.
Pass everything and combined_score = speedup. Fail anything and it is 0.

Cascade: stage 1 smoke -> stage 2 quality gate -> stage 3 timing. Every rejection
returns an artifact that says which fixture failed and by how much.
Run test_gaming.py before spending a token: the cheats must score zero.
"""
import importlib.util
import os
import sys
import time
import traceback

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fixtures import epe_metrics, make_suite  # noqa: E402  (15 pairs: 3 of each motion kind)

try:
    from openevolve.evaluation_result import EvaluationResult
except ImportError:  # lets test_gaming.py run without openevolve installed
    class EvaluationResult:  # type: ignore
        def __init__(self, metrics=None, artifacts=None):
            self.metrics, self.artifacts = metrics or {}, artifacts or {}

# ---- the gate: pre-registered, relative to the reference, in pixels of the analysis image ----
MEAN_SLACK = 0.30
WB_FACTOR = 1.5
WB_SLACK = 0.50
SUITE_SLACK = 0.15
TIMING_REPS = 5

_SUITE = None
_REF = {}


def _suite():
    global _SUITE
    if _SUITE is None:
        _SUITE = make_suite()
    return _SUITE


def _reference(a, b):
    return cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM).calc(a, b, None)


def reference_metrics(suite, key="dev"):
    """The reference's own error on each fixture. Deterministic, so computed once per suite key."""
    if key not in _REF:
        _REF[key] = {n: epe_metrics(_reference(a, b), gt, v) for n, (a, b, gt, v) in suite.items()}
    return _REF[key]


def gate(per, ref):
    """Return a list of human-readable problems; empty means the gate is passed."""
    problems = []
    for name, m in per.items():
        r = ref[name]
        if m["mean"] > r["mean"] + MEAN_SLACK:
            problems.append(f"{name}: mean EPE {m['mean']:.3f} px (reference {r['mean']:.3f}, limit {r['mean'] + MEAN_SLACK:.3f})")
        limit = WB_FACTOR * r["worst_block"] + WB_SLACK
        if m["worst_block"] > limit:
            problems.append(f"{name}: worst 32x32 block EPE {m['worst_block']:.2f} px (reference {r['worst_block']:.2f}, limit {limit:.2f}) "
                            "- a local region is wrong even if the average looks fine")
    suite_mean = float(np.mean([m["mean"] for m in per.values()]))
    ref_mean = float(np.mean([r["mean"] for r in ref.values()]))
    if suite_mean > ref_mean + SUITE_SLACK:
        problems.append(f"mean over fixtures {suite_mean:.3f} px (reference {ref_mean:.3f}, limit {ref_mean + SUITE_SLACK:.3f})")
    return problems


def _load(program_path):
    spec = importlib.util.spec_from_file_location("candidate", program_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.estimate_flow


def _fail(stage, reason):
    return EvaluationResult(metrics={"combined_score": 0.0, "mean_epe": 9.99},
                            artifacts={"rejected_at": stage, "reason": reason})


def _shape_ok(flow, a):
    if not isinstance(flow, np.ndarray):
        return f"returned {type(flow).__name__}, expected numpy.ndarray"
    if flow.shape != a.shape + (2,):
        return f"shape {flow.shape}, expected {a.shape + (2,)}"
    if flow.dtype != np.float32:
        return f"dtype {flow.dtype}, expected float32"
    if not np.isfinite(flow).all():
        return "flow contains NaN or Inf"
    return None


def evaluate_stage1(program_path):
    """Smoke: right shape, finite, not a no-op, and pure."""
    try:
        fn = _load(program_path)
        s = _suite()
        a, b, gt, valid = s["similarity#0"]
        a2, b2 = a[:270, :480].copy(), b[:270, :480].copy()
        f1 = fn(a2, b2)
        bad = _shape_ok(f1, a2)
        if bad:
            return _fail("stage1", bad)
        if float(np.abs(f1).max()) < 1e-3:
            return _fail("stage1", "flow is all zeros on a pair that clearly moves")
        ta, tb, _, _ = s["translation#0"]
        g = fn(ta[:270, :480].copy(), tb[:270, :480].copy())      # a different pair in between
        if isinstance(g, np.ndarray) and g.shape == f1.shape and np.array_equal(g, f1):
            return _fail("stage1", "two different pairs returned the identical flow: the answer is being reused. "
                                   "Compute every pair from its own pixels.")
        f2 = fn(a2, b2)
        if not np.array_equal(f1, f2):
            return _fail("stage1", "not a pure function: the same pair gave a different answer after another call "
                                   f"(max difference {float(np.abs(f1 - f2).max()):.3f} px). Keep no state between calls.")
        return EvaluationResult(metrics={"combined_score": 1.0}, artifacts={"stage1": "ok"})
    except Exception:
        return _fail("stage1", traceback.format_exc()[-1500:])


def _quality(fn):
    per = {}
    for name, (a, b, gt, valid) in _suite().items():
        flow = fn(a, b)
        bad = _shape_ok(flow, a)
        if bad:
            return None, f"{name}: {bad}"
        per[name] = epe_metrics(flow, gt, valid)
    return per, None


def evaluate_stage2(program_path):
    """The hard quality gate against ground truth."""
    try:
        per, bad = _quality(_load(program_path))
        if bad:
            return _fail("stage2", bad)
        suite_mean = float(np.mean([m["mean"] for m in per.values()]))
        problems = gate(per, reference_metrics(_suite()))
        if problems:
            r = _fail("stage2", "QUALITY GATE FAILED: " + "; ".join(problems))
            r.metrics["mean_epe"] = suite_mean
            return r
        worst = max(m["worst_block"] for m in per.values())
        return EvaluationResult(metrics={"combined_score": 1.0, "mean_epe": suite_mean, "worst_block": worst},
                                artifacts={"stage2": "gate passed", "per_fixture": {k: round(v["mean"], 3) for k, v in per.items()}})
    except Exception:
        return _fail("stage2", traceback.format_exc()[-1500:])


def _benchmark(fn):
    """Reference and candidate interleaved, warmed up, minimum of N: load can only add time."""
    pairs = [(a, b) for a, b, _, _ in _suite().values()]
    for a, b in pairs[:1]:
        _reference(a, b); fn(a, b)
    best_ref = best_cand = float("inf")
    for _ in range(TIMING_REPS):
        t0 = time.perf_counter()
        for a, b in pairs:
            _reference(a, b)
        t1 = time.perf_counter()
        for a, b in pairs:
            fn(a, b)
        t2 = time.perf_counter()
        best_ref, best_cand = min(best_ref, t1 - t0), min(best_cand, t2 - t1)
    return best_ref / len(pairs), best_cand / len(pairs)


def evaluate_stage3(program_path):
    """Timing, only for candidates that passed the gate."""
    try:
        fn = _load(program_path)
        per, bad = _quality(fn)
        if bad:
            return _fail("stage3", bad)
        suite_mean = float(np.mean([m["mean"] for m in per.values()]))
        worst = max(m["worst_block"] for m in per.values())
        ref_s, cand_s = _benchmark(fn)
        speedup = ref_s / cand_s
        return EvaluationResult(
            metrics={"combined_score": float(speedup), "speedup": float(speedup), "mean_epe": suite_mean,
                     "worst_block": worst, "ms_per_pair": cand_s * 1000.0},
            artifacts={"timing": f"reference {ref_s*1000:.1f} ms/pair, candidate {cand_s*1000:.1f} ms/pair, speedup {speedup:.2f}x",
                       "quality": f"mean EPE {suite_mean:.3f} px, worst block {worst:.2f} px"})
    except Exception:
        return _fail("stage3", traceback.format_exc()[-1500:])


def evaluate(program_path):
    r1 = evaluate_stage1(program_path)
    if r1.metrics.get("combined_score", 0.0) < 0.5:
        return r1
    r2 = evaluate_stage2(program_path)
    if r2.metrics.get("combined_score", 0.0) < 0.5:
        return r2
    return evaluate_stage3(program_path)
