---
status: in-progress
chunks:
  - "[x] A0. Record the four-area MVP acceptance contract and current evidence at one development SHA"
  - "[x] A1. Verify the native AI research-to-map-to-report chain and expose remaining boundary gaps"
  - "[x] A1b. Include recorded Deep Research over the same design and verify the frozen evidence and missing handoff"
  - "[x] A1c. Check the unmerged Sociomap stack plus Interpretation Research candidate and prepare the post-merge proof"
  - "[x] A2. Trace and prove the simulation, data-library and project-memory user journeys"
  - "[ ] A3. Review runtime complexity and carry out one measured simplification at a time"
  - "[x] A3a. Classify the candidate areas by traced consumers, at develop cd6da1e1"
  - "[x] A3b. Delete the root Fastify stub and its root npm package (no consumer)"
  - "[x] A3c. Remove the unconnected small surfaces the owner confirmed; test the kept snapshot route"
  - "[x] A3d. Decide the Sociomap body's duplicated side tables, then measure and simplify (queue item 3)"
  - "[x] A3e. One reader of a stored contract-3 map for the report and its figures (queue item 4)"
  - "[ ] A4. Run the complete four-area recorded acceptance on a release candidate"
  - "[ ] A5. Verify bounded deployed acceptance and record the release decision"
---
# Make the four-area MVP demonstrably work

**Publication scope, 2026-10-08:** the user authorized publishing this plan and the linked
client-knowledge proposal. This is a docs-only change based on develop `4d8f07d934e88a9d15b9da47c78c42a1b01ca019`.
The connected research test and two web-test fixes discussed below are pending local work,
not files added by this PR. Their recorded results are historical verification evidence;
they must not be mistaken for new merged tests or a release verdict. The client-knowledge
audit's two reproducible probes are included under `.planning/evidence/client-knowledge-review/`.

User direction, 2026-10-07: systematically address integration failures hidden by isolated
tests, and prioritize completion, consolidation and proof of usefulness. The user explicitly
requires all four areas for the MVP: simulation studio, Sociomapping, data library / social
intelligence, and project memory. Research is the first verification path, not a smaller MVP.

Baseline: `develop @ bdf0408`. This plan owns cross-area verification and simplification
evidence. Implementation status remains in the existing feature plans. It does not copy their
backlogs, override the canonical formula documents, or authorize live calls, data promotion,
deletion, deployment or merge. No new assurance framework or runtime abstraction is needed.

## What counts as assurance

Maintain four separate observations: code exists; a recorded application journey passes;
the deployed journey passes; the result is eligible for its intended use. A passing unit test,
a successful merge, a visible screen or a draft report cannot establish the other observations.
Use the levels in `docs/architecture/research-journey.md` §1, while checking its dated stage
table against current code and feature plans rather than treating it as current implementation.

Each proof records the exact source SHA, environment, fixture/source hashes, executed tests,
run and artifact identities where available, refusals, skips, and actual cost for live calls.
Keep test recordings fictional and offline. Inspect a failure before changing the test.
Never mark a capability complete by relabelling the required capability unsupported.

## Four-area release contract

These are minimum observable requirements; implementation choices remain in feature plans.
Detailed client-facing methodology and data eligibility still follow their existing decisions.
The user's all-four decision confirms release scope. These proposed technical acceptance
checks do not imply client approval of areas marked "K potvrzení klientem" in project context.

| Area | A user must be able to demonstrate | Required cross-boundary proof |
| --- | --- | --- |
| Simulation studio | Complete the declared 13 phases, approve a scenario contract, create at least two variants against one frozen baseline, inspect frozen outcomes and their deterministic comparison, retrieve a report with explicit review state | Context / population / dimensions -> approved WorldModel and scenario -> worker -> immutable results -> comparison -> report; retry preserves bindings; a new scenario cannot mutate the original result |
| Sociomapping | Select an audience and dimensions that actually reach fieldwork; inspect canonical object and respondent maps, supported segment/region comparisons and a stored view; compare revisions/scenarios on a consistent ruler; retrieve matching map/report output | Frozen design and population -> actual roster -> declared study-wide rating universe -> canonical method -> map -> region/view/report consumers; the same geometry, support, exclusions and method appear wherever shown |
| Data library / social intelligence | Receive a source, inspect its evidence proposal and provenance, accept it as a person, materialize an eligible dimension, validate it, and explicitly create a new LIVE population revision | Source -> scoped evidence -> acceptance -> materialization -> validation/calibration -> promotion; selecting a dimension cannot promote data; an existing run retains its older population binding |
| Project memory | Find the same client's historical studies, inspect their design, method and labelled results, and reuse a past design in a new study with human acceptance (result reuse after the MVP, owner 2026-10-10) | Past Design Revision -> scoped retrieval -> cited, labelled new Design Revision; historical results remain immutable; draft/synthetic limitations persist; another client or organization cannot access the source |

Shared acceptance: a researcher can see pending saves, stale-revision refusals, progress,
named failures, spending and recovery state. Changed material inputs invalidate the correct
stages; view-only changes do not rerun fieldwork. Same-organization access follows ADR 0019;
an incorrect Study/run pairing is refused. Synthetic evidence remains labelled and cannot
become client evidence. Client-facing release requires its own implemented contract and review.
Deep Research evidence must retain its sources and eligibility; any handoff to design,
fieldwork or interpretation must be explicit and follow the owning implementation plan.

## Current evidence and gaps

All anchors below are at `bdf0408` unless a test or later verification identifies otherwise.
The baseline is not an assessment of every file in the repository.

