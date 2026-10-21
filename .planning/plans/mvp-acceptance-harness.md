---
status: in-progress
chunks:
  - "[ ] 1. The USD 25 allocation: a ceiling per category, summed and checked before any recorded run, covering fieldwork, analysis and its repairs, the Lead's turns, Deep Research search and tool spend and the second (Interpretation) run, a retry round; the evaluation allowance stated apart"
  - "[ ] 2. The study's fixed inputs, fictional and committed: brief, client document, dataset with one personal column, a web page, a past study"
  - "[x] 3. The harness: tests/acceptance driven over HTTP, reusing the scripted-provider fixture of test_product_acceptance.py, and its CI step (collected, writing JUnit)"
  - "[ ] 4. Recorded doubles behind the gateway and the retrieval gate for the Lead, every worker, respondents, analysis and Deep Research"
  - "[ ] 5. Criteria wired one by one as each becomes runnable, the built ones first (AC-01, 06, 07, 12, 14)"
  - "[ ] 6. The acceptance record: one PASS/FAIL line per criterion, stored as an artifact, with the parity report beside it"
  - "[ ] 7. Tier B: the live run on develop, its runbook and its record"
  - "[ ] 8. Parity reports, never blocks (owner, 2026-10-19): the 18.6.6 comparison jobs stop gating merges and deploys and report in the step summary and the record"
  - "[x] 9. The `acceptance` marker registered (`pyproject.toml` runs `--strict-markers`) and the tree collected by CI"
  - "[ ] 10. Browser evidence kept distinct from HTTP evidence: real browser journeys (hand edits, pointing, proposals, keyboard and focus, stale states, all eleven stages, map view-only operations) are their own line in the record and never counted as HTTP"
  - "[ ] 11. The Deep Research evaluations 25, 26 and 39 before the final live chunk 27, and the second live Interpretation run, are in the tier B record and its allocation"
  - "[ ] 12. Production release is a blocker: the record states I-5 as not passed until the production release checklist is done, whatever tier B showed on develop"
  - "[ ] 13. Every prototype scenario (A to M, X1 to X7) is an acceptance journey on recorded doubles; X2 (missing evidence) and X6 (a methodology change refused) stay as negative cases"
  - "[ ] 15. The assumptions and open-answer coding journey (W5, MVPQ-02) with its refusals, over recorded doubles: `assumptions-and-open-answer-coding#AOC9`"
  - "[ ] 14. The acceptance wording reconciled in the acceptance document and `parity-matrix.json` together, in a PR that runs the tests: AC-02 (approval card and plan), AC-11 (OPEN posture), AC-13 (F17), AC-15 (separate model, tool, reservation, uncertain and billing-lag lines; the USD 0.01 tolerance kept unless the owner changes it)"
  - "[ ] 16. The per-number provenance walk for AC-15: every ledger ref of both reports resolves to its model binding, prompt pin, population version and weight role (G65)"
  - "[ ] 18. Performance budgets as a release gate: page and API latency budgets per journey (D-48; the numbers are open)"
---
# The MVP acceptance harness

