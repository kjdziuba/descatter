"""Request 02 task 6: project the cost of the step-4 grid at the new sigma(a).

Times 2 runs per condition at a = 3.5 and a = 5 um -- radii in the middle and
past the first Mie maximum, where the posterior is harder than at the
controls' a = 0.25 um -- then projects the 640-run grid on 14 workers.

The grid itself is NOT run: E1 needs Chris's APPROVED.

Run:  OMP_NUM_THREADS=1 .venv/bin/python -m scripts.e1_grid_projection
Writes results/e1/grid_projection.json.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import time

import numpy as np

from descatter.provenance import REPO_ROOT, Run
from scripts.e1_controls import CONDITIONS, NLIVE, N_WORKERS

OUT = REPO_ROOT / "results" / "e1"
TIMING_RADII = [3.5, 5.0]
DRAWS_PER_CELL = 2

#: the step-4 grid as pre-registered
GRID_RADII = [0.25, 1, 2, 3, 3.5, 4, 5, 6]
GRID_F_BETAS = [0, 1]
GRID_DRAWS = 20
GRID_N_RUNS = len(GRID_RADII) * len(GRID_F_BETAS) * GRID_DRAWS * len(CONDITIONS)


def _worker(job: dict) -> dict:
    import torch

    torch.set_num_threads(1)
    from descatter import infer_e1 as inf
    from descatter import physics as ph

    theta = ph.Theta(f_beta=job["f_beta"], a_um=job["a_um"], n_inf=1.40,
                     phi=ph.SIGMA_PHI, amplitude=1.0)
    res = inf.simulate_and_infer(theta, sigma=job["sigma"], condition=job["condition"],
                                 seed=job["seed"], nlive=NLIVE)
    res.pop("_samples", None)
    res["job"] = job
    return res


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    from descatter import physics as ph

    jobs = [
        {"a_um": a, "f_beta": f, "condition": c, "sigma": ph.sigma_for_radius(a),
         "seed": 77000 + s}
        for a in TIMING_RADII for c in CONDITIONS for f in (0.0, 1.0)
        for s in range(DRAWS_PER_CELL // 2 or 1)
    ]
    print(f"timing {len(jobs)} runs on {N_WORKERS} workers", flush=True)

    with Run("e1", "grid_projection",
             config={"timing_radii_um": TIMING_RADII, "grid_n_runs": GRID_N_RUNS,
                     "n_workers": N_WORKERS, "nlive": NLIVE}) as run:
        t0 = time.perf_counter()
        ctx = mp.get_context("spawn")
        with ctx.Pool(min(N_WORKERS, len(jobs))) as pool:
            runs = pool.map(_worker, jobs)
        wall = time.perf_counter() - t0
        for r in runs:
            r.update({k: r["job"][k] for k in ("a_um", "f_beta", "condition", "sigma")})

        per_cond = {}
        for c in CONDITIONS:
            sel = [r for r in runs if r["condition"] == c]
            per_cond[c] = {
                "n_timed": len(sel),
                "wall_s_mean": float(np.mean([r["wall_s"] for r in sel])),
                "wall_s_max": float(np.max([r["wall_s"] for r in sel])),
                "n_loglike_calls_mean": float(np.mean([r["n_loglike_calls"] for r in sel])),
            }
        per_radius = {}
        for a in TIMING_RADII:
            sel = [r for r in runs if r["a_um"] == a]
            per_radius[str(a)] = {
                "sigma_AU": float(sel[0]["sigma"]),
                "wall_s_mean": float(np.mean([r["wall_s"] for r in sel])),
                "W_values": [r["wrong_mode_mass_W"] for r in sel],
                "a_median_um": [round(r["a_median_um"], 3) for r in sel],
            }

        mean_pair = per_cond["raw"]["wall_s_mean"] + per_cond["preprocessed"]["wall_s_mean"]
        n_per_cond = GRID_N_RUNS // len(CONDITIONS)
        serial_s = n_per_cond * mean_pair
        parallel_h = serial_s / 3600 / N_WORKERS

        report = {
            "task": "request 02 task 6: step-4 grid cost projection at the new sigma(a)",
            "grid_as_pre_registered": {
                "radii_um": GRID_RADII, "f_betas": GRID_F_BETAS,
                "draws_per_combination": GRID_DRAWS, "conditions": list(CONDITIONS),
                "n_runs": GRID_N_RUNS,
            },
            "timing_sample": {"radii_um": TIMING_RADII, "n_runs_timed": len(jobs),
                              "wall_s_total": round(wall, 1)},
            "per_condition": per_cond,
            "per_radius": per_radius,
            "projection": {
                "serial_hours": round(serial_s / 3600, 2),
                f"hours_on_{N_WORKERS}_workers": round(parallel_h, 2),
                "fits_6h_budget": bool(parallel_h < 6.0),
                "basis": ("mean of the timed runs at a = 3.5 and 5 um, which are harder "
                          "than the controls' a = 0.25 um; the grid also includes easier "
                          "radii, so this should be an over- rather than under-estimate"),
            },
            "runs": [{k: v for k, v in r.items() if k != "job"} for r in runs],
        }
        (OUT / "grid_projection.json").write_text(json.dumps(report, indent=2) + "\n")
        run.notes["projection_hours"] = round(parallel_h, 2)

    print(f"\n{'condition':>14} {'mean wall/s':>12} {'max wall/s':>11} {'mean calls':>12}")
    for c, v in per_cond.items():
        print(f"{c:>14} {v['wall_s_mean']:12.1f} {v['wall_s_max']:11.1f} "
              f"{v['n_loglike_calls_mean']:12.0f}")
    print(f"\nstep-4 grid: {GRID_N_RUNS} runs -> {serial_s/3600:.2f} h serial, "
          f"{parallel_h:.2f} h on {N_WORKERS} workers "
          f"({'inside' if parallel_h < 6 else 'OVER'} the 6 h budget)")
    print("The grid was NOT run; E1 is not APPROVED.")


if __name__ == "__main__":
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(v, "1")
    main()
