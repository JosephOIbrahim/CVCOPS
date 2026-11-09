"""EXR in and out, through the OpenEXR package (OpenCV 5 wheels have none). Mission 2 writes the bodies."""


def write_flow_exr(path, rgb):
    """Write float32 (H, W, 3), channels R=u, G=v, B=valid, as 32-bit float with ZIP compression.

    Write to a temporary name in the same folder, then os.replace onto path, so a reader never sees half a file.
    The M2 threshold row sends the transport pattern (evidence/thresholds_reference.py) through this and
    read_flow_exr, and demands bit-exact bytes back.
    """
    raise NotImplementedError("write_flow_exr is Mission 2's work")


def read_flow_exr(path):
    """Return float32 (H, W, 3) exactly as written."""
    raise NotImplementedError("read_flow_exr is Mission 2's work")


def read_analysis_exr(path):
    """Read a grey analysis frame written raw by ROP Image and return uint8 (H, W), rounded to the nearest level.

    Probe P3 decides which channel carries the grey value and whether rows arrive top-down.
    """
    raise NotImplementedError("read_analysis_exr is Mission 2's work")
