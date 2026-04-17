"""Sanity tests for waterbody/postprocess.py."""

# TODO: add tests once postprocess.py is implemented.
# Planned:
#   - mask with one big blob + one tiny blob -> after clean() only the big blob remains
#   - blob_info has one entry per surviving blob, with area_px > 0
#   - km2 calculation is consistent with the supplied pixel size
