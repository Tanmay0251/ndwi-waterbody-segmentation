"""water_select.py — turn cluster labels into a water mask.

[OURS] After Mean-Shift has grouped pixels into clusters, we still need
to decide which of those clusters is actually water. Our rule: a cluster
is "water" if its mean NDWI is above a user-configurable threshold
(default 0.0). Multiple clusters can qualify if the scene has both
clear and turbid water, for example.

Exposes:
    pick_water(labels, ndwi, min_mean_ndwi=0.0) -> mask (H, W, bool)
"""

# TODO: implement pick_water()
