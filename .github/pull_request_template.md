<!--
The PR body is the commit body, widened (CLAUDE.md §5). Delete a heading only if
it genuinely does not apply — an empty one is more honest than a removed one.
-->

## Problem

What was wrong or missing, and how it showed up to a user or an operator.

## Approach

The shape chosen — and why the obvious fix is not the fix.

## Trade-off accepted

One sentence.

## Measured

Numbers, if this change is about performance, cost or volume. Burst size,
latency, money. Otherwise: `n/a`.

## Deliberately not done

What was in reach and left alone, and why.

## Checks

- [ ] `make verify` passes locally (typecheck, layering, format, tests)
- [ ] Parity suite run locally against `AIA_LEGACY_REFERENCE` **if this touches
      domain logic** — CI cannot run it, so green CI is not evidence
- [ ] `ARCHITECTURE.md` / `CLAUDE.md` / `AGENTS.md` updated in this change set,
      if anything they describe moved
- [ ] `.planning/PROGRESS.md` and the plan file reflect what landed
- [ ] Every new public function has tests; every new job and event has a test file
- [ ] No test skipped, disabled, quarantined or loosened to get green
