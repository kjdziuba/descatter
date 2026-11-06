"""REVIEW ONLY for the QUEUED request 02; nothing in the repo is modified.

The H1 confusion is 'alpha + large scatterer' vs 'beta + small scatterer'.
This minimises chi^2 between the f_beta=0 truth and the WHOLE f_beta=1 model
family -- a', n_inf', phi', amplitude, plus the linear nuisance terms -- under
the proposed sigma(a) = D(a)/295. W can only be large where this is O(1).
"""

import multiprocessing as mp

import numpy as np
import torch
from scipy.optimize import minimize

from descatter import infer_e1 as inf
from descatter import physics as ph

nu = ph.wavenumber_grid()
nun = nu.numpy()
SEL = (nun >= 1600) & (nun <= 1700)
PHI, SNR = 0.2, 295.0
B = inf.PRIOR_BOUNDS


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
    for a2 in np.arange(0.25, 8.01, 0.25):
        for ni in (1.30, 1.40, 1.50, 1.60):
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
    print("min chi^2 between the f_beta=0 truth and the WHOLE f_beta=1 family")
    print("(a', n_inf', phi', amplitude, scale and baseline all profiled), sigma(a)=D(a)/295\n")
    print(
        f"{'a_true':>7} {'sigma/AU':>10} | {'raw min chi2':>13} {'a*':>6} {'n*':>5} {'phi*':>5}"
        f" | {'pp min chi2':>12} {'a*':>6} {'n*':>5} {'phi*':>5}"
    )
    for a in (0.25, 1, 2, 3, 3.5, 4, 5, 6):
        vr, pr, s = d[(a, "raw")]
        vp, pp_, _ = d[(a, "preprocessed")]
        print(
            f"{a:7.2f} {s:10.3e} | {vr:13.3g} {pr[0]:6.2f} {pr[1]:5.2f} {pr[2]:5.2f}"
            f" | {vp:12.3g} {pp_[0]:6.2f} {pp_[1]:5.2f} {pp_[2]:5.2f}"
        )
    print("\nchi^2 = 9 is 3 sigma. W is only large where this is of order 1.")
