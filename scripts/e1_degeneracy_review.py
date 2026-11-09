"""REVIEW ONLY for the QUEUED request 02; nothing in the repo is modified.

The H1 confusion is 'alpha + large scatterer' vs 'beta + small scatterer'.
This minimises chi^2 between the f_beta=0 truth and the WHOLE f_beta=1 model
family -- a', n_inf', phi', amplitude, plus the linear nuisance terms -- under
the proposed sigma(a) = D(a)/295. W can only be large where this is O(1).
"""

import json
import multiprocessing as mp
import os
import sys

import numpy as np
import torch
from scipy.optimize import minimize

from descatter import infer_e1 as inf
from descatter import physics as ph

nu = ph.wavenumber_grid()
nun = nu.numpy()
SEL = (nun >= 1600) & (nun <= 1700)
PHI, SNR = 0.2, 295.0
#: "gauge" fixes n_inf' at 1.40 and uses the widened a'/amplitude bounds
#: (request 02 task 3); "legacy" is the seven-parameter box the first screen used.
GAUGE = os.environ.get("DEGEN_GAUGE", "1") == "1"
B = inf.PRIOR_BOUNDS_GAUGE if GAUGE else inf.PRIOR_BOUNDS_LEGACY


def sigma_of(a):
    k = ph.tissue_k(nu, 0.0, 1.0)
    A, _ = ph.apparent_absorbance(ph.qext_ada(nu, a, torch.ones_like(nu), k), PHI)
    return float(A[SEL].max()) / SNR


def spec(f, a, n_inf, phi, amp=1.0):
    with torch.no_grad():
        o = ph.forward(nu, ph.Theta(f_beta=f, a_um=a, n_inf=n_inf, phi=phi, amplitude=amp))
    return o["A_app"].numpy(), bool(o["valid"].all())


def rb(y):
    return (y - inf.rubberband_baseline(nun, y))[SEL]


def cost(p, y_true, s, cond, t_pp):
    a, n_inf, phi, amp = p
    if GAUGE:
        n_inf = inf.N_INF_GAUGE          # a choice of coordinates, not a restriction
    if not (
        B["a_um"][0] <= a <= B["a_um"][1]
        and B["n_inf"][0] <= n_inf <= B["n_inf"][1]
        and B["phi"][0] <= phi <= B["phi"][1]
        and B["amplitude"][0] <= amp <= B["amplitude"][1]
    ):
        return 1e18
    y, ok = spec(1.0, a, n_inf, phi, amp)
    if not ok:
        return 1e18
    if cond == "raw":
        A = np.column_stack([y, np.ones_like(y), (nun - nun.mean()) / 1000])
        t = y_true
    else:
        w = rb(y)
        A = np.column_stack([w, np.ones_like(w)])
        t = t_pp
    r = t - A @ np.linalg.lstsq(A, t, rcond=None)[0]
    return float(r @ r / s**2)


def job(args):
    a_t, cond = args
    s = sigma_of(a_t)
    y0, _ = spec(0.0, a_t, 1.40, PHI)
    t_pp = rb(y0)
    best = (np.inf, None)
    a_lo, a_hi = B["a_um"]
    n_scan = (inf.N_INF_GAUGE,) if GAUGE else (1.30, 1.40, 1.50, 1.60)
    for a2 in np.arange(a_lo, a_hi + 1e-9, (a_hi - a_lo) / 32.0):
        for ni in n_scan:
            for ph_ in (0.05, 0.15, 0.30):
                c = cost([a2, ni, ph_, 1.0], y0, s, cond, t_pp)
                if c < best[0]:
                    best = (c, [a2, ni, ph_, 1.0])
    for _ in range(3):
        r = minimize(
            cost,
            best[1],
            args=(y0, s, cond, t_pp),
            method="Nelder-Mead",
            options={"maxiter": 1500, "xatol": 1e-4, "fatol": 1e-3},
        )
        if r.fun < best[0]:
            best = (float(r.fun), list(r.x))
    return a_t, cond, best[0], best[1], s


