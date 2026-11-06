# Research brief: resonant Mie scattering and generative correction

Last updated 2026-11-05 (chat). This is the shared scientific context, so keep
it current. Numbers marked "Lesson 1" come from the Spectra Research course's
simulator (`rmies_sim.py`).

## 1. The problem

Cells and nuclei (about 1–10 µm) are comparable in size to mid-IR wavelengths
(about 5.5–10 µm in the fingerprint region), so they scatter strongly.

By Kramers–Kronig, the refractive index has a dispersive, derivative-shaped
feature at every absorption band. The scattering is therefore *resonant*:
- it puts band-shaped distortions on top of the broad Mie baseline;
- the distortion is known as the "dispersion artefact", or RMieS.

### Lesson 1 model

The model has:
- 14 Lorentz oscillators;
- the van de Hulst anomalous-diffraction approximation (ADA) for a sphere;
- n∞ = 1.40;
- all scattered light counted as lost.

**Mie curve.** Q_ext(ρ) with ρ = 4πa(n − 1)ν:
- first maximum 3.17 at ρ = 4.09;
- minimum 1.54 at ρ = 7.62.

The resonant term is proportional to slope × Δn. So Amide I shifts down on
rising slopes of the curve and up on falling ones.

**Apparent Amide I.** True position 1656 cm⁻¹; shifts measured after perfect
baseline removal.

| Radius a | Peak maximum shift | Second-derivative minimum shift |
|---|---|---|
| 1 µm | −8 cm⁻¹ | −4 cm⁻¹ |
| 2 µm | −18 cm⁻¹ | −9 cm⁻¹ |
| 3 µm | −32 cm⁻¹ | −16 cm⁻¹ |
| 4 µm | −50 cm⁻¹ | −25 cm⁻¹ |
| ≈ 5 µm | direction inverts | — |
| 6 µm | +62 cm⁻¹ | +34 cm⁻¹ |

Past the first maximum, the two peak-pickers can disagree in sign.

**Why this matters.**
- The α-helix → β-sheet Amide I gap is about 25 cm⁻¹, so a 3–4 µm scatterer
  (nucleus-sized) can mimic β-sheet.
- Absorption flattening: the Amide I/II ratio falls from 1.91 (thin) to 1.62
  (a = 2 µm) to 1.31 (a = 6 µm).
- Rubberband baselines, normalisation, Savitzky–Golay derivatives and
  polynomial EMSC all leave the resonant term in place.

### Existing model-based corrections

These are RMieS-EMSC (Bassan 2010, this group) and ME-EMSC (Konevskikh 2016;
open-source code in Solheim 2019).

Both start from a reference spectrum and pull their output towards it. Both
are slow on imaging data.

## 2. Learned correctors so far (every one returns a single answer)

| Work | Trained on | Scope | Note |
|---|---|---|---|
| Raulf et al. 2021 | RMieS-EMSC outputs | FFPE tissue | Orders of magnitude faster. Bayesian (MC-dropout) uncertainty coincides with the Amide I band shift |
| Magnussen et al. 2020 (DSAE) | ME-EMSC outputs | cells | Faster and less noisy than ME-EMSC, but inherits it as "truth" |
| Magnussen et al. 2022 | analytic Maxwell simulations of concentric spheres | cells | Infers absorption, morphology and effective refractive index from one spectrum |
| ACS Omega 2025 "universal" network | simulations with many reference spectra | microparticles, cells, fungi | Reference-free. Notes that the inverse Mie problem is ill-posed |
| Rodrigo et al. 2026 (preprint) | FDTD simulations of ellipsoid cell phantoms | cells | Simulation only. Also recovers cell dimensions |

As of 2026-11-05 we found no posterior-sampling (diffusion or normalising-flow)
RMieS corrector.

**Why a single answer is a problem.** An MSE-trained network returns the
posterior mean. Sometimes two explanations fit, for example "α-helix + large
scatterer" and "β-sheet + small scatterer". The mean is then a blend that is
neither. Raulf's uncertainty map points at exactly this region.

