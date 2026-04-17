"""Sanity tests for waterbody/water_select.py."""

import numpy as np
import pytest

from waterbody.water_select import pick_water


def test_pick_water_selects_high_ndwi_cluster_only():
    # Two clusters, left (id=0) has low NDWI, right (id=1) has high NDWI.
    labels = np.array([[0, 0, 1, 1],
                       [0, 0, 1, 1]], dtype=np.int32)
    ndwi = np.array([[-0.3, -0.2, 0.5, 0.6],
                     [-0.1, -0.4, 0.7, 0.8]], dtype=np.float32)
    mask = pick_water(labels, ndwi, min_mean_ndwi=0.0)

    expected = np.array([[False, False, True, True],
                         [False, False, True, True]])
    assert np.array_equal(mask, expected)


def test_pick_water_returns_bool_array():
    labels = np.zeros((3, 3), dtype=np.int32)
    ndwi = np.ones((3, 3), dtype=np.float32)
    mask = pick_water(labels, ndwi)
    assert mask.dtype == bool
    assert mask.shape == (3, 3)


def test_pick_water_all_false_when_no_cluster_above_threshold():
    labels = np.array([[0, 0], [0, 0]], dtype=np.int32)
    ndwi = np.array([[-0.5, -0.4], [-0.6, -0.3]], dtype=np.float32)
    mask = pick_water(labels, ndwi, min_mean_ndwi=0.0)
    assert not mask.any()


def test_pick_water_selects_multiple_clusters_if_both_qualify():
    # Both clusters have high mean NDWI.
    labels = np.array([[0, 1], [0, 1]], dtype=np.int32)
    ndwi = np.array([[0.4, 0.8], [0.3, 0.7]], dtype=np.float32)
    mask = pick_water(labels, ndwi, min_mean_ndwi=0.0)
    assert mask.all()


def test_pick_water_raises_on_shape_mismatch():
    labels = np.zeros((3, 3), dtype=np.int32)
    ndwi = np.zeros((3, 4), dtype=np.float32)
    with pytest.raises(ValueError):
        pick_water(labels, ndwi)


def test_pick_water_respects_custom_threshold():
    # Cluster 0 has mean NDWI = 0.1. With threshold 0.0 it qualifies;
    # with threshold 0.2 it does not.
    labels = np.zeros((2, 2), dtype=np.int32)
    ndwi = np.array([[0.05, 0.1], [0.1, 0.15]], dtype=np.float32)

    assert pick_water(labels, ndwi, min_mean_ndwi=0.0).all()
    assert not pick_water(labels, ndwi, min_mean_ndwi=0.2).any()
