"""LABELLED DIAGNOSTIC, not a control and not pre-registered.

The redesigned negative control FAILED in the raw condition: KS median 0.1346
against a 0.0063 sampling floor, with 0.35 of draws under the 0.1 threshold.
By construction that can only be a sampler artefact -- with f_beta inert the
model does not depend on f_beta at all, so the posterior must equal the prior,
and `test_inert_f_beta_likelihood_is_flat_in_f_beta` shows the log-likelihood
really is flat.

This asks one question: **can a sampler setting fix it?** The pre-registered
control stays as run; nothing here is a re-run of it, and whatever this finds
has to go back to the coordinator before the control is re-run under new
settings.

The candidates:
- more live points, so the flat direction is covered by more particles;
- slice sampling instead of a random walk. ``rwalk`` takes a fixed number of
  steps inside the bounding ellipsoid, which at sigma = 1.7e-5 is extremely
  thin in the six constrained directions, so the flat f_beta direction mixes
  slowly. ``rslice`` samples along random directions and does not have that
  failure mode.

Run:  OMP_NUM_THREADS=1 .venv/bin/python -m scripts.e1_sampler_diagnostic
Writes results/e1/sampler_diagnostic.json.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import time

import numpy as np

from descatter.provenance import REPO_ROOT, Run

OUT = REPO_ROOT / "results" / "e1"
A_UM = 0.25
N_WORKERS = 14
DRAWS = 4

SETTINGS = [
    {"name": "as-run (nlive 400, rwalk)", "nlive": 400, "sample": "rwalk"},
    {"name": "nlive 1500, rwalk", "nlive": 1500, "sample": "rwalk"},
    {"name": "nlive 400, rslice", "nlive": 400, "sample": "rslice"},
    {"name": "nlive 1000, rslice", "nlive": 1000, "sample": "rslice"},
]


def _worker(job: dict) -> dict:
    import time as _t

    import numpy as _np
    import torch

    torch.set_num_threads(1)
    import dynesty

    from descatter import infer_e1 as inf
    from descatter import physics as ph

    sigma = ph.sigma_for_radius(A_UM)
    theta = ph.Theta(f_beta=job["f_beta"], a_um=A_UM, n_inf=1.40, phi=ph.SIGMA_PHI,
                     amplitude=1.0, inert_f_beta=True)
    sim = ph.simulate(ph.wavenumber_grid(), theta, sigma=sigma, seed=job["seed"])
    problem = inf.E1Problem(
        nu=ph.wavenumber_grid(), data=sim["y"].numpy(), sigma=sigma,
        condition=job["condition"], inert_f_beta=True,
        truth={k: getattr(theta, k) for k in inf.PARAM_NAMES},
    )
    t0 = _t.perf_counter()
    sampler = dynesty.NestedSampler(
        problem.loglike, problem.prior_transform, len(problem.free_names),
        nlive=job["nlive"], rstate=_np.random.default_rng(job["seed"]),
        bound="multi", sample=job["sample"],
    )
    sampler.run_nested(dlogz=0.5, print_progress=False)
    samples = sampler.results.samples_equal(rstate=_np.random.default_rng(job["seed"] + 1))
    f = samples[:, inf.PARAM_NAMES.index("f_beta")]
    return {
        "setting": job["name"], "condition": job["condition"], "seed": job["seed"],
        "f_beta_true": job["f_beta"],
        "ks": inf.ks_vs_uniform(f),
        "n_samples": int(f.size),
        "ks_floor": float(0.86 / np.sqrt(f.size)),
        "wall_s": round(_t.perf_counter() - t0, 1),
        "n_loglike_calls": problem.n_calls,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [
        {**s, "condition": "raw", "f_beta": f, "seed": 61000 + i}
        for s in SETTINGS for i, f in enumerate([0.0, 1.0] * (DRAWS // 2))
    ]
    print(f"{len(jobs)} runs on {N_WORKERS} workers", flush=True)

    with Run("e1", "sampler_diagnostic",
             config={"status": "LABELLED DIAGNOSTIC, not a control",
                     "a_um": A_UM, "draws_per_setting": DRAWS,
                     "settings": SETTINGS, "condition": "raw"}) as run:
        t0 = time.perf_counter()
        ctx = mp.get_context("spawn")
        with ctx.Pool(N_WORKERS) as pool:
            res = []
            for i, r in enumerate(pool.imap_unordered(_worker, jobs), 1):
                res.append(r)
                print(f"  {i}/{len(jobs)}  {(time.perf_counter()-t0)/60:.1f} min", flush=True)
        wall = time.perf_counter() - t0

        table = []
        for s in SETTINGS:
            sel = [r for r in res if r["setting"] == s["name"]]
            ks = np.array([r["ks"] for r in sel])
            table.append({
                "setting": s["name"], "nlive": s["nlive"], "sample": s["sample"],
                "n": len(sel),
                "ks_median": float(np.median(ks)), "ks_max": float(ks.max()),
                "frac_ks_below_0.1": float((ks < 0.1).mean()),
                "ks_floor_median": float(np.median([r["ks_floor"] for r in sel])),
                "n_samples_median": float(np.median([r["n_samples"] for r in sel])),
                "wall_s_median": float(np.median([r["wall_s"] for r in sel])),
            })

        report = {
            "status": "LABELLED DIAGNOSTIC, not pre-registered, not a control re-run",
            "question": "the negative control failed in raw (KS median 0.1346, 0.35 of "
                        "draws under 0.1). With f_beta inert the model does not depend on "
                        "f_beta, so this can only be a sampler artefact. Can a sampler "
                        "setting fix it?",
            "does_not_change": "results/e1/controls.json stands as run. Re-running the "
                               "control under a new setting is the coordinator's call.",
            "wall_s_total": round(wall, 1),
            "settings": table,
            "runs": res,
        }
        (OUT / "sampler_diagnostic.json").write_text(json.dumps(report, indent=2) + "\n")
        run.notes["settings"] = table

    print(f"\n{'setting':>26} {'KS med':>8} {'KS max':>8} {'frac<0.1':>9} "
          f"{'floor':>8} {'wall/s':>8}")
    for t in table:
        print(f"{t['setting']:>26} {t['ks_median']:8.4f} {t['ks_max']:8.4f} "
              f"{t['frac_ks_below_0.1']:9.2f} {t['ks_floor_median']:8.4f} "
              f"{t['wall_s_median']:8.0f}")


if __name__ == "__main__":
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(v, "1")
    main()
