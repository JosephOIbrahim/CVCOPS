"""The worker's command line: one process per bake, files in and files out.

    python -m cvcops capabilities           print the manifest an agent registers tools from
    python -m cvcops package --write DIR    write the Houdini package file into DIR (install is one file)
    python -m cvcops flow ...               forward flow for each frame pair, with a receipt each
    python -m cvcops verify ...             fresh, stale or missing for each frame pair; writes nothing

Exit codes follow the manifest: 0 done, 1 failed, 3 broken environment. flow prints one line per pair on stdout,
flushed at once; reasons go to stderr (decision 0004).
"""
import argparse
import json
import os
import sys
import time
from importlib import resources

from .contract import BACKENDS, DEFAULT_TOLERANCE_PX, RECIPES, ContractError

EXIT_OK, EXIT_FAILED, EXIT_ENVIRONMENT = 0, 1, 3


class Broken(RuntimeError):
    """The environment cannot run the request: exit 3."""


class Refused(RuntimeError):
    """The request cannot run as asked, and nothing was written: exit 1."""


def load_manifest():
    return json.loads(resources.files("cvcops").joinpath("capabilities.json").read_text(encoding="utf-8"))


def _frames(text):
    first, _, last = text.partition("-")
    try:
        return int(first), int(last or first)
    except ValueError:
        raise argparse.ArgumentTypeError(f"frames must look like 1001-1100, not {text!r}")


def _tolerance(text):
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"tolerance must be a number of pixels, not {text!r}")
    if not value > 0 or value == float("inf"):
        raise argparse.ArgumentTypeError(f"tolerance must be a finite number of pixels above 0, not {text!r}")
    return value


def _err(*parts):
    print(*parts, file=sys.stderr, flush=True)


def _say(*parts):
    print(*parts, flush=True)


def _capabilities(args):
    print(json.dumps(load_manifest(), indent=2))
    return EXIT_OK


def _package(args):
    from .package import ROOT, write_package
    path = write_package(args.write, root=args.root or ROOT, worker_python=args.python)
    print(path)
    return EXIT_OK


# ---- the environment -------------------------------------------------------------------------------------------
def _import_runtime():
    try:
        import cv2  # noqa: F401
        import OpenEXR  # noqa: F401
    except Exception as e:  # noqa: BLE001 - any import failure is a broken environment
        raise Broken(f"cannot import the worker's runtime: {type(e).__name__}: {e}")


def opencl_device():
    """Name of the OpenCL device OpenCV would use, or None."""
    import cv2
    if not cv2.ocl.haveOpenCL():
        return None
    try:
        return cv2.ocl.Device.getDefault().name() or None
    except Exception:  # noqa: BLE001
        return None


def cuda_device_count():
    import cv2
    try:
        return int(cv2.cuda.getCudaEnabledDeviceCount())
    except Exception:  # noqa: BLE001 - a wheel without CUDA modules
        return 0


def select_backend(backend):
    """cpu runs with OpenCL switched off. opencl and cuda have no v0.1 recipe: refused before anything is written,
    exit 3 when the runtime is missing and exit 1 when it is there (decision 0004)."""
    import cv2
    if backend == "cpu":
        cv2.ocl.setUseOpenCL(False)
        return {"opencl_in_use": bool(cv2.ocl.useOpenCL()), "device": None}
    if backend == "cuda":
        if cuda_device_count() < 1:
            raise Broken("--backend cuda: this OpenCV build has no CUDA device; the cpu backend is not substituted")
        raise Refused("--backend cuda: no v0.1 recipe runs on CUDA; that is Mission 6's work")
    device = opencl_device()
    if device is None:
        raise Broken("--backend opencl: no usable OpenCL device; the cpu backend is not substituted")
    raise Refused(f"--backend opencl: a device is present ({device}), but no v0.1 recipe runs on OpenCL; "
                  "that is Mission 6's work")


# ---- flow ------------------------------------------------------------------------------------------------------
def _preflight(args):
    from . import receipt
    from .contract import frame_pairs
    first, last = args.frames
    pairs = frame_pairs(first, last)
    frames = [receipt.frame_path(args.analysis_pattern, f) for f in range(first, last + 2)]
    missing = [p for p in frames if not os.path.isfile(p)]
    if missing:
        raise Refused(f"analysis frames missing: {', '.join(missing)}")
    sidecar = receipt.read_analysis_sidecar(args.analysis_pattern)
    return pairs, sidecar