| Boundary | Existing evidence | Current assurance limit / owner |
| --- | --- | --- |
| Native research and analysis -> internal report | `test_analysis_executor.py::test_native_research_start_and_worker_complete_the_composed_analysis_graph` starts the application-owned 14-step template and creates a real lint-checked DOCX | Existing fixture uses deterministic fictional fieldwork; the new `test_native_ai_study_connects_a_populated_map_to_admitted_report_inputs` connects AI respondents and a nonempty map to the same application-owned chain (see verification log). `internal-report-composition.md` still owes deployed acceptance |
| AI fieldwork -> analysis | `test_analysis_executor.py::test_ai_respondents_answer_and_the_eight_modules_interpret_them_in_one_run` exercises the gateway and eight modules | `_start` in the same file constructs a 13-node graph directly and its DESIGN has no object battery. This alone proves neither the application report node nor a populated Sociomap |
| Deep Research -> same-study research and report | The new `test_native_ai_study_connects_a_populated_map_to_admitted_report_inputs[deep-research-and-internal-report]` executes six Deep Research stages, verifies grounded recorded snapshots and the seal, then runs the native AI/map/analysis/report chain over the same revision | The same-study coexistence is proved, not automatic bundle consumption. `apps/web/src/components/rehome/research/DeepResearchPanel.tsx:14` is review-only; report dependencies contain only the eight analysis modules. Result interpretation freezes exact lineage but enqueue raises `InterpretationNotReady` (`packages/aia_core/src/aia_core/application/deep_research.py:457-486`); implementation owner: Deep Research web-search chunk 30 / OI-88 |
| Report -> HTTP download | `test_research_api.py::test_internal_report_is_listed_and_downloaded_only_through_its_study_run` checks scoping, bytes, labels and corruption refusal | The route fixture writes test DOCX bytes and completes steps directly. It must later consume the actual worker's report in A4 |
| Browser -> research -> Results | `tools/ui_workbench/research_journey.mjs:1-20, 112-129` checks five base steps, aggregate table and INTERNAL_ONLY label | No full analysis/report download assertion and no evidence that selected dimensions/audience changed executed inputs. Extend the existing journey rather than adding a parallel browser harness |
| Selected dimensions/audience -> fieldwork | Compiler probes and six integration chunks in `sociomap-formula-corrections.md` §8.1 | Compiler drops selection semantics (`packages/aia_core/src/aia_core/domain/research_design.py:375-389`), and `apps/executors/src/aia_executors/ai_fieldwork.py:118-129` builds the fictional roster. Implementation owner: formula-corrections I0/I1, population capability dependency |
| Canonical map -> research report | `apps/executors/src/aia_executors/report.py:37-67, 71-103` reconstructs eight analysis modules and stores their dependencies | The general internal report executor does not read the canonical Sociomap artifact. Map/report equality remains formula-corrections chunk 5 / I5; the separate experimental H-Model report does not close this boundary |
| Simulation core -> studio | `packages/aia_core/src/aia_core/domain/simulation/` and `.planning/plans/done/simulation-deterministic-core.md`; the 13 stages are declared in `packages/aia_core/src/aia_core/domain/pipeline.py:117-131` | `apps/web/src/components/aia/SimulationFrame.tsx:3-5, 33-38` explicitly says the workflow is not implemented. `apps/executors/src/aia_executors/registry.py:37-57` registers no simulation chain. A2 must establish a dedicated implementation plan around the existing core |
| Sources/knowledge -> materialized population | `packages/aia_core/src/aia_core/application/population.py:345-412` supplies establish/promote; client knowledge and proposal acceptance exist | `apps/web/src/components/aia/GlobalPages.tsx:26-36` shows shared intelligence as not implemented; `apps/web/src/components/aia/clients/DataArea.tsx:17-59` lists client knowledge, not a completed materialization journey. Operator core availability does not prove the product path |
| Study listing -> reusable project memory | `apps/web/src/components/aia/GlobalPages.tsx:41-49` loads Study lists and filters names/client names | This is historical navigation, not retrieval of approved findings/artifacts. Native `answer_memory` proposals alone do not establish the intended search/reuse workflow. A2 must trace it and assign its missing implementation plan |

The map-body version, spec contract version, engine implementation version and method preset
are different identities. Preserve historical readers and the selected method at enqueue;
current engine-version cache invalidation does not provide that pin (formula-corrections I4).

## Work sequence and ownership

**A0 — scope and baseline.** Record this contract, the user's all-four requirement and evidence
table. Confirm the feature plans that own existing work. Mark uncertainties as unanswered; do
not repeat source-approved formulas as new approval questions. A0 is done once the contract
and current evidence are saved and validated, not once every capability is built.

**A1 — first connected proof.** Start a real `ResearchRuns.start` run with AI fieldwork,
analysis enabled and a declared object battery. Replace external transport with scripted
fictional responses; use the real database, worker, gateway, analysis reconstruction, map engine and DOCX
renderer. Assert that the map is nonempty and stored for this run, all eight modules are
complete, and the report is a readable unapproved internal draft with its source dependencies.
Exercise a blocked analysis, scoped download/corruption refusal, and engine-change reuse guard.
Report the proof's limits explicitly: SQLite is not PostgreSQL concurrency, a scripted model
is not live verification, and legacy geometry is not the completed canonical method.

**A1b — Deep Research in the same study (user request, 2026-10-08).** Extend the connected
test with recorded web/model transport from the existing Deep Research fixtures. Start
Design Research through `DeepResearchRuns.start` over the exact Design Revision, run its
registered executors, verify the sealed grounded evidence and immutable design, then execute
AI fieldwork -> map -> eight analyses -> internal report over that revision in the same
database/store/worker composition. Verify the Deep Research bundle remains unchanged.
The current review-only surface (`apps/web/src/components/rehome/research/DeepResearchPanel.tsx:14 @ bdf0408`) does not feed the
bundle into the native fieldwork/report chain. Do not fabricate that handoff in a fixture.
Freeze interpretation lineage from the resulting map and verify the existing
`InterpretationNotReady` refusal before any new run/model call (existing owner: Deep Research
web-search chunk 30 / OI-88). Record the absence of direct bundle consumption as a release
integration question owned by the existing Deep Research / workflow implementation plans.

**A2 — finish the remaining trace.** For each of simulation, library and memory, follow the
same concrete fixture from its UI action to stored output and reopen it. Reuse existing
scope/population/scenario/artifact primitives. Write a small feature implementation plan only
where no current plan owns the missing capability, with explicit contracts and dependency
boundaries before code. This plan keeps the user journey and evidence; those plans own fixes.
Client knowledge intake, typed meanings, source-backed acceptance, corrections and consumers
are now owned by `client-knowledge-lifecycle.md` (user direction, 2026-10-08). The user confirmed
documents/notes, datasets and web/external research are all integral; acceptance must exercise
all three. This supplies the library/materialization and project-memory dependencies rather
than adding a second population loader or changing canonical Sociomap math.
Prioritize library/materialization and I0/I1 where they supply inputs to both map and simulation.
Validate the exact 13-phase studio semantics before wiring its worker; do not infer readiness
from the numerical-core plan's completed status.

**A1c — incoming stack check (2026-10-08).** The user supplied PRs 187 -> 188 -> 189 ->
190 -> 191 -> 192 and independent PR 193. Their base/head metadata confirms this ordering;
all are open drafts, not landed changes. Prepare a disposable candidate from PR 192's
`46d38bdf` plus PR 193's patch (`4c440fa2` against `751d7ae`), preserving the pending local
work. Verify the existing assurance proof against it. PR 193 removes `InterpretationNotReady`:
prepare a successor test that actually executes interpretation of the produced map and a
real admitted analysis-module artifact. The baseline bdf0408 test remains valid for that
baseline; do not conditionally skip/refuse successful interpretation to make both look green.
The post-merge test belongs on the combined code after review/merge, not on bdf0408 alone.
Record the distinction between completed backend work and unbuilt selection application,
v2 Results/report rendering, Lens (31) and report evidence graph (32). Carry the PRs' exact
Doc follow-up into a separately authorized docs-only change after landing.

