"""postprocess.py — clean up the water mask.

[OURS] Raw segmentation often produces tiny spurious water blobs — a
few scattered pixels that happen to land in a water-ish cluster due to
sensor noise, cloud shadow, or a wet rooftop. This module removes any
connected blob smaller than a user-configurable pixel count and reports
stats (pixel count and physical area in km^2) for every surviving blob.

For connected-components labelling we call scipy.ndimage.label. That
is a well-known standard helper and sits in the same "plumbing"
category as numpy — we're not going to reinvent flood-fill.
"""

from typing import Dict, List, Tuple

import numpy as np
from scipy.ndimage import label   # [PLUMBING] — connected-components


def clean(
    mask: np.ndarray,
    min_blob_pixels: int = 50,
    pixel_size_m: float = 10.0,
) -> Tuple[np.ndarray, List[Dict]]:
    """Drop tiny blobs and report stats on the surviving ones.

    Parameters
    ----------
    mask : np.ndarray, shape (H, W), dtype bool
        Raw water mask from water_select.pick_water().
    min_blob_pixels : int
        Any connected component smaller than this is discarded. At
        10 m/pixel, 50 pixels is roughly 0.005 km^2 — a sensible
        "ignore noise" threshold for most Sentinel-2 scenes.
    pixel_size_m : float
        Ground size of one pixel in metres. Used only to convert
        pixel counts into km^2 for the stats. Default 10.0 matches
        Sentinel-2 Green/NIR bands.

    Returns
    -------
    clean_mask : np.ndarray, shape (H, W), dtype bool
        The mask with small blobs removed.
    blob_info : list of dicts, one per surviving blob
        Keys: "id" (0-based), "area_px" (int), "area_km2" (float).
    """
    # scipy.ndimage.label groups connected True pixels into components.
    # Default 4-connectivity (up/down/left/right — diagonals not linked)
    # is the standard choice for raster water-body extraction. `labeled`
    # is an int array where each blob has a unique positive id; 0 is
    # background.
    labeled, n_blobs = label(mask)

    clean_mask = np.zeros_like(mask, dtype=bool)
    blob_info: List[Dict] = []

    # Area of one pixel, in km^2 (for the reported stats).
    # (pixel_size_m metres)^2 gives m^2; divide by 1_000_000 for km^2.
    px_area_km2 = (pixel_size_m ** 2) / 1_000_000.0

    next_clean_id = 0
    for raw_id in range(1, n_blobs + 1):
        this_blob = labeled == raw_id
        area_px = int(this_blob.sum())

        # Skip blobs below the size threshold — leave their pixels False.
        if area_px < min_blob_pixels:
            continue

        # Blob survives — OR it into the clean mask and record its stats.
        clean_mask |= this_blob
        blob_info.append({
            "id": next_clean_id,
            "area_px": area_px,
            "area_km2": round(area_px * px_area_km2, 6),
        })
        next_clean_id += 1

    return clean_mask, blob_info
