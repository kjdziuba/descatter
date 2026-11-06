"""E1 diagnostics. NOT pre-registered, and NOT a re-tuned control.

Two separate analyses, both labelled so they can never be mistaken for the
pre-registered controls in scripts/e1_controls.py:

A. ``a_fixed`` -- the positive control re-run with the radius held at its true
   value. The pre-registered positive control asks the sampler to recover
   f_beta while a still ranges over [0.25, 8] um. If it fails only when a is
   free, the sampler is fine and the *data* cannot pin the radius; if it fails
   with a fixed too, the machinery is at fault. The two readings have very
   different consequences, and the pre-registered control cannot tell them
   apart.

B. ``grid_crosscheck`` -- the dense (f_beta, a) grid that E1 step 3 asks for:
   profile the five nuisance parameters out by optimisation at each grid point
   and compare the profile likelihood with dynesty's posterior.

Run:  OMP_NUM_THREADS=1 .venv/bin/python scripts/e1_diagnostics.py
Writes results/e1/diagnostics.json, results/e1/diagnostics.png and
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
SIGMA_E0 = 1.1e-3
A_CONTROL_UM = 0.25
N_WORKERS = 14
NLIVE = 400

#: three cases for the grid cross-check: the control radius, the heart of the
#: H1 regime, and a radius past the first Mie maximum
GRID_CASES = [
    {"f_beta": 0.0, "a_um": 0.25},
    {"f_beta": 1.0, "a_um": 3.5},
    {"f_beta": 0.0, "a_um": 3.5},
]
GRID_NF, GRID_NA = 31, 31


def _nested_worker(job: dict) -> dict:
    import torch

    torch.set_num_threads(1)
    from descatter import infer_e1 as inf
    from descatter import physics as ph

    theta = ph.Theta(f_beta=job["f_beta"], a_um=job["a_um"], n_inf=1.40, phi=0.2, amplitude=1.0)
    res = inf.simulate_and_infer(
        theta,
        sigma=job["sigma"],
        condition=job["condition"],
        seed=job["seed"],
        nlive=NLIVE,
        fixed=job.get("fixed"),
    )
    res.pop("_samples", None)
    res["job"] = job
    return res


def _grid_worker(job: dict) -> dict:
    """Profile likelihood over the (f_beta, a) grid for one case and condition."""
    import torch
    from scipy.optimize import minimize

    torch.set_num_threads(1)
    from descatter import infer_e1 as inf
    from descatter import physics as ph

    nu = ph.wavenumber_grid()
    theta_true = ph.Theta(
        f_beta=job["f_beta"], a_um=job["a_um"], n_inf=1.40, phi=0.2, amplitude=1.0
    )
    sim = ph.simulate(nu, theta_true, sigma=job["sigma"], seed=job["seed"])
    problem = inf.E1Problem(
        nu=nu,
        data=sim["y"].numpy(),
        sigma=job["sigma"],
        condition=job["condition"],
        truth={k: getattr(theta_true, k) for k in inf.PARAM_NAMES},
        fixed={"f_beta": 0.0, "a_um": 1.0},  # placeholders; overwritten per point
    )
    nuis = ("n_inf", "phi", "amplitude", "baseline_offset", "baseline_slope")
    bounds = [inf.PRIOR_BOUNDS[n] for n in nuis]
    x0 = np.array([1.40, 0.2, 1.0, 0.0, 0.0])

    f_grid = np.linspace(0.0, 1.0, GRID_NF)
    a_grid = np.linspace(0.25, 8.0, GRID_NA)
    prof = np.full((GRID_NF, GRID_NA), -np.inf)

    t0 = time.perf_counter()
    for i, f in enumerate(f_grid):
        for j, a in enumerate(a_grid):
            problem.fixed = {"f_beta": float(f), "a_um": float(a)}
            problem.free_names = nuis

            def neg(x: np.ndarray) -> float:
                ll = problem.loglike(x)
                return -ll if ll > inf.REJECT_LOGL / 2 else 1e12

            best = -np.inf
            for start in (x0, np.array([1.45, 0.1, 1.5, 0.0, 0.0])):
                r = minimize(neg, start, method="Nelder-Mead", bounds=bounds,
                             options={"maxiter": 400, "xatol": 1e-3, "fatol": 1e-2})
                best = max(best, -r.fun)
            prof[i, j] = best
    return {
        "job": job,
        "f_grid": f_grid.tolist(),
        "a_grid": a_grid.tolist(),
        "profile_loglike": prof.tolist(),
        "wall_s": round(time.perf_counter() - t0, 1),
        "n_loglike_calls": problem.n_calls,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=20)
    ap.add_argument("--skip-grid", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    nested_jobs = [
        {
            "analysis": "a_fixed",
            "f_beta": f,
            "a_um": A_CONTROL_UM,
            "sigma": SIGMA_E0,
            "condition": cond,
            "seed": 1000 + s,
            "fixed": {"a_um": A_CONTROL_UM},
        }
        for cond in ("raw", "preprocessed")
        for f in (0.0, 1.0)
        for s in range(args.draws)
    ]
    grid_jobs = (
        []
        if args.skip_grid
        else [
            {"analysis": "grid_crosscheck", **case, "sigma": SIGMA_E0,
             "condition": cond, "seed": 1000}
            for case in GRID_CASES
            for cond in ("raw", "preprocessed")
        ]
    )

    config = {
        "analyses": ["a_fixed", "grid_crosscheck"],
        "pre_registered": False,
        "draws": args.draws,
        "sigma_e0_AU": SIGMA_E0,
        "a_control_um": A_CONTROL_UM,
        "grid_cases": GRID_CASES,
        "grid_shape": [GRID_NF, GRID_NA],
        "nlive": NLIVE,
    }
    print(f"{len(nested_jobs)} nested runs + {len(grid_jobs)} profile grids on {N_WORKERS} workers")

    with Run("e1", "diagnostics", config=config, seeds={"base": 1000}) as run:
        ctx = mp.get_context("spawn")
        t0 = time.perf_counter()
        with ctx.Pool(N_WORKERS) as pool:
            nested = []
            for i, r in enumerate(pool.imap_unordered(_nested_worker, nested_jobs), 1):
                nested.append(r)
                if i % 20 == 0 or i == len(nested_jobs):
                    print(f"  a_fixed {i}/{len(nested_jobs)}  {(time.perf_counter()-t0)/60:.1f} min")
            grids = []
            for i, r in enumerate(pool.imap_unordered(_grid_worker, grid_jobs), 1):
                grids.append(r)
                print(f"  grid {i}/{len(grid_jobs)}  {(time.perf_counter()-t0)/60:.1f} min")
        wall = time.perf_counter() - t0

        for r in nested:
            r.update({k: r["job"][k] for k in ("analysis", "f_beta", "a_um")})

        summary = {}
        for cond in ("raw", "preprocessed"):
            sel = [r for r in nested if r["condition"] == cond]
            w = np.array([r["wrong_mode_mass_W"] for r in sel], dtype=float)
            summary[cond] = {
                "n_draws": len(sel),
                "W_median": float(np.median(w)),
                "W_max": float(w.max()),
                "frac_draws_W_below_0.05": float((w < 0.05).mean()),
                "f_beta_sd_median": float(np.median([r["f_beta_sd"] for r in sel])),
                "wall_s_median": float(np.median([r["wall_s"] for r in sel])),
            }

        report = {
            "experiment": "E1",
            "status": "DIAGNOSTIC, not pre-registered, not a control",
            "config": config,
            "a_fixed": {
                "question": (
                    "with the radius held at its true value, does the sampler recover "
                    "f_beta in both conditions? If yes, a free radius -- not the "
                    "machinery -- is what breaks the preprocessed positive control."
                ),
                "per_condition": summary,
                "runs": [{k: v for k, v in r.items() if k != "job"} for r in nested],
            },
            "grid_crosscheck": [
                {k: v for k, v in g.items() if k != "profile_loglike"}
                | {"profile_loglike": g["profile_loglike"]}
                for g in grids
            ],
            "wall_s_total": round(wall, 1),
        }
        (OUT / "diagnostics.json").write_text(json.dumps(report, indent=2) + "\n")
        _figure(nested, grids)
        run.notes["a_fixed_summary"] = summary

    print("\n" + "=" * 70)
    print("DIAGNOSTIC A: positive control with a fixed at truth")
    for c, v in summary.items():
        print(
            f"  {c:14s} W median {v['W_median']:.4f}, max {v['W_max']:.4f}, "
            f"frac(W<0.05) = {v['frac_draws_W_below_0.05']:.2f}"
        )
    print(f"\ntotal wall {wall/60:.1f} min")


def _figure(nested: list[dict], grids: list[dict]) -> None:
    n_grid = len(grids)
    fig = plt.figure(figsize=(14, 4.4 + 3.6 * ((n_grid + 2) // 3)), constrained_layout=True)
    gs = fig.add_gridspec(1 + (n_grid + 2) // 3, 3)

    ax = fig.add_subplot(gs[0, 0])
    for j, cond in enumerate(("raw", "preprocessed")):
        w = [r["wrong_mode_mass_W"] for r in nested if r["condition"] == cond]
        ax.scatter(np.full(len(w), j) + np.linspace(-0.15, 0.15, len(w)), w, s=14, alpha=0.75)
    ax.axhline(0.05, color="C3", ls="--", lw=1)
    ax.set_xticks([0, 1], ["raw", "preprocessed"])
    ax.set_ylabel("wrong-mode mass W")
    ax.set_ylim(-0.03, 1.03)
    ax.set_title("DIAGNOSTIC: positive control\nwith a fixed at its true value")

    ax = fig.add_subplot(gs[0, 1:])
    ax.axis("off")
    ax.text(
        0.0, 0.95,
        "Not a pre-registered control.\n\n"
        "The pre-registered positive control samples a over [0.25, 8] um.\n"
        "Holding a at the truth separates two very different failures:\n"
        "  - sampler/likelihood bug, which would show here too;\n"
        "  - the data not constraining a, which would not.\n\n"
        "Panels below: profile log-likelihood over (f_beta, a), with the five\n"
        "nuisance parameters optimised out at each point. The white cross is\n"
        "the truth. Two separated ridges mean a genuinely bimodal posterior,\n"
        "not a sampler artefact.",
        va="top", family="monospace", fontsize=9,
    )

    for i, g in enumerate(grids):
        ax = fig.add_subplot(gs[1 + i // 3, i % 3])
        prof = np.asarray(g["profile_loglike"])
        f_grid, a_grid = np.asarray(g["f_grid"]), np.asarray(g["a_grid"])
        rel = prof - np.nanmax(prof)
        im = ax.pcolormesh(a_grid, f_grid, np.clip(rel, -30, 0), cmap="magma", shading="nearest")
        ax.plot(g["job"]["a_um"], g["job"]["f_beta"], "wx", ms=11, mew=2.2)
        ax.set_xlabel("a / µm")
        ax.set_ylabel(r"$f_\beta$")
        ax.set_title(
            f"{g['job']['condition']}: truth $f_\\beta$={g['job']['f_beta']:.0f}, "
            f"a={g['job']['a_um']} µm",
            fontsize=10,
        )
        fig.colorbar(im, ax=ax, label="profile log L − max")

    fig.savefig(OUT / "diagnostics.png", dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(v, "1")
    main()
