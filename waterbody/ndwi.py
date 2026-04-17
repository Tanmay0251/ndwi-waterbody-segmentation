"""ndwi.py — NDWI formula and 3-band stacking.

[OURS] This file is ours. The NDWI formula is a standard remote-sensing
index, but the NumPy implementation here is written by the team.

Quick reminder of the math:
    NDWI = (Green - NIR) / (Green + NIR)

High NDWI (close to +1) means the pixel reflects a lot in Green and
absorbs in NIR — classic water behaviour. Vegetation does the opposite
(reflects NIR, so NDWI goes negative).

Exposes:
    compute_ndwi(green, nir) -> ndwi
    stack_bands(green, nir, ndwi) -> img3  (shape H, W, 3)
"""

# TODO: implement compute_ndwi and stack_bands
