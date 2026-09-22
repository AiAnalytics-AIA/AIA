# architecture-reconciliation

**STATUS: ACTIVE.** Cloud session. No local-machine dependency.

Environment: Claude Code on the web, ephemeral container, PostgreSQL 16.13 and
Python 3.12.3 provisioned in-session. Everything below was measured here, not
inherited.

## Merged

**Architecture v2.1 reconciliation** — PR #2, merged, `main` green at `8f545a5`.
Twelve conflicts between the frozen decision set and the repository, resolved:
configurable self-approval with an append-only decision ledger, the canonical
`AWAITING_*` / `WAITING_*` state vocabulary with provider and capacity waits
split, the fail-closed EU residency boundary, ADR 0002 rewritten (PostgreSQL is
the v0.1 queue, SQS deferred), ADR 0005 split into an Accepted contract and a
Proposed transport, ADR 0006 corrected, and eight documents brought back in line
with what the code does.

## Open, awaiting review

| PR | What | State |
|---|---|---|
| **#7** | Reference repository pointer + manifest reconciliation | **P1 resolved by me**; CI to confirm |
| **#8** | `fix(workflow)`: atomic study charge — the CI "flake" is a lost update | Draft. Owner: **platform-runtime** |
| **#9** | Remove the reference package from the public repo + exposure guard | Draft. Needs **D4/D5** human decisions |

### PR #7 — the P1

`test_module_inventory.py` told developers to repair manifest drift with
`python tools/reference_manifest.py write`, while that writer scanned the mutable
tree and emitted the old schema — discarding the archive SHA256, the repository
identity and the module list. Both remedies applied: the writer is now
archive-only and refuses a tree write, and every write is gated on a schema
validator. 23 tests, including the tree write asserted to fail *and* leave the
committed manifest byte-identical.

### PR #8 — the flake is a defect

`assert 5.0 == 10.0` was a **race in production logic**, not nondeterminism.
`_charge_study` was an unlocked read-modify-write; under READ COMMITTED two
settling transactions each read the pre-update value and the last writer won.
Probe: eight concurrent $5 charges recorded $5. Direction matters — spend was
*under*-recorded, and unrecorded spend is headroom the budget check hands back
out. Every settlement path was affected, including the `RECOVERY_REQUIRED` path
where the money may already be gone.

Fixed with an atomic `UPDATE … SET spent_usd = spent_usd + :amount`. The
assertion was not weakened and no retry was added. New regression test measured at
**12 failures in 12 runs against the old code, 0 in 12 against the new**; the
original test did not reproduce in 25 runs, so it would not have protected the
fix.

### PR #9 — exposure, and what removal does not fix

**Removing the package does not remove the client-identifying filenames.**
`docs/migration/reference-manifest.json` is already on `main` with 446 of the same
paths. 431 sit under `demo_library/`, which CI already excludes, so a targeted
reduction would remove 436 of 446 with no consumer affected — proposed, not
implemented, because it collides with PR #7 and the residual ~10 need a data-owner
classification.

**No history has been rewritten**, and the recommendation is against rewriting
first: it is a filename inventory rather than a rotatable secret, the repo may
already be cloned or forked, and a rewrite cannot retract what was fetched.
Making the repository private closes it faster. Filed as D5.

`.agent-status/` was found on `main` in `9153c1f` / `d1e9ff3`, contrary to the
rule in its own README. PR #9 removes it from `main` and the guard blocks its
return. **This branch is unaffected and remains its home.**

## Not mine, flagged

- **D4** — which legacy brand tokens name real clients. Not an engineering
  judgement; blocks the manifest reduction and D5.
- **`REF-GAP-SOCIO-R-SMACOF`** → parity-quality + sociomapa-deterministic.
- **`REF-GAP-SIMULATION-WORLD-MODEL`** → parity-quality + simulation-engine.
- **`REF-WITHHELD-REFERENCE-ARCHIVE`** → data owner / population-data, after the
  licensing decision; destination must satisfy EU residency (ADR 0008).

## Honest limitations

- **The parity suite has never run in this session.** The reference checkout is
  unavailable here, so the 94 parity and characterization tests report as
  skipped. They are not counted as passing anywhere I have written.
- **No Drive access.** No Drive file was read or written, and none is claimed.
- I have not read `AiAnalytics-AIA/AIA-reference`; it is outside this session's
  repository scope. Everything above about the reference comes from artifacts
  committed to the public repository.
