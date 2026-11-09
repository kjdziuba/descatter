# Experiments (pre-registered)

**Status values:** DRAFT → APPROVED (Chris) → RUNNING → DONE or ABANDONED.

Thresholds are fixed once an experiment is APPROVED. Any later change goes
below the experiment as a dated amendment with the reason.

---

## E0: environment and data smoke test (watford)

**Status:** APPROVED (no decision rides on it)

1. **Environment.** Create a venv at `~/Projects/descatter/.venv` (Python 3.12
   from `/opt/anaconda3`).
   - Install the torch CUDA build that matches the driver (rat-lung's venv
     has torch 2.14.1+cu130).
   - Then run `pip install -r requirements.txt`.
   - Record all versions in the watford row of `docs/machines.md`.
2. **GPU check.**
   - Run `nvidia-smi` and check `torch.cuda.is_available()`.
   - Run one small matmul while holding the rat-lung lock and with the 25 GB
     cap (see CLAUDE.md).
   - Record free VRAM. Skip the matmul if the lock is held, and say so.
3. **Download** Zenodo 10.5281/zenodo.17672476 (about 1.7 GB) to
   `~/descatter_data/pcuk2023_sample/` and verify the md5 checksums Zenodo
   lists.
4. **Inspect one raw core** (`*_raw.h5`). Report:
   - HDF5 keys, array shapes and dtypes;
   - wavenumber range and spacing (`wavenumbers_raw.npy`);
   - absorbance range over tissue pixels;
   - a noise estimate per tissue pixel: robust SD of first differences over
     1800–1900 cm⁻¹ divided by √2. Report the median and the 10th and 90th
     percentiles.

   Save a quick-look figure to `results/e0/`: mean ± SD raw spectrum over
   tissue, plus a map of the Amide I peak position.
5. **Define "preprocessed".** Find out what the non-raw files are, using the
   paper (doi:10.1021/acs.analchem.5c04765) or
   github.com/lyyraaa/pcuk2023_dataset_creation, and record it.
6. **Isilon check.** This is read-only and must take at most 2 minutes
   (`timeout 120`).
   - Is PCUK2023 or BR20832 already under `/mnt/isilon-gardner`? For example:
     `find /mnt/isilon-gardner -maxdepth 4 \( -iname '*pcuk*' -o -iname '*BR20832*' \)`.
   - Report the paths and copy nothing.

**Done when:** the venv works with CUDA, the sample is verified, and
`results/e0/summary.json` and the figure are committed.

---

## E1: is RMieS identifiable from one spectrum? (sphere model, simulation only)

**Status:** DRAFT. Chris must approve the thresholds before the grid run in
step 4.

**Question (H1).** Under the sphere model, can one spectrum distinguish
"α-helix + large scatterer" from "β-sheet + small scatterer"? And does
standard preprocessing destroy that ability?

### 1. Forward model

Write it in `descatter/physics.py`: PyTorch, float64, differentiable.

**Chemistry.** A Lorentz-oscillator tissue spectrum whose Amide I mixes two
lineshapes, weighted by f_β ∈ [0, 1]:
- an α-helix lineshape (≈1656 cm⁻¹);
- a β-sheet lineshape (≈1630 cm⁻¹ major and ≈1690 cm⁻¹ minor).

If `legacy/rmies_sim.py` (Lesson 1) is in the repo, port its 14-oscillator set
and use it. Otherwise build an equivalent set over 950–1800 cm⁻¹ and document
it here as an amendment.

**Refractive index.** n(ν) = n∞ + Δn(ν), with Δn obtained from k(ν) by FFT
Hilbert transform (Kramers–Kronig). Pad the spectrum to avoid edge
artefacts.

**Extinction** of a homogeneous sphere of radius a:
- van de Hulst ADA with a complex index (fast path, used for inference);
- exact Mie via miepython (reference, used for validation).

**Apparent absorbance**, counting scattered light as lost:
A_app = −log10(1 − φ·Q_ext), where φ ∈ (0, 1) is a geometric fill factor. Add
a linear baseline and Gaussian noise.

