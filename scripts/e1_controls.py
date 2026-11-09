"""E1 controls, redesigned 2026-11-06 (request 02 task 5).

Three sets of runs, all at a = 0.25 um under sigma(0.25 um), 40 draws per
condition each (f_beta,true in {0, 1} x 20 seeds):

- **positive**, with ``a`` FIXED at 0.25 um. Tests the sampler and likelihood
  alone. Criterion: W < 0.05 in >= 95 % of the 40 draws, in each condition.
- **negative**, with f_beta made INERT, so it has no effect on the spectrum.
  The posterior must then reproduce the prior. Criterion: KS < 0.1 in >= 90 %
  of the 40 draws, in each condition, from >= 2000 equal-weight samples.
- **free_a**, the old positive control with ``a`` sampled. A labelled
  observation, NOT thresholded: it is confounded with H1 itself, because the
  preprocessed window cannot pin the radius.

The step-4 grid is NOT run here; E1 needs Chris's APPROVED first.

Run:  OMP_NUM_THREADS=1 .venv/bin/python -m scripts.e1_controls [--draws N]
Writes results/e1/controls.{json,png}.
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
A_CONTROL_UM = 0.25
N_WORKERS = 14
NLIVE = 400
CONDITIONS = ("raw", "preprocessed")

#: name -> how the run is set up and how it is judged
CONTROLS = {
    "positive": {"thresholded": True, "fix_a": True, "inert": False,
                 "criterion": "W < 0.05 in >= 95 % of the 40 draws"},
    "negative": {"thresholded": True, "fix_a": False, "inert": True,
                 "criterion": "KS(f_beta, prior) < 0.1 in >= 90 % of the 40 draws"},
    "free_a": {"thresholded": False, "fix_a": False, "inert": False,
               "criterion": "labelled observation, not thresholded"},
}


def _worker(job: dict) -> dict:
    import torch

    torch.set_num_threads(1)
    from descatter import infer_e1 as inf
    from descatter import physics as ph

    theta = ph.Theta(
        f_beta=job["f_beta"], a_um=job["a_um"], n_inf=1.40, phi=ph.SIGMA_PHI,
        amplitude=1.0, inert_f_beta=job["inert"],
    )
    res = inf.simulate_and_infer(
        theta,
        sigma=job["sigma"],
        condition=job["condition"],
        seed=job["seed"],
        nlive=NLIVE,
        fixed={"a_um": job["a_um"]} if job["fix_a"] else None,
    )
    res.pop("_samples", None)
    res["job"] = job
    return res


def _summarise(runs: list[dict], control: str) -> dict:
    spec = CONTROLS[control]
    out: dict = {"control": control, "criterion": spec["criterion"],
                 "thresholded": spec["thresholded"], "per_condition": {}}
    for cond in CONDITIONS:
        sel = [r for r in runs if r["condition"] == cond]
        if not sel:
            continue
        w = np.array([r["wrong_mode_mass_W"] for r in sel], dtype=float)
        ks = np.array([r["ks_f_beta_vs_uniform_prior"] for r in sel], dtype=float)
        nsamp = np.array([r["n_posterior_samples"] for r in sel], dtype=int)
        frac_w = float((w < 0.05).mean())
        frac_ks = float((ks < 0.1).mean())
        cell = {
            "n_draws": len(sel),
            "W_median": float(np.median(w)), "W_max": float(w.max()),
            "frac_W_below_0.05": frac_w,
            "ks_median": float(np.median(ks)), "ks_max": float(ks.max()),
            "frac_ks_below_0.1": frac_ks,
            "f_beta_sd_median": float(np.median([r["f_beta_sd"] for r in sel])),
            "a_median_um_median": float(np.median([r["a_median_um"] for r in sel])),
            "min_posterior_samples": int(nsamp.min()),
            "meets_2000_sample_requirement": bool(nsamp.min() >= 2000),
            "logz_median": float(np.median([r["logz"] for r in sel])),
            "wall_s_median": float(np.median([r["wall_s"] for r in sel])),
            "n_loglike_calls_median": float(np.median([r["n_loglike_calls"] for r in sel])),
        }
        if spec["thresholded"]:
            cell["PASS"] = bool(frac_w >= 0.95) if control == "positive" else bool(frac_ks >= 0.90)
        out["per_condition"][cond] = cell
    if spec["thresholded"]:
        out["PASS"] = all(c["PASS"] for c in out["per_condition"].values())
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=20, help="noise draws per (f_beta, condition)")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    from descatter import infer_e1 as inf
    from descatter import physics as ph

    sigma = ph.sigma_for_radius(A_CONTROL_UM)
    jobs = [
        {"control": name, "f_beta": f, "a_um": A_CONTROL_UM, "sigma": sigma,
         "condition": cond, "seed": 5000 + 1000 * i + s,
         "fix_a": spec["fix_a"], "inert": spec["inert"]}
        for i, (name, spec) in enumerate(CONTROLS.items())
        for cond in CONDITIONS
        for f in (0.0, 1.0)
        for s in range(args.draws)
    ]

    config = {
        "redesign": "docs/EXPERIMENTS.md E1, Redesign 2026-11-06",
        "a_control_um": A_CONTROL_UM,
        "sigma_AU": sigma,
        "sigma_rule": "sigma(a) = D(a) / 295 (results/e1/sigma_table.json)",
        "draws_per_cell": args.draws,
        "draws_per_condition": 2 * args.draws,
        "nlive": NLIVE, "n_workers": N_WORKERS, "n_jobs": len(jobs),
        "preprocessed_likelihood": inf.PREPROCESSED_LIKELIHOOD,
        "prior_bounds": {k: list(v) for k, v in inf.PRIOR_BOUNDS.items()},
    }
    print(f"{len(jobs)} nested-sampling runs on {N_WORKERS} workers, sigma = {sigma:.4e} AU",
          flush=True)

    with Run("e1", "controls", config=config, seeds={"base": 5000}) as run:
        run.add_data_file(OUT / "sigma_table.json")
        run.add_data_file(OUT / "likelihood_calibration.json")

        t0 = time.perf_counter()
        ctx = mp.get_context("spawn")
        with ctx.Pool(N_WORKERS) as pool:
            runs = []
            for i, r in enumerate(pool.imap_unordered(_worker, jobs), 1):
                runs.append(r)
                if i % 20 == 0 or i == len(jobs):
                    print(f"  {i}/{len(jobs)}  elapsed {(time.perf_counter()-t0)/60:.1f} min",
                          flush=True)
        wall = time.perf_counter() - t0
        for r in runs:
            r.update({k: r["job"][k] for k in ("control", "f_beta", "a_um", "inert", "fix_a")})

        summaries = {name: _summarise([r for r in runs if r["control"] == name], name)
                     for name in CONTROLS}
        gate = json.loads((OUT / "likelihood_calibration.json").read_text())
        machinery_valid = (
            gate["GATE_PASSES"] and summaries["positive"]["PASS"] and summaries["negative"]["PASS"]
        )

        report = {
            "experiment": "E1",
            "step": "3, redesigned controls (the step-4 grid was NOT run)",
            "experiments_md_status_at_run_time": "DRAFT",
            "config": config,
            "likelihood_calibration_gate": gate["GATE_PASSES"],
            "positive_control": summaries["positive"],
            "negative_control": summaries["negative"],
            "free_a_observation": summaries["free_a"],
            "MACHINERY_VALID": bool(machinery_valid),
            "timing": {
                "wall_s_total": round(wall, 1),
                **{f"wall_s_median_{c}": float(np.median(
                    [r["wall_s"] for r in runs if r["condition"] == c])) for c in CONDITIONS},
            },
            "runs": [{k: v for k, v in r.items() if k != "job"} for r in runs],
        }
        (OUT / "controls.json").write_text(json.dumps(report, indent=2) + "\n")
        _figure(summaries, runs, sigma)
        run.notes["machinery_valid"] = bool(machinery_valid)

    print("\n" + "=" * 76)
    for name in ("positive", "negative", "free_a"):
        s = summaries[name]
        tag = ("PASS" if s.get("PASS") else "FAIL") if s["thresholded"] else "observation"
        print(f"{name.upper():9s} ({s['criterion']}): {tag}")
        for cond, v in s["per_condition"].items():
            print(f"  {cond:14s} W med {v['W_median']:.4f} max {v['W_max']:.4f} "
                  f"frac<0.05 {v['frac_W_below_0.05']:.2f} | KS med {v['ks_median']:.4f} "
                  f"frac<0.1 {v['frac_ks_below_0.1']:.2f} | a med {v['a_median_um_median']:.2f} "
                  f"| min samples {v['min_posterior_samples']}")
    print(f"\ncalibration gate: {'PASS' if gate['GATE_PASSES'] else 'FAIL'}")
    print(f"MACHINERY VALID: {machinery_valid}")
    print(f"total wall {wall/60:.1f} min over {len(runs)} runs")


def _figure(summaries: dict, runs: list[dict], sigma: float) -> None:
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.8), constrained_layout=True)
    for i, name in enumerate(("positive", "negative", "free_a")):
        s = summaries[name]
        metric = "ks_f_beta_vs_uniform_prior" if name == "negative" else "wrong_mode_mass_W"
        line = 0.1 if name == "negative" else 0.05
        for j, cond in enumerate(CONDITIONS):
            v = [r[metric] for r in runs if r["control"] == name and r["condition"] == cond]
            ax[i].scatter(np.full(len(v), j) + np.linspace(-0.18, 0.18, len(v)), v,
                          s=16, alpha=0.75, label=cond)
        ax[i].axhline(line, color="C3", ls="--", lw=1,
                      label=("KS = 0.1" if name == "negative" else "W = 0.05"))
        ax[i].set_xticks([0, 1], list(CONDITIONS))
        ax[i].set_ylabel("KS vs prior" if name == "negative" else "wrong-mode mass W")
        ax[i].set_ylim(-0.03, 1.03)
        tag = ("PASS" if s.get("PASS") else "FAIL") if s["thresholded"] else "observation only"
        sub = {"positive": "a fixed at truth", "negative": "f$_\\beta$ inert",
               "free_a": "a free — confounded with H1"}[name]
        ax[i].set_title(f"{name} — {tag}\n{sub}")
        ax[i].legend(fontsize=8, loc="upper right")
    fig.suptitle(f"E1 controls, redesigned 2026-11-06, at a = 0.25 µm, "
                 f"$\\sigma$ = {sigma:.3e} AU (tissue SNR)", fontsize=11)
    fig.savefig(OUT / "controls.png", dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(v, "1")
    main()
