"""Sanity tests for waterbody/mean_shift.py."""

# TODO: add tests once mean_shift.py is implemented.
# Planned:
#   - feed a synthetic 2-blob point cloud -> segment() returns exactly 2 unique labels
#   - output shape equals (H, W)
#   - running twice with the same inputs returns identical labels (reproducibility)
#   - bandwidth of 0 raises ValueError
