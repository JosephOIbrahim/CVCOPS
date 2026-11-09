"""
Dense optical flow recipe, seeded from sweep.py's winner. Same contract as initial_program.py.
"""
import cv2
import numpy as np


# EVOLVE-BLOCK-START
def estimate_flow(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    dis.setFinestScale(1)
    dis.setPatchStride(3)
    dis.setGradientDescentIterations(25)
    dis.setVariationalRefinementIterations(2)
    return dis.calc(a, b, None)


# EVOLVE-BLOCK-END
