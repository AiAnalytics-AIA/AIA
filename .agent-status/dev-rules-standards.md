# Agent Status — dev-rules-standards

## Identity

- Agent: `dev-rules-standards`
- Role: Repository operating standards and their mechanical enforcement — the development rules, the layering checker, the planning tree, and the documentation triad.
- Updated: 2026-09-22T10:58:00Z
- Product repository: `AiAnalytics-AIA/AIA`
- Product branch: `claude/amazing-cerf-1lhmze`
- Product HEAD: `c5057eb`
- Base/main SHA observed: `8f545a5`
- Coordination branch: `coordination/agent-status`

> **ID note.** An earlier draft of this file used `reference-rebuild`. The human
> confirmed mid-turn that the reference/ZIP assignment belongs to a **different
> agent**, so that ID was dropped before anything was pushed — claiming it would
> have told other agents this agent owns work it does not. Nothing under
> `reference-rebuild` was ever published. `dev-rules-standards` is stable from here.

## Current assignment

1. **Development rules — COMPLETED.** Adopt the supplied operating rules as repository content with mechanical enforcement. Merged to `main` via PR #4 as `10cf940`.
2. **Reference rebuild package — WITHDRAWN BY THE HUMAN.** Was worked before the reassignment was known; the resulting commit is open as draft PR #5 and is **awaiting disposition** (see *Blockers*). No further work on it by this agent.
3. **Agent coordination protocol — INSTALLED** this turn.

**Scope boundaries — not owned by this agent:** the reference/ZIP forensic rebuild (reassigned), and every product subsystem — research engine, simulation, Sociomapping, population, reporting, analysis, Data Library, frontend.

## Latest user instruction

Three instructions this session:

1. Implement the supplied development rules canonically for the AIA project, treating them as hardcoded in everything the team does.
2. *(Later shown to be misdirected)* Turn the original AIA / NPC Panel ZIP into an authoritative, lossless, rebuildable reference package.
3. Install a standing agent-coordination / ChatGPT handoff protocol: publish a concise but complete status to `coordination/agent-status` after every turn, from an isolated worktree, with a narrow standing authorization to push only the agent's own status file.

Then: *"forget the prompt about the local aia folder that was for a different agent"* — withdrawing #2.

## Latest result

**Development rules (merged).** Adapted the supplied rules to this repository rather than pasting them: every placeholder resolved to a real command, every enforced rule chosen because it *already passed* before being written down, and every anti-pattern named from this repository's own incident history.

Delivered: `ARCHITECTURE.md` (layers, contracts, a where-does-this-go decision tree, anti-patterns A1–A10 each with its audit command, CI tiers with a promotion condition per advisory check), `CLAUDE.md` (map, commands, working rules), `AGENTS.md` (framework gotchas with wrong/right pairs), `.planning/` (PROGRESS as tracker, open-items, plans + archived plan), `tools/layer_check.sh` (12 rules, blocking in CI and `make check`), `make verify`, a PR template, and edits to `Makefile`, `README.md`, `docs/migration/status.md` and `.github/workflows/ci.yml`.

The strongest rule now enforced mechanically is **scope contexts are issued only by `ScopeResolver`** — the Client/Study isolation boundary, previously held by a convention and a code comment.

**Deliberate deviation:** the supplied rules place lint and type checks in the advisory tier. Both were already green and blocking here, so demoting them would run the ratchet backwards. Stated with reasoning in `ARCHITECTURE.md §8`.

**Reference package (withdrawn).** Before the reassignment was known, this agent established that the reference tree and ZIP are **not present in this environment** — checked `../npc-panel-reference`, `$AIA_LEGACY_REFERENCE`, every `.zip` on the filesystem, session uploads, and characteristic prototype filenames (which appear only as two-file fakes inside `pytest` temp dirs). It therefore **refused** to write the capability map, methodology ledger or rebuild contract, since doing so would mean inferring behaviour from filenames. What it did build is tree-independent and honest: a snapshot, a 1324-file hashed inventory classified by type and zone, a dual-mode builder, and a 10-check verifier that runs in CI with no tree. The package reports its own audit as incomplete. **This is now the incoming agent's material, not this agent's work item.**

**Recovery performed:** PR #4 merged mid-turn. The reference-package commit had been pushed *after* that merge and so was not on `main`. The branch was restarted from current `origin/main` (`8f545a5`, including PRs #2 and #3), the commit cherry-picked as `c5057eb`, force-with-lease pushed, and a **new** draft PR #5 opened — a merged PR cannot track new work and was not reused.

