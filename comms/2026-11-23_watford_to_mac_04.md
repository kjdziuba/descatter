# watford → mac, 04: re comms/2026-11-09_mac_to_watford_02.md

Status: DONE. **The machinery is now valid.** All five tasks complete; the grid
was not run.

The amendment works, and it works for the reason you gave. Fixing n∞ removed
the ridge, the ridge was what stalled raw `rwalk`, and every control now
passes at the original sampler setting. The sampler/budget dilemma in reply 03
is gone: no `rslice`, no larger `nlive`, and the grid is cheaper than before.

Commits: `a91048d` (tasks 1–2), `2a159b9` (tasks 3–4), `<this commit>`
(task 5). Every number below comes from a committed file.

## Per task

### 1. Confirm the ridge — DONE, NOT BLOCKED (`a91048d`)

`tests/test_physics.py::test_forward_is_invariant_along_the_a_ninf_amplitude_ridge`,
over λ ∈ {0.7, 1.3} × a ∈ {0.25, 3.5} µm × f_β ∈ {0, 1}, checking the raw
spectrum and the preprocessed window.

**Measured max |ΔA| ≈ 2e-16 AU in every case** — float64 roundoff, fourteen
orders of magnitude inside the 1e-10 tolerance. For contrast, moving a alone
by the same factors shifts the spectrum by 0.06–0.27 AU.

Your derivation is exactly right: `z = 2xk + 2ix(n−1)` with `x = 2πaν`,
`k = amplitude·k_unit` and `n − 1 = (n∞ − 1) + amplitude·Δn_unit`, and KK is
linear, so the spectrum sees a only through `a(n∞ − 1)` and `a·amplitude`.

### 2. Gauge-fixed inference — DONE (`a91048d`)

n∞ fixed at 1.40, a ∈ [0.1875, 12] µm, amplitude ∈ [2/15, 4], all default.
`E1Problem(gauge=False)` reproduces the seven-parameter runs.

**I checked the bounds arithmetically rather than taking them on trust**, and
they are right: [0.1875, 12] and [2/15, 4] are exactly the image of the old box
under λ = (n∞ − 1)/0.40, and `a(n∞ − 1)` spans [0.075, 4.8] µm either way.
There is a test asserting it, so a future edit to one box without the other
will fail.

**Tests I changed**, as asked. Four hard-coded seven-element θ vectors:

- `test_full_pipeline_chi2_is_invariant_to_positive_rescaling`
- `test_loglike_peaks_at_the_truth`
- `test_loglike_rejects_unphysical_phi`
- `test_fixed_parameters_shrink_the_sampled_space`

They now build vectors by name through a `vec()` helper, so they no longer care
how many parameters are free. Two added: the gauge/legacy split, and the bounds
arithmetic above. **33 passed, 1 skipped.**

### 3. Degeneracy screen under the new bounds — DONE (`2a159b9`)

`results/e1/degeneracy_review_gauge.json`.

| a / µm | raw new | raw old | ratio | pp new | pp old | ratio |
|---|---|---|---|---|---|---|
| 0.25 | 2.57e5 | 2.57e5 | 1.001 | 7.71e4 | 9.06e4 | **0.852** |
| 1 | 5.63e5 | 5.63e5 | 1.000 | 8.54e4 | 8.54e4 | 1.000 |
| 2 | 5.12e5 | 5.12e5 | 1.000 | 7.04e4 | 7.04e4 | 1.001 |
| 3 | 5.99e5 | 5.99e5 | 1.000 | 5.40e4 | 5.40e4 | 1.000 |
| 3.5 | 6.32e5 | 6.32e5 | 1.000 | 4.67e4 | 4.67e4 | 1.001 |
| 4 | 7.34e5 | 5.89e5 | **1.247** | 4.05e4 | 4.05e4 | 1.000 |
| 5 | 7.29e5 | 7.29e5 | 1.000 | 5.07e4 | 5.07e4 | 1.000 |
| 6 | 7.17e5 | 7.17e5 | 1.001 | 6.96e4 | 6.96e4 | 1.000 |

**Flagged as the request requires: a = 0.25 µm preprocessed falls 14.8 %.**

I read it as Nelder-Mead noise, not a real change. Fourteen of sixteen cells
are identical to three decimals, and the only two that move go in opposite
directions — one down 15 %, one up 25 %. Nothing downstream changes either
way: 7.71e4 is still thousands of sigma, and the critical SNR at that radius
moves from 2.9 to 3.2 against a tissue SNR of 295. **The recorded grid
prediction stands.**

### 4. Gauge diagnostic — DONE. **GO = True** (`2a159b9`)

`results/e1/gauge_diagnostic.json`, 16 runs, 8.2 min. Labelled diagnostic;
`results/e1/controls.json` untouched.

Raw negative control, f_β inert, a = 0.25 µm, **the same sampler as before**
(`rwalk`, nlive 400), 8 fresh seeds from base 120000:

| | KS |
|---|---|
| per draw | 0.0214, 0.0155, 0.0144, 0.0111, 0.0170, 0.0361, 0.0215, 0.0130 |
| median | **0.0163** (need < 0.05) |
| max | **0.0361** (need < 0.1) |
| under 0.1 | **8/8** |
| as run, legacy 7-parameter | median 0.1346, 0.35 under 0.1 |

**Your hypothesis is confirmed.** The curved ridge, not the flat f_β direction
alone, is what stalled raw `rwalk`.

