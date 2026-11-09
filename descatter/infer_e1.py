"""E1 step 3: posterior inference on one simulated spectrum, two conditions.

theta = (f_beta, a_um, n_inf, phi, amplitude, baseline_offset, baseline_slope),
all with uniform priors; dynesty nested sampling, because the posterior is
expected to be multimodal in (f_beta, a).

Conditions, on identical simulated data:

(i)  ``raw``           -- likelihood on the apparent absorbance over 950-1800 cm^-1.
(ii) ``preprocessed``  -- rubberband baseline over 950-1800, cut to 1600-1700;
     the same operations are applied to the model, which is then fitted with a
     free scale and offset.

Condition (ii) was redesigned on 2026-11-06 after the first controls failed:
the window is fitted as ``s * m_w + c0`` with ``s`` and ``c0`` profiled out,
instead of being vector-normalised with ``sigma_pp = sigma / ||y_w||``. See
``PREPROCESSED_LIKELIHOOD``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np
import torch

from descatter import physics as ph

PREPROCESSED_LIKELIHOOD = (
    "rubberband (lower convex hull) over 950-1800 cm^-1, then cut to 1600-1700; "
    "y_w ~ N(s * m_w + c0, sigma^2 I) with s and c0 profiled out by linear least "
    "squares at every call and sigma exact. Pre-registered in docs/EXPERIMENTS.md "
    "E1 step 3 (redesign 2026-11-06). This replaces vector normalisation with "
    "sigma_pp = sigma / ||y_w||, whose effective sigma saturated at ~0.049 AU "
    "under heavy noise and which was biased by the rubberband lifting noisy data "
    "by +2.1 sigma (results/e1/superseded_phi_0.05_0.90/, 810bba6)."
)

#: Uniform priors. f_beta, a, n_inf and phi are pre-registered; the amplitude and
#: baseline ranges are only "wide" in the draft, so they are fixed here.
#: phi was narrowed to [0.05, 0.30] on 2026-11-06 (Chris, relayed by mac): the
#: old upper bound of 0.9 was mostly unreachable, because A_app needs
#: phi * Q_ext < 1 and Q_ext peaks near 3.2, and the resulting rejection put a
#: non-uniform effective prior on the radius at exactly the H1 radii.
PARAM_NAMES = (
    "f_beta",
    "a_um",
    "n_inf",
    "phi",
    "amplitude",
    "baseline_offset",
    "baseline_slope",
)
PRIOR_BOUNDS: dict[str, tuple[float, float]] = {
    "f_beta": (0.0, 1.0),
    "a_um": (0.25, 8.0),
    "n_inf": (1.30, 1.60),
    "phi": (0.05, 0.30),  # narrowed from 0.9 on 2026-11-06; see the phi note in E1
    "amplitude": (0.2, 3.0),
    "baseline_offset": (-0.5, 0.5),
    "baseline_slope": (-1.0, 1.0),  # AU per 1000 cm^-1
}

AMIDE_I_WINDOW = (1600.0, 1700.0)
REJECT_LOGL = -1e100


# --------------------------------------------------------------------------
# Preprocessing (condition ii)
# --------------------------------------------------------------------------
def rubberband_baseline(nu: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Lower convex hull of ``(nu, y)``, linearly interpolated onto ``nu``.

    Monotone chain over points sorted by ``nu``; O(n).
    """
    hull: list[int] = []
    for i in range(len(nu)):
        while len(hull) >= 2:
            i1, i2 = hull[-2], hull[-1]
            # drop i2 if it sits on or above the line i1 -> i
            cross = (nu[i2] - nu[i1]) * (y[i] - y[i1]) - (nu[i] - nu[i1]) * (y[i2] - y[i1])
            if cross <= 0:
                hull.pop()
            else:
                break
        hull.append(i)
    h = np.asarray(hull)
    return np.interp(nu, nu[h], y[h])


@dataclass
class Preprocessor:
    """Condition (ii): rubberband over the full range, then cut to the window.

    No normalisation: the free scale ``s`` in the likelihood carries what vector
    normalisation used to, and keeps sigma exact.
    """

    nu: np.ndarray
    window: tuple[float, float] = AMIDE_I_WINDOW

    def __post_init__(self) -> None:
        self.sel = (self.nu >= self.window[0]) & (self.nu <= self.window[1])

    def __call__(self, y: np.ndarray) -> np.ndarray:
        return (y - rubberband_baseline(self.nu, y))[self.sel]


def profile_scale_offset(target: np.ndarray, model: np.ndarray) -> tuple[np.ndarray, float, float]:
    """Least-squares fit of ``target ~ s * model + c0``.

    Returns ``(residual, s, c0)``. ``s`` is unconstrained, so it may be negative.
    """
    design = np.column_stack([model, np.ones_like(model)])
    coef, *_ = np.linalg.lstsq(design, target, rcond=None)
    return target - design @ coef, float(coef[0]), float(coef[1])


