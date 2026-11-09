"""
Dense optical flow recipe: the hot function of the worker.

Contract (do not change):
    estimate_flow(a, b) -> flow
    a, b : uint8, shape (H, W), same size. Frame A and the frame after it.
    flow : float32, shape (H, W, 2). Forward flow on A's grid, in pixels,
           x to the right and y downward: the content at p in A is at p + flow[p] in B.
    Pure function: no files, no globals, no memory of earlier calls.

The seed is OpenCV's DIS at the MEDIUM preset on the full-resolution images. It is
accurate and it is the thing to beat. The scorer only cares that the result still
matches ground truth (a hard gate) and that it is faster.
"""
import cv2
import numpy as np


# EVOLVE-BLOCK-START
def estimate_flow(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    return dis.calc(a, b, None)


# EVOLVE-BLOCK-END
