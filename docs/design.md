# Project notes — NDWI Water-Body Segmentation

*GNR Semester 8 — Problem Statement #6:*

> *"Generate an NDWI image and make a 3-band image of Green, NIR, and NDWI
> components. Extract all water bodies from this 3-band image using the
> Mean-Shift segmentation algorithm."*

These notes walk through the whole project — the problem, the algorithm,
how the code is laid out, and how data flows through it. A good starting
point for anyone on the team before opening the source files.

## 1. Problem statement in plain words

We need to find water bodies in satellite imagery. The assignment gives
us two hints:

1. **Use NDWI** — the Normalized Difference Water Index. Water reflects
   visible Green strongly and absorbs Near-Infrared (NIR) strongly, so
   the ratio `(Green − NIR) / (Green + NIR)` is high for water and low
   for everything else.
2. **Stack Green + NIR + NDWI into one 3-band image** — then every
   pixel is a 3-D point, not just a scalar NDWI value.
3. **Run Mean-Shift on that 3-band image** — an unsupervised clustering
   algorithm that will group spectrally-similar pixels together.

The output is a binary mask (one pixel per image pixel, `True` where
there is water, `False` elsewhere), plus some stats and a visual
overlay.

## 2. Why this is easier than it looks

- **No training needed.** NDWI is a formula; Mean-Shift is unsupervised.
  No labels, no training data, no model weights, no train/test splits.
- **No GPU needed.** Pure CPU, single-threaded NumPy + SciPy.
- **No external API at runtime.** The app is fully offline once the
  GeoTIFFs are on disk.

## 3. What we wrote vs what comes from libraries

The course rubric cares about this a lot, so here is the honest split:

| Category | What we do ourselves | What we delegate to libraries |
|---|---|---|
| **Algorithm** | NDWI formula, Mean-Shift loop, mode merging, water-cluster selection, blob-size filtering | — |
| **Data plumbing** | — | GeoTIFF parsing (`rasterio`), array math primitives (`numpy`), KD-tree neighbour lookup (`scipy.spatial.cKDTree`), connected-components (`scipy.ndimage.label`), UI (`streamlit`), plotting (`matplotlib`, `PIL`) |

Libraries we deliberately **do not** use:

- `sklearn.cluster.MeanShift` — would trivialise the whole project.
- `cv2.pyrMeanShiftFiltering` — same.

## 4. Architecture (file layout)

```
.
├── app.py                      # Streamlit UI entry point
├── waterbody/                  # our core package (the "method")
│   ├── __init__.py
│   ├── io_raster.py            # [PLUMBING] load Green + NIR GeoTIFFs via rasterio
│   ├── ndwi.py                 # [OURS] NDWI formula + 3-band stacking
│   ├── mean_shift.py           # [OURS] Mean-Shift from scratch — the heart
│   ├── water_select.py         # [OURS] pick which cluster(s) are water
│   └── postprocess.py          # [OURS] drop tiny blobs
├── scripts/
│   └── fetch_from_gee.py       # optional Google Earth Engine data helper
├── tests/                      # pytest sanity tests
├── docs/
│   └── design.md               # this document
├── data/samples/               # place GeoTIFFs here (gitignored)
└── requirements.txt
```

Each `[OURS]` module is small (about 50–150 lines) so that any teammate
can read one file end-to-end in half an hour and be ready to explain it
in the viva.

### Natural study split for the three of us (for viva, not ownership)

- **Person 1** — `ndwi.py` + `io_raster.py` (data loading + index math)
- **Person 2** — `mean_shift.py` (the algorithm itself — the big one)
- **Person 3** — `water_select.py` + `postprocess.py` + `app.py`
  (cluster selection, cleanup, UI)

## 5. Data flow

