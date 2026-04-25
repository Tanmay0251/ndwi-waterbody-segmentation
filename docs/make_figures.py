"""Generate the result figures embedded in the PDF/PPTX.

Run from the project root:
    python docs/make_figures.py

Writes PNGs into docs/figures/.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from waterbody import load_bands, compute_ndwi, stack_bands, segment, pick_water, clean


FIG_DIR = Path(__file__).resolve().parent / "figures"
FIG_DIR.mkdir(exist_ok=True)


def random_cmap(n, seed=0):
    rng = np.random.default_rng(seed)
    return mcolors.ListedColormap(rng.uniform(0.2, 1.0, size=(n, 3)))


def run_pipeline(name, k=6, bandwidth=0.5, min_ndwi=0.0, min_blob=50):
    g_path = f"data/samples/{name}_green.tif"
    n_path = f"data/samples/{name}_nir.tif"
    full_g, full_n, meta = load_bands(g_path, n_path)
    g = full_g[::k, ::k]
    n = full_n[::k, ::k]
    ndwi = compute_ndwi(g, n)
    img3 = stack_bands(g, n, ndwi)
    labels = segment(img3, bandwidth=bandwidth)
    raw = pick_water(labels, ndwi, min_mean_ndwi=min_ndwi)
    pixel_m = abs(float(meta["transform"][0])) * k if meta else 10.0 * k
    mask, info = clean(raw, min_blob_pixels=min_blob, pixel_size_m=pixel_m)
    return {
        "full_green": full_g, "green": g, "nir": n,
        "ndwi": ndwi, "labels": labels, "mask": mask, "info": info,
    }


def figure_pipeline(name, out):
    r = run_pipeline(name)
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.2))

    axes[0].imshow(r["green"], cmap="gray")
    axes[0].set_title("1. Green band (downsampled)")
    axes[0].set_axis_off()

    im = axes[1].imshow(r["ndwi"], cmap="RdBu", vmin=-1, vmax=1)
    axes[1].set_title("2. NDWI = (G - NIR) / (G + NIR)")
    axes[1].set_axis_off()
    plt.colorbar(im, ax=axes[1], shrink=0.7)

    n_clusters = int(r["labels"].max()) + 1
    axes[2].imshow(r["labels"], cmap=random_cmap(n_clusters))
    axes[2].set_title(f"3. Mean-Shift clusters ({n_clusters})")
    axes[2].set_axis_off()

    # mask overlay on green
    axes[3].imshow(r["green"], cmap="gray")
    overlay = np.zeros((*r["mask"].shape, 4), dtype=np.float32)
    overlay[r["mask"], 1] = 1.0
    overlay[r["mask"], 2] = 1.0
    overlay[r["mask"], 3] = 0.55
    axes[3].imshow(overlay)
    total_km2 = sum(b["area_km2"] for b in r["info"])
    axes[3].set_title(f"4. Water mask — {len(r['info'])} body(ies), {total_km2:.2f} km²")
    axes[3].set_axis_off()

    plt.suptitle(f"Pipeline on {name}", fontsize=13)
    plt.tight_layout()
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"  wrote {out}")


def figure_single_mask(name, out):
    r = run_pipeline(name)
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.5))

    axes[0].imshow(r["green"], cmap="gray")
    axes[0].set_title(f"{name}: Green band")
    axes[0].set_axis_off()

    axes[1].imshow(r["green"], cmap="gray")
    overlay = np.zeros((*r["mask"].shape, 4), dtype=np.float32)
    overlay[r["mask"], 1] = 1.0
    overlay[r["mask"], 2] = 1.0
    overlay[r["mask"], 3] = 0.55
    axes[1].imshow(overlay)
    total_km2 = sum(b["area_km2"] for b in r["info"])
    axes[1].set_title(f"Detected water ({len(r['info'])} body(ies), {total_km2:.2f} km²)")
    axes[1].set_axis_off()

    plt.tight_layout()
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"  wrote {out}")


def figure_meanshift_concept(out):
    """Toy 2-D figure showing how points drift toward density peaks."""
    rng = np.random.default_rng(0)
    # Two clusters
    blob1 = rng.normal(loc=(2, 2), scale=0.5, size=(60, 2))
    blob2 = rng.normal(loc=(6, 4), scale=0.7, size=(60, 2))
    noise = rng.uniform(low=0, high=8, size=(15, 2))
    pts = np.vstack([blob1, blob2, noise])

    # Simulate mean-shift: each point moves toward mean of its neighbours
    bandwidth = 1.0
    shifted = pts.copy()
    for _ in range(20):
        new_pts = np.zeros_like(shifted)
        for i, x in enumerate(shifted):
            d2 = ((shifted - x) ** 2).sum(axis=1)
            inside = d2 < bandwidth ** 2
            new_pts[i] = shifted[inside].mean(axis=0)
        shifted = new_pts

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))

    axes[0].scatter(pts[:, 0], pts[:, 1], s=25, alpha=0.7, color="#3b82f6", edgecolor="#1e40af")
    axes[0].set_title("Before: each pixel is a point in feature space")
    axes[0].set_xlim(-0.5, 8.5)
    axes[0].set_ylim(-0.5, 8.5)
    axes[0].set_aspect("equal")
    axes[0].grid(alpha=0.3)

    axes[1].scatter(pts[:, 0], pts[:, 1], s=18, alpha=0.25, color="#94a3b8")
    axes[1].scatter(shifted[:, 0], shifted[:, 1], s=35, alpha=0.9, color="#ef4444", edgecolor="#7f1d1d")
    # Draw arrows from original to shifted for ~20 points
    show = rng.choice(len(pts), size=25, replace=False)
    for i in show:
        axes[1].annotate("", xy=shifted[i], xytext=pts[i],
                         arrowprops=dict(arrowstyle="->", color="#64748b", lw=0.7, alpha=0.5))
    axes[1].set_title("After Mean-Shift: points converge to density peaks")
    axes[1].set_xlim(-0.5, 8.5)
    axes[1].set_ylim(-0.5, 8.5)
    axes[1].set_aspect("equal")
    axes[1].grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"  wrote {out}")


if __name__ == "__main__":
    print("Generating figures ...")
    figure_meanshift_concept(FIG_DIR / "meanshift_concept.png")
    figure_pipeline("tahoe", FIG_DIR / "pipeline_tahoe.png")
    figure_single_mask("mumbai_coast", FIG_DIR / "result_mumbai.png")
    figure_single_mask("khadakwasla", FIG_DIR / "result_khadakwasla.png")
    print("Done.")
