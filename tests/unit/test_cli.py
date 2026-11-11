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


FILL = {"{analysis_pattern}": "bake/analysis.####.exr", "{out_dir}": "bake", "{frames}": "1001-1010",
        "{recipe}": "dis_medium", "{backend}": "cpu", "{tolerance}": "1.0"}


def test_every_planned_operation_parses_its_own_argv():
    """The argv a manifest promises must be accepted by the parser, with placeholders filled."""
    parser = cli.build_parser()
    for op in cli.load_manifest()["operations"]:
        if op["status"] == "parked":
            continue
        argv = [FILL.get(a, a) for a in op["argv"]]
        parser.parse_args(argv)


def test_flow_and_verify_are_available_with_the_three_exit_codes():
    ops = {op["name"]: op for op in cli.load_manifest()["operations"]}
    for name in ("flow", "verify"):
        assert ops[name]["status"] == "available"
        assert set(ops[name]["exit_codes"]) == {"0", "1", "3"}


def test_every_available_operation_runs_its_filled_argv(tmp_path, capsys):
    """An adapter that fills the manifest's argv gets exit 0 on a small, fresh folder."""
    import numpy as np
    import OpenEXR
    rng = np.random.default_rng(2)
    base = rng.random((32, 48))
    for i in range(3):
        x = (np.clip(np.rint(np.roll(base, i, axis=1) * 255), 0, 255) / 255.0).astype(np.float32)
        with OpenEXR.File({"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage},
                          {"R": x, "G": x.copy(), "B": x.copy()}) as f:
            f.write(str(tmp_path / f"analysis.{1001 + i}.exr"))
    fill = dict(FILL, **{"{analysis_pattern}": str(tmp_path / "analysis.####.exr"), "{out_dir}": str(tmp_path),
                         "{frames}": "1001-1002"})
    ops = {op["name"]: op for op in cli.load_manifest()["operations"] if op["status"] == "available"}
    for name in ("capabilities", "flow", "verify"):        # verify needs flow's results to be fresh
        assert cli.main([fill.get(a, a) for a in ops.pop(name)["argv"]]) == 0, name
    assert not ops, f"an available operation has no run here: {sorted(ops)}"
    capsys.readouterr()


def test_package_file_points_at_this_checkout(tmp_path):
    path = write_package(tmp_path, worker_python="/opt/worker/python")
    data = json.loads(path.read_text())
    assert data == package_dict(worker_python="/opt/worker/python")
    assert data["hpath"].endswith("/houdini") and "\\" not in data["hpath"]
    assert {"CVCOPS_ROOT", "CVCOPS_WORKER_PYTHON"} == {k for entry in data["env"] for k in entry}
