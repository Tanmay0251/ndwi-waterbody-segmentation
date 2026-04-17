"""app.py — Streamlit UI for NDWI water-body segmentation.

Run with:
    streamlit run app.py

Nothing here is part of the "method" we defend in the viva. Streamlit
handles the UI plumbing — file uploads, sliders, tabs, image display.
All the algorithm work happens inside the waterbody/ package.

Flow of the app:
    1. User either uploads two GeoTIFFs or picks the bundled sample
    2. Sidebar sliders set scope (crop/downsample), bandwidth, kernel, etc.
    3. Clicking "Run Pipeline" kicks off the full pipeline
    4. Results are stored in st.session_state and rendered across tabs
"""

from io import BytesIO
from pathlib import Path
import tempfile

import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from PIL import Image

import rasterio
from rasterio.transform import Affine

from waterbody.io_raster import load_bands
from waterbody.ndwi import compute_ndwi, stack_bands
from waterbody.mean_shift import segment
from waterbody.water_select import pick_water
from waterbody.postprocess import clean


# =============================================================================
# Page config and title
# =============================================================================
st.set_page_config(page_title="NDWI Water-Body Segmentation", layout="wide")
st.title("NDWI Water-Body Segmentation")
st.caption(
    "GNR Semester 8 course project — Green/NIR → NDWI → Mean-Shift → water mask"
)


# =============================================================================
# Small helpers
# =============================================================================

SAMPLE_GREEN = Path("data/samples/green.tif")
SAMPLE_NIR = Path("data/samples/nir.tif")


def _save_upload_to_tempfile(upload) -> str:
    """Streamlit gives us bytes; rasterio wants a filesystem path. So we
    dump the upload into the OS temp folder and return its path."""
    tmp_dir = Path(tempfile.gettempdir()) / "ndwi_ui"
    tmp_dir.mkdir(exist_ok=True)
    tmp_path = tmp_dir / upload.name
    with open(tmp_path, "wb") as f:
        f.write(upload.getbuffer())
    return str(tmp_path)


@st.cache_data(show_spinner=False)
def _load_from_paths(green_path: str, nir_path: str):
    """Thin cached wrapper around io_raster.load_bands so changing a
    slider doesn't force us to re-read the GeoTIFFs from disk."""
    return load_bands(green_path, nir_path)


def _apply_scope(green, nir, mode, r1, r2, c1, c2, k):
    """Crop or downsample both bands the same way. Returns the reduced
    arrays plus a small dict the GeoTIFF-export step can use to adjust
    the georeferencing transform."""
    if mode == "Crop ROI":
        # Clamp to valid image coords so a mistyped bound doesn't crash.
        H, W = green.shape
        r1 = max(0, min(r1, H - 1))
        r2 = max(r1 + 1, min(r2, H))
        c1 = max(0, min(c1, W - 1))
        c2 = max(c1 + 1, min(c2, W))
        return green[r1:r2, c1:c2], nir[r1:r2, c1:c2], {
            "mode": "crop", "r1": r1, "c1": c1, "r2": r2, "c2": c2,
        }
    else:
        # Plain stride — every k-th pixel in both directions.
        return green[::k, ::k], nir[::k, ::k], {"mode": "downsample", "k": k}


def _make_random_colormap(n_colours: int, seed: int = 0):
    """A matplotlib ListedColormap with n random RGB colours. Used to
    visualise cluster labels — each cluster id gets its own colour."""
    rng = np.random.default_rng(seed)
    colours = rng.uniform(0.2, 1.0, size=(n_colours, 3))
    return mcolors.ListedColormap(colours)


