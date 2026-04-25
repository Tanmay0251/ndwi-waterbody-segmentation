"""Streamlit UI for NDWI water-body segmentation.

Run:  streamlit run app.py
"""

from pathlib import Path

import numpy as np
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from waterbody import (
    load_bands, compute_ndwi, stack_bands,
    segment, pick_water, clean,
)


SAMPLES_DIR = Path("data/samples")


def list_samples():
    """Return [(name, green_path, nir_path)] pairs found in data/samples/."""
    pairs = []
    for g in sorted(SAMPLES_DIR.glob("*_green.tif")):
        name = g.stem.replace("_green", "")
        n = SAMPLES_DIR / f"{name}_nir.tif"
        if n.exists():
            pairs.append((name, str(g), str(n)))
    return pairs


@st.cache_data(show_spinner=False)
def load_pair(green_path, nir_path):
    return load_bands(green_path, nir_path)


def random_colormap(n, seed=0):
    rng = np.random.default_rng(seed)
    return mcolors.ListedColormap(rng.uniform(0.2, 1.0, size=(n, 3)))


st.set_page_config(page_title="NDWI Water-Body Segmentation", layout="wide")
st.title("NDWI Water-Body Segmentation")
st.caption("GNR Semester 8 — Green/NIR → NDWI → Mean-Shift → water mask")


# sidebar
with st.sidebar:
    samples = list_samples()
    if not samples:
        st.error("No samples in data/samples/. Expected files named "
                 "<place>_green.tif and <place>_nir.tif.")
        st.stop()

    names = [p[0] for p in samples]
    chosen = st.selectbox("Scene", names, index=0)
    green_path, nir_path = next((g, n) for name, g, n in samples if name == chosen)

    st.caption("Downsample factor keeps every k-th pixel so Mean-Shift stays fast.")
    k = st.slider("Downsample factor (k)", 1, 20, 6)

    bandwidth = st.slider("Bandwidth", 0.1, 1.2, 0.5, 0.05)
    min_ndwi  = st.slider("Min mean NDWI for water", -1.0, 1.0, 0.0, 0.05)
    min_blob  = st.number_input("Drop blobs smaller than (pixels)", min_value=1, value=50, step=10)

    run = st.button("Run")


# load selected pair
try:
    full_green, full_nir, meta = load_pair(green_path, nir_path)
    load_err = None
except Exception as exc:
    full_green = full_nir = meta = None
    load_err = str(exc)


if "result" not in st.session_state:
    st.session_state["result"] = None


# run pipeline when the button is clicked
if run and full_green is not None:
    g = full_green[::k, ::k]
    n = full_nir[::k, ::k]
    st.write(f"Running on {g.shape} = {g.size} pixels ...")
    progress = st.progress(0.0)

    def cb(done, total):
        progress.progress(done / total)

    ndwi   = compute_ndwi(g, n)
    img3   = stack_bands(g, n, ndwi)
    labels = segment(img3, bandwidth=bandwidth, progress_cb=cb)
    raw    = pick_water(labels, ndwi, min_mean_ndwi=min_ndwi)

    # pixel size in metres (Sentinel-2 is 10 m; downsample scales it up)
    try:
        pixel_m = abs(float(meta["transform"][0])) if meta else 10.0
    except Exception:
        pixel_m = 10.0
    pixel_m *= k

    mask, info = clean(raw, min_blob_pixels=int(min_blob), pixel_size_m=pixel_m)
    progress.empty()

    st.session_state["result"] = {
        "green": g, "ndwi": ndwi, "labels": labels,
        "mask": mask, "info": info,
    }


# tabs
tab_in, tab_nd, tab_seg, tab_mask, tab_stats = st.tabs(
    ["Input", "NDWI", "Segmentation", "Water mask", "Stats"]
)


with tab_in:
    if load_err:
        st.error(load_err)
    elif full_green is not None:
        st.write(f"Scene: **{chosen}** — full-resolution shape {full_green.shape}")
        c1, c2 = st.columns(2)
        c1.caption("Green band")
        c1.image((full_green / (full_green.max() + 1e-9) * 255).astype(np.uint8), clamp=True)
        c2.caption("NIR band")
        c2.image((full_nir / (full_nir.max() + 1e-9) * 255).astype(np.uint8), clamp=True)


result = st.session_state["result"]


with tab_nd:
    if result is None:
        st.write("Click **Run** to compute.")
    else:
        fig, ax = plt.subplots(figsize=(6, 6))
        im = ax.imshow(result["ndwi"], cmap="RdBu", vmin=-1, vmax=1)
        plt.colorbar(im, ax=ax, shrink=0.7, label="NDWI")
        ax.set_axis_off()
        st.pyplot(fig)
        st.caption("Blue = high NDWI (water-like); red = low NDWI (land-like).")


with tab_seg:
    if result is None:
        st.write("Click **Run** to compute.")
    else:
        labels = result["labels"]
        n_clusters = int(labels.max()) + 1
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.imshow(labels, cmap=random_colormap(n_clusters))
        ax.set_axis_off()
        st.pyplot(fig)
        st.caption(f"{n_clusters} Mean-Shift clusters; each colour is one cluster.")


with tab_mask:
    if result is None:
        st.write("Click **Run** to compute.")
    else:
        c1, c2 = st.columns(2)
        c1.caption("Water mask")
        c1.image(result["mask"].astype(np.uint8) * 255, clamp=True)

        # overlay on the Green band
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.imshow(result["green"], cmap="gray")
        overlay = np.zeros((*result["mask"].shape, 4), dtype=np.float32)
        overlay[result["mask"], 1] = 1.0
        overlay[result["mask"], 2] = 1.0
        overlay[result["mask"], 3] = 0.5
        ax.imshow(overlay)
        ax.set_axis_off()
        c2.caption("Overlay on Green band")
        c2.pyplot(fig)


with tab_stats:
    if result is None:
        st.write("Click **Run** to compute.")
    else:
        info = result["info"]
        if not info:
            st.write("No water bodies detected — try lowering the min-NDWI threshold.")
        else:
            total_px = sum(b["area_px"] for b in info)
            total_km2 = sum(b["area_km2"] for b in info)
            st.write(
                f"**{len(info)}** water body/bodies — total area "
                f"**{total_km2:.4f} km²** ({total_px} pixels)"
            )
            st.dataframe(info, hide_index=True)
