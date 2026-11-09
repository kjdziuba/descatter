"""Request 02 (mac) task 4: does the gauge fix the raw negative control?

LABELLED DIAGNOSTIC, not a control. results/e1/controls.json stands as run.

The mac's hypothesis (docs/EXPERIMENTS.md, E1 Amendment 2026-11-09): what
stalled raw `rwalk` was not the flat f_beta direction alone but the curved
(a, n_inf, amplitude) ridge running through it. Fixing n_inf removes the ridge
as a choice of coordinates, so if the hypothesis is right the raw negative
control should now pass at the as-run sampler setting.

Two parts:
- **negative control set-up**: f_beta inert, a = 0.25 um, sigma(0.25 um), raw,
  rwalk, nlive 400, 8 fresh-seed draws.
- **timing**: 2 runs per condition at a = 3.5 and 5 um in the GRID
  configuration (f_beta active, a free), reporting each run's 90 % interval
  for a against the truth, and re-projecting the 640-run grid.

GO/NO-GO for task 5: KS < 0.1 in all 8 draws AND median KS < 0.05.

Run:  OMP_NUM_THREADS=1 .venv/bin/python -m scripts.e1_gauge_diagnostic
Writes results/e1/gauge_diagnostic.json.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import time

import numpy as np

from descatter.provenance import REPO_ROOT, Run

OUT = REPO_ROOT / "results" / "e1"
A_CONTROL_UM = 0.25
TIMING_RADII = [3.5, 5.0]
N_WORKERS = 14
NLIVE = 400
N_DRAWS = 8
#: fresh, not used by any earlier E1 run (earlier bases: 1000-4999, 5000-7999,
#: 61000, 77000, 90000)
SEED_BASE_NEG = 120000
SEED_BASE_TIMING = 130000

GRID_N_RUNS = 8 * 2 * 20 * 2  # radii x f_beta x draws x conditions


def _worker(job: dict) -> dict:
    import torch

    torch.set_num_threads(1)
    from descatter import infer_e1 as inf
    from descatter import physics as ph

    theta = ph.Theta(f_beta=job["f_beta"], a_um=job["a_um"], n_inf=inf.N_INF_GAUGE,
                     phi=ph.SIGMA_PHI, amplitude=1.0, inert_f_beta=job["inert"])
    res = inf.simulate_and_infer(
        theta, sigma=job["sigma"], condition=job["condition"], seed=job["seed"],
        nlive=NLIVE,
    )
    res.pop("_samples", None)
    res["job"] = job
    return res


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    from descatter import physics as ph

    sigma_c = ph.sigma_for_radius(A_CONTROL_UM)
    neg_jobs = [
        {"kind": "negative", "f_beta": float(i % 2), "a_um": A_CONTROL_UM,
         "sigma": sigma_c, "condition": "raw", "inert": True, "seed": SEED_BASE_NEG + i}
        for i in range(N_DRAWS)
    ]
    timing_jobs = [
        {"kind": "timing", "f_beta": f, "a_um": a, "sigma": ph.sigma_for_radius(a),
         "condition": c, "inert": False, "seed": SEED_BASE_TIMING + i}
        for a in TIMING_RADII for c in ("raw", "preprocessed")
        for i, f in enumerate((0.0, 1.0))
    ]
    jobs = neg_jobs + timing_jobs
    print(f"{len(jobs)} runs on {N_WORKERS} workers "
          f"({len(neg_jobs)} negative-control, {len(timing_jobs)} timing)", flush=True)

    with Run("e1", "gauge_diagnostic",
             config={"status": "LABELLED DIAGNOSTIC, not a control",
                     "gauge": True, "n_inf_fixed": 1.40,
                     "a_control_um": A_CONTROL_UM, "sigma_AU": sigma_c,
                     "n_draws": N_DRAWS, "nlive": NLIVE, "sample": "rwalk",
                     "timing_radii_um": TIMING_RADII,
                     "seed_bases": [SEED_BASE_NEG, SEED_BASE_TIMING]},
             seeds={"negative": SEED_BASE_NEG, "timing": SEED_BASE_TIMING}) as run:
        t0 = time.perf_counter()
        ctx = mp.get_context("spawn")
        with ctx.Pool(N_WORKERS) as pool:
            res = []
            for i, r in enumerate(pool.imap_unordered(_worker, jobs), 1):
                res.append(r)
                print(f"  {i}/{len(jobs)}  {(time.perf_counter()-t0)/60:.1f} min", flush=True)
        wall = time.perf_counter() - t0
        for r in res:
            r.update({k: r["job"][k] for k in ("kind", "f_beta", "a_um", "condition")})

        neg = [r for r in res if r["kind"] == "negative"]
        ks = np.array([r["ks_f_beta_vs_uniform_prior"] for r in neg])
        go = bool((ks < 0.1).all() and np.median(ks) < 0.05)

        timing = [r for r in res if r["kind"] == "timing"]
        for r in timing:
            lo, hi = r["a_q05_q95_um"]
            r["a_interval_contains_truth"] = bool(lo <= r["a_um"] <= hi)
        per_cond = {}
        for c in ("raw", "preprocessed"):
            sel = [r for r in timing if r["condition"] == c]
            per_cond[c] = {
                "n": len(sel),
                "wall_s_mean": float(np.mean([r["wall_s"] for r in sel])),
                "wall_s_max": float(np.max([r["wall_s"] for r in sel])),
                "frac_a_interval_contains_truth": float(
                    np.mean([r["a_interval_contains_truth"] for r in sel])),
            }
        serial = (GRID_N_RUNS // 2) * (per_cond["raw"]["wall_s_mean"]
                                       + per_cond["preprocessed"]["wall_s_mean"])
        grid_h = serial / 3600 / N_WORKERS

        report = {
            "status": "LABELLED DIAGNOSTIC, not a control; results/e1/controls.json "
                      "stands as run",
            "hypothesis": "the curved (a, n_inf, amplitude) ridge, not the flat f_beta "
                          "direction alone, is what stalled raw rwalk",
            "go_criterion": "KS < 0.1 in all 8 draws AND median KS < 0.05",
            "GO": go,
            "negative_control_raw": {
                "n_draws": len(neg),
                "ks_per_draw": [round(float(x), 5) for x in ks],
                "ks_median": float(np.median(ks)), "ks_max": float(ks.max()),
                "frac_ks_below_0.1": float((ks < 0.1).mean()),
                "ks_floor_median": float(0.86 / np.sqrt(
                    np.median([r["n_posterior_samples"] for r in neg]))),
                "wall_s_median": float(np.median([r["wall_s"] for r in neg])),
                "as_run_comparison": {
                    "source": "results/e1/controls.json (0e209c7), legacy 7-parameter",
                    "ks_median": 0.1346, "frac_ks_below_0.1": 0.35,
                },
            },
            "timing_runs": [
                {k: r[k] for k in ("a_um", "f_beta", "condition", "wall_s",
                                   "a_median_um", "a_q05_q95_um",
                                   "a_interval_contains_truth", "wrong_mode_mass_W",
                                   "n_loglike_calls")}
                for r in sorted(timing, key=lambda x: (x["a_um"], x["condition"], x["f_beta"]))
            ],
            "per_condition_timing": per_cond,
            "grid_projection": {
                "n_runs": GRID_N_RUNS,
                "serial_hours": round(serial / 3600, 2),
                f"hours_on_{N_WORKERS}_workers": round(grid_h, 2),
                "fits_6h_budget": bool(grid_h < 6.0),
                "previous_projection_hours": 4.68,
            },
            "wall_s_total": round(wall, 1),
        }
        (OUT / "gauge_diagnostic.json").write_text(json.dumps(report, indent=2) + "\n")
        run.notes["GO"] = go

    print("\n" + "=" * 70)
    print(f"raw negative control under the gauge, {len(neg)} draws:")
    print(f"  KS per draw: {', '.join(f'{x:.4f}' for x in ks)}")
    print(f"  median {np.median(ks):.4f} (need < 0.05), max {ks.max():.4f} (need < 0.1)")
    print(f"  as run (legacy): median 0.1346, frac<0.1 0.35")
    print(f"\nGO to task 5: {go}")
    print(f"\ntiming: raw mean {per_cond['raw']['wall_s_mean']:.0f} s, "
          f"preprocessed mean {per_cond['preprocessed']['wall_s_mean']:.0f} s")
    for r in report["timing_runs"]:
        print(f"  a={r['a_um']:.1f} f={r['f_beta']:.0f} {r['condition']:>13}: "
              f"a 90% [{r['a_q05_q95_um'][0]:.3f}, {r['a_q05_q95_um'][1]:.3f}] "
              f"{'contains' if r['a_interval_contains_truth'] else 'EXCLUDES'} truth, "
              f"{r['wall_s']:.0f} s")
    print(f"\ngrid: {GRID_N_RUNS} runs -> {grid_h:.2f} h on {N_WORKERS} workers "
          f"(was 4.68 h)")


if __name__ == "__main__":
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(v, "1")
    main()
