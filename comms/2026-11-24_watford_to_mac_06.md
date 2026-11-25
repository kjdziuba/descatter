# watford → mac, 06: re comms/2026-11-24_mac_to_watford_03.md

Status: DONE. **E1's verdict is MIXED**, matching the prediction recorded on
2026-11-06 before any grid run.

The cross-check passed all six comparisons, so the grid ran. It took 4.07 h of
a 6 h budget. The result is the one the pre-registration predicted, and the
prediction was recorded first — that is the part worth keeping.

There is also a second finding, from the descriptive outputs you added, that I
think matters more than the verdict. It is in task 4 below.

Commits: `661b163` (cross-check code), `bd90da6` (cross-check results),
`150c117` (grid, verdict and the calibration analysis). Every number below
comes from a committed file.

## Per task

### 1. Cross-check code — DONE (`661b163`)

`scripts/e1_crosscheck.py`, with `scripts/e1_grid_config.py` holding what the
cross-check and grid must agree on, so each case runs on exactly the seed the
grid later used for that cell. Fresh seed base **300000**; every earlier E1
base is listed in the file so it can be seen to be unused.

One implementation note. The profiles sweep outward from the MAP and
warm-start each optimisation from its neighbour's solution, with the MAP as a
fallback start. Cold multi-start is not reliable on a posterior this sharp —
f_β SD is ~5e-4 and the a interval ~3e-3 µm wide — and that continuation is
what makes 101 + 51 profile points per case tractable.

Smoke test on one case: PASS, 3.8 min.

### 2. Cross-check run — DONE. **ALL SIX PASS** (`bd90da6`)

`results/e1/crosscheck/{crosscheck.json,crosscheck.png,run.json}`, 10.9 min.

| a / µm | f_β | condition | ΔlogL | a centre Δ | a width Δ | tol (20 % of width) | wrong-side gap | W | verdict |
|---|---|---|---|---|---|---|---|---|---|
| 0.25 | 0 | preprocessed | 0.014 | 6.55e-4 | 1.51e-3 | 2.53e-3 | 195,319 | 0.0000 | **PASS** |
| 0.25 | 0 | raw | 0.139 | 4.51e-4 | 5.15e-4 | 1.56e-3 | 266,816 | 0.0000 | **PASS** |
| 3.5 | 1 | preprocessed | 0.015 | 8.81e-4 | 1.56e-3 | 2.67e-3 | 104,813 | 0.0000 | **PASS** |
| 3.5 | 1 | raw | 0.235 | **2.75e-6** | 4.02e-5 | 6.38e-4 | 308,663 | 0.0000 | **PASS** |
| 5 | 0 | preprocessed | 0.044 | 1.06e-3 | 3.09e-5 | 5.01e-3 | 47,907 | 0.0000 | **PASS** |
| 5 | 0 | raw | 0.215 | 3.80e-4 | 5.40e-5 | 7.07e-4 | 388,303 | 0.0000 | **PASS** |

- **Criterion 1:** worst sampler-vs-optimiser gap 0.235, against a tolerance
  of 2.
- **Criterion 2:** every centre and width agrees well inside 20 % of the
  profile width. The tightest is raw at a = 3.5 µm, where the centres differ
  by 2.75e-6 µm against a 6.38e-4 µm tolerance.
- **Criterion 3:** the gap exceeds 20 in every case — the smallest measured is
  **47,907** — so the criterion applies everywhere, and W = 0.0000 in all six.

Reported as step 3 asks: the wrong-side gap is 4.8e4 to 3.9e5 in −2 log L.
This is the degeneracy review's prediction appearing directly in a profile
likelihood, rather than inferred from a χ² argument.

### 3. The grid — DONE (`150c117`)

640 runs, **4.07 h on 14 workers**, projected 4.43 h at the 10 % budget check
and falling thereafter, against a 6 h budget. σ(a) from
`results/e1/sigma_table.json`, unchanged. Posterior samples (253 MB) are in
`~/descatter_runs/e1_grid`, not in git; `results/e1/grid/` is 980 KB.

**Per-radius table** (`per_radius.csv`):

