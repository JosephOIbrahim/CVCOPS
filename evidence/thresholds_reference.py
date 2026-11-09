"""Reference for every row of the blueprint's threshold table (docs/BLUEPRINT.md, section 8).

    python evidence/thresholds_reference.py             pinned fixtures: one line per row, PASS or FAIL
    python evidence/thresholds_reference.py --faults    planted faults: each must FAIL at least one row
    python evidence/thresholds_reference.py --seeds N   the same metrics on N fresh draws: min, median, max
    python evidence/thresholds_reference.py --json      pinned results as JSON

The reference implementation is stock DIS (MEDIUM unless a row says FAST) with validity by forward-backward
agreement within TAU pixels plus an in-bounds destination. Mission 0 wires these computations into
tests/thresholds/ with asserts and adds nothing of its own. ROWS holds the blueprint's wording and numbers;
evidence/refinement/gates.py fails if the two drift apart.

The seam. Every row grades an object with the five methods of Reference below: flow(a, b, preset, scale),
valid(a, b, tau), pull(a, b), write_exr(path, rgb) and read_exr(path). tests/thresholds/impls.py builds one from
the product's code for rung 1 and one that drives Houdini for the M3 and M4 rows; the self-test supplies Reference
and each fault. Nothing else about the product is assumed. METRICS maps each row to the function that measures it,
and the threshold tests call exactly those functions.

A row that cannot run fails. A missing OpenEXR package is a failure here, not a skip.

Run here, the M3 and M4 rows show what the flow itself contributes. Their real tests run the same metrics through
Houdini, so a larger error there points at the boundary, not at the flow.
"""
import argparse, hashlib, json, os, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "evolve", "flow_recipe"))
import numpy as np, cv2          # noqa: E402
import fixtures as fx            # noqa: E402

TAU = 1.0                        # validity tolerance in pixels: the contract's default
MARGIN = 24                      # border ignored by every metric, as in fixtures.epe_metrics
SHIFTS = [(1.0, 0.0), (0.0, 1.0), (3.0, -2.0), (0.5, 0.25), (-7.3, 4.6)]
WIDE = [dict(seed=21, t_bg=(1.2, 0.6), deg=20.0), dict(seed=22, t_bg=(-0.8, 1.5), deg=140.0), dict(seed=23, t_bg=(0.4, -1.1), deg=260.0)]
WIDE_MOTION = 16.0               # pixels of relative motion between the two regions of the wide-occlusion fixture
TWO_REGION = dict(seeds=(5, 6, 7), t_bg=(2.5, -1.5), t_fg=(-6.0, 3.5), radius=220, size=(1080, 1920))

# label and threshold are the blueprint's own words (Test and Threshold columns). kind: "max" passes at or below
# the limit, "min" at or above, "true" when the value is True.
ROWS = [
    dict(key="shift_medium", mission="M1", label="Periodic shifts, DIS MEDIUM, mean error", threshold="at most 0.05 px", limit=0.05, kind="max"),
    dict(key="shift_fast", mission="M1", label="Periodic shifts, DIS FAST, mean error", threshold="at most 0.15 px", limit=0.15, kind="max"),
    dict(key="zero_motion", mission="M1", label="Zero motion, mean error", threshold="at most 0.01 px", limit=0.01, kind="max"),
    dict(key="suite_mean", mission="M1", label="The 15-pair suite, MEDIUM, mean error over the pairs", threshold="at most 0.12 px", limit=0.12, kind="max"),
    dict(key="valid_false", mission="M1", label="Validity at 1.0 px: valid pixels flagged invalid, worst pair of the suite", threshold="at most 3%", limit=0.03, kind="max"),
    dict(key="valid_occluded", mission="M1", label="Validity at 1.0 px: occluded pixels caught, two regions 16 px apart in motion", threshold="at least 0.85", limit=0.85, kind="min"),
    dict(key="deterministic", mission="M1", label="Determinism on CPU", threshold="identical bytes across two runs and two thread counts", limit=True, kind="true"),
    dict(key="exr_roundtrip", mission="M2", label="EXR write then read, the transport pattern", threshold="bit-exact", limit=True, kind="true"),
    dict(key="two_region_s1", mission="M3", label="at analysis scale 1.0", threshold="at most 0.10 px", limit=0.10, kind="max"),
    dict(key="two_region_s05", mission="M3", label="at analysis scale 0.5", threshold="at most 0.25 px", limit=0.25, kind="max"),
    dict(key="pull_warp", mission="M4", label="frame B pulled onto A's grid by the forward flow, against A, the 12 pairs of the suite without a brightness change", threshold="at most 1.5 levels mean error, 8-bit", limit=1.5, kind="max"),
]


