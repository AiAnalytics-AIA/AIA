---
status: planned
chunks:
  - "[ ] FP0. An architecture decision for an organization-level work-queue read: today only WorkQueue reads across studies (ARCHITECTURE.md §3), so a Settings read of every study's waiting work needs its own scoped shape and an ADR"
  - "[ ] FP1. The read: running, waiting for budget, parked and retried in the last 24 hours, per step, with the reason code in words and since when; OWNER and ADMIN only"
  - "[ ] FP2. Fronta práce on Stav systému: four counts and rows Stav / Krok / Proč stojí / Od / Akce, each linking to where it is fixed (Zvednout rozpočet, Schválit pravidla, the run's Průběh)"
---
# Fronta práce: the organization's work queue on Stav systému (after the MVP)

**Nigel, 26 Oct 2026 ~00:38 UTC** (in the Settings session, relayed by the PM coordinator): "lets table this idea as a
plan in the future". This plan is that table: registered after the MVP (master §3.3), nothing scheduled.

**What it is.** The Settings prototype (<https://claude.ai/artifact/8W9LR8Ju9BWnR5JACmiWv7>, v91, artboard Stav
systému §2) draws a work queue for the whole organization: what is running, what waits for budget, what is parked
and what was retried in the last 24 hours, each row with its step, why it stands (the stored code, in words), since
when, and a link to the action that moves it (Zvednout rozpočet, Schválit pravidla, the run's Průběh).

**What it needs.** An organization-level read of the work queue. No route serves one, and `ARCHITECTURE.md` §3
allows only `WorkQueue` to query across studies, so FP0 is an architecture decision before any code. The
"Čeká na rozpočet" tile (`settings-redesign#F20`) needs a narrower read of the same kind; if F20 decides its shape
first, FP1 builds on it.

**Rules carried.** Unknown is never counted as fine; a reason code without words is shown as its code, never
dropped; only those who can act see the coral "needs you" mark.