**A3 — simplify after tracing consumers.** Review each runtime path from entry point through
its callers, registration, artifact readers and tests. Candidate areas are the three map
computations, duplicate/stale status narratives and disconnected product surfaces. Classify
each as required now, required for historical reading/reference, experimental, or unused with
evidence. Keep the frozen legacy oracle and historical readers until their consumers and
retention requirements are understood. One measured simplification per PR, with the relevant
connected proof rerun. Do not rewrite working subsystems because of file counts.
Ask an experienced independent reviewer to assess the four boundary contracts and release
proof; no claim that such a review has happened is implied by creating this plan.

**A4 — one release candidate and four journeys.** Run real Chromium, API, worker, disposable
PostgreSQL and artifact storage with recorded model/source transport at one combined SHA.
Cover source ingestion/promotion -> study dimension/audience resolution -> research/map/report
-> approved artifact reuse -> two simulation variants and frozen comparison. Exercise changed
inputs, old-run replay, save conflicts, missing support, cancelled/uncertain work, corrupted
artifacts and wrong organization/Study access using the existing fixtures/harnesses. Observe
that no product request depends on the legacy reference runtime. A4 requires all four areas;
partial successes are reported separately and never presented as a complete MVP.

**A5 — deployed acceptance and release.** After the necessary route/material/method approvals
and a bounded live run are explicitly authorized, repeat the supported journeys on the
deployed candidate. Record build identity, actual spend, reviewed outputs, rollback evidence
and remaining limitations. Internal acceptance, pilot eligibility and client release are
separate verdicts. Existing authorizations for other tasks are not a new spending allowance.

## A work cycle the owner can follow

1. Name one observable outcome and its owning feature-plan chunk.
2. Demonstrate the current failure or missing path with an anchor and a small reproduction.
3. Make the smallest coherent change; avoid adding an unrelated capability.
4. Run the relevant boundary proof and existing checks; inspect the actual stored output.
5. Record what now works, what remains, and the next acceptance condition in the owning plan.

The owner's update should say: demonstrated outcome; remaining failure; decision needed;
next proof. PR count, test count and code size are supporting evidence, not an MVP percentage.
Estimate dates from the remaining reviewed slices after A2, especially simulation and library;
the earlier conversational dates are provisional until those paths have executable estimates.

## Complexity baseline

Tracked text-source inventory at `bdf0408` (physical lines including blanks/comments; generated
code included; binary/data files excluded). This measures size, not bloat or code quality:

| Group | Files | Lines |
| --- | ---: | ---: |
| Application source | 416 | 120,761 |
| Tests and test helpers | 295 | 96,035 |
| Frozen legacy reference | 309 | 45,805 |
| Planning/documentation | 118 | 30,276 |
| Tools and other text source | 153 | 16,767 |

Extensions counted: `.py`, `.ts`, `.tsx`, `.js`, `.mjs`, `.md`; legacy first, then test paths
and `.test.` files, then docs/plans, then apps/packages. Do not treat all 309 legacy files as
product runtime or assume deleting tests/docs makes the application simpler. A3 adds consumer
evidence and change-specific measurements before recommending removal.

## Verification log

2026-10-08: fresh Python 3.12 environment prepared from the four packages' declared development
and report dependencies. The first attempt using an existing environment could not collect
report tests because `python-docx` was absent; no test passed in that attempt. No existing
environment was modified. Baseline source `bdf0408` plus the local added test; the publication
commit will identify the saved test. Initial test-source SHA-256 before A1b:
`fab8cea74cb89e5dd00bf7915d2d36293ec978445a03c6f2b5aa66bb2163fbb6`.

The new parametrized test
`apps/executors/tests/test_analysis_executor.py::test_native_ai_study_connects_a_populated_map_to_admitted_report_inputs`
uses file-backed SQLite, in-memory artifact bytes, a fake signer and `ScriptedModels` transport;
it makes no live calls. It uses the application-owned template and real worker, gateway,
evidence gates, legacy map engine and DOCX renderer. Test-local random run/artifact identities
are verified relationally rather than used as a replayable deployment record.

- 150 fictional respondents: the dataset and populated object/respondent map are stored,
  all eight analysis modules complete, and a lint-clean DOCX is stored as a synthetic,
  unapproved internal draft depending on this run's eight module artifacts. Design hash:
  `af2e00e3c0a20f31cd045a63418a368490d741bf5519b91774fae09b839c23ea`.
- 60 fictional respondents with this fixture's distributions: support suppression blocks all
  eight modules before any analysis call; the report step fails with `report_inputs_refused`
  and no report is stored. This is not a universal respondent-count threshold. Design hash:
  `34c47116fff83f68a88f3356c165bac8a1531fe419148bd5f0ffa0c26aa52775`.

The first new-test attempt expected a report from the 60-person fixture and correctly hit
the support gate. A subsequent negative-case assertion incorrectly required analysis calls;
that assertion was corrected to verify zero calls. No production gate was weakened.

Final focused runs: 29 analysis executor tests; 23 research API / engine-reuse tests; 76
population, simulation-results and workflow-template tests: **128 passed**. The boundary run
emitted two Starlette deprecation warnings. JUnit files are local temporary evidence:
`/private/tmp/aia-mvp-analysis-final.xml`, `/private/tmp/aia-mvp-boundaries-final.xml`,
`/private/tmp/aia-mvp-foundations.xml`.

A0/A1 complete these scoped offline checks, not the four-area release contract. The report
does not embed canonical map output, the selected audience/dimensions are not proven to drive
fieldwork, and this test does not prove browser/PostgreSQL concurrency or deployed behavior.
Broader repository checks are recorded below after execution.

The complete web suite now passes: **638 tests across 40 files** after F1's assertion fix;
the affected two files also pass independently (27 tests), using bundled Node 24.19.0 and
the locked web dependencies. Python and web type checking, Python and web lint, formatting
(557 Python files), design tokens / 210 contrast checks, 100 layering rules, seven exposure
rules, plan front-matter validation and diff whitespace checks pass.

Full Python run: **5,833 passed, 114 skipped, four failed, 27 setup errors**. Every failure
and setup error was a sandbox `PermissionError` when binding a local fixture server.
All **31 affected tests passed** when rerun with local socket permission, unchanged.
Thus 5,864 distinct Python cases passed across the full run and that bounded rerun; this
is not a claim that the initial command exited green. Full-run JUnit:
`/private/tmp/aia-mvp-python-full.xml`; rerun: `/private/tmp/aia-mvp-local-server-rerun.xml`.
No production files, dependency declarations or test gates were changed.

The 114 existing conditional skips remain unverified: 74 need AIA-reference; three need
the running legacy oracle; 37 need PostgreSQL (including worker and fan-out processes).
No skip was added. No browser journey, deployed acceptance or live model spend occurred.
These are verification limits, not evidence that concurrency or all four product areas work.

