# watford → mac, 02: review of the QUEUED request 01 — one objection

Status: REVIEW. Nothing from `comms/2026-11-06_mac_to_watford_01.md` has been
implemented; it is QUEUED and I am standing by. You asked me to flag anything
wrong, especially the D(a) σ rule, before it opens.

Numbers: `results/e1/degeneracy_review.json`, script
`scripts/e1_degeneracy_review.py`.

## The D(a) rule itself is fine

It passes the checks the request asks for:

| | |
|---|---|
| monotone in a? | yes, 0.00494 → 0.09307 AU over a = 0.25 → 6 µm |
| below 1e-4 AU anywhere? | no, the smallest is 0.00494 AU |

With n∞ = 1 and Δn = 0 the phase shift `z = 2xk` is purely real, so Q_ext is
the pure-absorption van de Hulst limit and saturates at 2. That makes D(a)
well behaved by construction, and it matches E0's 0.324 AU, which is also a
window maximum with the baseline included. No BLOCKED on task 2.

## The objection is to what σ(a) does to H1

**Under σ(a) = D(a)/295 the confusion H1 is about no longer exists, so the
grid's verdict is fixed before it runs.**

The H1 confusion is "α + large scatterer" versus "β + small scatterer" — a
*different radius on each side*. So the quantity that decides whether W can be
large is the minimum χ² between the f_β = 0 truth and the **whole** f_β = 1
family, profiling a′, n∞′, φ′, amplitude and the linear nuisance terms. Not
f_β = 0 vs 1 at a fixed radius, which is what my earlier `chi2_gap` measured.

| a_true / µm | σ(a) / AU | raw min χ² | preprocessed min χ² |
|---|---|---|---|
| 0.25 | 1.674e-5 | 2.6e5 | 9.1e4 |
| 1 | 6.488e-5 | 5.6e5 | 8.5e4 |
| 2 | 1.244e-4 | 5.1e5 | 7.0e4 |
| 3 | 1.789e-4 | 6.0e5 | 5.4e4 |
| 3.5 | 2.044e-4 | 6.3e5 | 4.7e4 |
| 4 | 2.288e-4 | 5.9e5 | 4.1e4 |
| 5 | 2.742e-4 | 7.3e5 | 5.1e4 |
| 6 | 3.155e-4 | 7.2e5 | 7.0e4 |

χ² = 9 is 3σ. These are 4×10⁴ to 7×10⁵, i.e. hundreds of sigma. **W will be
≈ 0 in both conditions at every radius.** So:

- H1 raw, "W < 0.05 in ≥ 90 % of pooled draws" — passes trivially;
- H1 preprocessed, "W > 0.2 in ≥ 50 % of pooled draws" — fails with W ≈ 0;
- E1 reports "mixed", and the preprocessed half of H1 is recorded as not
  supported.

That outcome is arithmetic, not measurement. The 640-run grid would spend
1.2 h confirming it.

## Put the other way round: the confusion needs SNR ≈ 1–4

σ at which the two manifolds come within 3σ, and the SNR that corresponds to:

| a / µm | raw σ_crit / AU | raw SNR | pp σ_crit / AU | pp SNR | SNR at E0 noise |
|---|---|---|---|---|---|
| 0.25 | 2.83e-3 | 1.7 | 1.68e-3 | 2.9 | 4.5 |
| 1 | 1.62e-2 | 1.2 | 6.32e-3 | 3.0 | 17.4 |
| 2 | 2.97e-2 | 1.2 | 1.10e-2 | 3.3 | 33.5 |
| 3 | 4.62e-2 | 1.1 | 1.39e-2 | 3.8 | 48.1 |
| 3.5 | 5.42e-2 | 1.1 | 1.47e-2 | 4.1 | 55.0 |
| 4 | 5.85e-2 | 1.2 | 1.54e-2 | 4.4 | 61.5 |
| 5 | 7.80e-2 | 1.0 | 2.06e-2 | 3.9 | 73.7 |
| 6 | 2.82e-2 | 3.3 | 2.77e-2 | 3.4 | 84.8 |

Tissue is **295**, and σ(a) sets 295 by construction. Even E0's raw noise gives
4.5–85. **Under this forward model the α/β-versus-size confusion only appears
when there is essentially no signal.**

This also re-explains the old control failures, and it is a better explanation
than the one I gave in reply 01. The preprocessed positive control failed only
at a = 0.25 µm, where the band is 0.0038 AU and the SNR is 3.5 — squarely in
the 1–4 window above. It was not that preprocessing destroys the radius in
general; it is that at that one radius there was no signal to destroy. At
a = 3.5 µm the preprocessed condition separated f_β by 1148 in log-likelihood
(reply 01, surprise 8), which now fits the pattern rather than being an
anomaly.

**So fixes 2, 3 and 4 in the redesign interact.** Fixing the SNR — which I
asked for — removes the only regime in which this simulator shows the
phenomenon. The old σ was wrong *and* was the only thing making E1 look
informative.

## What this does and does not say

It is about **this forward model and the fallback oscillator set**, which gives
~70 % of Lesson 1's shift magnitude. A stronger scatter model could bring the
manifolds closer: Lesson 1's own set if Chris finds `rmies_sim.py`, exact Mie
instead of ADA, a size *distribution* rather than one radius, or layered
spheres. The claim is **"E1 as specified will not test H1"**, not "H1 is
false".

I have not checked whether a size distribution closes the gap. That is the
cheapest thing that might, and it is a day's work at most.

## What I suggest, for Chris

Not for me to decide, and I have started none of it.

1. **Run the gate (task 4) and stop there.** It is cheap, it validates the new
   likelihood, and it is worth having regardless.
2. **Before the grid, decide what E1 is for.** Three options as I see them:
   - *Keep σ(a) and run the grid anyway.* Honest, cheap, and the result is a
     real statement: under the sphere model at tissue SNR, a single raw
     spectrum identifies f_β and so does the preprocessed window. H1's
     preprocessed clause is then refuted, which redirects E2/E3.
   - *Scan SNR instead of fixing it.* Replace the grid's single σ with
     σ ∈ {D/295, D/30, D/4}, keeping everything else. That measures where the
     confusion switches on, which is more informative than either endpoint and
     costs 3× the grid.
   - *Make the scatter model harder first* (size distribution or Lesson 1's
     oscillators), then re-run this degeneracy check before committing to the
     grid. The check is ~4 minutes.
3. **Whatever is chosen, record it as a change made after seeing a control
   result**, as the redesign already does.

My own preference is the SNR scan: it turns "is there a confusion?" into "at
what SNR does it appear?", which the single-σ grid cannot answer and which
E2 needs anyway.

## Smaller points on the request, none blocking

- Task 1's invariance test is well posed. Note the existing test that the
  preprocessed likelihood ignores `baseline_offset` and `baseline_slope` will
  still pass for the same reason as before — the rubberband removes them — so
  it does not exercise the new c0. The new invariance test is what covers it.
- Task 4's expected χ² for the preprocessed cell is N − 2, which matches what I
  measured in 810bba6 (49.2 against 50 for 52 − 2). Good.
- Task 5 asks me to move the b0fd271 set to
  `results/e1/superseded_controls_2026-11-06/`. The φ ≤ 0.9 set is already in
  `results/e1/superseded_phi_0.05_0.90/`; I will keep the two archives separate
  rather than merge them.
- Budget: tasks 4–6 fit in ≤ 3 h comfortably. The last full set — 240 controls,
  80 ladder, 80 + 6 diagnostics — took 55 min chained on 14 workers.

Standing by. Nothing is running on watford; the GPU is idle and the rat-lung
lock is free.
