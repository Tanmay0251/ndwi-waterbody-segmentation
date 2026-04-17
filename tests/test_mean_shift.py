"""Sanity tests for waterbody/mean_shift.py."""

import numpy as np
import pytest

from waterbody.mean_shift import segment


def _two_blob_image(shape=(10, 10), seed=0):
    """Build a (H, W, 3) image whose pixels form two clean clusters.

    Left half of the image has one spectral signature, right half has
    a very different one. Mean-Shift should find these as two clusters.
    """
    rng = np.random.default_rng(seed)
    H, W = shape
    img = np.empty((H, W, 3), dtype=np.float32)

    # Left half: roughly (Green=0.2, NIR=0.6, NDWI=-0.5) — vegetation-ish
    left_centre = np.array([0.2, 0.6, -0.5], dtype=np.float32)
    img[:, : W // 2] = left_centre + 0.02 * rng.standard_normal((H, W // 2, 3)).astype(np.float32)

    # Right half: roughly (Green=0.6, NIR=0.2, NDWI=+0.5) — water-ish
    right_centre = np.array([0.6, 0.2, 0.5], dtype=np.float32)
    img[:, W // 2 :] = right_centre + 0.02 * rng.standard_normal((H, W - W // 2, 3)).astype(np.float32)

    return img


def test_segment_two_blobs_returns_exactly_two_labels():
    img = _two_blob_image(shape=(10, 10))
    labels = segment(img, bandwidth=0.5)
    unique = np.unique(labels)
    assert len(unique) == 2, f"expected 2 clusters, got {len(unique)}: {unique}"


def test_segment_preserves_shape():
    img = _two_blob_image(shape=(8, 12))
    labels = segment(img, bandwidth=0.5)
    assert labels.shape == (8, 12)


def test_segment_is_reproducible():
    # Same input + same bandwidth should always give identical labels.
    img = _two_blob_image(shape=(8, 8), seed=1)
    a = segment(img, bandwidth=0.5)
    b = segment(img, bandwidth=0.5)
    assert np.array_equal(a, b)


def test_segment_rejects_nonpositive_bandwidth():
    img = np.zeros((5, 5, 3), dtype=np.float32)
    with pytest.raises(ValueError):
        segment(img, bandwidth=0.0)
    with pytest.raises(ValueError):
        segment(img, bandwidth=-0.1)


def test_segment_rejects_unknown_kernel():
    img = np.zeros((5, 5, 3), dtype=np.float32)
    with pytest.raises(ValueError):
        segment(img, bandwidth=0.5, kernel="elliptic")


def test_segment_rejects_non_3_band_input():
    img = np.zeros((5, 5, 4), dtype=np.float32)
    with pytest.raises(ValueError):
        segment(img, bandwidth=0.5)


def test_segment_flat_kernel_also_works():
    img = _two_blob_image(shape=(8, 8))
    labels = segment(img, bandwidth=0.5, kernel="flat")
    assert len(np.unique(labels)) == 2