def _mask_to_png_bytes(mask: np.ndarray) -> bytes:
    """Convert a bool mask to PNG bytes, ready to hand to st.download_button."""
    img = Image.fromarray((mask.astype(np.uint8) * 255))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _mask_to_geotiff_bytes(mask: np.ndarray, meta: dict, scope_info: dict) -> bytes:
    """Write the water mask as a georeferenced GeoTIFF. We adjust the
    affine transform to reflect any crop/downsample that was applied,
    so the output lines up correctly on a basemap in QGIS."""
    new_meta = meta.copy()
    new_meta.update(
        dtype="uint8",
        count=1,
        height=mask.shape[0],
        width=mask.shape[1],
        compress="lzw",
    )

    # Adjust the geo-transform for whichever scope mode was used.
    base_transform = meta.get("transform")
    if base_transform is not None and scope_info:
        if scope_info["mode"] == "crop":
            # Shift the origin by the crop offset (in pixels).
            new_transform = base_transform * Affine.translation(
                scope_info["c1"], scope_info["r1"]
            )
            new_meta["transform"] = new_transform
        elif scope_info["mode"] == "downsample":
            # Pixel size grows by factor k in both directions.
            k = scope_info["k"]
            new_transform = base_transform * Affine.scale(k, k)
            new_meta["transform"] = new_transform

    buf = BytesIO()
    with rasterio.io.MemoryFile() as memfile:
        with memfile.open(**new_meta) as dst:
            dst.write(mask.astype(np.uint8) * 255, 1)
        buf.write(memfile.read())
    return buf.getvalue()


def _render_overlay(green_arr: np.ndarray, mask: np.ndarray):
    """Return a matplotlib figure with the Green band in grayscale and
    the water mask overlaid in semi-transparent cyan."""
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.imshow(green_arr, cmap="gray")
    # Build an RGBA overlay: cyan where water, fully transparent elsewhere.
    overlay = np.zeros((*mask.shape, 4), dtype=np.float32)
    overlay[mask, 0] = 0.0  # R
    overlay[mask, 1] = 1.0  # G
    overlay[mask, 2] = 1.0  # B
    overlay[mask, 3] = 0.5  # alpha — so the underlying image shows through
    ax.imshow(overlay)
    ax.set_axis_off()
    return fig


# =============================================================================
# Sidebar — all controls live here
# =============================================================================

with st.sidebar:
    st.header("1. Input")

    # We expose the bundled sample (if it's present on disk) and also a
    # plain upload pathway. Users can switch between them at will.
    have_sample = SAMPLE_GREEN.exists() and SAMPLE_NIR.exists()
    source_options = ["Upload your own"]
    if have_sample:
        source_options.insert(0, "Use bundled sample")
    source = st.radio("Data source", source_options, index=0)

    upload_green = None
    upload_nir = None
    if source == "Upload your own":
        upload_green = st.file_uploader(
            "Green band GeoTIFF (.tif)", type=["tif", "tiff"], key="green"
        )
        upload_nir = st.file_uploader(
            "NIR band GeoTIFF (.tif)", type=["tif", "tiff"], key="nir"
        )

    st.header("2. Scope")
    st.caption(
        "Mean-Shift is O(N^2) per iteration. For a 512x512 crop it takes "
        "tens of seconds. Either crop a small area OR downsample the whole scene."
    )
    scope_mode = st.radio("Scope mode", ["Downsample", "Crop ROI"], index=0)

    crop_r1 = crop_r2 = crop_c1 = crop_c2 = 0
    downsample_k = 4
    if scope_mode == "Crop ROI":
        crop_r1 = st.number_input("Row start", min_value=0, value=0, step=16)
        crop_r2 = st.number_input("Row end", min_value=1, value=256, step=16)
        crop_c1 = st.number_input("Col start", min_value=0, value=0, step=16)
        crop_c2 = st.number_input("Col end", min_value=1, value=256, step=16)
    else:
        downsample_k = st.slider(
            "Downsample factor (k)", min_value=1, max_value=20, value=4,
            help="Every k-th pixel is kept. k=4 turns a 1000x1000 image into 250x250.",
        )

    st.header("3. Mean-Shift")
    kernel = st.radio("Kernel", ["gaussian", "flat"], index=0, horizontal=True)
    bandwidth = st.slider(
        "Bandwidth (in normalised feature space)",
        min_value=0.05, max_value=1.5, value=0.3, step=0.05,
        help="Smaller = many tight clusters. Larger = fewer broad clusters.",
    )
    max_iter = st.number_input(
        "Max iterations per point", min_value=10, max_value=500, value=100, step=10
    )

    st.header("4. Water rule")
    min_ndwi = st.slider(
        "Min mean NDWI for a cluster to count as water",
        min_value=-1.0, max_value=1.0, value=0.0, step=0.05,
    )
    min_blob_px = st.number_input(
        "Drop blobs smaller than (pixels)", min_value=1, value=50, step=10
    )

    run_clicked = st.button("Run Pipeline", type="primary", use_container_width=True)


