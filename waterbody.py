"""All the algorithm code for the project lives here.

Six small functions:
    load_bands      read Green + NIR GeoTIFFs (rasterio plumbing)
    compute_ndwi    NDWI = (Green - NIR) / (Green + NIR), per pixel
    stack_bands     turn three (H, W) arrays into one (H, W, 3) image
    segment         Mean-Shift clustering written from scratch
    pick_water      pick clusters whose mean NDWI is above a threshold
    clean           drop tiny noisy blobs and return per-blob area in km^2

Only `segment` is the algorithm we defend in the viva. Everything else
is short glue code around it.
"""

import numpy as np
import rasterio
from scipy.spatial import cKDTree   # fast neighbour lookup, used inside segment()
from scipy.ndimage import label      # connected-component labelling, used inside clean()


def load_bands(green_path, nir_path):
    """Read two single-band GeoTIFFs and return (green, nir, meta)."""
    with rasterio.open(green_path) as g:
        green = g.read(1).astype(np.float32)
        meta = g.meta.copy()
    with rasterio.open(nir_path) as n:
        nir = n.read(1).astype(np.float32)
    if green.shape != nir.shape:
        raise ValueError(f"green and nir shapes differ: {green.shape} vs {nir.shape}")
    return green, nir, meta


def compute_ndwi(green, nir):
    """NDWI = (Green - NIR) / (Green + NIR). High values = water-like pixels."""
    return ((green - nir) / (green + nir + 1e-10)).astype(np.float32)


def stack_bands(green, nir, ndwi):
    """Stack the three 2-D bands into one (H, W, 3) image."""
    return np.stack([green, nir, ndwi], axis=-1).astype(np.float32)


def segment(img3, bandwidth, max_iter=100, eps=1e-3, progress_cb=None):
    """Mean-Shift on every pixel of a 3-band image. Returns an (H, W) label map.

    For each pixel (treated as a 3-D point in feature space), repeatedly shift it
    to the weighted mean of its neighbours inside `bandwidth` until the shift
    gets tiny. Points that converge to the same peak get the same cluster id.
    """
    if bandwidth <= 0:
        raise ValueError("bandwidth must be positive")
    H, W, C = img3.shape
    if C != 3:
        raise ValueError(f"expected a 3-band image, got shape {img3.shape}")

    # flatten to (N, 3) and z-score normalise so bandwidth is isotropic
    points = img3.reshape(H * W, 3).astype(np.float32)
    mean = points.mean(axis=0)
    std = points.std(axis=0) + 1e-9
    pts_n = (points - mean) / std
    N = pts_n.shape[0]

    # KD-tree for fast neighbour lookup
    tree = cKDTree(pts_n)

    # shift every point toward the local density peak
    shifted = pts_n.copy()
    for i in range(N):
        x = shifted[i].copy()
        for _ in range(max_iter):
            idx = tree.query_ball_point(x, r=bandwidth)
            nbrs = pts_n[idx]
            if len(nbrs) == 0:
                break
            # Gaussian weights: closer neighbours count more
            d2 = ((nbrs - x) ** 2).sum(axis=1)
            w = np.exp(-d2 / (2.0 * bandwidth ** 2))
            x_new = (w[:, None] * nbrs).sum(axis=0) / w.sum()
            if np.linalg.norm(x_new - x) < eps:
                x = x_new
                break
            x = x_new
        shifted[i] = x
        if progress_cb is not None and (i % 1024 == 0 or i == N - 1):
            progress_cb(i + 1, N)

    # merge points that converged to (almost) the same mode
    modes = []
    labels = np.empty(N, dtype=np.int32)
    merge_radius = bandwidth / 2.0
    for i, p in enumerate(shifted):
        for mode_idx, m in enumerate(modes):
            if np.linalg.norm(p - m) < merge_radius:
                labels[i] = mode_idx
                break
        else:
            modes.append(p)
            labels[i] = len(modes) - 1

    return labels.reshape(H, W)


def pick_water(labels, ndwi, min_mean_ndwi=0.0):
    """Mark every pixel of any cluster whose mean NDWI exceeds the threshold."""
    if labels.shape != ndwi.shape:
        raise ValueError(f"shape mismatch: {labels.shape} vs {ndwi.shape}")
    mask = np.zeros_like(labels, dtype=bool)
    for cid in np.unique(labels):
        in_cluster = labels == cid
        if ndwi[in_cluster].mean() > min_mean_ndwi:
            mask[in_cluster] = True
    return mask


def clean(mask, min_blob_pixels=50, pixel_size_m=10.0):
    """Drop connected blobs smaller than the threshold. Returns (clean_mask, info)."""
    labeled, n_blobs = label(mask)
    clean_mask = np.zeros_like(mask, dtype=bool)
    px_area_km2 = (pixel_size_m ** 2) / 1_000_000.0
    info = []
    new_id = 0
    for raw_id in range(1, n_blobs + 1):
        blob = labeled == raw_id
        area = int(blob.sum())
        if area < min_blob_pixels:
            continue
        clean_mask |= blob
        info.append({"id": new_id, "area_px": area, "area_km2": round(area * px_area_km2, 6)})
        new_id += 1
    return clean_mask, info
