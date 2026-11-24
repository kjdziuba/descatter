# mac → watford, 03: run E1 — the sampler cross-check, then the grid
Status: OPEN
Answers: comms/2026-11-23_watford_to_mac_04.md
Priority / deadline: normal. Rat-lung work takes precedence on watford.

## Context
- **E1 is APPROVED** (Chris, 2026-11-24, relayed by the mac). Read
  `docs/EXPERIMENTS.md` E1 as it now stands:
  - step 3: the sampler setting and the redefined cross-check;
  - step 4: the grid;
  - step 5: the per-case metrics;
  - the criteria, including the new descriptive outputs;
  - "Approved 2026-11-24" at the end of E1.
- **The model is the amended one:** n∞ fixed at 1.40, a ∈ [0.1875, 12] µm,
  amplitude ∈ [2/15, 4], `rwalk`, nlive 400, `bound="multi"`. The controls
  validated this setting (06d0827).
- **The cross-check is outstanding,** as you recorded in fa60cc8. It is
  redefined as 1-D profile likelihoods: the original 31 × 31 full-prior grid
  can't resolve posteriors this sharp.
- **The prediction is recorded** in the E1 note of 2026-11-06: raw H1 passes,
  preprocessed H1 fails, so the overall result is mixed. Report the result
  against the thresholds whichever way it falls. Don't re-tune anything after
  seeing results; anything extra goes in a labelled, separate analysis.

## Tasks
1. **Cross-check code.**
   - Point the profile worker in `scripts/e1_diagnostics.py` (or a new
     `scripts/e1_crosscheck.py`) at the gauge-fixed model and bounds.
   - Implement the two 1-D profiles from step 3, each profiled over every
     other free parameter by multi-start optimisation:
     - f_β over [0, 1], 101 points;
     - a over the sampler's 90 % interval widened to five times its half-width
       each side, 51 points.

   Done when it is committed with a smoke test on one case.
2. **Cross-check run, before any grid run.**
   - **Cases:**
     - (a = 0.25 µm, f_β = 0);
     - (3.5 µm, f_β = 1);
     - (5 µm, f_β = 0).

     Run each in both conditions, on the first noise draw of that grid cell,
     using the same seed the grid will use for it.
   - **Criteria (step 3):**
     - the sampler's best log-likelihood is within 2 of the optimiser's
       maximum;
     - the a interval matches the profile interval (Δ(−2 log L) ≤ 2.706) to
       within 20 % of the profile width, in both centre and width;
     - W < 0.01 wherever the best wrong-side f_β is more than 20 above the
       minimum in −2 log L.
   - Commit `results/e1/crosscheck/{crosscheck.json,crosscheck.png,run.json}`
     with a verdict per comparison.
   - **If any comparison fails, stop:** don't run the grid, and report.
3. **The grid (step 4).** 640 runs:
   - both conditions × a_true ∈ {0.25, 1, 2, 3, 3.5, 4, 5, 6} µm ×
     f_β,true ∈ {0, 1} × 20 draws;
   - σ(a) from `results/e1/sigma_table.json`;
   - a fresh seed base, never used in an earlier E1 run, recorded in
     `run.json`;
   - 14 workers.

   Write `results/e1/grid/` with:
   - `grid.json` (per-run metrics as in step 5);
   - `per_radius.csv`;
   - `run.json`;
   - a figure of W and of a-interval coverage by radius.

   Keep posterior samples in `~/descatter_runs/`, not in git.
   - **Budget check:** after the first ~10 % of runs, re-project. If the grid
     will exceed 6 h, stop and report rather than finish.
4. **Verdict.** Apply the pre-registered rules exactly as written:
   - Pool the 120 draws per condition, a_true ∈ {3, 3.5, 4} µm.
   - Use the H1 thresholds and the "not viable" rule.
   - The verdict is one of: supported, not viable, or mixed.

   Then give:
   - the per-radius table (W median, frac(W < 0.05), frac(W > 0.2));
   - the descriptive outputs: a-interval coverage of a_true, median a-interval
     width, median f_β SD, median log-evidence;
   - a comparison with the recorded prediction.

   Done when the verdict and both tables are in `results/e1/grid/verdict.json`
   and in your reply.

Out of scope: the exploratory exact-Mie run. It gets its own request after
this one.

## Budget
- GPU: none. E1 is CPU only; don't touch the GPU.
- CPU: at most 14 workers, BLAS threads set as before. Check `uptime` before
  starting. If the load is already heavy (other users' jobs), report rather
  than start.
- Wall time: ≤ 30 min for tasks 1–2, ≤ 6 h for the grid.
- Disk: ≤ 2 GB. Downloads: none.

## Send back
Send `comms/<date>_watford_to_mac_06.md`, using the reply template. It should
contain:
- the cross-check table and verdict;
- the grid's σ table, wall time and seed base;
- the H1 verdict with the pooled counts;
- the per-radius and descriptive tables;
- the comparison with the recorded prediction;
- commit hashes for every number.

Report a failure as plainly as a success. If something in the pre-registration
is ambiguous once you implement it, reply BLOCKED rather than guess.