# =============================================================================
# Resolve the input source into two filesystem paths
# =============================================================================

green_path = nir_path = None
if source == "Use bundled sample" and have_sample:
    green_path = str(SAMPLE_GREEN)
    nir_path = str(SAMPLE_NIR)
elif source == "Upload your own" and upload_green is not None and upload_nir is not None:
    green_path = _save_upload_to_tempfile(upload_green)
    nir_path = _save_upload_to_tempfile(upload_nir)


# =============================================================================
# Load rasters if we have paths
# =============================================================================

full_green = full_nir = None
meta = None
load_error = None

if green_path and nir_path:
    try:
        full_green, full_nir, meta = _load_from_paths(green_path, nir_path)
    except Exception as exc:
        load_error = str(exc)


# =============================================================================
# Run the pipeline on demand and cache the result in session_state
# =============================================================================

if "result" not in st.session_state:
    st.session_state["result"] = None

if run_clicked:
    if full_green is None or full_nir is None:
        st.error("Load a Green and a NIR band first (sidebar section 1).")
    else:
        # Apply the chosen scope to reduce the pixel count.
        green_small, nir_small, scope_info = _apply_scope(
            full_green, full_nir, scope_mode,
            crop_r1, crop_r2, crop_c1, crop_c2, downsample_k,
        )

        # Run the five algorithmic steps, with a progress bar during the
        # long one (Mean-Shift).
        st.info(f"Running on {green_small.shape} = {green_small.size} pixels...")
        progress = st.progress(0.0, text="Mean-Shift: 0%")

        def _cb(done, total):
            frac = done / total
            progress.progress(frac, text=f"Mean-Shift: {int(frac * 100)}%")

        ndwi = compute_ndwi(green_small, nir_small)
        img3 = stack_bands(green_small, nir_small, ndwi)
        labels = segment(
            img3, bandwidth=bandwidth, kernel=kernel, max_iter=int(max_iter),
            progress_cb=_cb,
        )
        raw_mask = pick_water(labels, ndwi, min_mean_ndwi=min_ndwi)

        # Try to read pixel size from the geotransform for accurate km^2.
        # Defaults to 10 m (Sentinel-2) if we can't.
        try:
            pixel_m = abs(float(meta["transform"][0])) if meta else 10.0
        except Exception:
            pixel_m = 10.0
        # If we downsampled, each output pixel covers k times more ground.
        if scope_info["mode"] == "downsample":
            pixel_m *= scope_info["k"]

        clean_mask, blob_info = clean(
            raw_mask, min_blob_pixels=int(min_blob_px), pixel_size_m=pixel_m
        )

        progress.empty()

        st.session_state["result"] = {
            "green": green_small,
            "nir": nir_small,
            "ndwi": ndwi,
            "labels": labels,
            "raw_mask": raw_mask,
            "clean_mask": clean_mask,
            "blob_info": blob_info,
            "scope_info": scope_info,
            "pixel_m": pixel_m,
        }
        st.success(
            f"Done. Found {len(blob_info)} water body/bodies "
            f"from {len(np.unique(labels))} clusters."
        )


