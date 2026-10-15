---
status: in-progress
chunks:
  - "[x] 0. Make tools/layer_check.sh honest: a missing path fails, exemptions match by path from the root, a self-test"
  - "[ ] 1. Close the second model-call path: import-linter contract on model_adapters, grep rules for GovernedModelGateway( and gateway .invoke( (blocked: see Findings F1, F2)"
  - "[ ] 2. Not recorded in this file yet: the chunks after 1 come from the exploration report and are written here when they are taken up"
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
- 111 rules pass before and after. (The exploration report counted 131; the
  script at `5d545eb` runs 111 `forbid` calls, including the three in the
  dataset-connector loop.)

## Chunk 1 — close the second model-call path (blocked)

Planned: import-linter as a dev dependency, `lint-imports` in `make layer_check`,
one forbidden contract allowing only `aia_core.application.model_gateway`,
`aia_executors.ai_runtime`, `aia_executors.deep_research_live` and
`aia_executors.deep_research_runtime` (plus `model_adapters` itself) to import
`aia_core.infrastructure.model_adapters`; grep rules `GovernedModelGateway(` only
in `ai_runtime.py` and gateway `.invoke(` only in `ai_step.py`.

Stopped before writing code, on F1 and F2. The decision is the owner's.

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
