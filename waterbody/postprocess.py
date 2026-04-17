"""postprocess.py — clean up the water mask.

[OURS] Raw segmentation often produces tiny spurious water blobs (a few
scattered pixels that happen to have high NDWI — usually sensor noise
or shadows). This module drops any connected blob smaller than a
user-configurable pixel count, so the final mask is visually clean.

Connected-components labelling uses scipy.ndimage.label — standard
helper, same plumbing category as numpy.

Exposes:
    clean(mask, min_blob_pixels=50) -> (clean_mask, blob_info)
        blob_info is a list of dicts: {id, area_px, area_km2}
"""

# TODO: implement clean()