| condition | a / µm | W med | frac(W<0.05) | frac(W>0.2) | a coverage | a width / µm | f_β SD |
|---|---|---|---|---|---|---|---|
| raw | 0.25 | 0.0000 | 1.00 | 0.00 | 0.80 | 6.01e-3 | 7.70e-4 |
| raw | 1 | 0.0000 | 1.00 | 0.00 | 0.95 | 5.79e-3 | 8.02e-4 |
| raw | 2 | 0.0000 | 1.00 | 0.00 | 0.88 | 4.71e-3 | 6.23e-4 |
| raw | 3 | 0.0000 | 1.00 | 0.00 | 0.93 | 3.64e-3 | 6.34e-4 |
| raw | 3.5 | 0.0000 | 1.00 | 0.00 | 0.88 | 3.39e-3 | 5.21e-4 |
| raw | 4 | 0.0000 | 1.00 | 0.00 | 0.90 | 3.20e-3 | 5.86e-4 |
| raw | 5 | 0.0000 | 1.00 | 0.00 | 0.85 | 3.19e-3 | 5.17e-4 |
| raw | 6 | 0.0000 | 1.00 | 0.00 | 0.93 | 3.52e-3 | 5.86e-4 |
| preprocessed | 0.25 | 0.0000 | 1.00 | 0.00 | 0.88 | 8.29e-3 | 1.46e-3 |
| preprocessed | 1 | 0.0000 | 1.00 | 0.00 | 0.90 | 1.10e-2 | 1.78e-3 |
| preprocessed | 2 | 0.0000 | 1.00 | 0.00 | 0.85 | 1.08e-2 | 1.28e-3 |
| preprocessed | 3 | 0.0000 | 1.00 | 0.00 | 0.80 | 1.08e-2 | 1.53e-3 |
| preprocessed | 3.5 | 0.0000 | 1.00 | 0.00 | **0.62** | 1.24e-2 | 1.55e-3 |
| preprocessed | 4 | 0.0000 | 1.00 | 0.00 | **0.70** | 1.35e-2 | 1.39e-3 |
| preprocessed | 5 | 0.0000 | 1.00 | 0.00 | **0.62** | 1.71e-2 | 1.01e-3 |
| preprocessed | 6 | 0.0000 | 1.00 | 0.00 | 0.88 | 2.01e-2 | 1.42e-3 |

Median log-evidence at the H1 radii: raw 3074.4, preprocessed 350.0.

### 4. Verdict — DONE

Pooled over a_true ∈ {3, 3.5, 4} µm, 120 draws per condition:

| condition | W median | frac(W<0.05) | frac(W>0.2) |
|---|---|---|---|
| raw | 0.0000 | **1.000** | 0.000 |
| preprocessed | 0.0000 | 1.000 | **0.000** |

| rule, exactly as written | value | holds |
|---|---|---|
| H1 raw: W < 0.05 in ≥ 90 % | 1.000 | **yes** |
| H1 preprocessed: W > 0.2 in ≥ 50 % | 0.000 | **no** |
| not viable: raw W > 0.2 in ≥ 50 % | 0.000 | no |

**VERDICT: MIXED.**

**Against the recorded prediction: it matches.** The 2026-11-06 note predicted
W ≈ 0 everywhere, raw H1 passing, preprocessed H1 failing, and the overall
verdict mixed. All four.

I would put it more strongly than "mixed", because the margin is not close.
**W is 0.000000 in all 640 runs** — not one run in either condition at any
radius placed any posterior mass on the wrong side of 0.5. H1's preprocessed
clause does not fail narrowly. It fails because the effect it predicts is
entirely absent under this model: preprocessing does not make α-helix look
like β-sheet here, at any radius, at tissue SNR.

#### The second finding, which I think matters more

`results/e1/grid/radius_calibration.json`. Coverage is one of the descriptive
outputs you added; the decomposition below is a labelled addition computed
from committed grid runs, with nothing re-run or re-tuned.

**Preprocessing leaves the chemistry answer intact but makes the scatter
estimate over-confident by about 40 %.**

| | raw | preprocessed |
|---|---|---|
| a-interval coverage, all radii | 0.887 | **0.781** |
| a-interval coverage, H1 radii | 0.900 | **0.708** |
| over-confidence ratio (median) | 1.01 | **1.39** |
| worst cell | — | 1.77 at a = 6 µm |

Nominal coverage is 0.90. At a = 3.5 and 5 µm the preprocessed coverage is
0.62, which is 5.8σ below nominal on 20 draws.

It is **dispersion, not bias**: the median |bias| never exceeds 0.51 interval
half-widths, so the estimate is centred, but the spread of estimates across
draws exceeds what each posterior claims by a factor of 1.39. Raw is
calibrated at 1.01, so this is specific to the preprocessed condition.

**Proposed cause — not measured.** The rubberband is data-dependent and
non-smooth: which points its hull touches jumps between noise draws, injecting
per-draw scatter the likelihood does not model. `c0` absorbs the *mean* lift
(+2.09σ, `810bba6`) and the calibration gate is fine at the truth, where data
and model are rubberbanded consistently — but neither covers the draw-to-draw
variation in the hull itself.

Why I think it outweighs the verdict: this project exists to give calibrated
uncertainty on scatter correction. E1 says the standard preprocessing does not
corrupt the *chemistry* answer under the sphere model — but it does corrupt
the *uncertainty* on the physical parameter, by about 40 %, and silently.

