"""io_raster.py — load Green and NIR GeoTIFFs.

[PLUMBING] This module wraps rasterio. It is NOT part of the "method"
we defend in the viva — rasterio handles the GeoTIFF binary format,
projection info, nodata masks, and all the other raster bookkeeping.
We just call .open() and read the pixel array out.
"""

from typing import Tuple

import numpy as np
import rasterio


def load_bands(green_path: str, nir_path: str) -> Tuple[np.ndarray, np.ndarray, dict]:
    """Read Green and NIR single-band GeoTIFFs from disk.

    Parameters
    ----------
    green_path, nir_path : str or Path
        Paths to single-band GeoTIFF files. Both must cover the same
        pixels (same extent, CRS, and pixel size).

    Returns
    -------
    green, nir : np.ndarray, shape (H, W), dtype float32
    meta : dict
        Rasterio metadata (CRS, geotransform, pixel size, etc.) from the
        Green file. We keep it around so that when we save the water
        mask at the end, it comes out georeferenced — i.e., it lines up
        correctly if you drop it on a basemap in QGIS.
    """
    # rasterio's .read(1) returns the first band as a 2-D array.
    # (Using .read() without an index would give (bands, H, W), but our
    # inputs are single-band so we grab band 1 directly.)
    with rasterio.open(green_path) as g_src:
        green = g_src.read(1).astype(np.float32)
        meta = g_src.meta.copy()

    with rasterio.open(nir_path) as n_src:
        nir = n_src.read(1).astype(np.float32)

    # Guard against the most common user mistake: uploading two rasters
    # of different sizes. The error message here is deliberately clear
    # because users will see it in the Streamlit UI.
    if green.shape != nir.shape:
        raise ValueError(
            f"Green and NIR images have different shapes "
            f"({green.shape} vs {nir.shape}). "
            f"They must cover the exact same pixels."
        )

    return green, nir, meta
