"""Tests of the contract module. tests/unit/ is yours: add a test file per mission here, never in tests/thresholds/."""
import numpy as np
import pytest

from cvcops import contract as c


def test_pair_must_be_8bit_single_channel_same_size():
    a = np.zeros((4, 6), np.uint8)
    c.check_analysis_pair(a, a.copy())
    with pytest.raises(c.ContractError):
        c.check_analysis_pair(a.astype(np.float32), a)
    with pytest.raises(c.ContractError):
        c.check_analysis_pair(np.zeros((4, 6, 3), np.uint8), a)
    with pytest.raises(c.ContractError, match="nothing resizes"):
        c.check_analysis_pair(a, np.zeros((4, 7), np.uint8))


def test_flow_shape_and_type():
    c.check_flow(np.zeros((4, 6, 2), np.float32), (4, 6))
    with pytest.raises(c.ContractError):
        c.check_flow(np.zeros((4, 6, 2), np.float64), (4, 6))


def test_analysis_stats_warns_on_clipping_and_few_levels():
    clipped = np.full((10, 10), 255, np.uint8)
    share, levels, warnings = c.analysis_stats(clipped)
    assert share == 1.0 and levels == 1 and len(warnings) == 2
    healthy = np.arange(256, dtype=np.uint8)[None, 1:-1].repeat(4, 0)
    assert c.analysis_stats(healthy)[2] == []


def test_frame_pairs_need_one_extra_frame():
    assert c.frame_pairs(1001, 1003) == [(1001, 1002), (1002, 1003), (1003, 1004)]
    with pytest.raises(c.ContractError):
        c.frame_pairs(1003, 1001)


def test_cache_key_changes_with_every_part_and_rejects_unknown_backends():
    base = (["a" * 64, "b" * 64], "p" * 64, "r" * 64, "cpu", "5.0.0", "h" * 64)
    k = c.cache_key(*base)
    assert len(k) == 64
    for i in range(1, len(base)):
        changed = list(base)
        changed[i] = "cuda" if i == 3 else ("x" * 64 if isinstance(base[i], str) else ["c" * 64, "b" * 64])
        assert c.cache_key(*changed) != k
    assert c.cache_key(*base, contract="flow-contract-v2") != k
    with pytest.raises(c.ContractError):
        c.cache_key(*base[:3], "vulkan", *base[4:])


def test_param_digest_ignores_key_order():
    assert c.param_digest({"a": 1, "b": 2.0}) == c.param_digest({"b": 2.0, "a": 1})
