"""E1 step 2: report ADA vs exact Mie over a in [0.5, 8] um, and the Amide I
shift table the fallback oscillator set produces.

Not a pass/fail test -- E1 step 2 asks for the agreement to be *reported*.

Run:  OMP_NUM_THREADS=16 .venv/bin/python scripts/e1_ada_vs_mie.py
Writes results/e1/ada_vs_mie.json, results/e1/ada_vs_mie.png,
results/e1/amide_i_shifts.json and results/e1/<run_id>/run.json.
"""

from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

from descatter import physics as ph
from descatter.provenance import REPO_ROOT, Run

OUT = REPO_ROOT / "results" / "e1"
RADII = [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 8.0]
LESSON1_SHIFTS = {1.0: -8.0, 2.0: -18.0, 3.0: -32.0, 4.0: -50.0, 6.0: +62.0}


def main() -> None:
    nu = ph.wavenumber_grid()
    OUT.mkdir(parents=True, exist_ok=True)

    with Run("e1", "ada_vs_mie", config={"radii_um": RADII, "n_inf": 1.40, "f_beta": 0.0}) as run:
        k = ph.tissue_k(nu, 0.0)
        n = ph.refractive_index(k, 1.40)
        k_np, n_np = k.numpy(), n.numpy()

        rows = []
        curves = {}
        for a_um in RADII:
            q_ada = ph.qext_ada(nu, a_um, n, k).numpy()
            q_mie = ph.qext_mie(nu, a_um, n, k)
            resid = q_ada - q_mie
            rows.append(
                {
                    "a_um": a_um,
                    "x_at_1000cm1": float(2 * np.pi * a_um * ph.UM_TO_CM * 1000.0),
                    "mean_qext_ada": float(q_ada.mean()),
                    "mean_qext_mie": float(q_mie.mean()),
                    "mean_ratio": float(q_ada.mean() / q_mie.mean()),
                    "rmse": float(np.sqrt((resid**2).mean())),
                    "relative_rmse": float(np.sqrt((resid**2).mean()) / q_mie.mean()),
                    "max_abs_error": float(np.abs(resid).max()),
                    "correlation": float(np.corrcoef(q_ada, q_mie)[0, 1]),
                    "amide_i_shift_ada_cm1": _shift(nu, a_um, exact_mie=False),
                    "amide_i_shift_mie_cm1": _shift(nu, a_um, exact_mie=True),
                }
            )
            curves[a_um] = (q_ada, q_mie)

        report = {
            "note": (
                "E1 step 2 asks for the ADA-vs-exact-Mie agreement to be reported, not "
                "thresholded. ADA (van de Hulst anomalous diffraction) assumes a large, "
                "optically soft sphere, so it is worst at small radii."
            ),
            "model": {
                "n_inf": 1.40,
                "f_beta": 0.0,
                "oscillators": [
                    {"centre_cm1": c, "fwhm_cm1": w, "peak_k": p, "assignment": lab}
                    for c, w, p, lab in ph.oscillator_table(0.0)
                ],
                "grid": {
                    "lo_cm1": float(nu[0]),
                    "hi_cm1": float(nu[-1]),
                    "n": int(nu.numel()),
                    "spacing_cm1": float((nu[-1] - nu[0]) / (nu.numel() - 1)),
                },
            },
            "per_radius": rows,
        }
        (OUT / "ada_vs_mie.json").write_text(json.dumps(report, indent=2) + "\n")

        # ---- Amide I shift table, the fallback set's analogue of Lesson 1 ----
        shifts = {
            "null_means": (
                "the resonant distortion has flattened the apparent Amide I band away "
                "entirely, leaving no interior maximum in 1600-1700 cm^-1. Not a zero shift."
            ),
            "note": (
                "legacy/rmies_sim.py is absent, so the pre-registered Lesson 1 "
                "reproduction test is SKIPPED. These are the shifts the fallback "
                "oscillator set gives, listed next to the Lesson 1 targets for "
                "comparison only -- they are not a pass/fail check."
            ),
            "reference_position_cm1": _shift(nu, 1e-4, absolute=True),
            "per_radius": [
                {
                    "a_um": a,
                    "peak_max_shift_cm1": _shift(nu, a),
                    "second_derivative_shift_cm1": _shift(nu, a, second_derivative=True),
                    "lesson1_peak_max_shift_cm1": LESSON1_SHIFTS.get(a),
                }
                for a in RADII
            ],
        }
        (OUT / "amide_i_shifts.json").write_text(json.dumps(shifts, indent=2) + "\n")

        # ---------------------------- figure ----------------------------
        fig, ax = plt.subplots(2, 2, figsize=(13, 8.6), constrained_layout=True)

        for a_um in (0.5, 2.0, 4.0, 8.0):
            q_ada, q_mie = curves[a_um]
            (ln,) = ax[0, 0].plot(nu, q_mie, lw=1.1, label=f"a = {a_um} µm, exact Mie")
            ax[0, 0].plot(nu, q_ada, lw=1.1, ls="--", color=ln.get_color())
        ax[0, 0].set_xlabel("wavenumber / cm$^{-1}$")
        ax[0, 0].set_ylabel("$Q_{ext}$")
        ax[0, 0].set_title("solid = exact Mie (miepython), dashed = van de Hulst ADA")
        ax[0, 0].invert_xaxis()
        ax[0, 0].legend(fontsize=8)

        a_arr = np.array([r["a_um"] for r in rows])
        ax[0, 1].plot(a_arr, [r["mean_ratio"] for r in rows], "o-", label="mean $Q$ ratio ADA/Mie")
        ax[0, 1].plot(a_arr, [r["relative_rmse"] for r in rows], "s-", label="RMSE / mean $Q_{Mie}$")
        ax[0, 1].axhline(1.0, color="k", lw=0.8, ls=":")
        ax[0, 1].set_xlabel("sphere radius a / µm")
        ax[0, 1].set_title("ADA error vs radius\n(E1 infers with ADA, so this is its model error)")
        ax[0, 1].set_yscale("log")
        ax[0, 1].legend(fontsize=8)
        ax[0, 1].grid(alpha=0.3)

        for a_um in (0.5, 2.0, 4.0, 8.0):
            q_ada, q_mie = curves[a_um]
            ax[1, 0].plot(nu, q_ada - q_mie, lw=1.0, label=f"a = {a_um} µm")
        ax[1, 0].axhline(0.0, color="k", lw=0.8)
        ax[1, 0].set_xlabel("wavenumber / cm$^{-1}$")
        ax[1, 0].set_ylabel("$Q_{ADA} - Q_{Mie}$")
        ax[1, 0].set_title("residual: ADA minus exact Mie")
        ax[1, 0].invert_xaxis()
        ax[1, 0].legend(fontsize=8)

        nan = float("nan")
        ada_sh = [nan if r["amide_i_shift_ada_cm1"] is None else r["amide_i_shift_ada_cm1"]
                  for r in rows]
        mie_sh = [nan if r["amide_i_shift_mie_cm1"] is None else r["amide_i_shift_mie_cm1"]
                  for r in rows]
        ax[1, 1].plot(a_arr, ada_sh, "o-", label="ADA")
        ax[1, 1].plot(a_arr, mie_sh, "s--", label="exact Mie")
        gone = [a for a, v in zip(a_arr, ada_sh) if np.isnan(v)]
        for g in gone:
            ax[1, 1].axvline(g, color="grey", alpha=0.35, lw=6)
        la = sorted(LESSON1_SHIFTS)
        ax[1, 1].plot(la, [LESSON1_SHIFTS[a] for a in la], "k^:", label="Lesson 1 target")
        ax[1, 1].axhline(0.0, color="k", lw=0.8)
        ax[1, 1].set_xlabel("sphere radius a / µm")
        ax[1, 1].set_ylabel("apparent Amide I shift / cm$^{-1}$")
        ax[1, 1].set_title(
            "apparent Amide I shift (f$_\\beta$ = 0)\n"
            "fallback oscillator set, Lesson 1 numbers for comparison only"
        )
        ax[1, 1].legend(fontsize=8)
        ax[1, 1].grid(alpha=0.3)

        figpath = OUT / "ada_vs_mie.png"
        fig.savefig(figpath, dpi=120)
        plt.close(fig)
        run.notes["figure"] = str(figpath.relative_to(REPO_ROOT))

    print(json.dumps({"per_radius": rows}, indent=2))
    print("\nAmide I shifts:")
    for r in shifts["per_radius"]:
        tgt = "" if r["lesson1_peak_max_shift_cm1"] is None else (
            f"   (Lesson 1: {r['lesson1_peak_max_shift_cm1']:+.0f})"
        )

        def f(v: float | None) -> str:
            return "  no band" if v is None else f"{v:+7.1f}"

        print(
            f"  a = {r['a_um']:4.2f} um: peak max {f(r['peak_max_shift_cm1'])} cm^-1, "
            f"2nd deriv {f(r['second_derivative_shift_cm1'])} cm^-1{tgt}"
        )


def _shift(
    nu: torch.Tensor,
    a_um: float,
    second_derivative: bool = False,
    exact_mie: bool = False,
    absolute: bool = False,
) -> float | None:
    """Apparent Amide I position shift relative to the vanishing-scatter limit."""
    fn = (
        ph.amide_i_second_derivative_position if second_derivative else ph.amide_i_position
    )
    out = ph.forward(nu, ph.Theta(f_beta=0.0, a_um=a_um, phi=0.2), exact_mie=exact_mie)
    pos = fn(nu, out["A_app"])
    if absolute:
        return pos
    ref = ph.forward(nu, ph.Theta(f_beta=0.0, a_um=1e-4, phi=0.2), exact_mie=False)
    shift = pos - fn(nu, ref["A_app"])
    # nan means the apparent band has been flattened away; keep it as null in
    # the JSON rather than letting a railed argmax masquerade as a shift
    return None if np.isnan(shift) else round(shift, 3)


if __name__ == "__main__":
    main()
