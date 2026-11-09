"""Flow contract v1 as code: the conventions every other module and every consumer relies on.

docs/BLUEPRINT.md section 6 is the readable version. A change here is a contract change: bump CONTRACT_VERSION,
which changes every cache key, and write a line in docs/STATE.md.
"""
import hashlib
import json

import numpy as np

CONTRACT_VERSION = "flow-contract-v1"
RECEIPT_SCHEMA = "cvcops.receipt.v1"
CAPABILITIES_SCHEMA = "cvcops.capabilities.v1"

# Stored convention: x right, y down, pixels of the analysis image, forward from A to B. The worker never
# converts; exactly one node in the asset does.
STORED_CONVENTION = "opencv_px"
EXR_CHANNELS = {"R": "u", "G": "v", "B": "valid"}       # float32, ZIP; Houdini loads it at 32-bit

RECIPES = ("dis_medium", "dis_fast")                    # stock presets are recipes too
BACKENDS = ("cpu", "opencl", "cuda")                    # explicit; an unavailable one is an error
DEFAULT_TOLERANCE_PX = 1.0                              # validity: forward-backward agreement (FACTS M14)
WARN_CLIPPED_SHARE = 0.05                               # warn above 5% of analysis pixels clipped (FACTS M15)
WARN_MIN_GREY_LEVELS = 32                               # or below 32 grey levels
MAX_PATCH_SIZE_BEFORE_5_1 = 16                          # heap overflow above this before OpenCV 5.1 (FACTS C5)


class ContractError(ValueError):
    """Input that the contract forbids. The caller gets this, never a quiet repair."""


def check_analysis_pair(a, b):
    """DIS needs 8-bit, one channel, and both frames the same size. Nothing resizes implicitly."""
    for name, img in (("A", a), ("B", b)):
        if not isinstance(img, np.ndarray):
            raise ContractError(f"frame {name} is {type(img).__name__}, not a numpy array")
        if img.dtype != np.uint8 or img.ndim != 2:
            raise ContractError(f"frame {name} is {img.dtype} with shape {img.shape}; the contract needs 8-bit, one channel")
    if a.shape != b.shape:
        raise ContractError(f"frames differ in size, {a.shape} and {b.shape}; nothing resizes implicitly")


def check_flow(flow, shape):
    """Flow is float32 (H, W, 2) at the analysis image's size."""
    if not isinstance(flow, np.ndarray) or flow.dtype != np.float32 or flow.shape != tuple(shape) + (2,):
        got = (getattr(flow, "dtype", type(flow).__name__), getattr(flow, "shape", None))
        raise ContractError(f"flow must be float32 with shape {tuple(shape) + (2,)}; got {got}")


def analysis_stats(img):
    """Share of pixels at 0 or 255, distinct grey levels, and the warnings the node shows."""
    img = np.asarray(img)
    clipped = float(((img == 0) | (img == 255)).mean())
    levels = int(np.unique(img).size)
    warnings = []
    if clipped > WARN_CLIPPED_SHARE:
        warnings.append(f"{clipped:.1%} of analysis pixels are clipped; lower the gain or raise the gamma")
    if levels < WARN_MIN_GREY_LEVELS:
        warnings.append(f"only {levels} grey levels; raise the gain")
    return clipped, levels, warnings


def frame_pairs(first, last):
    """A bake of frames first..last pairs each frame with the next, so it needs analysis frames first..last+1."""
    if last < first:
        raise ContractError(f"frame range {first}-{last} is empty")
    return [(f, f + 1) for f in range(first, last + 1)]


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def param_digest(values):
    """Digest of the parameters that change the result, independent of key order."""
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def cache_key(input_digests, params_digest, recipe_sha256, backend, cv2_version, cv2_build_sha256, contract=CONTRACT_VERSION):
    """What makes a cached result fresh. Threads are not in it: DIS gives identical bytes at any count (FACTS M16)."""
    if backend not in BACKENDS:
        raise ContractError(f"unknown backend {backend!r}; one of {BACKENDS}")
    parts = [contract, *input_digests, params_digest, recipe_sha256, backend, cv2_version, cv2_build_sha256]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()