Track A of the MVP roadmap (`overview.md` § MVP roadmap, #493). Written 2026-10-19 from
`docs/migration/mvp-acceptance.md` (`MVP-ACCEPT-2`, #495) and `mvp-cohesion.md` F7 and F10 (#496).
**Owner: a chat session, named when chunk 1 starts.** This plan builds the test the document
defines; the document stays the definition.

**Depends on [#495](https://github.com/AiAnalytics-AIA/AIA/pull/495) merging first.** The
criterion ids below are `MVP-ACCEPT-2`'s. The checked-in `MVP-ACCEPT-1` numbers them differently
(its AC-07 is the worker kill and its AC-12 is configuration; its AC-14 is the parity gate that
MVP-21 removes), so this plan is wrong against `develop` until #495 lands.

## What the document defines (not repeated here)

Fifteen criteria; two tiers, both required for release: **A** in CI over HTTP on recorded doubles
behind the gateway and the retrieval gate, blocking once runnable; **B** a live run on develop
within USD 25 by a person. Every fixed input is committed with the test. No back door: no
repository, domain function or table is touched directly.

## What exists

- A walk of product scenarios over HTTP with the real worker, the stored report and a scripted
  Bedrock (`scripted_bedrock`): `apps/executors/tests/test_product_acceptance.py` (PC11), plus
  `apps/executors/tests/test_sociomap_acceptance.py`. **Extend their fixtures; do not build a
  second scripted provider.**
- Recorded retrieval doubles exist only in `aia_executors/deep_research_recorded.py`, local and
  test (`ARCHITECTURE.md` §3); `test_deep_research_journey.py` drives them.
- `parity_status.py` reports `MVP-ACCEPT-2` as `NOT_RUNNABLE` until the file exists
  (`mvp-acceptance.md` §5, #495).

## Chunks

1. **Budget.** A table, in this plan, of each category's ceiling against the USD 25 of MVP-20:
   fieldwork (`domain/run_cost.py`, an upper bound, n = 300), analysis with repairs, the Lead's
   turns and each worker, live Deep Research (its own pinned allowance, ADR 0022), the report
   writer and map interpreter. **`run_cost.py` covers fieldwork and analysis only** (hypothesis from
   the CLAUDE.md map; confirm in the chunk), so the other lines need their own bound. If the sum
   exceeds 25, the owner chooses a smaller n or a larger budget now, not after tier B.
2. **Inputs.** The brief and the five fictitious concepts from `mvp-acceptance.md` §1; a fictional
   annual summary, a fictional visits dataset with one personal column the contract must drop, one
   public page, one past fictional study; all pinned by SHA-256 like the golden fixtures. No client
   data, no client names (`tools/exposure_check.sh` must pass).
3. **Harness and its CI step.** `tests/acceptance/test_mvp_acceptance.py`, marked `acceptance`,
   never runtime-skipped as a placeholder. Decide here whether it shares `conftest` fixtures with
   the executors' tests or has its own; either way one provider double. **No CI command collects
   `tests/acceptance` today**: the collect-only pass and every pytest step name only
   `packages/aia_core`, `apps/api`, `apps/worker` and `apps/executors`
   (`.github/workflows/ci.yml:200, 208-251 @ 085abe0`), so a green CI would say nothing about it.
   This chunk adds the tree to the collect-only pass and gives it a step of its own that writes
   `--junit-xml … -o junit_family=xunit1`, which `parity_status.py` reads and
   `test_parity_matrix.py` requires of every pytest step (`AGENTS.md:248-251 @ 085abe0`). Test: a deliberately
   failing acceptance test turns CI red, and a skipped one reports `NOT_EXECUTED`, not green.
4. **Doubles.** One recorded exchange per model call kind and one per retrieval, deterministic,
   each stating that it is a recording, behind `GovernedModelGateway` and `RetrievalGate`, never
   around them.
5. **Wiring.** A criterion lands when its work does. The first batch exercises existing paths for AC-01 (scope, 404), AC-12 (project memory) and AC-14 (typed config). AC-06 requires RQC0's fieldwork checkpoint/kill proof and AC-07 requires WCE7's working-revision impact path; collecting older tests for them does not prove the stronger MVP obligations. Each later criterion arrives with the integration gate that makes it runnable
   (`mvp-cohesion.md` §4: I-1 to I-4).
6. **Record.** One line per criterion, `PASS` / `FAIL` with the observation that decided it, stored
   as an artifact of the study with the reports, approved map snapshots and their approval records,
   and the `parity_status.py` report from the same commit as information (MVP-21).
7. **Tier B.** The runbook for a person on develop: the live providers, the Class B route, the
   AWS-tagged spend check (`develop-spend-attribution`), the record. Run before every MVP release.

## Depends on / feeds

Chunks 1-3 can start now. Chunk 5 follows each track's gate (I-1 Lead drives a study, I-2 results
seen, I-3 evidence complete, I-4 Deep Research live). Chunk 7 needs `class-b-search-route` and
`develop-spend-attribution`. This plan ticks, from its single record, the "deploy and verify live"
chunks the consolidation lists (`mvp-consolidation.md` §4.3, #493).

## Chunk 1: the USD 25 allocation -- PROPOSAL, awaiting owner approval

**Status: PROPOSAL, awaiting owner approval.** Written 2026-10-21 for E01 (W0). The owner approved
spending up to USD 25 on Bedrock for live checks on fictional studies (Nigel Blount, 2026-10-20,
about 23:40 UTC, in the coordinator's session); that is the ceiling this table divides. **No paid
dispatch happens in the PR that adds it**, and none happens on it until the owner approves the
lines below: a paid probe or run names its line (E01). The same allocation is
`tests/acceptance/allocation.json` (`approved_by` null until then), which
`test_acceptance_harness.py` sums and holds equal to this table.

What enforces it. The system holds only the study's budget (each request reserved before it
leaves, `AWAITING_BUDGET` when it would not fit) and the spend-limit confirmation per start
(ADR 0019 gate 2). Nothing holds a line by itself: the tier B runbook (chunk 7) reads the usage
ledger after each dispatch and stops at a line's ceiling. In particular a Deep Research run is
not held by its approved run limit (Findings, F-2).

Prices: the route model at USD 3.30 / 16.50 per million input / output tokens (ADR 0010,
verified 2026-09-26); Brave at about USD 5 per 1,000 requests (the deployment's price is
configuration, not in the repository). "Measured" means a ledger figure exists; "assumed" is an
estimate to be replaced by the first measured run of its kind.

| Line | Category | Ceiling (USD) | Basis kind | Basis |
| --- | --- | ---: | --- | --- |
| A01 | `fieldwork` | 8.00 | measured | n 300 x 2 blocks (at most 16 items; MAX_BLOCK_ITEMS 8, domain/ai_respondent.py:111) = 600 requests at USD 0.013: USD 0.0115 measured per call on develop (20 calls, USD 0.2303301, docs/architecture/bedrock-develop-activation-2026-09-26.md) plus about 400 input tokens of a panel persona's profile. The ceiling a start shows (run_cost.py, 600 x the reservation) is far higher and is not spend. |
| A02 | `analysis_and_repairs` | 1.80 | assumed | 8 modules x (a draft and at most 2 repairs) = 24 calls at USD 0.075 (assumed: 12,000 input / 2,000 output tokens). |
| A03 | `lead_turns` | 2.60 | assumed | 20 Research Lead turns at USD 0.13 (assumed: 30,000 input / 1,500 output tokens at the route model's prices; a Lead model of its own replaces them). Each turn holds its reservation (Compose default USD 1.02) while it runs. |
| A04 | `design_workers` | 1.50 | assumed | 10 design-worker jobs (each available worker once, two rebuilds) at USD 0.15 (assumed: 10,000 input / 4,000 output tokens and one repair in three). |
| A05 | `report_writer_and_map_interpreter` | 0.60 | assumed | 4 calls at USD 0.15. These workers are not built (lead-orchestration LO9b); the line is re-set when their contracts land. |
| A06 | `deep_research_design_models` | 2.70 | assumed | One Design Research run's model calls. The plan's estimate for a Standard run is USD 5-7 (deep-research-web-search section 9), so at USD 2.70 the run is shallower than Standard (fewer tracks), or the owner takes option B. |
| A07 | `deep_research_interpretation_models` | 2.70 | assumed | The second (Interpretation Research) run behind the report's cited context (contextual_report.py), its model calls; as A06. |
| A08 | `deep_research_tools_and_search` | 0.60 | assumed | At most 120 Brave queries across both runs at about USD 5 per 1,000; public fetch and Wikipedia are fee-free; Common Crawl's priced index is not composed for the first live run. |
| A09 | `retry_round` | 1.80 | assumed | One analysis-only retry round (24 calls as A02) over the frozen dataset. A fieldwork restart is not covered: until run-qc-and-checkpoint RQC0 lands a restart repays fieldwork (OI-64), so AC-06's kill is proven in tier A, not paid for here. |
| A10 | `client_source_extraction` | 0.25 | assumed | Knowledge proposals from the fictional annual summary: one batch (BATCH_MAX_BYTES 24,000, domain/source_proposals.py). Charged to the client's budget, not the study's: the client's budget must be at least this. |
| A11 | `open_reservation_headroom` | 1.00 | assumed | Never spent: the holds of requests in flight when the study's spend nears its budget (reservation x concurrency). Without it the last requests park AWAITING_BUDGET. |
| A12 | `contingency` | 1.45 | assumed | Unallocated. A line that overruns draws on it only by a person's entry in the tier B record. |
| | **Total** | **25.00** | | the study's budget, MVP-20 |

The plan's hypothesis that `run_cost.py` covers fieldwork and analysis only is wrong in part: it
also bounds a Deep Research run (`deep_research_cost_ceiling`, `domain/run_cost.py:268 @
c88fd7fd`) and names a design job's reservation (`CeilingUnknown.RESEARCH_RESERVATION_MISSING`,
`:67`). No function bounds the Lead's turns or the report writer and map interpreter; their
lines above are this table's own bound.

**The sum exceeds 25 at the plan's own Deep Research estimate**, so the owner chooses now (chunk
1), not after tier B:

- **A (proposed above):** n 300 and both Deep Research runs held to USD 2.70 of model calls
  each, shallower than the Standard preset (fewer tracks).
- **B:** Deep Research at its Standard estimate (A06 and A07 USD 6.00 each): about USD 31.60, so
  a USD 32 budget.
- **C:** n 200 (A01 USD 5.20), freeing USD 2.80 for the Deep Research lines.

**Outside the budget, stated apart (the evaluation allowance).** The Deep Research evaluations
run before the live acceptance run 27 (`deep-research-web-search`, "Evaluations before the
final live run") and spend outside tier B's USD 25. At the plan's own estimates they cost far
more than anything approved so far (Findings, F-3); each needs its own approval and scope.

| Line | Category | Estimate (USD) | Basis |
| --- | --- | --- | --- |
| E25 | `evaluation_accuracy` | 15.00-65.00 | deep-research-web-search 25: 50 public Czech facts, a single-fact run each at Standard (about USD 0.30) and at Deep (about USD 1.00). |
| E26 | `evaluation_quality` | 1,740.00-2,780.00 | deep-research-web-search 26: 20 questions x 3 arms at Standard (USD 300-420), then Deep against Exhaustive on the 20 (USD 1,440-2,360), from the plan's section 9 estimates; the judge model's cost is unknown and not in the range. |
| E39 | `evaluation_extraction` | 48.00-72.00 | deep-research-web-search 39: about 4 catalogue runs at Deep (USD 12-18 each). |
| E50 | `evaluation_commercial_arm` | unknown | deep-research-web-search 50: a person runs Gemini Deep Research through Google's own interface; it spends nothing on AIA's ledger and its subscription cost is unknown. |

## W0 delivery (E01), 2026-10-21

Branch `feature/w0-acceptance-harness`, from `develop` @ `c88fd7fd`.

- **Chunk 9 (done).** `acceptance` registered in the root `pyproject.toml` beside `--strict-markers`;
  every module of the tree carries `pytestmark = pytest.mark.acceptance`
  (`test_acceptance_harness.py::test_every_test_module_here_is_marked_acceptance`); a misspelt
  marker stops the step (`test_acceptance_wiring.py::test_a_misspelt_marker_stops_the_step`).
- **Chunk 3 (done).** `tests/acceptance/`: `conftest.py` starts the stack (PostgreSQL named by
  `AIA_ACCEPTANCE_DATABASE_URL`; `uvicorn aia_api.main:app` and `python -m aia_worker` as processes
  of their own) after one declared bootstrap (`alembic upgrade head`, then `aia_executors.seed`:
  no route creates an organization or its owner, G76), kept on the stack for the record (chunk 6).
  Tier A has no SQLite variant: the migrations do not run on SQLite (AGENTS follow-up below), and
  production has none. CI: the collect-only step names the tree, and "MVP acceptance, tier A"
  runs it on a database of its own, writing `tmp/junit/acceptance.xml` (xunit1), with no escape;
  `parity_status.py` gives each criterion a tier-A verdict from the tests it lists
  (`mvp_acceptance.criteria[].tests`), the acceptance verdict the worst of them, path parity beside
  it and never in it (G75), and fails on a criterion FAIL; `acceptance` in `--available` makes a
  listed test that did not run a FAIL. The deliberately failing test is real
  (`test_acceptance_wiring.py::test_a_deliberately_failing_acceptance_test_fails_the_step_and_its_criterion`):
  run as the step runs it, it exits 1 and fails its criterion, and a skipped one is NOT_EXECUTED,
  or FAIL where the step ran. The `project.memory` row is PARTIAL with its anchors (G75).
  **Deviation, stated:** G76 asked for an import-linter contract; import-linter reads packages and
  `tests/acceptance` is not one (test trees are not packages, `AGENTS.md` § pytest), so the rule
  is an AST test over every import form (`test_the_tree_imports_nothing_it_drives`) and a grep
  rule in `tools/layer_check.sh`.
- **Chunk 4 (in part).** One recorded wire, `aia_executors/recorded_models.py`
  (`RecordedModels`), behind the real gateway: the respondent, analysis and Lead contracts, every
  answer `recorded-<kind>-<n>` with `x-aia-recording`; any other contract refused by name with an
  answered, unbilled 400, never invented. It replaces `apps/executors/tests/scripted_bedrock.py`
  (the analysis and product-acceptance suites use it unchanged), and the Lead suite proves it on a
  turn. `aia_executors/acceptance_recorded.py` is the harness's worker: production's composition
  (`registry.compose_registry`, now the one composition with the wire injectable) over the recorded
  wire, refused outside local and test and with Deep Research on; no deployment may name either
  module (`make layer_check`). Proven over HTTP: a run's 200 respondents and its analysis calls
  are all recorded, and the study's spend equals the recordings' usage at test prices to USD 1e-4
  (`test_a_run_is_answered_by_recorded_models_behind_the_gateway`). **Left:** the eight design
  workers (`aia_research_<action>`), the client-source extraction
  (`aia_knowledge_source_proposals`), the five Deep Research agents, and recorded retrieval in the
  harness's composition (`deep_research_recorded` exists; its fixture and agents are the
  suites' own). Each suite keeps its own double until its contract joins the shared wire.
- **Chunk 1 (proposed, not approved).** The table above; ticked when the owner approves it.
- **Chunk 14 (in part).** Done: AC-01 ("a user of another organization gets 404", G73) and AC-14
  (typed settings, the composition digest, D-09 (b)) in both files; each criterion's tier-A and
  tier-B projection in both files (`tier_a`, `tier_b`; §3.1; G77's wording half); the L-04 / L-29
  contradiction removed (`results.verification` out of AC-08, `statistics.calibration` out of
  AC-05, both off the MVP path). AC-02, AC-11, AC-13 and AC-15's separate lines were already
  reconciled by #503 and stand. **Left:** refreshing the three 18.6.6 ledgers
  (`legacy-route-ledger.json`, `legacy-ui-functions.json`, `interface-screens.json`), whose
  LEGACY / NOT_STARTED rows include built work (reverse scope audit §3): an audit of 157 routes,
  89 functions and 28 screens with their tests, a PR of its own.
- **Chunk 5 (ahead of its wave).** AC-01's tier-A tests landed, because the tree must hold a
  criterion that can pass end to end and AC-01's path exists: three tests in
  `test_mvp_acceptance.py`, listed under AC-01. The 404 probe reads every study route from the
  API's own document (96 routes at `c88fd7fd`) and requires the body another organization gets to
  equal the body an absent study gets. Chunk 5 stays open.

## Findings

- **F-1. The plan's `run_cost.py` hypothesis was half right.** It bounds fieldwork, analysis and a
  Deep Research run, and names a design job's reservation (`domain/run_cost.py:67, 86, 268 @
  c88fd7fd`); the Lead's turns and the unbuilt report writer and map interpreter have no bound.
  Not a defect; chunk 1's table carries their bound.
- **F-2. An approved Deep Research run limit bounds nothing.** `budgets.run_limit.<preset>` ("Most
  a Standard run may cost") is an approved, pinned setting (`domain/deep_research/settings.py:366-378
  @ c88fd7fd`) that no executor or enqueue reads; its one reader checks a scoped test policy's
  values against its cap (`infrastructure/deep_research_settings_repository.py:284`).
  Reproduction: `grep -rn "run_limit" packages/aia_core/src apps/executors/src --include=*.py` (two
  hits, neither stops a run). Consequence: an organization's per-run ceiling is not held; a run is
  bounded only by the study's budget and the start's confirmation, so tier B's lines A06-A08 are
  held by the runbook alone. Smallest fix: the enqueue refuses a run whose
  `deep_research_cost_ceiling` exceeds the pinned run limit, by name. Test: an enqueue whose
  ceiling exceeds an approved run limit answers 409 naming it.
- **F-3. The evaluations cost more than any approval so far.** At the plan's own estimates
  (`deep-research-web-search.md:486-488`, chunk 26's arms at `:705-712`) chunks 25, 26 and 39 cost
  about USD 1,800-2,900, chunk 26's Deep-against-Exhaustive pass most of it. Not a defect: the
  owner scopes them (fewer questions, Standard only) before W4, or approves them apart.
- **F-4. The acceptance study cannot use a scoped Deep Research test policy.** A study test policy
  requires the study's budget at most USD 20 (`infrastructure/deep_research_settings_repository.py:458-467
  @ c88fd7fd`); the representative study's is USD 25 (`docs/migration/mvp-acceptance.md` §1).
  Reproduction: propose a test policy for a study budgeted USD 25: refused, "test budget must cover
  this study and be at most USD 20". Consequence: tier B's live Deep Research needs the
  organization's own live approvals (ADR 0022), not the sandbox. Smallest fix: an owner choice --
  the organization's approvals for the acceptance organization, or a USD 20 study. Test: the
  existing guard (`test_deep_research_sandbox_policy.py`).
- **F-5. A respondent's model calls are not readable over HTTP.** The fieldwork dataset is never
  inlined (`apps/api/src/aia_api/routers/research.py:156 @ c88fd7fd`) and an artifact's response
  carries no provenance (`routers/runs.py:181-200`), so AC-15's per-number walk (chunk 16, G65) has
  no HTTP read for fieldwork calls. Reproduction: `GET …/research/runs/{id}/artifacts/{fieldwork
  artifact}` answers `payload: null` and no `provenance`. The harness reconciles them through the
  study's spend for now. Smallest fix: a run's usage lines over HTTP (call ids, request ids,
  model, cost), no respondent content. Test: over HTTP, a run's usage lists each respondent call's
  provider request id.

## Doc follow-up

For the docs PR (CLAUDE.md §1; this PR edits no shared file):

- `CLAUDE.md` §3, a row: "**MVP acceptance, tier A** | `make test-acceptance` (needs
  `AIA_ACCEPTANCE_DATABASE_URL`, a PostgreSQL database it may migrate and seed): `tests/acceptance`
  starts the API and a worker (`aia_executors.acceptance_recorded`) as processes after the
  declared bootstrap and drives them over HTTP; recorded models, nothing paid".
- `CLAUDE.md` §2 map: under `apps/executors/src/aia_executors/`, `recorded_models.py` ("the
  recorded Converse wire the suites and the acceptance harness share: respondent, analysis and
  Lead answers, `recorded-<kind>-<n>`; any other contract refused by name") and
  `acceptance_recorded.py` ("the acceptance harness's worker: production's composition over the
  recorded wire; local and test only; refuses Deep Research"); `registry.py` gains
  `compose_registry(transport=, signer=)`. A top-level `tests/acceptance/` entry ("MVP-ACCEPT-2
  tier A over HTTP; the stack, the bootstrap, `allocation.json`"). `tools/parity_status.py`:
  "the acceptance verdict per criterion from the acceptance step's JUnit, path parity beside it".
- `ARCHITECTURE.md` §3 table, four rules: "among the executors, only the acceptance composition
  imports the recorded models" (prevents a recording answering a production request); "no
  deployment runs the recorded models"; "the acceptance tree imports nothing it drives" (prevents a
  back door in the acceptance test; an AST test holds every import form); "no statically skipped
  or xfailed acceptance tests". §8 CI tiers: the collect-only pass covers five trees; a new row
  "MVP acceptance, tier A (`tests/acceptance`, its own PostgreSQL database)": **blocking**; the
  parity-status row: "blocking on a capability's or an acceptance criterion's `FAIL`".
- `AGENTS.md` § pytest: current markers add `acceptance`. Two gotchas, wrong beside right:
  - Alembic does not migrate SQLite: `DATABASE_URL=sqlite+pysqlite:///x.db alembic upgrade head`
    raises `NotImplementedError: No support for ALTER of constraints in SQLite dialect`; a harness
    that bootstraps through the migrations needs PostgreSQL (the suites' `Base.metadata.create_all`
    is not the operator path).
  - Two error answers differ by their `request_id`: compare the body without it, never the bytes
    (`test_mvp_acceptance.py::_error`).
- `.planning/open-items.md`: F-2, F-4 and F-5 above, numbered there.

## Chunk 8: parity reports and never blocks

**Decision.** The owner decided on 2026-10-19 that parity runs and reports but never blocks
(`mvp-cohesion.md` F9, Q28). Written against `develop` @ `de6ded8`.

**What changes.** Every job that compares AIA with 18.6.6 (`parity`, `oracle-parity`, and the
reference-repository steps of `golden-fixtures`, `.github/workflows/ci.yml`) is non-gating: its failure
is written to the step summary and to the JUnit artifact, `tools/parity_status.py` still prints
`FAIL`, and it exits 0 in CI (a `--report-only` flag, not a changed default, so a person running it
locally still sees a failing exit). `dispatch-develop`'s condition drops those jobs. A parity `FAIL`
also appears as one line in the acceptance record (chunk 6).

**What does not change.** `test_parity_matrix.py` (the matrix describes itself correctly), the vendored
Sociomap golden fixtures F1-F9 and every non-parity test stay blocking. Nothing is skipped or loosened:
the tests still run and still fail loudly in their own job.

**Cost, stated.** A regression against 18.6.6 can now merge and deploy; the protection is that the
report is read. The record's parity line and the PR summary are the only places it shows.

**Test.** A CI-script test feeds `parity_status.py --report-only` a JUnit file with a failing parity test
and asserts exit 0 and a `FAIL` line, and a matrix-consistency failure still exits 1.

## Added by the master plan (2026-10-19)

- **9.** The `acceptance` marker is unregistered under `--strict-markers` (`pyproject.toml:276-282`), so the
  tree would not collect. Gap G10.
- **10.** Tier A is "over HTTP". The workbench, Lead and artifact journeys run in a browser
  (`tools/ui_workbench/*_journey.mjs`); the record keeps them as a separate line so a browser pass is never
  read as an HTTP pass and the reverse.
- **11.** Chunk 7 (tier B) depends on the Deep Research route: the first release's route is Brave for an
  OPEN client (`deep-research-web-search` 53). Evaluations 25, 26 and 39 run before chunk 27
  (`deep-research-web-search`, "Evaluations before the final live run"); the second live run that "cited
  context in the report" needs (`contextual_report.py:985`) is added to AC-11's allocation. Gap G38.
- **12.** `mvp-development-plan.md` §8 said a production release "can follow the acceptance without moving
  the gate"; gate I-5 says "production released". I-5 stands: production is a blocker.
- **13.** The twenty scenarios of `prototypes/research-lead-v2` are the behaviour spec. X2 and X6 are
  central invariants (evidence that is missing says so; a methodology change is refused in place and
  routed to Metodika) and cheap to test on doubles, so they are not deferred. The scenario order is a
  build order, not a release scope.
- **Wording to reconcile, in a PR that runs the tests** (`docs/migration/` and `parity-matrix.json` are
  outside the docs-only path list and `test_parity_matrix.py` reads the matrix): AC-02 "a paid worker job
  starts only on an approval card" against the wallet and the plan card; AC-11 "approved for Class B"
  against the OPEN posture; AC-13 "a reviewer other than the producer" against F17 (withdrawn).

- **14.** The wording that disagrees with settled decisions is changed in the acceptance document and the
  machine criteria in one pull request that runs `test_parity_matrix.py` (those files are outside the
  docs-only path list). **AC-15's reconciliation is stated as separate lines**: model usage in the ledger,
  tool and search spend, reservations, uncertain calls, cloud-billing lag and non-provider infrastructure
  charges; a number never reads as zero because it is unknown. The edit is on `chore/acceptance-reconcile`.


## Incremental gates and full acceptance (2026-10-20)

W0 builds 1-4, 8-9 and 14. W1-W4 extend 5, 10 and 13. W5 finishes 6-7 and 11-12.
RQC10's population double lands before the W1 HTTP path. Do not give an unimplemented criterion
a passing placeholder: record PASS / FAIL / NOT_EXECUTED / BLOCKED with reason and evidence.

I-1 covers the available design workers, not all eleven workers; I-3/W3 adds LO9b and the eight
analysis prompt pins. Only final tier A can report AC-03 PASS for all of them. Browser proof grows
per artifact, and all eleven artifacts must pass before the release record. W0 tree collection,
partial I-1 coverage, live I-R probes, final tier B and production are distinct evidence classes.

The record pins the tested application SHA, plan/acceptance versions, fixture hashes, model and
prompt identities, deployment/composition and effective policy. It includes criterion/negative-case
id, expected/actual behavior, evidence artifact ref and cost/reservation/uncertainty lines. For a
changed input, method, contract, prompt or deployment, identify which evidence must be repeated;
do not carry a green release decision from an older SHA. Paid reruns still require their allowance.

**15. (2026-10-20)** The journey and refusals of `assumptions-and-open-answer-coding#AOC9` join the acceptance tree: an assumption created, evidence attached, status set by a person, shown in the report; open answers coded, counts admitted, shown in Results and the report; a status without support refused, counts never produced from prose, a codebook change that leaves fieldwork untouched. It runs on recorded doubles in tier A; the model coder, if any, is a recorded double.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

**New chunks.** 16 (W3), 18 (W4; D-48 in, its budget values open in the baseline).

**Existing chunks, changed.**

- **3 (G75).** `parity_status.py` computes MVP-ACCEPT-2's verdict from the acceptance step's own
  JUnit (which 3 already produces), with path parity reported beside it and never in it; a test line:
  a passing acceptance JUnit prints PASS while the path capabilities stay NOT_RUNNABLE. The
  `project.memory` row of `parity-matrix.json` is corrected with it (#515, narrowed: no new chunk).
- **3 (G76).** A declared operator bootstrap (`aia_executors.seed`, or production's
  `production-environment#PE10`), named in the record; everything after it over HTTP, the worker as a
  subprocess; an import-linter contract that `tests/acceptance` imports no application or
  infrastructure module.
- **5.** Its front matter's "the built ones first (AC-01, 06, 07, 12, 14)": only AC-12 is an existing
  path. Its wave: W5 (E24) governs.
- **6 (G77).** The record is per criterion per tier; each criterion carries its tier-A and tier-B
  projection, AC-15's AWS clause included.
- **10 (D-48).** Axe in every browser journey: a serious or critical violation fails it.
- **11 (D-11).** The acceptance study cites one known dead URL.
- **14.** AC-01 reads "a user of another organization gets 404, not 403, on every study route"
  (ADR 0019; G73). AC-14 reads "typed settings refuse a malformed value by name; each run records its
  composition digest" (D-09, `lead-orchestration#LO12c`). The three 18.6.6 ledgers are refreshed and
  the L-04 / L-29 contradiction removed.
