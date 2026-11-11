"""The bake receipt: timed bakes of the example, combined into docs/facts/m3_bake_receipt.json (cvcops.bake.v1).

    uv run python evidence/bake_receipt.py runs --n 1 --out examples/two_region/out/timing
    uv run python evidence/bake_receipt.py runs --n 4 --start 2 --out examples/two_region/out/timing
    uv run python evidence/bake_receipt.py aggregate --in examples/two_region/out/timing --write docs/facts/m3_bake_receipt.json
    uv run python evidence/bake_receipt.py --check docs/facts/m3_bake_receipt.json

Standard library only (M3.judge.bake_aggregator in docs/missions/M3_bake_asset.md; OD-07, OD-08, OD-16).

`runs` starts each timed bake as its own `probes/hython.py houdini/tests/bake_timing.py` call, in the foreground,
into a fresh empty folder <out>/run_<n>/, so each run gets a fresh hython and an empty cache, and inherits
probes/hython.py's 600 s limit and exit 3. Before and after each call it lists every hython and Houdini process
running and counts the other python processes, leaving out its own process and its launcher, and adds both to the
run's record. A run that overlapped a hython or Houdini process is refused; python processes are only counted, because
the workstation always runs dozens of idle ones (Joe, 11 Nov, narrowing the mission spec's 'python or hython'). It
stops at the first nonzero exit, and after run 1 if that run took over 300 s (OD-16: ask Joe about shrinking the
example).

`aggregate` reads every <in>/run_<n>/run.json, refuses anything that would make the medians untrustworthy, and writes
the receipt through a temporary name and os.replace. `--check` re-derives the medians and the quarter ratio from the
receipt's own runs and prints them.

The run record, <out>/run_<n>/run.json, schema cvcops.bake_run.v1. houdini/tests/bake_timing.py writes every key
except "exit", "snapshots" and "python_seen", which `runs` adds after the call returns. Paths are relative to the repository:

    {"schema": "cvcops.bake_run.v1", "run": 1,
     "workload": {"source": "examples/two_region/out/frames/two_region.$F4.exr", "size": [1920, 1080],
                  "frames": [1001, 1024], "pairs": 24, "analysis_scale": "1.0", "recipe": "dis_medium",
                  "backend": "cpu", "threads": 48, "cv2_version": "5.0.0", "cv2_build_sha256": "<hex>",
                  "houdini_build": "22.0.492", "licence": "<category>", "build_stamp": "<hex>", "git_head": "<hex>"},
     "wall_s": {"export": 1.2, "worker": 11.0, "load": 2.0, "total": 14.5},
     "pairs": [{"a": 1001, "b": 1002, "state": "computed",
                "timings_s": {"read": 0.03, "hash": 0.01, "flow": 0.08, "validity": 0.14, "write": 0.18, "total": 0.45}}],
     "exit": 0,
     "snapshots": {"before": [{"image": "hython.exe", "pid": 123}], "after": []},
     "python_seen": {"before": 40, "after": 40}}

wall_s is measured in hython: export (ROP Image), worker (the flow process), load (the File COP reload and a cook of
the flow output at every frame of the range), and total, from export start to the last of those cooks (OD-07). A pair
whose state is not "computed" was skipped as fresh, which a timed run must never do.

Phases per run (OD-07): flow_compute = sum of flow + validity; worker_io = sum of read + hash + write;
worker_other = worker wall minus both; other = total minus export, worker and load. The quarter ratio is the median
flow_compute over the median total, not a median of per-run ratios.

Exit codes: 0 done, 1 refused or a run failed, 2 bad arguments, 3 a broken environment (no tasklist, no hython).
"""
import argparse
import csv
import io
import json
import os
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "cvcops.bake.v1"
RUN_SCHEMA = "cvcops.bake_run.v1"
MIN_RUNS = 5
QUARTER = 0.25
RUN1_LIMIT_S = 300.0
EPS_S = 1e-3

WORKLOAD_KEYS = ("source", "size", "frames", "pairs", "analysis_scale", "recipe", "backend", "threads", "cv2_version",
                 "cv2_build_sha256", "houdini_build", "licence", "build_stamp", "git_head")