def _remove(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def _flow_pair(args, a, b, sidecar, backend_info, identity, cache):
    """One pair: skip it when fresh, otherwise write the flow file and then its receipt. Returns 'ok', 'skip' or
    'error'. A failure before both frames are hashed and read writes nothing; a later one writes an error receipt."""
    import cv2
    import numpy as np

    from . import contract, receipt
    from .io_exr import read_analysis_exr, write_flow_exr
    from .ops.flow import estimate_flow
    from .ops.validity import forward_backward_valid

    t_start = time.perf_counter()
    timings = dict.fromkeys(receipt.TIMING_KEYS, 0.0)
    path_a = receipt.frame_path(args.analysis_pattern, a)
    path_b = receipt.frame_path(args.analysis_pattern, b)
    flow_path, receipt_path = receipt.output_paths(args.out_dir, args.analysis_pattern, a)

    t = time.perf_counter()
    digest_a, digest_b = contract.sha256_file(path_a), contract.sha256_file(path_b)
    timings["hash"] = time.perf_counter() - t
    key = receipt.expected_cache_key([digest_a, digest_b], args.recipe, args.backend, args.tolerance, identity)
    state, _ = receipt.freshness(receipt_path, key, flow_path)
    if state == "fresh":
        _say(f"flow {a}-{b} skip fresh")
        return "skip"

    t = time.perf_counter()
    if path_a in cache:
        img_a, notes_a = cache[path_a]
    else:
        notes_a = []
        img_a = read_analysis_exr(path_a, report=notes_a)
    notes_b = []
    img_b = read_analysis_exr(path_b, report=notes_b)
    cache.clear()
    cache[path_b] = (img_b, notes_b)
    warnings = notes_a + notes_b
    timings["read"] = time.perf_counter() - t

    clipped_a, levels_a, _ = contract.analysis_stats(img_a)
    clipped_b, levels_b, _ = contract.analysis_stats(img_b)
    clipped, levels = max(clipped_a, clipped_b), min(levels_a, levels_b)
    _, _, stat_warnings = contract.analysis_stats(img_a if (clipped_a, -levels_a) >= (clipped_b, -levels_b) else img_b)
    analysis = {"clipped_share": clipped, "grey_levels": levels, "warnings": stat_warnings + warnings}
    common = dict(a=a, b=b, inputs={"a": (path_a, digest_a), "b": (path_b, digest_b)}, image=img_a.shape,
                  analysis=analysis, sidecar=sidecar, recipe=args.recipe, backend=args.backend,
                  tolerance_px=args.tolerance, cache_key=key, identity=identity, threads=cv2.getNumThreads(),
                  opencl_in_use=backend_info["opencl_in_use"], device=backend_info["device"])
    try:
        t = time.perf_counter()
        forward = estimate_flow(img_a, img_b, args.recipe)
        timings["flow"] = time.perf_counter() - t
        t = time.perf_counter()
        backward = estimate_flow(img_b, img_a, args.recipe)
        valid = forward_backward_valid(forward, backward, args.tolerance)
        timings["validity"] = time.perf_counter() - t
        rgb = np.dstack([forward[..., 0], forward[..., 1], valid.astype(np.float32)]).astype(np.float32)
        _remove(receipt_path)
        t = time.perf_counter()
        write_flow_exr(flow_path, rgb)
        out_digest = contract.sha256_file(flow_path)
        timings["write"] = time.perf_counter() - t
        timings["total"] = time.perf_counter() - t_start
        data = receipt.build_receipt(status="ok", output=(flow_path, out_digest), summary=receipt.summary(forward, valid),
                                     timings=timings, **common)
        receipt.write_receipt(receipt_path, data)
    except Exception as e:  # noqa: BLE001 - one pair failing never stops the others
        reason = f"{type(e).__name__}: {e}"
        for leftover in (flow_path, receipt_path):
            try:
                _remove(leftover)
            except OSError as e_rm:         # a File COP can hold the old file on Windows (OD-11)
                reason += f"; could not remove {os.path.basename(leftover)}: {type(e_rm).__name__}: {e_rm}"
        timings["total"] = time.perf_counter() - t_start
        try:
            receipt.write_receipt(receipt_path, receipt.build_receipt(status="error", error=reason, timings=timings,
                                                                      **common))
        except Exception as e2:  # noqa: BLE001
            reason += f"; the error receipt could not be written either: {e2}"
        _say(f"flow {a}-{b} error")
        _err(f"flow {a}-{b}: {reason}")
        return "error"
    _say(f"flow {a}-{b} ok {timings['total']:.3f}s")
    return "ok"


def _flow(args):
    from . import receipt
    try:
        _import_runtime()
        backend_info = select_backend(args.backend)
        pairs, sidecar = _preflight(args)
        identity = receipt.cv2_identity()
    except Broken as e:
        _err(f"cvcops flow: {e}")
        return EXIT_ENVIRONMENT
    except (Refused, ContractError) as e:
        _err(f"cvcops flow: {e}")
        return EXIT_FAILED
    os.makedirs(args.out_dir, exist_ok=True)
    cache, failed = {}, 0
    for a, b in pairs:
        try:
            result = _flow_pair(args, a, b, sidecar, backend_info, identity, cache)
        except Exception as e:  # noqa: BLE001 - before both frames were hashed and read: nothing written
            _say(f"flow {a}-{b} error")
            _err(f"flow {a}-{b}: {type(e).__name__}: {e}; nothing written for this pair")
            cache.clear()
            result = "error"
        failed += result == "error"
    return EXIT_FAILED if failed else EXIT_OK


# ---- verify ----------------------------------------------------------------------------------------------------
def _verify_pair(args, a, b, identity):
    from . import contract, receipt
    flow_path, receipt_path = receipt.output_paths(args.out_dir, args.analysis_pattern, a)
    recorded = {}
    try:
        with open(receipt_path, encoding="utf-8") as f:
            data = json.load(f)
        recorded = {"recipe": data["recipe"]["name"], "backend": data["backend"]["requested"],
                    "tolerance": data["validity"]["tolerance_px"]}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    recipe = args.recipe or recorded.get("recipe")
    backend = args.backend or recorded.get("backend")
    tolerance = args.tolerance if args.tolerance is not None else recorded.get("tolerance")
    key = None
    paths = [receipt.frame_path(args.analysis_pattern, f) for f in (a, b)]
    if recipe in RECIPES and backend in BACKENDS and tolerance is not None and all(os.path.isfile(p) for p in paths):
        key = receipt.expected_cache_key([contract.sha256_file(p) for p in paths], recipe, backend, tolerance, identity)
    return receipt.freshness(receipt_path, key, flow_path)


def _verify(args):
    from . import receipt
    from .contract import frame_pairs
    try:
        _import_runtime()
        identity = receipt.cv2_identity()
        first, last = args.frames
        pairs = frame_pairs(first, last)
        receipt.frame_path(args.analysis_pattern, first)
    except Broken as e:
        _err(f"cvcops verify: {e}")
        return EXIT_ENVIRONMENT
    except ContractError as e:
        _err(f"cvcops verify: {e}")
        return EXIT_FAILED
    results = [(a, b, *_verify_pair(args, a, b, identity)) for a, b in pairs]
    if args.json:
        print(json.dumps(receipt.verify_report(first, last, results), indent=2), flush=True)
    else:
        for a, b, state, reason in results:
            _say(f"{a}-{b} {state}: {reason}")
    return EXIT_OK if all(r[2] == "fresh" for r in results) else EXIT_FAILED


def build_parser():
    ap = argparse.ArgumentParser(prog="cvcops", description="OpenCV perception for Houdini 22 Copernicus (working title).")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("capabilities", help="print the capability manifest as JSON")
    p.set_defaults(run=_capabilities)

    p = sub.add_parser("package", help="write the Houdini package file")
    p.add_argument("--write", required=True, metavar="DIR", help="folder to write it into, such as $HOUDINI_USER_PREF_DIR/packages")
    p.add_argument("--root", help="repository root (default: this checkout)")
    p.add_argument("--python", help="worker interpreter the Bake button runs (default: this one)")
    p.set_defaults(run=_package)

    for name, helptext in (("flow", "forward flow for each frame pair, with receipts"), ("verify", "fresh, stale or missing per frame pair")):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("--in", dest="analysis_pattern", required=True, help="analysis frames, such as bake/analysis.####.exr")
        p.add_argument("--out", dest="out_dir", required=True, help="folder for flow files and receipts")
        p.add_argument("--frames", type=_frames, required=True, help="first and last frame A, such as 1001-1100")
        if name == "flow":
            p.add_argument("--recipe", choices=RECIPES, default="dis_medium")
            p.add_argument("--backend", choices=BACKENDS, default="cpu")
            p.add_argument("--tolerance", type=_tolerance, default=DEFAULT_TOLERANCE_PX, help="validity tolerance in pixels")
            p.set_defaults(run=_flow)
        else:
            p.add_argument("--recipe", choices=RECIPES, default=None, help="default: as each receipt recorded")
            p.add_argument("--backend", choices=BACKENDS, default=None, help="default: as each receipt recorded")
            p.add_argument("--tolerance", type=_tolerance, default=None, help="default: as each receipt recorded")
            p.add_argument("--json", action="store_true", help="print the result as JSON")
            p.set_defaults(run=_verify)
    return ap


def main(argv=None):
    try:
        args = build_parser().parse_args(argv)
    except SystemExit as e:                 # argparse exits 2 on a bad argument; the manifest promises 0, 1, 3
        return EXIT_FAILED if e.code == 2 else (e.code or EXIT_OK)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
