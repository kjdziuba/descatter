# Comms protocol (mac ↔ watford ↔ chat)

Git is the channel of record. A message that isn't in git didn't happen.

## Files

Name each note `comms/YYYY-MM-DD_<from>_to_<to>_NN.md`:
- `<from>` and `<to>` are each one of `mac`, `watford` or `chat`.
- `NN` counts per sender: 01, 02, ...

Never edit another session's file; reply with a new one. A reply names the
request it answers in its first line.

## Request template

```
# <from> → <to>, NN: <one-line goal>
Status: OPEN
Answers: (none) | <file this follows up>
Priority / deadline:

## Context
Links to EXPERIMENTS.md sections, earlier replies, commits.

## Tasks
1. ... (done when: <acceptance criterion>)
2. ...

## Budget
GPU: ≤ 25 GB, ≤ N h · CPU threads: 16 · disk: ≤ N GB · downloads: ...

## Send back
Which files and numbers the reply must contain, and the reply's file name.
```

## Reply template

```
# <from> → <to>, NN: re <request file>
Status: DONE | PARTIAL | BLOCKED

## Per task
1. DONE: numbers, run IDs, commit hashes, file paths
2. BLOCKED: why, what was tried, what is needed

## Deviations from the request or EXPERIMENTS.md
## Surprises the coordinator should know about
## Proposed next steps (not started)
```

## Rules

- A worker has at most one open request at a time. The requester closes the
  request by setting `Status: CLOSED` in its own file.
- If something is ambiguous or blocked, the worker replies `BLOCKED` and stops
  rather than guessing.
- The worker doesn't start work outside an open request, except to fix its own
  environment.
- Numbers in a reply come from committed `results/` files and cite the commit
  hash.
- Run `git pull --rebase` before starting and again before pushing. Never
  force-push.
- After pushing, send the other session a one-line nudge if direct messaging
  works, e.g. "pushed comms/2026-11-06_watford_to_mac_01.md".
  - If messaging fails (the rat-lung link returned HTTP 409 when stale), git
    alone is enough. Chris will tell the other session to pull.
