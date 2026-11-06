# Machines and environments

Update this file when an environment changes, and keep it short. Each session
fills in its own TBDs in its first session and commits them.

| | **mac** (coordinator) | **watford** (worker) | **chat** (research desk) | **CSF** (optional) |
|---|---|---|---|---|
| What | Chris's MacBook Pro (Mac16,8): Apple M4 Pro, 12 cores, 24 GB RAM, macOS 26.3 | Lab PC, Linux, multi-user (Gardner lab). AMD Threadripper PRO 7975WX (64 threads), 503 GB RAM | claude.ai project "Spectra Research" (cloud sandbox) | SLURM cluster `csf3.itservices.manchester.ac.uk` |
| Access | local. GitHub over HTTPS: `https://github.com/kjdziuba/descatter.git` | Chris logs in through a ThinLinc desktop, and Claude Code runs in a terminal there. Unix user `u37314kd`. GitHub over SSH: `git@github.com:kjdziuba/descatter.git` (HTTPS has no credentials there) | GitHub through the chat's git proxy, once Chris attaches the repo | password-only login; see spectral-tokenization `side_project/CSF3_REFERENCE.md` |
| Repo path | `/Users/krzysiudziuba/Projects/descatter` | `/home/u37314kd/Projects/descatter` | `/home/claude/descatter` (ephemeral) | — |
| Python | `/usr/local/bin/python3.12` (3.12.11, numpy 2.4.2). Bare `python3` is 3.6.8, so don't use it. No venv yet; make `.venv` from 3.12 only if the mac needs to re-run tests or plots (CPU) | TBD: new venv `~/Projects/descatter/.venv` (Python 3.12 from `/opt/anaconda3`), torch CUDA build. Keep it separate from rat-lung's `~/Projects/Syngenta/.venv` | sandbox, CPU only | module system (see CSF3_REFERENCE.md) |
| GPU | none for this project | **RTX 5000 Ada, 32 GB, shared with Haolin (m13672hz).** At most 25 GB, one job at a time, take the rat-lung lock (see CLAUDE.md). Driver 580.159.03 / CUDA 13.0 as of Oct 2026 | none | gpuA (A100 80 GB), gpuL (L40S 48 GB) |
| Data | not needed here | `~/descatter_data/` (100 GB budget). Local NVMe is shared, ~460 GB free in Oct 2026 | none | `~/scratch` |
| Runs | — | `~/descatter_runs/<run_id>/` | — | — |
| Isilon | `/Volumes/gardner` when Chris mounts it (not mounted on 2026-11-06) | `/mnt/isilon-gardner`, read-only for u37314kd. Writes need a per-user `gio mount` from a ThinLinc terminal (see rat-lung-project `docs/machines.md`) | no | not mounted |
| Quirks | No GNU `timeout`. `find` over ~/Documents or ~/Desktop can hang (iCloud), so search ~/Projects. Session messaging can't reach watford from here (2026-11-06), so Chris does the nudges | Case-sensitive filesystem. Set BLAS threads to 16. rat-lung jobs may be running: check `nvidia-smi` and the lock first | Can't reach the university network, LaCie or Isilon. Can't message other sessions | Login nodes: no computation |

Source for the watford row: rat-lung-project `docs/machines.md` and the
2026-10-14 watford readiness audit. Re-check RAM, disk and driver in the first
watford session.
