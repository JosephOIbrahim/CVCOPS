"""Temporal check: rank frames by change the flow cannot explain. Parked until v0.1 ships (decision 0003).

Do not write the bodies before the check's rows are in the blueprint's threshold table and locked. The
signatures and the definition are fixed here so the manifest's parked `temporal_check` operation, the
opportunity register and SYNAPSE's first question (which frames deserve attention) all mean the same thing.
The reference that already computes it on test frames is evidence/opportunities_reference.py.
"""


def pair_residual(a, pulled_b, valid):
    """Mean absolute difference, in 8-bit levels, between frame A and frame B pulled onto A's grid.

    a: uint8 (H, W). pulled_b: float32 (H, W), frame B sampled at p + flow(p). valid: bool (H, W); only
    trusted pixels count, so an occlusion does not read as a pop.
    """
    raise NotImplementedError("the temporal check is parked until v0.1 ships (docs/OPPORTUNITIES.md)")


def frame_scores(pair_residuals):
    """One score per frame: the smaller of its two neighbour residuals.

    pair_residuals[k] is the residual between frames k and k + 1. A pop disagrees with both neighbours and
    scores high; a hard cut disagrees with one, so by this definition it should not rank. The first and last
    frames have one neighbour and take that residual.
    """
    raise NotImplementedError("the temporal check is parked until v0.1 ships (docs/OPPORTUNITIES.md)")
