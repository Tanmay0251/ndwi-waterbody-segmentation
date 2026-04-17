"""Sanity tests for waterbody/postprocess.py."""

import numpy as np

from waterbody.postprocess import clean


def test_clean_drops_small_blob_keeps_large_one():
    # 10x10 mask with two blobs: a 4-pixel tiny one and a 25-pixel big one.
    mask = np.zeros((10, 10), dtype=bool)
    mask[0:2, 0:2] = True           # 2x2 = 4 pixels — small
    mask[3:8, 3:8] = True           # 5x5 = 25 pixels — big

    cleaned, info = clean(mask, min_blob_pixels=10, pixel_size_m=10.0)

    # Large blob survives, small one is gone.
    assert cleaned[3:8, 3:8].all()
    assert not cleaned[0:2, 0:2].any()

    assert len(info) == 1
    assert info[0]["id"] == 0
    assert info[0]["area_px"] == 25


def test_clean_preserves_shape_and_bool_dtype():
    mask = np.zeros((7, 9), dtype=bool)
    mask[2:5, 2:5] = True
    cleaned, _ = clean(mask, min_blob_pixels=1)
    assert cleaned.shape == mask.shape
    assert cleaned.dtype == bool


def test_clean_handles_empty_mask():
    mask = np.zeros((5, 5), dtype=bool)
    cleaned, info = clean(mask)
    assert not cleaned.any()
    assert info == []


def test_clean_area_km2_calculation_matches_pixel_size():
    # 4 pixels at 10 m/px: 4 * 100 m^2 = 400 m^2 = 0.0004 km^2.
    mask = np.zeros((5, 5), dtype=bool)
    mask[0:2, 0:2] = True
    _, info = clean(mask, min_blob_pixels=1, pixel_size_m=10.0)
    assert abs(info[0]["area_km2"] - 0.0004) < 1e-6


def test_clean_keeps_all_blobs_when_threshold_is_one():
    # Three tiny blobs, each 1 pixel.
    mask = np.zeros((5, 5), dtype=bool)
    mask[0, 0] = True
    mask[2, 2] = True
    mask[4, 4] = True
    cleaned, info = clean(mask, min_blob_pixels=1)
    assert cleaned.sum() == 3
    assert len(info) == 3
    # Ids should be assigned 0, 1, 2 in order.
    assert [b["id"] for b in info] == [0, 1, 2]
