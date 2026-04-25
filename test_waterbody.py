"""Tests for waterbody.py — run with `pytest -q`."""

import numpy as np
import pytest

from waterbody import compute_ndwi, stack_bands, segment, pick_water, clean


# --- NDWI + stacking ---

def test_ndwi_matches_hand_calculated():
    g = np.array([[0.3, 0.5], [0.1, 0.9]], dtype=np.float32)
    n = np.array([[0.1, 0.5], [0.8, 0.1]], dtype=np.float32)
    expected = np.array([[0.5, 0.0], [-7/9, 0.8]], dtype=np.float32)
    np.testing.assert_allclose(compute_ndwi(g, n), expected, atol=1e-3)


def test_ndwi_no_nan_on_zero_pixels():
    z = np.zeros((3, 3), dtype=np.float32)
    assert not np.isnan(compute_ndwi(z, z)).any()


def test_stack_bands_shape_and_channel_order():
    g = np.full((4, 5), 0.1, dtype=np.float32)
    n = np.full((4, 5), 0.2, dtype=np.float32)
    w = np.full((4, 5), 0.3, dtype=np.float32)
    out = stack_bands(g, n, w)
    assert out.shape == (4, 5, 3)
    assert np.all(out[..., 0] == 0.1)
    assert np.all(out[..., 1] == 0.2)
    assert np.all(out[..., 2] == 0.3)


# --- Mean-Shift ---

def _two_blobs(shape=(10, 10), seed=0):
    rng = np.random.default_rng(seed)
    H, W = shape
    img = np.empty((H, W, 3), dtype=np.float32)
    img[:, :W//2]  = np.array([0.2, 0.6, -0.5]) + 0.02 * rng.standard_normal((H, W//2, 3))
    img[:, W//2:]  = np.array([0.6, 0.2,  0.5]) + 0.02 * rng.standard_normal((H, W - W//2, 3))
    return img.astype(np.float32)


def test_segment_two_blobs_gives_two_labels():
    labels = segment(_two_blobs((10, 10)), bandwidth=0.5)
    assert len(np.unique(labels)) == 2


def test_segment_preserves_shape():
    labels = segment(_two_blobs((8, 12)), bandwidth=0.5)
    assert labels.shape == (8, 12)


def test_segment_is_reproducible():
    img = _two_blobs((8, 8), seed=1)
    assert np.array_equal(segment(img, 0.5), segment(img, 0.5))


def test_segment_rejects_bad_bandwidth():
    img = np.zeros((5, 5, 3), dtype=np.float32)
    with pytest.raises(ValueError):
        segment(img, bandwidth=0)


def test_segment_rejects_non_3_band_input():
    img = np.zeros((5, 5, 4), dtype=np.float32)
    with pytest.raises(ValueError):
        segment(img, bandwidth=0.5)


# --- Water-cluster selection ---

def test_pick_water_selects_high_ndwi_cluster():
    labels = np.array([[0, 0, 1, 1], [0, 0, 1, 1]])
    ndwi = np.array([[-0.3, -0.2, 0.5, 0.6], [-0.1, -0.4, 0.7, 0.8]], dtype=np.float32)
    expected = np.array([[False, False, True, True], [False, False, True, True]])
    assert np.array_equal(pick_water(labels, ndwi), expected)


def test_pick_water_all_false_when_nothing_qualifies():
    labels = np.zeros((2, 2), dtype=np.int32)
    ndwi = np.full((2, 2), -0.5, dtype=np.float32)
    assert not pick_water(labels, ndwi).any()


def test_pick_water_shape_mismatch_raises():
    with pytest.raises(ValueError):
        pick_water(np.zeros((3, 3)), np.zeros((3, 4)))


# --- Blob cleanup ---

def test_clean_drops_small_blob_keeps_large():
    mask = np.zeros((10, 10), dtype=bool)
    mask[0:2, 0:2] = True         # 4 px (small)
    mask[3:8, 3:8] = True         # 25 px (big)
    cleaned, info = clean(mask, min_blob_pixels=10)
    assert cleaned[3:8, 3:8].all()
    assert not cleaned[0:2, 0:2].any()
    assert len(info) == 1
    assert info[0]["area_px"] == 25


def test_clean_empty_mask():
    cleaned, info = clean(np.zeros((5, 5), dtype=bool))
    assert not cleaned.any()
    assert info == []


def test_clean_km2_matches_pixel_size():
    # 4 px at 10 m -> 400 m^2 -> 0.0004 km^2
    mask = np.zeros((5, 5), dtype=bool)
    mask[0:2, 0:2] = True
    _, info = clean(mask, min_blob_pixels=1, pixel_size_m=10.0)
    assert abs(info[0]["area_km2"] - 0.0004) < 1e-6