### 2. Unit tests (must pass before step 3)

- **Kramers–Kronig:** the FFT-Hilbert Δn matches the analytic Lorentz Δn over
  950–1800 cm⁻¹, with correlation ≥ 0.99 and scale factor between 0.98 and
  1.02.
- **Mie curve:** non-absorbing ADA has its first maximum Q ≈ 3.17 at ρ ≈ 4.09
  and a minimum Q ≈ 1.54 at ρ ≈ 7.62, each within ±1 %.
- **ADA vs exact Mie:** report the agreement over a ∈ [0.5, 8] µm (not
  pass/fail) and note where ADA deviates.
- **Lesson 1 reproduction** (only if `legacy/rmies_sim.py` is present): the
  apparent Amide I peak maximum shifts by −8, −18, −32 and −50 cm⁻¹ at
  a = 1, 2, 3 and 4 µm, each within ±3 cm⁻¹.

### 3. Inference

Write it in `descatter/infer_e1.py`.

**Parameters:** θ = (f_β, a, φ, amplitude, baseline offset, baseline slope).
n∞ is fixed at 1.40 in inference (amended 2026-11-09; see the n∞ amendment
at the end of E1). The simulated data are unchanged.

**Priors:** all uniform:
- f_β ∈ [0, 1]
- a ∈ [0.1875, 12] µm (was [0.25, 8] with n∞ free; amended 2026-11-09)
- n∞ fixed at 1.40 (was free in [1.30, 1.60]; amended 2026-11-09)
- φ ∈ [0.05, 0.30] (narrowed from [0.05, 0.9] on 2026-11-06; see the φ note
  at the end of E1)
- amplitude ∈ [2/15, 4] (was [0.2, 3] in the code; amended 2026-11-09)
- baseline offset ∈ [−0.5, 0.5], baseline slope ∈ [−1, 1]

**Noise** (redesigned 2026-11-06; see the redesign at the end of E1): σ is set
per radius so that the Amide I signal-to-noise matches tissue:
σ(a) = D(a) / 295.
- **295** is E0's tissue SNR: the median raw Amide I peak (0.324 AU, baseline
  included) over the median noise (1.097e-3 AU), core s10_c048
  (`results/e0/summary.json`).
- **D(a)** is the Amide I *absorption* depth of the same sphere with
  scattering switched off. Evaluate the forward model with n∞ = 1 and Δn = 0,
  keeping κ(ν), φ = 0.2, amplitude 1 and the α composition (f_β = 0). Then
  D = max over 1600–1700 cm⁻¹ of A_abs.
- Why the absorption depth: the *apparent* band flattens away near a = 5 µm,
  so its depth can't set σ.
- Why the α composition: so σ depends on a only, not on the true f_β.
- n∞ = 1 is used only to set σ. It is outside the inference prior.

**Sampler:** dynesty nested sampling (it handles multimodal posteriors). On
3 cases, cross-check it against a dense (f_β, a) grid profiled over the
nuisance parameters.

**Two conditions, same simulated data:**
- (i) **raw:** likelihood on the raw apparent absorbance over 950–1800 cm⁻¹;
- (ii) **preprocessed:** in this order:
  1. a rubberband baseline over 950–1800 cm⁻¹;
  2. a cut to 1600–1700 cm⁻¹;
  3. vector normalisation of that window.

  Apply identical preprocessing to the model output inside the likelihood.

  **Likelihood (redesigned 2026-11-06):** y_w ~ N(s · m_w + c0, σ² I).
  - y_w and m_w are the observed and model windows after steps 1–2.
  - s and c0 are free and profiled out by linear least squares at every
    likelihood call; s is unconstrained.
  - Step 3 is a rescaling, which s absorbs. So the likelihood is computed
    before it, and σ stays exact at any SNR.
  - c0 absorbs the lift that rubberbanding noisy data adds: the hull anchors
    on noise minima, raising the window by +2.1σ (watford, 810bba6).