2026-10-08, A1b extension: the third case of the connected test uses the existing Deep
Research web/agent recordings and a wholly fictional 150-person drinks study. The same
worker, scoped database, store and frozen revision serve both runs. Its six Deep Research
stages complete before the native 14-step research run. Each accepted quote resolves to
the run's recorded snapshot and exact quote span; the sealed bundle is labelled recorded,
fictional and non-client-facing, and is refused as live evidence. The design is unchanged.
The dataset, populated map, eight complete analysis modules and real internal DOCX are
produced. Afterwards the evidence seal remains unchanged; map interpretation freezes all
four producing artifacts by id and hash, then is refused before creating another run or
making another model call. The report's dependencies exclude the review-only bundle.

The first extension attempt correctly failed native readiness because the pre-existing
Deep Research fixture had no object-family declaration. The fixture now declares drinks
and its [1, 10] scale before either run; no readiness or material gate was weakened.

After extension: **77 related tests passed** (analysis executor, Deep Research journey and
Deep Research lineage), including all three connected cases. JUnit:
`/private/tmp/aia-mvp-deep-research-related.xml`. Python type, lint and format checks, all
100 layer rules, seven exposure rules, plan validation and diff whitespace checks pass.
The prior full Python/web results
above belong to A1 before this extension; no web or production code changed for A1b.

Current test-source SHA-256:
`3562b8f136c485d7995fc2cf2a8399b6c37b6df099b6b45ce9a89abdec4e6023`.
Deep Research fixture design hash:
`7c73ed8e077de375a1bbf9b8290857c58d6f0ddaf6023f30a225fc86d993c743`.
Recorded web fixture SHA-256:
`85b10dd82a65fbfa62c11f86a6c255eb6e701efd193754443cecc66397b65a2a`;
recorded agent fixture SHA-256:
`f143448468e7f266250e71efeccf04f3b437b4be907646063a8207168942f761`.

A1b adds Deep Research to the proof; it does not close the reviewed handoff to downstream
consumers or enable result-based Interpretation Research. Both remain explicit integration
limits with existing implementation owners. Its retrieval is the recorded planned web
mode, not live Wikipedia/Brave, fan-out, agent-directed or internal Client Knowledge
acceptance. Those modes retain their existing tests and release requirements.

2026-10-08, A1c incoming-stack verification (not a full PR review or merge approval).
The seven PRs remain OPEN DRAFTS. Their latest fetched CI runs all concluded SUCCESS
(runs 553-559). Verified base/head chain:

| PR | Exact head | Base |
| --- | --- | --- |
| 187 | `ac10dfdbdd1bf0968427fa331a51e87358eb5532` | develop `751d7ae3e1ae9f947bef5fe6882d2edf736ff3c0` |
| 188 | `71bf2947fdafb2bc9af3a2b2e9331b4bc7900055` | 187 |
| 189 | `cd87cf286eb7ef0a03b94552d5a5eb0e1a38022f` | 188 |
| 190 | `ca84d4d4b00dd43da8e93b32ca820bad741c6c7a` | 189 |
| 191 | `5e0dab15b97d463b95f7166ee54fa8d36b2f851b` | 190 |
| 192 | `46d38bdf7561bcdb199f35a12d2b62c98c269d1e` | 191 |
| 193 | `4c440fa2ddeab8f9c81dbaa9d7dc8de5993ce74c` | develop `751d7ae3e1ae9f947bef5fe6882d2edf736ff3c0` |

The disposable candidate is an archive of PR 192's head plus the binary diff from develop
to PR 193's head, which applies cleanly. It has no combined commit SHA. Candidate package
paths were explicitly selected with PYTHONPATH; the pending baseline checkout and its
original tests were preserved. The baseline test initially fails collection on this candidate
because PR 193 removes its imported `InterpretationNotReady`. This is a real successor-test
requirement, not a reason to skip interpretation.

The successor of `test_native_ai_study_connects_a_populated_map_to_admitted_report_inputs`
checks pinned methods and a typed stored v2 artifact in both successful research cases.
Its Deep Research case now executes interpretation of (1) the actual stored whole-battery
Sociomap and (2) the actual admitted OBJECTS analysis-module artifact. Both runs execute
six stages and seal accepted evidence with INTERPRETATION_RESEARCH purpose, target-specific
mission origins and exactly the frozen lineage. The original Design Research seal, report
hash, fieldwork-call count and analysis-call count remain unchanged. All source/model
transport is recorded; the candidate does not send live requests.

**3 connected cases passed; 201 related cases passed**, covering analysis execution,
Deep Research journey/lineage, Sociomap acceptance/frozen methods/rating universe/methods/
object maps, research selection, and Deep Research API/interpretation API. Python lint,
format (573 files) and type checks (304 source files) pass on the candidate. JUnit results
are preserved beside the successor patch in the project's `outputs/mvp-assurance/` directory.
The successor test SHA-256 is
`62a8b463e348765021edfaa3de328a688f95d316c8955f6d922a1e9a7dc1768d`.
Patch SHA-256 is
`c5a364e5a2fea958130f1a77a9bc9bb09a799e01c15fb492b590c0d39d55b82a`.
Apply that patch only after both this pending assurance test and the reviewed PR 187-193
code are present; it is not a patch for bare develop or the baseline bdf0408 checkout.

Incoming-code changes to the baseline gap table: PR 187 pins methods; PR 188 stores the
canonical v2 object map alongside v1 (respondents and terrain are explicitly not computed);
PR 189 declares the rating universe and roles; PR 190 records selection with `applied: false`;
PR 191 separates collectability from supported mapping; PR 192 exercises the composed stack;
PR 193 enables interpretation missions and execution (chunk 30 / OI-88). The successor's
AI fixture proves artifact storage and lineage, not a supported canonical layout on that
fixture; PR 192's dedicated acceptance cases exercise supported v2 layouts. Selected
dimensions/audiences still do not change fieldwork, and v2 Results/report consumers, Lens
chunk 31 and report evidence graph chunk 32 remain open. This focused candidate run is not
a full suite, browser/PostgreSQL journey, deployed acceptance, live-model proof or assurance
that the four-area MVP is ready. OI-88 is not closed in shared docs before the change lands.

Later status check, 2026-10-08: PRs 187-193 are all merged, and develop is
`67af44e5b9431d6293347b581fde7a34b95ed44c`. The OPEN DRAFT and CI statements above describe
the earlier candidate-verification snapshot. The pending baseline test has not yet been
rebased/published; its prepared successor is required on the merged code. Merge does not
establish deployed enablement or the unfinished consumers. The client-knowledge audit at
this merged SHA records two additional reproductions in its own feature plan.

