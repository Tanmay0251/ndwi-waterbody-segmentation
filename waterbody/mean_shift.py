"""mean_shift.py — Mean-Shift segmentation, written from scratch.

[OURS] This is the heart of the project. Every line of the algorithm
below is our own implementation. We deliberately do NOT call
sklearn.cluster.MeanShift or cv2.pyrMeanShiftFiltering.

Intuition
---------
Treat every pixel of the 3-band (Green, NIR, NDWI) image as a point in
a 3-D feature space. For each point, look at its neighbours within a
radius called the *bandwidth*, compute a weighted mean of those
neighbours, and shift the point toward the mean. Repeat until the shift
gets tiny. Points in dense regions of the feature space all drift
toward the same local peak (called a "mode"). Points that end up at
the same mode belong to the same cluster.

Water pixels share a similar (Green, NIR, NDWI) signature, so they
converge to the same mode and form one cluster — that is how the
algorithm "finds" water without being told what water is.

Speed note
----------
We use scipy.spatial.cKDTree for fast neighbour lookup. That is a
standard data structure in the same "plumbing" category as numpy — the
algorithm logic (the shift loop, weight formula, convergence check,
mode merging) is all ours.

For large images (e.g., 512x512 = 262k pixels) this will take tens of
seconds because the outer loop runs once per pixel. The UI shows a
progress bar while it runs.
"""

from typing import Callable, Optional

import numpy as np
from scipy.spatial import cKDTree   # [PLUMBING] — neighbour-search data structure


def segment(
    img3: np.ndarray,
    bandwidth: float,
    kernel: str = "gaussian",
    max_iter: int = 100,
    eps: float = 1e-3,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> np.ndarray:
    """Cluster every pixel of a 3-band image using Mean-Shift.

    Parameters
    ----------
    img3 : np.ndarray, shape (H, W, 3)
        The 3-band image (Green, NIR, NDWI) from ndwi.stack_bands.
    bandwidth : float
        Radius (in z-score-normalised feature space) within which
        neighbours contribute to the shift. This is THE knob of
        Mean-Shift — small values produce many tight clusters, large
        values produce few broad ones. Typical useful range 0.1 to 1.0.
    kernel : {"gaussian", "flat"}
        Gaussian weights distant neighbours less than close ones; flat
        treats all neighbours within the window equally. Gaussian is
        smoother and is our default.
    max_iter : int
        Safety cap on shift iterations per point. Rarely hit — most
        points converge in well under 20 iterations.
    eps : float
        Convergence threshold. If a shift moves the point by less than
        this (in normalised-feature units), we stop iterating that point.
    progress_cb : callable or None
        Optional callback of the form `progress_cb(i_done, n_total)`.
        Called periodically so a UI can draw a progress bar.

    Returns
    -------
    labels : np.ndarray, shape (H, W), dtype int32
        Each pixel is assigned a cluster id in [0, K-1].
    """
    if bandwidth <= 0:
        raise ValueError("bandwidth must be positive")
    if kernel not in {"gaussian", "flat"}:
        raise ValueError(f"unknown kernel: {kernel!r}. Use 'gaussian' or 'flat'.")

    H, W, C = img3.shape
    if C != 3:
        raise ValueError(f"segment() expects a 3-band image, got shape {img3.shape}")

    # ------------------------------------------------------------------
    # Step 1. Flatten the image into a point cloud.
    # ------------------------------------------------------------------
    # Each pixel becomes one 3-D point. The (H, W) grid layout is
    # discarded here and restored at the very end by reshape.
    points = img3.reshape(H * W, 3).astype(np.float32)
    N = points.shape[0]

    # ------------------------------------------------------------------
    # Step 2. Z-score normalise each feature.
    # ------------------------------------------------------------------
    # Green and NIR are usually in [0, 1] but NDWI is in [-1, 1] with
    # its own spread. If we skipped this step, the bandwidth would mean
    # different things along each axis — the neighbourhood would be an
    # ellipsoid instead of a sphere. Subtracting the mean and dividing
    # by the standard deviation puts all three features on the same
    # scale, so bandwidth becomes isotropic.
    mean = points.mean(axis=0)
    std = points.std(axis=0) + 1e-9  # +epsilon so we never divide by zero
    points_n = (points - mean) / std

    # ------------------------------------------------------------------
    # Step 3. Build a KD-tree over the normalised points.
    # ------------------------------------------------------------------
    # [PLUMBING] scipy.spatial.cKDTree. Without this, every iteration
    # would be O(N) (comparing the current point to all other points),
    # turning the whole algorithm into O(N^2 * iters). With a KD-tree,
    # each neighbour query is roughly O(log N).
    tree = cKDTree(points_n)

    # ------------------------------------------------------------------
    # Step 4. Shift every point toward the local density peak.
    # ------------------------------------------------------------------
    # This is the core loop. We walk through every point and repeatedly
    # nudge it toward the weighted mean of its neighbours until the nudge
    # gets smaller than eps.
    shifted = points_n.copy()
    for i in range(N):
        x = shifted[i].copy()

        for _ in range(max_iter):
            # Find indices of all points lying within `bandwidth` of x.
            neighbour_idx = tree.query_ball_point(x, r=bandwidth)
            neighbours = points_n[neighbour_idx]

            # No neighbours at all? Point is a singleton — leave it as is.
            if len(neighbours) == 0:
                break

            # Compute each neighbour's weight.
            if kernel == "gaussian":
                # Close neighbours count more; far neighbours count less.
                d2 = ((neighbours - x) ** 2).sum(axis=1)
                w = np.exp(-d2 / (2.0 * bandwidth ** 2))
            else:  # flat kernel
                # Every neighbour inside the window counts equally.
                w = np.ones(len(neighbours), dtype=np.float32)

            # Weighted mean of the neighbours. Broadcasting w[:, None]
            # to shape (k, 1) multiplies every neighbour row by its
            # scalar weight before we sum them.
            x_new = (w[:, None] * neighbours).sum(axis=0) / w.sum()

            # If the shift is tiny, the point has settled at a peak.
            if np.linalg.norm(x_new - x) < eps:
                x = x_new
                break
            x = x_new

        shifted[i] = x

        # Update the progress bar every so often (not every point — that
        # would slow us down and spam the UI).
        if progress_cb is not None and (i % 1024 == 0 or i == N - 1):
            progress_cb(i + 1, N)

    # ------------------------------------------------------------------
    # Step 5. Merge converged points into clusters.
    # ------------------------------------------------------------------
    # After the shift loop, points that landed essentially on top of
    # each other belong to the same cluster. "Essentially on top" means
    # within bandwidth/2 — a standard rule of thumb. We walk through the
    # shifted points and assign each either to an existing mode (cluster
    # centre) or, if none is close enough, as the representative of a
    # brand-new cluster.
    modes: list = []                       # list of 3-D mode locations
    labels = np.empty(N, dtype=np.int32)
    merge_radius = bandwidth / 2.0

    for i, p in enumerate(shifted):
        assigned = False
        for mode_idx, m in enumerate(modes):
            if np.linalg.norm(p - m) < merge_radius:
                labels[i] = mode_idx
                assigned = True
                break
        if not assigned:
            modes.append(p)
            labels[i] = len(modes) - 1

    # ------------------------------------------------------------------
    # Step 6. Reshape labels back into the image grid.
    # ------------------------------------------------------------------
    return labels.reshape(H, W)
