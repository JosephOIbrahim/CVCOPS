"""Mission 2: every receipt field the SYNAPSE mapping reads exists in the locked schema and in a real receipt."""
import json
import re
from pathlib import Path

import numpy as np
import OpenEXR

from cvcops import cli

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = json.loads((ROOT / "docs" / "contracts" / "receipt.schema.json").read_text(encoding="utf-8"))
MAPPING = (ROOT / "docs" / "contracts" / "synapse_observation_mapping.md").read_text(encoding="utf-8")
NULL_ALLOWED = {"analysis.color_space", "analysis.luminance_weights", "analysis.gain", "analysis.gamma", "frame.fps"}


def _paths():
    """The backticked receipt paths in the table's 'From the receipt' column. `verify` names an operation."""
    paths = set()
    for line in MAPPING.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[1] not in ("From the receipt", "none") and not set(cells[1]) <= set("- "):
            paths |= set(re.findall(r"`([a-z_][a-z0-9_.]*)`", cells[1])) - {"verify"}
    return sorted(paths)


def _schema_node(path):
    node = SCHEMA
    for part in path.split("."):
        if "$ref" in node:
            node = SCHEMA["$defs"][node["$ref"].rsplit("/", 1)[-1]]
        assert part in node.get("properties", {}), f"{path}: the schema has no {part}"
        node = node["properties"][part]
    return node


def test_the_mapping_names_receipt_fields():
    paths = _paths()
    assert {"cache_key", "frame.a", "inputs.a.path", "created_utc", "status", "summary", "output.path",
            "cv2.build_sha256", "recipe.source_sha256"} <= set(paths)


def test_every_mapped_field_is_in_the_schema_and_in_a_real_receipt(tmp_path, capsys):
    rng = np.random.default_rng(4)
    base = rng.random((32, 48))
    for i in range(2):
        x = (np.clip(np.rint(np.roll(base, i, axis=1) * 255), 0, 255) / 255.0).astype(np.float32)
        with OpenEXR.File({"compression": OpenEXR.ZIP_COMPRESSION, "type": OpenEXR.scanlineimage}, {"Y": x}) as f:
            f.write(str(tmp_path / f"analysis.{1001 + i}.exr"))
    assert cli.main(["flow", "--in", str(tmp_path / "analysis.####.exr"), "--out", str(tmp_path),
                     "--frames", "1001-1001"]) == 0
    capsys.readouterr()
    data = json.loads((tmp_path / "flow.1001.json").read_text(encoding="utf-8"))
    for path in _paths():
        _schema_node(path)
        node = data
        for part in path.split("."):
            assert part in node, f"{path}: a real receipt has no {part}"
            node = node[part]
        assert node is not None or path in NULL_ALLOWED, f"{path} is null in a real receipt"
