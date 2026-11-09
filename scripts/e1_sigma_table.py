"""Request 02 task 2: the sigma(a) table.

sigma(a) = D(a) / 295, with D(a) the Amide I absorption depth of the same
sphere with scattering switched off (n_inf = 1, dn = 0, phi = 0.2, amplitude 1,
f_beta = 0), taken as the maximum over 1600-1700 cm^-1.

BLOCKED if D(a) is non-monotone or below 1e-4 AU anywhere.

Run:  OMP_NUM_THREADS=16 .venv/bin/python -m scripts.e1_sigma_table
Writes results/e1/sigma_table.json.
"""

from __future__ import annotations

import json

import torch

from descatter import physics as ph
from descatter.provenance import REPO_ROOT, Run

OUT = REPO_ROOT / "results" / "e1"
GRID_RADII = [0.25, 1.0, 2.0, 3.0, 3.5, 4.0, 5.0, 6.0]
E0_SIGMA = 1.097e-3


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    nu = ph.wavenumber_grid()
    sel = (nu >= 1600.0) & (nu <= 1700.0)

    with Run("e1", "sigma_table",
             config={"radii_um": GRID_RADII, "tissue_snr": ph.TISSUE_SNR,
                     "phi": ph.SIGMA_PHI, "n_inf_for_D": 1.0, "window": [1600, 1700]}) as run:
        rows = []
        for a in GRID_RADII:
            D = ph.absorption_depth(nu, a)
            sigma = D / ph.TISSUE_SNR
            # the apparent band, for contrast: this is what D(a) deliberately avoids
            out = ph.forward(nu, ph.Theta(f_beta=0.0, a_um=a, n_inf=1.40, phi=ph.SIGMA_PHI))
            w, sp = nu[sel], out["A_app"][sel]
            base = sp[0] + (sp[-1] - sp[0]) * (w - w[0]) / (w[-1] - w[0])
            rows.append({
                "a_um": a,
                "D_AU": D,
                "sigma_AU": sigma,
                "snr_by_construction": D / sigma,
                "apparent_band_depth_AU": float((sp - base).max()),
                "sigma_relative_to_E0_noise": sigma / E0_SIGMA,
                "qext_abs_max": float(
                    ph.qext_ada(nu, a, torch.ones_like(nu), ph.tissue_k(nu, 0.0, 1.0)).max()
                ),
            })

        D_vals = [r["D_AU"] for r in rows]
        monotone = all(b > a for a, b in zip(D_vals, D_vals[1:]))
        above_floor = min(D_vals) >= 1e-4
        blocked = not (monotone and above_floor)

        report = {
            "task": "request 02 task 2: sigma(a) = D(a) / 295",
            "definition": (
                "D(a) = max over 1600-1700 cm^-1 of A_app evaluated with n_inf = 1 and "
                "dn = 0, keeping k(nu), phi = 0.2, amplitude 1 and the alpha composition "
                "(f_beta = 0). With n = 1 the complex phase shift z = 2xk + 2ix(n-1) is "
                "purely real, so Q_ext is the pure-absorption van de Hulst limit and "
                "saturates at 2 instead of oscillating. n_inf = 1 is used only to set "
                "sigma and is outside the inference prior."
            ),
            "tissue_snr": ph.TISSUE_SNR,
            "tissue_snr_source": (
                "E0: median raw Amide I peak 0.324 AU over median noise 1.097e-3 AU, "
                "core s10_c048 (results/e0/summary.json)"
            ),
            "blocked_checks": {
                "D_monotone_increasing": monotone,
                "D_min_AU": min(D_vals),
                "D_above_1e-4_everywhere": above_floor,
                "BLOCKED": blocked,
            },
            "per_radius": rows,
        }
        (OUT / "sigma_table.json").write_text(json.dumps(report, indent=2) + "\n")
        run.notes["blocked"] = blocked

    print(f"{'a/um':>6} {'D(a)/AU':>10} {'sigma(a)/AU':>13} {'SNR':>6} "
          f"{'apparent depth':>15} {'sigma/sigma_E0':>15}")
    for r in rows:
        print(f"{r['a_um']:6.2f} {r['D_AU']:10.5f} {r['sigma_AU']:13.4e} "
              f"{r['snr_by_construction']:6.1f} {r['apparent_band_depth_AU']:15.5f} "
              f"{r['sigma_relative_to_E0_noise']:15.4f}")
    print(f"\nmonotone: {monotone}   min D = {min(D_vals):.5f} AU   BLOCKED: {blocked}")


if __name__ == "__main__":
    main()
