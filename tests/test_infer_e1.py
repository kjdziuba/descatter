"""Tests for the E1 inference layer: preprocessing, likelihood and metrics."""

from __future__ import annotations

import numpy as np
import torch

from descatter import infer_e1 as inf
from descatter import physics as ph


# --------------------------------------------------------------------------
# Rubberband baseline
# --------------------------------------------------------------------------
def test_rubberband_of_a_line_is_that_line():
    nu = np.linspace(950.0, 1800.0, 441)
    y = 0.3 - 0.0002 * (nu - 950.0)
    assert np.allclose(inf.rubberband_baseline(nu, y), y, atol=1e-12)


def test_rubberband_lies_on_or_below_the_spectrum():
    nu = ph.wavenumber_grid().numpy()
    y = ph.forward(ph.wavenumber_grid(), ph.Theta(f_beta=0.4, a_um=3.0))["A_app"].numpy()
    base = inf.rubberband_baseline(nu, y)
    assert (base <= y + 1e-12).all()
    # and it touches at both ends, which is what makes it a hull
    assert abs(base[0] - y[0]) < 1e-12 and abs(base[-1] - y[-1]) < 1e-12


def test_rubberband_is_convex():
    nu = ph.wavenumber_grid().numpy()
    y = ph.forward(ph.wavenumber_grid(), ph.Theta(f_beta=0.0, a_um=4.0))["A_app"].numpy()
    slopes = np.diff(inf.rubberband_baseline(nu, y)) / np.diff(nu)
    assert (np.diff(slopes) >= -1e-9).all()


# --------------------------------------------------------------------------
# The preprocessed condition
# --------------------------------------------------------------------------
def _pre_of(theta: ph.Theta) -> np.ndarray:
    nu = ph.wavenumber_grid()
    pre = inf.Preprocessor(nu.numpy())
    return pre(ph.forward(nu, theta)["A_app"].numpy())


def test_preprocessing_removes_the_baseline_parameters_exactly():
    """Rubberband subtracts any constant and any line, so baseline_offset and
    baseline_slope cannot be identified in the preprocessed condition. Its
    effective dimension is 5, not 7 -- worth knowing before the step-4 grid.
    """
    base = _pre_of(ph.Theta(f_beta=0.4, a_um=3.0))
    shifted = _pre_of(ph.Theta(f_beta=0.4, a_um=3.0, baseline_offset=0.37))
    tilted = _pre_of(ph.Theta(f_beta=0.4, a_um=3.0, baseline_slope=-0.8))
    assert np.allclose(base, shifted, atol=1e-10)
    assert np.allclose(base, tilted, atol=1e-10)


def test_preprocessed_condition_keeps_sigma_exact():
    """The redesign drops sigma_pp = sigma / ||y_w||; sigma is now exact in both
    conditions, and the preprocessed cell loses 2 degrees of freedom to s and c0."""
    nu = ph.wavenumber_grid()
    sim = ph.simulate(nu, ph.Theta(f_beta=0.0, a_um=3.0), sigma=1.1e-3, seed=0)
    raw = inf.E1Problem(nu=nu, data=sim["y"].numpy(), sigma=1.1e-3, condition="raw")
    pre = inf.E1Problem(nu=nu, data=sim["y"].numpy(), sigma=1.1e-3, condition="preprocessed")
    assert raw.sigma_eff == 1.1e-3 and pre.sigma_eff == 1.1e-3
    assert raw.n_data == nu.numel() and raw.n_profiled == 0 and raw.dof == raw.n_data
    assert pre.n_data < raw.n_data  # only the 1600-1700 window survives
    assert pre.n_profiled == 2 and pre.dof == pre.n_data - 2


