"""The judge's front door. Every mission closes on one of these commands.

    uv run python tools/check.py             rung 1: the guards, your unit tests, the threshold rows of the missions in
                                             tests/thresholds/mission.txt, the judge lock and the pause line
    uv run python tools/check.py --hook      the same for the Stop hook, which checks the pause line itself
    uv run python tools/check.py --houdini   rung 2: the M3 and M4 rows through hython, and Houdini's site-packages
    uv run python tools/check.py --gpu       rung 3: tests/gpu, run by the CUDA interpreter named in local.toml
    uv run python tools/check.py --selftest  the judge's own exam: the reference passes every row, each planted fault fails one
    uv run python tools/check.py --list      every row beside its test

Exit codes: 0 pass; 1 a check failed; 2 usage; 3 broken environment (a missing package, no hython, no licence, no
device, a record a probe has not written yet, or a time limit). Failures go to stderr. A check that cannot run is
a failure, never a pass. Locked: it imports tools/lock_judge.py and fails while the judge differs from judge.lock.
"""
import argparse
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OK, FAILED, ENVIRONMENT = 0, 1, 3
RUNG1_LIMIT_S = 120
HOUDINI_LIMIT_S = 3600
GPU_LIMIT_S = 3600
SELFTEST_RUN_LIMIT_S = 600
REQUIRED = ("numpy", "cv2", "OpenEXR", "pytest", "jsonschema")
THRESHOLDS = "tests/thresholds/test_thresholds.py"
GUARDS = "tests/thresholds/test_guards.py"
P1_RECORD = ROOT / "docs" / "facts" / "p1_site_packages.json"


class Broken(Exception):
    """A broken environment: exit 3."""


def err(msg):
    print(msg, file=sys.stderr)


def preflight():
    missing = []
    for name in REQUIRED:
        try:
            importlib.import_module(name)
        except Exception as e:                                # an import can fail in more ways than ImportError
            missing.append(f"{name} ({type(e).__name__}: {e})")
    if missing:
        raise Broken("the worker environment is missing: " + "; ".join(missing) + ". Run `uv sync`.")


def judge():
    sys.path.insert(0, str(ROOT / "tools"))
    sys.path.insert(0, str(ROOT / "tests" / "thresholds"))
    import impls
    import lock_judge
    return lock_judge, impls


def pause_line():
    state = ROOT / "docs" / "STATE.md"
    if not state.is_file():
        return "docs/STATE.md is missing"
    first = state.read_text(encoding="utf-8").splitlines()[:1]
    if first and re.match(r"^(WAITING|BLOCKED):", first[0]):
        return first[0]
    return None


def run_pytest(targets, env_extra, timeout, extra=(), python=None):
    fd, results_path = tempfile.mkstemp(prefix="cvcops_results_", suffix=".json")
    os.close(fd)
    env = {**os.environ, **env_extra, "CVCOPS_RESULTS": results_path}
    cmd = [python or sys.executable, "-m", "pytest", "-q", "-rN", "--rootdir", str(ROOT), *extra, *targets]
    try:
        p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Broken(f"the tests ran past their {timeout} s limit")
    try:
        with open(results_path, encoding="utf-8") as f:
            results = json.load(f) if os.path.getsize(results_path) else {}
    finally:
        os.unlink(results_path)
    return p.returncode, results, (p.stdout + p.stderr)


def row_key(nodeid):
    m = re.search(r"test_row\[(\w+)\]", nodeid)
    return m.group(1) if m else None


