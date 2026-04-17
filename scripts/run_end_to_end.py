"""run_end_to_end.py — run the whole pipeline once, without any UI.

Useful for sanity-checking the algorithm against a real GeoTIFF pair
from the command line, before touching Streamlit. Saves the final
water mask as a PNG next to the input files.

Usage (from the project root, with the venv activated):

    python scripts/run_end_to_end.py \
        --green data/samples/green.tif \
        --nir   data/samples/nir.tif \
        --bandwidth 0.3 \
        --downsample 4 \
        --out   data/samples/out_mask.png
"""

import argparse
import sys
from pathlib import Path

# Make the project root importable even when this script is launched
# directly from the scripts/ folder. Saves the user from having to set
# PYTHONPATH manually.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from PIL import Image

from waterbody.io_raster import load_bands
from waterbody.ndwi import compute_ndwi, stack_bands
from waterbody.mean_shift import segment
from waterbody.water_select import pick_water
from waterbody.postprocess import clean


def _print_progress(done: int, total: int) -> None:
    """Tiny CLI progress bar — prints one line per ~10% of progress."""
    pct = 100 * done / total
    print(f"  mean-shift progress: {done} / {total}  ({pct:.1f}%)")


def main() -> None:
    parser = argparse.ArgumentParser(description="NDWI water-body extraction (CLI)")
    parser.add_argument("--green", required=True, help="path to Green band GeoTIFF")
    parser.add_argument("--nir", required=True, help="path to NIR band GeoTIFF")
    parser.add_argument(
        "--bandwidth", type=float, default=0.3,
        help="mean-shift bandwidth in normalised feature space (0.1 to 1.0 typical)",
    )
    parser.add_argument(
        "--downsample", type=int, default=1,
        help="take every k-th pixel; 1 = full resolution, 4 = 16x fewer pixels",
    )
    parser.add_argument(
        "--min-ndwi", type=float, default=0.0,
        help="a cluster counts as water if its mean NDWI exceeds this",
    )
    parser.add_argument(
        "--min-blob-px", type=int, default=50,
        help="drop connected water blobs smaller than this",
    )
    parser.add_argument("--out", default="out_mask.png", help="where to save the PNG mask")
    args = parser.parse_args()

    # --- Step 1: load the two bands -----------------------------------
    print("[1/5] loading rasters ...")
    green, nir, meta = load_bands(args.green, args.nir)
    print(f"       loaded Green {green.shape} and NIR {nir.shape}")

    # --- Step 2: optional downsample ----------------------------------
    # Takes every k-th row and column. Saves a lot of time because
    # Mean-Shift cost scales with the pixel count.
    if args.downsample > 1:
        k = args.downsample
        green = green[::k, ::k]
        nir = nir[::k, ::k]
        print(f"       downsampled by factor {k} -> now {green.shape}")

    # --- Step 3: NDWI + 3-band stacking -------------------------------
    print("[2/5] computing NDWI and stacking bands ...")
    ndwi = compute_ndwi(green, nir)
    img3 = stack_bands(green, nir, ndwi)

    # --- Step 4: Mean-Shift segmentation -------------------------------
    print("[3/5] running mean-shift segmentation ...")
    labels = segment(img3, bandwidth=args.bandwidth, progress_cb=_print_progress)
    print(f"       found {len(np.unique(labels))} clusters")

    # --- Step 5: pick water clusters and clean up ---------------------
    print("[4/5] selecting water clusters ...")
    raw_mask = pick_water(labels, ndwi, min_mean_ndwi=args.min_ndwi)

    print("[5/5] cleaning small blobs ...")
    clean_mask, blob_info = clean(
        raw_mask,
        min_blob_pixels=args.min_blob_px,
        pixel_size_m=float(meta.get("transform", [10.0])[0]) if meta else 10.0,
    )

    total_water_px = int(clean_mask.sum())
    total_area_km2 = sum(b["area_km2"] for b in blob_info)
    print(
        f"       result: {len(blob_info)} water bodies, "
        f"{total_water_px} pixels, {total_area_km2:.4f} km^2"
    )

    # --- Save PNG -----------------------------------------------------
    # Convert bool to 0/255 uint8 so PIL can write a plain grayscale PNG.
    out_path = Path(args.out)
    Image.fromarray((clean_mask.astype(np.uint8) * 255)).save(out_path)
    print(f"       saved mask to {out_path.resolve()}")


if __name__ == "__main__":
    main()
