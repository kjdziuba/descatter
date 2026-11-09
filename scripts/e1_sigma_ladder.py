"""RETIRED 2026-11-06. Kept for the record; it does not run under the current code.

This probed the *old* negative control, which raised sigma until the f_beta
posterior went flat, and the *old* preprocessed likelihood, whose sigma_eff it
measures. The redesign replaced both: the negative control now makes f_beta
inert, and the preprocessed likelihood keeps sigma exact. Its results are in
results/e1/superseded_phi_0.05_0.90/sigma_ladder.json.

Original docstring follows.

Find the noise level at which the E1 negative control actually fires.

The ladder inside scripts/e1_controls.py stops at sigma x 100. There, the raw
condition's KS is still falling (0.84 -> 0.24 -> 0.18 -> 0.093) while the
preprocessed condition has flattened out near 0.24. This script extends the
ladder far enough to tell "not enough noise yet" from "more noise will never
help".

Labelled analysis, not a pre-registered control.

Run:  OMP_NUM_THREADS=1 .venv/bin/python scripts/e1_sigma_ladder.py
Writes results/e1/sigma_ladder.json and results/e1/sigma_ladder.png.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from descatter.provenance import REPO_ROOT, Run
from scripts.e1_controls import SIGMA_E0, A_CONTROL_UM, N_WORKERS, _worker

OUT = REPO_ROOT / "results" / "e1"
MULTS = (300, 1000, 3000, 10000)
DRAWS = 5


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [
        {
            "control": "ladder_ext",
            "f_beta": f,
            "a_um": A_CONTROL_UM,
            "sigma": SIGMA_E0 * m,
            "sigma_mult": m,
            "condition": cond,
            "seed": 4000 + s,
        }
        for cond in ("raw", "preprocessed")
        for m in MULTS
        for f in (0.0, 1.0)
        for s in range(DRAWS)
    ]
    config = {
        "pre_registered": False,
        "sigma_multipliers": list(MULTS),
        "draws_per_cell": DRAWS,
        "a_control_um": A_CONTROL_UM,
        "sigma_e0_AU": SIGMA_E0,
        "n_jobs": len(jobs),
    }
    print(f"{len(jobs)} runs on {N_WORKERS} workers")

    with Run("e1", "sigma_ladder", config=config, seeds={"base": 4000}) as run:
        from descatter import infer_e1 as inf
        from descatter import physics as ph

        t0 = time.perf_counter()
        ctx = mp.get_context("spawn")
        with ctx.Pool(N_WORKERS) as pool:
            runs = []
            for i, r in enumerate(pool.imap_unordered(_worker, jobs), 1):
                runs.append(r)
                if i % 20 == 0 or i == len(jobs):
                    print(f"  {i}/{len(jobs)}  {(time.perf_counter()-t0)/60:.1f} min", flush=True)
        for r in runs:
            r.update({k: r["job"][k] for k in ("sigma_mult", "f_beta")})

        # effective sigma actually seen by each condition's likelihood
        nu = ph.wavenumber_grid()
        th = ph.Theta(f_beta=0.0, a_um=A_CONTROL_UM, n_inf=1.40, phi=0.2)
        sigma_eff = []
        for m in (1, 10, 100, 1000, 10000):
            row = {"sigma_mult": m, "sigma_AU": SIGMA_E0 * m}
            for cond in ("raw", "preprocessed"):
                vals = []
                for seed in range(5):
                    sim = ph.simulate(nu, th, sigma=SIGMA_E0 * m, seed=seed)
                    p = inf.E1Problem(
                        nu=nu, data=sim["y"].numpy(), sigma=SIGMA_E0 * m, condition=cond
                    )
                    vals.append(p.sigma_eff)
                row[f"sigma_eff_{cond}"] = float(np.mean(vals))
            sigma_eff.append(row)

        table = []
        for m in MULTS:
            row: dict = {"sigma_mult": m, "sigma_AU": SIGMA_E0 * m}
            for cond in ("raw", "preprocessed"):
                sel = [r for r in runs if r["sigma_mult"] == m and r["condition"] == cond]
                ks = np.array([r["ks_f_beta_vs_uniform_prior"] for r in sel])
                row[cond] = {
                    "n": len(sel),
                    "ks_median": float(np.median(ks)),
                    "ks_max": float(ks.max()),
                    "frac_ks_below_0.1": float((ks < 0.1).mean()),
                    "W_median": float(np.median([r["wrong_mode_mass_W"] for r in sel])),
                }
            table.append(row)

        report = {
            "experiment": "E1",
            "status": "labelled analysis, not a pre-registered control",
            "question": (
                "does raising sigma ever make the negative control fire, in each "
                "condition? Criterion for reference: KS < 0.1."
            ),
            "config": config,
            "effective_sigma": sigma_eff,
            "extended_ladder": table,
            "wall_s": round(time.perf_counter() - t0, 1),
            "runs": [{k: v for k, v in r.items() if k != "job"} for r in runs],
        }
        (OUT / "sigma_ladder.json").write_text(json.dumps(report, indent=2) + "\n")
        _figure(table, sigma_eff)
        run.notes["extended_ladder"] = table

    print()
    print(f"{'sigma x':>9} | {'raw KS med':>11} {'raw frac<0.1':>13} | {'pp KS med':>10} {'pp frac<0.1':>12}")
    for r in table:
        print(
            f"{r['sigma_mult']:9d} | {r['raw']['ks_median']:11.4f} "
            f"{r['raw']['frac_ks_below_0.1']:13.2f} | {r['preprocessed']['ks_median']:10.4f} "
            f"{r['preprocessed']['frac_ks_below_0.1']:12.2f}"
        )
    print("\neffective sigma reaching the likelihood:")
    for r in sigma_eff:
        print(
            f"  sigma x {r['sigma_mult']:6d}: raw {r['sigma_eff_raw']:.4e}   "
            f"preprocessed {r['sigma_eff_preprocessed']:.4e}"
        )


def _figure(table, sigma_eff) -> None:
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6), constrained_layout=True)
    m = [r["sigma_mult"] for r in table]
    for cond, mk in (("raw", "o-"), ("preprocessed", "s-")):
        ax[0].semilogx(m, [r[cond]["ks_median"] for r in table], mk, label=cond)
    ax[0].axhline(0.1, color="C3", ls="--", lw=1, label="KS = 0.1")
    ax[0].set_xlabel(r"$\sigma / \sigma_{E0}$")
    ax[0].set_ylabel("median KS vs prior")
    ax[0].set_title("extended negative-control ladder")
    ax[0].legend(fontsize=8)
    ax[0].grid(alpha=0.3)

    m2 = [r["sigma_mult"] for r in sigma_eff]
    for cond, mk in (("raw", "o-"), ("preprocessed", "s-")):
        ax[1].loglog(m2, [r[f"sigma_eff_{cond}"] for r in sigma_eff], mk, label=cond)
    ax[1].set_xlabel(r"$\sigma / \sigma_{E0}$")
    ax[1].set_ylabel(r"$\sigma_{eff}$ in the likelihood / AU")
    ax[1].set_title(
        "why: vector normalisation caps the preprocessed noise\n"
        r"$\sigma_{pp} = \sigma / \|y_w\|$ and $\|y_w\| \propto \sigma$ once noise dominates"
    )
    ax[1].legend(fontsize=8)
    ax[1].grid(alpha=0.3, which="both")
    fig.savefig(OUT / "sigma_ladder.png", dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(v, "1")
    main()