WALL_KEYS = ("export", "worker", "load", "total")
PAIR_TIMING_KEYS = ("read", "hash", "flow", "validity", "write", "total")
PHASE_KEYS = ("total", "export", "flow_compute", "worker_io", "worker_other", "load", "other")
HOUDINI_IMAGES = frozenset({"hython.exe", "hython", "houdini.exe", "houdinifx.exe", "houdinicore.exe", "hindie.exe",
                            "happrentice.exe", "hescape.exe"})
PYTHON_IMAGES = frozenset({"python.exe", "pythonw.exe", "python", "python3"})
_ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/])")

EXIT_OK, EXIT_FAILED, EXIT_ENVIRONMENT = 0, 1, 3


class Refused(ValueError):
    """The runs cannot make a trustworthy receipt; the message lists every reason."""


class BrokenEnvironment(RuntimeError):
    """The process list cannot be read: exit code 3."""


# ---- snapshots ---------------------------------------------------------------------------------------------------
def parse_tasklist(text, exclude=()):
    """From `tasklist /FO CSV /NH` output, leaving out the PIDs in exclude: the hython and Houdini processes, and
    how many python processes there are. Returns {"houdini": [{"image", "pid"}], "python": count}."""
    houdini, python = [], 0
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2:
            continue
        image = row[0].strip()
        try:
            pid = int(row[1])
        except ValueError:
            continue
        if pid in exclude:
            continue
        if image.lower() in HOUDINI_IMAGES:
            houdini.append({"image": image, "pid": pid})
        elif image.lower() in PYTHON_IMAGES:
            python += 1
    return {"houdini": sorted(houdini, key=lambda p: (p["image"].lower(), p["pid"])), "python": python}


def snapshot():
    """The hython and Houdini processes now running and the count of python processes, leaving out this one and
    its launcher (a Windows venv python.exe starts the real interpreter as its child)."""
    try:
        out = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        raise BrokenEnvironment(f"tasklist could not run: {e}") from e
    if out.returncode != 0:
        raise BrokenEnvironment(f"tasklist exited {out.returncode}: {out.stderr.strip()}")
    return parse_tasklist(out.stdout, exclude={os.getpid(), os.getppid()})


# ---- one run's numbers -------------------------------------------------------------------------------------------
def phases(record):
    """The seven phases of one run, in seconds (OD-07)."""
    wall = record["wall_s"]
    sums = {k: sum(float(p["timings_s"][k]) for p in record["pairs"]) for k in ("read", "hash", "flow", "validity", "write")}
    flow_compute = sums["flow"] + sums["validity"]
    worker_io = sums["read"] + sums["hash"] + sums["write"]
    return {"total": float(wall["total"]), "export": float(wall["export"]), "flow_compute": flow_compute,
            "worker_io": worker_io, "worker_other": float(wall["worker"]) - flow_compute - worker_io,
            "load": float(wall["load"]),
            "other": float(wall["total"]) - float(wall["export"]) - float(wall["worker"]) - float(wall["load"])}