**Controls (may run before approval; redesigned 2026-11-06):**
- *Likelihood calibration:* χ² of the true model against its own noisy data.
  - Cells: a ∈ {0.25, 3.5} µm × f_β ∈ {0, 1} × both conditions, 200 draws
    each.
  - Expected: N for raw and N − 2 for preprocessed, where N is the number of
    channels in the likelihood.
- *Positive:* a = 0.25 µm, with a fixed at its true value in the inference;
  every other parameter is free. Both conditions should recover f_β.
  - The free-a version runs alongside as a labelled observation and is not
    thresholded.
- *Negative:* a = 0.25 µm with f_β made inert.
  - Replace the β lineshape (bands 13–14) with the α lineshape (band 12), in
    both the simulation and the model. The likelihood then doesn't depend on
    f_β at all.
  - The f_β posterior must equal the prior, so any departure is a sampler or
    KS bug.
- *Noise:* both controls use σ(0.25 µm) from the SNR rule above.
- *Draws:* for each control, f_β,true ∈ {0, 1} with 20 noise draws each, in
  both conditions. That is 40 draws per condition, the same count as the grid.
  In the negative control the two f_β values give identical spectra; they are
  kept for the count.

### 4. Grid run (only after APPROVED)

Run, for both conditions:
- a_true ∈ {0.25, 1, 2, 3, 3.5, 4, 5, 6} µm
- f_β,true ∈ {0, 1}
- 20 noise draws for each combination
- σ(a) from the SNR rule in step 3. Report the σ table.

### 5. Metrics for each case

- Wrong-mode mass W: the posterior mass of f_β on the wrong side of 0.5.
- Posterior SD of f_β.
- Posterior median and 90 % interval of a at n∞ = 1.40, i.e. of
  a(n∞ − 1)/0.4, the combination the data identify (amended 2026-11-09).
  The truth uses n∞ = 1.40, so it compares directly with a_true.
- Log-evidence and wall time.

### Pre-registered criteria (proposed; Chris to confirm)

**The machinery is valid only if all three hold** (redesigned 2026-11-06):
- likelihood calibration: median χ² at the truth within ±10 % of its expected
  value, in every calibration cell;
- positive control (a fixed): W < 0.05 in ≥ 95 % of the 40 draws, in each
  condition;
- negative control (f_β inert): the KS distance between the f_β posterior and
  the prior is < 0.1 in ≥ 90 % of the 40 draws, in each condition. Compute KS
  from ≥ 2000 equal-weight posterior samples.

**How draws are counted for H1.** Pool the 120 draws per condition: a_true ∈
{3, 3.5, 4} µm × f_β,true ∈ {0, 1} × 20 draws. Always report the per-radius
table as well.

**H1 is supported if both hold:**
- raw: W < 0.05 in ≥ 90 % of the pooled draws;
- preprocessed: W > 0.2 in ≥ 50 % of the pooled draws.

**Single-spectrum correction is not viable under the sphere model if:**
- raw W > 0.2 in ≥ 50 % of the pooled draws.

In that case a corrector needs extra evidence (spatial context, H&E
morphology, or a second measurement geometry), and E2 is redesigned before
it runs.

**Anything else** is reported as mixed, with the per-radius table.

**Exploratory (not pre-registered):** generate data with exact Mie and run
inference with ADA. This shows how much the approximation alone costs.

**Budget:** CPU only (16 threads), ≤ 6 h wall time, ≤ 2 GB disk.

**Clarified 2026-11-06** (mac, at Chris's request, while still DRAFT):
- the step order and noise model of the preprocessed condition;
- the negative control's noise rule (Δχ² ≤ 0.1; σ × 100 turns out to meet
  it) — superseded by the redesign below;
- draw counts for the controls, and pooling of draws for H1;
- the φ prior, narrowed to [0.05, 0.30] (see the φ note below);
- **redesigned:** the controls, the preprocessed likelihood and the noise
  level (see the redesign at the end of E1).

The reasoning is in the 2026-11-06 (mac) WORKLOG entry. E1 still needs
Chris's APPROVED before the grid runs.

