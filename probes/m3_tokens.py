"""M3 probe, part 1: read parm names, labels, types, defaults and menu tokens off the running build. Runs in hython.

    uv run python probes/hython.py probes/m3_tokens.py probe_out/m3_tokens.json

Creates the COP node types the flow asset uses inside a throwaway copnet and writes, per type, every parm's name,
label, template type, default and menu items, plus the node's input and output names and data types. Builds nothing
on disk but the JSON. Exit 0 when written, 1 when a node type is missing, 3 without hou.
"""
import json
import os
import sys

try:
    import hou
except ImportError:
    print("no hou: run this through probes/hython.py", file=sys.stderr)
    sys.exit(3)

TYPES = ("opencl", "resample", "rop_image", "file", "subnet", "input", "output", "visualizevelocity", "uvtorgb",
         "distort", "switch", "null", "monotorgb", "rgbtouv", "constant")


def parm_info(t):
    info = {"name": t.name(), "label": t.label(), "type": t.type().name(), "components": t.numComponents()}
    try:
        info["default"] = list(t.defaultValue()) if t.numComponents() > 1 else t.defaultValue()
    except Exception:  # noqa: BLE001
        try:
            info["default"] = t.defaultValue()
        except Exception:  # noqa: BLE001
            info["default"] = None
    if hasattr(t, "menuItems") and t.menuItems():
        info["menu"] = list(zip(t.menuItems(), t.menuLabels()))
    if t.type() == hou.parmTemplateType.Folder and hasattr(t, "folderType"):
        info["folder_type"] = str(t.folderType())
    return info


def walk(templates, out):
    for t in templates:
        out.append(parm_info(t))
        if t.type() == hou.parmTemplateType.Folder:
            walk(t.parmTemplates(), out)


def ports(node):
    res = {}
    for kind in ("input", "output"):
        names = getattr(node, f"{kind}Names", lambda: ())()
        labels = getattr(node, f"{kind}Labels", lambda: ())()
        dtypes = []
        fn = getattr(node, f"{kind}DataTypes", None)
        if fn:
            try:
                dtypes = list(fn())
            except Exception as e:  # noqa: BLE001
                dtypes = [f"error {e}"]
        res[kind] = {"names": list(names), "labels": list(labels), "data_types": [str(d) for d in dtypes]}
    return res


def main(argv):
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    out_path = os.path.abspath(argv[0])
    net = hou.node("/obj").createNode("copnet", "m3_tokens")
    report = {"build": hou.applicationVersionString(), "licence": str(hou.licenseCategory()), "types": {}}
    missing = []
    for name in TYPES:
        try:
            node = net.createNode(name)
        except hou.OperationFailed as e:
            missing.append(name)
            report["types"][name] = {"error": str(e)}
            continue
        templates = []
        walk(node.parmTemplateGroup().entries(), templates)
        report["types"][name] = {"type_name": node.type().name(), "description": node.type().description(),
                                 "parms": templates, "ports": ports(node),
                                 "hou_methods": sorted(m for m in dir(node) if "ata" in m and "ype" in m)}
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1, default=str)
    print("build", report["build"], "licence", report["licence"], "missing", missing, "->", out_path)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
