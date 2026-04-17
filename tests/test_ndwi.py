"""Sanity tests for waterbody/ndwi.py."""

# TODO: add tests once ndwi.py is implemented.
# Planned:
#   - compute_ndwi() matches the hand-calculated value on a 3x3 toy array
#   - output shape equals input shape
#   - no NaN when both green and nir are zero at a pixel
#   - stack_bands() returns shape (H, W, 3) with correct channel order
