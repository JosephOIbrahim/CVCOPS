"""The worker's command line: one process per bake, files in and files out.

    python -m cvcops capabilities           print the manifest an agent registers tools from
    python -m cvcops package --write DIR    write the Houdini package file into DIR (install is one file)
    python -m cvcops flow ...               Mission 2
    python -m cvcops verify ...             Mission 2

Exit codes follow the manifest: 0 done, 1 failed, 3 broken environment.
"""
import argparse
import json
import sys
from importlib import resources

from .contract import BACKENDS, RECIPES

EXIT_OK, EXIT_FAILED, EXIT_ENVIRONMENT = 0, 1, 3


def load_manifest():
    return json.loads(resources.files("cvcops").joinpath("capabilities.json").read_text(encoding="utf-8"))


def _frames(text):
    first, _, last = text.partition("-")
    try:
        return int(first), int(last or first)
    except ValueError:
        raise argparse.ArgumentTypeError(f"frames must look like 1001-1100, not {text!r}")


def _not_built(name):
    def run(args):
        print(f"cvcops {name}: not built yet. It is Mission 2's work (docs/BLUEPRINT.md, section 8).", file=sys.stderr)
        return EXIT_FAILED
    return run


def _capabilities(args):
    print(json.dumps(load_manifest(), indent=2))
    return EXIT_OK


def _package(args):
    from .package import ROOT, write_package
    path = write_package(args.write, root=args.root or ROOT, worker_python=args.python)
    print(path)
    return EXIT_OK


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
            p.add_argument("--tolerance", type=float, default=1.0, help="validity tolerance in pixels")
        else:
            p.add_argument("--json", action="store_true", help="print the result as JSON")
        p.set_defaults(run=_not_built(name))
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
