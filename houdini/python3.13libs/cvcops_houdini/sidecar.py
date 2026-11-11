"""The analysis sidecar, Houdini's half: the prep values written beside the analysis frames (decision 0004).

Imports neither hou nor cv2. The worker reads the file back with cvcops.receipt.read_analysis_sidecar, under its
own schema id, never the receipt's.
"""
import json
import os
import tempfile

SCHEMA = "cvcops.analysis_sidecar.v1"


def fragment(luma_weights, gain, gamma, analysis_scale, fps):
    """The sidecar's content from the asset's control values. analysis_scale is the menu token, such as "0.5"."""
    return {"schema": SCHEMA,
            "analysis": {"luminance_weights": [float(w) for w in luma_weights], "gain": float(gain),
                         "gamma": float(gamma), "scale": float(analysis_scale), "color_space": None},
            "frame": {"fps": float(fps) if fps else None}}


def path_for(cache_dir, prefix="analysis"):
    return os.path.join(cache_dir, prefix + ".json")


def write(cache_dir, data, prefix="analysis"):
    """Write through a temporary name in the same folder, then os.replace, so the worker never reads half."""
    target = path_for(cache_dir, prefix)
    fd, tmp = tempfile.mkstemp(prefix=".cvcops-", suffix=".json.tmp", dir=cache_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=1)
            f.write("\n")
        os.replace(tmp, target)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return target


def matches(cache_dir, data, prefix="analysis"):
    """True when the sidecar on disk holds these values: Check Cache reports changed analysis settings otherwise."""
    try:
        with open(path_for(cache_dir, prefix), encoding="utf-8") as f:
            return json.load(f) == data
    except (OSError, ValueError):
        return False
