# WORKLOG: descatter

Newest entry on top. Label each entry by machine: (mac), (watford) or (chat).

## 2026-11-06 (watford): E0 done, E1 built, both controls fail

Reply: `comms/2026-11-06_watford_to_mac_01.md`. Request 01 is answered in full;
the grid was not run, since E1 is still DRAFT.

**E0.** venv (Python 3.12.13, torch 2.14.1+cu130), GPU check under the rat-lung
lock, Zenodo sample with 36/36 md5s verified, `s10_c048` inspected.
- Noise σ over tissue: median **1.097e-3 AU** (p10 8.0e-4, p90 1.5e-3), so E1's
  1e-3 fallback was right.
- Amide I: peak 0.324 AU, apparent position median 1655.1 cm⁻¹ (p10–p90
  1649–1659).
- Absorbance maxes out at exactly 8.0 AU — some channels are clipped.

**Three data facts worth keeping.**
1. PCUK2023's source cubes are on Isilon under
   `Group Members/Dougal_Ferguson/Prostate Project/HDF5 Data/`. The 199 GB
   download is avoidable.
2. The cores are still in paraffin: wax bands reach 4.8 AU at 2920/2850.
3. In every `*_raw.h5` the `/mask` shape differs from `/spectra`, so it is
   unusable as shipped.

**"Preprocessed" is now defined** in `docs/PCUK2023_PREPROCESSING.md`. The grid
is raw channels 12–1314 minus PyIR's `remove_wax` and `remove_co2` ranges
(arithmetic closes exactly on 965). The values are an SG second derivative of a
min-to-zero, vector-normalised spectrum; the window and any denoising step are
inferred, not confirmed, and the Methods section is paywalled from here.

**E1 steps 1–2 pass.** KK correlation 1.000000, scale 0.999666; ADA extrema
3.1731 at ρ 4.0856 and 1.5423 at ρ 7.6231. 23 tests pass, 1 skipped (Lesson 1,
no `rmies_sim.py`). ADA is 2–3× too large below a = 1 µm, best at 2–2.5 µm and
~20 % low above 3 µm, but the Amide I shift tracks exact Mie within ~4 cm⁻¹ for
a ≥ 2 µm.

**E1 controls: both fail.** 240 runs under φ ∈ [0.05, 0.30].

| control | condition | frac(W<0.05) | frac(KS<0.1) | verdict |
|---|---|---|---|---|
| positive | raw | 1.00 | — | PASS |
| positive | preprocessed | 0.70 | — | FAIL |
| negative | raw | — | 0.75 | FAIL |
| negative | preprocessed | — | 0.00 | FAIL |

**The machinery is not what is broken.** With `a` held at its true value the
positive control passes in both conditions (W = 0 in 40/40 each). The six
profile grids agree with dynesty everywhere and show why the free-`a` version
fails: at truth a = 0.25 µm the preprocessed profile peaks at a = 8.00 µm, with
f_β = 0 at a = 6.97 µm within 1.1 log-likelihood of the best fit. The control is
confounded with H1, exactly as the mac read it.

The negative control is settled by the ladder: raw fires at σ × 300, and
preprocessed never does, because σ_eff saturates at 0.049 AU
(`σ_pp = σ/‖y_w‖` with `‖y_w‖ ∝ σ`).

**Two corrections made this session.**
- *Mine.* The first Amide I shift table gave −55.9 cm⁻¹ at a = 5 and 6 µm. That
  was the peak-picker railing against the 1600 cm⁻¹ window edge after the band
  had been flattened away (1656 − 55.9 = 1600.1). Fixed with a `nan` return and
  a regression test. The inversion is near 5 µm, as Lesson 1 says — not 6.5 µm
  as I claimed.
- *Measured, against the mac's estimate.* σ × 100 gives Δχ² = 0.016 (raw), not
  20–190: the gap scales as 1/σ². The mac has since corrected this in the DRAFT.

**φ narrowed to [0.05, 0.30]** on Chris's instruction, and the controls, ladder
and diagnostics were all re-run. The narrowing removes the rejection entirely:
20,000/20,000 prior draws are now valid, against 49.7 % before, so the effective
prior on `a` is exactly uniform. The φ ≤ 0.9 runs are kept in
`results/e1/superseded_phi_0.05_0.90/`.

