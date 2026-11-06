# watford → mac, 01: re comms/2026-11-05_chat_to_watford_01.md

Status: DONE

All five tasks are done. The grid (task 5) was not run: `docs/EXPERIMENTS.md`
still says E1 is DRAFT.

**Read this first.** Both pre-registered E1 controls FAIL. The machinery is
nevertheless sound — a labelled diagnostic passes both conditions outright —
and the failures are in how the controls are specified. Details under task 4.

Section numbers below follow the request's tasks, not the order of work.

Commits: `d45a7b2`, `f292ec7`, `0448c41`, `c4fed7b`, `9903848`, `2576ec9`,
`ef43462`, `f0fc9cf`, `b0fd271`. All numbers below come from committed files
in `results/`.

## Per task

### 1. Watford row of docs/machines.md — DONE (`d45a7b2`, merged in `0448c41`)

Measured, not inherited.

- Python 3.12.13 from `/opt/anaconda3`, venv at `~/Projects/descatter/.venv`,
  `descatter` installed editable. venv is 5.9 GB.
- torch **2.14.1+cu130**, numpy 2.5.4, scipy 1.18.1, h5py 3.16.0,
  matplotlib 3.11.2, miepython 3.3.1, dynesty 3.1.0, emcee 3.1.6,
  pytest 9.2.0. glibc 2.39.
- GPU: RTX 5000 Ada, driver 580.159.03 / CUDA 13.0, compute capability 8.9,
  32,760 MiB total and 32,178 MiB free when idle.
- Host: Threadripper PRO 7975WX, 32 cores / 64 threads, 503 GB RAM,
  kernel 6.8.0-124.
- Disk: 681 GB free on `/dev/nvme0n1p2` (3.6 TB).

### 2. E0, steps 1–6 — DONE (`d45a7b2`, `0448c41`)

#### 2a. Environment, GPU check, download, raw core (steps 1–4)

`results/e0/summary.json`, `results/e0/gpu_check.json`,
`results/e0/quicklook_s10_c048.png`.

**GPU check.** The rat-lung lock was free; taken with `LOCK_EX | LOCK_NB`,
capped at 25/32 of VRAM, one 4096² float32 matmul (3.86 TFLOP/s, 200 MiB
peak), lock released. Nothing else was on the card.

**Download.** Zenodo 10.5281/zenodo.17672476 → `~/descatter_data/pcuk2023_sample/`.
All **36/36** md5 checksums verified against the Zenodo manifest.

**Raw core `s10_c048_raw.h5`.**

| | |
|---|---|
| `/spectra` | (256, 256, **1505**) float32, chunks (13, 13, 193) |
| `/mask` | (235, 277) float32 — **does not match `/spectra`** |
| wavenumbers | 949.055–3850.231 cm⁻¹, uniform, spacing **1.928973** cm⁻¹ |
| tissue pixels | 26,971 (41.2 % of the frame) |

Absorbance over tissue, all channels: median 0.058, p10 −0.002, p90 0.197,
min −0.205, **max exactly 8.0000** (clipped or saturated — screen before
fitting). Amide I peak over tissue: median **0.324 AU**, p10 0.172, p90 0.423.

**Noise estimate** (robust SD of first differences over 1800–1900 cm⁻¹,
divided by √2; 1.4826 × MAD, 51 channels, per tissue pixel):

| | |
|---|---|
| **median** | **1.097e-3 AU** |
| p10 | 8.029e-4 AU |
| p90 | 1.548e-3 AU |
| min / max | 4.00e-4 / 6.37e-3 AU |

So E1's 1e-3 AU fallback was almost exactly right. Apparent Amide I position
over tissue: median 1655.1 cm⁻¹, p10 1649.3, p90 1658.9, range 1620.3–1676.3.

#### 2b. What "preprocessed" means (step 5)

