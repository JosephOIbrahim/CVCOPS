"""Float32 EXR round trip for flow data with the OpenEXR Python package (pip install OpenEXR numpy).
OpenCV 5 no longer bundles OpenEXR, so the worker does not use cv2 for EXR."""
import os, sys, time, tempfile
import numpy as np
import OpenEXR

h, w = (2160, 3840) if len(sys.argv) < 3 else (int(sys.argv[1]), int(sys.argv[2]))
rng = np.random.default_rng(1)
u = (rng.standard_normal((h, w)) * 37.0).astype(np.float32)        # signed, larger than 1, sub-pixel detail
v = (rng.standard_normal((h, w)) * 11.0).astype(np.float32)
valid = (rng.random((h, w)) > 0.1).astype(np.float32)
path = os.path.join(tempfile.mkdtemp(), "flow_test.exr")

header = {"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage}
t0 = time.perf_counter()
with OpenEXR.File(header, {"R": u, "G": v, "B": valid}) as f:
    f.write(path)
t_write = time.perf_counter() - t0

t0 = time.perf_counter()
with OpenEXR.File(path, separate_channels=True) as f:
    ch = f.channels()
    names = sorted(ch)
    U, V, VA = ch["R"].pixels, ch["G"].pixels, ch["B"].pixels
t_read = time.perf_counter() - t0

print("OpenEXR", getattr(OpenEXR, "__version__", "?"), "| channels", names, "| dtype", U.dtype, "| shape", U.shape)
print("bit-exact round trip:", bool(np.array_equal(U, u) and np.array_equal(V, v) and np.array_equal(VA, valid)))
print(f"{w}x{h} float32 x3 ZIP (random data = worst case): write {t_write*1000:.0f} ms, read {t_read*1000:.0f} ms, "
      f"{os.path.getsize(path)/2**20:.1f} MiB")
