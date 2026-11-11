"""Mission 2: the manifest names every option flow and verify take, and nothing they do not."""
import pytest

from cvcops import cli

OPTION_INPUT = {"--in": "analysis_pattern", "--out": "out_dir", "--frames": "frames", "--recipe": "recipe",
                "--backend": "backend", "--tolerance": "tolerance"}


def _options(command):
    sub = next(a for a in cli.build_parser()._actions if getattr(a, "choices", None) and command in a.choices)
    return {opt: act for act in sub.choices[command]._actions for opt in act.option_strings if opt.startswith("--")}


@pytest.mark.parametrize("command", ["flow", "verify"])
def test_every_option_is_a_manifest_input_or_a_literal_flag(command):
    op = next(o for o in cli.load_manifest()["operations"] if o["name"] == command)
    inputs = {i["name"]: i for i in op["inputs"]}
    for opt, act in _options(command).items():
        if opt == "--help":
            continue
        if opt in OPTION_INPUT:
            name = OPTION_INPUT[opt]
            assert name in inputs, f"{command} {opt} has no manifest input {name}"
            assert f"{{{name}}}" in op["argv"] and op["argv"][op["argv"].index(f"{{{name}}}") - 1] == opt
            if act.choices:
                assert inputs[name]["choices"] == list(act.choices)
            if act.default is not None:
                assert inputs[name].get("default") == act.default, f"{command} {opt} default differs"
        else:
            assert opt in op["argv"], f"{command} {opt} is neither an input nor in the manifest's argv"
    assert set(inputs) <= set(OPTION_INPUT.values())
