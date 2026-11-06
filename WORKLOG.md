# WORKLOG: descatter

Newest entry on top. Label each entry by machine: (mac), (watford) or (chat).

## 2026-11-06 (mac): coordinator's first session

**State:** `comms/2026-11-05_chat_to_watford_01.md` is OPEN and has no reply
yet. Watford may not have started.

**Done:**
- Filled in the mac row of docs/machines.md.
- `legacy/rmies_sim.py`: not on the Mac (checked Spotlight and ~/Projects). If
  Chris doesn't add it, watford uses the fallback oscillator set, as request 01
  says.
- Watford can't be reached by session messaging from the Mac, so Chris nudges
  it.

**E1 pre-registration review, for Chris before he marks it APPROVED.** E1 is
still DRAFT, so these are clarifications, not amendments.

1. **The negative control as written won't fire.**
   - Back-of-envelope: absorbance Lorentzians, Amide I 0.5 AU, HWHM 12 cm⁻¹,
     amplitude and linear baseline profiled out, no scatter.
   - With noise σ × 100, the Δχ² between f_β = 0 and f_β = 1 is still about
     190 at σ = 1e-3 and about 22 at σ = 3e-3. So the f_β posterior won't
     match the prior.
   - The KS < 0.1 test needs Δχ² ≲ 1. Δχ² = 1 gives KS ≈ 0.04; Δχ² = 4 gives
     KS ≈ 0.2.
   - Proposal: choose σ_neg so that the noise-free, nuisance-profiled Δχ²
     between f_β = 0 and 1 is ≤ 1, and report σ_neg.
2. **The criteria don't say how draws are pooled.**
   - Should "W < 0.05 in ≥ 90 % of draws at a ∈ {3, 3.5, 4}" be pooled over
     all 120 draws (3 radii × 2 f_β × 20) or hold at each radius?
   - The number of control draws isn't set either. Proposal: 20 per f_β per
     condition, the same as the grid.
3. **The preprocessed-condition likelihood has no noise model.**
   - Vector normalisation rescales σ, and the choice sets W in the
     preprocessed condition, which is half of H1.
   - It's also unclear whether normalisation happens before or after the
     1600–1700 cut.
   - Proposal: rubberband over 950–1800, cut to 1600–1700, then
     vector-normalise the window, with σ_pp = σ / ‖window before
     normalisation‖.
4. **Runtime.** The grid is 640 dynesty runs in ≤ 6 h on 16 threads, which
   leaves about 9 CPU-minutes per run. Watford should time a control run and
   project the grid's total before starting it.

The raw condition generates and infers with the same ADA model, so it is a best
case. The exploratory exact-Mie → ADA run is what says how realistic it is.

**Open for Chris:**
1. E1: approve as written, or have the mac write clarifications 1–3 into the
   DRAFT first. Watford runs the controls under request 01, so decide before
   it reaches task 4.
2. Add `rmies_sim.py` if you have it somewhere other than this Mac.
3. Start or nudge the watford session (prompt in docs/KICKOFF.md).

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
