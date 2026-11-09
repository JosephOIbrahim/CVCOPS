"""Run a script in hython the way the judge does: the hython named in local.toml, an empty preferences folder,
only this package, no houdini.env (tests/thresholds/impls.py, hython_env).

    uv run python probes/hython.py probes/p1_environment.py --record docs/facts/p1_houdini.json

Exit code: the script's own, or 3 when hython is not configured or cannot start.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests" / "thresholds"))
import impls  # noqa: E402


def main(argv):
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    hython = impls.local_config().get("hython")
    if not hython or not Path(hython).is_file():
        print("no hython: put its path in local.toml", file=sys.stderr)
        return 3
    try:
        return subprocess.run([hython, *argv], env=impls.hython_env(), cwd=ROOT, timeout=impls.HYTHON_LIMIT_S).returncode
    except FileNotFoundError as e:
        print(f"hython could not start: {e}", file=sys.stderr)
        return 3
    except subprocess.TimeoutExpired:
        print(f"hython ran past {impls.HYTHON_LIMIT_S} s", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
