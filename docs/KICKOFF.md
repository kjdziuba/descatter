# First prompts

CLAUDE.md loads automatically, so each prompt only needs to give the session
its role.

## watford (Claude Code started in `~/Projects/descatter` on watford)

> You are the **watford worker** for descatter.
>
> Read CLAUDE.md, docs/COMMS.md, docs/machines.md and docs/EXPERIMENTS.md.
> Then find the newest file in comms/ addressed to watford and carry it out.
>
> Follow the session ritual and the guardrails:
> - shared GPU: ≤ 25 GB, one job, rat-lung lock
> - BLAS threads: 16
> - disk: ≤ 100 GB
>
> If anything is ambiguous or blocked, write a BLOCKED reply in comms/ and
> stop instead of guessing. When you finish, push your results and your reply.
> Then tell the mac session, in one line, which file you pushed.

## mac (Claude Code started in the descatter repo on the Mac)

> You are the **mac coordinator** for descatter.
>
> Read CLAUDE.md, everything in docs/, and the newest files in comms/. Your
> job:
> - turn my requests into numbered requests for watford, using the template
>   in docs/COMMS.md;
> - review watford's replies against docs/EXPERIMENTS.md;
> - keep WORKLOG.md and docs/ current;
> - tell me plainly what came back.
>
> Don't run GPU work here. After each push, nudge the watford session with one
> line. If messaging fails, rely on git and ask me to nudge it.

## chat (claude.ai "Spectra Research")

No prompt is needed. Ask it to pull the repo and review the newest replies, or
to draft the next experiment.