## 3. Hypotheses

- **H1, identifiability (tested by E1).** Under the sphere model, the full raw
  spectrum pins down scatter and chemistry. It carries the broad Mie baseline
  plus coherent dispersive features at every band. After rubberband,
  normalisation and an Amide I window, the inverse becomes ambiguous
  (α + large a vs β + small a).
- **H2, generative beats regression where it matters (E2).** Train both on the
  same simulator. A posterior sampler (conditional diffusion or flow, or a
  diffusion prior with DPS) gives calibrated intervals. An MSE regressor gives
  blends exactly where the posterior is bimodal.
- **H3, cross-sensor (later).** Map FTIR (full grid) and QCL (discrete bands)
  into one clean-absorbance space, using sensor-specific measurement operators
  and a shared prior. This should shrink the optics part of the cross-sensor
  gap. It cannot fix differences between the sample sets themselves.
- **H4, scatter is also signal (later).** Scatter parameters (a, n∞) encode
  morphology such as nuclear size, so keep them as an explicit channel rather
  than deleting them. In pollen, classification was best when scatter was
  kept or parameterised (Muthreich 2025).

## 4. Method sketch (for E2 and E3)

### Simulator

1. Start from a clean k(ν), built from mixtures of component spectra or
   oscillators.
2. Get n(ν) = n∞ + the Hilbert transform of k (via FFT).
3. Compute sphere extinction: ADA for speed, exact Mie (miepython) as the
   reference.
4. Convert to apparent absorbance, then add a baseline and noise matched to
   measured SNR.

### Posterior, two options

**(a) Amortised.** Train a conditional diffusion model or flow q(k, a, n∞ | y)
on simulator pairs.

**(b) Diffusion posterior sampling (DPS; Chung et al., ICLR 2023).**
- An unconditional diffusion prior over clean spectra, guided by the gradient
  of the physics likelihood through a differentiable forward model.
- PyMieDiff provides Mie scattering with autograd in PyTorch.
- Advantages: prior and physics stay separate, so the forward model can be
  swapped without retraining. QCL band subsets are just another measurement
  operator.
- Cost: hundreds of network calls per spectrum. For whole slides, distil it
  into (a).

### The prior's training data is the crux

Not ME-EMSC outputs (circular), and not class-conditional (label leakage).

| Candidate source | Caveat |
|---|---|
| simulated mixtures of pure-component references | limited realism |
| spectra from low-scatter regions | selection bias |
| O-PTIR (photothermal detection, insensitive to size/shape scattering) | about 10× finer resolution, so blur to match. Band ratios may differ from absorbance; check before use. The Gardner group has O-PTIR experience (Spadea 2021) |
| the same section measured in paraffin (index-matched) and after dewaxing | untested idea; paraffin bands must be modelled out |

## 5. Data

