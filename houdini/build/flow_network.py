"""The flow asset's inside, built by script: ports, prep, downscale, export, load, convert. Runs in hython.

build_hdas.py calls set_ports(subnet, spec) and build(subnet) on a COP subnet that already carries the asset's
parameters; nothing here runs at import. Node and parm tokens were read off 22.0.492 (probes/m3_tokens.py,
docs/FACTS.md). Every control reaches the inside by a channel reference to the asset's own parameter, so a locked
asset still follows its controls; the Bake function only presses buttons.
"""
from pathlib import Path

KERNELS = Path(__file__).with_name("kernels")
PORT_TYPES = {"RGBA": "vector4", "RGB": "vector", "UV": "vector2", "Mono": "float"}
INTERNAL = ("inputs", "prep", "downscale", "export", "load", "convert", "outputs")
EXPORT_DIR = ".export"
ANALYSIS_NAME = "analysis.$F4.exr"
FLOW_NAME = "flow.$F4.exr"


def set_ports(subnet, spec):
    """Typed, labelled ports from controls.json's v0.1 inputs and outputs, in file order."""
    for kind in ("input", "output"):
        ports = spec[kind + "s"]
        subnet.parm(kind + "s").set(len(ports))
        for i, port in enumerate(ports, 1):
            subnet.parm(f"{kind}label{i}").set(port["label"])
            subnet.parm(f"{kind}type{i}").set(PORT_TYPES[port["type"]])


def _raw_32bit_file(node, path_expr, layer_type):
    node.parm("filename").set(path_expr)
    node.parm("colorspace").set("raw")
    node.parm("missingdata").set("error")
    node.parm("aovs").set(1)
    node.parm("aov1").set("C")
    node.parm("type1").set(layer_type)
    node.parm("precision1").set("b32")
    node.parm("raw1").set(1)


def _opencl(node, kernel, inputs, outputs, bindings=(), metadata_from=None):
    node.parm("kernelcode").set((KERNELS / kernel).read_text(encoding="utf-8"))
    node.parm("inputs").set(len(inputs))
    for i, (name, typ) in enumerate(inputs, 1):
        node.parm(f"input{i}_name").set(name)
        node.parm(f"input{i}_type").set(typ)
    node.parm("outputs").set(len(outputs))
    for i, (name, typ) in enumerate(outputs, 1):
        node.parm(f"output{i}_name").set(name)
        node.parm(f"output{i}_type").set(typ)
        node.parm(f"output{i}_precision").set("32")
        if metadata_from:
            node.parm(f"output{i}_metadata").set("name")
            node.parm(f"output{i}_metaname").set(metadata_from)
    node.parm("bindings").set(len(bindings))
    for i, (name, typ) in enumerate(bindings, 1):
        node.parm(f"bindings{i}_name").set(name)
        node.parm(f"bindings{i}_type").set(typ)


def _ref(parm, expr):
    parm.setExpression(expr, language=_hscript())


def _hscript():
    import hou
    return hou.exprLanguage.Hscript


def build(subnet):
    """Create and wire the internal nodes. The subnet must already have its ports and the v0.1 parameters."""
    inputs = subnet.node("inputs")
    outputs = subnet.node("outputs")

    prep = subnet.createNode("opencl", "prep")
    _opencl(prep, "prep.cl", [("src", "float4")], [("grey", "float3")],
            bindings=[("weights", "float3"), ("gain", "float"), ("gamma", "float")])
    for comp, parm in zip(prep.parmTuple("bindings1_v3val"), subnet.parmTuple("luma_weights")):
        _ref(comp, f'ch("../{parm.name()}")')
    _ref(prep.parm("bindings2_fval"), 'ch("../gain")')
    _ref(prep.parm("bindings3_fval"), 'ch("../gamma")')
    prep.setInput(0, inputs, 0)

    down = subnet.createNode("resample", "downscale")
    down.parm("filter").set("box")
    _ref(down.parm("scale"), 'atof(chs("../analysis_scale"))')
    down.setInput(0, prep, 0)

    export = subnet.createNode("rop_image", "export")
    export.setInput(0, down, 0)
    export.parm("copoutput").set(f'`chs("../cache_dir")`/{EXPORT_DIR}/{ANALYSIS_NAME}')
    export.parm("trange").set("on")
    f = export.parmTuple("f")
    f.deleteAllKeyframes()
    _ref(f[0], 'ch("../frange1")')
    _ref(f[1], 'ch("../frange2") + 1')
    f[2].set(1)
    export.parm("colorconversion").set("raw")
    export.parm("setprecision").set(1)
    export.parm("precision").set("b32")
    export.parm("savebackground").set(0)
    export.parm("exportattribs").set(0)
    export.parm("mkpath").set(1)
    export.parm("aov1").set("C")
    export.parm("size1").set("float32")
    export.parm("raw1").set(1)

    load = subnet.createNode("file", "load")
    _raw_32bit_file(load, f'`chs("../cache_dir")`/{FLOW_NAME}', "vector")

    convert = subnet.createNode("opencl", "convert")
    _opencl(convert, "convert.cl", [("flowexr", "float3"), ("source", "float4")],
            [("flow", "float2"), ("valid", "float")], metadata_from="source")
    convert.setInput(0, load, 0)
    convert.setInput(1, inputs, 0)

    outputs.setInput(0, convert, 0)
    outputs.setInput(1, convert, 1)
    subnet.layoutChildren()
    return {n: subnet.node(n) for n in INTERNAL}
