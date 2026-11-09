"""Attack the evaluator before spending a token. Every cheat must score 0; honest work must score.

    python test_gaming.py
"""
import os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import evaluator as ev  # noqa: E402

HEADER = "import cv2\nimport numpy as np\n"


def _score(code):
    f = tempfile.NamedTemporaryFile("w", suffix=".py", delete=False); f.write(HEADER + code); f.close()
    try:
        return ev.evaluate(f.name)
    finally:
        os.unlink(f.name)


CHEATS = {
    "zeros": """
def estimate_flow(a, b):
    return np.zeros(a.shape + (2,), np.float32)
""",
    "one global shift painted everywhere": """
def estimate_flow(a, b):
    (dx, dy), _ = cv2.phaseCorrelate(a.astype(np.float32), b.astype(np.float32))
    f = np.empty(a.shape + (2,), np.float32); f[..., 0] = dx; f[..., 1] = dy
    return f
""",
    "quarter resolution, vectors not rescaled": """
def estimate_flow(a, b):
    h, w = a.shape
    sa, sb = cv2.resize(a, (w // 4, h // 4)), cv2.resize(b, (w // 4, h // 4))
    f = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST).calc(sa, sb, None)
    return cv2.resize(f, (w, h))
""",
    "oversmoothed: small moving object erased": """
def estimate_flow(a, b):
    h, w = a.shape
    sa, sb = cv2.resize(a, (w // 2, h // 2)), cv2.resize(b, (w // 2, h // 2))
    f = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST).calc(sa, sb, None)
    return cv2.blur(cv2.resize(f, (w, h)) * 2.0, (151, 151))
""",
    "stale: reuse the previous call's answer": """
_last = {}
def estimate_flow(a, b):
    if a.shape in _last:
        return _last[a.shape]
    f = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM).calc(a, b, None)
    _last[a.shape] = f
    return f
""",
    "wrong dtype (float64)": """
def estimate_flow(a, b):
    return cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM).calc(a, b, None).astype(np.float64)
""",
}

# Known dead ends: the holdout rejects these, so the dev suite must reject them too,
# or the search would climb towards them.
DEAD_END_HALF = """
def estimate_flow(a, b):
    h, w = a.shape
    sa = cv2.resize(a, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    sb = cv2.resize(b, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    f = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM).calc(sa, sb, None)
    return cv2.resize(f, (w, h), interpolation=cv2.INTER_LINEAR) * 2.0
"""
DEAD_END_FAST = """
def estimate_flow(a, b):
    return cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST).calc(a, b, None)
"""
HONEST_FEWER_REFINEMENTS = """
def estimate_flow(a, b):
    d = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    d.setVariationalRefinementIterations(2)
    return d.calc(a, b, None)
"""


class Gaming(unittest.TestCase):
    def test_cheats_score_zero(self):
        for name, code in CHEATS.items():
            r = _score(code)
            print(f"  CHEAT  {name:<42} score {r.metrics['combined_score']:.2f}  <- {str(r.artifacts.get('reason',''))[:95]}")
            self.assertEqual(r.metrics["combined_score"], 0.0, name)

    def test_seed_scores_about_one(self):
        r = ev.evaluate(os.path.join(HERE, "initial_program.py"))
        print(f"  SEED   {'DIS MEDIUM':<42} score {r.metrics['combined_score']:.2f}  mean EPE {r.metrics['mean_epe']:.3f}")
        self.assertGreater(r.metrics["combined_score"], 0.8); self.assertLess(r.metrics["combined_score"], 1.25)

    def test_known_dead_ends_score_zero(self):
        for name, code in (("half-resolution MEDIUM", DEAD_END_HALF), ("stock FAST preset", DEAD_END_FAST)):
            r = _score(code)
            print(f"  DEAD   {name:<42} score {r.metrics['combined_score']:.2f}  <- {str(r.artifacts.get('reason',''))[:80]}")
            self.assertEqual(r.metrics["combined_score"], 0.0, name)

    def test_honest_speedup_is_accepted(self):
        r = _score(HONEST_FEWER_REFINEMENTS)
        print(f"  HONEST {'MEDIUM, 2 refinement iterations':<42} score {r.metrics['combined_score']:.2f}  mean EPE {r.metrics['mean_epe']:.3f}")
        self.assertGreater(r.metrics["combined_score"], 1.1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
