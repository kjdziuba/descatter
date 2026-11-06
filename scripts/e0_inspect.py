"""E0 steps 4-6: inspect one raw PCUK2023 core, estimate noise, quick-look figure.

Run:  OMP_NUM_THREADS=16 .venv/bin/python scripts/e0_inspect.py
Writes results/e0/summary.json, results/e0/quicklook_<core>.png and
results/e0/<run_id>/run.json.
"""
from __future__ import annotations

import json
from pathlib import Path

import h5py
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from descatter.provenance import REPO_ROOT, Run

DATA = Path.home() / "descatter_data" / "pcuk2023_sample"
CORE = "s10_c048"
OUT = REPO_ROOT / "results" / "e0"
NOISE_WINDOW = (1800.0, 1900.0)
AMIDE_I = (1600.0, 1700.0)
# PyIR remove_wax (1340-1490, 2700-3000) + remove_co2 (2250-2450); see summary.json notes
WAX_CO2_CUTS = [(1340.0, 1490.0), (2250.0, 2450.0), (2700.0, 3000.0)]


def robust_sd(x: np.ndarray, axis: int = -1) -> np.ndarray:
    """1.4826 * MAD, a Gaussian-consistent SD that ignores bands and spikes."""
    med = np.median(x, axis=axis, keepdims=True)
    return 1.4826 * np.median(np.abs(x - med), axis=axis)


def summarise(name: str, values: np.ndarray) -> dict:
    q10, q50, q90 = np.percentile(values, [10, 50, 90])
    return {
        "quantity": name,
        "n": int(values.size),
        "median": float(q50),
        "p10": float(q10),
        "p90": float(q90),
        "min": float(values.min()),
        "max": float(values.max()),
    }


