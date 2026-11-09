"""Known-translation optical-flow probe. Synthetic, no external data."""
import os, sys, time, json
import numpy as np, cv2

def texture(h, w, seed=7):
    """Band-limited periodic noise, uint8-range float. Periodic => Fourier shift is exact."""
    rng = np.random.default_rng(seed)
    spec = rng.normal(size=(h, w)) + 1j * rng.normal(size=(h, w))
    fy = np.fft.fftfreq(h)[:, None]; fx = np.fft.fftfreq(w)[None, :]
    r = np.sqrt(fx * fx + fy * fy)
    spec *= np.exp(-(r / 0.06) ** 2)          # low-pass: features ~8-16 px
    img = np.fft.ifft2(spec).real
    img = (img - img.min()) / (img.max() - img.min())
    return img

def fourier_shift(img, dx, dy):
    """Content moves by +dx (right) and +dy (down): out(y, x) = img(y - dy, x - dx)."""
    h, w = img.shape
    fy = np.fft.fftfreq(h)[:, None]; fx = np.fft.fftfreq(w)[None, :]
    return np.fft.ifft2(np.fft.fft2(img) * np.exp(-2j * np.pi * (fx * dx + fy * dy))).real

def to_u8(img):
    return np.clip(np.rint(img * 255.0), 0, 255).astype(np.uint8)

def epe(flow, dx, dy, margin):
    f = flow[margin:-margin, margin:-margin]
    e = np.sqrt((f[..., 0] - dx) ** 2 + (f[..., 1] - dy) ** 2)
    return float(e.mean()), float(np.percentile(e, 95)), float(f[..., 0].mean()), float(f[..., 1].mean())

res = {}
h, w = 540, 960
a = texture(h, w)
A = to_u8(a)
cases = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (3.0, -2.0), (0.5, 0.25), (-7.3, 4.6), (24.0, 0.0), (60.0, 0.0)]
presets = {"ULTRAFAST": cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST, "FAST": cv2.DISOPTICAL_FLOW_PRESET_FAST, "MEDIUM": cv2.DISOPTICAL_FLOW_PRESET_MEDIUM}
rows = []
for name, preset in presets.items():
    dis = cv2.DISOpticalFlow_create(preset)
    for dx, dy in cases:
        B = to_u8(fourier_shift(a, dx, dy))
        flow = dis.calc(A, B, None)
        m, p95, mx, my = epe(flow, dx, dy, 48)
        rows.append((name, dx, dy, round(mx, 3), round(my, 3), round(m, 4), round(p95, 4)))
print("DIS  preset      true(dx,dy)      mean flow(x,y)      EPE mean / p95   [960x540, interior]")
for r in rows:
    print(f"  {r[0]:<9} ({r[1]:>6.2f},{r[2]:>6.2f})   ({r[3]:>8.3f},{r[4]:>8.3f})   {r[5]:.4f} / {r[6]:.4f}")

# output type / shape / determinism
dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
B = to_u8(fourier_shift(a, 3.0, -2.0))
f1 = dis.calc(A, B, None); f2 = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM).calc(A, B, None)
res["flow dtype/shape"] = (str(f1.dtype), f1.shape)
res["deterministic (fresh object, same inputs)"] = bool(np.array_equal(f1, f2))
f3 = dis.calc(A, B, None)
res["deterministic (reused object)"] = bool(np.array_equal(f1, f3))

# does DIS accept float input?
try:
    dis.calc(a.astype(np.float32), fourier_shift(a, 1, 0).astype(np.float32), None); res["DIS float32 input"] = "accepted"
except cv2.error as e:
    res["DIS float32 input"] = "rejected: " + str(e).strip().splitlines()[-1][:110]

# UMat path with OpenCL unavailable -> silent CPU?
res["ocl.haveOpenCL"] = cv2.ocl.haveOpenCL()
cv2.ocl.setUseOpenCL(True)
res["ocl.useOpenCL after setUseOpenCL(True)"] = cv2.ocl.useOpenCL()
try:
    fu = dis.calc(cv2.UMat(A), cv2.UMat(B), None)
    res["UMat calc returns"] = type(fu).__name__
    res["UMat result equals CPU result"] = bool(np.array_equal(fu.get(), f1))
except Exception as e:
    res["UMat calc"] = "ERR " + str(e)[:100]

# Farneback for comparison at the same case
ff = cv2.calcOpticalFlowFarneback(A, B, None, 0.5, 5, 21, 5, 7, 1.5, 0)
res["Farneback (3,-2) EPE mean/p95, mean flow"] = [round(v, 4) for v in epe(ff, 3.0, -2.0, 48)]

# forward-backward consistency as a validity signal
fb = dis.calc(B, A, None)
ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
bw = cv2.remap(fb, xs + f1[..., 0], ys + f1[..., 1], cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
fberr = np.sqrt(((f1 + bw) ** 2).sum(-1))
res["FB error interior mean / p95 (px)"] = [round(float(fberr[48:-48, 48:-48].mean()), 4), round(float(np.percentile(fberr[48:-48, 48:-48], 95)), 4)]

# timing (this sandbox: tiny CPU; order-of-magnitude only)
for (hh, ww) in [(1080, 1920), (2160, 3840)]:
    t = texture(hh, ww, 3); TA = to_u8(t); TB = to_u8(fourier_shift(t, 2.5, 1.5))
    for name in ("FAST", "MEDIUM"):
        d = cv2.DISOpticalFlow_create(presets[name]); d.calc(TA, TB, None)
        ts = []
        for _ in range(3):
            t0 = time.perf_counter(); fl = d.calc(TA, TB, None); ts.append(time.perf_counter() - t0)
        m, p95, mx, my = epe(fl, 2.5, 1.5, 64)
        res[f"time {ww}x{hh} DIS {name} (ms, median of 3, {cv2.getNumThreads()} threads)"] = round(1000 * sorted(ts)[1], 1)
        res[f"EPE  {ww}x{hh} DIS {name}"] = round(m, 4)
print(json.dumps(res, indent=1))
