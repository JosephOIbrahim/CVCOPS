"""Install CVCOPs from a git checkout, or make the checkout first.

    git clone https://github.com/JosephOIbrahim/CVCOPS.git
    cd CVCOPS
    uv run python tools/install.py

What it does, in order:

1. Builds the worker's environment from the pinned lock file (`uv sync`).
2. Finds Houdini's hython and writes `local.toml`, unless that file already exists.
3. Runs the judge's self-test, so you know the tests work on this machine.
4. Builds the asset under your own licence when it is missing or its build stamp differs from the tree, then writes
   one Houdini package file where desktop Houdini reads it, and prints the path for you to confirm.

What it never does: install anything into Houdini's Python, change a system setting, need administrator rights,
or overwrite a `local.toml` you already have. Run it again at any time; it only fills in what is missing.

    --check          report what it would do and change nothing
    --hython PATH    use this hython instead of searching for one
    --no-houdini     skip the Houdini steps
    --no-selftest    skip the self-test (about 40 seconds)
    --packages DIR   write the package file into DIR instead of the default folder
    --force          rebuild the asset even when its stamp matches

Run from outside a checkout (for example a copy downloaded from a release), it clones the tag in `RELEASE_TAG` into
./CVCOPS first and carries on there, so a downloaded installer keeps installing the version it came from.

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
RELEASE_TAG = "v0.1.0"          # a downloaded copy clones this tag, never main (OD-23)
HOUDINI_PREF = "houdini22.0"    # desktop Houdini 22's folder name inside Documents (OD-24)
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


def expand_hver(path, hython=None):
    """Houdini's `__HVER__` is `major.minor`; take it from the hython found, else 22.0."""
    if "__HVER__" not in str(path):
        return Path(path)
    major_minor = ".".join(str(v) for v in version_key(hython)[:2]) if hython else "22.0"
    return Path(str(path).replace("__HVER__", major_minor))


def documents_folder():
    """The Windows Documents known folder, which is where desktop Houdini looks. Never the shell's HOME (OD-24)."""
    if sys.platform == "win32":
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(260)
            if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0 and buf.value:
                return Path(buf.value)
        except (AttributeError, OSError):
            pass
    return Path.home() / "Documents"


def packages_folder(env=None, hython=None):
    """Where the package file goes: HOUDINI_USER_PREF_DIR if set, else Documents/houdini22.0/packages."""
    env = os.environ if env is None else env
    upd = env.get("HOUDINI_USER_PREF_DIR")
    if upd:
        return expand_hver(upd, hython) / "packages"
    return documents_folder() / HOUDINI_PREF / "packages"


def asset_file(root, names=None):
    """The asset's file name, from [tool.cvcops.names]."""
    if names is None:
        names = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["cvcops"]["names"]
    return f"{names['hda_namespace']}_{names['hda_flow']}.hda"


def tree_stamp(root):
    """houdini/build/stamp.py's stamp over the tree, imported by path so install needs no package."""
    import importlib.util
    path = root / "houdini" / "build" / "stamp.py"
    spec = importlib.util.spec_from_file_location("cvcops_stamp", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.stamp(root)


def _local_hython(root):
    try:
        return tomllib.loads((root / "local.toml").read_text(encoding="utf-8")).get("hython")
    except (OSError, tomllib.TOMLDecodeError):
        return None


def build_state(root):
    """(asset present, stamp matches, the stamp file's value, the tree's value)."""
    otls = root / "houdini" / "otls"
    name = asset_file(root)
    stamp_file = otls / f"{name}.stamp.json"
    built = (otls / name).is_file()
    recorded = None
    if stamp_file.is_file():
        import json
        recorded = json.loads(stamp_file.read_text(encoding="utf-8")).get("stamp")
    return built, recorded == tree_stamp(root), recorded, tree_stamp(root)


def main(argv=None, root=ROOT):
    ap = argparse.ArgumentParser(prog="install.py", description="Install CVCOPs from a git checkout.")
    ap.add_argument("--check", action="store_true", help="report what it would do and change nothing")
    ap.add_argument("--hython", help="use this hython instead of searching for one")
    ap.add_argument("--no-houdini", action="store_true", help="skip the Houdini steps")
    ap.add_argument("--no-selftest", action="store_true", help="skip the self-test")
    ap.add_argument("--packages", metavar="DIR", help="write the package file into DIR")
    ap.add_argument("--force", action="store_true", help="rebuild the asset even when its stamp matches")
    a = ap.parse_args(argv)

    if not in_checkout(root):                      # a lone copy, for example from a release page
        if not shutil.which("git"):
            say("STOP", "git is not on PATH. Install git, then run this again.")
            return 3
        target = Path.cwd() / "CVCOPS"
        if a.check:
            say("WOULD", f"clone {REPO} at {RELEASE_TAG or 'main'} into {target}")
            return 0
        if not in_checkout(target):
            say("RUN", f"git clone {REPO}")
            clone = ["git", "clone", "--depth", "1"]
            if RELEASE_TAG:
                clone += ["--branch", RELEASE_TAG]
            if run(clone + [REPO, str(target)], Path.cwd()).returncode:
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

    # 4. the asset, built here under this machine's licence
    if a.no_houdini:
        say("SKIP", "the asset build and the package file, as asked")
    else:
        built, matches, recorded, current = build_state(root)
        if built and matches and not a.force:
            say("KEEP", f"the asset is built and matches this tree (stamp {str(current)[:12]})")
        elif a.check:
            say("WOULD", "build the asset: uv run python probes/hython.py houdini/build/build_hdas.py --out houdini/otls")
        else:
            why = "forced" if a.force else ("no asset" if not built else "the tree changed since the build")
            say("RUN", f"the asset build ({why})")
            r = run(["uv", "run", "python", "probes/hython.py", "houdini/build/build_hdas.py", "--out", "houdini/otls"],
                    root)
            if r.returncode == 3:
                say("STOP", "the asset build needs a Houdini licence; run this on a machine with one")
                return 3
            if r.returncode:
                say("FAIL", "the asset build failed")
                return 1
            built, matches, recorded, current = build_state(root)
            if not built:
                say("FAIL", "the build reported success but wrote no asset")
                return 1
            say("OK", f"the asset is built under this machine's licence (stamp {str(current)[:12]})")

    # 5. one package file, where desktop Houdini looks
    if a.no_houdini:
        pass
    else:
        target = Path(a.packages) if a.packages else packages_folder(hython=_local_hython(root))
        if a.check:
            say("WOULD", f"write the package file into {target}")
        else:
            r = run(["uv", "run", "python", "-m", "cvcops", "package", "--write", str(target)], root, quiet=True)
            if r.returncode:
                say("FAIL", f"writing the package file into {target} failed")
                return 1
            say("OK", f"package file written: {target}  <- check this is the folder your desktop Houdini reads")

    print("Done." if not a.check else "Checked. Nothing was changed.")
    print("Where things stand: docs/STATE.md. Plain tools/check.py fails until the owner's judge.lock exists; that is by design.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
