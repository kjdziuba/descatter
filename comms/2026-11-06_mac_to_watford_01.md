# mac → watford, 01: implement the E1 control redesign and re-run the controls
Status: QUEUED. This opens when `comms/2026-11-05_chat_to_watford_01.md` is
CLOSED; the mac will flip it to OPEN and nudge you. Don't start before then.
On hold, too, until Chris answers your objection in
`comms/2026-11-06_watford_to_mac_02.md`. Task 6 may change; tasks 1–5 are
expected to stand.
Answers: comms/2026-11-06_watford_to_mac_01.md
Priority / deadline: normal. Rat-lung work takes precedence on watford.

## Context
- The redesign is in `docs/EXPERIMENTS.md` → E1 → "Redesign 2026-11-06". Step 3
  and the pre-registered criteria are edited to match. Chris approved the
  redesign; E1 is still DRAFT.
- It acts on your reply 01 (b0fd271, diagnostics.json), your bias check
  (810bba6) and the mac's review in the WORKLOG (b07b445, c3051f6).
- Unchanged: the forward model, the priors (φ ∈ [0.05, 0.30]), the grid, the
  metrics and the H1 thresholds.

## Tasks
1. **Preprocessed likelihood.** Change it to y_w ~ N(s · m_w + c0, σ² I) on
   the rubberbanded 1600–1700 window, with s and c0 profiled by linear least
   squares at every call (s unconstrained). Drop σ_pp = σ / ‖y_w‖.
   - Done when there is a unit test that the profiled χ² is invariant to
     y_w → α·y_w + β with σ scaled by α. Your existing test that the
     preprocessed likelihood ignores baseline offset and slope must still pass.
2. **Noise rule.** Implement σ(a) = D(a) / 295, with D(a) defined as in
   EXPERIMENTS.md step 3: max over 1600–1700 of A_abs, where A_abs comes from
   n∞ = 1, Δn = 0, φ = 0.2, amplitude 1, f_β = 0.
   - Done when there is a table of D and σ for a ∈ {0.25, 1, 2, 3, 3.5, 4, 5,
     6} µm, committed as `results/e1/sigma_table.json`.
   - If D(a) behaves oddly (non-monotone, or below 1e-4 AU anywhere), report
     BLOCKED rather than picking another definition.
3. **Two inference options** (code only):
   - fix a at a given value;
   - an inert-f_β mode, where the β lineshape (bands 13–14) is replaced by the
     α lineshape (band 12) in both simulation and model.

   Done when there is a unit test that, in inert mode, the model output is
   identical for f_β = 0 and 1.
4. **Likelihood calibration (gate).** χ² of the true model against its own
   noisy data, under the new σ(a).
   - Cells: a ∈ {0.25, 3.5} µm × f_β ∈ {0, 1} × {raw, preprocessed}, 200
     draws each.
   - Report median, p10 and p90 against the expected N (raw) or N − 2
     (preprocessed).
   - Done when `results/e1/likelihood_calibration.json` is committed. The gate
     passes if every median is within ±10 %.
   - If it fails, stop there and report; do not run task 5.
5. **Controls, redesigned.**
   - Runs:
     - positive with a fixed at 0.25 µm;
     - negative with f_β inert at a = 0.25 µm;
     - both under σ(0.25 µm), with 40 draws per condition each, as in
       EXPERIMENTS.md;
     - the free-a positive control as a labelled observation (40 draws per
       condition, not thresholded).
   - Judge against the criteria as now written.
   - Done when `results/e1/controls.{json,png}` are committed with verdicts.
     Move the b0fd271 set into `results/e1/superseded_controls_2026-11-06/`
     with a README.
6. **Grid cost projection** at the new σ.
   - Time 2 runs per condition at a = 3.5 and a = 5 µm, then project the
     640-run grid on 14 workers.
   - Don't run the grid; E1 is not APPROVED.

## Budget
- GPU: none (E1 is CPU only). CPU threads: 16 per process (set the BLAS
  variables), at most 14 workers.
- Wall time: ≤ 3 h for tasks 4–6 together. If the projection says otherwise
  partway, stop and report.
- Disk: ≤ 2 GB. Downloads: none.

## Send back
your next reply file (`comms/<date>_watford_to_mac_03.md`, since 02 is taken), using
the reply template. It should contain:
- the σ table;
- the calibration table with its gate verdict;
- the control verdict table in the same layout as reply 01, plus the free-a
  observation;
- the grid projection;
- commit hashes for every number.

Also flag anything in the redesign that looks wrong once implemented,
especially the D(a) definition. If something is ambiguous, reply BLOCKED
rather than guess.
