# mac → watford, 02: fix n∞ in E1's inference, test the raw negative control, then re-run the controls
Status: OPEN
Answers: comms/2026-11-09_watford_to_mac_03.md
Priority / deadline: normal. Rat-lung work takes precedence on watford.

## Context
- **Chris's decision (2026-11-09):** fix n∞, and test before re-running the
  controls. The amendment is in `docs/EXPERIMENTS.md`, E1 → "Amendment
  2026-11-09", with steps 3 and 5 edited to match. E1 is still DRAFT.
- **Why:** the mac's review of your reply 03 is in WORKLOG 2026-11-09 (mac),
  f7cffde.
  - In `qext_ada` the spectrum sees a only through a(n∞ − 1) and a·amplitude.
    So (a, n∞, amplitude) → (λa, 1 + (n∞ − 1)/λ, amplitude/λ) is an exact
    ridge.
  - At a = 0.25 µm the free-a posterior matches the predicted 1/a² ridge
    marginal to three decimals.
  - The mac's hypothesis is that the curved ridge, not f_β alone, is what
    stalls raw `rwalk`. This request tests it.
- **Unchanged:**
  - the forward model and the simulated data (truth n∞ = 1.40, amplitude 1);
  - σ(a);
  - the calibration gate, which stands as run;
  - the control designs, the criteria and the grid.
- **One cost note on `walks`.** The as-run controls make about 23 likelihood
  calls per iteration, which is about `walks`. So raising `walks` costs
  roughly linearly.

## Tasks
1. **Confirm the ridge.** Add a unit test that `forward()` gives the same
   A_app at (a, n∞, amplitude) and at (λa, 1 + (n∞ − 1)/λ, amplitude/λ).
   - Cases: λ ∈ {0.7, 1.3} × a ∈ {0.25, 3.5} µm × f_β ∈ {0, 1}.
   - Check the raw spectrum and the preprocessed window, to a maximum
     absolute difference of 1e-10 AU.
   - Done when the test is committed and passes.
   - If it fails beyond float noise, reply BLOCKED: the amendment rests on it.
2. **Gauge-fixed inference.** Make the amended E1 setup the default:
   - n∞ fixed at 1.40 in inference;
   - priors a ∈ [0.1875, 12] µm and amplitude ∈ [2/15, 4];
   - keep the old 7-parameter setup reachable by a flag, so the 0e209c7
     results still reproduce.

   Done when the full test suite passes. Update tests that assert the old
   bounds, and say which ones you changed.
3. **Degeneracy screen under the new bounds.** Re-run
   `scripts/e1_degeneracy_review.py` with n∞′ fixed at 1.40 and the new a′ and
   amplitude bounds. Commit `results/e1/degeneracy_review_gauge.json`.
   - Done when the reply tabulates min χ² per radius, in both conditions,
     against `degeneracy_review.json`.
   - Flag any radius where min χ² falls by more than 10 %. The recorded grid
     prediction was computed under the old bounds.
4. **Labelled diagnostic: raw negative control under the gauge.** This is not
   the control. Commit it as `results/e1/gauge_diagnostic.json`.
   - **Runs:**
     - f_β inert, a = 0.25 µm, σ(0.25 µm), raw, `rwalk`, nlive 400 (as run);
     - 8 draws (f_β,true ∈ {0, 1} × 4);
     - fresh seeds, not used in any earlier E1 run.
   - **Timing:** 2 runs per condition at a = 3.5 µm and at a = 5 µm, in the
     grid configuration.
     - Report each run's 90 % interval for a against the truth, and its wall
       time.
     - Re-project the 640-run grid on 14 workers.
   - **Go to task 5 only if** KS < 0.1 in all 8 draws and the median KS
     < 0.05.
   - **If it falls short:** run your `walks` test on the gauge-fixed model, as
     a labelled diagnostic (walks 50 and 100, 4 draws each, the same raw
     negative-control set-up). Then stop and report.
     - Don't adopt a new sampler setting, and don't re-run the controls. The
       budget is Chris's call.
5. **Controls under the amended model.** This is a new labelled analysis, and
   runs only if task 4 passes.
   - **Sets:**
     - positive (a fixed at its truth);
     - negative (f_β inert);
     - the free-a observation.
   - **Settings:** both conditions, 40 draws per condition per set, fresh
     seeds, σ(0.25 µm), `rwalk`, nlive 400.
   - **Output:** write to `results/e1/controls_gauge/` (`controls.json`,
     `controls.png`, `run.json`). Leave `results/e1/controls.json` exactly as
     run.
   - **Judging:** use the criteria as written. For the free-a observation, also
     report the fraction of draws whose 90 % interval for a contains 0.25 µm.
     It isn't thresholded.
   - Done when the files are committed with verdicts.
   - Don't run the grid; E1 is not APPROVED.

## Budget
- GPU: none (E1 is CPU only).
- CPU: at most 14 workers, with the BLAS thread variables set as in request
  01.
- Wall time: ≤ 2.5 h for tasks 3–5 together. If a projection says otherwise
  partway, stop and report.
- Disk: ≤ 2 GB. Downloads: none.

## Send back
Send `comms/<date>_watford_to_mac_04.md`, using the reply template. It should
contain:
- the ridge test result;
- the degeneracy-screen table (old against new);
- the diagnostic table: KS per draw, a-interval coverage, timing, and the new
  grid projection;
- if task 5 ran, the control verdict table in the reply-03 layout, plus the
  free-a coverage;
- commit hashes for every number.

Flag anything in the amendment that looks wrong once implemented, especially
the bounds. If something is ambiguous, reply BLOCKED rather than guess.
