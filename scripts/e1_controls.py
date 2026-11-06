"""E1 step 3: the positive and negative controls (allowed before approval).

Positive: a = 0.25 um, where scattering is negligible. Both conditions should
          recover f_beta.  Criterion: W < 0.05 in >= 95 % of draws.
Negative: the same setup with noise sigma x 100. The f_beta posterior should
          match the prior.  Criterion: KS(f_beta posterior, prior) < 0.1.

Also runs a sigma ladder, so the sigma at which the negative control starts to
fire is measured rather than argued about (mac WORKLOG 2026-11-06, point 1).

Does NOT run the E1 grid (step 4); that needs docs/EXPERIMENTS.md to say
Status: APPROVED.

Run:  OMP_NUM_THREADS=16 .venv/bin/python scripts/e1_controls.py [--draws N]
Writes results/e1/controls.json, results/e1/controls.png and
results/e1/<run_id>/run.json.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from descatter.provenance import REPO_ROOT, Run

OUT = REPO_ROOT / "results" / "e1"
SIGMA_E0 = 1.1e-3  # E0 median noise over tissue pixels, results/e0/summary.json
A_CONTROL_UM = 0.25
N_WORKERS = 14  # 14 single-threaded workers stays inside the 16-thread budget
NLIVE = 400


def _worker(job: dict) -> dict:
    """One nested-sampling run, single-threaded."""
    import torch

    torch.set_num_threads(1)
    from descatter import infer_e1 as inf
    from descatter import physics as ph

    theta = ph.Theta(
        f_beta=job["f_beta"], a_um=job["a_um"], n_inf=1.40, phi=0.2, amplitude=1.0
    )
    res = inf.simulate_and_infer(
        theta,
        sigma=job["sigma"],
        condition=job["condition"],
        seed=job["seed"],
        nlive=NLIVE,
    )
    res.pop("_samples", None)
    res["job"] = job
    return res


def _summarise(runs: list[dict], label: str) -> dict:
    """Pass/fail against the pre-registered criteria, per condition."""
    out: dict = {"label": label, "n_runs": len(runs), "per_condition": {}}
    for cond in ("raw", "preprocessed"):
        sel = [r for r in runs if r["condition"] == cond]
        if not sel:
            continue
        w = np.array([r["wrong_mode_mass_W"] for r in sel], dtype=float)
        ks = np.array([r["ks_f_beta_vs_uniform_prior"] for r in sel], dtype=float)
        out["per_condition"][cond] = {
            "n_draws": len(sel),
            "W_median": float(np.median(w)),
            "W_max": float(w.max()),
            "frac_draws_W_below_0.05": float((w < 0.05).mean()),
            "ks_median": float(np.median(ks)),
            "ks_max": float(ks.max()),
            "frac_draws_ks_below_0.1": float((ks < 0.1).mean()),
            "f_beta_sd_median": float(np.median([r["f_beta_sd"] for r in sel])),
            "a_median_um_median": float(np.median([r["a_median_um"] for r in sel])),
            "logz_median": float(np.median([r["logz"] for r in sel])),
            "wall_s_median": float(np.median([r["wall_s"] for r in sel])),
            "wall_s_total": float(np.sum([r["wall_s"] for r in sel])),
            "n_loglike_calls_median": float(np.median([r["n_loglike_calls"] for r in sel])),
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=20, help="noise draws per (f_beta, condition)")
    ap.add_argument("--ladder-draws", type=int, default=5)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    conditions = ("raw", "preprocessed")
    ladder_mults = (1, 10, 30, 100)

    jobs: list[dict] = []
    for cond in conditions:
        for f_beta in (0.0, 1.0):
            for s in range(args.draws):
                jobs.append(
                    {
                        "control": "positive",
                        "f_beta": f_beta,
                        "a_um": A_CONTROL_UM,
                        "sigma": SIGMA_E0,
                        "sigma_mult": 1,
                        "condition": cond,
                        "seed": 1000 + s,
                    }
                )
                jobs.append(
                    {
                        "control": "negative",
                        "f_beta": f_beta,
                        "a_um": A_CONTROL_UM,
                        "sigma": SIGMA_E0 * 100,
                        "sigma_mult": 100,
                        "condition": cond,
                        "seed": 2000 + s,
                    }
                )
            for mult in ladder_mults:
                for s in range(args.ladder_draws):
                    jobs.append(
                        {
                            "control": "ladder",
                            "f_beta": f_beta,
                            "a_um": A_CONTROL_UM,
                            "sigma": SIGMA_E0 * mult,
                            "sigma_mult": mult,
                            "condition": cond,
                            "seed": 3000 + s,
                        }
                    )

    config = {
        "sigma_e0_AU": SIGMA_E0,
        "a_control_um": A_CONTROL_UM,
        "draws_per_cell": args.draws,
        "ladder_draws_per_cell": args.ladder_draws,
        "ladder_sigma_multipliers": list(ladder_mults),
        "nlive": NLIVE,
        "n_workers": N_WORKERS,
        "n_jobs": len(jobs),
    }
    print(f"{len(jobs)} nested-sampling runs on {N_WORKERS} workers")

    with Run("e1", "controls", config=config, seeds={"base": 1000}) as run:
        from descatter import infer_e1 as inf
        from descatter import physics as ph

        run.add_data_file(REPO_ROOT / "results" / "e0" / "summary.json")

        # --- noise-free chi^2 gap: how separable are f_beta = 0 and 1 at all? ---
        gaps = []
        for mult in (1, 3, 10, 30, 100, 300, 1000):
            row = {"sigma_mult": mult, "sigma_AU": SIGMA_E0 * mult}
            for cond in conditions:
                row[f"chi2_gap_{cond}"] = inf.chi2_gap(
                    ph.Theta(f_beta=0.0, a_um=A_CONTROL_UM, n_inf=1.40, phi=0.2),
                    ph.Theta(f_beta=1.0, a_um=A_CONTROL_UM, n_inf=1.40, phi=0.2),
                    sigma=SIGMA_E0 * mult,
                    condition=cond,
                )
            gaps.append(row)

        t0 = time.perf_counter()
        ctx = mp.get_context("spawn")
        with ctx.Pool(N_WORKERS) as pool:
            runs = []
            for i, r in enumerate(pool.imap_unordered(_worker, jobs), 1):
                runs.append(r)
                if i % 20 == 0 or i == len(jobs):
                    print(f"  {i}/{len(jobs)}  elapsed {(time.perf_counter() - t0) / 60:.1f} min")
        wall = time.perf_counter() - t0

        for r in runs:
            r.update({k: r["job"][k] for k in ("control", "f_beta", "sigma_mult", "a_um")})

        pos = [r for r in runs if r["control"] == "positive"]
        neg = [r for r in runs if r["control"] == "negative"]
        lad = [r for r in runs if r["control"] == "ladder"]

        pos_sum = _summarise(pos, "positive control (a = 0.25 um, sigma = E0 median)")
        neg_sum = _summarise(neg, "negative control (a = 0.25 um, sigma x 100)")

        pos_pass = all(
            c["frac_draws_W_below_0.05"] >= 0.95 for c in pos_sum["per_condition"].values()
        )
        neg_pass = all(c["ks_median"] < 0.1 for c in neg_sum["per_condition"].values())

        ladder = []
        for mult in ladder_mults:
            row: dict = {"sigma_mult": mult, "sigma_AU": SIGMA_E0 * mult}
            for cond in conditions:
                sel = [r for r in lad if r["sigma_mult"] == mult and r["condition"] == cond]
                ks = np.array([r["ks_f_beta_vs_uniform_prior"] for r in sel])
                w = np.array([r["wrong_mode_mass_W"] for r in sel], dtype=float)
                row[cond] = {
                    "n": len(sel),
                    "ks_median": float(np.median(ks)),
                    "ks_min": float(ks.min()),
                    "ks_max": float(ks.max()),
                    "W_median": float(np.median(w)),
                    "f_beta_sd_median": float(np.median([r["f_beta_sd"] for r in sel])),
                }
            ladder.append(row)

        report = {
            "experiment": "E1",
            "step": "3 (controls only; the step-4 grid was NOT run)",
            "experiments_md_status_at_run_time": "DRAFT",
            "config": config,
            "preprocessed_condition_assumption": inf.PREPROCESSED_ASSUMPTION,
            "prior_bounds": {k: list(v) for k, v in inf.PRIOR_BOUNDS.items()},
            "pre_registered_criteria": {
                "positive": "W < 0.05 in >= 95 % of draws, in both conditions",
                "negative": "KS(f_beta posterior, uniform prior) < 0.1",
            },
            "noise_free_chi2_gap_f0_vs_f1": gaps,
            "positive_control": pos_sum | {"PASS": bool(pos_pass)},
            "negative_control": neg_sum | {"PASS": bool(neg_pass)},
            "sigma_ladder": ladder,
            "timing": {
                "wall_s_total": round(wall, 1),
                "wall_s_per_run_median": float(np.median([r["wall_s"] for r in runs])),
                "wall_s_per_run_median_raw": float(
                    np.median([r["wall_s"] for r in runs if r["condition"] == "raw"])
                ),
                "wall_s_per_run_median_preprocessed": float(
                    np.median([r["wall_s"] for r in runs if r["condition"] == "preprocessed"])
                ),
                "projected_grid_step4": _project_grid(runs),
            },
            "runs": [{k: v for k, v in r.items() if k != "job"} for r in runs],
        }
        (OUT / "controls.json").write_text(json.dumps(report, indent=2) + "\n")
        _figure(pos, neg, ladder, gaps, pos_pass, neg_pass)

        run.notes.update(
            {
                "positive_control_PASS": bool(pos_pass),
                "negative_control_PASS": bool(neg_pass),
                "n_runs": len(runs),
            }
        )

    print("\n" + "=" * 70)
    print(f"POSITIVE control: {'PASS' if pos_pass else 'FAIL'}")
    for c, v in pos_sum["per_condition"].items():
        print(
            f"  {c:14s} W median {v['W_median']:.4f}, max {v['W_max']:.4f}, "
            f"frac(W<0.05) = {v['frac_draws_W_below_0.05']:.2f}  [need >= 0.95]"
        )
    print(f"NEGATIVE control: {'PASS' if neg_pass else 'FAIL'}")
    for c, v in neg_sum["per_condition"].items():
        print(
            f"  {c:14s} KS median {v['ks_median']:.4f}, max {v['ks_max']:.4f}  [need < 0.1]"
        )
    print(f"\ntotal wall {wall / 60:.1f} min over {len(runs)} runs")
    print(json.dumps(report["timing"]["projected_grid_step4"], indent=2))


def _project_grid(runs: list[dict]) -> dict:
    """Project step 4's cost: 8 radii x 2 f_beta x 20 draws x 2 conditions."""
    raw = float(np.median([r["wall_s"] for r in runs if r["condition"] == "raw"]))
    pre = float(np.median([r["wall_s"] for r in runs if r["condition"] == "preprocessed"]))
    n_per_cond = 8 * 2 * 20
    serial_s = n_per_cond * (raw + pre)
    return {
        "n_runs": 2 * n_per_cond,
        "note": (
            "control runs are at a = 0.25 um where the posterior is simple; runs at "
            "a = 3-6 um are expected to be slower, so treat this as a lower bound"
        ),
        "serial_hours": round(serial_s / 3600, 2),
        f"hours_on_{N_WORKERS}_workers": round(serial_s / 3600 / N_WORKERS, 2),
        "fits_6h_budget_at_16_threads": bool(serial_s / N_WORKERS < 6 * 3600),
    }


