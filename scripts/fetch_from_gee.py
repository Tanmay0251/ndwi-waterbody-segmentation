"""fetch_from_gee.py — optional Google Earth Engine downloader.

This is a CLI utility, NOT part of the main app. Use it to pull a fresh
Sentinel-2 Green (B3) + NIR (B8) pair for any location and date range.

First-time setup (one command, opens a browser):
    earthengine authenticate

Usage:
    python scripts/fetch_from_gee.py \
        --bbox "72.8,19.0,72.9,19.1"   (min_lon, min_lat, max_lon, max_lat) \
        --start 2024-01-01 \
        --end   2024-03-31 \
        --out   data/samples/

Produces:
    data/samples/green.tif  and  data/samples/nir.tif
"""

# TODO: implement CLI + GEE download logic
