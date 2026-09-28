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

## Doc follow-up

What `CLAUDE.md`, `ARCHITECTURE.md`, `AGENTS.md`, `.planning/overview.md` or
`.planning/open-items.md` need once this merges — exact text, or precise enough
to apply without you. A feature PR never edits those files itself (CLAUDE.md §1);
the next docs-only PR applies this section. `none` if nothing moved.

## Checks

- [ ] `make verify` passes locally (typecheck, layering, format, tests)
- [ ] Parity suite run locally against `AIA_LEGACY_REFERENCE` **if this touches
      domain logic** — CI cannot run it, so green CI is not evidence
- [ ] No shared file edited (`ARCHITECTURE.md`, `CLAUDE.md`, `AGENTS.md`,
      `.planning/overview.md`, `.planning/open-items.md`); what moved is under
      Doc follow-up — unless this is the docs-only PR
- [ ] This feature's plan file front-matter reflects what landed
- [ ] Every new public function has tests; every new job and event has a test file
- [ ] No test skipped, disabled, quarantined or loosened to get green
