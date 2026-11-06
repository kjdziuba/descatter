"""E1 step 2 unit tests. Thresholds are the ones pre-registered in docs/EXPERIMENTS.md."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import torch

from descatter import physics as ph

LEGACY_SIM = Path(__file__).resolve().parent.parent / "legacy" / "rmies_sim.py"


# --------------------------------------------------------------------------
# Kramers-Kronig: FFT Hilbert vs the analytic Lorentz dispersion
# --------------------------------------------------------------------------
def _kk_pair(nu: torch.Tensor, f_beta: float = 0.3):
    rows = ph.oscillator_table(f_beta)
    centres = torch.tensor([r[0] for r in rows], dtype=ph.DTYPE)
    fwhm = torch.tensor([r[1] for r in rows], dtype=ph.DTYPE)
    peaks = torch.tensor([r[2] for r in rows], dtype=ph.DTYPE)
    k = ph.lorentz_k(nu, centres, fwhm, peaks)
    dn_exact = ph.lorentz_dn(nu, centres, fwhm, peaks)
    return k, dn_exact


def test_kramers_kronig_matches_analytic_lorentz():
    """PRE-REGISTERED (E1 step 2). FFT-Hilbert dn vs analytic Lorentz dn over
    950-1800 cm^-1: correlation >= 0.99 and scale factor in [0.98, 1.02].

    Uses the same path as the forward model: k is evaluated on a grid extended
    by 4x on each side, transformed there and cropped.
    """
    nu = ph.wavenumber_grid()
    _, dn_exact = _kk_pair(nu)
    rows = ph.oscillator_table(0.3)
    centres = torch.tensor([r[0] for r in rows], dtype=ph.DTYPE)
    fwhm = torch.tensor([r[1] for r in rows], dtype=ph.DTYPE)
    peaks = torch.tensor([r[2] for r in rows], dtype=ph.DTYPE)
    dn_fft = ph.kk_dn_extended(nu, lambda w: ph.lorentz_k(w, centres, fwhm, peaks))

    a, b = dn_fft.numpy(), dn_exact.numpy()
    corr = float(np.corrcoef(a, b)[0, 1])
    scale = float(np.dot(a, b) / np.dot(b, b))  # least-squares a ~ scale*b

    assert corr >= 0.99, f"KK correlation {corr:.6f} < 0.99"
    assert 0.98 <= scale <= 1.02, f"KK scale factor {scale:.6f} outside [0.98, 1.02]"


def test_kramers_kronig_truncated_window_loses_amplitude():
    """Documents why :func:`ph.kk_dn_extended` exists.

    Transforming k truncated to 950-1800 cm^-1 keeps the shape (correlation is
    still ~0.9996) but loses about 2.5 % of the dispersion amplitude, because the
    taper discards the Lorentzian tails of bands outside the window. That misses
    the pre-registered [0.98, 1.02] scale band, so the forward model must not
    take this path.
    """
    nu = ph.wavenumber_grid()
    k, dn_exact = _kk_pair(nu)
    a, b = ph.kk_dn(k, pad_factor=8.0).numpy(), dn_exact.numpy()
    corr = float(np.corrcoef(a, b)[0, 1])
    scale = float(np.dot(a, b) / np.dot(b, b))
    assert corr >= 0.99
    assert 0.96 < scale < 0.98, f"expected a ~2.5 % amplitude deficit, got scale {scale:.6f}"


def test_kramers_kronig_single_lorentzian_sign():
    """n rises below a band and dips above it (anomalous dispersion)."""
    nu = ph.wavenumber_grid()
    centres = torch.tensor([1656.0], dtype=ph.DTYPE)
    fwhm = torch.tensor([45.0], dtype=ph.DTYPE)
    peaks = torch.tensor([0.08], dtype=ph.DTYPE)
    dn = ph.kk_dn(ph.lorentz_k(nu, centres, fwhm, peaks), pad_factor=8.0)
    below = dn[(nu > 1600) & (nu < 1640)].mean()
    above = dn[(nu > 1672) & (nu < 1712)].mean()
    assert below > 0 > above


# --------------------------------------------------------------------------
# Mie curve: the non-absorbing ADA extrema
# --------------------------------------------------------------------------
def test_ada_nonabsorbing_curve_extrema():
    """Q_ext(rho) must have its first maximum 3.17 at rho = 4.09 and its minimum
    1.54 at rho = 7.62, each within 1 %."""
    rho = torch.linspace(1e-4, 20.0, 2_000_001, dtype=ph.DTYPE)
    # rho = 2x(n-1); drive the ADA through nu with n-1 = 1/(4 pi a) so rho = nu
    a_um, n_minus_1 = 1.0, 0.5
    nu = rho / (2.0 * 2.0 * torch.pi * a_um * ph.UM_TO_CM * n_minus_1)
    q = ph.qext_ada(nu, a_um, torch.full_like(nu, 1.0 + n_minus_1), torch.zeros_like(nu))

    # Q_ext rises from 0, so bracket each extremum rather than taking a global one
    hi_band = (rho >= 2.0) & (rho <= 6.0)
    lo_band = (rho >= 6.0) & (rho <= 10.0)
    max_idx = int(torch.nonzero(hi_band)[0]) + int(torch.argmax(q[hi_band]))
    first_min_idx = int(torch.nonzero(lo_band)[0]) + int(torch.argmin(q[lo_band]))
    assert q[max_idx] == pytest.approx(3.17, rel=0.01), f"first max Q={q[max_idx]:.4f}"
    assert rho[max_idx] == pytest.approx(4.09, rel=0.01), f"first max at rho={rho[max_idx]:.4f}"
    assert q[first_min_idx] == pytest.approx(1.54, rel=0.01), f"min Q={q[first_min_idx]:.4f}"
    assert rho[first_min_idx] == pytest.approx(7.62, rel=0.01), (
        f"min at rho={rho[first_min_idx]:.4f}"
    )


def test_ada_small_sphere_limit():
    """Q_ext -> rho^2/2 as rho -> 0, through the series branch of K(z)."""
    nu = ph.wavenumber_grid()
    n = torch.full_like(nu, 1.40)
    k = torch.zeros_like(nu)
    a_um = 1e-4
    q = ph.qext_ada(nu, a_um, n, k)
    rho = 2.0 * ph.size_parameter(nu, a_um) * 0.40
    assert torch.allclose(q, rho**2 / 2.0, rtol=1e-6, atol=1e-18)
    assert torch.isfinite(q).all()


def test_forward_model_is_differentiable():
    """Gradients must flow to f_beta, a, n_inf and phi (needed for DPS later)."""
    nu = ph.wavenumber_grid()
    f_beta = torch.tensor(0.3, dtype=ph.DTYPE, requires_grad=True)
    a_um = torch.tensor(3.0, dtype=ph.DTYPE, requires_grad=True)
    n_inf = torch.tensor(1.40, dtype=ph.DTYPE, requires_grad=True)
    phi = torch.tensor(0.2, dtype=ph.DTYPE, requires_grad=True)

    k = ph.tissue_k(nu, f_beta)
    n = ph.refractive_index(k, n_inf)
    q = ph.qext_ada(nu, a_um, n, k)
    a_app, _ = ph.apparent_absorbance(q, phi, nu=nu)
    a_app.sum().backward()

    for name, t in [("f_beta", f_beta), ("a", a_um), ("n_inf", n_inf), ("phi", phi)]:
        assert t.grad is not None and torch.isfinite(t.grad) and t.grad != 0, name


def test_apparent_absorbance_flags_unphysical_phi():
    """phi*Q_ext >= 1 must be flagged, not silently clamped."""
    q = torch.tensor([0.5, 2.0, 3.2], dtype=ph.DTYPE)
    _, valid = ph.apparent_absorbance(q, phi=0.9)
    assert valid.tolist() == [True, False, False]
    _, valid = ph.apparent_absorbance(q, phi=0.2)
    assert valid.all()


# --------------------------------------------------------------------------
# ADA vs exact Mie: reported, not pass/fail (E1 step 2)
# --------------------------------------------------------------------------
def test_ada_vs_exact_mie_runs_and_is_physical():
    """Not a threshold test. ADA must stay finite, positive and the same order
    as exact Mie across a in [0.5, 8] um; the agreement itself is reported by
    scripts/e1_ada_vs_mie.py."""
    nu = ph.wavenumber_grid()
    k = ph.tissue_k(nu, 0.0)
    n = ph.refractive_index(k, 1.40)
    for a_um in (0.5, 2.0, 4.0, 8.0):
        q_ada = ph.qext_ada(nu, a_um, n, k).numpy()
        q_mie = ph.qext_mie(nu, a_um, n, k)
        assert np.isfinite(q_ada).all() and np.isfinite(q_mie).all()
        assert (q_ada > 0).all() and (q_mie > 0).all()
        # ADA assumes a large, optically soft sphere, so it overshoots badly at
        # a = 0.5 um (ratio ~3.1). Only order-of-magnitude sanity is asserted;
        # scripts/e1_ada_vs_mie.py reports the agreement curve E1 step 2 asks for.
        ratio = q_ada.mean() / q_mie.mean()
        assert 0.1 < ratio < 10.0, f"a={a_um}: ADA/Mie mean ratio {ratio:.3f}"


# --------------------------------------------------------------------------
# Lesson 1 reproduction: only when legacy/rmies_sim.py is present
# --------------------------------------------------------------------------
@pytest.mark.skipif(
    not LEGACY_SIM.exists(),
    reason="legacy/rmies_sim.py absent; the fallback oscillator set is used instead "
    "(docs/EXPERIMENTS.md 2026-11-06 amendment)",
)
def test_lesson1_amide_i_shifts():
    """Apparent Amide I maximum must shift by -8, -18, -32 and -50 cm^-1 at
    a = 1, 2, 3 and 4 um, each within +/-3 cm^-1."""
    nu = ph.wavenumber_grid()
    expected = {1.0: -8.0, 2.0: -18.0, 3.0: -32.0, 4.0: -50.0}
    base = ph.forward(nu, ph.Theta(f_beta=0.0, a_um=1e-4, phi=0.2))
    pos0 = ph.amide_i_position(nu, base["A_app"])
    for a_um, want in expected.items():
        out = ph.forward(nu, ph.Theta(f_beta=0.0, a_um=a_um, phi=0.2))
        got = ph.amide_i_position(nu, out["A_app"]) - pos0
        assert abs(got - want) <= 3.0, f"a={a_um} um: shift {got:+.1f}, expected {want:+.1f}"