### Amendment 2026-11-06 (watford): the fallback oscillator set

`legacy/rmies_sim.py` was not in the repo, so step 1's fallback applies and the
Lesson 1 reproduction test in step 2 is **skipped**, not failed. The set below
is what `descatter/physics.py` uses. Each band is an absorptive Lorentzian
`k = P G² / ((ν₀ − ν)² + G²)` with `G = FWHM/2`.

| # | ν₀ / cm⁻¹ | FWHM / cm⁻¹ | peak k | assignment |
|---|---|---|---|---|
| 1 | 1030 | 40 | 0.012 | glycogen / C-O stretch |
| 2 | 1080 | 35 | 0.022 | symmetric PO2- stretch (nucleic acid) |
| 3 | 1170 | 30 | 0.010 | C-O stretch / ester |
| 4 | 1240 | 55 | 0.026 | asymmetric PO2- stretch / Amide III |
| 5 | 1310 | 30 | 0.009 | Amide III |
| 6 | 1340 | 30 | 0.010 | CH deformation / collagen |
| 7 | 1398 | 35 | 0.016 | symmetric COO- stretch / CH3 bend |
| 8 | 1450 | 35 | 0.018 | CH2 bend |
| 9 | 1468 | 20 | 0.008 | CH2 scissoring (lipid) |
| 10 | 1545 | 50 | 0.045 | Amide II |
| 11 | 1740 | 25 | 0.010 | ester C=O (lipid) |
| 12 | 1656 | 45 | (1 − f_β)·0.080 | Amide I α-helix |
| 13 | 1630 | 25 | f_β·0.080·1.573 | Amide I β-sheet major |
| 14 | 1690 | 20 | f_β·0.080·1.573·0.18 | Amide I β-sheet minor |

The β weights make the β lineshape equal in *area* to the α lineshape, so f_β
changes the Amide I shape and not the protein content. Amide I / Amide II is
1.78 in k, which is 1.91 in thin-film absorbance (A ∝ ν·k) — the Lesson 1
number in RESEARCH_BRIEF §1.

**How it compares with Lesson 1** (`results/e1/amide_i_shifts.json`):

| a / µm | fallback peak-max shift | fallback 2nd-derivative shift | Lesson 1 target |
|---|---|---|---|
| 1 | −6.0 cm⁻¹ | −4.3 cm⁻¹ | −8 cm⁻¹ |
| 2 | −13.1 cm⁻¹ | −9.2 cm⁻¹ | −18 cm⁻¹ |
| 3 | −22.4 cm⁻¹ | −15.3 cm⁻¹ | −32 cm⁻¹ |
| 4 | −35.8 cm⁻¹ | −23.3 cm⁻¹ | −50 cm⁻¹ |
| 5 | *no apparent band* | −34.8 cm⁻¹ | direction inverts |
| 6 | *no apparent band* | +31.0 cm⁻¹ | +62 cm⁻¹ |
| 7 | +31.5 cm⁻¹ | +25.0 cm⁻¹ | — |

The shape is right — the shift grows with a, the band then flattens away near
a = 5 µm and re-emerges on the positive side by a ≈ 6.5 µm, which is where
Lesson 1 puts the inversion. The magnitude is about 70 % of Lesson 1's.
**So E1 under this set is a slightly easier problem than Lesson 1.** If Chris
adds `legacy/rmies_sim.py`, port its set and re-run; the pre-registered test
will then be active.

*Corrected 2026-11-06 (watford).* The first version of this table reported
−55.9 cm⁻¹ at a = 5 and 6 µm. That was an artefact: at those radii the
resonant distortion flattens the apparent Amide I band completely, and a bare
argmax rails against the 1600 cm⁻¹ window edge (1656 − 55.9 = 1600.1).
`descatter.physics.amide_i_position` now returns `nan` on a window edge, and
the earlier claim that the inversion sits "near 6.5 µm rather than 5 µm" was
wrong — it rests on the artefact. The second-derivative picker still works
there, which is why it is tabulated alongside.

