---
status: done
chunks:
  - "[x] 1. Průběh follows the run an action answers with: ?run= names it, it is read again at once, and the poll restarts; the report card's tests wait until an option is offered before clicking it"
---
# Průběh follows a retry

Reported by the product owner, 2026-10-14: "Znovu spustit" on a partly failed research left the new
run's first step, Sestavení dotazníku z návrhu, on "Běží". After a reload and a second click the run
appeared to resume from the first click.

## Findings

- **F1. A retry's run was shown but never read again.**
  1. Claim: after an action, Průběh replaced its run with the one the API answered (a retry's new
     run) without reading it again, so the poll, which had stopped when the old run finished, never
     restarted; and `?run=` still named the old run.
  2. Anchor: `apps/web/src/components/rehome/research/ExecutionSteps.tsx:621 @ 1879783` (the only
     place a poll is scheduled is inside `read`, after a read) and `:638` (`useRun` handed out the
     bare `setRun`); `ProgressStep`'s `act` set the run and nothing else.
  3. Reproduction: `ExecutionSteps.test.tsx` "follows the run a retry starts and keeps reading it,
     so its steps move on screen" fails on 1879783 (`?run=RUN-1`, the step stays RUNNING).
  4. Consequence: the new run's steps froze on screen while the worker went on; a reload went back
     to the old run, and a second click looked like a resume. It was the same run: a retry's
     idempotency key carries the run it retries (`:retry:<run>`,
     `packages/aia_core/src/aia_core/application/research.py:464 @ 1879783`), so the second click
     was answered with the run already going, and nothing was started or paid twice.
  5. Fix: `useRun`'s setter follows the run it is given: writes it into `?run=` when the page has
     one, remembers it when it has none, and reads again at once, which restarts the poll while the
     run can change. Every action (retry, cancel, budget lift, analysis repair) goes through it.
  6. Test: the reproduction above, now passing; the cancel-and-retry, retry-at-the-limit and budget
     tests serve what the API would after the action (the cancelled run, the retry's run, the lifted
     run), since the page now reads it.
- **F2. A report card test clicked an option before it was offered.** "offers the client report
  only for modelled data…" (and the PDF test) clicked a radio that is disabled until the report's
  status is read: 1 failure in 3 runs alone. Both now wait until the option is offered (`offered`).
  The same flake was noted in AiAnalytics-AIA/AIA#417 for the PDF test.

## Doc follow-up

- CLAUDE.md § 2 map, rehome/research ExecutionSteps: "Průběh follows the run an action answers with
  (?run=, read again, the poll restarted)".
