"""Reproduce two recorder defects from motion-cops @ d2a22ad without Houdini.
Extracts only four pure functions (reviewed by hand) by AST; stubs `hou`."""
import ast, sys, math, types
import numpy as np

src_path = sys.argv[1]
tree = ast.parse(open(src_path, encoding="utf-8").read())
want = {"_storage_layout", "_layer_values", "_sample_frames", "_frame_index"}
mod = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in want], type_ignores=[])

class _ST:  # stand-in for hou.imageLayerStorageType
    Float32, Float16, Fixed8, Fixed16, Int8, Int16, Int32 = range(7)
hou = types.SimpleNamespace(imageLayerStorageType=_ST, NodeError=RuntimeError)
ns = {"np": np, "math": math, "hou": hou}
exec(compile(mod, src_path, "exec"), ns)

class FakeLayer:
    def __init__(self, arr, storage): self.a, self.s = arr, storage
    def storageType(self): return self.s
    def bufferResolution(self): return (self.a.shape[1], self.a.shape[0])
    def channelCount(self): return self.a.shape[2]
    def allBufferElements(self): return self.a.tobytes()

white8 = np.full((2, 2, 3), 255, np.uint8)
lum, _, _ = ns["_layer_values"](FakeLayer(white8, _ST.Fixed8), 5, False)       # 5 = luminance mode
red, _, _ = ns["_layer_values"](FakeLayer(white8, _ST.Fixed8), 1, False)       # 1 = first channel
print("Fixed8 white  | luminance mode ->", float(lum[0, 0]), "| single-channel mode ->", float(red[0, 0]))
white16 = np.full((2, 2, 3), 65535, np.uint16)
lum16, _, _ = ns["_layer_values"](FakeLayer(white16, _ST.Fixed16), 5, False)
print("Fixed16 white | luminance mode ->", float(lum16[0, 0]))

class FakeNode:
    def __init__(self, f, sub=1): self.f, self.sub = f, sub
    def evalParmTuple(self, name): return self.f
    def evalParm(self, name): return self.sub
frames = ns["_sample_frames"](FakeNode((1.0, 2.0, 0.3)))
state = {"frames": frames}
print("schedule (1, 2, 0.3) ->", [round(f, 4) for f in frames])
print("lookup per sample   ->", [ns["_frame_index"](state, f) for f in frames])
