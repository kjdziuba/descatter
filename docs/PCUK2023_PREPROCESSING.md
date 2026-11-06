# What "preprocessed" means in the PCUK2023 sample (E0 step 5)

Recorded by the watford session, 2026-11-06. Zenodo record
[10.5281/zenodo.17672476](https://doi.org/10.5281/zenodo.17672476) gives each
of the four cores twice: `<core>_raw.h5` and `<core>.h5`. The Zenodo page calls
the second "preprocessed" and never says what that means.

Paper: O'Leary L, Ferguson D, Hart C, Brown M, Oliveira P, Clarke N, Sachdeva A,
Gardner P, Yin H. *Spatial-Spectral Deep Learning for Prostate Cancer Tissue
Classification in Infrared Spectroscopy.* **Anal. Chem.** 2026, 98(4),
2743–2755. [doi:10.1021/acs.analchem.5c04765](https://doi.org/10.1021/acs.analchem.5c04765),
PMID 41566143. Verified against Crossref and PubMed. **The full text is
paywalled from watford**, so the Methods section was not read; what follows is
reconstructed from the files plus the authors' own code.

## The two arrays

| | `<core>_raw.h5` | `<core>.h5` |
|---|---|---|
| `/spectra` | (256, 256, **1505**) float32 | (256, 256, **965**) float32 |
| `/mask` | (235, 277) — **does not match `/spectra`** | (256, 256) — matches |
| wavenumbers | `wavenumbers_raw.npy`, 949.05–3850.23 cm⁻¹, uniform 1.92897 cm⁻¹ | `wavenumbers.npy`, 972.20–3483.73 cm⁻¹, **not uniform** |
| values | absorbance, median 0.058 over tissue | signed, ~1e-4, near zero mean |

Both are chunked (13, 13, 193). The Zenodo copies are lzf-compressed.

## What is certain

1. **The preprocessed grid is an exact subset of the raw grid** — every one of
   the 965 values matches a raw channel to the bit. No interpolation or
   rebinning happened.
2. **It is raw channels 12–1314 with three bands cut out.** The three gaps are

   | cut | last kept | first kept again |
   |---|---|---|
   | paraffin CH₃ 1377 / CH₂ 1462 | 1338.71 | 1491.10 |
   | atmospheric CO₂ 2349 | 2249.18 | 2451.72 |
   | paraffin CH₂/CH₃ stretch 2850/2920/2956 | 2698.63 | 3001.48 |

   These are exactly the limits of two functions in the group's own toolbox,
   [PyIR](https://github.com/lyyraaa/PyIR) `src/pyir_spectralcollection.py`:
   `remove_wax()` cuts 1340–1490 and 2700–3000, and `remove_co2()` cuts
   2250–2450. The arithmetic matches channel for channel:
   78 + 104 + 156 = 338 channels removed, 1303 − 338 = **965**.
3. **The tissue is still in paraffin.** The raw mean spectrum has sharp wax
   bands reaching 4.8 AU at 2920 and 2850 cm⁻¹ — see
   `results/e0/quicklook_s10_c048.png`. That is why the wax cut exists, and it
   matters for this project: any prior trained on PCUK2023 must model or
   exclude the paraffin bands.
4. **The tissue mask rule is published.** `pcuk2023_dataset_creation`
   `core_creation.ipynb` builds it as *area under 1600–1700 cm⁻¹ after
   min-to-zero, thresholded at 2* ("determined empirically"), integrating over
   channel index. Reproducing that rule on `s10_c048_raw.h5` gives IoU 0.984
   against the mask shipped in `s10_c048.h5`.

## What is inferred, not confirmed

The values themselves are a **Savitzky–Golay second derivative of a
min-to-zero, vector-normalised spectrum**, computed across the cut grid:

- The sign pattern, the ~1e-4 scale and the near-zero mean rule out plain
  absorbance.
- Sweeping (derivative order, window, polynomial order) against the raw data:
  first derivatives correlate poorly; **second** derivatives are the only family
  that matches. Pixel-by-pixel the best correlation is ~0.73 (window 13–15),
  and on the **mean spectrum over 2000 tissue pixels**, where noise averages
  out, it reaches **0.977** at window 11.
- At window 13 the predicted magnitude matches the file to 0.4 %
  (‖model‖/‖file‖ = 1.004), which pins the normalise-then-differentiate order:
  vector normalisation comes **before** the derivative, as in PyIR's
  `QCL2026` pipeline.
- The residual gap (0.977, not ~1.0) and the leftover channel arithmetic — the
  file trims 12 channels at the front and 190 at the back, which no single
  `data_deriv` window explains — say at least one more step is missing, most
  likely a denoiser (PyIR has `imnf_denoise` and a PCA smoother) and/or a
  `keep_range` call.

**The exact window, polynomial order and any denoising step are not pinned
down.** Nothing in this project depends on them yet; E1 is simulation-only and
defines its own preprocessing. If it starts to matter, the cheap fixes are to
read the paywalled Methods section or to email Lyra O'Leary
(lyra.oleary@manchester.ac.uk), who invites questions in both the repo README
and the Zenodo description.

## Consequences for descatter

- **Use `*_raw.h5` only.** The preprocessed files are second derivatives of
  normalised spectra: the scatter baseline and the absolute scale are already
  gone, which is exactly the information a physics-informed corrector needs.
- **The raw-file `/mask` is unusable as shipped** — its shape (235, 277) is not
  the shape of `/spectra` (256, 256). Use the mask from the matching `<core>.h5`,
  or regenerate it with the published Amide I rule.
- Raw absorbance tops out at exactly 8.0 AU in `s10_c048_raw.h5`, so some
  pixels are clipped or saturated. Screen for them before fitting.

## Sources

- Dataset-creation code: <https://github.com/lyyraaa/pcuk2023_dataset_creation>
  (`core_creation.ipynb`) — builds the 199 GB unprocessed release, cutting the
  spectra to the first 1479 channels. No derivative, no normalisation, no
  scatter correction.
- Paper code: <https://github.com/lyyraaa/spatial-spectral-prostate> — loads
  `<core>.h5` and hard-codes `num_wavenumbers = 965`. It does not contain the
  preprocessing itself.
- Toolbox: <https://github.com/lyyraaa/PyIR> — `remove_wax`, `remove_co2`,
  `vector_norm`, `all_spec_min2zero`, `data_deriv`, `area_between`.
- Full dataset: <https://zenodo.org/records/18671069> (199 GB, unprocessed).