if __name__ == "__main__":
    cells = [(a, c) for a in (0.25, 1, 2, 3, 3.5, 4, 5, 6) for c in ("raw", "preprocessed")]
    with mp.get_context("spawn").Pool(14) as pool:
        res = pool.map(job, cells)
    d = {(a, c): (v, p, s) for a, c, v, p, s in res}

    if len(sys.argv) > 1:
        from descatter.provenance import REPO_ROOT
        old = json.loads((REPO_ROOT / "results/e1/degeneracy_review.json").read_text())
        old_by_a = {r["a_um"]: r for r in old["per_radius"]}
        rows = []
        for a in (0.25, 1, 2, 3, 3.5, 4, 5, 6):
            o = old_by_a[a]
            row = {"a_um": a, "sigma_AU": d[(a, "raw")][2]}
            for c, key in (("raw", "min_chi2_raw"), ("preprocessed", "min_chi2_preprocessed")):
                new_v, params, _ = d[(a, c)]
                row[c] = {
                    "min_chi2_new": new_v, "min_chi2_old": o[key],
                    "ratio_new_over_old": new_v / o[key],
                    "fell_by_more_than_10pc": bool(new_v < 0.9 * o[key]),
                    "best_a_prime_um": params[0], "best_phi_prime": params[2],
                    "snr_at_which_confusion_appears": o["D_AU"] / (
                        d[(a, c)][2] * np.sqrt(new_v / 9.0)),
                }
            rows.append(row)
        report = {
            "task": "request 02 task 3: degeneracy screen under the gauge-fixed bounds",
            "gauge": GAUGE,
            "bounds": {k: list(v) for k, v in B.items()},
            "compared_with": "results/e1/degeneracy_review.json (138265b, legacy bounds)",
            "any_radius_fell_by_more_than_10pc": bool(any(
                row[c]["fell_by_more_than_10pc"] for row in rows
                for c in ("raw", "preprocessed"))),
            "per_radius": rows,
        }
        (REPO_ROOT / "results/e1" / sys.argv[1]).write_text(json.dumps(report, indent=2) + "\n")
        print(f"\nwrote results/e1/{sys.argv[1]}")
        print(f"{'a/um':>6} | {'raw new':>10} {'raw old':>10} {'ratio':>7} "
              f"| {'pp new':>10} {'pp old':>10} {'ratio':>7}")
        for row in rows:
            r, pp = row["raw"], row["preprocessed"]
            flag = "  <10%!" if (r["fell_by_more_than_10pc"] or pp["fell_by_more_than_10pc"]) else ""
            print(f"{row['a_um']:6.2f} | {r['min_chi2_new']:10.3g} {r['min_chi2_old']:10.3g} "
                  f"{r['ratio_new_over_old']:7.3f} | {pp['min_chi2_new']:10.3g} "
                  f"{pp['min_chi2_old']:10.3g} {pp['ratio_new_over_old']:7.3f}{flag}")
    print("min chi^2 between the f_beta=0 truth and the WHOLE f_beta=1 family")
    print("(a', n_inf', phi', amplitude, scale and baseline all profiled), sigma(a)=D(a)/295\n")
    print(
        f"{'a_true':>7} {'sigma/AU':>10} | {'raw min chi2':>13} {'a*':>6} {'n*':>5} {'phi*':>5}"
        f" | {'pp min chi2':>12} {'a*':>6} {'n*':>5} {'phi*':>5}"
    )
    for a in (0.25, 1, 2, 3, 3.5, 4, 5, 6):
        vr, pr, s = d[(a, "raw")]
        vp, pp_, _ = d[(a, "preprocessed")]
        # under the gauge n_inf is forced to N_INF_GAUGE inside cost(), so the
        # optimiser's own n_inf coordinate is a dead dimension and drifts freely.
        # Print what was actually used, not that drifting value.
        nr = inf.N_INF_GAUGE if GAUGE else pr[1]
        npp = inf.N_INF_GAUGE if GAUGE else pp_[1]
        print(
            f"{a:7.2f} {s:10.3e} | {vr:13.3g} {pr[0]:6.2f} {nr:5.2f} {pr[2]:5.2f}"
            f" | {vp:12.3g} {pp_[0]:6.2f} {npp:5.2f} {pp_[2]:5.2f}"
        )
    print("\nchi^2 = 9 is 3 sigma. W is only large where this is of order 1.")
