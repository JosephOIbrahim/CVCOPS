"""The Bake and Check Cache buttons of cvcops::flow::1.0. Runs inside Houdini; never imports cv2.

bake(node) is the one function the button, houdini/tests/bake_once.py and every example call:

1. Export analysis frames f1 to f2 + 1 through the asset's ROP Image into <cache>/.export/ (raw, float32).
2. Move each into <cache>/analysis.####.exr with os.replace, unless the frame already there has bit-identical
   pixels: ROP Image stamps the date into every header, so a re-export of the same pixels gets new bytes, and the
   worker's cache key hashes bytes (Joe, 11 Nov, OD-13). Keeping the old file keeps fresh pairs fresh.
3. Write the analysis sidecar with the prep values and hou.fps() (decision 0004).
4. Run the worker once for the whole range, polled inside hou.InterruptableOperation so Esc cancels it.
5. Reload the File COP only after the worker has exited (OD-11), time one cook of the outputs, and write
   <cache>/bake.json last.
"""
import json
import os
import tempfile
import time

from . import sidecar, worker


class BakeError(RuntimeError):
    def __init__(self, message, code=worker.EXIT_FAILED):
        super().__init__(message)
        self.code = code


def _hou():
    import hou
    return hou


def _pixels(path):
    import OpenEXR
    with OpenEXR.File(path, separate_channels=True) as f:
        return {name: ch.pixels.tobytes() for name, ch in f.channels().items()}


def _same_pixels(a, b):
    try:
        return _pixels(a) == _pixels(b)
    except Exception:  # noqa: BLE001 - an unreadable old frame is replaced
        return False


def settings(node):
    """The control values a bake uses, evaluated once."""
    f1, f2 = (int(v) for v in node.parmTuple("frange").eval())
    return {"first": f1, "last": f2, "cache": node.parm("cache_dir").evalAsString(),
            "recipe": node.parm("recipe").evalAsString(), "backend": node.parm("backend").evalAsString(),
            "tolerance": node.parm("tolerance").eval(), "luma_weights": list(node.parmTuple("luma_weights").eval()),
            "gain": node.parm("gain").eval(), "gamma": node.parm("gamma").eval(),
            "analysis_scale": node.parm("analysis_scale").evalAsString()}


def _place_frames(cache, first, last):
    staged = os.path.join(cache, ".export")
    kept = replaced = 0
    for frame in range(first, last + 2):
        name = f"analysis.{frame:04d}.exr"
        src, dst = os.path.join(staged, name), os.path.join(cache, name)
        if not os.path.isfile(src):
            raise BakeError(f"the export wrote no {name}; does the source have frame {frame}?")
        if os.path.isfile(dst) and _same_pixels(src, dst):
            os.remove(src)
            kept += 1
        else:
            os.replace(src, dst)
            replaced += 1
    return kept, replaced


def _write_record(cache, record):
    fd, tmp = tempfile.mkstemp(prefix=".cvcops-", suffix=".json.tmp", dir=cache)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(record, f, indent=1)
            f.write("\n")
        os.replace(tmp, os.path.join(cache, "bake.json"))
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise


def bake(node, env_prefix="CVCOPS"):
    """Export, run the worker, load. Returns the phase timings in seconds; raises BakeError with the exit code."""
    hou = _hou()
    s = settings(node)
    python = worker.worker_python(env_prefix)
    if s["last"] < s["first"]:
        raise BakeError(f"Frame Range {s['first']}-{s['last']} is empty")
    cache = s["cache"]
    os.makedirs(os.path.join(cache, ".export"), exist_ok=True)
    t_start = time.perf_counter()

    export = node.node("export")
    export.parm("execute").pressButton()
    if export.errors():
        raise BakeError("the analysis export failed:\n" + "\n".join(export.errors()))
    kept, replaced = _place_frames(cache, s["first"], s["last"])
    sidecar.write(cache, sidecar.fragment(s["luma_weights"], s["gain"], s["gamma"], s["analysis_scale"], hou.fps()))
    t_export = time.perf_counter()

    argv = worker.flow_argv(python, os.path.join(cache, "analysis.####.exr"), cache, s["first"], s["last"],
                            s["recipe"], s["backend"], s["tolerance"])
    pairs = s["last"] - s["first"] + 1
    done = [0]
    with hou.InterruptableOperation("CVCOPs flow", long_operation_name=f"Flow for {pairs} frame pairs",
                                    open_interrupt_dialog=True) as op:
        def tick(line):
            if line is not None and line.startswith("flow "):
                done[0] += 1
            op.updateLongProgress(min(done[0] / pairs, 1.0), line or "")
        code, lines, tail = worker.run_worker(argv, worker.scrubbed_env(), cache, tick=tick)
    t_worker = time.perf_counter()
    if code != worker.EXIT_OK:
        raise BakeError(worker.describe_exit(code, tail), code)

    node.node("load").parm("reload").pressButton()
    node.node("convert").cook(force=True)
    t_load = time.perf_counter()
    record = {"schema": "cvcops.bake.v1", "node": node.path(), "frames": [s["first"], s["last"]],
              "settings": s, "worker_argv": argv, "worker_exit": code, "progress": lines,
              "analysis_frames": {"kept": kept, "replaced": replaced},
              "timings_s": {"export": t_export - t_start, "worker": t_worker - t_export, "load": t_load - t_worker,
                            "total": t_load - t_start}}
    _write_record(cache, record)
    return record["timings_s"]


def check_cache(node, env_prefix="CVCOPS"):
    """Ask the worker which pairs are fresh, stale or missing, and show it in the Status folder."""
    hou = _hou()
    s = settings(node)
    python = worker.worker_python(env_prefix)
    argv = worker.verify_argv(python, os.path.join(s["cache"], "analysis.####.exr"), s["cache"], s["first"], s["last"],
                              s["recipe"], s["backend"], s["tolerance"])
    code, lines, tail = worker.run_worker(argv, worker.scrubbed_env(), s["cache"] if os.path.isdir(s["cache"]) else None)
    if code == worker.EXIT_ENVIRONMENT or code not in (0, 1):
        raise BakeError(worker.describe_exit(code, tail), code)
    report = json.loads("\n".join(lines))
    c = report["counts"]
    node.setUserData("cvcops_state", f"{c['fresh']} fresh, {c['stale']} stale, {c['missing']} missing")
    same = sidecar.matches(s["cache"], sidecar.fragment(s["luma_weights"], s["gain"], s["gamma"],
                                                        s["analysis_scale"], hou.fps()))
    if not same:
        node.setUserData("cvcops_encoding", "analysis settings differ from the last bake")
    newest = os.path.join(s["cache"], f"flow.{s['last']:04d}.json")
    try:
        with open(newest, encoding="utf-8") as f:
            r = json.load(f)
        node.setUserData("cvcops_ran", f"{r['recipe']['name']} on {r['backend']['ran']}, OpenCV {r['cv2']['version']}")
        if same:
            a = r["analysis"]
            node.setUserData("cvcops_encoding", f"{a['clipped_share']:.1%} clipped, {a['grey_levels']} grey levels")
    except (OSError, ValueError, KeyError):
        pass
    return report


def _report(fn, node, env_prefix):
    hou = _hou()
    try:
        return fn(node, env_prefix)
    except (BakeError, worker.WorkerEnvironmentError) as e:
        if hou.isUIAvailable():
            hou.ui.displayMessage(str(e), severity=hou.severityType.Error, title="CVCOPs")
            return None
        raise


def on_bake(node, env_prefix="CVCOPS"):
    return _report(bake, node, env_prefix)


def on_check_cache(node, env_prefix="CVCOPS"):
    return _report(check_cache, node, env_prefix)
