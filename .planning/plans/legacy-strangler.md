# Legacy strangler — 18.6.6 as the AIA product, behind the running oracle

**Status:** in progress · **Owner:** parity-quality + api (slice 1); one owner per
slice below · **Started:** 2026-09-23

Decision: [ADR 0011](../../docs/architecture/adr/0011-vendor-legacy-product-unit.md).
The working NPC Panel 18.6.6 product is the canonical baseline. AIA delivers
what it shows and computes, restructured onto AIA's layers, PostgreSQL, S3,
Cognito and the develop host, by replacing one capability at a time behind the
running unit (`legacy-panel`, the **oracle**) and retiring each legacy path only
after a differential test against the oracle passes for it.

## Problem

After five phases the deployed rebuild does not resemble the product: 19 of 136
HTTP paths are ported, the client is mock-backed, and the 88 research functions
in `ui_app.html` have no server-side home except the Sociomap slice already
ported from fixtures F5–F9. Parity is measured against committed fixtures only;
nothing compares AIA with the *running* product, and nothing says, route by route
and function by function, which of the 162 routes and 88 functions AIA already
serves, which the oracle still serves, and which are retired by decision.

## Approach

**Strangle behind the oracle, one thin vertical slice per PR.** Each slice
carries: the parity tests for its capability ids, the port (domain → application
→ route/executor → screen, reusing what AIA has), the documents, green CI, and
the ledger rows moved. Observable behaviour changes only by a recorded decision;
the one pre-approved class is fail-closed replacing silent substitution
(reference R1–R4, R11, R16, R17).

Two ledgers make the strangling visible and testable:

- **The route ledger** `docs/migration/legacy-route-ledger.json` — one row per
  unique verb + path of the reference's 162 dispatch arms (153 unique; six paths
  have two arms), with the reference capability id, the family, the AIA status
  (`LEGACY` served by the oracle only · `PORTING` an AIA route exists, parity
  not yet `PASS` · `PORTED` parity `PASS`, legacy path retired for it · `RETIRED`
  no production equivalent by a recorded decision), the AIA route when one
  exists, and the scope decision (D8: every ported route's scope is *decided*,
  never inferred). A test keeps it covering exactly the reference's ledger, and
  an API test proves every `PORTING`/`PORTED` row's AIA route is in the OpenAPI
  document.
- **The UI function ledger** `docs/migration/legacy-ui-functions.json` — the
  88 `METHODOLOGY_SEMANTICS` and `DETERMINISTIC_COMPUTATION` functions of
  `ui_app.html`, each with the SHA256 of its extracted source in the vendored
  unit, its product area, its status (`LEGACY` · `PORTING` · `PORTED`) and its
  AIA implementation anchor and fixture ids once ported. The extraction
  (`tools/ui_functions.py`) uses the reference's brace-matching algorithm, and a
  test asserts it finds the same 737 functions the reference ledger counts.

Two harnesses produce the evidence:

- **HTTP-level** (`tools/legacy_oracle.py`, stdlib): `probe` the oracle;
  `record` request/response pairs from it on the seeded fictional demo into
  `packages/aia_core/tests/fixtures/legacy_http/`; `compare` a recorded pair
  with a live response field by field under a declared tolerance and a list of
  volatile fields (timestamps, ids) that are compared by *shape*. The oracle is
  reached only through `AIA_LEGACY_REFERENCE_URL` plus
  `AIA_LEGACY_REFERENCE_USER` / `AIA_LEGACY_REFERENCE_PASSWORD` from the
  environment (the Caddy basic-auth gate); tests marked `oracle` skip cleanly
  when the URL is unset and fail when `AIA_REQUIRE_LEGACY_ORACLE=1`, the same
  ratchet as `AIA_REQUIRE_POSTGRES`. Credentials are never committed.
- **Function-level** (`tools/ui_functions.py`, `tools/ui_function_runner.mjs`,
  `tools/ui_function_capture.py`): the functions are extracted verbatim from the
  vendored `ui_app.html` (byte-identical to the archive, so this *is* the
  reference), executed under Node in a `vm` sandbox with only the helper
  closure they need, on authored input cases, and the outputs are written as
  fixtures in the reference's fixture shape under
  `packages/aia_core/tests/fixtures/legacy_ui/`, pinned by SHA256 in its
  `index.json` together with the SHA256 of the function source they were
  captured from. A fixture whose function source changes is *known* stale.

