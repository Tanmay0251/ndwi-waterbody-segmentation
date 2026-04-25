# NDWI Water-Body Segmentation

Extract water bodies from satellite imagery using the **Normalized Difference
Water Index (NDWI)** and **Mean-Shift segmentation**.

> GNR Semester 8 — Problem Statement #6:
> *"Generate an NDWI image and make a 3-band image of Green, NIR, and NDWI
> components. Extract all water bodies from this 3-band image using the
> Mean-Shift segmentation algorithm."*

## Team

- Tanmay Mandaliya
- Rohan
- Pravesh Khaparde

## What the code does

Given a Green-band and a NIR-band GeoTIFF of the same scene, the pipeline:

1. Computes NDWI at every pixel: `NDWI = (Green − NIR) / (Green + NIR)`.
2. Stacks Green, NIR and NDWI into one 3-band image — every pixel is a
   point in 3-D feature space.
3. Runs **Mean-Shift** (written from scratch) on those points, grouping
   spectrally-similar pixels into clusters.
4. Picks the cluster(s) whose mean NDWI is above a threshold — those are water.
5. Drops tiny spurious blobs and reports each surviving blob's area in km².

A Streamlit UI wraps the whole pipeline so you can pick a bundled scene,
tweak the parameters, and see the result.

## What we wrote vs what comes from libraries

| File / function | Ours? | Library used |
|---|---|---|
| `compute_ndwi`, `stack_bands` | yes | `numpy` |
| `segment` (Mean-Shift) | **yes — the star** | `numpy`, `scipy.spatial.cKDTree` (fast neighbour lookup) |
| `pick_water` | yes | `numpy` |
| `clean` | yes | `numpy`, `scipy.ndimage.label` (connected components) |
| `load_bands` | plumbing | `rasterio` |
| `app.py` | plumbing | `streamlit`, `matplotlib` |

We deliberately do **not** call `sklearn.cluster.MeanShift` or
`cv2.pyrMeanShiftFiltering` — those would skip the interesting part.

## Quick start

```bash
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # macOS / Linux

pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`. Pick a scene from the dropdown,
tweak the bandwidth slider, click **Run**.

## Project layout

```
.
├── app.py                # Streamlit UI
├── waterbody.py          # Core functions (NDWI, Mean-Shift, water selection, cleanup)
├── test_waterbody.py     # pytest sanity tests
├── data/samples/         # Bundled Green + NIR pairs from Sentinel-2
└── requirements.txt
```

Three Python files, no sub-packages. Each file has one clear job.

## Bundled sample scenes

`data/samples/` ships with ~10 Sentinel-2 crops covering different kinds of
water bodies (mountain lake, river delta, coastline, reservoir, etc.) so the
UI works out of the box without any data-hunting. All pulled from AWS's public
Sentinel-2 COG bucket — no auth needed to regenerate.

Filename pattern: `<place>_green.tif` and `<place>_nir.tif`. Drop your own
pair in using the same pattern and it'll show up in the dropdown.

## Running the tests

```bash
pytest -q
```

## Documentation for teammates

The `docs/` folder has a longer write-up of the project and a slide deck:

- `docs/project_overview.pdf` — full explanation of NDWI, Mean-Shift, the
  pipeline, hyperparameters, UI, and data sources. ~12 pages.
- `docs/project_presentation.pptx` — a 10-slide deck for the class presentation.
- `docs/project_overview.md` — the markdown source the PDF is built from.
- `docs/make_figures.py`, `docs/make_pdf.py`, `docs/make_pptx.py` — scripts that
  regenerate the figures, PDF, and slides if any of the content changes.
