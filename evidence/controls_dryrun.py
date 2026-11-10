"""Dry run: can Houdini build the flow asset's parameters from houdini/build/controls.json?

Run in hython, the way the judge runs it:

    uv run python probes/hython.py evidence/controls_dryrun.py

It makes one throwaway node in an unsaved session, builds a parameter for every control whose status is v0.1,
and reads each one back: the name, the folder, the default, and a menu's items. No asset is built and nothing is
saved. This shows the spec is buildable. It does not replace Mission 3, which builds the real asset and whose
labels and defaults Joe confirms.

Exit code: 0 when every row passes, 1 when one fails.
"""
import ast
import json
import sys
from pathlib import Path

import hou

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "houdini" / "build" / "controls.json"
CONTRACT = ROOT / "src" / "cvcops" / "contract.py"


def contract_tuples():
    """RECIPES and BACKENDS, read from the contract's source without importing the engine into Houdini."""
    out = {}
    for node in ast.parse(CONTRACT.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ("RECIPES", "BACKENDS"):
            out["contract." + node.targets[0].id] = list(ast.literal_eval(node.value))
    return out


def template(c, lists):
    """One control as a hou.ParmTemplate."""
    name, label, kind, hlp = c["name"], c["label"], c["type"], c.get("help", "")
    if kind == "float":
        lo, hi = c.get("soft_range", (0.0, 10.0))
        return hou.FloatParmTemplate(name, label, 1, default_value=(float(c["default"]),), min=lo, max=hi, help=hlp)
    if kind == "float3":
        return hou.FloatParmTemplate(name, label, 3, default_value=tuple(float(v) for v in c["default"]), help=hlp)
    if kind == "int2":
        return hou.IntParmTemplate(name, label, 2, default_value=(1, 1), default_expression=tuple(c["default"]),
                                   default_expression_language=(hou.scriptLanguage.Hscript,) * 2, help=hlp)
    if kind == "menu":
        items = c.get("choices") or lists[c["choices_from"]]
        return hou.MenuParmTemplate(name, label, tuple(items), tuple(items), default_value=items.index(c["default"]), help=hlp)
    if kind == "directory":
        return hou.StringParmTemplate(name, label, 1, default_value=(c["default"],), string_type=hou.stringParmType.FileReference,
                                      file_type=hou.fileType.Directory, help=hlp)
    if kind == "button":
        return hou.ButtonParmTemplate(name, label, help=hlp)
    if kind == "label":
        return hou.LabelParmTemplate(name, label, column_labels=("",), help=hlp)
    if kind == "toggle":
        return hou.ToggleParmTemplate(name, label, default_value=bool(c.get("default", False)), help=hlp)
    raise ValueError(f"no parameter type for {kind!r}")


def main():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    lists = contract_tuples()
    live = [c for c in spec["controls"] if c["status"] == "v0.1"]
    node = hou.node("/obj").createNode("null", "cvcops_controls_dryrun")
    group = node.parmTemplateGroup()
    for folder in spec["folders"]:
        inside = [template(c, lists) for c in live if c["folder"] == folder]
        if inside:
            group.append(hou.FolderParmTemplate("cvcops_" + folder.lower(), folder, parm_templates=inside, folder_type=hou.folderType.Tabs))
    node.setParmTemplateGroup(group)

    fails = 0
    def row(ok, text):
        nonlocal fails
        fails += 0 if ok else 1
        print(("  PASS  " if ok else "  FAIL  ") + text)

    built = node.parmTemplateGroup()
    fstart, fend = int(hou.hscriptExpression("$FSTART")), int(hou.hscriptExpression("$FEND"))
    for c in live:
        name, kind = c["name"], c["type"]
        found = built.find(name)
        if found is None:
            row(False, f"{name}: not on the node")
            continue
        folder = built.containingFolder(name).label()
        where = f"{name} ({kind}) in {folder}"
        if folder != c["folder"]:
            row(False, f"{where}: the spec says {c['folder']}")
        elif kind == "float":
            row(abs(node.parm(name).eval() - c["default"]) < 1e-9, f"{where}: default {node.parm(name).eval()}")
        elif kind == "float3":
            got = node.parmTuple(name).eval()
            row(all(abs(a - b) < 1e-6 for a, b in zip(got, c["default"])), f"{where}: default {tuple(round(v, 4) for v in got)}")
        elif kind == "int2":
            got = node.parmTuple(name).eval()
            row(tuple(got) == (fstart, fend), f"{where}: follows the scene's range, {got}")
        elif kind == "menu":
            p = node.parm(name)
            want = c.get("choices") or lists[c["choices_from"]]
            row(list(p.menuItems()) == want and p.evalAsString() == c["default"], f"{where}: {len(want)} items, default {p.evalAsString()}")
        elif kind == "directory":
            row(node.parm(name).unexpandedString() == c["default"], f"{where}: default {node.parm(name).unexpandedString()}")
        else:
            row(True, where)
    names = [c["name"] for c in live]
    row(len(set(names)) == len(names), f"{len(names)} controls, every name unique")
    node.destroy()
    print("CHECK: " + ("the spec builds, and every control reads back as written" if not fails else f"{fails} problem(s)"))
    return 1 if fails else 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.exit(code)
