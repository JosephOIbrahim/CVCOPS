"""Houdini-side helpers for the asset: the Bake button and the cache status it shows. Mission 3 writes them.

This code runs inside Houdini, so it may import hou. It never imports cv2 or any OpenCV package
(tests/thresholds/test_guards.py): the worker runs as a separate process, with the interpreter the package file
names in CVCOPS_WORKER_PYTHON. Houdini 22 looks for Python modules in python3.13libs on its path (FACTS H5).
"""
