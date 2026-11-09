# watford → mac, 03: re comms/2026-11-06_mac_to_watford_01.md

Status: DONE — but the machinery is **not valid**, so E1 should not be marked
APPROVED yet.

All six tasks are complete. The calibration gate passed, so task 5 ran as
instructed. The grid was not run.

**Read this first.** The positive control passes in both conditions. The
negative control fails in the raw condition, and by construction that can only
be a sampler artefact rather than anything about the likelihood or the physics.
It is fixable, but every fix I measured breaks E1's 6 h grid budget. That
trade-off is the one decision this reply needs from you.

Commits: `8f07934` (tasks 1–4), `0e209c7` (tasks 5–6), `<this commit>`
(sampler diagnostic). Every number below comes from a committed file.

## Per task

### 1. Preprocessed likelihood — DONE (`8f07934`)

`y_w ~ N(s·m_w + c0, σ² I)` on the rubberbanded 1600–1700 window, with `s` and
`c0` profiled by linear least squares at every call, `s` unconstrained, and σ
exact. `σ_pp = σ/‖y_w‖` is gone. `Preprocessor` no longer normalises;
`E1Problem` gains `.chi2()`, `.n_profiled` and `.dof`.

**One deviation, deliberate.** The required invariance test is written against
the **window**, not the spectrum. On `y_w` the invariance holds for any α ≠ 0.
Through the full pipeline it holds only for α > 0, because the rubberband is a
*lower* convex hull, so `rb(−y) ≠ −rb(y)` and a negative scale turns it into an
upper hull. That is correct behaviour, not a bug. Both are tested, and the
second test asserts the asymmetry so it cannot regress silently.

The existing test that the preprocessed likelihood ignores `baseline_offset`
and `baseline_slope` still passes. As you noted, it passes for the old reason —
the rubberband removes them — so it does not exercise `c0`; the new invariance
test is what covers that.

### 2. Noise rule — DONE, NOT BLOCKED (`8f07934`)

`results/e1/sigma_table.json`.

| a / µm | D(a) / AU | σ(a) / AU | apparent band depth / AU | σ(a)/σ_E0 |
|---|---|---|---|---|
| 0.25 | 0.00494 | 1.674e-5 | 0.00382 | 0.0153 |
| 1 | 0.01914 | 6.488e-5 | 0.01489 | 0.0591 |
| 2 | 0.03671 | 1.244e-4 | 0.02553 | 0.1134 |
| 3 | 0.05279 | 1.789e-4 | 0.02524 | 0.1631 |
| 3.5 | 0.06030 | 2.044e-4 | 0.01951 | 0.1863 |
| 4 | 0.06748 | 2.288e-4 | 0.01108 | 0.2085 |
| 5 | 0.08088 | 2.742e-4 | **0.00000** | 0.2499 |
| 6 | 0.09308 | 3.155e-4 | **0.00000** | 0.2876 |

D is monotone (0.00494 → 0.09308) and its minimum is 0.00494 AU, fifty times
the 1e-4 floor. Neither BLOCKED condition fires.

The rule behaves the way its rationale says it should. With n = 1 the complex
phase shift `z = 2xk + 2ix(n−1)` is purely real, so Q_ext is the
pure-absorption van de Hulst limit and rises monotonically to 2 instead of
oscillating. The last-but-one column is the reason that matters: the *apparent*
band depth is exactly 0.00000 at a = 5 and 6 µm, where the resonant distortion
has flattened the band away, so it could not have set σ there.

### 3. Two inference options — DONE (`8f07934`)

`fixed=` already existed from the earlier diagnostic. Added `inert_f_beta` to
`tissue_k`, `Theta` and `E1Problem`: it swaps bands 13–14 for band 12, so
`f_β` has no effect on the spectrum at all.

Tested: output identical for f_β = 0, 0.63 and 1; equal to pure α rather than a
blend; log-likelihood flat in f_β; and f_β *does* still change the spectrum
when the mode is off, so it is a mode and not a no-op.

### 4. Likelihood calibration — DONE. **GATE PASSES** (`8f07934`)

`results/e1/likelihood_calibration.{json,png}`, 200 draws per cell.

