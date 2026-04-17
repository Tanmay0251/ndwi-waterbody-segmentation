"""mean_shift.py — Mean-Shift segmentation, written from scratch.

[OURS] This is the heart of the project. Every line here is our own
implementation. We deliberately do NOT use sklearn.cluster.MeanShift
or cv2.pyrMeanShiftFiltering.

Intuition:
    Treat every pixel as a point in a 3-D feature space (Green, NIR, NDWI).
    For each point, look at its neighbours within a radius called the
    *bandwidth*, compute a weighted mean of those neighbours, and shift
    the point toward that mean. Repeat until the shift is negligible.
    Points that drift to the same peak belong to the same cluster.

We use scipy.spatial.cKDTree for fast neighbour lookup. That is a
standard data structure — same category as numpy — and it's labelled as
such in our comments. The algorithm logic is ours.

Exposes:
    segment(img3, bandwidth, kernel="gaussian", max_iter=100, eps=1e-3)
        -> labels  (shape H, W, int cluster-id per pixel)
"""

# TODO: implement segment()