def test_profiled_chi2_is_invariant_to_affine_rescaling():
    """REQUIRED BY REQUEST 02 TASK 1. The profiled chi^2 must be unchanged by
    y_w -> alpha*y_w + beta with sigma scaled by alpha, because s and c0 absorb
    exactly that family. Checked on the window itself, where no hull is
    recomputed, so any alpha != 0 including negative ones must hold."""
    rng = np.random.default_rng(3)
    m_w = rng.normal(size=52)
    y_w = 1.7 * m_w - 0.3 + rng.normal(0, 0.05, 52)
    sigma = 0.05

    def chi2(t, mdl, s):
        r, _, _ = inf.profile_scale_offset(t, mdl)
        return float(r @ r / s**2)

    base = chi2(y_w, m_w, sigma)
    for alpha, beta in [(2.0, 0.0), (0.5, 0.0), (1.0, 0.37), (-3.0, -0.2), (7.5, 1.9)]:
        got = chi2(alpha * y_w + beta, m_w, abs(alpha) * sigma)
        assert np.isclose(got, base, rtol=1e-10), (alpha, beta)


def test_full_pipeline_chi2_is_invariant_to_positive_rescaling():
    """The same invariance through the whole condition, starting from the raw
    spectrum. Only alpha > 0 can hold here: the rubberband is a LOWER convex
    hull, so rb(-y) != -rb(y) and a negative scale turns it into an upper hull.
    That is correct behaviour, and it is why the task-1 test above works on the
    window rather than the spectrum."""
    nu = ph.wavenumber_grid()
    sim = ph.simulate(nu, ph.Theta(f_beta=0.3, a_um=3.0, n_inf=1.40, phi=0.2),
                      sigma=1.1e-3, seed=7)
    theta_vec = [0.3, 3.0, 1.40, 0.2, 1.0, 0.0, 0.0]
    base = inf.E1Problem(nu=nu, data=sim["y"].numpy(), sigma=1.1e-3,
                         condition="preprocessed").chi2(theta_vec)
    for alpha, beta in [(2.0, 0.0), (0.5, 0.0), (1.0, 0.37), (7.5, 1.9)]:
        scaled = inf.E1Problem(nu=nu, data=alpha * sim["y"].numpy() + beta,
                               sigma=alpha * 1.1e-3, condition="preprocessed")
        assert np.isclose(scaled.chi2(theta_vec), base, rtol=1e-8), (alpha, beta)

    nun = nu.numpy(); y = sim["y"].numpy()
    assert np.allclose(inf.rubberband_baseline(nun, 2 * y), 2 * inf.rubberband_baseline(nun, y))
    assert not np.allclose(inf.rubberband_baseline(nun, -y), -inf.rubberband_baseline(nun, y))


def test_profile_scale_offset_recovers_the_fit():
    rng = np.random.default_rng(0)
    m = rng.normal(size=60)
    r, s, c = inf.profile_scale_offset(2.5 * m - 0.4, m)
    assert np.isclose(s, 2.5) and np.isclose(c, -0.4) and np.allclose(r, 0.0, atol=1e-12)
    # s is unconstrained, so a negative scale is recoverable too
    _, s_neg, _ = inf.profile_scale_offset(-1.3 * m + 0.2, m)
    assert np.isclose(s_neg, -1.3)


# --------------------------------------------------------------------------
# Likelihood
# --------------------------------------------------------------------------
def test_loglike_peaks_at_the_truth():
    nu = ph.wavenumber_grid()
    truth = ph.Theta(f_beta=0.0, a_um=3.0, n_inf=1.40, phi=0.2, amplitude=1.0)
    sim = ph.simulate(nu, truth, sigma=1.1e-3, seed=3)
    p = inf.E1Problem(nu=nu, data=sim["y"].numpy(), sigma=1.1e-3, condition="raw")
    at_truth = p.loglike([0.0, 3.0, 1.40, 0.2, 1.0, 0.0, 0.0])
    for wrong in ([1.0, 3.0, 1.40, 0.2, 1.0, 0.0, 0.0], [0.0, 6.0, 1.40, 0.2, 1.0, 0.0, 0.0]):
        assert at_truth > p.loglike(wrong)