def _figure(pos, neg, ladder, gaps, pos_pass, neg_pass) -> None:
    fig, ax = plt.subplots(2, 2, figsize=(13, 8.6), constrained_layout=True)

    for i, (runs, name, ok) in enumerate(
        [(pos, "positive control", pos_pass), (neg, "negative control", neg_pass)]
    ):
        for j, cond in enumerate(("raw", "preprocessed")):
            w = [r["wrong_mode_mass_W"] for r in runs if r["condition"] == cond]
            ax[0, i].scatter(
                np.full(len(w), j) + np.linspace(-0.15, 0.15, len(w)), w, s=14, alpha=0.75,
                label=cond,
            )
        ax[0, i].axhline(0.05, color="C3", ls="--", lw=1, label="W = 0.05")
        ax[0, i].set_xticks([0, 1], ["raw", "preprocessed"])
        ax[0, i].set_ylabel("wrong-mode mass W")
        ax[0, i].set_ylim(-0.03, 1.03)
        ax[0, i].set_title(f"{name} — {'PASS' if ok else 'FAIL'}")
        ax[0, i].legend(fontsize=8)

    for j, cond in enumerate(("raw", "preprocessed")):
        for runs, name, mk in [(pos, "positive", "o"), (neg, "negative", "s")]:
            ks = [r["ks_f_beta_vs_uniform_prior"] for r in runs if r["condition"] == cond]
            ax[1, 0].scatter(
                np.full(len(ks), 2 * j + (0 if name == "positive" else 0.4)),
                ks, s=14, marker=mk, alpha=0.75,
                label=f"{cond}, {name}" if j == 0 or True else None,
            )
    ax[1, 0].axhline(0.1, color="C3", ls="--", lw=1, label="KS = 0.1")
    ax[1, 0].set_xticks([0.2, 2.2], ["raw", "preprocessed"])
    ax[1, 0].set_ylabel("KS(f$_\\beta$ posterior, uniform prior)")
    ax[1, 0].set_title("circles = positive (should be far from the prior)\n"
                       "squares = negative (should sit on the prior)")
    ax[1, 0].legend(fontsize=7, ncol=2)

    m = [g["sigma_mult"] for g in gaps]
    ax[1, 1].loglog(m, [g["chi2_gap_raw"] for g in gaps], "o-", label="raw")
    ax[1, 1].loglog(m, [g["chi2_gap_preprocessed"] for g in gaps], "s-", label="preprocessed")
    ax[1, 1].axhline(1.0, color="k", ls=":", lw=1, label=r"$\Delta\chi^2 = 1$")
    ax2 = ax[1, 1].twinx()
    for cond, mk in (("raw", "o"), ("preprocessed", "s")):
        ax2.plot(
            [r["sigma_mult"] for r in ladder],
            [r[cond]["ks_median"] for r in ladder],
            mk + "--", color="C3", alpha=0.6,
            label=f"KS median, {cond}",
        )
    ax2.axhline(0.1, color="C3", ls=":", lw=1)
    ax2.set_ylabel("KS median (red)", color="C3")
    ax[1, 1].set_xlabel(r"noise multiplier $\sigma / \sigma_{E0}$")
    ax[1, 1].set_ylabel(r"noise-free $\Delta\chi^2$ (f$_\beta$=0 vs 1)")
    ax[1, 1].set_title("how much noise kills f$_\\beta$ identifiability")
    ax[1, 1].legend(fontsize=7, loc="lower left")

    fig.savefig(OUT / "controls.png", dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(v, "1")
    main()
