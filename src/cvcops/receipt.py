"""Receipts: one JSON file per frame pair, written last, and the freshness rule that reads them back.

The shape is fixed by docs/contracts/receipt.schema.json (cvcops.receipt.v1), with an example beside it. SYNAPSE's
adapter turns each receipt into an observation (docs/contracts/synapse_observation_mapping.md). Houdini's prep values
arrive in a sidecar beside the analysis frames, under its own schema id (decision 0004).
"""
import datetime
import hashlib
import inspect
import json
import math
import os
import re

import numpy as np

from . import contract
from .contract import ContractError

SIDECAR_SCHEMA = "cvcops.analysis_sidecar.v1"
SIDECAR_FIELDS = ("analysis.luminance_weights", "analysis.gain", "analysis.gamma", "analysis.scale",
                  "analysis.color_space", "frame.fps")
MEASURED_FIELDS = ("clipped_share", "grey_levels", "warnings", "image")
NO_SIDECAR = {"analysis": {"luminance_weights": None, "gain": None, "gamma": None, "scale": 1.0, "color_space": None},
              "frame": {"fps": None}}
TIMING_KEYS = ("read", "hash", "flow", "validity", "write", "total")
REQUIRED = ("schema", "status", "contract", "engine", "frame", "inputs", "image", "analysis", "recipe", "validity",
            "cv2", "backend", "threads", "cache_key", "created_utc")
OPTIONAL = ("error", "output", "params", "summary", "timings_s")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_HASHES = re.compile(r"#+")


# ---- frame patterns -------------------------------------------------------------------------------------------
def _hash_run(pattern):
    runs = list(_HASHES.finditer(os.path.basename(str(pattern))))
    if len(runs) != 1:
        raise ContractError(f"{pattern!r} must name the frame number with one run of #, such as analysis.####.exr")
    return runs[0]


def frame_path(pattern, frame):
    """bake/analysis.####.exr and 1001 -> bake/analysis.1001.exr; the number is zero-padded to the count of #."""
    pattern = str(pattern)
    run = _hash_run(pattern)
    head, base = os.path.split(pattern)
    name = base[:run.start()] + f"{frame:0{run.end() - run.start()}d}" + base[run.end():]
    return os.path.join(head, name) if head else name


def output_paths(out_dir, pattern, a):
    """Where pair (a, a + 1) writes: flow.<a>.exr and its receipt flow.<a>.json, padded like the input."""
    run = _hash_run(pattern)
    stem = os.path.join(str(out_dir), f"flow.{a:0{run.end() - run.start()}d}")
    return stem + ".exr", stem + ".json"


def sidecar_path(pattern):
    """bake/analysis.####.exr -> bake/analysis.json."""
    pattern = str(pattern)
    run = _hash_run(pattern)
    head, base = os.path.split(pattern)
    prefix = base[:run.start()].rstrip("._-") or "analysis"
    return os.path.join(head, prefix + ".json")


def posix_abspath(path):
    return os.path.abspath(str(path)).replace("\\", "/")


# ---- the sidecar ----------------------------------------------------------------------------------------------
def _number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def read_analysis_sidecar(pattern):
    """The prep values Houdini's export recorded, or the no-sidecar values: scale 1.0 (the source as given), the
    rest null. A file that breaks cvcops.analysis_sidecar.v1 is a ContractError, never half-read."""
    path = sidecar_path(pattern)
    values = {"analysis": dict(NO_SIDECAR["analysis"]), "frame": dict(NO_SIDECAR["frame"])}
    if not os.path.exists(path):
        return values
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        raise ContractError(f"{path}: not a readable sidecar: {e}")
    if not isinstance(data, dict) or data.get("schema") != SIDECAR_SCHEMA:
        raise ContractError(f"{path}: schema must be {SIDECAR_SCHEMA!r}, not {getattr(data, 'get', lambda k: None)('schema')!r}")
    for key in data:
        if key not in ("schema", "analysis", "frame"):
            raise ContractError(f"{path}: unknown key {key!r}; a sidecar sets only {', '.join(SIDECAR_FIELDS)}")
    for section in ("analysis", "frame"):
        given = data.get(section, {})
        if not isinstance(given, dict):
            raise ContractError(f"{path}: {section} must be an object")
        for key, value in given.items():
            if section == "analysis" and key in MEASURED_FIELDS:
                raise ContractError(f"{path}: analysis.{key} is measured by the worker; a sidecar cannot set it")
            if f"{section}.{key}" not in SIDECAR_FIELDS:
                raise ContractError(f"{path}: unknown key {section}.{key}; a sidecar sets only {', '.join(SIDECAR_FIELDS)}")
            _check_sidecar_value(path, f"{section}.{key}", value)
            values[section][key] = value
    return values