```
USER in Streamlit
    │   uploads: green.tif, nir.tif
    │   sets:    bandwidth, scope-mode, crop-rect OR downsample-factor
    ▼
[1] io_raster.load_bands(...)         [PLUMBING]
    -> green (H, W) float32
    -> nir   (H, W) float32
    -> meta  dict with CRS + geotransform (used later for GeoTIFF export)
    ▼
[2] apply scope choice (in app.py):
        crop       -> green[r1:r2, c1:c2], nir[r1:r2, c1:c2]
        downsample -> green[::k, ::k],     nir[::k, ::k]
    -> (h, w) pair, typically 512x512
    ▼
[3] ndwi.compute_ndwi(green, nir)      [OURS]
    -> ndwi  (h, w) float32 in [-1, 1]

    ndwi.stack_bands(green, nir, ndwi) [OURS]
    -> img3  (h, w, 3) float32 — "the 3-band image" the assignment asks for
    ▼
[4] mean_shift.segment(img3, bandwidth, kernel)   [OURS]
    internally:
      a) reshape to (h*w, 3) — every pixel is a point in 3-D feature space
      b) z-score normalise each feature so bandwidth is isotropic
      c) build a scipy.spatial.cKDTree for fast neighbour lookup
      d) for each point: iterate shift-toward-local-mean until convergence
      e) merge converged points that land within bandwidth/2 -> cluster ids
    -> labels (h, w) int
    ▼
[5] water_select.pick_water(labels, ndwi, min_mean_ndwi)   [OURS]
    compute mean NDWI per cluster id; pick clusters above the threshold
    -> mask (h, w) bool
    ▼
[6] postprocess.clean(mask, min_blob_pixels)   [OURS]
    connected-components labelling, drop blobs smaller than the threshold
    -> (clean_mask, blob_info)
    ▼
UI RENDERING (back in app.py)
    Tab "Input"         -> preview of Green and NIR bands, optional ROI rectangle
    Tab "NDWI"          -> NDWI with RdBu colormap + colorbar
    Tab "Segmentation"  -> every cluster in a random colour
    Tab "Water Mask"    -> binary mask + semi-transparent cyan overlay
    Tab "Stats"         -> table of blob_info (count, area_px, area_km2)
    Tab "Download"      -> PNG and georeferenced GeoTIFF (using meta from step 1)
```

## 6. The Mean-Shift algorithm in detail

### 6.1 Intuition

Treat every pixel as a point in a 3-D feature space `(Green, NIR, NDWI)`.
For each point, look at its neighbours within a radius called the
**bandwidth**, compute a weighted mean of those neighbours, and shift
toward the mean. Repeat until the shift is tiny. Points in dense regions
of the feature space all drift toward the same local peak (called a
**mode**). Points that converge to the same mode form one cluster.
Water pixels share a similar `(Green, NIR, NDWI)` signature, so they
converge together — that is how the algorithm "finds" water without
being told what water is.

### 6.2 Math (two formulas, that's all)

For a point `x` with neighbours `{x_i}` within bandwidth `h`:

**Kernel (Gaussian — our default):**

    w_i = exp( -||x - x_i||^2 / (2 * h^2) )

Closer neighbours contribute more than far ones.

**Shift (weighted mean of neighbours):**

    x_new = sum(w_i * x_i) / sum(w_i)

Then set `x <- x_new` and repeat until `||x_new - x_old|| < eps`.

Everything else is bookkeeping.

### 6.3 Pseudocode

```
def segment(img3, bandwidth, kernel="gaussian", max_iter=100, eps=1e-3):

    # 1. flatten to a point cloud
    h, w, _ = img3.shape
    points = img3.reshape(h * w, 3)                 # (N, 3)

    # 2. z-score normalise so bandwidth means the same in every direction
    mean  = points.mean(axis=0)
    std   = points.std(axis=0) + 1e-9
    pts_n = (points - mean) / std

    # 3. build a KD-tree for fast neighbour lookup
    tree = cKDTree(pts_n)

    # 4. shift every point until convergence
    shifted = pts_n.copy()
    for i in range(len(pts_n)):
        x = shifted[i]
        for _ in range(max_iter):
            idx       = tree.query_ball_point(x, r=bandwidth)
            neighbors = pts_n[idx]
            if kernel == "gaussian":
                d2 = ((neighbors - x) ** 2).sum(axis=1)
                w  = np.exp(-d2 / (2 * bandwidth ** 2))
            else:                                    # flat
                w  = np.ones(len(neighbors))
            x_new = (w[:, None] * neighbors).sum(axis=0) / w.sum()
            if np.linalg.norm(x_new - x) < eps:
                break
            x = x_new
        shifted[i] = x

    # 5. merge points that converged to "the same" mode
    modes  = []
    labels = np.empty(len(pts_n), dtype=int)
    for i, p in enumerate(shifted):
        assigned = False
        for m_idx, m in enumerate(modes):
            if np.linalg.norm(p - m) < bandwidth / 2:
                labels[i] = m_idx
                assigned  = True
                break
        if not assigned:
            modes.append(p)
            labels[i] = len(modes) - 1

    # 6. reshape back into an image
    return labels.reshape(h, w)
```

