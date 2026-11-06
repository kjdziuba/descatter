"""E1 forward model: Lorentz chemistry -> Kramers-Kronig -> sphere extinction.

PyTorch, float64, differentiable end to end (the ADA path; the exact-Mie path is
numpy and is only a reference).

Conventions
-----------
- wavenumber ``nu`` in cm^-1, sphere radius ``a`` in micrometres;
- complex refractive index ``m = n - i k`` (van de Hulst / miepython sign), with
  ``n = n_inf + dn`` and ``dn`` the Kramers-Kronig transform of ``k``;
- size parameter ``x = 2 pi a nu`` with ``a`` converted to cm;
- all scattered light is counted as lost, so the apparent absorbance is
  ``A_app = -log10(1 - phi * Q_ext)``.

See docs/EXPERIMENTS.md E1 step 1 and the 2026-11-06 amendment that documents
the fallback oscillator set used here (``legacy/rmies_sim.py`` is absent).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import torch

UM_TO_CM = 1e-4
DTYPE = torch.float64


# --------------------------------------------------------------------------
# Chemistry: the fallback 14-oscillator tissue set
# --------------------------------------------------------------------------
# (centre cm^-1, FWHM cm^-1, peak k, label). Eleven fixed bands plus the three
# Amide I lineshapes (alpha, beta major, beta minor) = 14 oscillators.
# Peak k values are scaled so Amide I / Amide II = 1.78 in k, which is 1.91 in
# thin-film absorbance (A ~ nu * k), matching the Lesson 1 number in
# docs/RESEARCH_BRIEF.md.
FIXED_BANDS: tuple[tuple[float, float, float, str], ...] = (
    (1030.0, 40.0, 0.012, "glycogen / C-O stretch"),
    (1080.0, 35.0, 0.022, "symmetric PO2- stretch (nucleic acid)"),
    (1170.0, 30.0, 0.010, "C-O stretch / ester"),
    (1240.0, 55.0, 0.026, "asymmetric PO2- stretch / Amide III"),
    (1310.0, 30.0, 0.009, "Amide III"),
    (1340.0, 30.0, 0.010, "CH deformation / collagen"),
    (1398.0, 35.0, 0.016, "symmetric COO- stretch / CH3 bend"),
    (1450.0, 35.0, 0.018, "CH2 bend"),
    (1468.0, 20.0, 0.008, "CH2 scissoring (lipid)"),
    (1545.0, 50.0, 0.045, "Amide II"),
    (1740.0, 25.0, 0.010, "ester C=O (lipid)"),
)

AMIDE_I_PEAK_K = 0.080
#: alpha-helix Amide I
ALPHA_BAND = (1656.0, 45.0)
#: beta-sheet Amide I: major and minor components
BETA_MAJOR = (1630.0, 25.0)
BETA_MINOR = (1690.0, 20.0)
#: minor/major peak ratio within the beta lineshape
BETA_MINOR_RATIO = 0.18


def _beta_scale() -> float:
    """Peak of the beta major band that makes the beta lineshape equal in area
    to the alpha band, so ``f_beta`` changes Amide I *shape* and not protein
    content. A Lorentzian of peak P and half-width G has area pi*P*G."""
    g_a = ALPHA_BAND[1] / 2.0
    g_maj, g_min = BETA_MAJOR[1] / 2.0, BETA_MINOR[1] / 2.0
    return g_a / (g_maj + BETA_MINOR_RATIO * g_min)


BETA_SCALE = _beta_scale()


def amide_i_bands(f_beta: float | torch.Tensor) -> list[tuple[float, float, torch.Tensor]]:
    """The three Amide I lineshapes at mixing fraction ``f_beta``."""
    fb = torch.as_tensor(f_beta, dtype=DTYPE)
    return [
        (ALPHA_BAND[0], ALPHA_BAND[1], (1.0 - fb) * AMIDE_I_PEAK_K),
        (BETA_MAJOR[0], BETA_MAJOR[1], fb * AMIDE_I_PEAK_K * BETA_SCALE),
        (BETA_MINOR[0], BETA_MINOR[1], fb * AMIDE_I_PEAK_K * BETA_SCALE * BETA_MINOR_RATIO),
    ]


def oscillator_table(f_beta: float = 0.0) -> list[tuple[float, float, float, str]]:
    """The full 14-oscillator set, for documentation and tests."""
    rows = [tuple(b) for b in FIXED_BANDS]
    labels = ("Amide I alpha-helix", "Amide I beta-sheet major", "Amide I beta-sheet minor")
    for (c, fwhm, peak), lab in zip(amide_i_bands(f_beta), labels):
        rows.append((c, fwhm, float(peak), lab))
    return rows  # type: ignore[return-value]


def lorentz_k(
    nu: torch.Tensor,
    centres: torch.Tensor,
    fwhm: torch.Tensor,
    peaks: torch.Tensor,
) -> torch.Tensor:
    """Absorptive Lorentzian sum: ``k = sum_j P_j G_j^2 / ((nu0_j-nu)^2 + G_j^2)``."""
    g = fwhm / 2.0
    d = centres[..., :, None] - nu[..., None, :]
    return (peaks[..., :, None] * g[..., :, None] ** 2 / (d**2 + g[..., :, None] ** 2)).sum(-2)


def lorentz_dn(
    nu: torch.Tensor,
    centres: torch.Tensor,
    fwhm: torch.Tensor,
    peaks: torch.Tensor,
) -> torch.Tensor:
    """The analytic Kramers-Kronig partner of :func:`lorentz_k`:
    ``dn = sum_j P_j G_j (nu0_j - nu) / ((nu0_j-nu)^2 + G_j^2)``.

    Used only to check the FFT-Hilbert transform; the forward model uses the FFT.
    """
    g = fwhm / 2.0
    d = centres[..., :, None] - nu[..., None, :]
    return (peaks[..., :, None] * g[..., :, None] * d / (d**2 + g[..., :, None] ** 2)).sum(-2)


def tissue_k(nu: torch.Tensor, f_beta: float | torch.Tensor, amplitude: float | torch.Tensor = 1.0):
    """Tissue ``k(nu)`` from the 14-oscillator set at Amide I mixing ``f_beta``."""
    bands = [(c, w, torch.as_tensor(p, dtype=DTYPE)) for c, w, p, _ in FIXED_BANDS]
    bands += amide_i_bands(f_beta)
    centres = torch.tensor([b[0] for b in bands], dtype=DTYPE)
    fwhm = torch.tensor([b[1] for b in bands], dtype=DTYPE)
    peaks = torch.stack([torch.as_tensor(b[2], dtype=DTYPE) for b in bands])
    return torch.as_tensor(amplitude, dtype=DTYPE) * lorentz_k(nu, centres, fwhm, peaks)


# --------------------------------------------------------------------------
# Kramers-Kronig by FFT Hilbert transform
# --------------------------------------------------------------------------
def hilbert(x: torch.Tensor) -> torch.Tensor:
    """``H[x](t) = (1/pi) P int x(s)/(t-s) ds``, via ``-i sgn(f)`` in the FFT."""
    n = x.shape[-1]
    freqs = torch.fft.fftfreq(n, dtype=x.dtype, device=x.device)
    h = -1j * torch.sign(freqs)
    return torch.fft.ifft(torch.fft.fft(x.to(torch.complex128)) * h).real


def _taper_pad(x: torch.Tensor, pad: int) -> torch.Tensor:
    """Extend both ends by ``pad`` samples, ramping the edge value to zero with a
    raised cosine. Keeps the signal continuous so the FFT sees no step."""
    if pad == 0:
        return x
    t = torch.linspace(0.0, 1.0, pad + 1, dtype=x.dtype, device=x.device)[:-1]
    ramp = 0.5 * (1.0 - torch.cos(torch.pi * t))  # 0 -> 1
    left = x[..., :1] * ramp
    right = x[..., -1:] * ramp.flip(-1)
    return torch.cat([left, x, right], dim=-1)


def kk_dn(k: torch.Tensor, pad_factor: float = 4.0) -> torch.Tensor:
    """Kramers-Kronig ``dn = n - n_inf`` from ``k``, by FFT Hilbert transform.

    ``dn(nu) = (1/pi) P int k(nu')/(nu'-nu) dnu' = -H[k](nu)``, which for a single
    Lorentzian reproduces :func:`lorentz_dn` exactly. The spectrum is taper-padded
    by ``pad_factor * n`` samples on each side so the periodic FFT does not wrap
    one edge onto the other.
    """
    n = k.shape[-1]
    pad = int(round(pad_factor * n))
    return -hilbert(_taper_pad(k, pad))[..., pad : pad + n]


def extended_wavenumber_grid(
    nu: torch.Tensor, extend_factor: float = 4.0
) -> tuple[torch.Tensor, int]:
    """``nu`` widened by ``extend_factor * n`` samples on each side, same spacing.

    Returns ``(nu_ext, pad)`` so the original window is ``nu_ext[pad:pad+n]``.
    """
    n = nu.shape[-1]
    step = (nu[-1] - nu[0]) / (n - 1)
    pad = int(round(extend_factor * n))
    return torch.arange(-pad, n + pad, dtype=DTYPE, device=nu.device) * step + nu[0], pad


def kk_dn_extended(
    nu: torch.Tensor,
    k_of_nu,
    extend_factor: float = 4.0,
    pad_factor: float = 1.0,
) -> torch.Tensor:
    """Kramers-Kronig ``dn`` on ``nu``, with ``k`` evaluated on a wider grid first.

    This is the accurate path and the one the forward model uses. Calling
    :func:`kk_dn` on a spectrum truncated to 950-1800 cm^-1 instead costs about
    2.5 % of the dispersion amplitude, because the taper throws away the
    Lorentzian tails of bands just outside the window -- see
    ``tests/test_physics.py::test_kramers_kronig_truncated_window_loses_amplitude``.
    """
    nu_ext, pad = extended_wavenumber_grid(nu, extend_factor)
    return kk_dn(k_of_nu(nu_ext), pad_factor=pad_factor)[..., pad : pad + nu.shape[-1]]


def refractive_index(
    k: torch.Tensor, n_inf: float | torch.Tensor, pad_factor: float = 4.0
) -> torch.Tensor:
    """``n(nu) = n_inf + KK[k](nu)`` from an already-sampled ``k``.

    Prefer :func:`kk_dn_extended` when the band parameters are available.
    """
    return torch.as_tensor(n_inf, dtype=DTYPE) + kk_dn(k, pad_factor=pad_factor)


# --------------------------------------------------------------------------
# Sphere extinction
# --------------------------------------------------------------------------
def size_parameter(nu: torch.Tensor, a_um: float | torch.Tensor) -> torch.Tensor:
    """``x = 2 pi a nu`` with ``a`` in micrometres and ``nu`` in cm^-1."""
    return 2.0 * torch.pi * torch.as_tensor(a_um, dtype=DTYPE) * UM_TO_CM * nu


def _vdh_K(z: torch.Tensor) -> torch.Tensor:
    """van de Hulst ``K(z) = 1/2 + e^-z / z + (e^-z - 1)/z^2``.

    Near ``z = 0`` the two poles cancel but catastrophically in floating point,
    so switch to the series ``z/3 - z^2/8 + z^3/24`` there.
    """
    small = z.abs() < 1e-2
    zs = torch.where(small, torch.ones_like(z), z)  # keep the division finite
    ez = torch.exp(-zs)
    full = 0.5 + ez / zs + (ez - 1.0) / zs**2
    series = z / 3.0 - z**2 / 8.0 + z**3 / 24.0
    return torch.where(small, series, full)


def qext_ada(
    nu: torch.Tensor,
    a_um: float | torch.Tensor,
    n: torch.Tensor,
    k: torch.Tensor,
) -> torch.Tensor:
    """van de Hulst anomalous-diffraction extinction efficiency of a sphere.

    ``Q_ext = 4 Re K(z)`` with the complex phase shift ``z = 2 x k + 2 i x (n-1)``.
    With ``k = 0`` this is the textbook
    ``2 - 4 sin(rho)/rho + 4 (1-cos rho)/rho^2`` for ``rho = 2x(n-1)``.
    Differentiable in ``a``, ``n`` and ``k``.
    """
    x = size_parameter(nu, a_um)
    z = torch.complex(2.0 * x * k, 2.0 * x * (n - 1.0))
    return 4.0 * _vdh_K(z).real


def qext_mie(
    nu: np.ndarray | torch.Tensor,
    a_um: float,
    n: np.ndarray | torch.Tensor,
    k: np.ndarray | torch.Tensor,
) -> np.ndarray:
    """Exact Mie extinction efficiency (miepython). Reference only, not differentiable."""
    import miepython

    nu_np = np.asarray(torch.as_tensor(nu).detach().cpu().numpy(), dtype=np.float64)
    n_np = np.asarray(torch.as_tensor(n).detach().cpu().numpy(), dtype=np.float64)
    k_np = np.asarray(torch.as_tensor(k).detach().cpu().numpy(), dtype=np.float64)
    x = 2.0 * np.pi * a_um * UM_TO_CM * nu_np
    m = n_np - 1j * k_np  # miepython's sign convention
    qext, _, _, _ = miepython.efficiencies_mx(m, x)
    return np.asarray(qext, dtype=np.float64)


# --------------------------------------------------------------------------
# Apparent absorbance
# --------------------------------------------------------------------------
#: ``1 - phi*Q_ext`` is floored here; below this the parameters are unphysical
#: (more light removed than arrives) and the likelihood should reject them.
TRANSMITTANCE_FLOOR = 1e-12


def apparent_absorbance(
    qext: torch.Tensor,
    phi: float | torch.Tensor,
    baseline_offset: float | torch.Tensor = 0.0,
    baseline_slope: float | torch.Tensor = 0.0,
    nu: torch.Tensor | None = None,
) -> tuple[torch.Tensor, torch.Tensor]:
    """``A_app = -log10(1 - phi Q_ext)`` plus a linear baseline.

    Returns ``(A_app, valid)``. ``valid`` is False wherever ``phi*Q_ext >= 1``,
    i.e. where the "all scattered light is lost" model removes more light than
    arrives. Q_ext peaks near 3.2, so phi above about 0.31 is unreachable for
    some spectra -- see the note in docs/EXPERIMENTS.md on the phi prior.
    """
    phi_t = torch.as_tensor(phi, dtype=DTYPE)
    trans = 1.0 - phi_t * qext
    valid = trans > TRANSMITTANCE_FLOOR
    a = -torch.log10(torch.clamp(trans, min=TRANSMITTANCE_FLOOR))
    a = a + torch.as_tensor(baseline_offset, dtype=DTYPE)
    if nu is not None:
        nu0 = nu.mean()
        a = a + torch.as_tensor(baseline_slope, dtype=DTYPE) * (nu - nu0) / 1000.0
    return a, valid


# --------------------------------------------------------------------------
# The whole forward model
# --------------------------------------------------------------------------
@dataclass
class Theta:
    """E1 parameter vector (docs/EXPERIMENTS.md E1 step 3)."""

    f_beta: float = 0.0
    a_um: float = 3.0
    n_inf: float = 1.40
    phi: float = 0.20
    amplitude: float = 1.0
    baseline_offset: float = 0.0
    baseline_slope: float = 0.0


def wavenumber_grid(
    lo: float = 950.0, hi: float = 1800.0, spacing: float = 1.928973
) -> torch.Tensor:
    """Default E1 grid: 950-1800 cm^-1 at the PCUK2023 raw spacing (E0 summary)."""
    n = int(np.floor((hi - lo) / spacing)) + 1
    return torch.arange(n, dtype=DTYPE) * spacing + lo


def forward(
    nu: torch.Tensor,
    theta: Theta,
    pad_factor: float = 4.0,
    exact_mie: bool = False,
) -> dict[str, torch.Tensor]:
    """Chemistry -> KK -> sphere extinction -> apparent absorbance.

    ``k`` and ``dn`` are built on a grid extended by ``pad_factor * n`` samples on
    each side, so bands just outside 950-1800 cm^-1 contribute to the dispersion
    inside it, then cropped. Returns a dict with ``k``, ``n``, ``qext`` and
    ``A_app`` (noise free), plus ``valid``.
    """
    def k_of(w: torch.Tensor) -> torch.Tensor:
        return tissue_k(w, theta.f_beta, theta.amplitude)

    k = k_of(nu)
    n_idx = theta.n_inf + kk_dn_extended(nu, k_of, extend_factor=pad_factor, pad_factor=1.0)

    if exact_mie:
        qext = torch.as_tensor(qext_mie(nu, theta.a_um, n_idx, k), dtype=DTYPE)
    else:
        qext = qext_ada(nu, theta.a_um, n_idx, k)

    a_app, valid = apparent_absorbance(
        qext, theta.phi, theta.baseline_offset, theta.baseline_slope, nu
    )
    return {"k": k, "n": n_idx, "qext": qext, "A_app": a_app, "valid": valid}


def simulate(
    nu: torch.Tensor,
    theta: Theta,
    sigma: float = 1.1e-3,
    seed: int | None = None,
    exact_mie: bool = False,
) -> dict[str, torch.Tensor]:
    """:func:`forward` plus i.i.d. Gaussian noise of SD ``sigma``."""
    out = forward(nu, theta, exact_mie=exact_mie)
    gen = torch.Generator().manual_seed(seed) if seed is not None else None
    noise = torch.randn(out["A_app"].shape, dtype=DTYPE, generator=gen) * sigma
    out["y"] = out["A_app"] + noise
    out["sigma"] = torch.as_tensor(sigma, dtype=DTYPE)
    return out


# --------------------------------------------------------------------------
# Diagnostics (the Lesson 1 names)
# --------------------------------------------------------------------------
def _parabolic_extremum(w: np.ndarray, y: np.ndarray, idx: int) -> float:
    """Sub-grid extremum from a parabola through the three samples around ``idx``.

    The E1 grid is 1.93 cm^-1, so a bare argmax quantises the Amide I shift into
    steps that eat most of the +/-3 cm^-1 Lesson 1 tolerance.
    """
    if idx <= 0 or idx >= len(y) - 1:
        return float(w[idx])
    y0, y1, y2 = y[idx - 1], y[idx], y[idx + 1]
    denom = y0 - 2.0 * y1 + y2
    if denom == 0.0:
        return float(w[idx])
    delta = 0.5 * (y0 - y2) / denom  # in samples, within (-1, 1)
    step = (w[-1] - w[0]) / (len(w) - 1)
    return float(w[idx] + delta * step)


def amide_i_position(
    nu: torch.Tensor, spectrum: torch.Tensor, window: tuple[float, float] = (1600.0, 1700.0)
) -> float:
    """Apparent Amide I maximum, after removing a straight line through the
    window's two endpoints (the "perfect baseline removal" of Lesson 1).

    Refined to sub-grid precision by a 3-point parabola.
    """
    sel = (nu >= window[0]) & (nu <= window[1])
    w, s = nu[sel], spectrum[sel]
    base = s[0] + (s[-1] - s[0]) * (w - w[0]) / (w[-1] - w[0])
    y = (s - base).detach().cpu().numpy()
    return _parabolic_extremum(w.detach().cpu().numpy(), y, int(np.argmax(y)))


def amide_i_second_derivative_position(
    nu: torch.Tensor,
    spectrum: torch.Tensor,
    window: tuple[float, float] = (1600.0, 1700.0),
    sg_window: int = 13,
    sg_poly: int = 3,
) -> float:
    """Apparent Amide I position from the second-derivative minimum."""
    from scipy.signal import savgol_filter

    d2 = savgol_filter(spectrum.detach().cpu().numpy(), sg_window, sg_poly, deriv=2)
    sel = ((nu >= window[0]) & (nu <= window[1])).detach().cpu().numpy()
    w, y = nu.detach().cpu().numpy()[sel], d2[sel]
    return _parabolic_extremum(w, -y, int(np.argmin(y)))
