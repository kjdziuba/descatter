# WORKLOG: descatter

Newest entry on top. Label each entry by machine: (mac), (watford) or (chat).

## 2026-11-05 (chat): repo scaffolded

**Background,** from the Spectra Research chat:
- The idea is a generative, physics-informed RMieS correction: a diffusion
  prior plus a differentiable Kramers–Kronig + Mie likelihood, sampled with
  DPS.
- Literature check: every learned corrector so far returns a single answer.
  No posterior-sampling version was found.
- Public data: PCUK2023 (raw prostate TMA), BR20832 (breast TMA) and a 4-core
  sample.
- The watford setup was recovered from rat-lung-project `docs/machines.md`.

**Written:**
- CLAUDE.md
- docs/RESEARCH_BRIEF.md, EXPERIMENTS.md, COMMS.md, machines.md and KICKOFF.md
- the first request: `comms/2026-11-05_chat_to_watford_01.md`

**Open for Chris:**
1. Approve or edit the E1 thresholds in docs/EXPERIMENTS.md.
2. If you have it, add Lesson 1's `rmies_sim.py` as `legacy/rmies_sim.py`.
3. Fill in the mac row of docs/machines.md, or let the mac session do it.
