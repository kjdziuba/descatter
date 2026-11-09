# Superseded: the E1 controls before the 2026-11-06 redesign

These ran under φ ∈ [0.05, 0.30] but with the **old** preprocessed likelihood
(vector normalisation with σ_pp = σ / ‖y_w‖), the **old** noise level (E0's
flat 1.097e-3 AU) and the **old** control definitions (free a; negative control
by raising σ). Commit `b0fd271`.

The redesign in `docs/EXPERIMENTS.md` (E1, "Redesign 2026-11-06") replaced all
three. The current controls are one level up.

**What these showed, and why it is still worth keeping:**

| file | finding |
|---|---|
| `controls.json` | both controls failed: positive preprocessed 0.70 of draws, negative raw 0.75, negative preprocessed 0.00 |
| `sigma_ladder.json` | σ_eff saturates at ≈0.049 AU in the preprocessed condition, so the old negative control could never fire at any σ — raw fired at σ × 300 |
| `diagnostics.json` | with a held at its true value the positive control passes in both conditions, 40/40 draws each; the six (f_β, a) profile grids agree with dynesty |

The a-fixed diagnostic is now the pre-registered positive control, and the
profile grids remain the sampler cross-check E1 step 3 asks for.

An earlier set under φ ∈ [0.05, 0.9] is in
`results/e1/superseded_phi_0.05_0.90/`.

Do not quote any of this as a current E1 result.