Both feed `tools/parity_status.py`: unit-captured fixtures are a new fixture
source `legacy_unit` (they need nothing but the repository), oracle gates carry
the new requirement `legacy_oracle`, and CI's `parity-status` job reports each
as `PASS` / `FAIL` / `NOT_EXECUTED` / `NOT_RUNNABLE` beside the existing gates.

### Rejected

- **Porting before the harness.** The whole point of ADR 0011 is a running
  system to check against; a port with no differential test is the rebuild from
  prose that ADR 0011 stopped.
- **Editing the unit to make it testable** (a CORS header, a JSON `Accept`).
  The unit is regenerated, never edited; the harness rewrites nothing and
  reaches the oracle exactly as a browser behind the gate does.
- **Reinventing terrain or the layouts from their descriptions.** The 88
  functions are ported *from the JavaScript*, with fixtures captured from that
  JavaScript first, so the port is checked against the source it replaces.
- **A parity fixture directory named after the data it holds.**
  `exposure_check` rule 2c refuses dataset nouns in `.json` names; fixture ids
  therefore name the *function*, never the data (`AGENTS.md` § pytest).

## Trade-off accepted

Until an operator provisions `AIA_LEGACY_REFERENCE_*` as CI secrets (or runs the
oracle suite from a machine that can reach the develop host), every oracle gate
reports `NOT_EXECUTED`; the function-level harness runs everywhere because the
oracle's own bytes are in the repository, so slice 1 ships real parity evidence
for the frontend mathematics and only the *contract* for the HTTP oracle.

## Phase 0 — the oracle, as found on 2026-09-23

| Check | Result | Anchor |
| --- | --- | --- |
| CI green on `develop` at the unit commit | **yes** — run 108 (`35882425631`) `success` @ `09810d1` | GitHub Actions `ci.yml`, branch `develop` |
| `legacy-panel` deployed and healthy | **not yet** — *Deploy develop* run 6 (`35880744530`) @ `71d3576` failed at *Build and push aia-legacy-panel*: `unable to prepare context: path "legacy/npc-panel-18.6.6" not found`. That SHA is PR #38 (the integration) merged *before* PR #39 (the unit's files); `git ls-tree 71d3576 -- legacy` holds only `legacy/README.md`. Run 7 (`35883107082`) @ `09810d1`, which has the unit, has been `waiting` on the `develop` environment since 15:39 UTC — a human approval or protection rule, not a code defect | `.github/workflows/deploy-develop.yml:128-141 @ 09810d1`; OI-39 |
| Data bundle synced (`AIA_LEGACY_DATA_PREFIX`) | **unverifiable from here** — happens in `bin/deploy.sh` on the host during run 7 | `deploy/develop/bin/deploy.sh:39-48 @ 09810d1` |
| Anonymous request refused (401) | **unverifiable from here** — the develop hostnames are denied by the cloud session's egress policy (`connect_rejected`), and no Docker daemon is available to build the unit locally. The check exists as `bin/smoke.sh` on the host and as `test_legacy_oracle.py::test_anonymous_request_is_refused` here, for any environment that can reach the oracle | `deploy/develop/bin/smoke.sh:44-50 @ 09810d1`; OI-39 |
| Oracle endpoint contract for parity tests | **landed in slice 1** — `AIA_LEGACY_REFERENCE_URL` (+ user/password), `legacy_oracle` fixture, `oracle` marker, `make test-oracle` | `packages/aia_core/tests/conftest.py` `legacy_oracle`; `tools/legacy_oracle.py` |

## Slice order

Dependency order from the reference's `dependency-map.md` (load-bearing modules
first: `runtime_config`, `edition_config`, `project_store`, `job_store`,
`prototype_server.load_panel_cached`) and the family table in
`rebuild-contract.md`. Capability ids are the reference's (`capability-map.md`);
route counts are from `api-ledger.json`; function counts from
`ui-capability-ledger.md`. **Done** for every slice means: its parity rows are
`PASS` from *executed* gates, its ledger rows moved, the documents changed in
the same PR, CI green, and — for a retired legacy path — the oracle no longer
the only server of that capability.