Publication refresh: develop advanced to `4d8f07d934e88a9d15b9da47c78c42a1b01ca019`,
which merges docs follow-up PR 194. OI-88 is now closed in shared documentation and the
Sociomap/Interpretation Research follow-ups are recorded there. This supersedes the earlier
pending-docs statements, not their historical verification results. Selected inputs are still
unapplied and the remaining four-area consumer gaps remain open. No runtime code changed
between the client-knowledge audit baseline and this publication base.

2026-10-09, **A2 trace** at `develop @ c6ee438` (static: code read hop by hop from the UI
action to the store, every hop anchored in the owning plan's table). None of the three
journeys can be followed with a fixture past its first hop, so "prove" here is the trace and
the assignment of every missing hop to a plan; the executable proof is A4's.

| Area | Where the journey stops | Missing hops now owned by |
|---|---|---|
| Simulation studio | after "create a SIMULATION study": the page is a notice (`SimulationFrame.tsx:3-5, 33-38`), working content refused (`study_workspace_repository.py:135`), no workflow type (`workflow_templates.py:58`), no executor, no route; the core is pure and unconnected (its only non-test importer is `routers/settings.py`) | new [`simulation-studio.md`](simulation-studio.md) S0-S7 |
| Data library / social intelligence | after "accept a knowledge item": no source intake (`workspace.py:385-394` takes kind/title/summary), a DIMENSION is a title, nothing outside the core calls `PopulationRuntime` / `PopulationAuthority`, no run records a binding (`workflows.py:96-105`) | intake, typed revisions, context, dimension definitions: [`client-knowledge-lifecycle.md`](client-knowledge-lifecycle.md) K2-K5; binding semantics and selection in fieldwork: `sociomap-formula-corrections.md` I0/I1; the operator root, registry, binding at creation, materialization contract and Promote: new [`population-operations.md`](population-operations.md) P1-P5 |
| Project memory | after "list past studies by name": artifact approval has no caller (`artifact_repository.py:523-571`), no search crosses studies, accepting a memory answer raises `advice_only` (`research.py:637-638`), a revision cannot cite a source | [`project-memory-reuse.md`](project-memory-reuse.md) M0 (decided 2026-10-10) and M1-M4. "Find" is met by M1 (#279: `GET /clients/{id}/memory/search`, test `test_the_sibling_clients_study_saying_the_same_is_never_returned`); "inspect" by M2 (#285: `/app/clients/<client>/memory/<study>`, `MemoryStudy.test.tsx`); "reuse" by M3 (#295: `POST /clients/{id}/memory/reuse`, `test_design_reuse.py`); the connected proof by M4 (#299: `test_project_memory_proof.py::test_a_fictional_source_reused_stays_untouched_cites_its_labels_and_never_crosses_a_boundary`). Project memory's MVP scope is met; result reuse stays after the MVP |

Decisions the traces surfaced, each recorded in its plan: D9 reads as open while the user's
2026-10-07 direction requires the studio (`simulation-studio.md` S0); memory's reach across
clients, reuse unit and synthetic eligibility (`project-memory-reuse.md` M0); where and in what
form materialization makes a revision, under OI-61 and D8 (`population-operations.md` P4).
18.6.6's library approved its own calibration into LIVE (`data_library.py:621-626`); that is
recorded as not to be ported. Order across areas, unchanged from A2's guidance: population
P1-P3 first (they feed map, fieldwork and simulation S2), then K2-K5, then simulation and memory.

## A3 — consumer-traced classification (2026-10-12, `develop @ cd6da1e1`)

Static trace: every production caller found by `grep -rlw <name> apps packages tools` with
`/tests/` and `.test.` excluded, then each caller followed to a registered executor
(`apps/executors/src/aia_executors/registry.py`), a route, the web or an operator command;
`deploy/`, `Makefile` and `.github/workflows` checked for the rest. Classes: **now** (a
product path calls it), **historical** (needed to read what was stored), **parity** (gated by
a fixture or the parity matrix), **experimental** (behind a switch or a planned chunk),
**unused** (no consumer of any kind).

Size at the same rule as the baseline (reproduced: tests and legacy match `bdf0408`'s figures
exactly; application source counts 411 files, 120,492 lines at `bdf0408`):

| Group | `bdf0408` files / lines | `cd6da1e1` files / lines |
| --- | ---: | ---: |
| Application source | 411 / 120,492 | 480 / 145,133 |
| Tests and test helpers | 295 / 96,035 | 384 / 115,421 |
| Frozen legacy reference | 309 / 45,805 | 309 / 45,805 |
| Planning/documentation | 213 / 34,722 | 244 / 42,857 |
| Tools and other text source | 63 / 12,590 | 73 / 13,757 |

330 commits landed between the two. The growth is new capability (project memory, population
operations, methodology, Deep Research web search), not duplication; size stays supporting
evidence only.

**The map computations are two, not three.** `domain/research_sociomap.py` orchestrates: each
battery calls `compute_sociomap` once (contract 2, the one spec `read_methods` allows,
`research_sociomap.py:391-396 @ cd6da1e1`) and `compute_object_map` once per pinned contract-3
spec (`:563-573`).

| Path | Consumers | Class |
| --- | --- | --- |
| `sociomap/engine.py` `compute_sociomap` (contract 2, `aia-sociomap-1`) | every run's `SociomapExecutor` (`aia_executors/research.py:546`); the web's comparison table reads `object_ids`, `layout.object_xy`, `relation.scores` (`apps/web/src/lib/research-execution.ts:205-210`) | **now**; its `respondent_terrain`, `object_terrain`, `object_metrics` have no reader |
| No pin (`LEGACY_METHODS`, `research_sociomap.py:342`) | `read_methods(None)` for runs stored before pins; also inside `default_methods()` | **now** + **historical** |
| `sociomap/engine_v2.py` `compute_object_map` (contract 3), `aia-sociomap-3` | new runs' pin; Metodika compare (`methodology/sociomap_check.py:234`); readers `object-map-view.ts:75`, `report_maps.py:65`, `object_map_figure.py:110` | **now** |
| `aia-sociomap-2` | retries of runs that pinned it (`application/research.py:421`); still offered as a base preset (`methodology/sociomap.py:623`) | **historical** (see F3) |
| `aia-sociomap-4` | the editor's default base (`MethodologyVersions.tsx:144`); never pinned bare | **now** as a base; the bare key in `object-map-view.ts:20` cannot occur |
| H-Model `research_sociomapping.py` | `SociomappingExecutor`, only with `AIA_SOCIOMAPPING_EXPERIMENTAL_ENABLED` | **experimental** |
| `sociomap/view.py` drag, view terrain, scenario layers | no product caller; `parity-matrix.json:279` names `apply_view_overrides` as an entry point, gated by `test_f9_manual_drag_is_a_view_override` | **parity**: kept |

Duplication inside the map path, with anchors at `cd6da1e1`: the body's rescaled pair
relations, `object_scores` and K100 (`research_sociomap.py:536-615`) repeat what each
contract-3 map computes (`engine_v2.py:306-313, 379-421`), including a second bootstrap closure
that the K100 copy shortcut (`:582-600`) exists to avoid paying for twice; two readers repeat
the same contract-3 loop and check (`report_maps.py:65-70`, `object_map_figure.py:119-122`);
`CONNECTEDNESS_NOT_COMPUTED` (`research_sociomap.py:496`) and `engine_v2`'s `CONNECTEDNESS_OFF`
say the same; "-3 is in force" is stated by `default_methods()` and by `methodology/sociomap.py:625`.
The body's side tables are documented artifact content (CLAUDE.md map, research_sociomap), so
removing them is a stored-contract decision, not a cleanup (A3d).

**Disconnected product surfaces**, at `cd6da1e1`:

| Surface | Evidence | Class |
| --- | --- | --- |
| `src/server.js`, `src/views/`, root `package.json` + `package-lock.json` (177 packages) | CI's two Node jobs run in `apps/web` with its lockfile (`.github/workflows/ci.yml:610-622, 885-893`); `make setup` installs only `apps/web` (`Makefile:24`); `apps/web/Dockerfile:55`'s `server.js` is Next.js's; the root lockfile has no Playwright for `tools/ui_workbench/capture.mjs:63` to find; `overview.md` "Next" item 8 records the deletion as unblocked | **unused** → removed by A3b |
| `api.ts` `workspace.revisions` (`:536`), `deepResearch.run` (`:793`) | no non-test caller | **unused** |
| `GET …/deep-research/runs/{id}/snapshots/{snapshot_id}` (`routers/deep_research.py:691`) | no web caller, no API test (`DeepResearchRuns.snapshot` is tested and used by the executors) | **unused**, untested |
| `application/analysis.py` `run_pending_modules` (`:225`), `application/deep_research.py` `run_settings` (`:944`) | tests only | **unused** |
| `POST /clients` (`routers/scope.py:311`), `POST /studies` (`:410`) | the web creates through `/workspace/clients` and `/clients/{id}/studies` | **unused** by the product; API-tested |
| project `PATCH`, `/revisions`, `/events`, `/trash`, `/restore` (`routers/projects.py:272-440`) | tests only; `/impact` is in CI's required-path list (`ci.yml:510`) | **unused** by the product; larger, touches CI |
| Deep Research `/coverage`, `/provenance`, `/design-proposal`, `/accept` | tested; no screen yet (ADR 0019 gate 1 has no UI) | **experimental**: the missing consumer is the gap |
| `application/deep_research_triage.py`, `application/site_crawl.py` (~740 lines each with their domain files) | tests only; kept for plan chunks 23 and 36 (`deep-research-web-search.md:931, 1447-1449`) | **experimental**: owner's call, not cleanup |
| `aia_executors/legacy_workspace.py`, `application/workspace_migration.py` | operator runbook; the migration is not yet run on develop | **now** (operator) until it is applied and verified |
| `apps/web/src/design/tokens.ts` | generated; read only by its test | **unused** at runtime, pinned by `tokens:check` |

Every workflow template has a start path; every executor module is reached from a registered
composition or an operator command. `analysis.py` *is* registered (`registry.py:79-83, 119-128`,
behind `AIA_AI_ANALYSIS_ENABLED`): the CLAUDE.md line saying otherwise is stale (Doc follow-up).

**Status narratives.** Only plan front-matter (`tools/progress.py`) and `parity-matrix.json`
(`test_parity_matrix.py`, `parity_status.py`) are checked by anything. `research-journey.md`'s
stage table (`:100-114`, "at `ceee2dc`") still says analysis and report have no executor;
`docs/migration/status.md:337-339, 385-392` and `overview.md:31-37, 157-196, 248-256, 503-512`
describe states since superseded; `mvp-acceptance.md:3-9, 115-118` is research-only (F2).
Every one is a shared document: the corrections are listed under Doc follow-up for a docs PR.

**Simplification queue**, one per PR, smallest consumer risk first:

1. A3b — the root Fastify stub (this PR). Nothing runs it; measured below.
2. A3c — the unused small surfaces above (two `api.ts` functions, the untested snapshot route,
   `run_pending_modules`, `run_settings`; then, separately, `POST /clients` / `POST /studies`
   and the project command routes). Each removal names its tests; the owner confirms none is
   kept for an operator or a planned screen.
3. A3d — the Sociomap body's duplicated side tables. Decide first: no product reader reads the
   body's `relation_rescaled`, `object_scores` or `connectedness_100`; each contract-3 map holds
   its own. Measure the sociomap step's time with and without, on the 150-respondent fixture,
   before any change; an engine-version change re-keys reuse.
4. A3e — one Python reader of a stored contract-3 map for `report_maps.py` and
   `object_map_figure.py`.

Kept, with the reason: `view.py` (parity F9), contract 2 (every run pins it; the web reads
it), `LEGACY_METHODS` and `LEGACY_UNVERSIONED` (historical runs), the 18.6.6 migration (not yet
run), triage and site crawl (planned chunks), the frozen legacy reference (the oracle).

**A3b measured.** Removed: `src/server.js` (44 lines), `src/views/index.ejs` and `login.ejs` (51 lines),
root `package.json` (27 lines) and `package-lock.json` (2,001 lines, 177 locked packages, among them
fastify, ejs, better-sqlite3, exceljs, papaparse, zod): 2,123 lines in all, none of them run by
CI, a Dockerfile, Compose or the Makefile. The deploy builds the web image with context
`apps/web` (`.github/workflows/deploy-develop.yml:132`), whose `Dockerfile:18` copies that
directory's own `package*.json`; the Python image copies no root package
(`deploy/docker/python.Dockerfile:32-39, 76-77`). Run on this branch: the web job's steps from
`apps/web` (lint, `tsc --noEmit`, `tokens:check`, 1,211 Vitest tests in 60 files, `next build`),
all passing; `make layer_check` (113 rules) and `make exposure_check` (7 rules) pass. The image
build itself was not run here (no Docker daemon); CI and the develop deploy build it.

**A3c (owner, 2026-10-12: "go A3c" on the recommendation below).** The rule: nothing in the
repository uses it and no plan needs it, remove it; a planned screen will need it, keep it and
test it. Re-checked on `develop @ 42be47c1` before removal.

| Item | Done | Why |
| --- | --- | --- |
| `api.ts` `workspace.revisions` and its `KnowledgeRevision` type, `deepResearch.run` | removed | no caller; `deepResearch[action]` in `InterpretationResearch.tsx:95` names only `retry` and `cancel` |
| `application/analysis.py` `run_pending_modules` | removed | the worker reuses a module by `module_input_fingerprint` (`aia_executors/analysis.py:516, 712`), never through it |
| `GET …/deep-research/runs/{id}/snapshots/{snapshot_id}` | kept, tested | a finding is a quote in a captured source; "show the source" is the screen that will read it |
| `application/deep_research.py` `run_settings` | kept | seven lines; the verified read-back a Settings or audit view will need |
| `POST /clients`, `POST /studies`, the project command routes | deferred past the MVP | unused, but removing them touches CI's required paths and repository code for no runtime gain |
| `domain/simulation/reference.py:131` | corrected | cited the retired `.planning/PROGRESS.md`; the decision is `PROGRESS D10` in `overview.md` |

Tests of `run_pending_modules`, and where each property is now held: resume after module five
(`test_analysis_modules.py::test_resume_after_module_five_continues_at_six`); a blocked module
strands no other (`test_analysis_executor.py::test_a_module_whose_drafts_cite_nothing_is_blocked_after_three_calls_and_strands_no_other`);
a revoked holdout reruns every module as PENDING (`test_analysis_runner.py::test_revoking_a_holdout_does_not_reuse_the_validated_stamp`,
rewritten over `modules_to_run` and `run_analysis_module`, its assertions unchanged). The new
`test_deep_research_api.py::test_a_snapshot_is_read_only_through_its_own_published_run` fails
when the route's snapshot-id pattern is loosened (checked by mutation). `modules_to_run` now has
no production caller; it stays as the domain's statement of the unit's resume rule, which its
tests pin.

**A3e (owner, 2026-10-12: "start A3e").** `domain/sociomap/models_v3.py` `read_object_maps`
is now the one reader of a battery's stored `maps`: each read by `read_artifact` (fingerprints
verified), contract 3, and computed under the method it is stored by, or
`ArtifactIntegrityError`. `application/report_maps.py` `compose_map_sections` and
`infrastructure/report_docx/object_map_figure.py` `object_map_snapshots` both call it; their two
copies of the loop are gone. The copies had drifted: the figure renderer did not check the
stored key against the map's method, so it would draw a map stored under another method's
name (the report then refused it; the work was wasted, nothing wrong was printed).
`test_report_map_snapshots.py::test_a_map_stored_under_another_method_is_refused_by_report_and_figure_alike`
holds the shared rule, and fails when the key check is removed (checked by mutation);
`test_read_object_maps_reads_in_stored_order_and_refuses_another_contract` holds the reader.
The web's reader (`apps/web/src/lib/object-map-view.ts`) is TypeScript and stays separate.

**A3d (owner, 2026-10-14: "go ahead", after the measurement below).** Decision: the body keeps
no second copy of what each pinned contract-3 map holds. Its `relation_rescaled`,
`object_scores` and `connectedness_100` are gone; `relation` (the contract-2 matrix and pairs)
and the `side_tables` record stay. Traced consumers: none outside the body's own tests -- the
web, the API, `report.py`, `report_maps.py`, `object_map_figure.py`, Metodika's compare, the
analysis modules and Interpretation Research all read the maps. `battery_sociomap`
(`packages/aia_core/src/aia_core/domain/research_sociomap.py:441-541`, this PR) now computes the
pairs and the maps only; `SOCIOMAP_VERSION` is `aia-research-sociomap-10` (`:134`), so a body
stored under `9` is not reused as if it were `10` -- reuse of earlier Sociomaps is re-keyed once,
and a stored body is never rewritten. A run that pinned no object map (`LEGACY_METHODS`) loses
the copies on recompute; nothing read them. The `-3` map uses Kish n, so the body's K100
shortcut ("copy the map's") never fired and, with the K100 switch on, the body paid a second
bootstrap.

Measured before the change (fictional respondents, 4-core container, the methods a new run
pins today; scratch bench, not committed):

| respondents x objects | K100 switch | whole step | the side tables alone | their share of the body JSON |
|---|---|---|---|---|
| 150 x 5 | off | 0.46 s | 0.004 s (1 %) | 6 of 240 KiB (2 %) |
| 150 x 5 | on | 1.7 s | 0.54 s (31 %) | 3 % |
| 1,500 x 22 | off | 17.5 s | 0.5 s (3 %) | 85 of 498 KiB (17 %) |
| 1,500 x 22 | on | 251 s | 94 s (38 %) | 18 % |

Develop's Compose does not set `AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED`, so develop saves
the off rows. The methodology is unchanged: the weights step's formula is the same, its pin
(`domain/methodology/sociomap_reference.py`) moves only because `battery_sociomap`'s source
moved. Tests: `test_research_sociomap.py::test_the_body_keeps_one_copy_of_what_each_map_holds`,
`::test_with_the_switch_on_a_set_pays_one_bootstrap_per_pinned_map` (one bootstrap per pinned
map, counted), `::test_with_the_switch_off_no_bootstrap_runs_and_each_map_says_so`; the F2/F8
and K100 assertions moved onto the map (`sociomapping-evidence-register.json` names them);
`test_research_sociomap_k100_copy.py` is deleted with the rule it tested.

## Findings

**F3 — A superseded Sociomap method can still be put in force as an edited version (hypothesis).**
1. Claim: `aia-sociomap-2` remains a registered base preset, so an administrator can store and
   activate `aia-sociomap-2+e<n>`, and new runs would then pin a method that no unedited new
   run pins any more.
2. Anchor: `packages/aia_core/src/aia_core/domain/methodology/sociomap.py:623`,
   `apps/web/src/components/aia/settings/MethodologyVersions.tsx:319-323`,
   `apps/api/src/aia_api/routers/methodology.py:620, 665, 708`,
   `packages/aia_core/src/aia_core/domain/methodology/pins.py:60-71 @ cd6da1e1`.
3. Reproduction: not yet run (a `POST …/methodology/…/versions` with `base_preset =
   "aia-sociomap-2"` followed by activation and a run start). Until it is, this is a hypothesis.
4. Consequence: a new run could compute a method that the in-force default (-3) replaced,
   without anyone choosing -2 for new work on purpose.
5. Smallest fix: if the owner confirms -2 is historical only, refuse it as a base for a new
   version while keeping it readable for stored runs and versions.
6. Test: an API test that the version POST refuses a superseded base and a stored -2 run
   still reads and retries.

**F2 — The machine-readable MVP contract still describes the earlier research-only scope.**
1. Claim: MVP-ACCEPT-1 does not yet enforce the user's four-area release requirement.
2. Anchor: `docs/migration/parity-matrix.json` key `mvp_acceptance`, and
   `docs/migration/mvp-acceptance.md:1-16, 65-85 @ 67af44e`.
3. Reproduction: read the 14 acceptance criteria in that key: they cover the research lifecycle;
   the test path is null. They do not require a source-to-materialized-dimension journey,
   approved historical-artifact reuse or a complete simulation variant/comparison journey.
4. Consequence: completion and blocking-capability reporting remain tied to an older contract,
   even though this local plan explicitly requires all four areas. Green component checks or
   the old blocker list cannot decide release readiness under the current scope.
5. Smallest fix: reconcile the owning acceptance contract and executable gate with the all-four
   decision, retain existing checks and current ADR rules, and implement the existing A4 journey.
6. Test: the A4 recorded browser/API/worker/PostgreSQL/store scenario must produce explicit
   observations for all four areas; validation must refuse a completion record missing an area.
   This finding does not claim that an executable old MVP acceptance test currently passes.

**F1 — download assertions use an unsupported jsdom Blob method.**
At `apps/web/src/components/rehome/research/BriefStep.test.tsx:181` and
`QuestionnaireStep.test.tsx:243 @ bdf0408`, the existing download tests call `Blob.text()`
on jsdom's Blob, which has no such method. Reproduction from `apps/web`:
`npm test -- src/components/rehome/research/BriefStep.test.tsx src/components/rehome/research/QuestionnaireStep.test.tsx`.
The full web suite reproduced both failures (636 passed, 2 failed). This blocks trustworthy
download verification; it does not demonstrate a failure in the browser's file download.
The smallest fix is to read the captured bytes with the files' existing FileReader-backed
`arrayBuffer()` stand-in and decode them. Both original tests retain their exact content,
route and download-click assertions; no product behavior or evidence gate changes.

**F-S3-1 clarification — adding a rated context item versus relabelling an existing item.**
The owning finding is `sociomap-formula-corrections.md:1031-1041 @ 46d38bdf`, anchored in
F2's study-wide min-max and `test_a_context_object_has_no_score_and_scores_nobody`.
A recorded probe preserves all 200 people's original five ratings (fixture seed 3):
relabelling the already-rated Voda as SECONDARY leaves the rescaled pair matrix unchanged;
adding a sixth rated SECONDARY item at alternating scale endpoints leaves the original raw
pair matrix unchanged but changes the five originals' rescaled matrix. For example the
Kava/Caj relation moves from `0.12779057728514173` to `0.5423263190416822`.
This does not claim primary scores remain unchanged on relabelling: their own included
pairs change with the roles. The exact reproducible probe is preserved with the candidate
artifacts. Ask the audit author whether SECONDARY items belong in F2's normalization universe,
or whether the acceptance promise means only that their own pairs do not contribute to
PRIMARY scores. Do not silently alter the canonical formula or treat this as a presentation
choice; no methodology decision or message to the author was made by this check.

## Doc follow-up

Once each boundary is demonstrated, update `research-journey.md` with its current graph and
acceptance limits in a docs-only PR. Reconcile completed/superseded status narratives with the
owning plan files; do not create another progress index. Describe any implemented simulation,
materialization and artifact-reuse entry points in CLAUDE/ARCHITECTURE only after they exist.
No independent technical review has been completed by this slice.

A3 (2026-10-12) follow-ups for the docs PR:
- A3b: delete the `src/server.js` row from CLAUDE.md's map (`CLAUDE.md:671`) and the legacy-stub
  row of ARCHITECTURE.md (`:56`); mark `overview.md` "Next" item 8 done; in
  `docs/architecture/README.md:116`, `docs/migration/status.md:58, 395, 499-528` and
  `docs/migration/parity-matrix.md:212` (hand-written table) say the stub was removed, citing
  this PR. ADR 0001 stays as written: it is history.
- CLAUDE.md `analysis.py` "registered by no composition yet" (`:210-212`) is stale: it is
  registered behind `AIA_AI_ANALYSIS_ENABLED` (`registry.py:79-83, 119-128 @ cd6da1e1`); the
  executors map also lacks `report.py` and `sociomapping_report.py`.
- `research-journey.md:100-114, 517-527`, `docs/migration/status.md:3-6, 337-339, 385-392`,
  `docs/architecture/README.md:160-168` and `overview.md:14-16, 31-37, 157-196, 248-256, 503-512`:
  bring each in line with the plan files, or replace the narrative with a pointer to
  `tools/progress.py`, rather than maintaining a second status.
- `packages/aia_core/src/aia_core/domain/simulation/reference.py:131` cites
  `.planning/PROGRESS.md`; the decision now lives in `overview.md` (code change, next A3c PR).
- F3 into `open-items.md` with an OI number, as a hypothesis until reproduced.
F1 needs a docs-only follow-up alongside the existing AGENTS.md jsdom guidance: Blob.text()
is also absent; captured download bytes can use the existing arrayBuffer() test stand-in.

The following PR 187-193 follow-up checklist was recorded before merge. PR 194 now applies
the shared-document updates, including OI-88 closure; check its actual diff before treating
an entry as outstanding. The addition/relabel clarification and this plan's F1 guidance
remain this plan's own follow-up where not already covered:

| Source | Required documentation follow-up |
| --- | --- |
| PR 187 | CLAUDE map: pinned methods/default/readers and start/retry; deterministic-engine stored spec contracts and run pins; ARCHITECTURE versioned contracts coexist |
| PR 188 | CLAUDE: spec contract 3, pairs, models_v3/engine_v2 and uncomputed respondent/terrain outputs; deterministic-engine sections 2/5/8; methodology decision identifies aia-sociomap-2; sociomapping-engine chunk 7's SOMECS contract collision in its own plan PR |
| PR 189 | CLAUDE and research-journey: sociomap_rating/context_objects inputs; open-items: F-S3-1 author question with the addition/relabel distinction above |
| PR 190 | CLAUDE and research-journey: SpecSelection recorded, applied false; open-items: identity fixed, actual selection application still open |
| PR 191 | research-journey: collectability versus sociomap_support |
| PR 192 | No additions beyond earlier slices |
| PR 193 / deep-research-web-search section 16 | ADR 0021 consequences: interpretation enqueue/execute and target-derived mission; close OI-88 with landed anchors; CLAUDE interpretation module, enqueue/retry and route; deep-research architecture route, mission table and mission-mismatch/lineage-changed errors; remove obsolete interpretation-not-ready descriptions |

AGENTS.md's robots.txt parser guidance in the Deep Research plan's section 16 belongs to
the separately identified robots fix, not automatically to PR 193. Include it only after
checking that fix's landing and current documentation; F1's Blob guidance is this plan's
separate follow-up. Preserve the distinction between completed backend work, unfinished
product consumers and unresolved methodology. The user explicitly authorized publishing
these plans on 2026-10-08; implementation, merge and deployment are separate actions.

## Disposition (MP3, 2026-10-26)

**CLOSE A4 and A5; keep A3 optional**, accepted (the product owner in the Decision Review,
2026-10-26, relayed by the PM coordinator: "Accept: CLOSE A4 and A5; keep A3 optional"). A4 and A5
define an older four-area MVP with Simulation; `mvp-acceptance-harness` replaces them. A3 (one
measured simplification at a time) stays optional. The chunks are left as they are; the owner closes
A4 and A5 with a pointer to `mvp-acceptance-harness`.
