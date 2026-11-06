# CLAUDE.md — descatter

Shared context for every Claude session that works on this repo: the Mac
coordinator, the Watford worker and the claude.ai "Spectra Research" chat.
Claude Code loads this file automatically when started in this directory.
**Git is the only shared memory.** Anything another machine needs to know
goes in the repo.

## What this is

This repo is a research sandbox for **resonant Mie scattering (RMieS) in
infrared (IR) tissue spectra**. It is part of Krzysztof (Chris) Dziuba's PhD
(University of Manchester, Gardner group).

The question: does physics-informed *generative* inference separate scatter
from chemistry better than ME-EMSC, RMieS-EMSC and learned regressors? Such
inference samples a posterior from two pieces: a learned prior over clean
absorbance spectra and a differentiable Kramers–Kronig + Mie forward model.
It should also say honestly when it can't separate them.

Why it matters:
- RMieS can shift the apparent Amide I band by as much as the gap between
  α-helix and β-sheet.
- It was one of two diagnosed causes of the Spectral-JEPA cross-sensor collapse
  (macro-F1 0.044 across sensors vs 0.566 within a sensor). The other cause was
  disjoint per-sensor manifolds.

**This is a side project.** It must not slow down rat-lung-project (Syngenta
presentation, late November 2026) or the thesis (submission around mid-2027).
When in doubt, rat-lung gets the GPU and Chris's time.

- Science, prior work, data and references: `docs/RESEARCH_BRIEF.md`.
- Pre-registered experiments and their status: `docs/EXPERIMENTS.md`.

## Roles

| Session | Where | Role |
|---|---|---|
| **mac** (coordinator) | Claude Code on Chris's Mac, in this repo | The session Chris talks to. Turns his asks into numbered requests for watford, reviews replies against `docs/EXPERIMENTS.md`, and keeps WORKLOG.md and docs/ current. Runs no GPU work. |
| **watford** (worker) | Claude Code on the lab PC watford, in `~/Projects/descatter` | Does what an open request says (code, tests, simulations, training) and reports back through git. Never starts work that no request asked for, apart from fixing its own environment. |
| **chat** (research desk) | claude.ai project "Spectra Research" | Literature, experiment design, reviewing results. Can push to this repo once Chris attaches it. Cannot reach watford's network or message other sessions. |

Paths, environments and budgets for each machine are in `docs/machines.md`.

## Session ritual (every machine, every session)

- **Start:** run `git pull --rebase`. Then read the top WORKLOG.md entry, the
  newest files in `comms/`, and your machine's row of `docs/machines.md`.
- **End, or at any milestone:**
  - Add to your dated WORKLOG.md entry and label it `(mac)`, `(watford)` or `(chat)`.
  - Commit and push.
  - Keep commits small and frequent, and never leave work unpushed overnight.
- **WORKLOG conflicts** are both sessions adding an entry at the top. Resolve
  them by keeping both entries.

## Communication

Git is the channel of record: notes in `comms/`, protocol in `docs/COMMS.md`.

Direct session-to-session messages are only nudges, such as "pushed comms/…,
please pull". The rat-lung sessions' direct link went stale repeatedly
(HTTP 409). Never put content only in a direct message.

## Guardrails

**GPU (watford).** The RTX 5000 Ada (32 GB) is shared; Haolin (m13672hz)
also uses it.
- Before any GPU job, check `nvidia-smi`.
- Take the exclusive lock rat-lung uses so the two projects never overlap:
  `~/.cache/rat_lung_gpu.lock`, via `fcntl.flock` with `LOCK_EX | LOCK_NB`. See
  rat-lung-project `ml/train/twostage.py`.
- Cap memory at 25 GB with `torch.cuda.set_per_process_memory_fraction`.
- Run one GPU job at a time.
- If the lock is held, or a rat-lung queue is running, do not wait in a loop:
  report it and stop.

**CPU.** Export `OMP_NUM_THREADS=16 OPENBLAS_NUM_THREADS=16
MKL_NUM_THREADS=16`. The default 64-thread BLAS pools oversubscribe the shared
machine.

**Disk (watford).**
- Data goes in `~/descatter_data/` and runs in `~/descatter_runs/<run_id>/`.
- Keep the total at 100 GB or less unless Chris agrees.
- Never download the full PCUK2023 (199 GB) without asking. Check Isilon first.

**Other repos are read-only from here.** Don't edit rat-lung-project, spec-ml,
xfer-anno or spectral-tokenization. If one of them needs a change, propose it in
`comms/`.

**Isilon** is read-only on watford. Never stack a second mount on it (see
rat-lung-project `docs/machines.md`).

**Pre-registration.**
- Before the run that decides an experiment, commit its plan, metrics and
  pass/fail thresholds in `docs/EXPERIMENTS.md`.
- Chris must mark them `APPROVED` there, or the mac session can relay his
  approval.
- Smoke tests and controls may run before approval.
- Report failures as plainly as successes.
- Never re-tune after seeing a result unless the re-tuned run is logged as a
  new, labelled analysis.

**Controls.** Every diagnostic needs a positive control, which should fire, and
a negative control, which should not.

**Leakage.**
- Split data by patient or core, never by pixel.
- Never train a prior on evaluation cores.
- Never condition a prior on class labels.

**Provenance.**
- Every run writes `results/<exp>/<run_id>/run.json` with:
  - git commit and dirty flag
  - config
  - data files with their sha256
  - seeds, host and library versions
  - wall time and peak VRAM
- Commit only small outputs (JSON, CSV, PNG under 1 MB). Checkpoints and arrays
  stay in `~/descatter_runs/`.

**Citations.** Papers cited in docs/ carry DOIs or arXiv IDs. Check journal
papers against PubMed or Crossref, and label preprints as preprints.

## Layout

```
CLAUDE.md               this file
WORKLOG.md              dated log, newest on top, labelled by machine
docs/RESEARCH_BRIEF.md  problem, prior work, hypotheses, data, references
docs/EXPERIMENTS.md     pre-registered experiments (E0, E1, ...) and their status
docs/COMMS.md           request/reply protocol and templates
docs/machines.md        per-machine paths, environments, budgets
docs/KICKOFF.md         first prompts for the mac and watford sessions
comms/                  request/reply notes: YYYY-MM-DD_<from>_to_<to>_NN.md
descatter/              python package (physics, inference, data loading)
scripts/ configs/ tests/ results/
legacy/                 reference code (e.g. Lesson 1 rmies_sim.py)
```

## Current state

See the top of WORKLOG.md and the newest file in `comms/`.
