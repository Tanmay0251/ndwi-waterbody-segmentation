"""app.py — Streamlit UI entry point.

Run with:
    streamlit run app.py

Nothing here is part of the "method" we defend in the viva. Streamlit
handles the UI plumbing — file uploads, sliders, tabs, image display.
All the algorithm work happens inside the waterbody/ package.
"""

import streamlit as st

st.set_page_config(page_title="NDWI Water-Body Segmentation", layout="wide")
st.title("NDWI Water-Body Segmentation")
st.caption("GNR Semester 8 course project — Green/NIR → NDWI → Mean-Shift → water mask")

st.info("UI not yet implemented. See docs/design.md for the planned layout.")
