"""Starting the worker from Houdini: its interpreter, a clean environment, the argv, and a pipe-safe run.

Imports neither hou nor cv2, so the unit tests run it at rung 1. The worker is a separate process on its own Python
(FACTS P1: hython is 3.13.17 with Houdini's NumPy; the worker is 3.13.14 with OpenCV), started with -I -u so no
PYTHON* variable leaks in and progress lines arrive as they are printed (decision 0004, OD-09).
"""
import os
import queue
import subprocess
import tempfile
import threading

EXIT_OK, EXIT_FAILED, EXIT_ENVIRONMENT = 0, 1, 3
SCRUB = ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE", "VIRTUAL_ENV")


class WorkerEnvironmentError(RuntimeError):
    """The worker cannot be started: exit code 3 semantics."""


def worker_python(prefix, environ=None):
    environ = os.environ if environ is None else environ
    var = f"{prefix}_WORKER_PYTHON"
    path = environ.get(var)
    if not path:
        raise WorkerEnvironmentError(f"{var} is not set; install the package file (python -m cvcops package --write)")
    if not os.path.isfile(path):
        raise WorkerEnvironmentError(f"{var} names {path}, which is not a file")
    return path


def scrubbed_env(environ=None):
    environ = os.environ if environ is None else environ
    return {k: v for k, v in environ.items() if k not in SCRUB and not k.startswith("HOUDINI_PYTHON")}


def _base(python):
    return [python, "-I", "-u", "-m", "cvcops"]


def flow_argv(python, pattern, out_dir, first, last, recipe, backend, tolerance):
    return _base(python) + ["flow", "--in", pattern, "--out", out_dir, "--frames", f"{first}-{last}",
                            "--recipe", recipe, "--backend", backend, "--tolerance", repr(float(tolerance))]


def verify_argv(python, pattern, out_dir, first, last, recipe, backend, tolerance):
    return _base(python) + ["verify", "--in", pattern, "--out", out_dir, "--frames", f"{first}-{last}",
                            "--recipe", recipe, "--backend", backend, "--tolerance", repr(float(tolerance)), "--json"]


def run_worker(argv, env, cwd, tick=None, grace_s=3.0, tail_lines=20):
    """Run the worker, reading stdout line by line and sending stderr to a temporary file, so neither pipe can fill
    and stall the other. tick(line or None) is called for each progress line and while waiting; if it raises, the
    worker is terminated, then killed after grace_s, and the exception is raised again.
    Returns (exit code, stdout lines, last lines of stderr)."""
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as err:
        proc = subprocess.Popen(argv, env=env, cwd=cwd, stdout=subprocess.PIPE, stderr=err, text=True, bufsize=1,
                                encoding="utf-8", errors="replace")
        lines, inbox = [], queue.Queue()
        reader = threading.Thread(target=_pump, args=(proc.stdout, inbox), daemon=True)
        reader.start()
        try:
            while True:
                try:
                    line = inbox.get(timeout=0.05)
                except queue.Empty:
                    if tick:
                        tick(None)          # lets a cancel land while the worker is inside one long pair
                    continue
                if line is None:
                    break
                lines.append(line)
                if tick:
                    tick(line)
            proc.wait()
        except BaseException:
            proc.terminate()
            try:
                proc.wait(grace_s)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            raise
        finally:
            proc.stdout.close()
        code = proc.wait()
        err.seek(0)
        tail = err.read().splitlines()[-tail_lines:]
    return code, lines, tail


def _pump(stream, inbox):
    """Move stdout lines into the queue; None marks the end."""
    try:
        for line in stream:
            inbox.put(line.rstrip("\n"))
    finally:
        inbox.put(None)


def describe_exit(code, tail):
    """What the node says for a worker exit code (the manifest's 0, 1, 3)."""
    text = "\n".join(tail)
    if code == EXIT_OK:
        return "done"
    if code == EXIT_FAILED:
        return "a pair failed or the request was refused:\n" + text
    if code == EXIT_ENVIRONMENT:
        return "the worker's environment is broken:\n" + text
    return f"the worker crashed with exit code {code}:\n" + text