def run_problems(record):
    """Every reason one run record cannot be used, as sentences naming the run."""
    name = f"run {record.get('run', '?')}"
    if record.get("schema") != RUN_SCHEMA:
        return [f"{name}: schema is {record.get('schema')!r}, not {RUN_SCHEMA}"]
    problems = []
    workload = record.get("workload")
    if not isinstance(workload, dict) or set(workload) != set(WORKLOAD_KEYS):
        return [f"{name}: workload must have exactly the keys {', '.join(WORKLOAD_KEYS)}"]
    frames, size, count = workload["frames"], workload["size"], workload["pairs"]
    if not (_ints(frames, 2) and frames[0] <= frames[1] and _ints(size, 2) and isinstance(count, int)
            and not isinstance(count, bool)):
        return [f"{name}: workload frames and size must be two whole numbers each (first <= last), pairs a whole number"]
    wall = record.get("wall_s")
    if not isinstance(wall, dict) or set(wall) != set(WALL_KEYS):
        return [f"{name}: wall_s must have exactly the keys {', '.join(WALL_KEYS)}"]
    if record.get("exit") != 0:
        problems.append(f"{name}: bake_timing.py exited {record.get('exit')!r}")
    snaps, seen = record.get("snapshots"), record.get("python_seen")
    if (not isinstance(snaps, dict) or not isinstance(snaps.get("before"), list) or not isinstance(snaps.get("after"), list)
            or not isinstance(seen, dict) or not all(_count(seen.get(w)) for w in ("before", "after"))):
        problems.append(f"{name}: no before and after process snapshots (start it with `runs`)")
    else:
        for when in ("before", "after"):
            if snaps[when]:
                listed = ", ".join(f"{p.get('image')} {p.get('pid')}" for p in snaps[when])
                problems.append(f"{name}: overlapped a hython or Houdini process {when} the run: {listed}")
    for key in WALL_KEYS:
        value = wall[key]
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
            problems.append(f"{name}: wall_s.{key} is {value!r}, not a non-negative number")
    if not problems and wall["total"] <= 0:
        problems.append(f"{name}: wall_s.total is {wall['total']!r}; a bake takes time")
    pairs = record.get("pairs")
    first, last = workload["frames"]
    expected = list(range(first, last + 1))
    if (not isinstance(pairs, list) or not all(isinstance(p, dict) for p in pairs)
            or [p.get("a") for p in pairs] != expected or any(p.get("b") != p.get("a") + 1 for p in pairs)):
        problems.append(f"{name}: pairs must be {first}-{first + 1} through {last}-{last + 1}, one each, in order")
        return problems
    if len(pairs) != workload["pairs"]:
        problems.append(f"{name}: {len(pairs)} pairs, but the workload says {workload['pairs']}")
    for p in pairs:
        if p.get("state") != "computed":
            problems.append(f"{name}: pair {p['a']}-{p['b']} was {p.get('state')!r}, not computed (a skipped fresh pair)")
        timings = p.get("timings_s")
        if not isinstance(timings, dict) or set(timings) != set(PAIR_TIMING_KEYS):
            problems.append(f"{name}: pair {p['a']}-{p['b']} timings_s must have exactly {', '.join(PAIR_TIMING_KEYS)}")
            continue
        for key, value in timings.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                problems.append(f"{name}: pair {p['a']}-{p['b']} timings_s.{key} is {value!r}, not a non-negative number")
    if problems:
        return problems
    ph = phases(record)
    if ph["other"] < -EPS_S:
        problems.append(f"{name}: export + worker + load ({ph['total'] - ph['other']:.3f} s) is past total ({ph['total']:.3f} s)")
    if ph["worker_other"] < -EPS_S:
        problems.append(f"{name}: the worker's own timings ({ph['flow_compute'] + ph['worker_io']:.3f} s) are past its wall time "
                        f"({float(wall['worker']):.3f} s)")
    return problems


def _count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _ints(value, n):
    return (isinstance(value, list) and len(value) == n
            and all(isinstance(v, int) and not isinstance(v, bool) for v in value))


def _absolute_paths(value, where=""):
    if isinstance(value, str):
        return [where] if _ABSOLUTE.match(value) else []
    if isinstance(value, dict):
        return [hit for k, v in value.items() for hit in _absolute_paths(v, f"{where}.{k}" if where else k)]
    if isinstance(value, list):
        return [hit for i, v in enumerate(value) for hit in _absolute_paths(v, f"{where}[{i}]")]
    return []


def _kept(record):
    """Only the fields a receipt keeps from a run record (the receipt is committed to a public repository)."""
    return {"run": record["run"], "exit": record["exit"],
            "wall_s": {k: record["wall_s"][k] for k in WALL_KEYS},
            "pairs": [{"a": p["a"], "b": p["b"], "state": p["state"],
                       "timings_s": {k: p["timings_s"][k] for k in PAIR_TIMING_KEYS}} for p in record["pairs"]],
            "snapshots": {w: [{"image": s["image"], "pid": s["pid"]} for s in record["snapshots"][w]]
                          for w in ("before", "after")},
            "python_seen": {w: record["python_seen"][w] for w in ("before", "after")}}