# --------------------------------------------------------------------------
# Likelihood
# --------------------------------------------------------------------------
@dataclass
class E1Problem:
    """One simulated spectrum plus one likelihood condition."""

    nu: torch.Tensor
    data: np.ndarray
    sigma: float
    condition: str = "raw"
    truth: dict | None = None
    #: parameters held at a fixed value instead of being sampled. Used by the
    #: redesigned positive control (a fixed) and by labelled diagnostics.
    fixed: dict[str, float] = field(default_factory=dict)
    #: negative control: make f_beta have no effect on the model at all.
    inert_f_beta: bool = False
    _pre: Preprocessor | None = field(default=None, init=False, repr=False)
    n_calls: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.condition not in ("raw", "preprocessed"):
            raise ValueError(self.condition)
        bad = set(self.fixed) - set(PARAM_NAMES)
        if bad:
            raise ValueError(f"unknown fixed parameters: {sorted(bad)}")
        self.free_names = tuple(n for n in PARAM_NAMES if n not in self.fixed)
        nu_np = self.nu.numpy()
        if self.condition == "preprocessed":
            self._pre = Preprocessor(nu_np)
            self.target = self._pre(self.data)
            self.n_profiled = 2  # s and c0
        else:
            self.target = self.data
            self.n_profiled = 0
        #: sigma is now exact in both conditions -- nothing rescales it
        self.sigma_eff = self.sigma
        self.n_data = int(self.target.size)
        #: degrees of freedom of chi^2 at the truth
        self.dof = self.n_data - self.n_profiled

    # -- dynesty hooks ----------------------------------------------------
    def prior_transform(self, u: np.ndarray) -> np.ndarray:
        out = np.empty_like(u)
        for i, name in enumerate(self.free_names):
            lo, hi = PRIOR_BOUNDS[name]
            out[i] = lo + u[i] * (hi - lo)
        return out

    def full_theta(self, theta_vec: Sequence[float]) -> dict[str, float]:
        values = dict(self.fixed)
        values.update(zip(self.free_names, (float(v) for v in theta_vec)))
        return {n: values[n] for n in PARAM_NAMES}

    def model(self, theta_vec: Sequence[float]) -> tuple[np.ndarray | None, bool]:
        th = ph.Theta(**self.full_theta(theta_vec), inert_f_beta=self.inert_f_beta)
        with torch.no_grad():
            out = ph.forward(self.nu, th)
        if not bool(out["valid"].all()):
            return None, False
        y = out["A_app"].numpy()
        if self._pre is not None:
            y = self._pre(y)
        return y, True

    def chi2(self, theta_vec: Sequence[float]) -> float | None:
        """chi^2 of the model against the data, with s and c0 profiled out in the
        preprocessed condition. ``None`` when the parameters are unphysical."""
        y, ok = self.model(theta_vec)
        if not ok:
            return None
        if self._pre is not None:
            resid, _, _ = profile_scale_offset(self.target, y)
        else:
            resid = self.target - y
        return float(np.dot(resid, resid) / self.sigma_eff**2)

    def loglike(self, theta_vec: Sequence[float]) -> float:
        self.n_calls += 1
        c2 = self.chi2(theta_vec)
        if c2 is None:
            return REJECT_LOGL
        return float(-0.5 * c2 - self.n_data * np.log(self.sigma_eff * np.sqrt(2 * np.pi)))


# --------------------------------------------------------------------------
# Sampling and metrics
# --------------------------------------------------------------------------
def run_nested(
    problem: E1Problem,
    nlive: int = 400,
    seed: int = 0,
    dlogz: float = 0.5,
    maxcall: int | None = None,
    print_progress: bool = False,
) -> dict:
    """dynesty nested sampling; returns equal-weight samples and E1's metrics."""
    import dynesty

    t0 = time.perf_counter()
    sampler = dynesty.NestedSampler(
        problem.loglike,
        problem.prior_transform,
        len(problem.free_names),
        nlive=nlive,
        rstate=np.random.default_rng(seed),
        bound="multi",
        sample="rwalk",
    )
    sampler.run_nested(dlogz=dlogz, maxcall=maxcall, print_progress=print_progress)
    res = sampler.results
    free = res.samples_equal(rstate=np.random.default_rng(seed + 1))
    wall = time.perf_counter() - t0

    # re-expand to the full 7-parameter layout so metrics() indexing is stable
    samples = np.empty((free.shape[0], len(PARAM_NAMES)))
    for i, name in enumerate(PARAM_NAMES):
        if name in problem.fixed:
            samples[:, i] = problem.fixed[name]
        else:
            samples[:, i] = free[:, problem.free_names.index(name)]

    out = metrics(samples, truth=problem.truth)
    out.update(
        {
            "condition": problem.condition,
            "logz": float(res.logz[-1]),
            "logz_err": float(res.logzerr[-1]),
            "wall_s": round(wall, 2),
            "n_loglike_calls": problem.n_calls,
            "nlive": nlive,
            "seed": seed,
            "n_data": problem.n_data,
            "sigma_eff": problem.sigma_eff,
            "fixed": dict(problem.fixed),
            "inert_f_beta": problem.inert_f_beta,
            "dof": problem.dof,
            "n_free_params": len(problem.free_names),
        }
    )
    return out | {"_samples": samples}


