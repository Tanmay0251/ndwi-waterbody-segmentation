"""ndwi.py — NDWI formula and 3-band stacking.

[OURS] This file is ours. The NDWI formula is a standard remote-sensing
index, but the NumPy implementation here is written by the team.

Quick reminder of the math:

    NDWI = (Green - NIR) / (Green + NIR)

High NDWI (close to +1) means the pixel reflects a lot in Green and
absorbs in NIR — classic water behaviour. Vegetation does the opposite
(reflects NIR strongly, so NDWI goes negative for it).
"""

import numpy as np


def compute_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """Compute the Normalised Difference Water Index pixel-by-pixel.

    Parameters
    ----------
    green, nir : np.ndarray
        Two 2-D float arrays of identical shape (H, W). Values are
        expected to be reflectances, typically in [0, 1].

    Returns
    -------
    ndwi : np.ndarray, shape (H, W), dtype float32, values in [-1, 1]
    """
    # Guard against divide-by-zero at pixels where both bands are exactly
    # zero (that happens outside the scene footprint, for instance).
    # Adding a tiny number to the denominator is simpler than a masked
    # array and keeps the output shape perfectly clean.
    denom = green + nir + 1e-10
    ndwi = (green - nir) / denom
    return ndwi.astype(np.float32)


def stack_bands(green: np.ndarray, nir: np.ndarray, ndwi: np.ndarray) -> np.ndarray:
    """Stack Green, NIR, and NDWI into one (H, W, 3) image.

    This is the "3-band image" the assignment talks about. Mean-Shift
    will treat every pixel of this array as a point in a 3-D feature
    space and cluster them.

    The channel order is fixed: 0 = Green, 1 = NIR, 2 = NDWI.
    """
    # np.stack with axis=-1 places the three input arrays along a new
    # last dimension, in the exact order we pass them in.
    img3 = np.stack([green, nir, ndwi], axis=-1)
    return img3.astype(np.float32)