| # | Slice | Capability ids | Routes / functions | Parity gate | Owner |
| --- | --- | --- | --- | --- | --- |
| 1 | **Prove the oracle; build both harnesses** (this PR) | `api.http` (ledger only), `sociomapping.core` (harness proven on `normalizer66`, `objectMetricArray66` with fresh inputs) | route ledger 153/153; UI ledger 88/88; first unit-captured fixtures | function-level fixtures gated against `aia_core.domain.sociomap`; oracle gate `NOT_EXECUTED` until credentials exist | parity-quality + api |
| 2 | **Platform reads** | `config.edition` (R17 → fail closed), `config.environment`, `operability.integrity`, `ai.provider_parity`, `api.http` | `GET /health`, `GET /api/bootstrap`, `GET /api/providers/parity/status`, `GET /api/providers/claude-code/status`, `GET /api/command-center` | HTTP differential on the oracle (`SEMANTIC`, volatile fields masked); production tests for the two intentional differences | platform |
| 3 | **Projects** onto AIA's study-scoped project model | `project.persistence`, `project.memory`, `pipeline.stages` | 13 `/api/projects*` + 4 `/api/project/*` + `GET /api/history` | HTTP differential on the seeded fictional demo (D4 default set); `pipeline.stages` stays `EXACT` | project |
| 4 | **Workflows and jobs** onto `WorkflowRun/StepRun/StepAttempt` | `workflow.engine`, `workflow.step_execution`, `workflow.config` (`COST_MODES` `EXACT`), `workflow.dispatch`, `workflow.legacy_dispatch` | 6 `/api/workflows*`, 6 `/api/jobs*`, 2 `/api/approvals*`, 4 `/api/schedules*` | HTTP differential + the 24-node DAG shape `EXACT` | workflow |
| 5 | **Demo library** | `data_library.demos` (R15: no AI on open) | `GET /api/demos`, `POST /api/demos/copy` | `EXACT` on the demo registry and the seeded project shape; **D4 decides which demos** (default: the ten fictional showcase demos) | data-library |
| 6 | **Population and audience** through `PopulationRuntime` | `population.core`, `population.panel_loader`, `population.weighting`, `population.readiness`, `audience.definition`, `audience.segments` | `GET /api/panel_values`, 3 `/api/audience*`, 5 `/api/audiences*`, `GET /api/populations`, `POST /api/segment/preview` | F10/F11 (already gated) + HTTP differential; `audience.segments` `NUMERICAL` 1e-9; **D3 (licence) decides storage** | population-data + audience |
| 7 | **Sociomapping server-side** — the 35 research functions of the `sociomapping` area, terrain ported *from the JavaScript* | `sociomapping.core`, `sociomapping.study_module` | 8 `/api/visualization*`, 2 `/api/study*`; functions `terrain66`, `terrainData1865`, `renderTerrain1796`, `draw66`, `projection66`, `baseObjectLayout66`, `forceLayout27`, … | unit-captured fixtures at 1e-9 for every pure function; F1–F9; **D6 decides the generation** where several ship | A8 sociomapa-deterministic |
| 8 | **Questionnaire and research, deterministic parts first** | `questionnaire.instruments` (`EXACT`), `questionnaire.conditionals` (1e-9), `questionnaire.engine`, `research.design` | `GET /api/instruments`, 4 `/api/questionnaire*`, 6 `/api/research*`, `POST /api/navrh`, `POST /api/preflight` | HTTP differential for the deterministic routes; AI-backed routes need the governed `ModelGateway` live transport (D6/D7/D8 in PROGRESS) and a **recorded decision before any live-AI run on the oracle** | research |
| 9 | **Results, analysis, statistics, governance** | `results.registry`, `results.verification`, `results.dialogue`, `analysis.qc`, `statistics.*`, `governance.validation_state`, `governance.evidence_audit`, `governance.legal`, `governance.anchors` | 3 `/api/results*`, 2 `/api/results-registry*`, `GET /api/validation`, 5 `/api/persona*` | `NUMERICAL` 1e-9 via unit/oracle fixtures; gate decisions `EXACT` | analysis + governance |
| 10 | **Simulation** onto the deterministic core | `simulation.engine`, `simulation.scenarios` | 10 `/api/fullsim*`, 6 `/api/scenario*`, 3 `/api/simulation/context*` | F13 when captured (OI-27); HTTP differential for the deterministic routes; reject-not-clip as intentional difference | A7 simulation-engine |
| 11 | **Data library ingestion** | `data_library.ingestion` (`EXACT` ordering), `data_library.ingest_subsystem`, `data_library.panel_tools` | 18 `/api/library*`, `POST /api/ingest`, 3 `/api/population/calibration*` | HTTP differential; leakage decision `EXACT` | data-library |
| 12 | **Reports** | `reports.generation` | `POST /api/projects/export`, `POST /api/results/final_report` | report *data* `EXACT`, prose `SEMANTIC`; **D5 decides the authoritative generation** | reporting |
| 13 | **AI runtime settings and assistants** | `ai.provider_diagnostics`, `ai.provider_setup`, `ai.credentials`, `research.copilot` | 4 `/api/settings*`, `POST /api/providers/claude-code/setup`, 2 `/api/assistant*`, `POST /api/copilot/chat`, `POST /api/discovery*` | intentional differences with production tests (Secrets Manager, no local keystore) | ai-runtime |
| 14 | **Second HTTP server's four routes and the static arms** | `population.panel_loader` (loader already ported), `operability.support` | `prototype_server.py` `GET /`, `/health`, `/files/`, `/cancel`; `ui_server` `/artifacts/`, `/brand/`, `/project-attachments/`, `/api/support*` | **D9 decides** retain or retire; until then `LEGACY` | platform |
| 15+ | **Frontend re-homing**, one product area per slice after its backend: `shell`, `project`, `workflow`, `data_library`, `audience`, `questionnaire`, `results`, `sociomapping`, `simulation`, `analysis`, `population`, `reports`, `ai_runtime`, `governance`, `settings` | the same ids, per area | 247 presentation + 291 orchestration functions restructured freely; the 88 research functions already server-side | screens look and behave the same (browser tests against both); `discoverBackend()`, the origin guard and build-suffixed ids dropped by decision | web |
| last | **Retire** `legacy-panel` by ADR when every row is `PASS` and every area is re-homed | — | — | — | data owner |

