"""Forward optical flow. Mission 1 writes the body; the signature and contract are fixed here.

The threshold tests reach this function through tests/thresholds/impls.py, which maps a preset to a recipe name:
MEDIUM to "dis_medium", FAST to "dis_fast".
"""
from ..contract import RECIPES, ContractError, check_analysis_pair


def estimate_flow(a, b, recipe="dis_medium"):
    """Forward flow from frame a to frame b.

    a, b: uint8 arrays of shape (H, W), the same size (contract.check_analysis_pair).
    recipe: a name in contract.RECIPES. Each recipe is a named pure function; the receipt records its name and
    source hash.
    Returns float32 (H, W, 2) in opencv_px: the content at pixel p in a is at p + flow[p] in b.
    The same inputs, recipe and build give identical bytes at any thread count.
    """
    check_analysis_pair(a, b)
    if recipe not in RECIPES:
        raise ContractError(f"unknown recipe {recipe!r}; one of {RECIPES}")
    raise NotImplementedError("estimate_flow is Mission 1's work (docs/BLUEPRINT.md, section 8)")
