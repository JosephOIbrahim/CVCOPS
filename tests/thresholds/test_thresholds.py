"""One test per row of the blueprint's threshold table. Locked.

Each test calls the same function evidence/thresholds_reference.py uses for that row, so the exam and its
reference cannot measure differently. tools/check.py chooses the rows (CVCOPS_ROWS) and the object graded
(CVCOPS_IMPL). Run bare, this file grades the product on the rung-1 rows of the missions in mission.txt.
"""
import os

import numpy as np
import pytest

import impls


def _selected():
    keys = os.environ.get("CVCOPS_ROWS")
    if keys == "all":
        return list(impls.ROWS)
    if keys is not None:
        wanted = {k for k in keys.split(",") if k}
        return [r for r in impls.ROWS if r["key"] in wanted]
    return impls.rows_for(impls.missions(), 1)


@pytest.mark.parametrize("row", _selected(), ids=lambda r: r["key"])
def test_row(row, impl, cache, record_property):
    value = impls.METRICS[row["key"]](impl, cache)
    value = bool(value) if isinstance(value, (bool, np.bool_)) else float(value)
    record_property("value", value)
    assert impls.verdict(row, value) == "PASS", (
        f"{row['mission']} {row['label']}: measured {value}, threshold {row['threshold']}")
