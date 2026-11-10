"""Forward optical flow.

The threshold tests reach this function through tests/thresholds/impls.py, which maps a preset to a recipe name:
MEDIUM to "dis_medium", FAST to "dis_fast".

Each recipe is a module-level pure function (a, b) -> flow, named in contract.RECIPES. It runs stock DIS on numpy
arrays, so it runs on CPU: DIS takes its OpenCL path only with a UMat output (FACTS C4), and on the workstation
the OpenCL result differs from the CPU result (FACTS P6). No recipe touches cv2.ocl or the thread count; DIS
gives identical bytes at any thread count (FACTS M16).
"""
import hashlib
import inspect

import cv2
import numpy as np

from ..contract import MAX_PATCH_SIZE_BEFORE_5_1, RECIPES, ContractError, check_analysis_pair


def _before_5_1(version=None):
    major, minor = (int(x) for x in (version or cv2.__version__).split(".")[:2])
    return (major, minor) < (5, 1)


def _dis(preset):
    """A fresh DIS object at a stock preset, refused if its patch size could overflow before 5.1 (FACTS C5)."""
    dis = cv2.DISOpticalFlow_create(preset)
    if _before_5_1() and dis.getPatchSize() > MAX_PATCH_SIZE_BEFORE_5_1:
        raise ContractError(f"DIS patch size {dis.getPatchSize()} is above {MAX_PATCH_SIZE_BEFORE_5_1} on OpenCV {cv2.__version__}")
    return dis


def dis_medium(a, b):
    """Stock DIS at the MEDIUM preset, full resolution."""
    return _dis(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM).calc(a, b, None)


def dis_fast(a, b):
    """Stock DIS at the FAST preset, full resolution."""
    return _dis(cv2.DISOPTICAL_FLOW_PRESET_FAST).calc(a, b, None)


_RECIPE_FUNCTIONS = {"dis_medium": dis_medium, "dis_fast": dis_fast}
assert tuple(_RECIPE_FUNCTIONS) == RECIPES, "every recipe in the contract needs exactly one function"


def _recipe(name):
    if name not in _RECIPE_FUNCTIONS:
        raise ContractError(f"unknown recipe {name!r}; one of {RECIPES}")
    return _RECIPE_FUNCTIONS[name]


def recipe_source_sha256(name):
    """SHA-256 of the recipe's source, which the receipt records beside its name. It covers the recipe function
    and the DIS helper it calls, so a change to either changes every cache key."""
    src = inspect.getsource(_recipe(name)) + inspect.getsource(_dis)
    return hashlib.sha256(src.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def estimate_flow(a, b, recipe="dis_medium"):
    """Forward flow from frame a to frame b.

    a, b: uint8 arrays of shape (H, W), the same size (contract.check_analysis_pair).
    recipe: a name in contract.RECIPES. Each recipe is a named pure function; the receipt records its name and
    source hash.
    Returns float32 (H, W, 2) in opencv_px: the content at pixel p in a is at p + flow[p] in b.
    The same inputs, recipe and build give identical bytes at any thread count.
    """
    check_analysis_pair(a, b)
    fn = _recipe(recipe)
    flow = fn(np.ascontiguousarray(a), np.ascontiguousarray(b))
    return np.ascontiguousarray(flow, dtype=np.float32)