def judge_results(rc, results, output, expected_rows):
    """Problems from one pytest run. Raises Broken when a test reported a broken environment."""
    env = [f"{k}: {v.get('message', '')}" for k, v in results.items() if v["outcome"] == "environment"]
    if env:
        raise Broken("a test reported a broken environment:\n  " + "\n  ".join(env))
    problems = []
    by_row = {row_key(k): v for k, v in results.items() if row_key(k)}
    for row in expected_rows:
        r = by_row.get(row["key"])
        if r is None:
            problems.append(f"{row['mission']} no test ran for the row: {row['label']}")
        elif r["outcome"] != "passed":
            problems.append(f"{row['mission']} FAIL {row['label']} (threshold {row['threshold']}): {r.get('message', r['outcome'])}")
    for nodeid, r in results.items():
        if not row_key(nodeid) and r["outcome"] == "failed":
            problems.append(f"FAIL {nodeid}: {r.get('message', '')}")
    if rc not in (0, 1, 5) or (rc == 1 and not problems):
        problems.append(f"pytest exited {rc}:\n" + "\n".join(output.strip().splitlines()[-25:]))
    return problems


def lock_problems(lock_judge):
    return [f"judge: {p}" for p in lock_judge.verify(ROOT)]


def finish(problems, passed_note):
    if problems:
        for p in problems:
            err(p)
        print(f"CHECK: {len(problems)} problem(s)")
        return FAILED
    print("CHECK: " + passed_note)
    return OK


# ---- the modes -----------------------------------------------------------------------------------------------------
def rung1(hook):
    problems = []
    if not hook:
        line = pause_line()
        if line:
            problems.append(f"docs/STATE.md starts with a pause line, so the mission is not done: {line}")
    preflight()
    lock_judge, impls = judge()
    try:
        listed = impls.missions()
    except ValueError as e:
        listed = []
        problems.append(str(e))
    problems += lock_problems(lock_judge)
    rows = impls.rows_for(listed, 1)
    targets = [GUARDS, THRESHOLDS] + (["tests/unit"] if (ROOT / "tests" / "unit").is_dir() else [])
    rc, results, out = run_pytest(targets, {"CVCOPS_IMPL": "product", "CVCOPS_ROWS": ",".join(r["key"] for r in rows)}, RUNG1_LIMIT_S)
    problems += judge_results(rc, results, out, rows)
    return finish(problems, f"rung 1 passes for {', '.join(listed) or 'no mission'} ({len(rows)} threshold rows)")


def houdini():
    preflight()
    lock_judge, impls = judge()
    listed = impls.missions()
    problems = lock_problems(lock_judge)
    hython = impls.local_config().get("hython")
    if not hython or not Path(hython).is_file():
        raise Broken("no hython: put its path in local.toml (probe P1)")
    if not P1_RECORD.is_file():
        raise Broken(f"probe P1 has not recorded Houdini's site-packages in {P1_RECORD.relative_to(ROOT)}")
    try:
        p = subprocess.run([hython, str(ROOT / "probes" / "p1_environment.py"), "--site-packages"], env=impls.hython_env(),
                           capture_output=True, text=True, timeout=impls.HYTHON_LIMIT_S)
    except subprocess.TimeoutExpired:
        raise Broken(f"hython ran past {impls.HYTHON_LIMIT_S} s listing site-packages")
    if p.returncode != 0:
        raise Broken("hython could not list its site-packages:\n" + "\n".join(p.stderr.strip().splitlines()[-15:]))
    now, before = json.loads(p.stdout), json.loads(P1_RECORD.read_text(encoding="utf-8"))
    for name in sorted(set(now) | set(before)):
        if now.get(name) != before.get(name):
            problems.append(f"Houdini's Python changed since P1: {name} {before.get(name)} -> {now.get(name)}")
    rows = impls.rows_for(listed, 2)
    if rows:
        rc, results, out = run_pytest([THRESHOLDS], {"CVCOPS_IMPL": "houdini", "CVCOPS_ROWS": ",".join(r["key"] for r in rows)}, HOUDINI_LIMIT_S)
        problems += judge_results(rc, results, out, rows)
    return finish(problems, f"rung 2 passes ({len(rows)} threshold rows; Houdini's Python unchanged since P1)")


