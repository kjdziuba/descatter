"""Reproduce the two posterior measurements quoted in the 2026-11-25 correction.

Requested by the mac (25d163d). Those numbers were computed in ad-hoc shell
snippets while checking the mac's review; this makes them reproducible, with
provenance, from the saved grid posteriors.

Reads only `~/descatter_runs/e1_grid` and `results/e1/grid/grid.json`, both
produced by the grid run in `150c117`. **Runs no inference**: no sampling, no
simulation, nothing new.

Two quantities:

1. **corr(f_beta, a) in the posterior.** This is what converts the boundary
   push on f_beta into an offset in a, and why the preprocessed condition
   loses more coverage than raw.
2. **How far f_beta_hat is pushed inward from its prior boundary**, in units of
   its own posterior SD. f_beta,true is 0 or 1, exactly on the edge of [0, 1],
   so the posterior is truncated and the median cannot sit at the truth.

Run:  OMP_NUM_THREADS=16 .venv/bin/python -m scripts.e1_posterior_correlation
Writes results/e1/grid/posterior_correlation.json and its run.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from descatter import infer_e1 as inf
from descatter.provenance import REPO_ROOT, Run
from scripts.e1_grid_config import CONDITIONS, GRID_RADII, H1_RADII

SAMPLES_DIR = Path.home() / "descatter_runs" / "e1_grid"
OUT = REPO_ROOT / "results" / "e1" / "grid"
#: the subset the correction originally quoted, kept so the two can be compared
ORIGINAL_SUBSET_PER_CELL = 5

I_F = inf.PARAM_NAMES.index("f_beta")
I_A = inf.PARAM_NAMES.index("a_um")


def _corrs(cond: str, radii: list[float], limit: int | None) -> list[float]:
    vals = []
    for a in radii:
        for f in (0, 1):
            files = sorted(SAMPLES_DIR.glob(f"{cond}_a{a}_f{f}_s*.npy"))
            for p in files[:limit] if limit else files:
                s = np.load(p)
                c = np.corrcoef(s[:, I_F], s[:, I_A])[0, 1]
                if np.isfinite(c):
                    vals.append(float(c))
    return vals


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    grid = json.loads((OUT / "grid.json").read_text())
    runs = grid["runs"]

    with Run("e1", "posterior_correlation",
             config={"purpose": "reproduce the numbers quoted in the 2026-11-25 "
                                "correction (707bf06), requested by the mac in 25d163d",
                     "reads": [str(SAMPLES_DIR), "results/e1/grid/grid.json"],
                     "runs_inference": False,
                     "source_of_posteriors": "the E1 grid, 150c117",
                     "h1_radii": H1_RADII}) as run:
        run.add_data_file(OUT / "grid.json")

        corr = {}
        for cond in CONDITIONS:
            full_h1 = _corrs(cond, H1_RADII, None)
            sub_h1 = _corrs(cond, H1_RADII, ORIGINAL_SUBSET_PER_CELL)
            full_all = _corrs(cond, GRID_RADII, None)
            corr[cond] = {
                "median_corr_H1_radii_all_draws": float(np.median(full_h1)),
                "n_posteriors_H1_all_draws": len(full_h1),
                "median_corr_H1_radii_first5_per_cell": float(np.median(sub_h1)),
                "n_posteriors_H1_first5": len(sub_h1),
                "median_corr_all_radii": float(np.median(full_all)),
                "n_posteriors_all_radii": len(full_all),
                "iqr_H1_all_draws": [float(np.percentile(full_h1, 25)),
                                     float(np.percentile(full_h1, 75))],
            }

        push = {}
        for cond in CONDITIONS:
            for f in (0.0, 1.0):
                sel = [r for r in runs
                       if r["condition"] == cond and r["f_beta"] == f
                       and r["a_um"] in H1_RADII]
                med = float(np.median([r["f_beta_median"] for r in sel]))
                sd = float(np.median([r["f_beta_sd"] for r in sel]))
                push[f"{cond}_f{int(f)}"] = {
                    "n": len(sel),
                    "median_f_beta_hat": med,
                    "offset_from_truth": med - f,
                    "offset_in_posterior_SD": (med - f) / sd,
                    "median_posterior_SD": sd,
                }

        report = {
            "purpose": "the two posterior measurements quoted in the 2026-11-25 "
                       "correction to comms/2026-11-24_watford_to_mac_06.md",
            "runs_inference": False,
            "source": "saved posteriors from the E1 grid (150c117); nothing re-run",
            "corr_f_beta_a": corr,
            "f_beta_boundary_push": push,
            "note_on_the_original_numbers": (
                "the correction quoted -0.332 (raw) and -0.773 (preprocessed) from the "
                "first 5 draws of each H1 cell. The all-draws values are reported "
                "alongside so the two can be compared; see 'agreement' below."
            ),
            "agreement": {
                cond: {
                    "quoted_in_correction": {"raw": -0.332, "preprocessed": -0.773}[cond],
                    "all_draws": corr[cond]["median_corr_H1_radii_all_draws"],
                    "difference": abs(corr[cond]["median_corr_H1_radii_all_draws"]
                                      - {"raw": -0.332, "preprocessed": -0.773}[cond]),
                }
                for cond in CONDITIONS
            },
            "reading": (
                "f_beta and a are far more strongly correlated in the preprocessed "
                "posterior than in the raw one. With f_beta,true on its prior boundary "
                "the posterior is truncated and f_beta_hat is pushed inward by about one "
                "posterior SD; that correlation is what drags a_hat with it, oppositely "
                "at the two boundaries, and why the same boundary effect costs the "
                "preprocessed condition more radius coverage."
            ),
        }
        (OUT / "posterior_correlation.json").write_text(json.dumps(report, indent=2) + "\n")
        run.notes["corr_H1"] = {c: corr[c]["median_corr_H1_radii_all_draws"]
                                for c in CONDITIONS}

    print("median posterior corr(f_beta, a):")
    for cond in CONDITIONS:
        c = corr[cond]
        print(f"  {cond:>13}  H1 all draws {c['median_corr_H1_radii_all_draws']:+.3f} "
              f"(n={c['n_posteriors_H1_all_draws']}, IQR "
              f"[{c['iqr_H1_all_draws'][0]:+.3f}, {c['iqr_H1_all_draws'][1]:+.3f}])"
              f" | first-5 subset {c['median_corr_H1_radii_first5_per_cell']:+.3f}"
              f" | all radii {c['median_corr_all_radii']:+.3f}")
    print("\nf_beta_hat pushed inward from its prior boundary:")
    for k, v in push.items():
        print(f"  {k:>20}: median f_hat {v['median_f_beta_hat']:.5f}, "
              f"offset {v['offset_in_posterior_SD']:+.2f} posterior SD (n={v['n']})")
    print("\nagreement with the numbers quoted in the correction:")
    for cond, v in report["agreement"].items():
        print(f"  {cond:>13}: quoted {v['quoted_in_correction']:+.3f}, "
              f"all draws {v['all_draws']:+.3f}, difference {v['difference']:.3f}")


if __name__ == "__main__":
    main()