# =============================================================================
# Tabs — show results
# =============================================================================

tab_input, tab_ndwi, tab_seg, tab_mask, tab_stats, tab_dl = st.tabs(
    ["Input", "NDWI", "Segmentation", "Water Mask", "Stats", "Download"]
)


with tab_input:
    if load_error:
        st.error(f"Could not load rasters: {load_error}")
    elif full_green is None:
        st.info("Pick a data source in the sidebar to get started.")
    else:
        st.write(f"Full-resolution shape: **{full_green.shape}**")
        col1, col2 = st.columns(2)
        with col1:
            st.caption("Green band")
            st.image(
                (full_green / (full_green.max() + 1e-9) * 255).astype(np.uint8),
                use_container_width=True, clamp=True,
            )
        with col2:
            st.caption("NIR band")
            st.image(
                (full_nir / (full_nir.max() + 1e-9) * 255).astype(np.uint8),
                use_container_width=True, clamp=True,
            )


result = st.session_state["result"]


with tab_ndwi:
    if result is None:
        st.info("Click **Run Pipeline** in the sidebar to populate this tab.")
    else:
        fig, ax = plt.subplots(figsize=(6, 6))
        im = ax.imshow(result["ndwi"], cmap="RdBu", vmin=-1, vmax=1)
        plt.colorbar(im, ax=ax, shrink=0.7, label="NDWI")
        ax.set_axis_off()
        st.pyplot(fig, use_container_width=True)
        st.caption("Blue = high NDWI (water-like); red = low NDWI (land-like).")


with tab_seg:
    if result is None:
        st.info("Click **Run Pipeline** in the sidebar to populate this tab.")
    else:
        labels = result["labels"]
        n_clusters = int(labels.max()) + 1
        cmap = _make_random_colormap(n_clusters)
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.imshow(labels, cmap=cmap)
        ax.set_axis_off()
        st.pyplot(fig, use_container_width=True)
        st.caption(f"{n_clusters} clusters found. Each colour = one cluster.")


with tab_mask:
    if result is None:
        st.info("Click **Run Pipeline** in the sidebar to populate this tab.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.caption("Binary water mask")
            st.image(
                result["clean_mask"].astype(np.uint8) * 255,
                use_container_width=True, clamp=True,
            )
        with col2:
            st.caption("Overlay on Green band")
            fig = _render_overlay(result["green"], result["clean_mask"])
            st.pyplot(fig, use_container_width=True)


with tab_stats:
    if result is None:
        st.info("Click **Run Pipeline** in the sidebar to populate this tab.")
    else:
        info = result["blob_info"]
        if not info:
            st.warning(
                "No water bodies detected. Try lowering the **Min mean NDWI** "
                "slider or the **Min blob** threshold."
            )
        else:
            total_px = sum(b["area_px"] for b in info)
            total_km2 = sum(b["area_km2"] for b in info)
            c1, c2, c3 = st.columns(3)
            c1.metric("Water bodies", len(info))
            c2.metric("Total area (pixels)", total_px)
            c3.metric("Total area (km²)", f"{total_km2:.4f}")
            st.dataframe(info, use_container_width=True, hide_index=True)


with tab_dl:
    if result is None:
        st.info("Run the pipeline first.")
    else:
        st.download_button(
            "Download mask as PNG",
            data=_mask_to_png_bytes(result["clean_mask"]),
            file_name="water_mask.png",
            mime="image/png",
        )
        if meta is not None:
            try:
                tif_bytes = _mask_to_geotiff_bytes(
                    result["clean_mask"], meta, result["scope_info"]
                )
                st.download_button(
                    "Download mask as GeoTIFF (georeferenced)",
                    data=tif_bytes,
                    file_name="water_mask.tif",
                    mime="image/tiff",
                )
            except Exception as exc:
                st.warning(f"GeoTIFF export failed: {exc}")
