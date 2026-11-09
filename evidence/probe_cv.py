import os, sys, time, json, tempfile
os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"      # must be set before importing cv2
import numpy as np, cv2

out = {}
out["cv2"] = cv2.__version__
out["numpy"] = np.__version__
out["python"] = sys.version.split()[0]
out["threads"] = cv2.getNumThreads()
out["cpu_count"] = os.cpu_count()
bi = cv2.getBuildInformation()
def grab(key):
    for line in bi.splitlines():
        if key in line:
            return " ".join(line.split())
    return None
for k in ["OpenCL:", "OpenEXR:", "NVIDIA CUDA:", "Parallel framework:", "CPU/HW features", "Baseline:", "C++ standard:", "To be built:", "Unavailable:", "FFMPEG:"]:
    out["build " + k] = grab(k)
out["ocl.haveOpenCL"] = cv2.ocl.haveOpenCL()
out["ocl.useOpenCL"] = cv2.ocl.useOpenCL()
out["has cv2.cuda"] = hasattr(cv2, "cuda")
try:
    out["cuda devices"] = cv2.cuda.getCudaEnabledDeviceCount()
except Exception as e:
    out["cuda devices"] = "ERR " + str(e)[:80]
out["has NvidiaOpticalFlow_2_0"] = hasattr(cv2, "cuda_NvidiaOpticalFlow_2_0") or (hasattr(cv2, "cuda") and hasattr(cv2.cuda, "NvidiaOpticalFlow_2_0"))
out["has DISOpticalFlow_create"] = hasattr(cv2, "DISOpticalFlow_create")
out["has DISOpticalFlow.create"] = hasattr(getattr(cv2, "DISOpticalFlow", None), "create")
out["DIS presets"] = {n: getattr(cv2, n) for n in dir(cv2) if n.startswith("DISOPTICAL_FLOW_PRESET") or n.startswith("DISOpticalFlow_PRESET")}
out["has findTransformECCMultiScale"] = hasattr(cv2, "findTransformECCMultiScale")
out["has optflow (contrib)"] = hasattr(cv2, "optflow")
print(json.dumps(out, indent=1))
