"""Mission 1's own tests: estimate_flow and validity on small ground-truth fixtures. The rows are in tests/thresholds/."""
import numpy as np
import pytest

from cvcops import contract as c
from cvcops.ops import flow as flow_mod
from cvcops.ops.flow import estimate_flow, recipe_source_sha256
from cvcops.ops.validity import forward_backward_valid, validity

H, W = 128, 192


def _texture(seed=3):
    """Band-limited periodic noise in 0..1, so an integer roll is an exact shift."""
    rng = np.random.default_rng(seed)
    spec = rng.normal(size=(H, W)) + 1j * rng.normal(size=(H, W))
    fy = np.fft.fftfreq(H)[:, None]
    fx = np.fft.fftfreq(W)[None, :]
    spec *= np.exp(-(np.sqrt(fx * fx + fy * fy) / 0.08) ** 2)
    img = np.fft.ifft2(spec).real
    return (img - img.min()) / (img.max() - img.min())


def _u8(img):
    return np.clip(np.rint(img * 255.0), 0, 255).astype(np.uint8)


@pytest.fixture(scope="module")
def pair():
    a = _texture()
    dx, dy = 3, -2                                      # content moves 3 px right and 2 px up
    return _u8(a), _u8(np.roll(a, (dy, dx), axis=(0, 1))), (dx, dy)


@pytest.mark.parametrize("recipe", c.RECIPES)
def test_flow_sign_direction_and_type(pair, recipe):
    a, b, (dx, dy) = pair
    f = estimate_flow(a, b, recipe)
    c.check_flow(f, a.shape)
    inner = f[24:-24, 24:-24]
    assert abs(float(inner[..., 0].mean()) - dx) < 0.2
    assert abs(float(inner[..., 1].mean()) - dy) < 0.2


def test_flow_is_repeatable(pair):
    a, b, _ = pair
    assert estimate_flow(a, b).tobytes() == estimate_flow(a, b).tobytes()


def test_flow_enforces_the_contract(pair):
    a, b, _ = pair
    with pytest.raises(c.ContractError):
        estimate_flow(a.astype(np.float32), b)
    with pytest.raises(c.ContractError, match="nothing resizes"):
        estimate_flow(a, b[:-1])
    with pytest.raises(c.ContractError, match="unknown recipe"):
        estimate_flow(a, b, "dis_ultrafast")


def test_every_recipe_has_a_distinct_stable_source_hash():
    hashes = [recipe_source_sha256(r) for r in c.RECIPES]
    assert all(len(h) == 64 for h in hashes) and len(set(hashes)) == len(hashes)
    assert hashes == [recipe_source_sha256(r) for r in c.RECIPES]
    with pytest.raises(c.ContractError):
        recipe_source_sha256("nope")


def test_patch_size_guard_reads_the_version():
    assert flow_mod._before_5_1("5.0.0") and flow_mod._before_5_1("4.13.0")
    assert not flow_mod._before_5_1("5.1.0") and not flow_mod._before_5_1("6.0.0")


def _uniform(dx, dy):
    f = np.zeros((H, W, 2), np.float32)
    f[..., 0], f[..., 1] = dx, dy
    return f


def test_consistent_flows_are_valid_where_the_destination_is_inside():
    v = forward_backward_valid(_uniform(5.0, -3.0), _uniform(-5.0, 3.0))
    assert v.dtype == bool and v.shape == (H, W)
    assert v[3:, : W - 5].all()                         # destination inside the frame
    assert not v[:3].any() and not v[:, W - 5:].any()   # destination above or right of the frame


def test_disagreeing_flows_are_invalid_and_tolerance_is_inclusive():
    fwd = _uniform(2.0, 0.0)
    assert not forward_backward_valid(fwd, _uniform(-0.5, 0.0), 1.0)[10:-10, 10:-10].any()
    assert forward_backward_valid(fwd, _uniform(-1.0, 0.0), 1.0)[10:-10, 10:-10].all()


def test_mask_on_a_grid_marks_pixels_invalid_and_leaves_the_rest():
    fwd, bwd = _uniform(0.0, 0.0), _uniform(0.0, 0.0)
    mask = np.ones((H, W), bool)
    mask[40:60, 50:90] = False
    v = forward_backward_valid(fwd, bwd, mask=mask)
    assert np.array_equal(v, mask)


def test_bad_tolerance_and_mask_are_refused(pair):
    a, b, _ = pair
    f = _uniform(0.0, 0.0)
    for tol in (-1.0, float("nan"), float("inf"), "1"):
        with pytest.raises(c.ContractError):
            forward_backward_valid(f, f, tol)
    with pytest.raises(c.ContractError):
        forward_backward_valid(f, f, mask=np.ones((H, W), np.uint8))
    with pytest.raises(c.ContractError):
        validity(a, b, mask=np.ones((H + 1, W), bool))
    with pytest.raises(c.ContractError):
        forward_backward_valid(f, f[:-1])


def test_validity_on_a_pure_shift(pair):
    a, b, (dx, dy) = pair
    v = validity(a, b)
    assert v.dtype == bool and v.shape == a.shape
    assert v[24:-24, 24:-24].mean() > 0.99
    assert not v[:, W - 2:].any()                       # 3 px right of the last columns is outside the frame
    mask = np.ones(a.shape, bool)
    mask[:, :W // 2] = False
    assert np.array_equal(validity(a, b, mask=mask), v & mask)
