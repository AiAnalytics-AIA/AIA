# Plans

One file per feature, broken into chunks agreed **before** code is written.

A plan file is written when a design discussion produces an implementation plan —
not after the work, and not instead of it. It holds the chunks, the design
decisions taken and why the alternatives were rejected, and the review outcome.

Rules:

- Chunks are small enough to build, test and commit one at a time. If a chunk
  feels large, split it again.
- After each chunk lands, update both this file and `../PROGRESS.md`.
- When every chunk is done, move the feature to Completed in `../PROGRESS.md` and
  move this file to [`done/`](done/).
- Every claim about code carries `file:line @ SHA` or a test name.

Template:

```markdown
# <feature>

**Status:** in progress · **Owner:** … · **Started:** YYYY-MM-DD

## Problem
What is wrong or missing, and how it shows up to a user or an operator.

## Approach
The shape chosen, and why the obvious alternative was not.

## Trade-off accepted
One sentence.

## Chunks
- [ ] 1. … — lands: code + tests + doc update
- [ ] 2. …

## Review outcome
Filled in when the plan is archived: what the reviewer found, what changed.
```
