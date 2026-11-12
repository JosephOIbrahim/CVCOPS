"""CVCOPs engine (working title): OpenCV perception for Houdini 22 Copernicus.

Pure: nothing under src/ imports hou, SYNAPSE, the evidence scripts or the tests (tests/thresholds/test_guards.py).
Arrays and parameters go in; arrays and a receipt come out.
"""
__version__ = "0.1.0"

from .contract import CONTRACT_VERSION, RECEIPT_SCHEMA  # noqa: E402,F401