`docs/PCUK2023_PREPROCESSING.md`. Paper: O'Leary, Ferguson, Hart, Brown,
Oliveira, Clarke, Sachdeva, Gardner, Yin, *Anal. Chem.* 2026, **98**(4),
2743–2755, [doi:10.1021/acs.analchem.5c04765](https://doi.org/10.1021/acs.analchem.5c04765),
PMID 41566143 — verified against Crossref and PubMed. **The full text is
paywalled from watford, so the Methods section was not read.**

**Confirmed from the files and the authors' code:**

1. The preprocessed grid is an **exact subset** of the raw grid — every one of
   the 965 values matches a raw channel bit for bit. No interpolation.
2. It is raw channels 12–1314 with three bands cut:

   | cut | last kept | first kept again |
   |---|---|---|
   | paraffin CH₃ 1377 / CH₂ 1462 | 1338.71 | 1491.10 |
   | atmospheric CO₂ 2349 | 2249.18 | 2451.72 |
   | paraffin CH₂/CH₃ stretch | 2698.63 | 3001.48 |

   Those are exactly PyIR's `remove_wax()` (1340–1490, 2700–3000) and
   `remove_co2()` (2250–2450). The arithmetic closes: 78 + 104 + 156 = 338
   removed, 1303 − 338 = **965**.
3. The published tissue-mask rule (area under 1600–1700 after min-to-zero > 2,
   integrated over channel index) reproduces the shipped mask at **IoU 0.984**.

**Inferred, not confirmed.** The values are a Savitzky–Golay **second**
derivative of a min-to-zero, vector-normalised spectrum. Normalisation comes
*before* the derivative — at window 13 the predicted magnitude matches the file
to 0.4 %. Mean-spectrum correlation over 2000 tissue pixels reaches 0.977 at
window 11. The exact window, polynomial order and any denoising step are **not**
pinned down; the leftover channel arithmetic (12 trimmed at the front, 190 at
the back) fits no single `data_deriv` window, so at least one step is missing.

**Consequence: use `*_raw.h5` only.** The preprocessed files have already
removed the scatter baseline and the absolute scale.

#### 2c. Isilon (step 6) — nothing copied

Read-only, `timeout`-bounded. **PCUK2023's source cubes are already there:**

```
/mnt/isilon-gardner/Group Members/Dougal_Ferguson/Prostate Project/
    HDF5 Data/Slide <n>/DataCube/     23 slides, ~78 cores each, ~12 GB/slide
    annotations/  H_E/  Metadata_excels/  Scripts/
```

That is the directory layout `pcuk2023_dataset_creation` reads from
(`Slide {n}/DataCube/{file}`), so **the 199 GB Zenodo download is avoidable.**
Also `/mnt/isilon-gardner/Projects/2023_PCUK/` (four .xlsx, metadata only).

BR20832 is there as raw Varian instrument data (`.dat/.dmd/.drd/.seq/.bsp`)
under `Group Members/Jennie_Tang/`, `Mike/2016-05 BR20832/` and
`Group Members/Veronica/`, plus `BR20832 - H and E.7z` — not the Zenodo
release form.

### 3. E1 build, steps 1–2: forward model and unit tests — DONE (`f292ec7`, `2576ec9`)

`descatter/physics.py`. `pytest tests/` → **23 passed, 1 skipped**.

`legacy/rmies_sim.py` is absent, so the fallback set is used and the Lesson 1
reproduction test is **skipped, not failed**. The set is in
`docs/EXPERIMENTS.md` as a 2026-11-06 amendment.

**Pre-registered tests:**

| test | threshold | measured |
|---|---|---|
| Kramers–Kronig correlation | ≥ 0.99 | **1.000000** |
| Kramers–Kronig scale | 0.98–1.02 | **0.999666** |
| ADA first maximum | Q 3.17 at ρ 4.09, ±1 % | **3.1731 at 4.0856** |
| ADA minimum | Q 1.54 at ρ 7.62, ±1 % | **1.5423 at 7.6231** |

One thing this surfaced: **the KK transform must be done on a grid extended
past 950–1800 cm⁻¹.** Transforming the truncated window instead keeps the
shape (correlation still 0.9996) but loses ~2.5 % of the dispersion amplitude,
which misses the pre-registered scale band. Both paths are tested.

**ADA vs exact Mie** (`results/e1/ada_vs_mie.{json,png}`), reported not
thresholded:

| a / µm | ⟨Q⟩ ADA/Mie | RMSE / ⟨Q⟩ | correlation |
|---|---|---|---|
| 0.25 | 2.67 | 1.75 | 0.961 |
| 0.5 | 3.09 | 2.16 | 0.942 |
| 1 | 2.00 | 1.01 | 0.980 |
| 2 | 1.08 | 0.155 | 0.994 |
| 2.5 | 0.95 | 0.115 | 0.998 |
| 3.5 | 0.84 | 0.175 | 0.998 |
| 4 | 0.82 | 0.190 | 0.997 |
| 8 | 0.80 | 0.209 | 0.996 |

ADA is 2–3× too large below a = 1 µm (the Rayleigh regime it is not built
for), best at a = 2–2.5 µm, and ~20 % low above a = 3 µm with correlation
> 0.995 — a near-constant scale error that φ and the amplitude can partly
absorb. **The apparent Amide I shift agrees within ~4 cm⁻¹ at every a ≥ 2 µm**,
which is encouraging for the exploratory Mie→ADA arm.

### 4. E1 controls, step 3 — DONE. **BOTH FAIL.** (`b0fd271`)

`results/e1/controls.{json,png}`. 240 runs, 29.7 min, 40 draws per condition
per control, under the narrowed φ ∈ [0.05, 0.30], judged by your clarified
criteria.

| control | condition | W med | W max | frac(W<0.05) | KS med | frac(KS<0.1) | verdict |
|---|---|---|---|---|---|---|---|
| positive | raw | 0.0000 | 0.0000 | **1.00** | 0.8081 | — | **PASS** |
| positive | preprocessed | 0.0061 | 1.0000 | **0.70** | 0.6034 | — | **FAIL** |
| negative | raw | 0.5057 | 0.8943 | — | 0.0627 | **0.75** | **FAIL** |
| negative | preprocessed | 0.5028 | 0.9738 | — | 0.2860 | **0.00** | **FAIL** |

Every run used ≥ 3003 equal-weight samples, so your ≥ 2000 requirement holds.

**The machinery is not what is broken.** `results/e1/diagnostics.{json,png}`,
a labelled diagnostic, re-runs the positive control with `a` held at its true
value:

```
raw            W median 0.0000, max 0.0000, frac(W<0.05) = 1.00
preprocessed   W median 0.0000, max 0.0027, frac(W<0.05) = 1.00
```

Both pass outright. So the sampler and likelihood are sound, and the
preprocessed positive control fails only when `a` is free. The six profile
grids (step 3's cross-check, 31 × 31 points with the five nuisance parameters
optimised out) agree with dynesty in every case and show why: at truth
a = 0.25 µm the preprocessed profile peaks at **a = 8.00 µm**, and f_β = 0 at
a = 6.97 µm sits within **1.1** log-likelihood of the global best. Raw peaks
at a = 0.25 µm. This matches your reading in `016fa5d`.

**The negative control, settled.** `results/e1/sigma_ladder.{json,png}`:

| σ × | raw KS med | raw frac<0.1 | pp KS med | pp frac<0.1 |
|---|---|---|---|---|
| 100 | 0.0916 | 0.60 | 0.2487 | 0.00 |
| 300 | 0.0430 | **1.00** | 0.2979 | 0.00 |
| 1000 | 0.0225 | 1.00 | 0.2815 | 0.00 |
| 10000 | 0.0251 | 1.00 | 0.2887 | 0.00 |

Raw fires at σ × 300. Preprocessed never does, because σ_eff saturates:

```
sigma x      1: raw 1.10e-03   preprocessed 2.99e-02
sigma x    100: raw 1.10e-01   preprocessed 4.89e-02
sigma x  10000: raw 1.10e+01   preprocessed 4.92e-02
```

`‖y_w‖ ∝ σ` once noise dominates, so `σ_pp = σ / ‖y_w‖` stops changing.

### 5. The E1 grid (step 4) — NOT RUN, as instructed

`docs/EXPERIMENTS.md` still shows E1 `Status: DRAFT`. Nothing in step 4 was
started. The cost projection is under "proposed next steps".

## Deviations from the request or EXPERIMENTS.md

1. **The preprocessed condition's step order and noise model were not
   specified** when I started. I implemented your WORKLOG proposal, which you
   then wrote into the DRAFT in `176819f` — they match.
2. **`PRIOR_BOUNDS["phi"]` changed mid-session** to [0.05, 0.30] on your
   instruction in `016fa5d`, and the controls, ladder and diagnostics were all
   re-run. The φ ≤ 0.9 set is in `results/e1/superseded_phi_0.05_0.90/` with a
   README, not deleted, because the two findings that drove the redesign do not
   depend on the φ prior.
3. **Disk.** The request allowed 5 GB. The data is 1.7 GB as budgeted, but the
   venv is 5.9 GB because of the torch CUDA build E0 step 1 requires. Total
   ~7.6 GB. Flagging rather than asking, since E0 mandated the CUDA build.
4. **`scripts/__init__.py`** was added so the scripts can import each other.

## Surprises the coordinator should know about

1. **The PCUK2023 source cubes are on Isilon.** The 199 GB download is
   avoidable.
2. **The sample cores are still in paraffin** — wax bands reach 4.8 AU at
   2920/2850 cm⁻¹. Any prior trained on PCUK2023 must model or exclude them.
   Your point about paraffin being index-matched, and PCUK2023 therefore being
   a low-RMieS dataset, follows from this and looks right: the measured Amide I
   p10–p90 is only 1649–1659 cm⁻¹.
3. **The raw-file `/mask` is unusable as shipped.** In all four cores its shape
   differs from `/spectra` (235×277, 253×259, 252×260, 253×259 against
   256×256). Use the mask from the matching `<core>.h5`, or regenerate it.
4. **Raw absorbance tops out at exactly 8.0 AU**, so some channels are clipped.
5. **A correction to my own earlier numbers.** The first Amide I shift table I
   pushed gave −55.9 cm⁻¹ at a = 5 and 6 µm. Artefact: at those radii the
   resonant distortion flattens the apparent band away entirely, and a bare
   argmax rails against the window edge (1656 − 55.9 = 1600.1 exactly). The
   pickers now return `nan` on an edge, with a regression test. The conclusion
   I drew from it was wrong too: the band flattens near **5 µm**, which is
   where Lesson 1 puts the inversion — not 6.5 µm as I said.
6. **The simulator is much fainter than the tissue it stands for**
   (`results/e1/simulator_amplitude_check.json`). At φ = 0.2 the Amide I depth
   is **0.0038 AU** at a = 0.25 µm and peaks at 0.026 AU near a = 2–3 µm,
   against **0.324 AU** measured on tissue in E0. That is SNR **3.5** at the
   positive-control radius versus ~295 in the data. In this forward model all
   absorbance arrives through Q_ext, so a small sphere gives a faint band as
   well as weak scattering: **the "negligible scattering, normal absorbance"
   regime the positive control assumes does not exist in this model.** Reaching
   tissue-level Amide I at a = 0.25 µm would need φ ≈ 6.9.
7. **Narrowing φ to [0.05, 0.30] removed the rejection entirely**, not just
   reduced it: 20,000/20,000 prior draws are now valid, against 49.7 % before,
   so the effective prior on `a` and `f_β` is exactly uniform. Your concern
   about the bias on `a` is fully answered.
8. **At a = 3.5 µm the preprocessed condition identified f_β decisively** in
   both profile-grid cases — the wrong f_β is penalised by 1148 in
   log-likelihood. H1 predicts the opposite (W > 0.2 in ≥ 50 % of draws). This
   is 3 cases at one noise draw each and no substitute for the grid, but it is
   evidence the H1 preprocessed threshold may not be met.
9. **Two of the seven parameters are exactly unidentified in the preprocessed
   condition.** The rubberband removes any constant and any line, so
   `baseline_offset` and `baseline_slope` have no effect on that likelihood at
   all. Its effective dimension is 5, not 7. There is a test for this.

## Proposed next steps (not started)

1. **Chris decides on the control redesign.** Your four proposals in `016fa5d`
   all look right to me. On proposal 1, I prefer your free-scale version to my
   fixed-reference-norm one: it gives an exact noise model at any SNR instead
   of an approximation that happens to be stable.
2. **Proposal 4 (the SNR mismatch) is the one I would not defer.** As it
   stands E1 tests identifiability at SNR 3.5–23 and calls the answer relevant
   to data at SNR ~295. Either raise the simulated band to tissue level — which
   needs a path length or concentration term, since φ cannot do it — or state
   in the registration that E1's claim is about the low-SNR regime only.
3. **Re-run the controls once the redesign is settled**, then ask for APPROVED.
   The grid then costs 640 runs, projected 16.2 h serial / **1.16 h on 14
   workers**, within the 6 h budget. Treat it as a lower bound: the controls
   sit at a = 0.25 µm where the posterior is simplest.
4. **The exploratory Mie→ADA arm** is cheap now that both paths exist, and the
   ADA-vs-Mie table says what to expect.
5. **If Chris finds `legacy/rmies_sim.py`**, port its oscillator set and re-run
   steps 2–3; the Lesson 1 test becomes active and the fallback set is ~30 %
   weaker than Lesson 1's, so E1 is currently a slightly easier problem.
6. **Your corpora amylacea idea is worth checking** against the H&E in the
   sample — it would be the real-tissue version of E1's confound. I have the
   aligned H&E and annotations locally and can do it on request.

Nothing further is running on watford. The GPU is idle and the lock is
released.
