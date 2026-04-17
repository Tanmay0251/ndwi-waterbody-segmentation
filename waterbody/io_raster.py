"""io_raster.py — load Green and NIR GeoTIFFs.

[PLUMBING] This module wraps rasterio. It is NOT part of the "method" we
defend in the viva — rasterio handles all the GeoTIFF parsing, projection,
and metadata bookkeeping for us. We just call .open() and read the array.

Exposes:
    load_bands(green_path, nir_path) -> (green, nir, meta)
"""

# TODO: implement load_bands
