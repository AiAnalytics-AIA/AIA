---
status: in-progress
chunks:
  - "[x] 0. Make tools/layer_check.sh honest: a missing path fails, exemptions match by path from the root, a self-test"
  - "[x] 1. Close the second model-call path: the web routes' helpers out of model_adapters; an import-linter contract on model_adapters; grep rules for GovernedModelGateway( and the gateway's .invoke("
  - "[x] 2. Fence network egress to the transport modules: ruff TID251 banned-api, one root ruff configuration, an import contract keeping live wires out of the deep-research steps"
  - "[x] 3. Pin what a worker that outlived its lease can still write (B completes, then A writes)"
  - "[x] 4. The core's layers, the apps' independence and the routers' boundary (a ratchet) as import contracts; the grep rules they cover removed"
  - "[x] 5. Decide the application layer's table access (repositories own it) and encode it as a ratchet contract naming today's three modules"
  - "[ ] 6. develop_seed.py and workspace_migration.py reach their rows through repositories; both leave the ratchet"
  - "[ ] 7. ScopeResolver's queries move behind an infrastructure repository (scope_repository.py); scope.py leaves the ratchet, still the only issuer of a context"
  - "[x] 8. Harden against accidental bypass (audit at e57c3b82): an unsearchable grep pattern fails, no inline suppression of the bans, the tests exemption names its four trees, stale per-file-ignores fail, make verify runs ruff check, any static skip is caught"
  - "[ ] 9. A scope context and an admitted claim carry a digest of their fields, so a modified copy (dataclasses.replace) is refused; its own PR, reviewed by Kyi"
  - "[ ] 10. Contracts from the audit: no tables row imported from any module, synthetic_fieldwork and the workbench fenced, API non-router modules off tables, the domain's import allowlist"
---
# Architecture enforcement — the layering guard says what it checks

`tools/layer_check.sh` is the enforcement behind ARCHITECTURE.md §3 and the only
blocking guard on the layering. This plan makes the guard honest about what it
sees, then closes the gaps it cannot see as a grep.

## Chunk 0 — make `tools/layer_check.sh` honest (done)

What was wrong (`tools/layer_check.sh:28-50 @ 5d545eb`):

- A rule whose path did not exist printed `skip` and returned 0. A moved package
  turned its rules off without a red run.
