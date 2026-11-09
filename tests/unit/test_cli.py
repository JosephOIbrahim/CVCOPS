"""The command line's shape, which SYNAPSE's adapter relies on."""
import json

from cvcops import cli
from cvcops.package import package_dict, write_package


def test_capabilities_prints_the_manifest(capsys):
    assert cli.main(["capabilities"]) == 0
    manifest = json.loads(capsys.readouterr().out)
    assert manifest["schema"] == "cvcops.capabilities.v1"
    names = {op["name"] for op in manifest["operations"]}
    assert {"capabilities", "flow", "verify"} <= names


def test_every_planned_operation_parses_its_own_argv():
    """The argv a manifest promises must be accepted by the parser, with placeholders filled."""
    fill = {"{analysis_pattern}": "bake/analysis.####.exr", "{out_dir}": "bake", "{frames}": "1001-1010",
            "{recipe}": "dis_medium", "{backend}": "cpu"}
    parser = cli.build_parser()
    for op in cli.load_manifest()["operations"]:
        if op["status"] == "parked":
            continue
        argv = [fill.get(a, a) for a in op["argv"]]
        parser.parse_args(argv)


def test_package_file_points_at_this_checkout(tmp_path):
    path = write_package(tmp_path, worker_python="/opt/worker/python")
    data = json.loads(path.read_text())
    assert data == package_dict(worker_python="/opt/worker/python")
    assert data["hpath"].endswith("/houdini") and "\\" not in data["hpath"]
    assert {"CVCOPS_ROOT", "CVCOPS_WORKER_PYTHON"} == {k for entry in data["env"] for k in entry}
