"""Mission 3: the Bake button's hou-free glue (worker.py, sidecar.py), tested at rung 1 with stand-in workers."""
import json
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "houdini" / "python3.13libs"))

from cvcops_houdini import sidecar, worker  # noqa: E402

from cvcops import cli, receipt  # noqa: E402


def test_worker_python_needs_a_real_file(tmp_path):
    with pytest.raises(worker.WorkerEnvironmentError, match="not set"):
        worker.worker_python("CVCOPS", {})
    with pytest.raises(worker.WorkerEnvironmentError, match="not a file"):
        worker.worker_python("CVCOPS", {"CVCOPS_WORKER_PYTHON": str(tmp_path / "nope.exe")})
    assert worker.worker_python("CVCOPS", {"CVCOPS_WORKER_PYTHON": sys.executable}) == sys.executable


def test_scrubbed_env_drops_python_and_houdini_python_variables():
    env = worker.scrubbed_env({"PATH": "p", "SYSTEMROOT": "s", "PYTHONPATH": "x", "PYTHONHOME": "x",
                               "PYTHONSTARTUP": "x", "PYTHONUSERBASE": "x", "VIRTUAL_ENV": "x",
                               "HOUDINI_PYTHON_VERSION": "x", "CVCOPS_ROOT": "r"})
    assert env == {"PATH": "p", "SYSTEMROOT": "s", "CVCOPS_ROOT": "r"}


@pytest.mark.parametrize("make", [worker.flow_argv, worker.verify_argv])
def test_argv_is_isolated_unbuffered_and_parses(make):
    argv = make("/w/python", "C:/a b/cache/analysis.####.exr", "C:/a b/cache", 1001, 1024, "dis_medium", "cpu", 1.0)
    assert argv[:5] == ["/w/python", "-I", "-u", "-m", "cvcops"]
    args = cli.build_parser().parse_args(argv[5:])
    assert args.frames == (1001, 1024) and args.recipe == "dis_medium" and args.backend == "cpu" and args.tolerance == 1.0


def _fake(tmp_path, body):
    script = tmp_path / "fake_worker.py"
    script.write_text(body, encoding="utf-8")
    return [sys.executable, "-u", str(script)]


@pytest.mark.parametrize("code", [0, 1, 3])
def test_run_worker_returns_code_progress_and_stderr_tail(tmp_path, code):
    argv = _fake(tmp_path, f"import sys\nprint('flow 1-2 ok')\nprint('flow 2-3 ok')\nprint('why', file=sys.stderr)\nsys.exit({code})\n")
    ticks = []
    got, lines, tail = worker.run_worker(argv, dict(os.environ), str(tmp_path), tick=ticks.append)
    assert got == code and lines == ["flow 1-2 ok", "flow 2-3 ok"] and tail == ["why"]
    assert "flow 1-2 ok" in ticks
    assert worker.describe_exit(code, tail).startswith(("done", "a pair failed", "the worker's environment"))


def test_a_worker_flooding_stderr_does_not_hang(tmp_path):
    argv = _fake(tmp_path, "import sys\nfor i in range(20000):\n    sys.stderr.write('x' * 100 + '\\n')\nprint('flow 1-2 ok')\n")
    t = time.monotonic()
    code, lines, tail = worker.run_worker(argv, dict(os.environ), str(tmp_path))
    assert code == 0 and lines == ["flow 1-2 ok"] and len(tail) == 20 and time.monotonic() - t < 30


def test_a_cancelled_worker_is_gone(tmp_path):
    argv = _fake(tmp_path, "import time\nprint('flow 1-2 ok', flush=True)\ntime.sleep(60)\n")

    class Cancelled(Exception):
        pass

    def tick(line):
        if line is None:
            raise Cancelled

    t = time.monotonic()
    with pytest.raises(Cancelled):
        worker.run_worker(argv, dict(os.environ), str(tmp_path), tick=tick, grace_s=1.0)
    assert time.monotonic() - t < 5


@pytest.mark.parametrize("weights, gain, gamma, scale, fps", [
    ([0.2126, 0.7152, 0.0722], 1.0, 1.0, "1.0", 24.0),
    ([0.3, 0.6, 0.1], 4.0, 2.2, "0.5", 25.0),
    ([0.3, 0.6, 0.1], 1.0, 1.0, "0.25", None),
])
def test_the_sidecar_round_trips_through_the_worker(tmp_path, weights, gain, gamma, scale, fps):
    data = sidecar.fragment(weights, gain, gamma, scale, fps)
    path = sidecar.write(str(tmp_path), data)
    assert os.path.basename(path) == "analysis.json" and not [n for n in os.listdir(tmp_path) if n.startswith(".")]
    got = receipt.read_analysis_sidecar(str(tmp_path / "analysis.####.exr"))
    assert got["analysis"] == {"luminance_weights": weights, "gain": gain, "gamma": gamma, "scale": float(scale),
                               "color_space": None}
    assert got["frame"] == {"fps": fps}
    assert sidecar.matches(str(tmp_path), data) and not sidecar.matches(str(tmp_path), sidecar.fragment(weights, gain, gamma, "1.0", 30.0))
    assert json.loads(Path(path).read_text(encoding="utf-8"))["schema"] == receipt.SIDECAR_SCHEMA
