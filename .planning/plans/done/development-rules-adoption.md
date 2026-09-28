---
status: done
chunks:
  - "[x] 1. tools/layer_check.sh + make layer_check / make verify"
  - "[x] 2. ARCHITECTURE.md"
  - "[x] 3. CLAUDE.md + AGENTS.md"
  - "[x] 4. .planning/"
  - "[x] 5. CI: layer_check blocking"
---
# Development rules adoption

**Status:** complete · **Landed:** 2026-09-22 · **Branch:** `claude/amazing-cerf-1lhmze`

## Problem

The operating rules for this codebase lived in a prompt handed to an agent at the
start of a session. Nothing enforced them, nothing outlived the session, and
every new session started by re-deriving the same conventions from the code — or
not. Three specific costs were already visible in the history at df294e2:

- Layering held only by review. Nothing mechanically prevented a `Session` in a
  route handler or a `sqlalchemy` import in the pure domain.
- Progress and open questions lived in `docs/migration/status.md`, a narrative
  document that mixes reasoning with tracking. A narrative cannot be a tracker:
  the item and the fix drift apart.
- Framework gotchas — the hardcoded `.venv` path, the root `pyproject.toml`
  discovery trap, the `Any` leak through a declared `-> str` — were recorded in
  commit bodies and code comments, where they are found only by someone who
  already knows to look.

## Approach

Adapt the rules to this repository rather than paste them. Every placeholder is
resolved to a real command, every enforced rule is one that already passes, and
every anti-pattern names the incident from *this* history.

Three decisions taken with the repository owner before writing:

1. **`main` is both trunk and release.** A separate release branch buys nothing
   until there is a deployment to protect; recorded as OI-3 with a trigger to
   revisit.
2. **`Co-Authored-By` trailers stay**, consistent with all existing history.
3. Permission to commit this change set was given explicitly; the standing
   permission rule in `CLAUDE.md §5` binds from the next session onward.

One deliberate deviation from the rules as written: they place lint and type
checks in the advisory tier. Here `ruff` and `mypy --strict` are already green and
already blocking, so demoting them would be a ratchet running backwards. The
deviation and its reasoning are stated in `ARCHITECTURE.md §8`.

## Trade-off accepted

Four root-level documents and a `.planning/` tree are now a maintenance
obligation in every change set — the cost of the rule that stale docs are worse
than no docs is that keeping them current is real work, paid on every commit.

## Chunks

- [x] 1. `tools/layer_check.sh` + `make layer_check` / `make verify`. 12 rules,
      all green at adoption, each proven to fail when violated.
- [x] 2. `ARCHITECTURE.md` — layers, contracts, the where-does-this-go tree,
      anti-patterns A1–A10 with audit commands, CI tiers with promotion
      conditions.
- [x] 3. `CLAUDE.md` + `AGENTS.md` — the map and the working rules; the framework
      gotchas with wrong/right pairs.
- [x] 4. `.planning/` — `PROGRESS.md` as the tracker, `open-items.md` with four
      anchored entries, `plans/` with its template.
- [x] 5. CI: `layer_check` as a blocking step; `docs/migration/status.md`
      pointed at the tracker so the narrative cannot silently become one.

## Review outcome

Verified on Python 3.12.12 and PostgreSQL 16, in a virtualenv built from declared
dependencies only:

| Gate | Result |
| --- | --- |
| `mypy --strict` | clean, 32 source files |
| `ruff check` / `ruff format --check` | clean, 48 files |
| `layer_check` | 12 rules pass |
| `alembic upgrade head` / `check` / downgrade-to-base | clean, no drift, reversible |
| Concurrency suite, `AIA_REQUIRE_POSTGRES=1` | **16 passed** — real contention, not skipped |
| Full suite on PostgreSQL | **402 passed, 94 skipped** |
| Full suite on SQLite | **386 passed, 110 skipped** |

The 94 skips are the parity and characterization tests; the prototype is
deliberately not vendored (OI-1). 402 + 94 = 496, matching the documented
baseline at df294e2 exactly, which is the evidence that this change set moved
nothing.

`layer_check` was proven to fail, not merely to pass: an injected
`from sqlalchemy import select` in `domain/` and an injected `StudyContext(...)`
in `apps/api/` both produced a named FAIL and exit 1, and removing them returned
the run to green.

Every audit command in `ARCHITECTURE.md §6` was executed. A4's 8 hits were
reviewed and closed as OI-4. Running the §10 sequence for the first time found a
real defect in `make deps`, filed as OI-5 and deliberately **not** fixed here —
one logical change per commit.

**Not run in this environment:** the frontend gates (`npm run lint`,
`tsc --noEmit`, `npm run build`) and the startup smoke test. No file under
`apps/web/` was touched; CI covers both.

No source file under `packages/` or `apps/` was modified. This change set is
documentation, one shell script, and the Makefile and CI wiring that run it.