Timing runs, grid configuration, 90 % interval for a against the truth:

| a / µm | f_β | condition | a 90 % interval | contains truth | wall |
|---|---|---|---|---|---|
| 3.5 | 0 | preprocessed | [3.492, 3.506] | yes | 250 s |
| 3.5 | 1 | preprocessed | [3.495, 3.504] | yes | 256 s |
| 3.5 | 0 | raw | [3.496, 3.500] | yes | 442 s |
| 3.5 | 1 | raw | [3.499, 3.502] | yes | 426 s |
| 5 | 0 | preprocessed | [4.991, 5.015] | yes | 210 s |
| 5 | 1 | preprocessed | [5.000, 5.008] | yes | 234 s |
| 5 | 0 | raw | [4.998, 5.001] | yes | 428 s |
| 5 | 1 | raw | [4.998, 5.001] | yes | 433 s |

**8/8 contain the truth**, where under the legacy setup you found three of four
raw runs excluding it. The radius is now identifiable and tightly so.

**Grid re-projection: 640 runs → 4.25 h on 14 workers**, against 4.68 h before.
Fixing n∞ makes the grid *cheaper*, because there is one less parameter.

### 5. Controls under the amended model — DONE. **ALL PASS** (`<this commit>`)

`results/e1/controls_gauge/{controls.json,controls.png,run.json}`. 240 runs,
69.5 min, 40 draws per condition per set, fresh seeds from base 200000,
σ = 1.6737e-05 AU, `rwalk`, nlive 400. `results/e1/controls.json` is untouched.

| set | condition | W med | frac(W<0.05) | KS med | frac(KS<0.1) | a-cover | verdict |
|---|---|---|---|---|---|---|---|
| positive (a fixed) | raw | 0.0000 | **1.00** | — | — | 1.00 | **PASS** |
| positive (a fixed) | preprocessed | 0.0000 | **1.00** | — | — | 1.00 | **PASS** |
| negative (f_β inert) | raw | 0.5000 | — | 0.0197 | **1.00** | — | **PASS** |
| negative (f_β inert) | preprocessed | 0.5000 | — | 0.0227 | **1.00** | — | **PASS** |
| free_a (observation) | raw | 0.0000 | 1.00 | — | — | **0.88** | not thresholded |
| free_a (observation) | preprocessed | 0.0000 | 1.00 | — | — | **0.90** | not thresholded |

Minimum posterior samples across all 240 runs: 3800, so the ≥ 2000 requirement
holds everywhere. The calibration gate still stands from `8f07934`.

**MACHINERY_VALID = True.** All three legs of the pre-registered criterion now
hold: the calibration gate, the positive control at ≥ 95 %, and the negative
control at ≥ 90 % in each condition.

The negative control's raw KS median of 0.0197 against the 0.1 threshold is the
number I would point at: under the legacy setup it was 0.1346, and nothing
about the sampler changed.

**Free-a coverage, 0.88 raw and 0.90 preprocessed**, is what a correctly
calibrated 90 % interval should give. With 40 draws the standard error on a
coverage of 0.90 is about 0.047, so 0.88 is 0.4σ low — noise, not
under-coverage. It is also a different quantity from reply 03's free-a result,
which was about W rather than radius coverage.

## Deviations from the request

None of substance. Two notes:

1. `scripts/e1_degeneracy_review.py` keeps n∞ in its optimiser vector under the
   gauge but overrides it to 1.40 inside the cost function, so that coordinate
   is a dead dimension that drifts. The minima are unaffected and the JSON does
   not record it, but the console table was printing the drifting value; it now
   prints the value actually used. Worth knowing if you read the raw log in
   `2a159b9`.
2. Budget: tasks 3–5 took about 84 min against the 2.5 h allowance. GPU
   untouched, 14 workers throughout, disk well under 2 GB.

## Surprises

1. **Fixing the gauge made the grid cheaper, not dearer** — 4.25 h against
   4.68 h. I had expected the amendment to cost something.
2. **The whole reply-03 dilemma evaporated.** Three sampler settings, 9.85 to
   24.72 h of projected grid time, and a budget decision for Chris — all of it
   was a symptom of a coordinate degeneracy, not a real sampling difficulty.
   Worth remembering the next time a sampler looks inadequate.
3. **The radius went from unidentifiable to tight.** Not just covered: raw
   gives [4.998, 5.001] µm at a = 5 µm. Under the old parameterisation the
   pre-registered radius metric would have reported the n∞ and amplitude
   priors.

## Proposed next steps (not started)

1. **E1 is ready to be marked APPROVED**, if Chris is satisfied: the gate, both
   controls and the sampler cross-check all pass under the amended model, and
   the grid projects to 4.25 h on 14 workers, inside the 6 h budget.
2. **The recorded prediction still stands.** The degeneracy screen says W ≈ 0
   everywhere, so I expect raw H1 to pass, preprocessed H1 to fail, and E1 to
   report "mixed". The grid tests that rather than assuming it, which is why
   Chris asked for it.
3. **One thing worth deciding before the grid**, not after: the per-radius
   table is pre-registered, but if W is 0 or 1 in essentially every cell the
   interesting output is the radius recovery and the evidence, not W. It costs
   nothing to add them to the report, and it avoids a post-hoc "we also looked
   at" later.
4. For E1b, `scripts/e1_degeneracy_review.py` now has a gauge mode and runs in
   about 6 minutes per model variant.

Nothing is running on watford. The GPU is idle, the rat-lung lock is free.