def _check_sidecar_value(path, field, value):
    if field == "analysis.luminance_weights":
        ok = value is None or (isinstance(value, list) and len(value) == 3 and all(_number(v) for v in value))
    elif field == "analysis.scale":
        ok = _number(value) and 0 < value <= 1
    elif field == "analysis.color_space":
        ok = value is None or isinstance(value, str)
    else:
        ok = value is None or _number(value)
    if not ok:
        raise ContractError(f"{path}: {field} = {value!r} is not allowed")


# ---- the build, the code and the cache key --------------------------------------------------------------------
def cv2_identity():
    """(cv2.__version__, SHA-256 of cv2.getBuildInformation() with line endings normalised). The only place the
    build is read, at call time, so a test can stand in another build."""
    import cv2
    info = cv2.getBuildInformation().replace("\r\n", "\n").replace("\r", "\n")
    return cv2.__version__, hashlib.sha256(info.encode("utf-8")).hexdigest()


def _source_sha256(*functions):
    text = "\n".join(inspect.getsource(f) for f in functions)
    return hashlib.sha256(text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")).hexdigest()


def code_hashes():
    """Source hashes of the code that turns analysis frames into a flow file, line endings normalised."""
    from . import io_exr
    from .ops import flow, validity
    reader = _source_sha256(io_exr.read_analysis_exr, io_exr._grey_channel)
    reader = hashlib.sha256(f"{reader}\n{io_exr._ALPHA.pattern}".encode("utf-8")).hexdigest()
    return {"read_analysis_exr": reader,
            "estimate_flow": _source_sha256(flow.estimate_flow),
            "validity": _source_sha256(validity.forward_backward_valid, validity.validity)}


def request_params(tolerance_px):
    values = {"tolerance_px": float(tolerance_px), "mask": False, "source_sha256": code_hashes()}
    return {"digest": contract.param_digest(values), "values": values}


def expected_cache_key(input_digests, recipe, backend, tolerance_px, identity=None):
    """The key a fresh result for this request on this build must carry. Threads and the engine version are not in
    it; the frame digests, the request, the code and the build are."""
    from .ops.flow import recipe_source_sha256
    version, build = identity or cv2_identity()
    return contract.cache_key(list(input_digests), request_params(tolerance_px)["digest"],
                              recipe_source_sha256(recipe), backend, version, build)


# ---- assembling and writing ------------------------------------------------------------------------------------
def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def summary(flow, valid):
    """valid_share, and the median and 99th percentile motion over valid pixels when there are any."""
    out = {"valid_share": float(np.mean(valid))}
    if valid.any():
        mag = np.sqrt((flow[valid].astype(np.float64) ** 2).sum(-1))
        out["median_motion_px"] = float(np.median(mag))
        out["p99_motion_px"] = float(np.percentile(mag, 99))
    return out


def build_receipt(*, status, a, b, inputs, image, analysis, sidecar, recipe, backend, tolerance_px, cache_key,
                  identity, threads, opencl_in_use, device=None, output=None, error=None, summary=None,
                  timings=None):
    """A receipt dict in cvcops.receipt.v1. inputs maps 'a' and 'b' to (path, sha256); output is (path, sha256)."""
    from . import __version__
    from .ops.flow import recipe_source_sha256
    version, build = identity
    data = {
        "schema": contract.RECEIPT_SCHEMA,
        "status": status,
        "contract": contract.CONTRACT_VERSION,
        "engine": {"package": __package__, "version": __version__},
        "frame": {"a": int(a), "b": int(b), "fps": sidecar["frame"]["fps"], "interval": float(b - a)},
        "inputs": {k: {"path": posix_abspath(p), "sha256": h} for k, (p, h) in inputs.items()},
        "image": {"width": int(image[1]), "height": int(image[0])},
        "analysis": {**sidecar["analysis"], **analysis},
        "params": request_params(tolerance_px),
        "recipe": {"name": recipe, "source_sha256": recipe_source_sha256(recipe)},
        "validity": {"tolerance_px": float(tolerance_px), "mask": False},
        "cv2": {"version": version, "build_sha256": build},
        "backend": {"requested": backend, "ran": backend, "opencl_in_use": bool(opencl_in_use), "device": device},
        "threads": int(threads),
        "cache_key": cache_key,
        "created_utc": utc_now(),
    }
    if output is not None:
        data["output"] = {"path": posix_abspath(output[0]), "sha256": output[1]}
    if error is not None:
        data["error"] = str(error)
    if summary is not None:
        data["summary"] = summary
    if timings is not None:
        data["timings_s"] = {k: float(timings.get(k, 0.0)) for k in TIMING_KEYS}
    return data


def check_receipt(data):
    """The schema's rules, checked by hand so the worker needs no jsonschema. Raises ContractError."""
    def need(cond, msg):
        if not cond:
            raise ContractError(f"receipt: {msg}")

    need(isinstance(data, dict), "not an object")
    missing = [k for k in REQUIRED if k not in data]
    need(not missing, f"missing {missing}")
    extra = [k for k in data if k not in REQUIRED + OPTIONAL]
    need(not extra, f"unknown keys {extra}")
    need(data["schema"] == contract.RECEIPT_SCHEMA, "wrong schema")
    need(data["status"] in ("ok", "error"), "status is ok or error")
    need(data["contract"] == contract.CONTRACT_VERSION, "wrong contract")
    sections = ("engine", "frame", "inputs", "image", "analysis", "recipe", "validity", "cv2", "backend")
    for key in sections + tuple(k for k in ("output", "params", "summary", "timings_s") if k in data):
        need(isinstance(data[key], dict), f"{key} is an object")
    need(set(data["inputs"]) >= {"a", "b"} and all(isinstance(f, dict) for f in data["inputs"].values()),
         "inputs a and b are objects")
    need(data["status"] != "ok" or "output" in data, "an ok receipt names its output")
    need(data["status"] != "error" or isinstance(data.get("error"), str), "an error receipt says why")
    be = data["backend"]
    need(isinstance(be, dict) and be.get("requested") in contract.BACKENDS and be.get("ran") in contract.BACKENDS,
         "backend requested and ran are cpu, opencl or cuda")
    need(isinstance(be.get("opencl_in_use"), bool), "backend.opencl_in_use is a boolean")
    if data["status"] == "ok":
        need(be["ran"] == be["requested"], "an ok receipt ran on the backend it asked for")
        need(be["requested"] != "opencl" or be["opencl_in_use"], "an ok opencl receipt used OpenCL")
    shas = [data["cache_key"], data["recipe"].get("source_sha256"), data["cv2"].get("build_sha256")]
    shas += [f.get("sha256") for f in data["inputs"].values()]
    shas += [data["output"].get("sha256")] if "output" in data else []
    shas += [data["params"].get("digest")] if "params" in data else []
    need(all(isinstance(s, str) and _SHA.match(s) for s in shas), "every sha256 is 64 lowercase hex digits")
    an = data["analysis"]
    need(_number(an.get("scale")) and 0 < an["scale"] <= 1, "analysis.scale is in (0, 1]")
    need(_number(an.get("clipped_share")) and 0 <= an["clipped_share"] <= 1, "analysis.clipped_share is in [0, 1]")
    need(isinstance(an.get("grey_levels"), int) and 0 <= an["grey_levels"] <= 256, "analysis.grey_levels is 0 to 256")
    need(_number(data["validity"].get("tolerance_px")) and data["validity"]["tolerance_px"] > 0, "tolerance above 0")
    need(isinstance(data["threads"], int) and data["threads"] >= 1, "threads is at least 1")
    im = data["image"]
    need(isinstance(im.get("width"), int) and isinstance(im.get("height"), int) and im["width"] >= 1 and im["height"] >= 1,
         "image width and height are at least 1")
    need(all(_number(v) and v >= 0 for v in data.get("timings_s", {}).values()), "timings are numbers at or above 0")


def write_receipt(path, data):
    """Check data against the schema's rules, write it to a temporary name, then os.replace onto path."""
    from .io_exr import write_atomic
    check_receipt(data)
    text = json.dumps(data, indent=2, sort_keys=False) + "\n"

    def write(tmp):
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    write_atomic(path, write, suffix=".json")


def read_receipt(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    check_receipt(data)
    return data


# ---- freshness ------------------------------------------------------------------------------------------------
def freshness(receipt_path, expected_cache_key, flow_path):
    """('fresh' | 'stale' | 'missing', reason).

    missing: no receipt, or no flow file. stale: an unreadable or malformed receipt, status error, an input frame
    gone, another cache key (code, build, inputs or request changed), or a flow file that differs from its receipt.
    expected_cache_key None means it could not be computed, which is stale."""
    if not os.path.exists(receipt_path):
        return "missing", "no receipt"
    if not os.path.exists(flow_path):
        return "missing", "no flow file"
    try:
        data = read_receipt(receipt_path)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:      # ContractError is a ValueError
        return "stale", f"unreadable or malformed receipt: {type(e).__name__}: {e}"
    if data["status"] != "ok":
        return "stale", f"the last run failed: {data.get('error', '')}"
    for key, f in data["inputs"].items():
        if not os.path.exists(f["path"]):
            return "stale", f"input frame {key} is gone: {f['path']}"
    if expected_cache_key is None or data["cache_key"] != expected_cache_key:
        return "stale", "the cache key differs: the inputs, the request, the code or the OpenCV build changed"
    if contract.sha256_file(flow_path) != data["output"]["sha256"]:
        return "stale", "the flow file differs from the one its receipt records"
    return "fresh", "the receipt matches the inputs, the request, the code and the build"


def verify_report(first, last, pairs):
    """pairs is a list of (a, b, state, reason). The shape verify --json prints (decision 0004)."""
    counts = {"fresh": 0, "stale": 0, "missing": 0}
    for _, _, state, _ in pairs:
        counts[state] += 1
    return {"frames": {"first": int(first), "last": int(last)}, "counts": counts,
            "pairs": [{"a": int(a), "b": int(b), "state": s, "reason": r} for a, b, s, r in pairs]}
