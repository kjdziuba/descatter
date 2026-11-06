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
    return pre(ph.forward(nu, theta)["A_app"].numpy())[0]


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


def test_preprocessing_output_is_unit_norm():
    out = _pre_of(ph.Theta(f_beta=0.7, a_um=2.0))
    assert np.isclose(np.linalg.norm(out), 1.0)


def test_preprocessed_condition_rescales_sigma():
    nu = ph.wavenumber_grid()
    sim = ph.simulate(nu, ph.Theta(f_beta=0.0, a_um=3.0), sigma=1.1e-3, seed=0)
    raw = inf.E1Problem(nu=nu, data=sim["y"].numpy(), sigma=1.1e-3, condition="raw")
    pre = inf.E1Problem(nu=nu, data=sim["y"].numpy(), sigma=1.1e-3, condition="preprocessed")
    assert raw.sigma_eff == 1.1e-3 and raw.n_data == nu.numel()
    assert pre.n_data < raw.n_data  # only the 1600-1700 window survives
    assert np.isclose(pre.sigma_eff, 1.1e-3 / pre.data_norm)
    assert pre.sigma_eff > raw.sigma_eff  # the window norm is below 1 AU


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