### Note 2026-11-06 (watford): the φ prior is partly unreachable

Q_ext peaks near 3.2, so `A_app = −log10(1 − φ·Q_ext)` needs `φ < 1/max Q_ext ≈
0.31`. The pre-registered prior φ ∈ [0.05, 0.9] therefore contains a large
region where the model is undefined. `descatter/physics.py` flags it and the
likelihood rejects it, so the runs are correct, but roughly two thirds of the
φ prior volume is wasted. Worth narrowing before the step-4 grid.

**Resolved 2026-11-06** (mac, Chris agreed; E1 still DRAFT): the φ prior is
now **[0.05, 0.30]**.
- **The bigger reason was bias, not wasted volume.** Rejecting φ·Q_ext ≥ 1
  made the effective prior on a non-uniform. Relative to a ≤ 1 µm, a = 3, 4
  and 6 µm got only 0.42, 0.34 and 0.32 of the prior mass (mac numpy check:
  ADA, n∞ ~ U[1.3, 1.6]). That favoured "β + small scatterer" at exactly the
  H1 radii.
- **The new range removes the bias.** ADA's Q_ext peaks at about 3.17, so
  φ ≤ 0.30 keeps φ·Q_ext < 1 everywhere, and the prior on a is flat. The
  simulation truth φ = 0.2 stays inside.
- **The controls must run under this prior.** Any control set sampled with
  [0.05, 0.9] is superseded; report it, if at all, only as a labelled
  comparison.

### Redesign 2026-11-06 (mac; Chris approved the redesign; E1 still DRAFT)

**This is post-hoc.** It was made after the first control runs failed. It
changes the controls, the preprocessed likelihood and the noise level. It does
not change:
- the H1 thresholds or the "not viable" rule;
- the grid, priors or metrics;
- the forward model.

**Why.** Under φ ∈ [0.05, 0.30] (watford, b0fd271; reply
`comms/2026-11-06_watford_to_mac_01.md`):

| Control | Raw | Preprocessed |
|---|---|---|
| Positive (W < 0.05) | 40/40, PASS | 0.70, FAIL |
| Negative (KS < 0.1) | 0.75, FAIL | 0.00, FAIL |

The causes:
1. **The preprocessed likelihood was misspecified.**
   - Rubberbanding noisy data lifts the window by +2.1σ, which is 58 % of the
     Amide I depth at a = 0.25 µm.
   - χ² of the truth against its own data was 99.7 on 52 points (810bba6). In
     the profile grid the best fit beat the truth by 39.7 log-likelihood
     (diagnostics.json).
   - Separately, σ_pp = σ / ‖y_w‖ saturates at about 0.049 once noise
     dominates, so the preprocessed negative control could never fire. That
     was the mac's design error.
2. **The positive control was confounded.**
   - With a free, the preprocessed failures put the posterior at a ≈ 5–8 µm.
   - With a fixed at its truth, both conditions pass in 40/40 draws
     (diagnostics.json). So the sampler is sound.
3. **The negative control's noise rule was too weak.** Δχ² ≤ 0.1 at
   a = 0.25 µm predicted that σ × 40 would suffice. Raw needed σ × 300,
   because the posterior roams to large a, where f_β carries more information.
4. **E1's SNR was far below tissue.**
   - In the sphere model all absorbance comes through Q_ext, so the simulated
     Amide I depth is 0.0038–0.026 AU against 0.324 AU in tissue.
   - At the E0 noise that is SNR 3.5–24, against about 295 in tissue
     (`results/e1/simulator_amplitude_check.json`).

**What changed.** Each fix is written into step 3 and the criteria above:
1. **Preprocessed likelihood:** s · m_w + c0 with σ exact, replacing
   σ / ‖y_w‖. watford's check (810bba6) gives χ² 49.2 against 50 expected.
   A slope term bought only 1.5 χ², so it's left out of E1. Revisit it for
   real data in E3.
2. **Positive control:** a fixed at its truth. The free-a run is a labelled
   observation.
