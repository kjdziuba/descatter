# watford → mac, 05: the rat-lung GPU lock does not cover the shared GPU

Status: FYI — no action needed from watford, but CLAUDE.md's GPU guardrail has
a hole worth closing before descatter runs anything on the GPU.

Not blocking anything: E1 is CPU-only and nothing of ours is running. I found
this while confirming watford was idle after request 02.

## What I observed, 2026-11-23

`nvidia-smi` shows **15,705 MiB in use and 100 % utilisation**, from four
processes:

```
2844609  13:35 elapsed  ~/Projects/jepa/.venv/bin/python scripts/train_a1_spatial.py --dataset-config configs/cv/breast_q…
2844608  13:35          (same)
2844613  13:35          (same)
2846514  08:40          (same)
```

They are owned by `u37314kd`, our Unix account, but they are **not** descatter
and **not** rat-lung — they are the **jepa** project (Spectral-JEPA), run from
`~/Projects/jepa/`.

Meanwhile:

```
~/.cache/rat_lung_gpu.lock   flock: FREE (fuser reports no holder)
                             contents: "186293"  (a stale PID, file dated 21 Oct)
```

## Why this matters

CLAUDE.md tells every descatter session to serialise GPU work by taking the
rat-lung lock:

> Take the exclusive lock rat-lung uses so the two projects never overlap:
> `~/.cache/rat_lung_gpu.lock` … If the lock is held, or a rat-lung queue is
> running, do not wait in a loop: report it and stop.

That protocol assumes the only two GPU users on watford are descatter and
rat-lung. **jepa is a third user and does not take the lock.** So:

- **a free lock does not mean a free GPU.** Right now the lock is free and
  15.7 GB of a 32 GB card is in use;
- a descatter job that trusted the lock and took its permitted 25 GB would ask
  for 40.7 GB on a 32 GB card and OOM — taking jepa's run down with it, after
  13 minutes of its training;
- the stale PID in the lock file is harmless (`flock` is what counts, not the
  contents) but it reads as though something holds it, which could mislead
  someone checking by eye.

CLAUDE.md does already say "Before any GPU job, check `nvidia-smi`". The point
is that the lock is **necessary but not sufficient**, and the current wording
reads as though the lock is the authoritative check.

## What I suggest

Not for me to decide — CLAUDE.md is shared, and jepa is another repo, which
CLAUDE.md says is read-only from here.

1. **Reword descatter's GPU guardrail** so the order is explicit: read free
   VRAM from `nvidia-smi` first, take the lock second, and require *both*
   before starting. Something like "free VRAM must exceed the job's cap, and
   the lock must be free; a free lock on its own is not enough."
2. **Ask Chris whether jepa should take the same lock.** That is the real fix —
   one lock all three projects honour. It is a one-line `fcntl.flock` in
   jepa's training entry point, but it is jepa's change to make, so it should
   be proposed to that session rather than done from here.
3. **Clear the stale lock file contents** or have whoever takes the lock write
   its own PID, so reading the file by eye is not misleading.

Until something changes, I will check free VRAM as well as the lock before any
descatter GPU work, and report rather than wait if either says no.

## Current state

Nothing of ours is running. descatter has used the GPU exactly once, for E0's
one-minute matmul check, which did take the lock and released it
(`results/e0/gpu_check.json`).
