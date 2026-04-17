"""Sanity tests for waterbody/ndwi.py."""

import numpy as np
import pytest

from waterbody.ndwi import compute_ndwi, stack_bands


def test_compute_ndwi_matches_hand_calculated_values():
    # Four pixels with known-in-advance NDWI values.
    # Pixel 1: (0.3 - 0.1) / (0.3 + 0.1) =  0.5
    # Pixel 2: (0.5 - 0.5) / (0.5 + 0.5) =  0.0
    # Pixel 3: (0.1 - 0.8) / (0.1 + 0.8) = -0.777...
    # Pixel 4: (0.9 - 0.1) / (0.9 + 0.1) =  0.8
    green = np.array([[0.3, 0.5], [0.1, 0.9]], dtype=np.float32)
    nir = np.array([[0.1, 0.5], [0.8, 0.1]], dtype=np.float32)
    expected = np.array([[0.5, 0.0], [-7.0 / 9.0, 0.8]], dtype=np.float32)
    np.testing.assert_allclose(compute_ndwi(green, nir), expected, atol=1e-3)


def test_compute_ndwi_preserves_shape():
    g = np.random.rand(50, 60).astype(np.float32)
    n = np.random.rand(50, 60).astype(np.float32)
    assert compute_ndwi(g, n).shape == (50, 60)


def test_compute_ndwi_no_nan_when_both_bands_are_zero():
    # Outside the scene footprint, both bands are zero. The epsilon in
    # the denominator should keep the result finite.
    g = np.zeros((3, 3), dtype=np.float32)
    n = np.zeros((3, 3), dtype=np.float32)
    result = compute_ndwi(g, n)
    assert not np.isnan(result).any()
    assert np.isfinite(result).all()


def test_stack_bands_shape_and_channel_order():
    # Each channel gets a constant value so we can check placement.
    g = np.full((4, 5), 0.1, dtype=np.float32)
    n = np.full((4, 5), 0.2, dtype=np.float32)
    w = np.full((4, 5), 0.3, dtype=np.float32)
    out = stack_bands(g, n, w)

    assert out.shape == (4, 5, 3)
    assert np.all(out[:, :, 0] == 0.1), "channel 0 should be Green"
    assert np.all(out[:, :, 1] == 0.2), "channel 1 should be NIR"
    assert np.all(out[:, :, 2] == 0.3), "channel 2 should be NDWI"
