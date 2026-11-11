"""Self-test of the built flow asset, in a fresh hython started the judge's way. Runs in hython:

    uv run python probes/hython.py houdini/tests/build_selftest.py

The asset must load from <hpath>/otls at start-up through the package file alone (no installFile): that is how an
artist's Houdini and bake_once.py meet it. Then an instance must carry exactly the v0.1 ports and controls of
controls.json, the PythonModule, and a build stamp equal to the tree on disk; the cache paths inside must follow the
Cache Folder control; and instantiating it must not import OpenCV. Prints one line per check. Exit 0 all pass, 1 a
check failed, 3 without hou or without the asset (rebuild with houdini/build/build_hdas.py).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "houdini" / "build"))


def main():
    try:
        import hou
    except ImportError:
        print("build_selftest.py: no hou; run it through probes/hython.py", file=sys.stderr)
        return 3
    import build_hdas
    import stamp as stamp_mod
    from flow_network import PORT_TYPES

    n = build_hdas.names()
    spec = build_hdas.controls()
    tname = build_hdas.type_name(n)
    nt = hou.nodeType(hou.copNodeTypeCategory(), tname)
    if nt is None or nt.definition() is None:
        print(f"build_selftest.py: {tname} did not load from <hpath>/otls; build it first", file=sys.stderr)
        return 3
    results = []

    def check(name, ok, detail=""):
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f": {detail}" if detail else ""))

    defn = nt.definition()
    check("loaded from hpath without installFile", Path(defn.libraryFilePath()).parent.name == "otls",
          defn.libraryFilePath())
    net = hou.node("/obj").createNode("copnet", "selftest")
    node = net.createNode(tname, "flow1")
    want_in = [(p["label"], p["type"]) for p in spec["inputs"]]
    want_out = [(p["label"], p["type"]) for p in spec["outputs"]]
    got_in = list(zip(node.inputLabels(), [str(d) for d in node.inputDataTypes()]))
    got_out = list(zip(node.outputLabels(), [str(d) for d in node.outputDataTypes()]))
    check("input ports", got_in == want_in, f"{got_in}")
    check("output ports", got_out == want_out, f"{got_out}")
    missing, wrong = [], []
    for c in spec["controls"]:
        t = node.parmTemplateGroup().find(c["name"])
        if t is None:
            missing.append(c["name"])
            continue
        if t.label() != c["label"]:
            wrong.append(f"{c['name']} label {t.label()!r}")
        if c["type"] in ("float", "float3"):
            got = list(node.parmTuple(c["name"]).eval())
            want = c["default"] if isinstance(c["default"], list) else [c["default"]]
            if [round(x, 6) for x in got] != [round(x, 6) for x in want]:
                wrong.append(f"{c['name']} default {got}")
        if c["type"] == "menu":
            if node.parm(c["name"]).evalAsString() != c["default"]:
                wrong.append(f"{c['name']} default {node.parm(c['name']).evalAsString()}")
        if c["type"] == "int2":
            exprs = [p.expression() for p in node.parmTuple(c["name"])]
            if exprs != c["default"]:
                wrong.append(f"{c['name']} default {exprs}")
    check("every v0.1 control, label and default", not missing and not wrong, f"missing {missing} wrong {wrong}")
    planned = [c["name"] for c in json.loads((ROOT / "houdini" / "build" / "controls.json").read_text("utf-8"))["controls"]
               if c["status"] != "v0.1"]
    check("no planned control built", not any(node.parm(p) for p in planned), str(planned))
    check("PythonModule is Python", defn.hasSection("PythonModule") and bool(defn.extraFileOptions().get("PythonModule/IsPython")))
    module = node.hdaModule()
    check("module exposes on_bake and on_check_cache", hasattr(module, "on_bake") and hasattr(module, "on_check_cache"))
    built = json.loads(defn.sections()["CvcopsStamp"].contents())
    now = stamp_mod.stamp(ROOT)
    check("build stamp matches the tree on disk", built["stamp"] == now, f"built {built['stamp'][:12]} now {now[:12]}")
    node.parm("cache_dir").set("$HIP/cvcops_selftest/$OS")
    cache = node.parm("cache_dir").evalAsString()
    load = node.node("load").parm("filename").evalAsString()
    export = node.node("export").parm("copoutput").evalAsString()
    check("load reads <cache>/flow.$F4.exr", load.startswith(cache + "/flow.") and cache.endswith("/flow1"), load)
    check("export writes <cache>/.export/analysis.$F4.exr", export.startswith(cache + "/.export/analysis."), export)
    node.parmTuple("frange").deleteAllKeyframes()
    node.parmTuple("frange").set((1001, 1004))
    f = node.node("export").parmTuple("f").eval()
    check("export renders f1 to f2 + 1", tuple(f[:2]) == (1001.0, 1005.0), str(f))
    check("OpenCV not imported", "cv2" not in sys.modules)
    print(json.dumps({"type": tname, "file": defn.libraryFilePath(), "licence": str(hou.licenseCategory()),
                      "houdini": hou.applicationVersionString(), "stamp": built["stamp"]}))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