## Decisions not taken here (asked, not resolved in code)

Recorded in `.planning/open-items.md` / `PROGRESS.md` *Decisions needed*, with
the reference's ids: population licence and storage (D3), which demos ship (D4,
default the ten fictional showcase demos), authoritative report and Sociomapping
generation (D5, D6), the second server's four routes (D9), per-route
authorization (D8, decided per ported route and recorded in the route ledger),
any live-AI run on the oracle (a provider credential through the governed
`ModelGateway`, ADR 0005), real-client identifiers inside code (D-L1).

## Chunks — slice 1

- [x] 0. This plan.
- [x] 1. **Oracle endpoint contract** — `AIA_LEGACY_REFERENCE_URL` /
      `_USER` / `_PASSWORD`; `legacy_oracle` session fixture (skip when unset,
      fail under `AIA_REQUIRE_LEGACY_ORACLE=1`); `oracle` marker in both
      `pyproject.toml`; `make test-oracle`; `.env.example`; first oracle tests
      (`/health` shape and release, anonymous 401) — lands: `conftest.py`,
      `tools/legacy_oracle.py`, `test_legacy_oracle.py`.
- [x] 2. **HTTP harness** — `tools/legacy_oracle.py` `probe` / `record` /
      `compare` with tolerances and volatile-field masks; offline tests of the
      comparer and of `record` against a local stub server — lands:
      `test_legacy_oracle.py`.
- [x] 3. **Route ledger** — `docs/migration/legacy-route-ledger.json`, 153
      rows; coverage test against the reference `api-ledger.json` (pinned by
      SHA256, needs `reference_repo`) and self-consistency without it; API test
      that every `PORTING` row names a route in the OpenAPI document — lands:
      `test_legacy_route_ledger.py` (core), `test_legacy_route_claims.py` (API).
- [x] 4. **UI function extraction and ledger** — `tools/ui_functions.py`
      (737 functions, per-function SHA256); `docs/migration/legacy-ui-functions.json`
      (88 rows); tests: count agrees with the reference ledger, every ledger row
      is found and hashes as recorded — lands: `test_legacy_ui_functions.py`.
- [x] 5. **Node runner and first fixtures** — `tools/ui_function_runner.mjs`,
      `tools/ui_function_capture.py`; cases and fixtures for `normalizer66` and
      `objectMetricArray66` with inputs the reference did not use, gated against
      `build_normalizer` / `object_metric`; captures for the pure unported
      functions (`computeDirectedMatrix1798`, `buildFullMatrix1797`,
      `layoutFromMatrix1797`, `layoutStatic1798`, `forceLayout27`,
      `keyInsights`, `workflowStepLabel`, `sampleRecommendation1785`) awaiting
      their port; `index.json` pins — lands: fixtures, `test_legacy_ui_functions.py`.
- [ ] 6. **Matrix, CI and documents** — `legacy_unit` fixture source and
      `legacy_oracle` requirement in `parity-matrix.json` and its tests; new
      gate on `sociomapping.core`; CI `oracle-parity` job (secrets-gated, JUnit
      into `parity-status`); `CLAUDE.md` map and commands, `ARCHITECTURE.md`
      CI tier, `parity-matrix.md` rules, `PROGRESS.md`, OI-39.

## Review outcome

Filled in when the plan is archived.
