"""E1 step 3, redefined 2026-11-24: the sampler cross-check (request 03 tasks 1-2).

The original 31 x 31 (f_beta, a) grid over the full prior cannot resolve
posteriors this sharp -- f_beta SD is about 0.001 and the a interval about
0.005 um wide. So the cross-check is now two 1-D profile likelihoods per case,
each profiled over every other free parameter by multi-start optimisation, and
compared with what dynesty found on the same data with the same seed.

Three cases, both conditions, each the first noise draw of its grid cell:
  (0.25 um, f_beta 0), (3.5 um, f_beta 1), (5 um, f_beta 0).

Passes if, in every comparison:
  1. the sampler's best log-likelihood is within 2 of the optimiser's maximum;
  2. the sampler's 90 % a interval matches the profile interval
     (delta(-2 log L) <= 2.706) to within 20 % of the profile width, in both
     centre and width;
  3. W < 0.01 wherever the best wrong-side f_beta is more than 20 above the
     minimum in -2 log L. The gap is reported in every case.

**If any comparison fails, the grid must not run.**

Run:  OMP_NUM_THREADS=1 .venv/bin/python -m scripts.e1_crosscheck [--smoke]
Writes results/e1/crosscheck/{crosscheck.json,crosscheck.png,run.json}.
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
from scripts.e1_grid_config import (
    BOUND,
    CONDITIONS,
    CROSSCHECK_CASES,
    N_WORKERS,
    NLIVE,
    SAMPLE,
    grid_seed,
)

OUT = REPO_ROOT / "results" / "e1" / "crosscheck"
N_F_POINTS = 101
N_A_POINTS = 51
A_WIDEN = 5.0  # the sampler's 90 % interval widened to 5x its half-width each side
CHI2_90_1DOF = 2.706


def _profile(problem, free_idx: int, values: np.ndarray, x_map: np.ndarray) -> np.ndarray:
    """-2 log L profiled over every free parameter except ``free_idx``.

    Swept outward from the point nearest the MAP in both directions, warm-starting
    each optimisation from its neighbour's solution (continuation) with the MAP as
    a fallback start. That is what makes a profile this sharp tractable.
    """
    from scipy.optimize import minimize

    names = problem.free_names
    others = [i for i in range(len(names)) if i != free_idx]
    bounds = [problem.bounds[names[i]] for i in others]

    def nll(sub: np.ndarray, fixed_val: float) -> float:
        full = np.empty(len(names))
        full[free_idx] = fixed_val
        full[others] = sub
        ll = problem.loglike(full)
        return -2.0 * ll if ll > problem.REJECT / 2 else 1e18

    out = np.full(values.size, np.nan)
    start_map = x_map[others].copy()
    order = np.argsort(np.abs(values - x_map[free_idx]))  # nearest the MAP first

    warm: dict[int, np.ndarray] = {}
    for k in order:
        starts = [start_map]
        for nb in (k - 1, k + 1):
            if nb in warm:
                starts.insert(0, warm[nb])
        best, best_x = np.inf, None
        for s0 in starts[:2]:
            r = minimize(nll, np.clip(s0, [b[0] for b in bounds], [b[1] for b in bounds]),
                         args=(values[k],), method="Nelder-Mead", bounds=bounds,
                         options={"maxiter": 2000, "xatol": 1e-7, "fatol": 1e-4})
            if r.fun < best:
                best, best_x = float(r.fun), r.x
        out[k] = best
        warm[k] = best_x
    return out


def _interval_from_profile(values: np.ndarray, chi2: np.ndarray) -> tuple[float, float]:
    """Where the profile is within CHI2_90_1DOF of its minimum, by linear
    interpolation on the crossing points."""
    rel = chi2 - np.nanmin(chi2)
    inside = rel <= CHI2_90_1DOF
    if not inside.any():
        return (np.nan, np.nan)
    i0, i1 = int(np.argmax(inside)), int(len(inside) - 1 - np.argmax(inside[::-1]))

    def cross(lo: int, hi: int) -> float:
        if lo < 0 or hi >= len(values) or rel[hi] == rel[lo]:
            return float(values[max(0, min(lo, len(values) - 1))])
        t = (CHI2_90_1DOF - rel[lo]) / (rel[hi] - rel[lo])
        return float(values[lo] + t * (values[hi] - values[lo]))

    lo = float(values[0]) if i0 == 0 else cross(i0, i0 - 1)
    hi = float(values[-1]) if i1 == len(values) - 1 else cross(i1, i1 + 1)
    return (lo, hi)


def _worker(job: dict) -> dict:
    import torch

    torch.set_num_threads(1)
    import dynesty

    from descatter import infer_e1 as inf
    from descatter import physics as ph

    a_um, f_beta, cond, seed = job["a_um"], job["f_beta"], job["condition"], job["seed"]
    sigma = ph.sigma_for_radius(a_um)
    theta = ph.Theta(f_beta=f_beta, a_um=a_um, n_inf=inf.N_INF_GAUGE,
                     phi=ph.SIGMA_PHI, amplitude=1.0)
    sim = ph.simulate(ph.wavenumber_grid(), theta, sigma=sigma, seed=seed)
    problem = inf.E1Problem(
        nu=ph.wavenumber_grid(), data=sim["y"].numpy(), sigma=sigma, condition=cond,
        truth={k: getattr(theta, k) for k in inf.PARAM_NAMES},
    )
    problem.REJECT = inf.REJECT_LOGL

    # ---- the sampler, exactly as the grid will run it ----
    t0 = time.perf_counter()
    sampler = dynesty.NestedSampler(
        problem.loglike, problem.prior_transform, len(problem.free_names),
        nlive=NLIVE, rstate=np.random.default_rng(seed), bound=BOUND, sample=SAMPLE,
    )
    sampler.run_nested(dlogz=0.5, print_progress=False)
    res = sampler.results
    eq = res.samples_equal(rstate=np.random.default_rng(seed + 1))
    wall_sampler = time.perf_counter() - t0

    i_f = problem.free_names.index("f_beta")
    i_a = problem.free_names.index("a_um")
    f_post, a_post = eq[:, i_f], eq[:, i_a]
    a_lo, a_hi = float(np.percentile(a_post, 5)), float(np.percentile(a_post, 95))
    W = float((f_post < 0.5).mean()) if f_beta >= 0.5 else float((f_post > 0.5).mean())
    k_best = int(np.argmax(res.logl))
    x_map = np.asarray(res.samples[k_best], dtype=float)
    ll_sampler = float(res.logl[k_best])

    # ---- the profiles ----
    t1 = time.perf_counter()
    f_vals = np.linspace(0.0, 1.0, N_F_POINTS)
    f_chi2 = _profile(problem, i_f, f_vals, x_map)

    half = max((a_hi - a_lo) / 2.0, 1e-9)
    centre = 0.5 * (a_lo + a_hi)
    lo_b, hi_b = problem.bounds["a_um"]
    a_vals = np.linspace(max(lo_b, centre - A_WIDEN * half),
                         min(hi_b, centre + A_WIDEN * half), N_A_POINTS)
    a_chi2 = _profile(problem, i_a, a_vals, x_map)
    wall_profile = time.perf_counter() - t1

    ll_opt = float(-0.5 * min(np.nanmin(f_chi2), np.nanmin(a_chi2)))
    p_lo, p_hi = _interval_from_profile(a_vals, a_chi2)

    # criterion 3: how far above the minimum is the best WRONG-side f_beta?
    rel_f = f_chi2 - np.nanmin(f_chi2)
    wrong = f_vals < 0.5 if f_beta >= 0.5 else f_vals > 0.5
    wrong_gap = float(np.nanmin(rel_f[wrong])) if wrong.any() else float("nan")

    return {
        "a_um": a_um, "f_beta_true": f_beta, "condition": cond, "seed": seed,
        "sigma_AU": sigma,
        "sampler": {
            "best_loglike": ll_sampler, "logz": float(res.logz[-1]),
            "a_q05_q95": [a_lo, a_hi], "a_centre": centre, "a_width": a_hi - a_lo,
            "W": W, "f_beta_sd": float(f_post.std(ddof=1)),
            "n_samples": int(eq.shape[0]), "wall_s": round(wall_sampler, 1),
        },
        "profile": {
            "best_loglike": ll_opt,
            "a_interval": [p_lo, p_hi], "a_centre": 0.5 * (p_lo + p_hi),
            "a_width": p_hi - p_lo,
            "wrong_side_f_beta_gap_in_2logL": wrong_gap,
            "f_values": f_vals.tolist(), "f_chi2": f_chi2.tolist(),
            "a_values": a_vals.tolist(), "a_chi2": a_chi2.tolist(),
            "wall_s": round(wall_profile, 1),
        },
    }


def _judge(r: dict) -> dict:
    s, p = r["sampler"], r["profile"]
    d_ll = abs(s["best_loglike"] - p["best_loglike"])
    pw = p["a_width"]
    centre_ok = abs(s["a_centre"] - p["a_centre"]) <= 0.20 * pw if pw > 0 else False
    width_ok = abs(s["a_width"] - pw) <= 0.20 * pw if pw > 0 else False
    gap = p["wrong_side_f_beta_gap_in_2logL"]
    w_applies = bool(gap > 20.0)
    w_ok = (s["W"] < 0.01) if w_applies else True
    return {
        "loglike_gap": d_ll, "loglike_within_2": bool(d_ll <= 2.0),
        "a_centre_abs_diff": abs(s["a_centre"] - p["a_centre"]),
        "a_width_abs_diff": abs(s["a_width"] - pw),
        "a_tolerance_20pc_of_profile_width": 0.20 * pw,
        "a_centre_ok": bool(centre_ok), "a_width_ok": bool(width_ok),
        "wrong_side_gap": gap, "W_criterion_applies": w_applies,
        "W": s["W"], "W_ok": bool(w_ok),
        "PASS": bool(d_ll <= 2.0 and centre_ok and width_ok and w_ok),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="one case, one condition")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    cases = CROSSCHECK_CASES[:1] if args.smoke else CROSSCHECK_CASES
    conds = CONDITIONS[1:] if args.smoke else CONDITIONS
    jobs = [
        {"a_um": c["a_um"], "f_beta": c["f_beta"], "condition": cond,
         "seed": grid_seed(c["a_um"], c["f_beta"], 0)}
        for c in cases for cond in conds
    ]
    print(f"{len(jobs)} cross-check runs on {min(N_WORKERS, len(jobs))} workers", flush=True)

    with Run("e1", "crosscheck",
             config={"step": "E1 step 3, redefined 2026-11-24",
                     "cases": cases, "conditions": list(conds),
                     "n_f_points": N_F_POINTS, "n_a_points": N_A_POINTS,
                     "a_widen": A_WIDEN, "chi2_90_1dof": CHI2_90_1DOF,
                     "nlive": NLIVE, "sample": SAMPLE, "bound": BOUND,
                     "seeds": [j["seed"] for j in jobs]},
             seeds={"from": "scripts/e1_grid_config.grid_seed, draw 0"}) as run:
        t0 = time.perf_counter()
        ctx = mp.get_context("spawn")
        with ctx.Pool(min(N_WORKERS, len(jobs))) as pool:
            res = []
            for i, r in enumerate(pool.imap_unordered(_worker, jobs), 1):
                res.append(r)
                print(f"  {i}/{len(jobs)}  {(time.perf_counter()-t0)/60:.1f} min", flush=True)
        wall = time.perf_counter() - t0

        for r in res:
            r["verdict"] = _judge(r)
        res.sort(key=lambda r: (r["a_um"], r["condition"]))
        all_pass = all(r["verdict"]["PASS"] for r in res)

        report = {
            "step": "E1 step 3 cross-check, redefined 2026-11-24",
            "criteria": {
                "1": "sampler best log-likelihood within 2 of the optimiser's maximum",
                "2": "sampler 90 % a interval matches the profile interval "
                     "(delta(-2 log L) <= 2.706) to within 20 % of the profile width, "
                     "in centre and width",
                "3": "W < 0.01 wherever the best wrong-side f_beta is more than 20 above "
                     "the minimum in -2 log L",
            },
            "ALL_PASS": all_pass,
            "grid_may_run": all_pass,
            "wall_s_total": round(wall, 1),
            "comparisons": res,
        }
        (OUT / "crosscheck.json").write_text(json.dumps(report, indent=2) + "\n")
        _figure(res)
        run.notes["ALL_PASS"] = all_pass

    print("\n" + "=" * 92)
    print(f"{'a/um':>6} {'f_b':>4} {'condition':>13} | {'dlogL':>8} {'a centre d':>11} "
          f"{'a width d':>10} {'tol':>9} | {'gap':>9} {'W':>7} | verdict")
    for r in res:
        v = r["verdict"]
        print(f"{r['a_um']:6.2f} {r['f_beta_true']:4.0f} {r['condition']:>13} | "
              f"{v['loglike_gap']:8.3f} {v['a_centre_abs_diff']:11.3e} "
              f"{v['a_width_abs_diff']:10.3e} {v['a_tolerance_20pc_of_profile_width']:9.3e} | "
              f"{v['wrong_side_gap']:9.1f} {v['W']:7.4f} | "
              f"{'PASS' if v['PASS'] else 'FAIL'}")
    print(f"\nALL_PASS: {all_pass}   ->  grid {'may' if all_pass else 'must NOT'} run")
    print(f"total wall {wall/60:.1f} min")


def _figure(res: list[dict]) -> None:
    n = len(res)
    fig, ax = plt.subplots(2, n, figsize=(3.3 * n, 7.2), constrained_layout=True, squeeze=False)
    for j, r in enumerate(res):
        s, p = r["sampler"], r["profile"]
        f_vals, f_chi2 = np.array(p["f_values"]), np.array(p["f_chi2"])
        ax[0, j].plot(f_vals, f_chi2 - np.nanmin(f_chi2), lw=1.2)
        ax[0, j].axvline(r["f_beta_true"], color="C2", ls="-", lw=1.2, label="truth")
        ax[0, j].axvline(0.5, color="k", ls=":", lw=0.9)
        ax[0, j].axhline(20.0, color="C3", ls="--", lw=1, label="gap = 20")
        ax[0, j].set_yscale("symlog", linthresh=1.0)
        ax[0, j].set_xlabel(r"$f_\beta$")
        ax[0, j].set_ylabel(r"$\Delta(-2\log L)$")
        ax[0, j].set_title(f"a={r['a_um']} µm, $f_\\beta$={r['f_beta_true']:.0f}\n"
                           f"{r['condition']}", fontsize=9)
        ax[0, j].legend(fontsize=7)

        a_vals, a_chi2 = np.array(p["a_values"]), np.array(p["a_chi2"])
        ax[1, j].plot(a_vals, a_chi2 - np.nanmin(a_chi2), lw=1.2, label="profile")
        ax[1, j].axhline(CHI2_90_1DOF, color="C3", ls="--", lw=1, label="2.706")
        ax[1, j].axvspan(*s["a_q05_q95"], color="C0", alpha=0.25, lw=0, label="sampler 90 %")
        ax[1, j].axvspan(*p["a_interval"], color="C1", alpha=0.25, lw=0, label="profile 90 %")
        ax[1, j].axvline(r["a_um"], color="C2", lw=1.2, label="truth")
        ax[1, j].set_ylim(0, 12)
        ax[1, j].set_xlabel("a / µm")
        ax[1, j].set_ylabel(r"$\Delta(-2\log L)$")
        ax[1, j].set_title("PASS" if r["verdict"]["PASS"] else "FAIL", fontsize=9)
        ax[1, j].legend(fontsize=6)
    fig.suptitle("E1 sampler cross-check: 1-D profile likelihoods against dynesty", fontsize=11)
    fig.savefig(OUT / "crosscheck.png", dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    for v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(v, "1")
    main()
