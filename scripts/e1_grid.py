"""E1 step 4: the grid, and step 5's metrics (request 03 tasks 3-4).

640 runs: both conditions x a_true in {0.25, 1, 2, 3, 3.5, 4, 5, 6} um x
f_beta,true in {0, 1} x 20 draws, at sigma(a) from results/e1/sigma_table.json,
with the amended model (n_inf fixed at 1.40) and the sampler setting the
controls validated.

**Only runs after the cross-check passes.** The verdict applies the
pre-registered rules exactly as written -- pooling the 120 draws per condition
at a_true in {3, 3.5, 4} um -- and reports whichever way it falls.

Posterior samples go to ~/descatter_runs/, not to git.

Run:  OMP_NUM_THREADS=1 .venv/bin/python -m scripts.e1_grid
Writes results/e1/grid/{grid.json,per_radius.csv,verdict.json,grid.png,run.json}.
"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import os
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from descatter.provenance import REPO_ROOT, Run
from scripts.e1_grid_config import (
    BOUND,
    CONDITIONS,
    GRID_F_BETAS,
    GRID_N_RUNS,
    GRID_RADII,
    H1_RADII,
    N_DRAWS,
    N_WORKERS,
    NLIVE,
    SAMPLE,
    SEED_BASE,
    grid_seed,
)

OUT = REPO_ROOT / "results" / "e1" / "grid"
SAMPLES_DIR = Path.home() / "descatter_runs" / "e1_grid"
BUDGET_H = 6.0


def _worker(job: dict) -> dict:
    import torch

    torch.set_num_threads(1)
    import numpy as _np

    from descatter import infer_e1 as inf
    from descatter import physics as ph

    theta = ph.Theta(f_beta=job["f_beta"], a_um=job["a_um"], n_inf=inf.N_INF_GAUGE,
                     phi=ph.SIGMA_PHI, amplitude=1.0)
    out = inf.simulate_and_infer(
        theta, sigma=job["sigma"], condition=job["condition"], seed=job["seed"],
        nlive=NLIVE,
    )
    samples = out.pop("_samples", None)
    if samples is not None:
        SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        _np.save(SAMPLES_DIR / f"{job['condition']}_a{job['a_um']}_f{job['f_beta']:.0f}"
                               f"_s{job['seed']}.npy", samples.astype(_np.float32))
    lo, hi = out["a_q05_q95_um"]
    out["a_interval_contains_truth"] = bool(lo <= job["a_um"] <= hi)
    out["a_interval_width_um"] = hi - lo
    out.update({k: job[k] for k in ("a_um", "f_beta", "condition", "sigma", "seed")})
    return out


def _cells(runs: list[dict]) -> list[dict]:
    rows = []
    for cond in CONDITIONS:
        for a in GRID_RADII:
            sel = [r for r in runs if r["condition"] == cond and r["a_um"] == a]
            w = np.array([r["wrong_mode_mass_W"] for r in sel], dtype=float)
            rows.append({
                "condition": cond, "a_um": a, "n": len(sel),
                "sigma_AU": float(sel[0]["sigma"]),
                "W_median": float(np.median(w)),
                "frac_W_below_0.05": float((w < 0.05).mean()),
                "frac_W_above_0.2": float((w > 0.2).mean()),
                "a_coverage": float(np.mean([r["a_interval_contains_truth"] for r in sel])),
                "a_interval_width_median_um": float(
                    np.median([r["a_interval_width_um"] for r in sel])),
                "f_beta_sd_median": float(np.median([r["f_beta_sd"] for r in sel])),
                "logz_median": float(np.median([r["logz"] for r in sel])),
                "wall_s_median": float(np.median([r["wall_s"] for r in sel])),
            })
    return rows


def _verdict(runs: list[dict]) -> dict:
    """The pre-registered rules, applied exactly as written."""
    pooled = {}
    for cond in CONDITIONS:
        sel = [r for r in runs if r["condition"] == cond and r["a_um"] in H1_RADII]
        w = np.array([r["wrong_mode_mass_W"] for r in sel], dtype=float)
        pooled[cond] = {
            "n_draws": len(w),
            "W_median": float(np.median(w)),
            "frac_W_below_0.05": float((w < 0.05).mean()),
            "frac_W_above_0.2": float((w > 0.2).mean()),
        }
    raw, pp = pooled["raw"], pooled["preprocessed"]

    h1_raw = raw["frac_W_below_0.05"] >= 0.90
    h1_pp = pp["frac_W_above_0.2"] >= 0.50
    supported = bool(h1_raw and h1_pp)
    not_viable = bool(raw["frac_W_above_0.2"] >= 0.50)

    if not_viable:
        verdict = "not viable"
    elif supported:
        verdict = "supported"
    else:
        verdict = "mixed"

    return {
        "pooled_over": {"radii_um": H1_RADII, "f_betas": GRID_F_BETAS,
                        "draws_each": N_DRAWS, "per_condition": 120},
        "pooled": pooled,
        "h1_raw_clause": {"rule": "raw: W < 0.05 in >= 90 % of the pooled draws",
                          "value": raw["frac_W_below_0.05"], "holds": bool(h1_raw)},
        "h1_preprocessed_clause": {"rule": "preprocessed: W > 0.2 in >= 50 % of the "
                                           "pooled draws",
                                   "value": pp["frac_W_above_0.2"], "holds": bool(h1_pp)},
        "not_viable_rule": {"rule": "raw W > 0.2 in >= 50 % of the pooled draws",
                            "value": raw["frac_W_above_0.2"], "holds": bool(not_viable)},
        "VERDICT": verdict,
        "recorded_prediction": {
            "source": "docs/EXPERIMENTS.md, E1 note 2026-11-06 "
                      "(results/e1/degeneracy_review.json, 138265b)",
            "predicted": "W ~ 0 everywhere; raw H1 passes, preprocessed H1 fails, "
                         "so the overall verdict is mixed",
            "matches": bool(verdict == "mixed" and h1_raw and not h1_pp),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=N_DRAWS)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    xc = json.loads((REPO_ROOT / "results/e1/crosscheck/crosscheck.json").read_text())
    if not xc.get("grid_may_run"):
        raise SystemExit("cross-check did not pass; the grid must not run")
    if len(xc["comparisons"]) < 6:
        raise SystemExit(f"cross-check has only {len(xc['comparisons'])} comparisons; "
                         "the full six are required before the grid")

    from descatter import infer_e1 as inf
    from descatter import physics as ph

    sigma_by_a = {a: ph.sigma_for_radius(a) for a in GRID_RADII}
    jobs = [
        {"a_um": a, "f_beta": f, "condition": cond, "sigma": sigma_by_a[a],
         "seed": grid_seed(a, f, s)}
        for cond in CONDITIONS for a in GRID_RADII for f in GRID_F_BETAS
        for s in range(args.draws)
    ]
    config = {
        "step": "E1 step 4, APPROVED 2026-11-24",
        "radii_um": GRID_RADII, "f_betas": GRID_F_BETAS, "draws": args.draws,
        "conditions": list(CONDITIONS), "n_runs": len(jobs),
        "seed_base": SEED_BASE, "seed_scheme": "SEED_BASE + 1000*radius_idx + 100*f_idx + draw",
        "sigma_by_a_um": {str(k): v for k, v in sigma_by_a.items()},
        "sigma_rule": "sigma(a) = D(a)/295 (results/e1/sigma_table.json)",
        "nlive": NLIVE, "sample": SAMPLE, "bound": BOUND, "n_workers": N_WORKERS,
        "gauge": True, "n_inf_fixed": inf.N_INF_GAUGE,
        "prior_bounds": {k: list(v) for k, v in inf.PRIOR_BOUNDS.items()},
        "samples_dir": str(SAMPLES_DIR),
        "crosscheck": "results/e1/crosscheck/crosscheck.json, ALL_PASS",
    }
    print(f"E1 GRID: {len(jobs)} runs on {N_WORKERS} workers, seed base {SEED_BASE}",
          flush=True)

    with Run("e1", "grid", config=config, seeds={"base": SEED_BASE}) as run:
        run.add_data_file(REPO_ROOT / "results/e1/sigma_table.json")
        run.add_data_file(REPO_ROOT / "results/e1/crosscheck/crosscheck.json")

        t0 = time.perf_counter()
        checkpoint = max(1, len(jobs) // 10)
        ctx = mp.get_context("spawn")
        with ctx.Pool(N_WORKERS) as pool:
            runs = []
            for i, r in enumerate(pool.imap_unordered(_worker, jobs), 1):
                runs.append(r)
                if i % 20 == 0 or i == len(jobs):
                    el = time.perf_counter() - t0
                    proj = el / i * len(jobs) / 3600
                    print(f"  {i}/{len(jobs)}  {el/60:.1f} min  "
                          f"projected total {proj:.2f} h", flush=True)
                if i == checkpoint:
                    proj = (time.perf_counter() - t0) / i * len(jobs) / 3600
                    print(f"  BUDGET CHECK at {i}/{len(jobs)}: projected {proj:.2f} h "
                          f"against a {BUDGET_H} h budget", flush=True)
                    if proj > BUDGET_H:
                        pool.terminate()
                        raise SystemExit(
                            f"projected {proj:.2f} h exceeds the {BUDGET_H} h budget; "
                            "stopping as the request requires")
        wall = time.perf_counter() - t0

        cells = _cells(runs)
        verdict = _verdict(runs)
        verdict["wall_s_total"] = round(wall, 1)
        verdict["per_radius"] = cells

        (OUT / "grid.json").write_text(json.dumps(
            {"config": config, "wall_s_total": round(wall, 1),
             "runs": [{k: v for k, v in r.items() if not k.startswith("_")} for r in runs]},
            indent=2) + "\n")
        (OUT / "verdict.json").write_text(json.dumps(verdict, indent=2) + "\n")
        with open(OUT / "per_radius.csv", "w", newline="") as fh:
            wcsv = csv.DictWriter(fh, fieldnames=list(cells[0]))
            wcsv.writeheader()
            wcsv.writerows(cells)
        _figure(cells, verdict)
        run.notes["verdict"] = verdict["VERDICT"]

    print("\n" + "=" * 86)
    print(f"{'condition':>13} {'a/um':>6} {'W med':>9} {'frac<0.05':>10} {'frac>0.2':>9} "
          f"{'a cover':>8} {'a width':>9} {'f sd':>9}")
    for c in cells:
        print(f"{c['condition']:>13} {c['a_um']:6.2f} {c['W_median']:9.4f} "
              f"{c['frac_W_below_0.05']:10.2f} {c['frac_W_above_0.2']:9.2f} "
              f"{c['a_coverage']:8.2f} {c['a_interval_width_median_um']:9.2e} "
              f"{c['f_beta_sd_median']:9.2e}")
    print(f"\npooled over a in {H1_RADII} um, 120 draws per condition:")
    for cond, v in verdict["pooled"].items():
        print(f"  {cond:>13}: W median {v['W_median']:.4f}, "
              f"frac(W<0.05) {v['frac_W_below_0.05']:.3f}, "
              f"frac(W>0.2) {v['frac_W_above_0.2']:.3f}")
    print(f"\n  H1 raw clause          : {verdict['h1_raw_clause']['holds']}")
    print(f"  H1 preprocessed clause : {verdict['h1_preprocessed_clause']['holds']}")
    print(f"  not-viable rule        : {verdict['not_viable_rule']['holds']}")
    print(f"\nVERDICT: {verdict['VERDICT'].upper()}")
    print(f"matches the recorded prediction: {verdict['recorded_prediction']['matches']}")
    print(f"total wall {wall/3600:.2f} h over {len(runs)} runs")


def _figure(cells: list[dict], verdict: dict) -> None:
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.6), constrained_layout=True)
    for cond, mk in (("raw", "o-"), ("preprocessed", "s--")):
        sel = [c for c in cells if c["condition"] == cond]
        a = [c["a_um"] for c in sel]
        ax[0].plot(a, [c["W_median"] for c in sel], mk, label=cond)
        ax[1].plot(a, [c["a_coverage"] for c in sel], mk, label=cond)
        ax[2].semilogy(a, [c["a_interval_width_median_um"] for c in sel], mk, label=cond)
    for x in H1_RADII:
        for k in range(3):
            ax[k].axvspan(x - 0.08, x + 0.08, color="C2", alpha=0.12, lw=0)
    ax[0].axhline(0.05, color="C3", ls=":", lw=1, label="W = 0.05")
    ax[0].axhline(0.2, color="C1", ls=":", lw=1, label="W = 0.2")
    ax[0].set_ylabel("median wrong-mode mass W"); ax[0].set_ylim(-0.03, 1.03)
    ax[0].set_title(f"W by radius — verdict: {verdict['VERDICT']}")
    ax[1].axhline(0.90, color="C3", ls=":", lw=1, label="nominal 0.90")
    ax[1].set_ylabel("coverage of a_true by the 90 % interval"); ax[1].set_ylim(0, 1.05)
    ax[1].set_title("radius-interval coverage")
    ax[2].set_ylabel("median 90 % interval width / µm")
    ax[2].set_title("radius-interval width")
    for k in range(3):
        ax[k].set_xlabel("a$_{true}$ / µm"); ax[k].legend(fontsize=8); ax[k].grid(alpha=0.3)
    fig.suptitle("E1 grid (green bands: the H1 radii pooled for the verdict)", fontsize=11)
    fig.savefig(OUT / "grid.png", dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(v, "1")
    main()
