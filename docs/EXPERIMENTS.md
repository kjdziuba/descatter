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

**Parameters:** θ = (f_β, a, n∞, φ, amplitude, baseline offset, baseline
slope).

**Priors:** all uniform:
- f_β ∈ [0, 1]
- a ∈ [0.25, 8] µm
- n∞ ∈ [1.30, 1.60]
- φ ∈ [0.05, 0.9]
- amplitude and baseline over wide ranges

**Noise:** σ is the median noise estimate from E0. Fall back to 1e-3 AU if E0
is not done, and say so.

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
  The Gaussian likelihood on the window uses σ_pp = σ / ‖y_w‖, where y_w is
  the observed window after the rubberband and before normalisation. This is
  first-order propagation and ignores the rubberband's effect on the noise.

**Controls (may run before approval):**
- *Positive:* a = 0.25 µm, where scattering is negligible. Both conditions
  should recover f_β.
- *Negative:* a = 0.25 µm, with the noise raised to σ_neg.
  - Choose σ_neg so that, in each condition, the noise-free Δχ² between
    f_β = 0 and f_β = 1 (minimised over the other parameters) is ≤ 0.1. Take
    the larger of the two σ values and report it.
  - The data then carry almost no information about f_β, so its posterior
    should match the prior.
  - σ × 100 is not enough: a rough estimate leaves Δχ² ≈ 20–190.
- *Draws:* for each control, f_β,true ∈ {0, 1} with 20 noise draws each, in
  both conditions. That is 40 draws per condition, the same count as the grid.

### 4. Grid run (only after APPROVED)

Run, for both conditions:
- a_true ∈ {0.25, 1, 2, 3, 3.5, 4, 5, 6} µm
- f_β,true ∈ {0, 1}
- 20 noise draws for each combination

### 5. Metrics for each case

- Wrong-mode mass W: the posterior mass of f_β on the wrong side of 0.5.
- Posterior SD of f_β.
- Posterior median and 90 % interval of a.
- Log-evidence and wall time.

### Pre-registered criteria (proposed; Chris to confirm)

**The machinery is valid only if both hold:**
- positive control: W < 0.05 in ≥ 95 % of the 40 draws, in each condition;
- negative control: the KS distance between the f_β posterior and the prior
  is < 0.1 in ≥ 90 % of the 40 draws, in each condition. Compute KS from
  ≥ 2000 equal-weight posterior samples.

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
- the negative control's noise level (σ × 100 left f_β identifiable);
- draw counts for the controls, and pooling of draws for H1.

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

| a / µm | fallback peak-max shift | Lesson 1 target |
|---|---|---|
| 1 | −6.0 cm⁻¹ | −8 cm⁻¹ |
| 2 | −13.1 cm⁻¹ | −18 cm⁻¹ |
| 3 | −22.4 cm⁻¹ | −32 cm⁻¹ |
| 4 | −35.8 cm⁻¹ | −50 cm⁻¹ |
| 6 | −55.9 cm⁻¹ | +62 cm⁻¹ |

The shape is right — shift grows with a, then inverts — but the magnitude is
about 70 % of Lesson 1's and the inversion is near 6.5 µm rather than 5 µm.
**So E1 under this set is a slightly easier problem than Lesson 1.** If Chris
adds `legacy/rmies_sim.py`, port its set and re-run; the pre-registered test
will then be active.

### Note 2026-11-06 (watford): the φ prior is partly unreachable

Q_ext peaks near 3.2, so `A_app = −log10(1 − φ·Q_ext)` needs `φ < 1/max Q_ext ≈
0.31`. The pre-registered prior φ ∈ [0.05, 0.9] therefore contains a large
region where the model is undefined. `descatter/physics.py` flags it and the
likelihood rejects it, so the runs are correct, but roughly two thirds of the
φ prior volume is wasted. Worth narrowing before the step-4 grid.

---

## E2: regression vs posterior sampling on simulations (H2)

**Status:** OUTLINE. To be designed after E1.

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
