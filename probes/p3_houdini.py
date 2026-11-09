"""Probe P3, Houdini's half: File COP reads the transport pattern, ROP Image writes it back. Runs in hython.

    uv run python probes/p3_transport.py write probe_out/
    uv run python probes/hython.py probes/p3_houdini.py probe_out/transport.1001.exr probe_out/returned.1001.exr
    uv run python probes/p3_transport.py compare probe_out/transport.1001.exr probe_out/returned.1001.exr

Settings under test (node and parm names introspected in hython 22.0.492, Mission 0):
  File COP   colorspace=raw, missingdata=error, every AOV precision#=b32 and raw#=1
  ROP Image  colorconversion=raw, every AOV size#=float32 and raw#=1, setprecision=1 with precision=b32
Prints the AOVs and the parm values it actually set, so FACTS can record them. Builds nothing on disk but the image.
Exit 0 when the image was written, 1 when the network could not cook, 3 when hou is unavailable.
"""
import os
import sys

try:
    import hou
except ImportError:
    print("no hou: run this through probes/hython.py", file=sys.stderr)
    sys.exit(3)


def build(src, dst):
    net = hou.node("/obj").createNode("copnet", "p3")
    f = net.createNode("file", "read")
    f.parm("filename").set(src.replace("\\", "/"))
    f.parm("colorspace").set("raw")
    f.parm("missingdata").set("error")
    f.parm("addaovs").pressButton()
    count = f.parm(f.parm("aov1").parentMultiParm().name()).eval() if f.parm("aov1") else 0
    for i in range(1, count + 1):
        f.parm(f"precision{i}").set("b32")
        f.parm(f"raw{i}").set(1)
    rop = net.createNode("rop_image", "write")
    rop.setInput(0, f)
    rop.parm("copoutput").set(dst.replace("\\", "/"))
    rop.parm("colorconversion").set("raw")
    rop.parm("setprecision").set(1)
    rop.parm("precision").set("b32")
    rop.parm("addaovs").pressButton()
    rcount = rop.parm(rop.parm("aov1").parentMultiParm().name()).eval() if rop.parm("aov1") else 0
    for i in range(1, rcount + 1):
        rop.parm(f"size{i}").set("float32")
        rop.parm(f"raw{i}").set(1)
    return net, f, rop, count, rcount


def describe(node, names):
    out = {}
    for p in node.parms():
        if any(p.name().rstrip("0123456789") == n for n in names):
            out[p.name()] = p.evalAsString()
    return out


def main(argv):
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    src, dst = (os.path.abspath(a) for a in argv)
    hou.setFrame(1001)
    net, f, rop, count, rcount = build(src, dst)
    print("build", hou.applicationVersionString())
    print("file AOVs", count, describe(f, ["filename", "colorspace", "missingdata", "aov", "type", "precision", "raw"]))
    print("rop AOVs", rcount, describe(rop, ["copoutput", "colorconversion", "setprecision", "precision", "aov", "size", "raw"]))
    try:
        rop.parm("execute").pressButton()
    except hou.Error as e:
        print("cook failed:", e, file=sys.stderr)
        return 1
    for n in (f, rop):
        if n.errors():
            print(n.name(), "errors:", n.errors(), file=sys.stderr)
            return 1
        if n.warnings():
            print(n.name(), "warnings:", n.warnings())
    if not os.path.isfile(dst):
        print("ROP Image wrote nothing at", dst, file=sys.stderr)
        return 1
    print("wrote", dst)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