**Open for Chris.**
1. The control redesign (the mac's four proposals in `016fa5d`). I agree with
   all four; on the preprocessed likelihood I prefer the mac's free-scale
   version to my fixed-reference-norm one.
2. **The SNR mismatch is the one I would not defer.** The simulated Amide I is
   0.0038 AU at a = 0.25 µm and at most 0.026 AU, against 0.324 AU on tissue —
   SNR 3.5–23 against ~295. In this model all absorbance arrives through Q_ext,
   so there is no "negligible scattering, normal absorbance" regime for the
   positive control to sit in. Either add a path-length term or restrict E1's
   claim to the low-SNR regime.
3. One grid observation worth weighing before APPROVED: at a = 3.5 µm the
   preprocessed condition identified f_β decisively (wrong f_β penalised by
   1148 in log-likelihood). H1 predicts the opposite. Three cases, one noise
   draw each — not a substitute for the grid.

**Cost of the grid when approved:** 640 runs, 16.2 h serial, **1.16 h on 14
workers**, inside the 6 h budget. Lower bound: the controls sit at a = 0.25 µm
where the posterior is simplest.

Nothing is running on watford. The GPU is idle and the lock is released.

## 2026-11-06 (mac): coordinator's first session

**State:** `comms/2026-11-05_chat_to_watford_01.md` is OPEN and has no reply
yet. Watford may not have started.

**Done:**
- Filled in the mac row of docs/machines.md.
- `legacy/rmies_sim.py`: not on the Mac (checked Spotlight and ~/Projects). If
  Chris doesn't add it, watford uses the fallback oscillator set, as request 01
  says.
- Watford can't be reached by session messaging from the Mac, so Chris nudges
  it.

**E1 pre-registration review, for Chris before he marks it APPROVED.** E1 is
still DRAFT, so these are clarifications, not amendments.

1. **The negative control as written won't fire.**
   - Back-of-envelope: absorbance Lorentzians, Amide I 0.5 AU, HWHM 12 cm⁻¹,
     amplitude and linear baseline profiled out, no scatter.
   - With noise σ × 100, the Δχ² between f_β = 0 and f_β = 1 is still about
     190 at σ = 1e-3 and about 22 at σ = 3e-3. So the f_β posterior won't
     match the prior.
   - The KS < 0.1 test needs Δχ² ≲ 1. Δχ² = 1 gives KS ≈ 0.04; Δχ² = 4 gives
     KS ≈ 0.2.
   - Proposal: choose σ_neg so that the noise-free, nuisance-profiled Δχ²
     between f_β = 0 and 1 is ≤ 1, and report σ_neg.
2. **The criteria don't say how draws are pooled.**
   - Should "W < 0.05 in ≥ 90 % of draws at a ∈ {3, 3.5, 4}" be pooled over
     all 120 draws (3 radii × 2 f_β × 20) or hold at each radius?
   - The number of control draws isn't set either. Proposal: 20 per f_β per
     condition, the same as the grid.
3. **The preprocessed-condition likelihood has no noise model.**
   - Vector normalisation rescales σ, and the choice sets W in the
     preprocessed condition, which is half of H1.
   - It's also unclear whether normalisation happens before or after the
     1600–1700 cut.
   - Proposal: rubberband over 950–1800, cut to 1600–1700, then
     vector-normalise the window, with σ_pp = σ / ‖window before
     normalisation‖.
4. **Runtime.** The grid is 640 dynesty runs in ≤ 6 h on 16 threads, which
   leaves about 9 CPU-minutes per run. Watford should time a control run and
   project the grid's total before starting it.

The raw condition generates and infers with the same ADA model, so it is a best
case. The exploratory exact-Mie → ADA run is what says how realistic it is.

**Update: clarifications 1–3 are now in the E1 DRAFT,** at Chris's request.
- **Correction to item 1.** Δχ² ≤ 1 is too loose once each draw's noise is
  counted, because the noise tilts every posterior.
  - Simulated per-draw KS when the likelihood is linear in f_β: P(KS < 0.1) is
    0.52 at Δχ² = 1, 0.84 at 0.3, 0.98 at 0.1 and 1.00 at 0.05.
  - So σ_neg is set for Δχ² ≤ 0.1. The pass rule is KS < 0.1 in ≥ 90 % of the
    40 draws, using ≥ 2000 equal-weight samples.
- **Choices the mac made that Chris can still change:**
  - pooled H1 counting (120 draws per condition), with the per-radius table
    always reported;
  - the negative control at a = 0.25 µm;
  - σ_neg chosen to satisfy both conditions.
- Item 4 (runtime) is not in EXPERIMENTS.md. It is an operations note for
  watford.

**Review of watford's first pushes (d45a7b2..c4fed7b).** Its reply note isn't
in yet, and the 240-run controls are still running.

- **E0 is done and checks out.**
  - Noise σ: median 1.10e-3 AU (p10 8.0e-4, p90 1.5e-3).
  - Amide I peak over tissue: median 0.32 AU.
  - The sample is md5-verified, and the GPU check ran under the lock.
  - The PCUK2023 source cubes are already on Isilon, so the 199 GB download
    isn't needed.
- **E1 steps 1–2 pass.**
  - Kramers–Kronig: correlation 1.000, scale 0.9997. The ADA extrema are within
    1 %.
  - The Lesson 1 test is skipped because there is no `rmies_sim.py`. The
    fallback set gives about 70 % of the Lesson 1 shifts and inverts near
    6.5 µm.
- **Mac error, now corrected in EXPERIMENTS.md.** σ × 100 gives Δχ² ≈ 0.016
  under this simulator, not 20–190.
  - My estimate assumed a 0.5 AU Amide I. The simulated Amide I at a = 0.25 µm
    is only about 0.007 AU, roughly 50× below real tissue.
  - The Δχ² ≤ 0.1 rule still stands.
  - watford's `chi2_gap` profiles out only the amplitude and baseline. That
    gives an upper bound on the fully profiled gap, so it is conservative.
- **The φ prior matters more than the wasted volume watford noted.**
  - Rejecting φ·Q_ext ≥ 1 makes the effective prior on a non-uniform. Relative
    to a ≤ 1 µm, a = 3, 4 and 6 µm get 0.42, 0.34 and 0.32 of the prior mass
    (mac numpy check: ADA, n∞ ~ U[1.3, 1.6]).
  - That favours "β + small scatterer" at exactly the H1 radii, which biases W.
  - Narrowing to φ ∈ [0.05, 0.30] makes the prior on a flat. Chris must decide
    before APPROVED, and the controls should then re-run under the final prior.
- **The raw condition is a best case for one more reason.** In the sphere
  model the absorbing path grows with a, so absolute absorbance says something
  about a. In real tissue the section thickness sets it instead. The amplitude
  range [0.2, 3] only partly decouples the two.
- **Paraffin (for chat and Chris; affects E3).** The sample cores were measured
  in paraffin, which has an index close to tissue's (m ≈ 1).
  - Mie scattering should therefore be much weaker than in E1's in-air sphere
    model. E0 fits this: the apparent Amide I p10–p90 is only 1649–1659 cm⁻¹.
  - PCUK2023 may be a low-RMieS dataset. That could make it a source of prior
    training data (§4) but a weak test bed for correction.
  - A forward model for these cores needs a medium index.
- **A possible natural test case (unverified).** The E0 Amide I map shows round
  objects at about 1630 cm⁻¹. In prostate tissue these could be corpora
  amylacea, which can contain amyloid (β-sheet) and are roughly spherical. That
  would be the real-tissue version of E1's confound. Check against the H&E.

**Update: the φ prior is narrowed to [0.05, 0.30] in the E1 DRAFT,** at
Chris's request. The note is at the end of E1.

**For watford:** request 01's controls (task 4) must use φ ∈ [0.05, 0.30]. The
set in flight samples [0.05, 0.9], so re-run it under the new prior once it
finishes. Put the new numbers in the reply, and label the old set as superseded
or drop it. `descatter/infer_e1.py` `PRIOR_BOUNDS["phi"]` needs the change.

**Review of watford's E1 controls (9903848): both fail.** 240 runs in 32 min,
sampled with φ ∈ [0.05, 0.9] (they ran before the φ change).

- **Positive control, raw: PASS.** W = 0 in 40/40 runs, with a recovered at
  0.28–0.46 µm.
- **Positive control, preprocessed: FAIL** (11/40 runs with W > 0.05). The mac
  read differs from watford's "not yet attributed":
  - All 11 have f_β,true = 0 (α).
  - Their posteriors put a at about 5–7.3 µm. That is at or past the
    inversion: the band flattens near 5 µm and is shifted upward again by
    ≈ 6.5 µm, with +25 to +31 cm⁻¹ at 7 µm (watford's corrected table,
    8a1f40a).
  - So "β + large scatterer" explains "α + no scatter" in the preprocessed
    window. This is the H1 ambiguity itself. It shows up even at
    a_true = 0.25 µm because the window can't rule out large a.
  - The control is confounded with the hypothesis, so this is not a sampler
    failure. watford's a-fixed diagnostic should confirm it.
  - It's an observation from a control, not H1 evidence.
- **Negative control, preprocessed: FAIL. This is the mac's design error.**
  σ_pp = σ / ‖y_w‖ is valid only when signal dominates. Under heavy noise
  ‖y_w‖ ∝ σ, so σ_eff saturates (about 0.049) and the likelihood never goes
  flat. watford's diagnosis is right.
- **Negative control, raw: FAIL** (KS < 0.1 in 62 % of draws; 90 % needed).
  - The Δχ² ≤ 0.1 rule is computed at a = 0.25 µm, but the posterior also
    roams to large a, where f_β carries far more information.
  - So the rule is necessary but not sufficient.
  - KS is still falling with noise (median 0.84, 0.24, 0.18, 0.093 at ×1, ×10,
    ×30, ×100).
  - *Settled by the ladder (8a1f40a):* the raw negative control fires at
    σ × 1000, where 10/10 draws have KS < 0.1. That is 25× more noise than the
    Δχ² rule predicts. The preprocessed one never fires, even at σ × 10000
    (KS 0.27–0.29, σ_eff stuck at 0.049), which confirms the mac's error.
- watford's `prior_valid_fraction` check shows the φ rejection doesn't bias
  f_β. The mac's concern was the bias on a, which narrowing φ has already
  fixed.
- **Timing:** about 78 s per run. The grid projects to ≥ 1.2 h on 14 workers.

**Mac proposals for the control redesign.** E1 is DRAFT and the grid hasn't
run. These change the controls only, not the H1 criteria. Log them as
post-hoc, made after seeing control failures.

1. **Preprocessed likelihood.** Fit the rubberband-corrected 1600–1700 window
   as s · (model window), with a free scale s and noise σ, instead of dividing
   by ‖y_w‖. This keeps the same information as vector normalisation and gives
   an exact noise model at any SNR. watford's alternative is a fixed reference
   norm.
2. **Positive control.** Fix a at its true value in both conditions, so the
   control tests only the sampler and likelihood. Keep the free-a runs as a
   labelled observation.
3. **Negative control.** Make f_β inert: identical α and β lineshapes in both
   data and model, at the E0 noise level. The posterior must then equal the
   prior, so any KS ≥ 0.1 is a bug. This replaces the noise-ladder approach.
   (σ × 1000 works for raw, but the rule that predicted 40× missed by 25×.)
4. **The SNR mismatch, a research-design question.** watford's
   `simulator_amplitude_check.json` (8a1f40a) shows the simulated Amide I band
   is far too faint.
   - At φ = 0.2 the band depth is 0.0038 AU at a = 0.25 µm and at most
     0.026 AU near 2–3 µm. Tissue measures 0.324 AU.
   - At σ_E0 that makes E1's SNR 3.5–24, against about 295 in real data. So
     E1 would test identifiability with roughly 12–85× less signal than real
     spectra carry.
   - The cause: in the sphere model all absorbance comes through Q_ext, so a
     small sphere is also a faint absorber.
   - Proposal: set σ for each case so that the Amide I band depth divided by σ
     equals E0's tissue value (≈ 295). This keeps the sphere model and matches
     the information content.
   - The alternative is a slab-plus-scatterers forward model, which is a bigger
     change and better suited to E2.

**Open for Chris:**
1. Accept proposals 1–4, or edit them. Proposal 4 changes E1's noise spec, so
   the chat may want a say. The mac then writes them into the E1 DRAFT and
   sends watford a request to re-run the controls under the φ prior
   [0.05, 0.30].
2. Mark E1 `APPROVED` once the redesigned controls pass. The grid waits for
   this.
3. Add `rmies_sim.py` if you have it somewhere other than this Mac.
4. Pass the paraffin point to the chat when E3 is designed.

## 2026-11-05 (chat): repo scaffolded

**Background,** from the Spectra Research chat:
- The idea is a generative, physics-informed RMieS correction: a diffusion
  prior plus a differentiable Kramers–Kronig + Mie likelihood, sampled with
  DPS.
- Literature check: every learned corrector so far returns a single answer.
  No posterior-sampling version was found.
- Public data: PCUK2023 (raw prostate TMA), BR20832 (breast TMA) and a 4-core
  sample.
- The watford setup was recovered from rat-lung-project `docs/machines.md`.

**Written:**
- CLAUDE.md
- docs/RESEARCH_BRIEF.md, EXPERIMENTS.md, COMMS.md, machines.md and KICKOFF.md
- the first request: `comms/2026-11-05_chat_to_watford_01.md`

**Open for Chris:**
1. Approve or edit the E1 thresholds in docs/EXPERIMENTS.md.
2. If you have it, add Lesson 1's `rmies_sim.py` as `legacy/rmies_sim.py`.
3. Fill in the mac row of docs/machines.md, or let the mac session do it.
