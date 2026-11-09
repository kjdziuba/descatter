"""Request 02 task 4: the likelihood-calibration gate.

chi^2 of the TRUE model against its own noisy data, under sigma(a). If the
likelihood is correctly specified this is a chi^2 draw on N degrees of freedom
in the raw condition and N - 2 in the preprocessed one, where s and c0 are
profiled out.

Cells: a in {0.25, 3.5} um x f_beta in {0, 1} x {raw, preprocessed},
200 draws each. The gate passes if every median is within +/-10 % of its
expected value.

If it fails, STOP: do not run task 5.

Run:  OMP_NUM_THREADS=16 .venv/bin/python -m scripts.e1_calibration
Writes results/e1/likelihood_calibration.json and .png.
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from descatter import infer_e1 as inf
from descatter import physics as ph
from descatter.provenance import REPO_ROOT, Run

OUT = REPO_ROOT / "results" / "e1"
RADII = [0.25, 3.5]
F_BETAS = [0.0, 1.0]
CONDITIONS = ["raw", "preprocessed"]
N_DRAWS = 200
TOL = 0.10


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    nu = ph.wavenumber_grid()

    with Run("e1", "likelihood_calibration",
             config={"radii_um": RADII, "f_betas": F_BETAS, "conditions": CONDITIONS,
                     "n_draws": N_DRAWS, "tolerance": TOL,
                     "likelihood": inf.PREPROCESSED_LIKELIHOOD},
             seeds={"base": 90000}) as run:
        cells = []
        for a in RADII:
            sigma = ph.sigma_for_radius(a)
            for f in F_BETAS:
                theta = ph.Theta(f_beta=f, a_um=a, n_inf=1.40, phi=ph.SIGMA_PHI, amplitude=1.0)
                theta_vec = [f, a, 1.40, ph.SIGMA_PHI, 1.0, 0.0, 0.0]
                for cond in CONDITIONS:
                    vals = []
                    for s in range(N_DRAWS):
                        sim = ph.simulate(nu, theta, sigma=sigma, seed=90000 + s)
                        prob = inf.E1Problem(nu=nu, data=sim["y"].numpy(), sigma=sigma,
                                             condition=cond)
                        c2 = prob.chi2(theta_vec)
                        assert c2 is not None, (a, f, cond, s)
                        vals.append(c2)
                    vals = np.array(vals)
                    expected = prob.dof
                    med = float(np.median(vals))
                    # the median of chi^2_k is not k; compare like with like
                    from scipy.stats import chi2 as chi2_dist
                    med_expected = float(chi2_dist.median(expected))
                    cells.append({
                        "a_um": a, "f_beta": f, "condition": cond,
                        "sigma_AU": sigma,
                        "n_data": prob.n_data, "n_profiled": prob.n_profiled,
                        "expected_dof": expected,
                        "mean": float(vals.mean()),
                        "median": med,
                        "p10": float(np.percentile(vals, 10)),
                        "p90": float(np.percentile(vals, 90)),
                        "ratio_mean_to_dof": float(vals.mean() / expected),
                        "ratio_median_to_dof": float(med / expected),
                        "ratio_median_to_chi2_median": float(med / med_expected),
                        "chi2_median_expected": med_expected,
                        "within_10pc_of_dof": bool(abs(med / expected - 1.0) <= TOL),
                        "within_10pc_of_chi2_median": bool(
                            abs(med / med_expected - 1.0) <= TOL),
                    })

        gate = all(c["within_10pc_of_dof"] for c in cells)
        gate_strict = all(c["within_10pc_of_chi2_median"] for c in cells)

        report = {
            "task": "request 02 task 4: likelihood calibration gate",
            "criterion": "median chi^2 at the truth within +/-10 % of its expected value "
                         "(N for raw, N - 2 for preprocessed), in every cell",
            "note": ("the request compares the median against N (or N-2). The median of a "
                     "chi^2_k variate is about k*(1 - 2/(9k))^3, slightly below k, so both "
                     "comparisons are reported. The verdict uses the request's definition."),
            "n_draws_per_cell": N_DRAWS,
            "GATE_PASSES": gate,
            "gate_against_chi2_median": gate_strict,
            "cells": cells,
        }
        (OUT / "likelihood_calibration.json").write_text(json.dumps(report, indent=2) + "\n")
        _figure(cells)
        run.notes["gate"] = gate

    print(f"{'a/um':>6} {'f_beta':>7} {'condition':>14} {'N':>5} {'dof':>5} "
          f"{'median':>9} {'p10':>8} {'p90':>8} {'med/dof':>8}  verdict")
    for c in cells:
        print(f"{c['a_um']:6.2f} {c['f_beta']:7.1f} {c['condition']:>14} {c['n_data']:5d} "
              f"{c['expected_dof']:5d} {c['median']:9.2f} {c['p10']:8.2f} {c['p90']:8.2f} "
              f"{c['ratio_median_to_dof']:8.4f}  "
              f"{'ok' if c['within_10pc_of_dof'] else 'FAIL'}")
    print(f"\nGATE: {'PASS' if gate else 'FAIL'}")
    if not gate:
        print("Task 5 must not run. Reporting and stopping, as the request requires.")


def _figure(cells: list[dict]) -> None:
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6), constrained_layout=True)
    for i, cond in enumerate(CONDITIONS):
        sub = [c for c in cells if c["condition"] == cond]
        labels = [f"a={c['a_um']}\n$f_\\beta$={c['f_beta']:.0f}" for c in sub]
        x = np.arange(len(sub))
        med = [c["median"] for c in sub]
        lo = [c["median"] - c["p10"] for c in sub]
        hi = [c["p90"] - c["median"] for c in sub]
        ax[i].errorbar(x, med, yerr=[lo, hi], fmt="o", capsize=5, ms=7)
        dof = sub[0]["expected_dof"]
        ax[i].axhline(dof, color="C3", ls="--", lw=1.2, label=f"expected dof = {dof}")
        ax[i].axhspan(dof * (1 - TOL), dof * (1 + TOL), color="C3", alpha=0.15, lw=0,
                      label="±10 % gate")
        ax[i].set_xticks(x, labels, fontsize=8)
        ax[i].set_ylabel(r"$\chi^2$ at the truth")
        ax[i].set_title(f"{cond}  (points = median, bars = p10–p90 over {N_DRAWS} draws)")
        ax[i].legend(fontsize=8)
    fig.savefig(OUT / "likelihood_calibration.png", dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    main()
