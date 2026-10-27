---
status: planned
chunks:
  - "[ ] FP0. An architecture decision for an organization-level work-queue read: today only WorkQueue reads across studies (ARCHITECTURE.md §3), so a Settings read of every study's waiting work needs its own scoped shape and an ADR"
  - "[ ] FP1. The read: running, waiting for budget, parked and retried in the last 24 hours, per step, with the reason code in words and since when; OWNER and ADMIN only"
  - "[ ] FP2. Fronta práce on Stav systému: four counts and rows Stav / Krok / Proč stojí / Od / Akce, each linking to where it is fixed (Zvednout rozpočet, Schválit pravidla, the run's Průběh)"
  - "[ ] FP3. The Command Center for researchers: a researcher's own queue of what waits, across clients and studies, over FP0's read (the prototypes, V2; after the MVP, Nigel 27 Oct 2026)"
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

## From the unplanned-features inventory (2026-10-27)

Source: the five inventories of 27 Oct 2026 (the Lead, the client pages, Settings, the research stages and the
prototypes, each compared with develop `dbaa7720`) and the product owner's decisions on them (Nigel, 27 Oct 2026,
~01:10-01:40 UTC, in the PM coordinator's chat: "lets turn these into chunks", then an answer to every decision
question). The research build spec cited is <https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy> (spec v6,
prototype v78); its ids carry their section prefix (`navrh/`, `vzorek/`, `sber/`, `szz/`, `lead/`). Waves are in
`.planning/mvp-execution-contracts.md`; a chunk marked **after the MVP** has the wave POST there. Ids are only
added, never renumbered; a ticked chunk a decision reopens gets a follow-up chunk.

**FP3. Command Center** (after the MVP). The prototypes inventory found V2's Command Center for researchers partly
covered by this plan (the organization's queue); Nigel, 27 Oct 2026, keeps it after the MVP with the rest of this plan.
