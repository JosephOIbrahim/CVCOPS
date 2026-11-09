"""Probe P7: can hython build a digital asset by script, and which licence flavour does it carry? Runs in hython.

    uv run python probes/hython.py probes/p7_asset.py probe_out/p7

Builds a throwaway COP asset (a subnet holding one Constant COP) into probe_out/p7, installs the file again from
disk and reports what it carries: the file Houdini actually wrote, its first bytes, the session's licence
category, and which licence markers (limited-commercial or non-commercial) the definition's sections carry. Nothing here is the real asset; houdini/build/build_hdas.py
stays Mission 3's. Exit 0 when the asset was written and reloads, 1 when it was not, 3 without hou.
"""
import json
import os
import sys

try:
    import hou
except ImportError:
    print("no hou: run this through probes/hython.py", file=sys.stderr)
    sys.exit(3)


def main(argv):
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    out = os.path.abspath(argv[0])
    os.makedirs(out, exist_ok=True)
    net = hou.node("/obj").createNode("copnet", "p7")
    sub = net.createNode("subnet", "probe_asset")
    sub.createNode("constant")
    wanted = os.path.join(out, "cvcops_probe_p7.hda").replace("\\", "/")
    try:
        node = sub.createDigitalAsset(name="cvcops_probe::p7::1.0", hda_file_name=wanted,
                                      description="CVCOPs P7 probe", min_num_inputs=0, max_num_inputs=1)
    except hou.Error as e:
        print("createDigitalAsset failed:", e, file=sys.stderr)
        return 1
    defn = node.type().definition()
    written = defn.libraryFilePath()
    files = sorted(os.listdir(out))
    hou.hda.uninstallFile(written)
    hou.hda.installFile(written)
    reloaded = [d.nodeTypeName() for d in hou.hda.definitionsInFile(written)]
    contents = defn.uncompressedContents() if hasattr(defn, "uncompressedContents") else ""
    markers = {m: (m in contents) for m in ("LIMITED_COMMERCIAL_FILE", "NON_COMMERCIAL_FILE", "HouLC", "HouNC")}
    with open(written, "rb") as f:
        head = f.read(16)
    report = {
        "build": hou.applicationVersionString(),
        "session_licence_category": str(hou.licenseCategory()),
        "asked_for": wanted,
        "written": written,
        "files_in_folder": files,
        "type_name": node.type().name(),
        "reloaded_types": reloaded,
        "file_head_bytes": repr(head),
        "licence_markers_in_contents": markers,
    }
    print(json.dumps(report, indent=1))
    return 0 if os.path.isfile(written) and reloaded else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
