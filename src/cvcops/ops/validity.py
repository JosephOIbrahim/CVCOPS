"""Validity flag: forward-backward agreement, an in-frame destination, and an optional mask on A's grid.

The formulation is the one the M1 thresholds were measured on (FACTS M12 to M14): the backward flow is sampled
bilinearly at p + f(p); a destination outside the frame reads a far-off sentinel, so it fails; the bounds are
inclusive; and a pixel passes when |f(p) + back(p)| <= tolerance.
"""
import math

import cv2
import numpy as np

from ..contract import DEFAULT_TOLERANCE_PX, ContractError, check_analysis_pair, check_flow
from .flow import estimate_flow

_OUTSIDE = 1e6                                          # backward flow read past the frame: never agrees


def _check_tolerance(tolerance_px):
    if not isinstance(tolerance_px, (int, float)) or isinstance(tolerance_px, bool) or not math.isfinite(tolerance_px) or tolerance_px < 0:
        raise ContractError(f"tolerance_px must be a finite number of pixels at or above 0, not {tolerance_px!r}")


def _check_mask(mask, shape):
    if not isinstance(mask, np.ndarray) or mask.dtype != bool or mask.shape != tuple(shape):
        got = (getattr(mask, "dtype", type(mask).__name__), getattr(mask, "shape", None))
        raise ContractError(f"mask must be bool with shape {tuple(shape)}, on frame A's grid; got {got}")


def forward_backward_valid(forward, backward, tolerance_px=DEFAULT_TOLERANCE_PX, mask=None):
    """Bool (H, W) from two flows: forward A to B, backward B to A, both float32 (H, W, 2) in opencv_px.

    mask, if given, is bool (H, W) on A's grid; pixels where it is False are invalid, the rest unchanged.
    """
    if not isinstance(forward, np.ndarray) or forward.ndim != 3:
        raise ContractError(f"forward flow must be float32 (H, W, 2); got {getattr(forward, 'shape', type(forward).__name__)}")
    shape = forward.shape[:2]
    check_flow(forward, shape)
    check_flow(backward, shape)
    _check_tolerance(tolerance_px)
    if mask is not None:
        _check_mask(mask, shape)
    h, w = shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    dest_x = xs + forward[..., 0]
    dest_y = ys + forward[..., 1]
    back = cv2.remap(backward, dest_x, dest_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=_OUTSIDE)
    inside = (dest_x >= 0) & (dest_x <= w - 1) & (dest_y >= 0) & (dest_y <= h - 1)
    valid = (np.sqrt(((forward + back) ** 2).sum(-1)) <= tolerance_px) & inside
    if mask is not None:
        valid &= mask
    return valid


def validity(a, b, tolerance_px=DEFAULT_TOLERANCE_PX, recipe="dis_medium", mask=None):
    """Bool (H, W): True where the forward flow is trusted.

    A pixel is valid when the backward flow at its destination brings it back within tolerance_px, the
    destination lies inside the frame, and the optional mask (bool (H, W), on A's grid; 0 is invalid) is True
    there. It is a flag, not a confidence: it catches wide occlusions and misses narrow ones (FACTS M14).
    """
    check_analysis_pair(a, b)
    _check_tolerance(tolerance_px)
    if mask is not None:
        _check_mask(mask, a.shape)
    forward = estimate_flow(a, b, recipe)
    backward = estimate_flow(b, a, recipe)
    return forward_backward_valid(forward, backward, tolerance_px, mask)