## Files changed in product worktree

None uncommitted; working tree clean.

Landed on `main` by `10cf940` (PR #4, merged): `ARCHITECTURE.md`, `CLAUDE.md`, `AGENTS.md`, `tools/layer_check.sh`, `.planning/PROGRESS.md`, `.planning/open-items.md`, `.planning/plans/README.md`, `.planning/plans/done/development-rules-adoption.md`, `.github/pull_request_template.md`, plus edits to `Makefile` (adds `layer_check`, `verify`), `README.md`, `docs/migration/status.md`, `.github/workflows/ci.yml` (adds the blocking layering step).

Open in PR #5 by `c5057eb`: 20 files under `aia-reference-rebuild-package/` — **withdrawn assignment, awaiting disposition.**

## Commands / verification

Observed results:

- `./tools/layer_check.sh` on `c5057eb`, rebased onto `main` incl. PRs #2/#3 — **12 rules pass, exit 0**
- `layer_check` negative control — injected `from sqlalchemy import select` in `domain/` and `StudyContext(...)` in `apps/api/`: **named FAIL, exit 1**; removed: green again. The checker is proven able to fail.
- `pytest packages/aia_core apps/api -q` on PostgreSQL 16 — **402 passed, 94 skipped**
- Same on SQLite — **386 passed, 110 skipped**
- `pytest test_workflow_concurrency.py` with `AIA_REQUIRE_POSTGRES=1` — **16 passed** under real contention
- `mypy --strict` — **clean, 32 source files**
- `ruff check` / `ruff format --check` — **clean, 48 files**
- `alembic upgrade head`, `alembic check`, `downgrade base` + re-upgrade — **clean, no drift, reversible**
- `verify_reference_inventory.py` — **8 pass, 2 skip, 0 fail**
- Parity suite — **not run: reference checkout unavailable**, after checking the locations listed above
- Frontend gates and startup smoke — **not run locally**; nothing under `apps/web/` touched
- **CI on PR #5 — not checked yet.** CI on PR #4 completed with no failing suite before merge.

402 + 94 = 496, matching the baseline at `df294e2` — the evidence the rules change moved no behaviour.

## Findings

**F1 · FINDING · `make deps` installs into the system interpreter, not the venv it creates.**
`Makefile:10-12 @ df294e2`. `:=` is evaluated when make *parses* the file, before `deps` creates `.venv`, so `PY`/`BIN` resolve against a tree with no venv.
Reproduction: `rm -rf .venv && make -n deps` → `/usr/local/bin/python3 -m pip install ...`.
Consequence: a clean checkout's `make setup` installs into system Python or fails outright (it did here — `python3` is 3.11, below the `>=3.12` floor). CI never sees it, having no `.venv`, so this fails **only for first-time setup**.
Smallest fix: lazy expansion (`PY =`, `BIN =`) plus an explicit interpreter floor in `deps`.
Test that would catch it: a CI job running `make setup && make test` from a clean checkout on an image whose default `python3` predates 3.12.
Filed as **OI-5**, now on `main`. Deliberately not fixed in the same commit — one logical change per commit. **Unclaimed and available.**

**F2 · FINDING · The legacy reference is absent from this environment.**
Checked: `../npc-panel-reference` (absent), `$AIA_LEGACY_REFERENCE` (unset), all `.zip` on disk (only OS/toolchain), session uploads, and characteristic prototype filenames (only `pytest` temp fakes).
Consequence: the 94 parity tests cannot run here, matching CI. Relevant to whichever agent owns the reference rebuild.

**F3 · FINDING (self-inflicted, fixed) · Location masked file type in the first inventory build.**
The initial classifier returned `demo_library_asset` before checking extension, hiding 74 of 76 HTML files. Zone and category are now separate facets; counts reconcile exactly against manifest extension totals. Documented in the tool rather than silently patched.

## Decisions / assumptions

**Frozen by the product owner** (asked before writing):
- `main` is both trunk and release; no separate release branch yet. Revisit trigger recorded as OI-3.
- `Co-Authored-By` trailers retained, consistent with existing history.

**Made within delegated authority:**
- Lint and types stay **blocking**, deviating from the supplied rules; reasoning in `ARCHITECTURE.md §8`.
- The 12 layering rules were each chosen because they already passed, so the check is green from day one and red always means a regression.
- OI-5 filed, not fixed, to preserve one-logical-change-per-commit.
- Agent ID changed from `reference-rebuild` to `dev-rules-standards` after the reassignment, before any publication.

**Unresolved question:** disposition of PR #5 — see *Blockers*.

## Blockers / questions for human

1. **PR #5 disposition.** It contains the withdrawn reference-package work: [#5](https://github.com/AiAnalytics-AIA/AIA/pull/5), draft, on branch `claude/amazing-cerf-1lhmze`. Options: leave it open as a starting point for the incoming reference agent, close it, or hand the branch over. **Not closed unilaterally** — it is deletable work but the decision is the owner's, and the incoming agent may want the 1324-file hashed inventory and the verifier rather than rebuilding them.

## Coordination notes for other agents

- **`tools/layer_check.sh` is blocking in CI on `main` as of PR #4.** A new module will fail the build if it imports a framework/driver/SDK into `aia_core/domain/`, opens a `Session` in `apps/api/` outside `dependencies.py`/`main.py`, imports `infrastructure.tables` from the API, constructs an `OrganizationContext`/`ClientContext`/`StudyContext` outside `application/scope.py`, adds a static `@pytest.mark.skip`/`xfail`, or puts a database client in `apps/web/`. Verified 12/12 against the newly merged `residency.py` and self-approval work from PRs #2 and #3. A legitimate new case gets a named `--exclude` plus a comment — do not delete the rule.
- **Documentation is now part of every change set.** `ARCHITECTURE.md`, `CLAUDE.md`, `AGENTS.md` and `.planning/` are on `main`, and `.github/pull_request_template.md` carries the checklist. `.planning/PROGRESS.md` is the tracker; `docs/migration/status.md` is explicitly the narrative and loses when they disagree.
- **Commit style changed:** imperative subject, no `type(scope):` prefix, body explains why not what. Existing history is not rewritten.
- **To the incoming reference-rebuild agent:** PR #5 already contains a 1324-file hashed inventory of the prototype, a dual-mode inventory builder, and a 10-check verifier that runs in CI **without** the reference tree. It also records that the tree is absent here, with the exact locations checked, and four evidence-backed findings (three population-panel generations plus 18 special panels are canonical and hashed; the manifest excludes all runtime-generated output, recoverable only from the ZIP; zero standalone JS/CSS against 76 HTML files; and the prototype's own `FINAL_FILE_MANIFEST_18_6_6.csv` must be reconciled against our manifest before any parity anchor is trusted). Reuse or discard as you prefer — this agent makes no claim on it.
- **No migrations, schema, contract or API surface** introduced by this agent.
- **OI-5 (`make deps`) is unclaimed** — a clean, isolated one-line fix.

## Git state

- Branch: `claude/amazing-cerf-1lhmze`
- HEAD: `c5057eb`
- Working tree: **clean**
- Uncommitted product changes: none
- Product commits since previous update: `10cf940` (merged via PR #4) and `c5057eb` (open in PR #5). Both pushed with explicit permission at the time.
- Force-with-lease used once, on this agent's own branch, to rebase after PR #4 merged. No other branch's history touched.
- PRs: [#4](https://github.com/AiAnalytics-AIA/AIA/pull/4) **merged** (`62ae995` on `main`) · [#5](https://github.com/AiAnalytics-AIA/AIA/pull/5) **open, draft, awaiting disposition**
- `main` observed at `8f545a5`, carrying merged PRs #2 and #3 from other agents.

## Next step

Await the human's decision on PR #5, and on what this agent's next assignment is. No further work on the reference/ZIP task. If nothing else is assigned, the standing obligation is to watch PR #5's CI — specifically whether `tools/layer_check.sh` executes correctly on the GitHub runner, which has run on `main` but not yet been observed on a PR by this agent.

## Latest response to the human

Confirmed the reference/ZIP assignment is dropped and reported that the agent ID was changed from `reference-rebuild` to `dev-rules-standards` before anything was published, so as not to claim another agent's territory.

Reported the coordination protocol as installed: `coordination/agent-status` did not exist and was created from `origin/main`; the status file is `.agent-status/dev-rules-standards.md`; work is done in an isolated worktree at `/tmp/aia-agent-status-reference-rebuild` so the product tree is never switched or stashed.

Flagged that PR #5 still contains the withdrawn reference-package work and asked whether to leave it open for the incoming agent, close it, or hand the branch over — noting it was not closed unilaterally, and that it already contains a 1324-file hashed inventory and a verifier the incoming agent may not want to rebuild.

Noted that the completed and merged work — the development rules and the blocking layering checker — stands and is unaffected by the reassignment, and that `layer_check` passes 12/12 against the production code merged from PRs #2 and #3.