### 6.4 Key design choices (these will come up in viva)

| Choice | What we did | Why |
|---|---|---|
| Feature space | 3-D: `(Green, NIR, NDWI)` | Matches the assignment's "3-band image" exactly. Spatial `(x, y)` deliberately NOT included, so far-apart water bodies still cluster together. |
| Kernel | Gaussian default; flat available via UI | Gaussian is smoother; flat is simpler to explain. Having both is a nice demo. |
| Normalisation | z-score per feature | Puts all three bands on equal scales so bandwidth is isotropic. |
| Bandwidth | User-controlled slider, default ~0.3 | Bandwidth is *the* hyperparameter. Slider = live feedback = good viva demo. |
| KD-tree | `scipy.spatial.cKDTree` for neighbours | Honest plumbing, same category as numpy. Without it, each iteration is O(N^2). |
| Mode merging | Threshold at `bandwidth / 2` | Standard heuristic. |
| Max iterations | 100 per point | Safety net; most points converge in fewer than 20. |

### 6.5 Speed estimate

- 512 × 512 crop = 262 144 points. With KD-tree + vectorised weights:
  **~10–40 seconds** on a laptop (single-threaded).
- 1000 × 1000 downsample (k=10 from a full Sentinel-2 tile): **1–3 min**.

Both are tolerable for a UI demo. Sliders don't re-run automatically —
the user must click **Run Pipeline** to trigger segmentation.

### 6.6 What we deliberately skipped

- No GPU acceleration. Pure NumPy is explainable.
- No adaptive bandwidth. Fixed is easier to defend.
- No parallel multiprocessing. Adds complexity, no viva payoff.
- No alternative clustering algorithms (k-means, DBSCAN). Assignment says
  Mean-Shift.

## 7. UI layout (Streamlit wireframe)

```
+------------------------------------------------------------------------+
| NDWI Water-Body Segmentation                                           |
| GNR Semester 8 course project                                          |
+----------------------+-------------------------------------------------+
| SIDEBAR              | MAIN — Tabs:                                    |
|                      | [Input] [NDWI] [Segmentation] [Water Mask]      |
| -- 1. Input --       | [Stats] [Download]                              |
| ( ) Upload your own  |                                                 |
| (*) Use sample scene |  {tab content here}                             |
|     [dropdown]       |                                                 |
| [Green upload]       |                                                 |
| [NIR upload]         |                                                 |
|                      |                                                 |
| -- 2. Scope --       |                                                 |
| ( ) Crop ROI         |                                                 |
| (*) Downsample       |                                                 |
| [row/col ranges]     |                                                 |
| [downsample k: 10]   |                                                 |
|                      |                                                 |
| -- 3. Mean-Shift --  |                                                 |
| Kernel: ( )G (*)Flat |                                                 |
| Bandwidth: [--o---]  |                                                 |
| Max iter: 100        |                                                 |
|                      |                                                 |
| -- 4. Water rule --  |                                                 |
| Min mean NDWI: 0.0   |                                                 |
| Min blob (px): 50    |                                                 |
|                      |                                                 |
| [ RUN PIPELINE ]     |                                                 |
+----------------------+-------------------------------------------------+
```

**Tab contents:**

| Tab | What it shows | Why |
|---|---|---|
| Input | Green and NIR bands side by side, with dimensions | Check the files loaded correctly |
| NDWI | NDWI array with a blue-red colormap + colorbar | See what Mean-Shift is going to cluster on |
| Segmentation | Label map with a random colour per cluster | See how the clustering actually split things |
| Water Mask | Binary mask + semi-transparent cyan overlay on Green | The final answer, easy to eyeball |
| Stats | Table of per-blob id, pixel area, km² | Numbers to quote in the report |
| Download | "Download PNG" + "Download GeoTIFF" buttons | Save the mask to open in QGIS later |