# ---- the receipt -------------------------------------------------------------------------------------------------
def build_receipt(records):
    """The cvcops.bake.v1 receipt from run records; raises Refused listing every reason it cannot."""
    records = sorted(records, key=lambda r: (r.get("run") is None, r.get("run")))
    problems = []
    if len(records) < MIN_RUNS:
        problems.append(f"{len(records)} runs; the receipt needs at least {MIN_RUNS}")
    numbers = [r.get("run") for r in records]
    if len(set(numbers)) != len(numbers):
        problems.append(f"run numbers repeat: {numbers}")
    for r in records:
        problems.extend(run_problems(r))
    good = [r for r in records if isinstance(r.get("workload"), dict) and set(r["workload"]) == set(WORKLOAD_KEYS)]
    if good:
        base = good[0]
        for r in good[1:]:
            for key in WORKLOAD_KEYS:
                if r["workload"][key] != base["workload"][key]:
                    problems.append(f"run {r.get('run')}: workload {key} is {r['workload'][key]!r}, "
                                    f"but run {base.get('run')} has {base['workload'][key]!r}")
    if problems:
        raise Refused("\n".join(problems))
    per_run = [phases(r) for r in records]
    medians = {k: statistics.median(p[k] for p in per_run) for k in PHASE_KEYS}
    ratio = medians["flow_compute"] / medians["total"]
    receipt = {"schema": SCHEMA, "n": len(records), "workload": dict(records[0]["workload"]),
               "runs": [_kept(r) for r in records], "medians_s": medians,
               "quarter": {"ratio": ratio, "at_least_a_quarter": ratio >= QUARTER, "threshold": QUARTER}}
    absolute = _absolute_paths(receipt)
    if absolute:
        raise Refused("absolute paths would be committed: " + ", ".join(absolute))
    return receipt


def read_runs(in_dir):
    in_dir = Path(in_dir)
    paths = sorted(in_dir.glob("run_*/run.json"))
    records = []
    for p in paths:
        try:
            records.append(json.loads(p.read_text(encoding="utf-8")))
        except (OSError, ValueError) as e:
            raise Refused(f"{p.as_posix()}: unreadable run record: {e}") from e
    return records


def write_json(path, obj):
    """Write obj through a dot-named temporary file in the same folder, then os.replace it into place, so an
    interrupted write leaves the previous file whole."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".cvcops-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def check_receipt(receipt):
    """Re-derive the receipt from its own runs. Returns the re-derived receipt; raises Refused on any mismatch."""
    if not isinstance(receipt, dict):
        raise Refused("not a JSON object")
    if "node" in receipt or "settings" in receipt:
        raise Refused("this is one bake's record ($cache/bake.json), not the bake receipt")
    if receipt.get("schema") != SCHEMA:
        raise Refused(f"schema is {receipt.get('schema')!r}, not {SCHEMA}")
    for key in ("n", "workload", "runs", "medians_s", "quarter"):
        if key not in receipt:
            raise Refused(f"no {key!r}")
    records = [{"schema": RUN_SCHEMA, "workload": receipt["workload"], **r} for r in receipt["runs"]]
    rebuilt = build_receipt(records)
    for key in ("n", "medians_s", "quarter", "runs", "workload"):
        if rebuilt[key] != receipt[key]:
            raise Refused(f"{key} does not match what its runs give: {receipt[key]!r} against {rebuilt[key]!r}")
    return rebuilt


def summary(receipt):
    m, q = receipt["medians_s"], receipt["quarter"]
    lines = [f"cvcops.bake.v1: n = {receipt['n']}, {receipt['workload']['pairs']} pairs at "
             f"{receipt['workload']['size'][0]}x{receipt['workload']['size'][1]}, {receipt['workload']['recipe']} on "
             f"{receipt['workload']['backend']}, analysis scale {receipt['workload']['analysis_scale']}",
             "medians (s): " + ", ".join(f"{k} {m[k]:.3f}" for k in PHASE_KEYS),
             f"quarter: median flow_compute / median total = {q['ratio']:.4f}; "
             + ("at least a quarter" if q["at_least_a_quarter"] else "less than a quarter")]
    return "\n".join(lines)


# ---- running the timed bakes -------------------------------------------------------------------------------------
def launch_bake_timing(run, out, extra):
    """One timed bake in a fresh hython, the judge's way. Returns its exit code."""
    argv = [sys.executable, "probes/hython.py", "houdini/tests/bake_timing.py", "--run", str(run), "--out", out, *extra]
    return subprocess.run(argv, cwd=ROOT).returncode


