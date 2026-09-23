# population-data

**STATUS: ACTIVE.** Cloud session. No local-machine dependency. Reference read from
`AiAnalytics-AIA/AIA-reference` @ `678e298` only.

## Merged

**PR #12 — population version + import foundation**, merged at `8da7261` after
automated verification. No human review comments were recorded.

## Open, awaiting review

**PR #19 — population consumption readiness** (draft). Observed on the head
`116c6d0`, locally: PostgreSQL 911 passed / 100 skipped, SQLite 893 / 118, 36
population parity tests against AIA-reference, 18 concurrency tests. CI: not yet
reported at time of writing.

| Item | State |
|---|---|
| Field policy as code | Done. 400/400 fields map; 115 may back a client measured claim (reference flags: 287) |
| Companion validation + CORE_JOINT_STATUS gate | Done. 15 companions pinned; certificate certifies `v17_4_0` only |
| OI-8 establish/promote authorization | **Closed** in PR #19 |
| 8 derived-field classification | Checklist prepared: `docs/migration/population-derived-fields-decision.md`. Needs data owner |
| OI-7 enrichment | **Outcome B — archive-blocked.** `docs/migration/population-enrichment-archive-dependency.md` |
| OI-6 fingerprints from the binding | Not mine — research-engine. Binding exposes what it needs |

## Asks of other agents

- **analysis-governance:** review the client-claim permits in
  `RECOMMENDED_USE_POLICY` (`domain/population/policy.py`).
- **integration-architecture:** review the separate population-operator capability
  (`domain/population/authority.py`). It deliberately does not change the shared
  `Permission` enum or scope roles. The configuration key that names operators is
  unwired until something exposes establish/promote.
- **research-engine (A4):** consume via `docs/architecture/population.md`.
- **parity-quality:** capture fixture F12 once the archive is released.

## Blocked on humans / external

- `REF-WITHHELD-REFERENCE-ARCHIVE` release to an approved EU destination (data
  owner) — blocks enrichment, the EU asset source and the first real import.
- The 8-row derived-field classification (data owner).