### 7.1 Streamlit-specific details

- **Caching:** `io_raster.load_bands` and the scope (crop/downsample)
  step are decorated with `@st.cache_data` so changing a slider doesn't
  re-read from disk.
- **Run trigger:** the pipeline runs only on clicking **Run Pipeline**,
  not on every slider tweak. Last result is kept in `st.session_state`
  so switching tabs doesn't re-run.
- **Progress feedback:** `st.progress()` bar during `segment()`
  (update every N points). Important because segmentation can take
  tens of seconds.
- **Error handling:** mismatched Green/NIR shapes, invalid ROI, NaNs,
  zero-bandwidth — all caught at the boundary and shown as
  `st.error(...)` or `st.warning(...)` rather than crashing.

### 7.2 Things we are NOT doing in the UI

- No mouse-drawn ROI. Streamlit doesn't support it natively and
  `streamlit-drawable-canvas` is an unnecessary dependency. Text inputs
  for row/col ranges are fine.
- No saved sessions, user accounts, or databases.
- No custom CSS.

## 8. Error handling

Only at system boundaries; internal code trusts itself.

| Where | What can go wrong | What we do |
|---|---|---|
| `io_raster.load_bands` | File is not a valid GeoTIFF | Catch `rasterio.errors.RasterioIOError` → `st.error(...)` |
| `io_raster.load_bands` | Green and NIR differ in shape | Raise `ValueError` → friendly error in UI |
| Scope step | ROI outside image | Clamp to valid range + `st.warning(...)` |
| `compute_ndwi` | Division by zero | `+ 1e-10` in the denominator |
| `segment` | Bandwidth ≤ 0 | Raise `ValueError` |
| `pick_water` | No cluster above threshold | Return all-False mask + friendly hint |

No try/except wrappers inside the algorithm — if our math is wrong, we
want the stack trace, not silent failure.

## 9. Testing

One `tests/test_<module>.py` per `[OURS]` module. Pure NumPy sanity
tests, no pytest plugins:

- `test_ndwi.py` — formula matches hand-calculated values; shape
  preserved; no NaN when both bands are zero; stack_bands returns
  `(H, W, 3)` with the right channel order.
- `test_mean_shift.py` — synthetic 2-blob input returns 2 unique labels;
  shape preserved; reproducibility across runs; bandwidth 0 raises.
- `test_water_select.py` — correct cluster is picked given known mean
  NDWIs; output dtype `bool`.
- `test_postprocess.py` — one big + one tiny blob → only big blob
  survives; per-blob stats are consistent.

No tests for `io_raster.py` (we trust rasterio) or `app.py` (UI — tested
manually).

## 10. Build order

Built in this order so each step is usable and testable before moving on:

1. Skeleton — folders, `requirements.txt`, placeholder modules, README stub.
2. `ndwi.py` — simplest ours module.
3. `io_raster.py` — rasterio wrapper.
4. `mean_shift.py` — the big one.
5. `water_select.py`.
6. `postprocess.py`.
7. End-to-end smoke script (`scripts/run_end_to_end.py`) — runs all five
   steps on a real GeoTIFF without the UI.
8. `app.py` — Streamlit UI, built tab by tab.
9. `fetch_from_gee.py` — optional GEE helper.
10. Bundled sample + default-parameter tuning.

## 11. Data sources

The tutor said we can use Google Earth Engine, direct satellite downloads,
or any open source. We have three paths:

1. **Bundled sample** — a small Sentinel-2 crop of Lake Tahoe committed
   in `data/samples/` so the demo works out of the box.
2. **Google Earth Engine** — `scripts/fetch_from_gee.py` for pulling
   fresh data for any location (needs a one-time `earthengine authenticate`).
3. **Manual download** — Copernicus Browser or USGS Earth Explorer.

GEE is only used to fetch files. The NDWI and Mean-Shift computation
always runs on our machine — otherwise we would not really be writing
the algorithm ourselves.