def gpu():
    preflight()
    lock_judge, impls = judge()
    listed = impls.missions()
    problems = lock_problems(lock_judge)
    if "M6" not in listed:
        return finish(problems + ["nothing to check: M6 is not in tests/thresholds/mission.txt"], "")
    cuda_python = impls.local_config().get("cuda_python")
    if not cuda_python or not Path(cuda_python).is_file():
        raise Broken("no CUDA interpreter: put cuda_python in local.toml (docs/missions/M6_cuda_build.md, step 5)")
    if not (ROOT / "tests" / "gpu").is_dir():
        return finish(problems + ["M6 is listed and tests/gpu does not exist"], "")
    rc, results, out = run_pytest(["tests/gpu"], {}, GPU_LIMIT_S, python=cuda_python)
    if rc != 0:
        problems.append(f"tests/gpu exited {rc}:\n" + "\n".join(out.strip().splitlines()[-25:]))
    return finish(problems, "rung 3 passes")


def selftest():
    preflight()
    _, impls = judge()
    ref = impls.ref
    t0 = time.time()
    print("The reference must pass every row:")
    rc, results, out = run_pytest([THRESHOLDS], {"CVCOPS_IMPL": "reference", "CVCOPS_ROWS": "all"}, SELFTEST_RUN_LIMIT_S)
    problems = judge_results(rc, results, out, impls.ROWS)
    by_row = {row_key(k): v for k, v in results.items() if row_key(k)}
    for row in impls.ROWS:
        r = by_row.get(row["key"], {})
        v = r.get("value")
        shown = "-" if v is None else (str(v) if isinstance(v, bool) else f"{v:.4f}")
        print(f"  {'PASS' if r.get('outcome') == 'passed' else 'FAIL':<5} {row['mission']}  rung {impls.RUNG[row['mission']]}  {row['label'][:70]:<70}  {shown}")
    print("Each planted fault must fail at least one row:")
    for i, fault in enumerate(ref.FAULTS):
        rc, results, out = run_pytest([THRESHOLDS], {"CVCOPS_IMPL": f"fault:{i}", "CVCOPS_ROWS": "all"}, SELFTEST_RUN_LIMIT_S, extra=["-x"])
        failed = [row_key(k) for k, v in results.items() if row_key(k) and v["outcome"] == "failed"]
        if any(v["outcome"] == "environment" for v in results.values()):
            raise Broken(f"the fault run '{fault.name}' hit a broken environment")
        print(f"  {'caught' if failed else 'MISSED':<7} {fault.name:<40} {', '.join(failed)}")
        if not failed:
            problems.append(f"the planted fault '{fault.name}' passed every row: the judge is not ready to lock")
    print(f"  ({time.time() - t0:.0f} s)")
    print("Not proven here: the product and Houdini adapters in tests/thresholds/impls.py run for real only when M1 and M3 do.")
    return finish(problems, "the reference passes every row and every planted fault is caught")


def listing():
    preflight()
    _, impls = judge()
    listed = impls.missions()
    for row in impls.ROWS:
        mark = "listed" if row["mission"] in listed else "      "
        print(f"{mark}  {row['mission']}  rung {impls.RUNG[row['mission']]}  {THRESHOLDS}::test_row[{row['key']}]")
        print(f"              {row['label']}  |  {row['threshold']}")
    return OK


def main(argv=None):
    ap = argparse.ArgumentParser(description="The judge's front door.")
    mode = ap.add_mutually_exclusive_group()
    for flag in ("--hook", "--houdini", "--gpu", "--selftest", "--list"):
        mode.add_argument(flag, action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.selftest:
            return selftest()
        if a.list:
            return listing()
        if a.houdini:
            return houdini()
        if a.gpu:
            return gpu()
        return rung1(hook=a.hook)
    except Broken as e:
        err(f"BROKEN ENVIRONMENT: {e}")
        err("Write BLOCKED: and this reason on the first line of docs/STATE.md, and edit no code to get around it.")
        return ENVIRONMENT


if __name__ == "__main__":
    sys.exit(main())