| a / µm | f_β | condition | N | dof | median χ² | p10 | p90 | median/dof |
|---|---|---|---|---|---|---|---|---|
| 0.25 | 0 | raw | 441 | 441 | 438.63 | 404.51 | 474.12 | 0.9946 |
| 0.25 | 0 | preprocessed | 52 | 50 | 48.70 | 36.83 | 60.68 | 0.9740 |
| 0.25 | 1 | raw | 441 | 441 | 438.63 | 404.51 | 474.12 | 0.9946 |
| 0.25 | 1 | preprocessed | 52 | 50 | 48.29 | 37.56 | 61.70 | 0.9658 |
| 3.5 | 0 | raw | 441 | 441 | 438.63 | 404.51 | 474.12 | 0.9946 |
| 3.5 | 0 | preprocessed | 52 | 50 | 49.93 | 36.45 | 69.20 | 0.9987 |
| 3.5 | 1 | raw | 441 | 441 | 438.63 | 404.51 | 474.12 | 0.9946 |
| 3.5 | 1 | preprocessed | 52 | 50 | 53.48 | 40.19 | 74.96 | 1.0696 |

Every median is inside ±10 %. The worst cell is preprocessed at a = 3.5,
f_β = 1 at +6.96 %.

The four raw cells are identical on purpose, not by accident: χ² of the truth
against its own data is `Σ(noise/σ)²`, which at matched seeds does not depend
on a or f_β at all. That it comes out at 438.63 against 441 is a check that the
raw likelihood carries no model error whatsoever.

### 5. Controls — DONE. **Positive PASSES, negative FAILS in raw** (`0e209c7`)

`results/e1/controls.{json,png}`. 240 runs, 75.7 min, 40 draws per condition
per set, at a = 0.25 µm under σ = 1.6737e-05 AU.

| set | condition | W med | W max | frac(W<0.05) | KS med | KS max | frac(KS<0.1) | verdict |
|---|---|---|---|---|---|---|---|---|
| positive (a fixed) | raw | 0.0000 | 0.0000 | **1.00** | 0.9950 | — | — | **PASS** |
| positive (a fixed) | preprocessed | 0.0000 | 0.0000 | **1.00** | 0.9910 | — | — | **PASS** |
| negative (f_β inert) | raw | 0.5000 | 0.7970 | — | 0.1346 | 0.3372 | **0.35** | **FAIL** |
| negative (f_β inert) | preprocessed | 0.5000 | 0.5544 | — | 0.0298 | 0.0673 | **1.00** | **PASS** |
| free_a (observation) | raw | 0.0000 | 0.0000 | 1.00 | 0.9949 | — | — | not thresholded |
| free_a (observation) | preprocessed | 0.0000 | 0.0000 | 1.00 | 0.9917 | — | — | not thresholded |

Minimum posterior samples across all runs: 4500, so the ≥ 2000 requirement
holds everywhere. **MACHINERY_VALID = False**, on the negative control alone.

**The raw failure can only be a sampler artefact.** With f_β inert the model
does not depend on f_β, so the posterior must reproduce the prior exactly —
there is nothing for the data to say. Three things pin it down:

- the log-likelihood really is flat in f_β (`test_inert_f_beta_likelihood_is_flat_in_f_beta`);
- KS median 0.1346 sits **21× above the 0.0063 sampling floor** for the 18,670
  equal-weight samples these runs produce;
- KS falls as the sample count rises (r = −0.38), which is the signature of
  incomplete mixing rather than a bias.

The preprocessed condition is clean: 0.0298 against a 0.0125 floor.

The asymmetry has a plain cause. At σ = 1.7e-5 over 441 points the raw
likelihood is extremely sharp in the six *constrained* parameters, so the
bounding ellipsoid is very thin and `rwalk`'s fixed step count moves slowly
along the flat f_β direction. The preprocessed condition has 52 points and two
parameters profiled away, so it is far less sharp and mixes fine.

**This is the redesigned control working.** The old noise-ladder version could
not have found this: it confounded "the sampler cannot mix" with "the noise has
not flattened the posterior". Making f_β inert separates them, exactly as
intended.

**The free-a observation flipped sign since reply 01.** It now passes in both
conditions — W = 0 in 40/40, radius recovered at 0.29 µm — where it failed at
0.70 under the old likelihood and noise. That is what
`results/e1/degeneracy_review.json` predicted: at tissue SNR the radius is
identifiable even through the preprocessed window. It remains an observation,
not a threshold.

### 6. Grid projection — DONE (`0e209c7`)

`results/e1/grid_projection.json`. Timed 8 runs at a = 3.5 and 5 µm:

| condition | mean wall | max wall | mean likelihood calls |
|---|---|---|---|
| raw | 450.6 s | 466.0 s | 497,354 |
| preprocessed | 286.6 s | 293.2 s | 192,248 |

640 runs → **65.5 h serial, 4.68 h on 14 workers.** Inside the 6 h budget, but
far tighter than the 1.16 h the old grid needed, because σ is now up to 65×
smaller and the posterior correspondingly sharper.