- An exemption was a `grep --exclude=<basename>`, so it exempted every file of
  that name under the rule's path. Measured at `5d545eb`, three exemptions reached
  files nobody named:
  - `tables.py` (six "touched only by their repository" rules over `$CORE`) also
    exempted `infrastructure/report_docx/tables.py`;
  - `research.py` (the design project's owner rule over `$CORE`) also exempted
    `domain/research.py`;
  - `scope.py` (scope contexts are issued only by ScopeResolver) also exempted
    `domain/scope.py`. Its only matches are the contexts' own `__repr__` strings,
    so it is now exempt by name, with that reason.

What changed:

- `forbid` takes exempt paths from the repository root and drops a hit only when
  its file is exactly one of them. A missing rule path or a missing exempt path
  fails the rule.
- Sourcing the script defines `forbid` and stops before the rules, so the engine
  is tested on a scratch tree:
  `packages/aia_core/tests/test_layer_check_tool.py` (a violation is caught, an
  exempted path passes, a same-basename file elsewhere is not exempt, a bare
  basename exempts nothing, a missing rule or exempt path fails).
- 111 rules pass before and after at `5d545eb`. After merging `develop` (CI runs
  the merge), 131 pass, which is the exploration report's count: it was taken
  against the newer `develop`. That merge brought five more basename exemptions,
  converted the same way. One was the widest found: `__init__.py`, on the
  population-tables rule over `$CORE`, exempted every package `__init__` in the
  core; it now names `infrastructure/__init__.py` alone.

## Chunk 1 — close the second model-call path (done)

Two commits.

**1. The helpers the web routes borrowed leave `model_adapters`** (pure move, F1).
`infrastructure/http_transport.py` (new) holds `certificate_refused` (was
`model_adapters/live_transport._certificate_refused`), `CredentialSource` (was
`model_adapters/transport.py`) and `SigningUnavailable` (was
`model_adapters/bedrock.py`). None had a home outside the package:
`model_adapters/aws_signing.py`, where signing lives, is itself inside `model_adapters`.
`model_adapters` imports them from there and re-exports none (`CredentialSource`
left `model_adapters.__all__`). Afterwards the AST graph of the four source trees
names exactly `aia_executors.ai_runtime`, `aia_executors.deep_research_live` and
`aia_executors.deep_research_runtime` as importers outside the package.

**2. Enforcement.**

- `import-linter` (`packages/aia_core[dev]`), `[tool.importlinter]` in the root
  `pyproject.toml`: one forbidden contract, sources `aia_core.domain`,
  `aia_core.application`, `aia_core.infrastructure.*`, `aia_api`, `aia_worker`,
  `aia_executors`; the three compositions and `model_adapters`' own imports
  ignored. Direct imports only (`allow_indirect_imports`): the registry reaches
  the adapters through a composition, which is the design. An ignore that matches
  nothing fails the run.
- `make layer_check` runs `tools/layer_check.sh` then `lint-imports --no-cache`,
  both always, failing if either fails. CI's Backend job runs `make layer_check`
  (`.github/workflows/ci.yml`); the docs-only job keeps the script (F6).
- `tools/layer_check.sh`: `GovernedModelGateway(` only in
  `aia_executors/ai_runtime.py`; the gateway's `.invoke(` (receiver named
  `*gateway*` / `*Gateway*`, so `StepModelCaller`'s `caller.invoke(` is not it) only
  in `aia_executors/ai_step.py`, over each of the four source trees; and the two
  `__init__` modules above `model_adapters` never name it (F5). 121 rules.
  `test_layer_check_tool.py` runs both gateway patterns from the script itself.
- Each rule shown to bite with a temporary violation (PR description).

## Chunk 2 — fence network egress (done, #444)

- `packages/aia_core` and `apps/api` extend the root ruff configuration instead of copying it
  (95990c9d), so a rule added at the root reaches every tree.
- Ruff `TID251` bans `urllib3`, `urllib.request`, `http.client`, `socket` and `ssl` outside
  seven named files (the model and web transports, `http_transport.py`, the Cognito JWKS fetch,
  the worker's hostname) and tests (1dce09c7); `httpx` and `requests` too (922e120a, #450).
- An import contract keeps `web_retrieval_live`, `web_retrieval_brave`, `common_crawl` and
  `model_adapters.live_transport` out of `aia_executors.deep_research`.
- Findings, for decisions (#444): **E1** `application/web_retrieval.py:140` imports protocols
  from `infrastructure/common_crawl.py`, which imports `web_retrieval_live`, so the contract
  needs `allow_indirect_imports`; moving those protocols to a protocol module would let it
  forbid indirect imports. *Closed by #450:* the protocols live in
  `infrastructure/archive_index.py` (d10e2cce) and the contract forbids indirect imports
  (e1a170e9). **E2** `aia_worker/registry.py:32` imports any module
  `AIA_WORKER_EXECUTORS` names, unrestricted (operator configuration). *Closed:* outside
  `AIA_ENV=local`/`test` (unset or unknown counts as deployed) a factory must come from
  `aia_executors.`, refused before it is imported (`load_executors`,
  `test_a_deployed_worker_refuses_a_factory_outside_aia_executors`). **E3** the contract's
  source is the deep-research steps only; widening it to every executor and the API needs one
  ignore, `aia_api/routers/deep_research.py:69` (`MIN_SCAN_CUTOFF_BYTES`). *Closed:* the constant moved to
  `domain/deep_research/common_crawl.py`, so the API imports no wire module, and the contract's
  sources are every app plus the core's domain and application layers, indirect imports
  included, the compositions' own edges ignored ("only the executor compositions import a live
  network wire").

## Chunk 3 — what a stale worker can still write (done, #443)

`apps/worker/tests/test_stale_lease_artifacts.py` (PostgreSQL) pins:
`test_a_stale_worker_is_refused_before_it_reaches_the_store`,
`test_a_put_inside_the_fence_holds_off_recovery_and_a_failed_block_orphans_its_object` (the
orphan is OI-114) and
`test_an_artifact_committed_before_the_lease_lapsed_is_reused_by_the_successor`.

## Chunk 4 — core layering and the API boundary as import contracts (done)

Four contracts beside the two already there (`pyproject.toml`, `[tool.importlinter]`):

- **Layers** inside `aia_core`: application > infrastructure > domain. Kept at
  `c032cf72`. It replaces the grep rule "domain does not import outward", which matched
  only `from ..application` / `from aia_core.application`. Probed on one tree:
  `from ...application import scope` in `domain/deep_research/contracts.py` and
  `import aia_core.infrastructure.tables` in `domain/licence.py` both passed the grep and
  failed the contract. Nothing checked infrastructure importing application before;
  `from ..application import scope` in `infrastructure/storage.py` now fails.
- **Independence** of `aia_api`, `aia_worker`, `aia_executors` (source only), with one
  allowance: `aia_executors.** -> aia_worker.executor`, the step protocol (25 imports,
  all of that one module). It replaces "the worker never imports the API" and
  "executors never import the API". Probed: worker -> executors, executors ->
  `aia_worker.worker`, API -> `aia_worker.settings` each fail.
- **Routers -> infrastructure, a ratchet** (decided 2026-10-16): 28 router -> module
  edges across nine routers were listed; 27 since #467, because #461 had already removed
  `deep_research.py`'s `common_crawl` import and the stale line failed `develop`'s
  Layering rules (run 1245) -- the ratchet shrinking as designed, two merges apart. A new router complies, a listed router can't
  add an infrastructure module, and a line no import matches fails lint-imports, so
  the list only shrinks. `projects.py` only caught `ProjectNotFound`; it now imports
  the repository's own class from `aia_core/application/errors.py`
  (`test_application_errors.py`). Probed: a new router, `research.py` importing
  `tables`, `projects.py` regressing, and a stale ignore line each fail.

`layer_check`: 145 rules -> 142 + 5 contracts.

**Not encoded, open with Kyi** (TODO in `pyproject.toml` beside the layers contract):
`application/scope.py` queries tables with raw `select()` (`scope.py:23,45,98 @
c032cf72`). It isn't alone: `application/develop_seed.py` and
`application/workspace_migration.py` import `infrastructure.tables` too. A contract
forbidding application -> tables would need all three named, or moved behind
repositories. Also open with Kyi: the two contradictions in ARCHITECTURE.md's layer
table (see the exploration report).

Decided 2026-10-16 (chunk 5 below); the exploration report was never filed, so
chunks 6 and 7 are written from the code, not from it.

## Chunk 5 — the application reaches the tables only through a repository (done)

**Decision** (2026-10-16, the owner delegated it: "decide this off of best
practices"). ARCHITECTURE.md §2 gives infrastructure "SQLAlchemy tables and
repositories"; the repository is where a table's isolation predicate lives
(`ProjectRepository(owner=)`, `ClientKnowledgeRepository` querying by the resolved
client). A use case that writes its own `select()` over `tables` can drop that
predicate, and the next query written beside it copies the one before. So:
application modules read and write rows only through a repository, and keep what
is theirs -- deciding, issuing a context, orchestrating. `ScopeResolver` stays the
only issuer of a scope context (ARCHITECTURE.md §2, layer 2); what moves is how it
reads memberships, studies and clients, not who decides.

Not chosen: a named, permanent exception for `scope.py`. It is the most
security-critical query code in the repository, which is the argument for a
repository with its own tests, not against one.

**Encoded** as a forbidden contract, `aia_core.application` ->
`aia_core.infrastructure.tables` (`pyproject.toml`), with today's three importers
listed as a ratchet, as the routers' contract is: `develop_seed`, `scope`,
`workspace_migration`. They are the only application modules that import
`sqlalchemy`'s `select` too (`develop_seed.py:31`, `scope.py:23`,
`workspace_migration.py:35 @ b8d9789b`); every other application module imports
`Session` or `IntegrityError` alone. Replaces the TODO beside the layers contract.

Probed on one tree, each restored after:
`from ..infrastructure import tables` in `application/research.py` and
`import aia_core.infrastructure.tables` in `application/project_memory.py` each
fail the contract; a fourth ignore line (`application.research -> tables`) that no
import matches fails the run ("No matches for ignored import").

`layer_check`: 142 rules + 6 contracts.

## Chunk 8 — accidental bypass, from the audit at `e57c3b82` (done)

An adversarial audit of `develop @ e57c3b82` (103 probes in a throwaway worktree)
found where the enforcement could be switched off or stepped around without anything
failing. This chunk takes the accidents; chunks 9 and 10 take the rest. Each change
was proved with a temporary violation, then reverted.

- **An unsearchable pattern passed.** `forbid` ran grep with `2>/dev/null || true`
  (`tools/layer_check.sh:57 @ e57c3b82`), so grep's exit 2 read as "no match": with
  `_across_studies(` as the pattern and a violation present, 142 rules passed. Exit 2
  now fails the rule (`test_a_pattern_grep_cannot_run_fails_the_rule`).
- **Inline suppression lifted the egress ban.** `# noqa: TID251`, a bare `# noqa` and
  a code-less `# ruff: noqa` each passed. Three grep rules per source tree refuse them;
  code-scoped `# ruff: noqa: RUF001` (`persona_profile.py:29`) and `# noqa: E501` pass.
- **The tests exemption reached source.** `"**/tests/**"` (`pyproject.toml:45 @
  e57c3b82`) exempted a source package named `tests`; so did `packages/*/tests/**`,
  because ruff's `*` crosses a `/` (measured). The four test trees are now named. The
  five stub-server tests still pass.
- **A stale per-file-ignore passed silently.** `test_ruff_config.py` fails an entry
  whose path does not exist, and one starting with `**`.
- **`make verify` never ran `ruff check`** (`Makefile:193-200 @ e57c3b82`), so TID251
  never ran locally through the pre-commit sequence. It does now.
- **Static skips by any name.** `pytestmark = pytest.mark.skip`, an alias, `from pytest
  import mark` and `pytest.param(..., marks=...xfail)` passed the decorator-only
  pattern. The pattern is any `mark.skip` / `mark.xfail`, `skipif` included (the old
  pattern refused it too, as a prefix; a first version of this change let it through and
  Codex caught the loosening on #476). A runtime `pytest.skip(...)` is the allowed form.
- **`noqa` in any case.** Ruff honours a line's `# NOQA` (measured), so the two `noqa`
  rules match it in any case; `# ruff: noqa` is honoured only in lower case.
- **The script header** said "no AST, no dependency-graph tool"; it now says it is the
  text half of `make layer_check`.

`layer_check`: 142 -> 154 rules + 6 contracts.

## Findings

- **F1. Three web-retrieval adapters import from `model_adapters`.** The AST
  import graph at `5d545eb` finds, beyond the four expected importers:
  `infrastructure/web_retrieval_live.py:53` and
  `infrastructure/web_retrieval_brave.py:61` (`live_transport._certificate_refused`),
  `infrastructure/web_retrieval_brave.py:62` (`transport.CredentialSource`),
  `infrastructure/common_crawl.py:211` (`live_transport._certificate_refused`) and
  `infrastructure/common_crawl.py:328` (`bedrock.SigningUnavailable`). They borrow
  TLS-refusal, credential and signing helpers, not a model call, but the contract
  as specified would fail on them. Reproduction: the AST walk in the PR
  description. Smallest fix, for a decision: move the shared helpers out of
  `model_adapters` into a neutral infrastructure module (for example
  `infrastructure/http_transport.py`), then write the contract with no exemption.
- **F2. `application/model_gateway.py` imports nothing from `model_adapters`.**
  It receives adapters through its protocol (`model_gateway.py:39-77 @ 5d545eb`).
  Listing it in the contract's allowed importers would grant an allowance it does
  not use.
- **F3. CI does not run `make layer_check`.** Both CI jobs run
  `./tools/layer_check.sh` directly (`.github/workflows/ci.yml:87`, `:151 @
  5d545eb`), so a `lint-imports` step added only to the Makefile target would not
  run in CI. Chunk 1 needs the backend job's step to become `make layer_check` (or
  a step of its own); the docs-only job installs nothing and keeps the script.
- **F4. ARCHITECTURE.md is a shared file** (CLAUDE.md §1): the two grep rules'
  rows in §3 go under Doc follow-up, not into the feature PR.
- **F5. A forbidden contract whose source contains the forbidden package reports
  nothing.** With `aia_core.infrastructure` as a source, an added
  `from aia_core.infrastructure.model_adapters.transport import HttpRequest` in
  `web_retrieval_live.py` raised the graph from 1667 to 1668 dependencies and the
  contract stayed KEPT. `aia_core.infrastructure.*` reports it; that wildcard leaves
  out `aia_core/__init__.py` and `aia_core/infrastructure/__init__.py`, now a grep
  rule. Belongs in AGENTS.md (below).
  *Not the 2.12 overlap limitation.* Codex's later finding (the minimum raised to
  2.12, `packages/aia_core/pyproject.toml`) looked like the same problem, so the
  plain source was re-tested with the same probe: still `1 kept, 0 broken` under
  import-linter 2.12 and 2.15 (clean venvs, 2026-10-15), and an
  `infrastructure/__init__.py` import of `.model_adapters` is missed too. 2.12 made
  the overlapping configuration *valid* (2.11 rejects even the clean tree:
  `0 kept, 1 broken`, flagging model_adapters' own imports); it did not make an
  import from the source package into its own descendant *visible*. The likely
  mechanism (hypothesis, not read in import-linter's source): an import between
  two modules of the same source package is treated as internal to that source.
  The wildcard and the `__init__` grep rule stay.
- **F6. A docs-only PR cannot change what lint-imports or the grep rules read.**
  The `changes` job (`.github/workflows/ci.yml:62-66 @ 5d545eb`) sets `code=false`
  only when every changed path matches `.planning/*`, `docs/architecture/adr/*`,
  `CLAUDE.md`, `AGENTS.md` or `ARCHITECTURE.md`. A `case` `*` crosses `/`, so such a
  PR *can* carry a `.py` file -- one exists,
  `.planning/evidence/client-knowledge-review/test_client_knowledge_review_probe.py`
  -- but only under `.planning/` or `docs/architecture/adr/`, outside every
  import-linter root package and every layer_check rule path. `pyproject.toml`
  (where the contract lives) is not on the list, so changing it runs Backend. A push
  to `develop` always runs everything.

- **F7. A dynamic import is invisible to both the grep rules and import-linter.**
  Two exist in source (AST walk, `c032cf72`): `domain/methodology/resolution.py:145`
  (`importlib.import_module` of a declared function's module) and
  `aia_worker/registry.py:32` (the `AIA_WORKER_EXECUTORS` loader, by design). Named in
  the contracts' comments; nothing enforces them.
- **F8. A warm `.mypy_cache` reused across a branch switch or merge reports errors CI
  does not; the interpreter is not the cause.** Reproduced on 3.12 alone (mypy 1.20.2,
  pydantic 2.14.1, 2026-10-16): warm the cache on `0678c398`, check `da826d80` with it,
  and `domain/ai_respondent.py:494,505,516` report three `create_model` arg-type errors
  on every later run; a fresh cache, a warm cache on an unchanged tree, a 3.13 venv
  with a fresh cache and `--no-incremental` on the stale cache are all clean. #441
  blamed 3.13 (wrong). Fix: `make typecheck` runs `mypy --no-incremental`, CI's own
  check, ~45 s against 0.7 s warm (AiAnalytics-AIA/AIA#466).

## Doc follow-up

For the next docs-only PR:

- **ARCHITECTURE.md §3**, intro: "`make layer_check` runs two halves:
  `tools/layer_check.sh` (grep rules) and `lint-imports` (import contracts,
  `[tool.importlinter]` in `pyproject.toml`). CI's Backend job runs the target; the
  docs-only job runs the script alone."
- **ARCHITECTURE.md §3**, rule table, three rows:
  | only the executor compositions import the model adapters (import contract) | A second model-call path: an adapter driven without the gateway's retry, budget, egress and provenance (ADR 0005) |
  | only the AI runtime composition builds the model gateway | A gateway nobody configured: a route, policy or registry outside `ai_runtime.py`'s validated settings |
  | only the step's model caller invokes the model gateway | A model call with no reservation, no settle and no journal under the lease (`ai_step.py`, StepModelCaller) |
- **ARCHITECTURE.md §3**, exemptions bullet (from chunk 0): "An exempt path is
  the file's path from the repository root, never a basename; a rule whose path or
  exempt path does not exist fails rather than skipping."
- **CLAUDE.md §2 map**: `infrastructure/http_transport.py  What every outbound HTTP
  adapter shares: certificate_refused, CredentialSource, SigningUnavailable (model
  adapters and web routes alike; nothing outside the compositions imports
  model_adapters)`. §3 commands: "Layering | `make layer_check` (grep rules +
  `lint-imports`)".
- **AGENTS.md**, import-linter: WRONG `source_modules = ["aia_core.infrastructure"]`
  with `forbidden_modules = ["aia_core.infrastructure.model_adapters"]` -- KEPT
  with a violating import present (F5). RIGHT
  `source_modules = ["aia_core.infrastructure.*"]`, plus a check of the
  containing packages' `__init__` modules, which the wildcard leaves out.
- **ARCHITECTURE.md §3**, rule table, three rows (chunk 4):
  | the core's layers: application above infrastructure above domain (import contract) | A domain that reaches infrastructure, or infrastructure that reaches application, by any import form (the grep rule it replaced missed `from ...` and `import a.b`) |
  | the API, the worker and the executors are independent but for the executor seam | A worker that loads a step, an executor that drives the loop, or anything of the API outside the API |
  | routers reach infrastructure only through the application layer (ratchet) | A route that queries or stores where the application layer never sees it; today's nine routers listed edge by edge, leaving when next touched |
- **ARCHITECTURE.md §3**: drop the rows for "domain does not import outward", "the
  worker never imports the API" and "executors never import the API", if present (the
  contracts above replace them).
- **CLAUDE.md §2 map**: `application/errors.py  The infrastructure errors a router
  catches, re-exported (the same classes) so routers need not import infrastructure`.
- **AGENTS.md**, mypy: the cache trap of F8 -- carried by AiAnalytics-AIA/AIA#466's Doc
  follow-up (wrong: trust a warm cache after a branch switch; right: `--no-incremental`).
- **ARCHITECTURE.md §3**, rule table, one row (chunk 5):
  | the application reaches the tables only through a repository (import contract, ratchet) | A use case that queries a table itself and drops the isolation predicate its repository carries; today's three modules listed, leaving with chunks 6 and 7 |
- **ARCHITECTURE.md §2**, the two places the prose disagrees with the table and
  with the contracts:
  - Replace "Each layer calls the layer directly below." with "Each layer depends
    only on the layers its row names, and every dependency points toward the
    domain; `make layer_check` holds the rows (§3)." The table itself has
    application -> infrastructure (2 -> 3) and workers, executors and transport
    each reaching 1, 2 and 3, none of which is "directly below".
  - Transport's "May depend on" cell, "1, 2, 3 — through `dependencies.py` only",
    becomes "1, 2; 3 only in the composition root (`dependencies.py`, `main.py`).
    Routers that import infrastructure today are a ratchet in `pyproject.toml`
    and leave it when next touched". Routers import application and domain
    directly throughout (none goes through `dependencies.py` for them), and nine
    routers import infrastructure (the ratchet's 27 edges).
  - Application's "Owns" cell, after "Orchestrates domain + infrastructure.":
    "Reaches rows only through a repository (chunk 5's contract)."
- **ARCHITECTURE.md:90** (chunk 8): "a grep-level checker with no toolchain of its own"
  becomes "`tools/layer_check.sh` holds the text rules (names and patterns, nothing to
  install); the import contracts in the root `pyproject.toml` hold which module may
  import which". **ARCHITECTURE.md:94**: "Run it before every commit" becomes "Run
  `make layer_check` before every commit (`make verify` runs it with `ruff check`)".
- **ARCHITECTURE.md §3**, rule table, two rows (chunk 8):
  | the bans are never suppressed inline: no `# noqa: TID251`, bare `# noqa` or code-less `# ruff: noqa` in a source tree | A ban lifted in one line of a large diff instead of by a named exemption in `pyproject.toml` |
  | no static skip or xfail, however the marker is written (`pytestmark`, an alias, `from pytest import mark`) | The same signal deleted by a spelling the decorator-only rule did not see |
  and in the "Exemptions are named" bullet: "a ruff per-file-ignore that names no path
  fails (`test_ruff_config.py`); the tests' TID251 exemption names its four trees."
- **CLAUDE.md §10**: add `ruff check packages/aia_core apps/api apps/worker
  apps/executors migrations` to the command list, before `ruff format --check`
  (`make verify` runs it since chunk 8).

