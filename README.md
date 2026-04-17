# NDWI Water-Body Segmentation

Extract water bodies from satellite imagery using the **Normalized Difference Water Index (NDWI)** and **Mean-Shift segmentation**.

> GNR Semester 8 course project.
> Problem statement #6 — *"Generate an NDWI image and make a 3-band image of Green, NIR, and NDWI components. Extract all water bodies from this 3-band image using the Mean-Shift segmentation algorithm."*

## Team

- Tanmay Mandaliya
- Rohan
- Pravesh Khaparde

## What this project does (in one paragraph)

Given two single-band GeoTIFFs — one for the Green band and one for the Near-Infrared (NIR) band — the tool:

1. Computes NDWI at every pixel: `NDWI = (Green − NIR) / (Green + NIR)`
2. Stacks Green, NIR, and NDWI into one 3-band image — each pixel becomes a point in a 3-D feature space.
3. Runs a from-scratch Mean-Shift segmentation on those points, clustering spectrally-similar pixels together.
4. Picks the cluster(s) whose mean NDWI is above a threshold — those are water.
5. Cleans up the mask by removing tiny blobs and exports the result as a PNG and a georeferenced GeoTIFF.

A Streamlit UI wraps the whole pipeline so a user can upload their own data, tweak parameters with sliders, and see results instantly.

## What's ours vs what's a library (important for the viva)

| Module | Status | Uses |
|---|---|---|
| `waterbody/ndwi.py` | **Ours** (NumPy math) | `numpy` |
| `waterbody/mean_shift.py` | **Ours** — the core algorithm | `numpy`, `scipy.spatial.cKDTree` (neighbour-search data structure) |
| `waterbody/water_select.py` | **Ours** (label-based cluster selection) | `numpy` |
| `waterbody/postprocess.py` | **Ours** (blob-area filtering) | `numpy`, `scipy.ndimage.label` (standard connected-components) |
| `waterbody/io_raster.py` | Plumbing | `rasterio` (GeoTIFF reader/writer) |
| `app.py` | Plumbing | `streamlit` (UI), `matplotlib`, `PIL` |
| `scripts/fetch_from_gee.py` | Plumbing (optional) | `earthengine-api` |

The rubric asks us to distinguish our implementation from external packages — this table is the answer. No `sklearn.cluster.MeanShift`, no `cv2.pyrMeanShiftFiltering`.

## Quick start

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Put a pair of Green + NIR GeoTIFFs in data/samples/
#    (see data/samples/README.md for how to obtain them)

# 4. Launch the UI
streamlit run app.py
```

The app opens in your browser at `http://localhost:8501`. Upload the two GeoTIFFs in the sidebar, tweak the bandwidth slider, and click **Run Pipeline**.

## Data sources

Three documented paths to obtain Green + NIR bands (see `data/samples/README.md` for details):

1. **Bundled sample** — a small Sentinel-2 crop included in `data/samples/`. Works out of the box.
2. **Google Earth Engine** — run `python scripts/fetch_from_gee.py` for fresh data anywhere in the world (one-time `earthengine authenticate` setup).
3. **Manual download** — Copernicus Browser or USGS Earth Explorer.

## Project layout

```
.
├── app.py                  # Streamlit UI entry point
├── waterbody/              # core package (our implementation)
│   ├── io_raster.py        # Load GeoTIFFs (rasterio plumbing)
│   ├── ndwi.py             # NDWI formula + 3-band stacking
│   ├── mean_shift.py       # Mean-Shift from scratch — the heart
│   ├── water_select.py     # Pick which cluster(s) are water
│   └── postprocess.py      # Blob cleanup
├── scripts/
│   └── fetch_from_gee.py   # Optional GEE data helper
├── tests/                  # Pytest sanity tests
├── docs/
│   └── design.md           # Full design document
├── data/samples/           # Sample GeoTIFFs (not committed — see README)
└── requirements.txt
```

## Design document

Full design — architecture, data flow, algorithm walk-through, UI wireframe — is in [`docs/design.md`](docs/design.md). Start there if you want the complete picture before reading code.

## Running the tests

Pytest is already in `requirements.txt`, so once the venv is set up:

```bash
pytest -q
```

There are 22 tests covering every module except `io_raster.py` (which just
wraps rasterio) and `app.py` (UI — tested manually in the browser).

## Running end-to-end from the command line (no UI)

Handy for quickly checking the pipeline against a real GeoTIFF pair:

```bash
python scripts/run_end_to_end.py \
    --green data/samples/green.tif \
    --nir   data/samples/nir.tif \
    --bandwidth 0.3 \
    --downsample 4 \
    --out   data/samples/out_mask.png
```

## License

Course project, no license. Please don't copy for your own submission.