### Not a task: can the sampler be fixed? (`<this commit>`)

`results/e1/sampler_diagnostic.json`. **Labelled diagnostic, not a re-run of
the control** — `results/e1/controls.json` stands exactly as run. 16 runs at
a = 0.25 µm, raw, f_β inert, 4 draws per setting.

| setting | KS med | KS max | frac(KS<0.1) | floor | wall | × cost | projected grid |
|---|---|---|---|---|---|---|---|
| as run: nlive 400, rwalk | 0.1568 | 0.5114 | 0.25 | 0.0063 | 373 s | 1.00 | 4.68 h |
| nlive 1500, rwalk | 0.0547 | 0.0998 | **1.00** | 0.0033 | 1350 s | 3.62 | 16.96 h |
| nlive 400, rslice | 0.0601 | 0.0990 | **1.00** | 0.0064 | 784 s | 2.10 | **9.85 h** |
| nlive 1000, rslice | 0.0170 | 0.0903 | **1.00** | 0.0040 | 1968 s | 5.28 | 24.72 h |

**Every setting that fixes the control breaks the 6 h grid budget.** The
cheapest adequate one, `rslice` at the current nlive, roughly doubles the cost
and lands at 9.85 h on 14 workers.

Two cautions on that table:

- Four draws per setting is thin. `nlive 400, rslice` has a maximum KS of
  0.0990 against a 0.1 threshold, so I would not bet on it clearing ≥ 90 % over
  40 draws. Only `nlive 1000, rslice` (median 0.0170) has real margin, and it
  is the most expensive.
- The timings come from the negative-control configuration. Grid runs differ,
  so treat the ratios as indicative rather than exact.

## Deviations from the request

1. The task-1 invariance test is on the window rather than the spectrum, for
   the reason in task 1 above.
2. I ran the sampler diagnostic, which the request does not ask for. It is
   clearly labelled, it does not touch the committed control, and without it
   the reply would say "the machinery failed" with no way for you to judge the
   cost of fixing it. I did not re-run the control under any new setting: that
   is your call, and re-running after seeing a failure needs logging as a new
   labelled analysis either way.
3. Budget: tasks 4–6 took about 89 min against the 3 h allowance; the
   diagnostic added 39 min, so ~2.1 h in total. GPU untouched, disk well under
   2 GB, 14 workers throughout.

## Surprises

1. **The negative control caught a real sampler problem on its first run.**
   That is the control doing its job, and it is an argument for the redesign.
2. **Fixing it costs more than the grid budget allows.** This is the decision I
   need from you, and I have not pre-empted it.
3. **The free-a observation reversed.** Under the old likelihood and noise it
   failed at 0.70; it now passes at 1.00 in both conditions. Reply 01 blamed
   preprocessing for destroying the radius; that was wrong, and the degeneracy
   review's account — the radius is identifiable at tissue SNR, and the old
   failures were an SNR-3.5 artefact — is what the data now support.
4. **The apparent band depth is exactly zero at a = 5 and 6 µm.** This is the
   same flattening that produced the −55.9 cm⁻¹ artefact I corrected in reply
   01, and it is a good independent reason why D(a) rather than the apparent
   depth had to set σ.

## Proposed next steps (not started)

1. **Decide the sampler/budget trade-off.** As I see it:
   - *Adopt `rslice` and relax the budget* to about 10 h on 14 workers. The
     budget is a pre-registered number, so changing it should be logged like
     any other amendment.
   - *Adopt `rslice` and widen the pool.* Watford has 64 threads; the request
     caps me at 14 workers. At 28 workers the rslice grid is about 4.9 h. That
     needs Chris's agreement because the machine is shared with Haolin and with
     rat-lung.
   - *Try the cheaper fix I did not test:* keep `rwalk` and raise dynesty's
     `walks` (default 25) rather than `nlive`. That targets mixing directly and
     may cost well under 2×. About 40 min to test.
   My preference is to test `walks` first, since it is cheap and may make the
   whole trade-off go away.
2. **Re-run the negative control under whichever setting is chosen**, logged as
   a new labelled analysis, before E1 is marked APPROVED.
3. **The positive control and the gate do not need re-running** — both passed,
   and neither is affected by the f_β mixing problem, which only shows up when
   a direction is exactly flat.
4. For E1b, `scripts/e1_degeneracy_review.py` now takes about 4 minutes per
   model variant and is the cheap screen that outline asks for.

Nothing is running on watford. The GPU is idle, the rat-lung lock is free.
