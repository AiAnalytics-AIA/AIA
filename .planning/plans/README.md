# Plans

One file per feature, broken into chunks agreed **before** code is written.

A plan file is written when a design discussion produces an implementation plan —
not after the work, and not instead of it. It holds the chunks, the design
decisions taken and why the alternatives were rejected, and the review outcome.

Rules:

- Chunks are small enough to build, test and commit one at a time. If a chunk
  feels large, split it again.
- The plan's status is its front-matter: `status:` (`planned`, `in-progress`
  or `done`) and a `chunks:` checklist. After each chunk lands, tick it and
  update `status:`. A feature PR touches **only its own plan file** — not
  another plan, not `../overview.md`, not this README (CLAUDE.md §1, §4).
- When every chunk is done, set `status: done` and leave the file where it is.
  [`done/`](done/) holds plans archived before 2026-09-28; nothing new moves
  there, because a rename conflicts with every open PR that edits the file.
- Findings the feature makes go under **Findings** here, with all six parts
  (CLAUDE.md §9); the docs PR moves them into `../open-items.md` and numbers
  them.
- Every claim about code carries `file:line @ SHA` or a test name.

Template:

```markdown
---
status: planned            # planned | in-progress | done
chunks:
  - "[ ] 1. … — lands: code + tests"
  - "[ ] 2. …"
---
# <feature>

**Owner:** … · **Started:** YYYY-MM-DD

## Problem
What is wrong or missing, and how it shows up to a user or an operator.

## Approach
The shape chosen, and why the obvious alternative was not.

## Trade-off accepted
One sentence.

## Chunks
What each chunk in the front-matter means, in more words than fit there.

## Findings
Defects and questions found on the way, each with all six parts (CLAUDE.md §9).

## Doc follow-up
What the shared documents need once this merges; copied into the PR description.

## Review outcome
Filled in when the plan is archived: what the reviewer found, what changed.
```