| Dataset | What | Size | Notes |
|---|---|---|---|
| PCUK2023 FTIR prostate TMA | 1,045 cores from 181 patients. Spectra unprocessed. Agilent Cary 620, 949–3800 cm⁻¹ (1,479 channels). Aligned H&E. Sparse 9-class pixel annotations on 227 cores | 199 GB | Zenodo [10.5281/zenodo.18671069](https://doi.org/10.5281/zenodo.18671069), CC BY 4.0. Gardner group (O'Leary, Ferguson et al.), so it may already be on Isilon: check before downloading. Stored with maximum gzip compression; re-save locally for training |
| PCUK2023 sample | 4 cores (s10_c048, s17_c015, s33_c059, s33_c070), raw and "preprocessed" (undefined on the page), H&E, masks, weights for 10 classifiers | 1.7 GB | Zenodo [10.5281/zenodo.17672476](https://doi.org/10.5281/zenodo.17672476) |
| BR20832 breast TMA | FTIR raw data, H&E image | 181 GB | Zenodo record 4986399 (Tang, Henderson, Gardner 2021), CC BY 4.0. Processed MATLAB version: 10.5281/zenodo.4730312 |
| Ovarian TMA, O-PTIR + FTIR | same tissue measured both ways | — | Gajjela et al. (Reddy and Mayerich, Houston). No public release found; ask the authors |

### Tools

- **miepython:** exact Mie, numpy.
- **PyMieDiff:** PyTorch, differentiable.
- **biospectools** (BioSpecNorway): includes ME-EMSC.
- **RMieS-EMSC:** Gardner group.
- **DPS reference code:** github.com/DPS2022/diffusion-posterior-sampling.

## 6. References

✓ marks a DOI checked on PubMed on 2026-11-05. The others are taken from
publisher or preprint pages.

- ✓ Bassan P, Kohler A, Martens H, …, Gardner P. Resonant Mie scattering (RMieS) correction of infrared spectra from highly scattering biological samples. *Analyst* 2010;135:268–277. doi:10.1039/b921056c
- Konevskikh T, et al. Mie scatter corrections in single cell infrared microspectroscopy. *Faraday Discuss* 2016;187:235–257. doi:10.1039/c5fd00171d
- Solheim JH, Gunko E, Petersen D, Großerüschkamp F, Gerwert K, Kohler A. An open-source code for Mie extinction extended multiplicative signal correction for infrared microscopy spectra of cells and tissues. *J Biophotonics* 2019;12:e201800415. doi:10.1002/jbio.201800415
- ✓ Raulf AP, Butke J, Menzen L, Küpper C, Großerueschkamp F, Gerwert K, Mosig A. A representation learning approach for recovering scatter-corrected spectra from Fourier-transform infrared spectra of tissue samples. *J Biophotonics* 2021;14:e202000385. doi:10.1002/jbio.202000385
- ✓ Magnussen EA, et al. Deep convolutional neural network recovers pure absorbance spectra from highly scatter-distorted spectra of cells. *J Biophotonics* 2020;13:e202000204. doi:10.1002/jbio.202000204
- ✓ Magnussen EA, et al. Deep learning-enabled inference of 3D molecular absorption distribution of biological cells from IR spectra. *Commun Chem* 2022;5:175. doi:10.1038/s42004-022-00792-3
- A universal approach to Mie scatter correction in FTIR analysis of microsized samples. *ACS Omega* 2025;10:61710–61721. doi:10.1021/acsomega.5c07884
- Rodrigo SG, Rasskazov IL, Martin-Moreno L, Schnell M. Scattering correction for infrared spectra of biological cells using computational infrared microspectroscopy and deep learning. arXiv:2605.22503 (preprint, 2026)
- ✓ Muthreich F, et al. Analytical and experimental solutions for Fourier transform infrared microspectroscopy measurements of microparticles: a case study on Quercus pollen. *Anal Chim Acta* 2025;1351:343879. doi:10.1016/j.aca.2025.343879
- Chung H, Kim J, McCann MT, Klasky ML, Ye JC. Diffusion posterior sampling for general noisy inverse problems. ICLR 2023. arXiv:2209.14687
- PyMieDiff: a differentiable Mie scattering library. arXiv:2512.08614 (preprint)
- ✓ Spadea A, Denbigh J, Lawrence MJ, Kansiz M, Gardner P. Analysis of fixed and live single cells using optical photothermal infrared with concomitant Raman spectroscopy. *Anal Chem* 2021;93:3938–3950. doi:10.1021/acs.analchem.0c04846
- Gajjela CC, et al. Leveraging mid-infrared spectroscopic imaging and deep learning for tissue subtype classification in ovarian cancer. *Analyst*. doi:10.1039/D2AN01035F
- O'Leary L, Ferguson D, …, Gardner P, Yin H, Oliveira P. Spatial-spectral deep learning for prostate cancer tissue classification in infrared spectroscopy. *Anal Chem*. doi:10.1021/acs.analchem.5c04765
