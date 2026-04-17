# Sample data

Drop your Green-band and NIR-band GeoTIFFs in this folder — the app will
pick them up when you select **"Use sample scene"** in the sidebar.

Expected filenames:

- `green.tif` — Sentinel-2 Band 3 (Green, 10 m resolution) or equivalent
- `nir.tif`   — Sentinel-2 Band 8 (NIR, 10 m resolution) or equivalent

Both files must cover the same geographic extent and have the same
pixel size / CRS.

## Three ways to get sample data

### 1. Use what's bundled

One or two small crops (about 512 × 512 pixels each) will eventually be
committed here for out-of-the-box demos. For now this folder is empty.

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