# ---- the implementation under test --------------------------------------------------------------------------
class Reference:
    """What Mission 1 has to match: stock DIS, validity by forward-backward agreement."""
    name = "reference (stock DIS)"

    def flow(self, a, b, preset="MEDIUM", scale=1.0):
        """Forward flow from a to b in a's pixels. scale < 1 estimates on downscaled copies, as Houdini's prep does,
        and returns the flow upsampled and rescaled to a's resolution, as the conversion node does."""
        if scale == 1.0:
            return cv2.DISOpticalFlow_create(getattr(cv2, "DISOPTICAL_FLOW_PRESET_" + preset)).calc(a, b, None)
        h, w = a.shape; size = (int(w * scale), int(h * scale))
        sa = cv2.resize(a, size, interpolation=cv2.INTER_AREA); sb = cv2.resize(b, size, interpolation=cv2.INTER_AREA)
        return cv2.resize(self.flow(sa, sb, preset), (w, h), interpolation=cv2.INTER_LINEAR) / scale

    def pull(self, a, b):
        """Frame b pulled onto a's grid by the forward flow, as float32 8-bit levels."""
        f = self.flow(a, b); h, w = a.shape; ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        return cv2.remap(b.astype(np.float32), xs + f[..., 0], ys + f[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    def valid(self, a, b, tau=TAU):
        f, bwd = self.flow(a, b), self.flow(b, a)
        h, w = a.shape; ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        back = cv2.remap(bwd, xs + f[..., 0], ys + f[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=1e6)
        inside = (xs + f[..., 0] >= 0) & (xs + f[..., 0] <= w - 1) & (ys + f[..., 1] >= 0) & (ys + f[..., 1] <= h - 1)
        return (np.sqrt(((f + back) ** 2).sum(-1)) <= tau) & inside

    def write_exr(self, path, rgb):
        """rgb is float32 HxWx3: u, v, validity. Written as R, G, B, 32-bit float, ZIP."""
        import OpenEXR
        header = {"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage}
        with OpenEXR.File(header, {"R": rgb[..., 0].copy(), "G": rgb[..., 1].copy(), "B": rgb[..., 2].copy()}) as f:
            f.write(path)

    def read_exr(self, path):
        import OpenEXR
        with OpenEXR.File(path, separate_channels=True) as f:
            ch = f.channels()
            return np.dstack([ch["R"].pixels, ch["G"].pixels, ch["B"].pixels])


def fault(name, **over):
    """A copy of the reference with one thing broken."""
    cls = type("Fault", (Reference,), dict(name=name, **over))
    return cls()


def _flip_v(self, a, b, preset="MEDIUM", scale=1.0):
    f = Reference.flow(self, a, b, preset, scale).copy(); f[..., 1] *= -1; return f
def _swap_uv(self, a, b, preset="MEDIUM", scale=1.0):
    return Reference.flow(self, a, b, preset, scale)[..., ::-1].copy()
def _half(self, a, b, preset="MEDIUM", scale=1.0):
    h, w = a.shape
    sa = cv2.resize(a, (w // 2, h // 2), interpolation=cv2.INTER_AREA); sb = cv2.resize(b, (w // 2, h // 2), interpolation=cv2.INTER_AREA)
    return cv2.resize(Reference.flow(self, sa, sb, preset, scale), (w, h), interpolation=cv2.INTER_LINEAR)      # vectors not rescaled
def _noisy(self, a, b, preset="MEDIUM", scale=1.0):
    f = Reference.flow(self, a, b, preset, scale); return f + np.float32(1e-4) * np.random.default_rng().standard_normal(f.shape).astype(np.float32)
def _push(self, a, b):
    f = -Reference.flow(self, a, b); h, w = a.shape; ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    return cv2.remap(b.astype(np.float32), xs + f[..., 0], ys + f[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

FAULTS = [
    fault("zero flow", flow=lambda self, a, b, preset="MEDIUM", scale=1.0: np.zeros(a.shape + (2,), np.float32)),
    fault("sign of v flipped", flow=_flip_v),
    fault("u and v swapped", flow=_swap_uv),
    fault("half resolution, vectors not rescaled", flow=_half),
    fault("validity always true", valid=lambda self, a, b, tau=TAU: np.ones(a.shape, bool)),
    fault("validity always false", valid=lambda self, a, b, tau=TAU: np.zeros(a.shape, bool)),
    fault("flow not repeatable", flow=_noisy),
    fault("EXR written as half float", write_exr=lambda self, path, rgb: Reference.write_exr(self, path, rgb.astype(np.float16))),
    fault("warp pushes instead of pulls", pull=_push),
]


# ---- fixtures that are not in fixtures.py ---------------------------------------------------------------------
def periodic_texture(h, w, seed=7):
    """Band-limited periodic noise, so a Fourier shift is exact."""
    rng = np.random.default_rng(seed)
    spec = rng.normal(size=(h, w)) + 1j * rng.normal(size=(h, w))
    fy = np.fft.fftfreq(h)[:, None]; fxx = np.fft.fftfreq(w)[None, :]
    spec *= np.exp(-((np.sqrt(fxx * fxx + fy * fy)) / 0.06) ** 2)
    img = np.fft.ifft2(spec).real
    return (img - img.min()) / (img.max() - img.min())

def fourier_shift(img, dx, dy):
    """Content moves by +dx to the right and +dy down."""
    h, w = img.shape; fy = np.fft.fftfreq(h)[:, None]; fxx = np.fft.fftfreq(w)[None, :]
    return np.fft.ifft2(np.fft.fft2(img) * np.exp(-2j * np.pi * (fxx * dx + fy * dy))).real

def u8(img):
    return np.clip(np.rint(img * 255.0), 0, 255).astype(np.uint8)

def wide_occlusion(seed, t_bg, deg, motion=WIDE_MOTION, radius=70, h=540, w=960):
    th = np.deg2rad(deg); t_fg = (t_bg[0] + motion * np.cos(th), t_bg[1] + motion * np.sin(th))
    return fx.layered(h, w, seed, t_bg=t_bg, t_fg=t_fg, radius=radius)

def transport_pattern(h=270, w=480):
    """Float32 RGB that a lossy path cannot carry: signed and large vectors, values half float cannot hold, a 0/1
    channel, and a corner marker that pins the orientation. Probe P3 sends this same pattern through Houdini."""
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    u = (xs - w / 2) * 7.123456 + 0.000123              # about -1710 to +1710, never a round number
    v = (h / 2 - ys) * 9.876543 - 1000.3                # about -2334 to +333, negative on most of the frame
    valid = ((xs.astype(int) // 16 + ys.astype(int) // 16) % 2).astype(np.float32)
    img = np.dstack([u, v, valid]).astype(np.float32)
    img[0, 0] = (-1234.5677, 4321.1235, 1.0)            # top-left marker
    img[0, w - 1] = (1e-3, -1e-3, 0.0)                  # top-right marker: tiny values survive only without clamping
    return img


# ---- metrics ----------------------------------------------------------------------------------------------------
def _interior(mask):
    m = mask.copy(); m[:MARGIN] = m[-MARGIN:] = False; m[:, :MARGIN] = m[:, -MARGIN:] = False; return m

def shift_error(impl, preset, shifts=SHIFTS, seed=7, h=540, w=960):
    a = periodic_texture(h, w, seed); A = u8(a); worst = 0.0
    for dx, dy in shifts:
        f = impl.flow(A, u8(fourier_shift(a, dx, dy)), preset)[48:-48, 48:-48]
        worst = max(worst, float(np.sqrt((f[..., 0] - dx) ** 2 + (f[..., 1] - dy) ** 2).mean()))
    return worst

def zero_motion(impl, seed=7, h=540, w=960):
    A = u8(periodic_texture(h, w, seed)); f = impl.flow(A, A)[48:-48, 48:-48]
    return float(np.sqrt((f ** 2).sum(-1)).mean())

def suite_metrics(impl, suite):
    """Mean error over the pairs, and the worst share of valid pixels flagged invalid."""
    errs, false_inv = [], []
    for name, (a, b, gt, v) in suite.items():
        errs.append(fx.epe_metrics(impl.flow(a, b), gt, v)["mean"])
        pv = impl.valid(a, b); gv = _interior(v)
        false_inv.append(float((~pv & gv).sum() / gv.sum()))
    return float(np.mean(errs)), max(false_inv)

def pull_warp(impl, suite):
    """Worst mean error, in 8-bit levels, of frame B pulled onto A's grid, over the pairs without a brightness change."""
    warps = []
    for name, (a, b, gt, v) in suite.items():
        if not name.startswith("exposure"):
            warps.append(float(np.abs(np.asarray(impl.pull(a, b), np.float32) - a.astype(np.float32))[_interior(v)].mean()))
    return max(warps)

def occluded_caught(impl, fixture):
    a, b, gt, v = fixture
    pv = impl.valid(a, b); inner = np.zeros_like(v); inner[MARGIN:-MARGIN, MARGIN:-MARGIN] = True
    occ = ~v & inner
    return float((~pv & occ).sum() / max(occ.sum(), 1))

def two_region(impl, seed, scale, t_bg, t_fg, radius, size):
    h, w = size
    a, b, gt, valid = fx.layered(h, w, seed, t_bg=t_bg, t_fg=t_fg, radius=radius)
    ys, xs = np.mgrid[0:h, 0:w]; d = np.sqrt((xs - w * 0.55) ** 2 + (ys - h * 0.5) ** 2)
    keep = _interior(valid & (np.abs(d - radius) >= 8))
    f = impl.flow(a, b, scale=scale)
    return float(np.sqrt(((f - gt) ** 2).sum(-1))[keep].mean())

def deterministic(impl):
    a, b, _, _ = fx.layered(540, 960, 5, **fx.draw("layered", np.random.default_rng(5)))
    before = cv2.getNumThreads(); digests = set()
    try:
        for threads in (1, 4):
            cv2.setNumThreads(threads)
            for _ in range(2):
                digests.add(hashlib.sha256(impl.flow(a, b).tobytes()).hexdigest())
    finally:
        cv2.setNumThreads(before)
    return len(digests) == 1

def exr_roundtrip(impl):
    """Write the transport pattern through the implementation and read it back. False if it cannot run."""
    img = transport_pattern(); path = os.path.join(tempfile.mkdtemp(prefix="cvcops_exr_"), "pattern.exr")
    try:
        impl.write_exr(path, img); back = np.asarray(impl.read_exr(path))
    except ImportError as e:
        print(f"  the EXR row cannot run: {e}", file=sys.stderr)
        return False
    return bool(back.dtype == np.float32 and back.shape == img.shape and np.array_equal(back, img))


def _suite(cache):
    if "suite" not in cache:
        cache["suite"] = fx.make_suite()                        # the 15-pair dev suite, seeds fixed in fixtures.py
    return cache["suite"]

def _suite_metrics(impl, cache):
    if "suite_metrics" not in cache:
        cache["suite_metrics"] = suite_metrics(impl, _suite(cache))
    return cache["suite_metrics"]

def _two_region(impl, scale):
    tr = TWO_REGION
    return max(two_region(impl, s, scale, tr["t_bg"], tr["t_fg"], tr["radius"], tr["size"]) for s in tr["seeds"])

# One function per row. The threshold tests call these, so the tests and this script cannot measure differently.
# cache is a dict shared by the rows of one run with one implementation.
METRICS = {
    "shift_medium": lambda impl, cache: shift_error(impl, "MEDIUM"),
    "shift_fast": lambda impl, cache: shift_error(impl, "FAST"),
    "zero_motion": lambda impl, cache: zero_motion(impl),
    "suite_mean": lambda impl, cache: _suite_metrics(impl, cache)[0],
    "valid_false": lambda impl, cache: _suite_metrics(impl, cache)[1],
    "valid_occluded": lambda impl, cache: min(occluded_caught(impl, wide_occlusion(**p)) for p in WIDE),
    "deterministic": lambda impl, cache: deterministic(impl),
    "exr_roundtrip": lambda impl, cache: exr_roundtrip(impl),
    "two_region_s1": lambda impl, cache: _two_region(impl, 1.0),
    "two_region_s05": lambda impl, cache: _two_region(impl, 0.5),
    "pull_warp": lambda impl, cache: pull_warp(impl, _suite(cache)),
}
assert set(METRICS) == {r["key"] for r in ROWS}, "every row needs exactly one metric"

def measure(impl):
    cache = {}
    return {row["key"]: METRICS[row["key"]](impl, cache) for row in ROWS}

def verdict(row, value):
    if row["kind"] == "max": return "PASS" if value <= row["limit"] else "FAIL"
    if row["kind"] == "min": return "PASS" if value >= row["limit"] else "FAIL"
    return "PASS" if value is True else "FAIL"

def report(impl):
    values = measure(impl); out = {}
    for row in ROWS:
        v = values[row["key"]]; out[row["key"]] = dict(value=v, verdict=verdict(row, v))
    return out

def show(result):
    for row in ROWS:
        r = result[row["key"]]; v = r["value"]
        text = str(v) if isinstance(v, bool) else f"{v:.4f}"
        print(f"  {r['verdict']:<5} {row['mission']}  {row['label'][:74]:<74}  {row['threshold']:<52}  {text}")


# ---- fresh seeds --------------------------------------------------------------------------------------------------
def fresh(n, seed0=None):
    """The same metrics on n fresh draws. Thresholds must hold with room to spare here, or a pinned pass is luck."""
    impl = Reference(); rng = np.random.default_rng(seed0); acc = {r["key"]: [] for r in ROWS if r["kind"] != "true"}
    for i in range(n):
        s = int(rng.integers(1, 2 ** 31 - 1)); r = np.random.default_rng(s); u = lambda lo, hi: float(r.uniform(lo, hi))
        shifts = [(u(-8, 8), u(-8, 8))]
        acc["shift_medium"].append(shift_error(impl, "MEDIUM", shifts, seed=s)); acc["shift_fast"].append(shift_error(impl, "FAST", shifts, seed=s))
        acc["zero_motion"].append(zero_motion(impl, seed=s))
        suite = fx.make_suite(base=s); mean, false_inv = suite_metrics(impl, suite)
        acc["suite_mean"].append(mean); acc["valid_false"].append(false_inv); acc["pull_warp"].append(pull_warp(impl, suite))
        acc["valid_occluded"].append(occluded_caught(impl, wide_occlusion(s, (u(-2, 2), u(-2, 2)), u(0, 360), radius=int(u(45, 80)))))
        while True:
            tb = (u(-3, 3), u(-3, 3)); tf = (u(-10, 10), u(-10, 10))
            if all(abs(x) >= 0.5 for x in (*tb, *tf)) and abs(abs(tb[0]) - abs(tb[1])) >= 0.5 and abs(abs(tf[0]) - abs(tf[1])) >= 0.5 and np.hypot(tf[0] - tb[0], tf[1] - tb[1]) >= 4:
                break
        for key, scale in (("two_region_s1", 1.0), ("two_region_s05", 0.5)):
            acc[key].append(two_region(impl, s, scale, tb, tf, TWO_REGION["radius"], TWO_REGION["size"]))
        print(f"  draw {i + 1} of {n}", end="\r", file=sys.stderr, flush=True)
    out = {}
    for row in ROWS:
        if row["key"] not in acc: continue
        x = np.asarray(acc[row["key"]]); bad = (x > row["limit"]) if row["kind"] == "max" else (x < row["limit"])
        out[row["key"]] = dict(min=float(x.min()), median=float(np.median(x)), max=float(x.max()), failing=int(bad.sum()), n=int(len(x)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--faults", action="store_true"); ap.add_argument("--seeds", type=int, default=0)
    ap.add_argument("--seed0", type=int, default=None); ap.add_argument("--json", action="store_true")
    a = ap.parse_args(); t0 = time.time()
    if a.seeds:
        res = fresh(a.seeds, a.seed0)
        if a.json: print(json.dumps(res, indent=1)); return 0
        print(f"\n{a.seeds} fresh draws, reference implementation, OpenCV {cv2.__version__}")
        for row in ROWS:
            if row["key"] not in res: continue
            r = res[row["key"]]
            print(f"  {row['mission']}  {row['label'][:74]:<74}  {row['threshold']:<26}  min {r['min']:.4f}  median {r['median']:.4f}  max {r['max']:.4f}  failing {r['failing']} of {r['n']}")
        print(f"  {time.time() - t0:.0f} s"); return 0
    if a.faults:
        ok = True
        ref = report(Reference())
        if any(r["verdict"] == "FAIL" for r in ref.values()):
            print("The reference itself fails a row. Fix that before reading the faults."); show(ref); return 1
        for f in FAULTS:
            res = report(f); failed = [row["key"] for row in ROWS if res[row["key"]]["verdict"] == "FAIL"]
            ok &= bool(failed)
            print(f"  {'caught' if failed else 'MISSED':<8} {f.name:<40} {', '.join(failed)}")
        print("FAULTS: " + ("every planted fault is caught" if ok else "a planted fault got through: the judge is not ready to lock"))
        return 0 if ok else 1
    res = report(Reference())
    if a.json: print(json.dumps(res, indent=1)); return 0 if all(r["verdict"] != "FAIL" for r in res.values()) else 1
    print(f"Pinned fixtures, reference implementation, OpenCV {cv2.__version__}, {cv2.getNumThreads()} threads")
    show(res)
    bad = [k for k, r in res.items() if r["verdict"] == "FAIL"]
    print(("REFERENCE: every row passes" if not bad else "REFERENCE FAILS: " + ", ".join(bad)) + f"   ({time.time() - t0:.0f} s)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