def test_loglike_rejects_unphysical_phi():
    nu = ph.wavenumber_grid()
    sim = ph.simulate(nu, ph.Theta(f_beta=0.0, a_um=3.0), sigma=1.1e-3, seed=0)
    p = inf.E1Problem(nu=nu, data=sim["y"].numpy(), sigma=1.1e-3, condition="raw")
    assert p.loglike([0.0, 4.0, 1.40, 0.89, 1.0, 0.0, 0.0]) == inf.REJECT_LOGL


def test_fixed_parameters_shrink_the_sampled_space():
    nu = ph.wavenumber_grid()
    sim = ph.simulate(nu, ph.Theta(f_beta=0.0, a_um=3.0), sigma=1.1e-3, seed=0)
    p = inf.E1Problem(
        nu=nu, data=sim["y"].numpy(), sigma=1.1e-3, condition="raw", fixed={"a_um": 3.0}
    )
    assert p.free_names == tuple(n for n in inf.PARAM_NAMES if n != "a_um")
    assert p.full_theta([0.2, 1.4, 0.2, 1.0, 0.0, 0.0])["a_um"] == 3.0
    assert p.loglike([0.0, 1.40, 0.2, 1.0, 0.0, 0.0]) > inf.REJECT_LOGL


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------
def test_wrong_mode_mass_counts_the_far_side_of_half():
    s = np.zeros((1000, len(inf.PARAM_NAMES)))
    s[:, inf.PARAM_NAMES.index("f_beta")] = np.linspace(0, 1, 1000)
    assert np.isclose(inf.metrics(s, truth={"f_beta": 1.0})["wrong_mode_mass_W"], 0.5, atol=0.01)
    assert np.isclose(inf.metrics(s, truth={"f_beta": 0.0})["wrong_mode_mass_W"], 0.5, atol=0.01)
    s[:, inf.PARAM_NAMES.index("f_beta")] = np.linspace(0.9, 1.0, 1000)
    assert inf.metrics(s, truth={"f_beta": 1.0})["wrong_mode_mass_W"] == 0.0
    assert inf.metrics(s, truth={"f_beta": 0.0})["wrong_mode_mass_W"] == 1.0


def test_ks_vs_uniform_is_small_for_a_uniform_sample():
    rng = np.random.default_rng(0)
    assert inf.ks_vs_uniform(rng.uniform(size=20_000)) < 0.02
    assert inf.ks_vs_uniform(rng.uniform(0.0, 0.3, size=20_000)) > 0.5


def test_chi2_gap_scales_as_one_over_sigma_squared():
    ta = ph.Theta(f_beta=0.0, a_um=0.25)
    tb = ph.Theta(f_beta=1.0, a_um=0.25)
    g1 = inf.chi2_gap(ta, tb, sigma=1.1e-3)
    g2 = inf.chi2_gap(ta, tb, sigma=1.1e-2)
    g3 = inf.chi2_gap(ta, tb, sigma=1.1e-1)
    assert np.isclose(g1 / g2, 100.0, rtol=1e-6)
    assert np.isclose(g2 / g3, 100.0, rtol=1e-6)
    # at the E0 noise level f_beta = 0 and 1 are far apart; at sigma x 100 --
    # the pre-registered negative control -- the gap is far below 1, so the
    # f_beta posterior there should indeed collapse onto the prior
    assert g1 > 100.0
    assert g3 < 0.1


def test_metrics_shapes():
    rng = np.random.default_rng(1)
    s = rng.uniform(size=(500, len(inf.PARAM_NAMES)))
    s[:, inf.PARAM_NAMES.index("a_um")] = rng.uniform(0.25, 8.0, 500)
    m = inf.metrics(s, truth={"f_beta": 1.0, "a_um": 3.0})
    assert set(m) >= {
        "wrong_mode_mass_W",
        "f_beta_sd",
        "ks_f_beta_vs_uniform_prior",
        "a_median_um",
        "a_q05_q95_um",
    }
    assert 0.25 <= m["a_median_um"] <= 8.0
    assert m["a_q05_q95_um"][0] <= m["a_median_um"] <= m["a_q05_q95_um"][1]


