# Superseded: E1 runs under φ ∈ [0.05, 0.9]

These are the E1 control, ladder and diagnostic runs made before Chris
narrowed the φ prior to **[0.05, 0.30]** on 2026-11-06 (mac, WORKLOG; the φ
note at the end of E1 in docs/EXPERIMENTS.md). They sampled the old
φ ∈ [0.05, 0.9].

They are kept because the two findings that drove the control redesign do not
depend on the φ prior, and the evidence for them lives here:

- `sigma_ladder.json` — in the preprocessed condition σ_eff saturates at
  ≈ 0.049 AU, so the negative control can never fire under
  σ_pp = σ / ‖y_w‖. Flat KS 0.27–0.29 from σ × 10 to σ × 10000.
  The raw negative control does fire, at σ × 1000.
- `diagnostics.json` — with a held at its true value the positive control
  passes in both conditions (W = 0 in 40/40 draws each), so the sampler and
  likelihood are sound.

The headline numbers under the current prior are in the files one level up.
Do not quote these as E1 results.
