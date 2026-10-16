---
status: in-progress
chunks:
  - "[x] 0. Make tools/layer_check.sh honest: a missing path fails, exemptions match by path from the root, a self-test"
  - "[x] 1. Close the second model-call path: the web routes' helpers out of model_adapters; an import-linter contract on model_adapters; grep rules for GovernedModelGateway( and the gateway's .invoke("
  - "[x] 2. Fence network egress to the transport modules: ruff TID251 banned-api, one root ruff configuration, an import contract keeping live wires out of the deep-research steps"
  - "[x] 3. Pin what a worker that outlived its lease can still write (B completes, then A writes)"
  - "[ ] 4. Not recorded in this file yet: the chunks after 3 come from the exploration report and are written here when they are taken up"
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
  ignore, `aia_api/routers/deep_research.py:69` (`MIN_SCAN_CUTOFF_BYTES`).

## Chunk 3 — what a stale worker can still write (done, #443)

`apps/worker/tests/test_stale_lease_artifacts.py` (PostgreSQL) pins:
`test_a_stale_worker_is_refused_before_it_reaches_the_store`,
`test_a_put_inside_the_fence_holds_off_recovery_and_a_failed_block_orphans_its_object` (the
orphan is OI-114) and
`test_an_artifact_committed_before_the_lease_lapsed_is_reused_by_the_successor`.

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
