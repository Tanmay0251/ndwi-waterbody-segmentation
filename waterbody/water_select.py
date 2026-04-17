"""water_select.py — turn cluster labels into a water mask.

[OURS] After Mean-Shift has grouped pixels into clusters, we still
need to decide which of those clusters is actually water. Our rule is
simple and honest: a cluster counts as water if the mean NDWI of its
pixels is above a user-configurable threshold (default 0.0). Multiple
clusters can qualify — useful when a scene contains both clear and
turbid water, which Mean-Shift may split into separate clusters.
"""

import numpy as np


def pick_water(
    labels: np.ndarray,
    ndwi: np.ndarray,
    min_mean_ndwi: float = 0.0,
) -> np.ndarray:
    """Build a boolean water mask from cluster labels and the NDWI image.

    Parameters
    ----------
    labels : np.ndarray, shape (H, W), dtype int
        Cluster id per pixel, as produced by mean_shift.segment().
    ndwi : np.ndarray, shape (H, W), dtype float
        The NDWI array from ndwi.compute_ndwi().
    min_mean_ndwi : float
        A cluster is considered water if its mean NDWI is strictly
        greater than this threshold. 0.0 is the classic rule-of-thumb
        boundary between water (NDWI > 0) and non-water (NDWI < 0).

    Returns
    -------
    mask : np.ndarray, shape (H, W), dtype bool
        True at pixels that belong to a water cluster.
    """
    if labels.shape != ndwi.shape:
        raise ValueError(
            f"labels shape {labels.shape} does not match ndwi shape {ndwi.shape}"
        )

    mask = np.zeros_like(labels, dtype=bool)

    # Walk through each cluster id once. For each, compute the average
    # NDWI of all pixels inside that cluster, and if that average clears
    # the threshold, mark every pixel of the cluster as water.
    for cluster_id in np.unique(labels):
        pixels_in_cluster = labels == cluster_id
        mean_ndwi_here = ndwi[pixels_in_cluster].mean()
        if mean_ndwi_here > min_mean_ndwi:
            mask[pixels_in_cluster] = True

    return mask