def metrics(samples: np.ndarray, truth: dict | None = None) -> dict:
    """E1 step 5 metrics from equal-weight posterior samples."""
    f = samples[:, PARAM_NAMES.index("f_beta")]
    a = samples[:, PARAM_NAMES.index("a_um")]
    f_true = None if truth is None else truth.get("f_beta")

    if f_true is None:
        wrong_mass = None
    elif f_true >= 0.5:
        wrong_mass = float((f < 0.5).mean())  # truth is beta, wrong side is alpha
    else:
        wrong_mass = float((f > 0.5).mean())

    return {
        "wrong_mode_mass_W": wrong_mass,
        "f_beta_mean": float(f.mean()),
        "f_beta_sd": float(f.std(ddof=1)),
        "f_beta_median": float(np.median(f)),
        "f_beta_q05_q95": [float(np.percentile(f, 5)), float(np.percentile(f, 95))],
        "ks_f_beta_vs_uniform_prior": ks_vs_uniform(f),
        "a_median_um": float(np.median(a)),
        "a_q05_q95_um": [float(np.percentile(a, 5)), float(np.percentile(a, 95))],
        "n_posterior_samples": int(samples.shape[0]),
        "truth": truth,
    }


def ks_vs_uniform(x: np.ndarray, lo: float = 0.0, hi: float = 1.0) -> float:
    """Kolmogorov-Smirnov distance between ``x`` and Uniform(lo, hi).

    The negative control passes when this is < 0.1 (docs/EXPERIMENTS.md E1).
    """
    from scipy.stats import kstest

    return float(kstest(x, "uniform", args=(lo, hi - lo)).statistic)


# --------------------------------------------------------------------------
# Convenience: simulate then infer
# --------------------------------------------------------------------------
def simulate_and_infer(
    theta_true: ph.Theta,
    sigma: float,
    condition: str,
    nu: torch.Tensor | None = None,
    seed: int = 0,
    nlive: int = 400,
    exact_mie: bool = False,
    fixed: dict[str, float] | None = None,
    **kwargs,
) -> dict:
    nu = ph.wavenumber_grid() if nu is None else nu
    sim = ph.simulate(nu, theta_true, sigma=sigma, seed=seed, exact_mie=exact_mie)
    problem = E1Problem(
        nu=nu,
        data=sim["y"].numpy(),
        sigma=sigma,
        condition=condition,
        truth={k: getattr(theta_true, k) for k in PARAM_NAMES},
        fixed=fixed or {},
        inert_f_beta=theta_true.inert_f_beta,
    )
    out = run_nested(problem, nlive=nlive, seed=seed, **kwargs)
    out["sigma_true"] = sigma
    out["exact_mie_data"] = exact_mie
    return out


def chi2_gap(
    theta_a: ph.Theta,
    theta_b: ph.Theta,
    sigma: float,
    nu: torch.Tensor | None = None,
    condition: str = "raw",
    profile: Callable[[np.ndarray, np.ndarray], np.ndarray] | None = None,
) -> float:
    """Noise-free chi^2 between two parameter settings, with amplitude and a
    linear baseline profiled out by least squares.

    This is the quantity the negative control has to kill: if the gap between
    f_beta = 0 and f_beta = 1 is much above 1, no amount of posterior width will
    make the f_beta posterior match the prior.
    """
    nu = ph.wavenumber_grid() if nu is None else nu
    with torch.no_grad():
        ya = ph.forward(nu, theta_a)["A_app"].numpy()
        yb = ph.forward(nu, theta_b)["A_app"].numpy()
    if condition == "preprocessed":
        pre = Preprocessor(nu.numpy())
        ya, norm = pre(ya)
        yb, _ = pre(yb)
        sigma = sigma / norm
        design = np.ones((ya.size, 1))
    else:
        x = (nu.numpy() - nu.numpy().mean()) / 1000.0
        design = np.column_stack([yb, np.ones_like(x), x])
    if profile is not None:
        design = profile(ya, yb)
    coef, *_ = np.linalg.lstsq(design, ya, rcond=None)
    resid = ya - design @ coef
    return float(np.dot(resid, resid) / sigma**2)