def main() -> None:
    raw_path = DATA / f"{CORE}_raw.h5"
    pre_path = DATA / f"{CORE}.h5"
    wn_raw_path = DATA / "wavenumbers_raw.npy"
    wn_pre_path = DATA / "wavenumbers.npy"

    with Run("e0", "inspect_raw_core", config={"core": CORE, "noise_window": NOISE_WINDOW}) as run:
        for p in (raw_path, pre_path, wn_raw_path, wn_pre_path):
            run.add_data_file(p)

        wr = np.load(wn_raw_path).astype(np.float64)
        wp = np.load(wn_pre_path).astype(np.float64)

        with h5py.File(raw_path, "r") as f:
            raw_shape = f["spectra"].shape
            raw_dtype = str(f["spectra"].dtype)
            raw_chunks = f["spectra"].chunks
            raw_mask_shape = f["mask"].shape
            spec = f["spectra"][:, :, :].astype(np.float64)
        with h5py.File(pre_path, "r") as f:
            pre_shape = f["spectra"].shape
            pre_dtype = str(f["spectra"].dtype)
            mask = f["mask"][:, :] > 0.5

        H, W, C = spec.shape
        flat = spec.reshape(H * W, C)
        tissue = flat[mask.reshape(-1)]

        # --- our own tissue mask, by the published rule (area under Amide I > 2) ---
        ai = (wr >= AMIDE_I[0]) & (wr <= AMIDE_I[1])
        band = flat[:, ai]
        area = np.trapezoid(band - band.min(axis=1, keepdims=True), x=wr[ai], axis=1)
        own_mask = (area > 2.0).reshape(H, W)
        # PyIR integrates over channel index, not wavenumber; rescale for comparability
        area_idx = area / float(np.mean(np.diff(wr)))
        own_mask_idx = (area_idx > 2.0).reshape(H, W)

        # --- noise: robust SD of first differences over 1800-1900, / sqrt(2) ---
        nw = (wr >= NOISE_WINDOW[0]) & (wr <= NOISE_WINDOW[1])
        d1 = np.diff(tissue[:, nw], axis=1)
        noise = robust_sd(d1, axis=1) / np.sqrt(2.0)

        absorb = summarise("absorbance over tissue pixels (all channels)", tissue)
        amide_peak_abs = summarise(
            "tissue absorbance at Amide I max", tissue[:, ai].max(axis=1)
        )

        # Amide I apparent peak position per tissue pixel (raw, no baseline removal)
        wa = wr[ai]
        pos_map = np.full((H, W), np.nan)
        pos_map[mask] = wa[np.argmax(tissue[:, ai], axis=1)]

        summary = {
            "core": CORE,
            "files": {
                "raw": str(raw_path),
                "preprocessed": str(pre_path),
            },
            "hdf5": {
                "raw": {
                    "keys": ["mask", "spectra"],
                    "spectra_shape": list(raw_shape),
                    "spectra_dtype": raw_dtype,
                    "spectra_chunks": list(raw_chunks),
                    "mask_shape": list(raw_mask_shape),
                    "compression": "lzf (re-saved by zenodo_get source; Zenodo lists gzip-9)",
                },
                "preprocessed": {
                    "keys": ["mask", "spectra"],
                    "spectra_shape": list(pre_shape),
                    "spectra_dtype": pre_dtype,
                    "mask_shape": [256, 256],
                },
            },
            "wavenumbers_raw": {
                "n": int(wr.size),
                "min_cm1": float(wr.min()),
                "max_cm1": float(wr.max()),
                "spacing_mean_cm1": float(np.mean(np.diff(wr))),
                "spacing_min_cm1": float(np.min(np.diff(wr))),
                "spacing_max_cm1": float(np.max(np.diff(wr))),
                "uniform": True,
            },
            "wavenumbers_preprocessed": {
                "n": int(wp.size),
                "min_cm1": float(wp.min()),
                "max_cm1": float(wp.max()),
                "uniform": False,
                "is_subset_of_raw_grid": True,
                "gaps_cm1": [
                    [float(wp[i]), float(wp[i + 1])]
                    for i in np.where(np.diff(wp) > 2.5)[0]
                ],
            },
            "tissue": {
                "mask_source": f"{CORE}.h5:/mask (256x256, matches the spectra grid)",
                "n_tissue_px": int(mask.sum()),
                "tissue_fraction": float(mask.mean()),
                "own_amideI_area_mask_agreement": {
                    "rule": "trapezoid area under 1600-1700 cm^-1 after min-to-zero > 2",
                    "integrated_over_wavenumber_fraction": float(own_mask.mean()),
                    "integrated_over_channel_index_fraction": float(own_mask_idx.mean()),
                    "iou_with_file_mask_channel_index": float(
                        (own_mask_idx & mask).sum() / (own_mask_idx | mask).sum()
                    ),
                },
            },
            "absorbance": {
                "all_channels_over_tissue": absorb,
                "amide_I_peak_over_tissue": amide_peak_abs,
            },
            "noise_estimate": {
                "definition": (
                    "per tissue pixel: 1.4826*MAD of first differences of raw absorbance "
                    f"over {NOISE_WINDOW[0]:.0f}-{NOISE_WINDOW[1]:.0f} cm^-1, divided by sqrt(2)"
                ),
                "n_channels_in_window": int(nw.sum()),
                **{k: v for k, v in summarise("noise sigma (AU)", noise).items() if k != "quantity"},
            },
            "amide_I_apparent_peak_position_cm1": {
                k: v
                for k, v in summarise("Amide I argmax over tissue", pos_map[mask]).items()
                if k != "quantity"
            },
        }

        # ---------------- quick-look figure ----------------
        fig, ax = plt.subplots(2, 2, figsize=(13.5, 8.4), constrained_layout=True)
        ax = ax.ravel()

        mu, sd = tissue.mean(axis=0), tissue.std(axis=0)

        for a, (lo, hi, title) in enumerate(
            [
                (wr.min(), wr.max(), "full range"),
                (950.0, 1800.0, "fingerprint region"),
            ]
        ):
            sl = (wr >= lo) & (wr <= hi)
            ax[a].fill_between(wr[sl], (mu - sd)[sl], (mu + sd)[sl], alpha=0.3, color="C0",
                               label="±1 SD")
            ax[a].plot(wr[sl], mu[sl], color="C0", lw=1.0, label="mean")
            for clo, chi in WAX_CO2_CUTS:
                if chi > lo and clo < hi:
                    ax[a].axvspan(max(clo, lo), min(chi, hi), color="grey", alpha=0.18, lw=0)
            if NOISE_WINDOW[1] > lo and NOISE_WINDOW[0] < hi:
                ax[a].axvspan(*NOISE_WINDOW, color="C3", alpha=0.18, lw=0)
            ax[a].set_xlabel("wavenumber / cm$^{-1}$")
            ax[a].set_ylabel("raw absorbance / AU")
            ax[a].invert_xaxis()
            ax[a].legend(loc="upper right", fontsize=8)
        ax[0].set_title(
            f"{CORE} raw, mean ± SD over {mask.sum():,} tissue px — full range\n"
            "sharp 2920/2850 bands are paraffin; grey = wax/CO$_2$ cuts, red = noise window"
        )
        ax[1].set_title(
            "fingerprint region — Amide I 1656, Amide II 1545\n"
            "grey band at 1340-1490 is the wax cut (CH$_3$ 1377, CH$_2$ 1462)"
        )

        im = ax[2].imshow(pos_map, cmap="viridis", interpolation="nearest")
        ax[2].set_title("Amide I apparent peak position / cm$^{-1}$\n(raw, no baseline removal)")
        ax[2].set_xticks([]); ax[2].set_yticks([])
        fig.colorbar(im, ax=ax[2], shrink=0.85)

        ax[3].hist(noise, bins=80, color="C2")
        for q, style in zip(np.percentile(noise, [10, 50, 90]), ["--", "-", "--"]):
            ax[3].axvline(q, color="k", ls=style, lw=1)
        ax[3].set_xlabel(r"noise $\sigma$ / AU")
        ax[3].set_ylabel("tissue pixels")
        ax[3].set_title(
            "per-pixel noise, 1800-1900 cm$^{-1}$\n"
            f"median {np.median(noise):.2e} AU (p10 {np.percentile(noise,10):.2e}, "
            f"p90 {np.percentile(noise,90):.2e})"
        )

        OUT.mkdir(parents=True, exist_ok=True)
        figpath = OUT / f"quicklook_{CORE}.png"
        fig.savefig(figpath, dpi=120)
        plt.close(fig)

        summary["figure"] = str(figpath.relative_to(REPO_ROOT))
        (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        run.notes["figure"] = summary["figure"]
        run.notes["noise_median_AU"] = summary["noise_estimate"]["median"]

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