# --------------------------------------------------------------------------
# Inert f_beta (request 02 task 3) and the sigma(a) rule (task 2)
# --------------------------------------------------------------------------
def test_inert_f_beta_makes_the_model_identical_for_0_and_1():
    """REQUIRED BY REQUEST 02 TASK 3. In inert mode f_beta must have no effect
    on the spectrum at all, so the negative control's posterior has to
    reproduce the prior and any KS >= 0.1 is a bug."""
    nu = ph.wavenumber_grid()
    for a_um in (0.25, 3.5):
        a = ph.forward(nu, ph.Theta(f_beta=0.0, a_um=a_um, inert_f_beta=True))["A_app"]
        b = ph.forward(nu, ph.Theta(f_beta=1.0, a_um=a_um, inert_f_beta=True))["A_app"]
        c = ph.forward(nu, ph.Theta(f_beta=0.63, a_um=a_um, inert_f_beta=True))["A_app"]
        assert torch.equal(a, b) and torch.equal(a, c), a_um
    # and it is genuinely a mode, not a no-op: normally f_beta does change it
    n0 = ph.forward(nu, ph.Theta(f_beta=0.0, a_um=3.5))["A_app"]
    n1 = ph.forward(nu, ph.Theta(f_beta=1.0, a_um=3.5))["A_app"]
    assert not torch.allclose(n0, n1)


def test_inert_mode_matches_pure_alpha():
    """Inert mode is the alpha lineshape at full strength, not a blend."""
    nu = ph.wavenumber_grid()
    inert = ph.forward(nu, ph.Theta(f_beta=1.0, a_um=2.0, inert_f_beta=True))["A_app"]
    alpha = ph.forward(nu, ph.Theta(f_beta=0.0, a_um=2.0))["A_app"]
    assert torch.allclose(inert, alpha)


def test_inert_f_beta_likelihood_is_flat_in_f_beta():
    nu = ph.wavenumber_grid()
    sim = ph.simulate(
        nu, ph.Theta(f_beta=0.0, a_um=0.25, inert_f_beta=True),
        sigma=ph.sigma_for_radius(0.25), seed=0,
    )
    p = inf.E1Problem(
        nu=nu, data=sim["y"].numpy(), sigma=ph.sigma_for_radius(0.25),
        condition="raw", inert_f_beta=True,
    )
    vals = [p.loglike([f, 0.25, 1.40, 0.2, 1.0, 0.0, 0.0]) for f in (0.0, 0.25, 0.5, 0.75, 1.0)]
    assert np.allclose(vals, vals[0])


def test_sigma_rule_is_monotone_and_above_the_floor():
    """Task 2's BLOCKED conditions: D(a) must be monotone and never below 1e-4."""
    nu = ph.wavenumber_grid()
    d = [ph.absorption_depth(nu, a) for a in (0.25, 1, 2, 3, 3.5, 4, 5, 6)]
    assert all(b > a for a, b in zip(d, d[1:])), d
    assert min(d) > 1e-4, d
    # sigma(a) = D(a)/295 reproduces the tissue SNR by construction
    assert np.isclose(ph.sigma_for_radius(3.5), ph.absorption_depth(nu, 3.5) / 295.0)


def test_absorption_depth_has_no_scattering_resonances():
    """With n = 1 the phase shift is real, so Q_ext rises monotonically to 2
    instead of oscillating -- that is why D(a) can set sigma where the apparent
    band cannot."""
    nu = ph.wavenumber_grid()
    k = ph.tissue_k(nu, 0.0, 1.0)
    for a_um in (0.25, 2.0, 8.0, 50.0):
        q = ph.qext_ada(nu, a_um, torch.ones_like(nu), k)
        assert (q >= 0).all() and float(q.max()) < 2.0 + 1e-9, a_um
