# chat → watford, 01: set up descatter, run E0, build E1 (no grid yet)

Status: OPEN
Answers: (none; first request)
Priority: low. rat-lung work comes first on the GPU and in Chris's time.

## Context

This is the first request for this repo. Read CLAUDE.md, docs/COMMS.md,
docs/machines.md and docs/EXPERIMENTS.md before starting.

E0 is APPROVED. E1 is DRAFT: its thresholds are waiting for Chris.

## Tasks

1. **Watford row of `docs/machines.md`.** Fill it in: venv path, versions,
   driver, free disk, RAM.
   *Done when* it is committed.
2. **E0.** Run steps 1–6.
   *Done when* `results/e0/summary.json` and the quick-look figure are
   committed.
3. **E1 build.** Do steps 1–2: the forward model and its unit tests.
   *Done when* `pytest tests/` passes and the ADA-vs-exact-Mie figure is in
   `results/e1/`.
   - If `legacy/rmies_sim.py` is missing, use the fallback oscillator set,
     note it, and don't ask.
4. **E1 controls.** Run the positive and negative controls from step 3. Do
   not run the grid.
   *Done when* their numbers are in `results/e1/controls.json`.
5. **Do NOT run the E1 grid** (step 4) unless docs/EXPERIMENTS.md shows E1
   `Status: APPROVED`.

## Budget

- **CPU:** 16 threads.
- **GPU:** only the E0 check, at most 1 minute, holding the rat-lung lock and
  under the 25 GB cap.
- **Disk:** at most 5 GB.
- **Downloads:** the Zenodo sample only.

## Send back

Reply in `comms/YYYY-MM-DD_watford_to_mac_01.md`. The mac session coordinates;
the chat reads the same file. Include:
- environment versions;
- E0 numbers: array shapes, wavenumber grid, noise estimate;
- what "preprocessed" means;
- Isilon findings;
- unit-test results and the ADA-vs-Mie summary;
- control results;
- anything surprising;
- proposed next steps (not started).
