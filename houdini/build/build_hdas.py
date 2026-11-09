"""Build the assets from source, by script. Mission 3 writes this; probe P7 finds out whether hython can.

    uv run python probes/hython.py houdini/build/build_hdas.py --out houdini/otls

What it builds (docs/BLUEPRINT.md, section 5): one asset whose operator name is
<hda_namespace>::<hda_flow>::1.0, both read from [tool.cvcops.names] in pyproject.toml (decision 0002). Inside:
the prep network (luminance, gain, gamma, optional downscale), ROP Image writing analysis.####.exr raw, a Bake
button that starts the worker with the interpreter named in <env_prefix>_WORKER_PYTHON, File COP reading
flow.####.exr (Raw, 32-bit, Missing Data on Report Message), and the one conversion node, which outputs flow as
a UV layer and valid as Mono. Never hand-edit the built file; change this script and build again.

The asset's inputs, outputs, folders and parameters come from controls.json beside this file and from nowhere
else (docs/CONTROLS.md). Build only the entries whose status is "v0.1"; menus marked choices_from read the
contract at build time.
"""
import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def names():
    with open(ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)["tool"]["cvcops"]["names"]


def controls(status="v0.1"):
    """The asset's interface from controls.json, keeping only entries with the given status."""
    spec = json.loads((Path(__file__).with_name("controls.json")).read_text(encoding="utf-8"))
    for key in ("inputs", "outputs", "controls"):
        spec[key] = [c for c in spec[key] if c.get("status") == status]
    return spec


def main():
    n = names()
    print(f"build_hdas.py: not built yet. Mission 3 builds {n['hda_namespace']}::{n['hda_flow']}::1.0.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
