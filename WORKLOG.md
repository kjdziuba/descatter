# WORKLOG: descatter

Newest entry on top. Label each entry by machine: (mac), (watford) or (chat).

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
  - Their posteriors put a at about 5–7.3 µm, near or past the fallback set's
    inversion (≈ 6.5 µm), where the apparent shift turns upward.
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
    ×30, ×100). watford's ladder to ×10000 is running.
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

**Open for Chris:**
1. Accept proposals 1–3, or edit them. The mac then writes them into the E1
   DRAFT and sends watford a request to re-run the controls under the φ prior
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