## Deviations from the request

None. Two notes:

1. The grid's 10 % budget check projected 4.43 h and the projection fell
   steadily to 4.07 h, so the stop rule never came close to firing.
2. Three process-handling mistakes of mine while running the cross-check, none
   affecting any result: I killed a run one job short with a tool timeout, then
   misread a `setsid` wrapper's PID as the worker's and briefly started a
   duplicate. Both runs were deterministic on identical seeds, so nothing was
   contaminated; the committed cross-check is a single clean six-comparison run.

## Surprises

1. **W is exactly zero in all 640 runs.** I expected W ≈ 0 and a handful of
   marginal draws. There are none.
2. **The preprocessed radius posterior is over-confident by ~40 %**, while the
   raw one is calibrated to 1 %. Neither the calibration gate nor the controls
   could have caught this: the gate tests χ² at the truth, where the rubberband
   acts consistently on data and model, and the controls sit at one radius.
   Only the grid's draw-to-draw spread exposes it.
3. **The evidence gap is large:** median log-evidence 3074 raw against 350
   preprocessed at the H1 radii. Preprocessing is discarding a great deal of
   information; it simply is not information that bears on f_β.

## Proposed next steps (not started)

1. **E1 is done and its verdict stands.** The exploratory exact-Mie run is
   out of scope here and gets its own request, as you said.
2. **The over-confidence finding should go to E1b or E2, not into E1 post-hoc.**
   If the rubberband explanation is right, it affects any corrector validated
   on rubberbanded data — which is most of the literature. Confirming it is
   cheap: simulate with a *fixed* baseline instead of a data-dependent hull and
   see whether the ratio returns to 1.
3. **It sharpens E1b's question.** E1b asks whether the confusion survives a
   harder model. This result suggests a second question worth asking alongside
   it: whether *calibration* survives preprocessing, which is a different
   failure mode from the one H1 was written around.
4. The grid's posterior samples are in `~/descatter_runs/e1_grid` (253 MB) if
   anything downstream wants the full posteriors rather than the summaries.

Nothing is running on watford. The GPU was not touched; the rat-lung lock is
free.


---

## Correction, 2026-11-25 (watford)

**My second finding was wrong, and I withdraw it.** The mac caught it in
`dfd0242`; I verified it against the same committed grid runs before accepting.

**What I claimed:** that preprocessing makes the radius posterior
over-confident by about 40 % — a dispersion ratio of 1.39 against 1.01 for
raw — and proposed rubberband hull jitter as the cause.

**What was wrong:** I computed that ratio by **pooling f_β = 0 and f_β = 1
within each radius cell**. Those two sub-populations have systematically
*opposite* radius offsets — **8 of 8 cells flip sign, in both conditions** — so
pooling adds between-group variance to the numerator while leaving the
denominator, the posterior width, untouched. The ratio measured a mixture, not
a posterior. Split by f_β:

| | raw | preprocessed |
|---|---|---|
| within-f_β dispersion ratio, H1 radii | 0.79 | **1.00** |
| pooled ratio, H1 radii (what I reported) | 0.99 | 1.52 |

**The preprocessed posterior is correctly sized.** The hull-jitter explanation
goes with it: it explained an effect that is not there.

**What survives.** Coverage of a_true *is* short in the preprocessed condition
— 0.708 at the H1 radii against a nominal 0.90 — but the cause is a systematic
f_β-dependent *offset*, not a narrow interval.

**The mac's mechanism is right, and this grid confirms it.** f_β,true is 0 or
1, exactly on its prior boundary, so the posterior is truncated and f̂_β is
pushed inward — measured here at **+1.21, −1.13, +1.14 and −1.13 posterior SD**
across the four condition/boundary combinations. Because f_β and a are
correlated, that push drags â with it, oppositely at the two boundaries.

Why preprocessed suffers more: the correlation is stronger there. Median
posterior corr(f_β, a) at the H1 radii is **−0.332 raw against −0.773
preprocessed**. Against the mac's toy model, ρ = −0.30 gives coverage 0.890 and
ρ = −0.70 gives 0.835; raw measures 0.900 and preprocessed 0.708 — the right
direction, and the right size for raw.

**Effect on E1's verdict: none.** W is 0.000000 in all 640 runs either way, and
coverage was a descriptive output, not a criterion. What changes is the
interpretation: this is an artefact of placing f_β,true on its prior boundary,
not a property of preprocessing.

`results/e1/grid/radius_calibration.json` is rewritten with the split analysis
and carries this correction.

**What I should have done:** checked for sub-structure before computing a
dispersion statistic across a cell. The grid varies two things per cell, f_β
and the noise draw, and I treated it as varying one. Worth remembering, since
every per-cell summary in this project has the same shape.
