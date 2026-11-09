"""Validity flag. Mission 1 writes the body; the signature and contract are fixed here."""
from ..contract import DEFAULT_TOLERANCE_PX, check_analysis_pair


def validity(a, b, tolerance_px=DEFAULT_TOLERANCE_PX, recipe="dis_medium", mask=None):
    """Bool (H, W): True where the forward flow is trusted.

    A pixel is valid when the backward flow at its destination brings it back within tolerance_px, the
    destination lies inside the frame, and the optional mask (bool (H, W)) is True there. It is a flag, not a
    confidence: it catches wide occlusions and misses narrow ones (FACTS M14).
    """
    check_analysis_pair(a, b)
    raise NotImplementedError("validity is Mission 1's work (docs/BLUEPRINT.md, section 8)")