def run_timed(n, out, start=1, extra=(), launch=launch_bake_timing, take_snapshot=snapshot, echo=print):
    """Run n timed bakes, numbered from start, one at a time. Returns the exit code of the whole batch."""
    out = Path(out)
    for run in range(start, start + n):
        folder = out / f"run_{run}"
        if folder.exists() and any(folder.iterdir()):
            echo(f"run {run}: {folder.as_posix()} is not empty; each timed run needs a fresh empty folder")
            return EXIT_FAILED
        folder.mkdir(parents=True, exist_ok=True)
        before = take_snapshot()
        code = launch(run, folder.as_posix(), list(extra))
        after = take_snapshot()
        if code != 0:
            echo(f"run {run}: bake_timing.py exited {code}; stopping")
            return code
        record_path = folder / "run.json"
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            echo(f"run {run}: no readable run.json after exit 0: {e}")
            return EXIT_FAILED
        if record.get("schema") != RUN_SCHEMA or record.get("run") != run:
            echo(f"run {run}: run.json is not a {RUN_SCHEMA} record for run {run}")
            return EXIT_FAILED
        record["exit"] = code
        record["snapshots"] = {"before": before["houdini"], "after": after["houdini"]}
        record["python_seen"] = {"before": before["python"], "after": after["python"]}
        write_json(record_path, record)
        total = float(record.get("wall_s", {}).get("total", float("nan")))
        overlap = len(before["houdini"]) + len(after["houdini"])
        echo(f"run {run}: exit 0, total {total:.2f} s, python processes {before['python']} before and "
             f"{after['python']} after" + (f", {overlap} hython or Houdini processes seen" if overlap else ""))
        if run == 1 and total > RUN1_LIMIT_S:
            echo(f"run 1 took {total:.0f} s, over {RUN1_LIMIT_S:.0f} s: ask Joe about shrinking the example (OD-16)")
            return EXIT_FAILED
    return EXIT_OK


# ---- command line ------------------------------------------------------------------------------------------------
def build_parser():
    ap = argparse.ArgumentParser(prog="bake_receipt.py", description="Timed bakes and the bake receipt (cvcops.bake.v1).")
    ap.add_argument("--check", metavar="PATH", help="validate a receipt and print its medians and quarter ratio")
    sub = ap.add_subparsers(dest="command")
    r = sub.add_parser("runs", help="run timed bakes, one fresh hython each, into <out>/run_<n>/")
    r.add_argument("--n", type=int, required=True)
    r.add_argument("--start", type=int, default=1)
    r.add_argument("--out", required=True)
    r.add_argument("extra", nargs=argparse.REMAINDER, help="after --, options passed on to bake_timing.py")
    a = sub.add_parser("aggregate", help="combine <in>/run_*/run.json into the receipt")
    a.add_argument("--in", dest="in_dir", required=True)
    a.add_argument("--write", required=True)
    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    if bool(args.check) == bool(args.command):
        ap.error("give either --check PATH or one command (runs, aggregate)")
    try:
        if args.check:
            receipt = check_receipt(json.loads(Path(args.check).read_text(encoding="utf-8")))
            print(summary(receipt))
            return EXIT_OK
        if args.command == "aggregate":
            receipt = build_receipt(read_runs(args.in_dir))
            write_json(args.write, receipt)
            print(summary(receipt))
            print(f"wrote {args.write}")
            return EXIT_OK
        extra = args.extra[1:] if args.extra[:1] == ["--"] else args.extra
        if args.n < 1 or args.start < 1:
            ap.error("--n and --start must be at least 1")
        return run_timed(args.n, args.out, start=args.start, extra=extra, launch=launch_bake_timing,
                         take_snapshot=snapshot)
    except Refused as e:
        print(f"refused:\n{e}", file=sys.stderr)
        return EXIT_FAILED
    except BrokenEnvironment as e:
        print(f"broken environment: {e}", file=sys.stderr)
        return EXIT_ENVIRONMENT
    except (OSError, ValueError) as e:
        print(f"failed: {e}", file=sys.stderr)
        return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
