# Sample data

This folder holds Green and NIR GeoTIFFs. The app looks for the bundled
sample first (`sample_green.tif` + `sample_nir.tif`); if those aren't
present you can always upload your own via the sidebar.

## Three ways to get sample data

### 1. Use the bundled sample (easiest)

The repo ships with a ~11 km × 11 km crop of Sentinel-2 imagery over
the **west shore of Lake Tahoe, California** (scene date 2025-09-27,
~0.4% cloud cover). Files:

- `sample_green.tif` — Sentinel-2 Band 3 (Green)
- `sample_nir.tif`   — Sentinel-2 Band 8 (NIR)

Pulled directly from the public **AWS Open Data** Sentinel-2 COG bucket,
no authentication needed. When you open `streamlit run app.py` and pick
**"Use bundled sample"** in the sidebar, this is what loads.

Good starting parameters: bandwidth 0.5, downsample factor 6, min-mean-NDWI 0.0.

### 2. Google Earth Engine (tutor-recommended)

Run the helper script once you've set up GEE:

```bash
earthengine authenticate          # one-time browser flow
python scripts/fetch_from_gee.py --bbox "72.8,19.0,72.9,19.1" \
                                 --start 2024-01-01 \
                                 --end   2024-03-31 \
                                 --out   data/samples/
```

### 3. Manual download

- **Copernicus Browser** — https://browser.dataspace.copernicus.eu/
  Find a Sentinel-2 L2A scene over your area of interest, download the
  product, then extract `*_B03_10m.jp2` (Green) and `*_B08_10m.jp2` (NIR).
  Convert to GeoTIFF if needed (`gdal_translate`), rename to
  `green.tif` / `nir.tif`, and drop them here.

- **USGS Earth Explorer** — https://earthexplorer.usgs.gov/
  Useful if you want Landsat-8/9 instead of Sentinel-2. For Landsat,
  Green is Band 3 and NIR is Band 5.

## Why these files are gitignored

GeoTIFFs are often 10–100 MB each. Committing them would bloat the repo.
If you need to share a specific scene with a teammate, use a shared
Google Drive / OneDrive link instead.