3. **Negative control:** f_β inert, replacing the noise ladder.
4. **Noise:** σ(a) = D(a)/295, from the index-matched absorption depth.
5. **New gate:** the likelihood-calibration check.

**Status of earlier results.** The control runs in `results/e1/` from b0fd271
and earlier are superseded. They stay in git as labelled history (the φ ≤ 0.9
set in `results/e1/superseded_phi_0.05_0.90/`), not as evidence for or against
H1.

**Heads-up, not a result.** In three profile-grid cases at a = 3.5 µm, the
preprocessed condition separated f_β decisively, at low SNR and under the old
likelihood (watford's surprise 8). If that holds on the grid, the
preprocessed half of H1 fails. That is a legitimate outcome, and the
thresholds stay as written.

### Note 2026-11-06 (watford, mac): the grid's outcome is predictable under σ(a)

**Decided 2026-11-06 (Chris, relayed by mac): run the grid as written, then
E1b.**
- E1 keeps σ(a) and the redesigned controls. The grid runs once the
  calibration gate and both controls pass and Chris marks E1 `APPROVED`.
- The prediction below stands as written. The grid result is reported against
  the H1 thresholds whichever way it falls.
- The harder-model question moves to E1b (below), pre-registered separately.

**The calculation** (`results/e1/degeneracy_review.json`, 138265b):
- the min χ² between the α truth and the whole β family, profiling a′, n∞′,
  φ′, amplitude and the linear terms;
- under σ(a) it is 4×10⁴ to 7×10⁵ at every grid radius, in both conditions.

**What follows:**
- W ≈ 0 everywhere. Raw H1 passes and preprocessed H1 fails.
- **This prediction is recorded here before any grid run.**
- In this model the α/β-versus-size confusion appears only at Amide I
  SNR ≈ 1–4, where tissue is about 295.

**Scope.** This is about this forward model, with the fallback oscillators and
a one-parameter chemistry (f_β), not about H1 in general. A freer chemistry or
a harder scatter model may close the gap. Options and the mac's
recommendation are in the WORKLOG (2026-11-06, mac).

### Amendment 2026-11-09 (mac; Chris approved; E1 still DRAFT): n∞ fixed in inference

**This is post-hoc.** It was made after the redesigned negative control failed
in raw (0e209c7, reply `comms/2026-11-09_watford_to_mac_03.md`).
- It changes: the inference parameters, the a and amplitude priors, and the
  radius metric (step 3 and step 5 above).
- It does not change: the forward model, the simulated data, σ(a), the control
  designs, the criteria, the H1 thresholds or the grid.

**Why: a, n∞ and amplitude are exactly degenerate in the ADA model.**
- The phase shift is z = 2xk + 2ix(n − 1), with:
  - x = 2πaν;
  - k = amplitude · k_unit;
  - n − 1 = (n∞ − 1) + amplitude · Δn_unit (KK is linear).
- So the spectrum depends on a only through a(n∞ − 1) and a·amplitude. It is
  unchanged under (a, n∞, amplitude) → (λa, 1 + (n∞ − 1)/λ, amplitude/λ).
- The evidence (WORKLOG 2026-11-09, mac):
  - At a = 0.25 µm, the free-a posterior matches the predicted ridge marginal
    (∝ 1/a² on [0.25, 0.333] µm) to three decimals: q05, median and q95 of
    0.253, 0.286 and 0.328.
  - Raw `rwalk` under-covers the ridge.
  - At a = 3.5 and 5 µm, three of four raw timing runs give tight radius
    intervals that exclude the truth.
- The consequences:
  - With n∞ free, the radius is not identifiable at any SNR.
  - The pre-registered radius metric would report the n∞ and amplitude
    priors, not the data.
  - The curved flat direction is the likely cause of the raw sampler failure.
    That is a hypothesis; request `comms/2026-11-09_mac_to_watford_02.md`
    tests it.

**What changed** (written into steps 3 and 5 above):
1. **n∞ is fixed at 1.40 in inference.**
   - Along an exact ridge this is a choice of coordinates. It removes no
     fitting freedom.
   - A unit test that the forward model is invariant along the ridge is what
     licenses it.
2. **Priors widened:** a ∈ [0.1875, 12] µm and amplitude ∈ [2/15, 4].
   - These cover every spectrum the old prior reached: a(n∞ − 1) still spans
     [0.075, 4.8] µm, and the ridge maps the old amplitudes into [2/15, 4].
   - The covered set is slightly larger than before, and the prior over the
     identified combinations changes. Neither should matter at SNR 295. The
     degeneracy screen is re-run under the new bounds to check.
3. **Radius metric:** a at n∞ = 1.40, i.e. a(n∞ − 1)/0.4.
4. **The sampler cross-check** (step 3) uses this a.

**Status of earlier results.**
- The 0e209c7 controls stay as run in `results/e1/controls.json`. They are the
  record of the failure, not evidence about the amended model.
- The controls under the amended model are a new labelled analysis, in
  `results/e1/controls_gauge/`.
- The calibration gate (8f07934) stands: the true spectrum and the likelihood
  at the truth are unchanged.

**Effect on H1 and the recorded prediction: none expected.**
- W depends only on f_β, and the likelihood is identical at every point on the
  ridge, for any f_β.
- In the H1 question, "large" and "small scatterer" now mean large and small
  a(n∞ − 1).

**Not covered.**
- Exact Mie breaks the ridge only weakly, which leaves a near-degeneracy. That
  matters for the exploratory Mie run and for E1b.
- E2 uses the same ADA model, so it has the same ridge.

---

## E1b: does the confusion survive a harder model? (simulation only)

**Status:** OUTLINE. Design requested from chat in
`comms/2026-11-06_mac_to_chat_01.md`.

**Question.** At tissue SNR (~295), can "α-helix + one scatterer size" be
confused with "β-sheet + another size"? This is asked once the model is
harder than E1's, in two ways:
- the chemistry is no longer fixed except for f_β;
- the scatter model is richer: a size distribution, Lesson 1's oscillators,
  exact Mie, or layered spheres.

**Why.** E1's one-parameter chemistry and single homogeneous sphere put the
α and β families 4×10⁴–7×10⁵ χ² apart at tissue SNR (see the E1 note above).
So E1 can't show the confusion H1 and E2 are built on.

**Shape.**
1. Screen each candidate model cheaply, using watford's degeneracy check
   (`scripts/e1_degeneracy_review.py`): the min χ² between the α truth and
   the whole β family, and the critical SNR it implies.
2. Run a posterior grid only on models whose critical SNR comes near tissue
   level.

**The crux is the chemistry prior.** Unconstrained chemistry makes anything
non-identifiable trivially. The prior has to be realistic, and that is the
same problem E2's learned prior faces.

**Budget:** CPU only. Design first; no compute until a DRAFT exists.

## E2: regression vs posterior sampling on simulations (H2)

**Status:** OUTLINE. To be designed after E1. Its "ambiguous regime" may not
exist at tissue SNR under E1's model, so E1b decides what E2 oversamples.
Under ADA, a, n∞ and amplitude form an exact ridge (E1 amendment
2026-11-09). E2's parameterisation and metrics must account for it.

- Use the same simulator as E1, with broader chemistry (mixtures of component
  spectra) and size distributions.
- Compare two models trained on identical simulated pairs:
  - (a) a 1D-CNN regressor with MSE loss, raw → clean k;
  - (b) a conditional diffusion or flow posterior.
- Test on held-out simulations, oversampling E1's ambiguous regime.
- Metrics:
  - Amide I position error;
  - RMSE of k;
  - coverage of 90 % intervals (target 0.85–0.95);
  - CRPS;
  - how often the regressor's Amide I falls between the two posterior modes.
- Budget: ≤ 25 GB VRAM, ≤ 8 h.

## E3: DPS on real tissue (the 4 sample cores)

**Status:** PLACEHOLDER. Needs a decision on the prior's training data
(RESEARCH_BRIEF §4).
