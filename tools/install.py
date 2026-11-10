"""Install CVCOPs from a git checkout, or make the checkout first.

    git clone https://github.com/JosephOIbrahim/CVCOPS.git
    cd CVCOPS
    uv run python tools/install.py

What it does, in order:

1. Builds the worker's environment from the pinned lock file (`uv sync`).
2. Finds Houdini's hython and writes `local.toml`, unless that file already exists.
3. Runs the judge's self-test, so you know the tests work on this machine.
4. Registers the node with Houdini, once the node exists. Today it does not, so this step is skipped and says so.

What it never does: install anything into Houdini's Python, change a system setting, need administrator rights,
or overwrite a `local.toml` you already have. Run it again at any time; it only fills in what is missing.

    --check          report what it would do and change nothing
    --hython PATH    use this hython instead of searching for one
    --no-houdini     skip the Houdini steps
    --no-selftest    skip the self-test (about 40 seconds)

Run from outside a checkout (for example a copy downloaded from a release), it clones the repository into
./CVCOPS first and carries on there.

Exit code: 0 done, 1 the self-test failed, 3 a tool this needs is missing.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = "https://github.com/JosephOIbrahim/CVCOPS.git"
ROOT = Path(__file__).resolve().parents[1]


def in_checkout(root=ROOT):
    """True when this file sits in a CVCOPs checkout."""
    try:
        return tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["name"] == "cvcops"
    except (OSError, KeyError, tomllib.TOMLDecodeError):
        return False


def say(mark, text):
    print(f"  {mark:<5} {text}", flush=True)


def version_key(path):
    """Houdini's version from an install path, as a tuple, so 22.0.492 sorts above 22.0.90."""
    found = re.findall(r"(\d+)\.(\d+)\.(\d+)", str(path))
    return tuple(int(n) for n in found[-1]) if found else (0, 0, 0)


def hython_candidates(platform=sys.platform, env=None, roots=None):
    """Every hython this machine seems to have, newest Houdini first."""
    env = os.environ if env is None else env
    if roots is None:
        roots = {"win32": [Path(env.get("ProgramFiles", "C:/Program Files")) / "Side Effects Software"],
                 "darwin": [Path("/Applications/Houdini")]}.get(platform, [Path("/opt")])
    exe = "hython.exe" if platform == "win32" else "hython"
    found = []
    if env.get("HFS"):
        found.append(Path(env["HFS"]) / "bin" / exe)
    for root in roots:
        if root.is_dir():
            found += [p for p in root.glob(f"*/bin/{exe}")] + [p for p in root.glob(f"*/Frameworks/Houdini.framework/Versions/Current/Resources/bin/{exe}")]
    found = [p for p in dict.fromkeys(found) if p.is_file()]
    return sorted(found, key=version_key, reverse=True)


def write_local_toml(root, hython):
    """Make local.toml from the example, pointing at this hython. UTF-8 without a byte-order mark (FACTS K18).

    Returns False, and writes nothing, when local.toml already exists.
    """
    target = root / "local.toml"
    if target.exists():
        return False
    text = (root / "local.toml.example").read_text(encoding="utf-8")
    line = f'hython = "{Path(hython).as_posix()}"'
    text, n = re.subn(r'(?m)^hython\s*=.*$', lambda _: line, text, count=1)
    if n == 0:
        text += "\n" + line + "\n"
    target.write_bytes(text.encode("utf-8"))
    return True


def run(cmd, root, quiet=False):
    return subprocess.run(cmd, cwd=root, capture_output=quiet, text=True)


def main(argv=None, root=ROOT):
    ap = argparse.ArgumentParser(prog="install.py", description="Install CVCOPs from a git checkout.")
    ap.add_argument("--check", action="store_true", help="report what it would do and change nothing")
    ap.add_argument("--hython", help="use this hython instead of searching for one")
    ap.add_argument("--no-houdini", action="store_true", help="skip the Houdini steps")
    ap.add_argument("--no-selftest", action="store_true", help="skip the self-test")
    a = ap.parse_args(argv)

    if not in_checkout(root):                      # a lone copy, for example from a release page
        if not shutil.which("git"):
            say("STOP", "git is not on PATH. Install git, then run this again.")
            return 3
        target = Path.cwd() / "CVCOPS"
        if a.check:
            say("WOULD", f"clone {REPO} into {target}")
            return 0
        if not in_checkout(target):
            say("RUN", f"git clone {REPO}")
            if run(["git", "clone", REPO, str(target)], Path.cwd()).returncode:
                return 3
        return subprocess.run(["uv", "run", "python", "tools/install.py", *(argv if argv is not None else sys.argv[1:])], cwd=target).returncode

    print(f"CVCOPs installer, in {root}")
    if not shutil.which("uv"):
        say("STOP", "uv is not on PATH. Get it from https://docs.astral.sh/uv/ and run this again.")
        return 3

    # 1. the worker's environment
    if a.check:
        say("WOULD", "uv sync: build the worker's environment from uv.lock")
    else:
        say("RUN", "uv sync")
        if run(["uv", "sync"], root, quiet=True).returncode:
            say("STOP", "uv sync failed. Run it by hand to see why.")
            return 3
        say("OK", "the worker's environment is in .venv")

    # 2. hython and local.toml
    if a.no_houdini:
        say("SKIP", "Houdini steps, as asked")
    elif (root / "local.toml").exists():
        say("KEEP", "local.toml is already here; left as it is")
    else:
        found = [Path(a.hython)] if a.hython else hython_candidates()
        if a.hython and not found[0].is_file():
            say("STOP", f"no file at {a.hython}")
            return 3
        if not found:
            say("NOTE", "no hython found. The judge's first rung needs none. Later: copy local.toml.example to local.toml, or pass --hython")
        elif a.check:
            say("WOULD", f"write local.toml pointing at {found[0]}")
        else:
            write_local_toml(root, found[0])
            say("OK", f"local.toml points at {found[0]}")

    # 3. the self-test
    if a.no_selftest:
        say("SKIP", "the self-test, as asked")
    elif a.check:
        say("WOULD", "uv run python tools/check.py --selftest: prove the judge on this machine")
    else:
        say("RUN", "the judge's self-test (about 40 seconds)")
        r = run(["uv", "run", "python", "tools/check.py", "--selftest"], root, quiet=True)
        last = (r.stdout.strip().splitlines() or [r.stderr.strip()[-200:]])[-1]
        if r.returncode:
            say("FAIL", last)
            return 1
        say("OK", last.replace("CHECK: ", ""))

    # 4. the node
    built = any((root / "houdini" / "otls").glob("*.hda")) if (root / "houdini" / "otls").is_dir() else False
    if a.no_houdini:
        pass
    elif not built:
        say("SKIP", "the Houdini node is not built yet (Mission 3), so nothing is added to Houdini")
    elif a.check:
        say("WOULD", "write one Houdini package file with: uv run python -m cvcops package --write")
    else:
        say("NEXT", 'run: uv run python -m cvcops package --write "$HOUDINI_USER_PREF_DIR/packages"')

    print("Done." if not a.check else "Checked. Nothing was changed.")
    print("Where things stand: docs/STATE.md. Plain tools/check.py fails until the owner's judge.lock exists; that is by design.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
