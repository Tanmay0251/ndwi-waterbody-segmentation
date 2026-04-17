"""fetch_from_gee.py — optional Google Earth Engine downloader.

This is an OPTIONAL helper. The main Streamlit app does not need GEE.
Use this script only when you want to pull a fresh Sentinel-2 Green
(B3) + NIR (B8) pair for a specific place and time.

One-time setup
--------------
You need a (free) Google Cloud project with the Earth Engine API
enabled, and then a browser auth flow:

    pip install earthengine-api
    earthengine authenticate

If the auth command opens a browser and says "Welcome, <your name>",
you're good.

Usage
-----
    python scripts/fetch_from_gee.py \
        --bbox      72.80,19.00,72.90,19.10 \
        --start     2024-01-01 \
        --end       2024-03-31 \
        --out       data/samples/ \
        --max-cloud 20

Produces ``green.tif`` and ``nir.tif`` inside the --out folder.

Tips
----
* Keep the bounding box small (around 0.1 degrees = ~10 km). GEE's
  synchronous download endpoint has a size limit around 32 MB; wider
  bboxes fail with an opaque error.
* The script picks the LEAST CLOUDY image in the date range. Widen the
  date range if nothing is returned.
"""

import argparse
import sys
import urllib.request
from pathlib import Path

# Make the project root importable (not strictly needed here, but keeps
# the convention consistent with scripts/run_end_to_end.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _parse_bbox(text: str):
    """Parse 'lon_min,lat_min,lon_max,lat_max' into four floats."""
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        raise ValueError(
            "bbox must be exactly four numbers: lon_min,lat_min,lon_max,lat_max"
        )
    lon_min, lat_min, lon_max, lat_max = (float(p) for p in parts)
    if lon_min >= lon_max or lat_min >= lat_max:
        raise ValueError("bbox corners are not in the expected order")
    return lon_min, lat_min, lon_max, lat_max


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Sentinel-2 Green+NIR via GEE")
    parser.add_argument(
        "--bbox", required=True,
        help="'lon_min,lat_min,lon_max,lat_max' in decimal degrees (EPSG:4326)",
    )
    parser.add_argument("--start", required=True, help="start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="end date YYYY-MM-DD")
    parser.add_argument(
        "--out", default="data/samples/",
        help="folder where green.tif and nir.tif are written",
    )
    parser.add_argument(
        "--max-cloud", type=float, default=20.0,
        help="reject scenes with cloudy-pixel percentage above this",
    )
    args = parser.parse_args()

    # -- Lazy imports so users who never run this script don't need GEE --
    try:
        import ee
    except ImportError:
        print("earthengine-api is not installed. Install it first:")
        print("    pip install earthengine-api")
        sys.exit(1)

    # -- Authenticate & initialise -------------------------------------
    # ee.Initialize() reads the credentials written by
    # `earthengine authenticate`. If that never happened, we print a
    # friendly hint instead of a Python stack trace.
    try:
        ee.Initialize()
    except Exception as exc:
        print("Earth Engine is not initialised.")
        print("Run this once first (opens a browser):")
        print("    earthengine authenticate")
        print(f"(original error: {exc})")
        sys.exit(1)

    # -- Parse the bounding box ----------------------------------------
    lon_min, lat_min, lon_max, lat_max = _parse_bbox(args.bbox)
    region = ee.Geometry.Rectangle([lon_min, lat_min, lon_max, lat_max])

    # -- Find the least-cloudy Sentinel-2 scene in the date range ------
    # COPERNICUS/S2_SR_HARMONIZED is the surface-reflectance (L2A) product.
    print("Searching Sentinel-2 archive ...")
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(args.start, args.end)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", args.max_cloud))
        .sort("CLOUDY_PIXEL_PERCENTAGE")
    )

    n = collection.size().getInfo()
    if n == 0:
        print(
            "No scenes match. Try widening the date range "
            "or raising --max-cloud."
        )
        sys.exit(1)

    image = ee.Image(collection.first())
    info = image.getInfo()["properties"]
    print(
        f"Picked scene from {info.get('DATE_ACQUIRED')} "
        f"with cloud cover {info.get('CLOUDY_PIXEL_PERCENTAGE'):.1f}%"
    )

    # -- Download Green (B3) and NIR (B8) ------------------------------
    # getDownloadURL returns a URL for a GeoTIFF clipped to our region.
    # Scale=10 matches Sentinel-2's native 10 m pixel size for these bands.
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    band_to_filename = [("B3", "green.tif"), ("B8", "nir.tif")]
    for band, filename in band_to_filename:
        print(f"Downloading {band} -> {filename} ...")
        url = image.select(band).getDownloadURL({
            "scale": 10,
            "region": region,
            "format": "GEO_TIFF",
            "crs": "EPSG:4326",
        })
        dest = out_dir / filename
        urllib.request.urlretrieve(url, str(dest))
        size_kb = dest.stat().st_size / 1024
        print(f"  saved {dest} ({size_kb:.1f} KB)")

    print("Done. Fire up the UI with:  streamlit run app.py")


if __name__ == "__main__":
    main()
