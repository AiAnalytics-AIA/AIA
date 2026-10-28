# MVP acceptance test — `MVP-ACCEPT-2`

**The MVP is done when one representative study is created, worked through the Research Lead
workbench and delivered through the production stack, and every criterion below is observed to
pass.** Not before, and not on the strength of green unit tests.

`MVP-ACCEPT-2` replaces `MVP-ACCEPT-1` (2026-10-19). The product owner redefined the MVP that day
(`.planning/overview.md` § MVP roadmap, decisions MVP-1 to MVP-33): the study is worked through the
Research Lead and its eleven step artifacts, maps include respondents and segments, a client's own
data takes part, live Deep Research runs on the full design, and Simulation is out. **Parity with
18.6.6 is no longer a release gate** (MVP-21): AC-14 of `MVP-ACCEPT-1` ("every capability above
reports PASS") is gone, and no capability is a release blocker. The parity suites themselves are
unchanged: they are regression tests of behaviour ported from 18.6.6, and like every test they fail
a build when that behaviour changes (CLAUDE.md §5: a test is never loosened to get green). What
MVP-21 removes is parity as a condition of the MVP release; a deliberate departure from 18.6.6 is
recorded as an intentional difference in `parity-matrix.json`, as before.

This document defines the test. It does not exist as code yet, because much of what it drives is
not built. Its criteria are machine-readable in [`parity-matrix.json`](parity-matrix.json) under
`mvp_acceptance`. A criterion names the 18.6.6 capabilities it exercises, which marks them
`mvp_path` so their parity is reported beside the run; it blocks nothing
(`test_parity_matrix.py::test_parity_blocks_no_release`). Criteria for what 18.6.6 never had (the
Lead, client data, a live search route under the open posture) name no capability.

## 1. The representative study

A Research study, because research is the MVP's deliverable (Simulation is out, MVP-1).

| | |
| --- | --- |
| Client | `acceptance-client` — an AIA-internal client record created for this test. **No client work, no client data, no client names.** |
| Study | `mvp-acceptance`, budget **USD 25** (MVP-20), self-approval **disallowed** |
| Brief | *"How do Czech adults aged 18–65 rate five proposed changes to municipal library services, and which groups would use them?"* Neutral by design: a public-interest topic with no brand |
| Tracked objects | five fictitious service concepts, `service_a` … `service_e` |
| Audience | population mode, age 18–65; selected dimensions applied to the respondents |
| Respondents | AI respondents drawn from the population (`MODELLED_AI_PANEL`), n = 300 |
| Population | LIVE `v17_4_0`, imported losslessly, SHA256 verified; weighting declared: `vaha_strukturalni_2025` |
| Client material | a fictional document (the library's annual summary), a fictional dataset (visits by branch and month, with one personal column the contract must drop), one public web page |
| Project memory | one past fictional study of the same client whose design is reused |
| Deliverables | the internal report and the client report (DOCX and PDF) and approved map snapshots, approved by a second person |

The brief and every fixed input are committed with the test when it lands.

## 2. The production stack

Driven **over HTTP only**, against the same process topology production runs:

- the API behind the `IdentityProvider` seam (Cognito in the deployed tier),
- the worker process draining the PostgreSQL queue,
- PostgreSQL 16 as the source of truth,
- the artifact store (S3 in the deployed tier, EU region),
- the `ModelGateway`, through a route approved under
  [ADR 0008](../architecture/adr/0008-eu-data-residency.md), and the Deep Research search routes
  under the client's data posture (OPEN or CLASSIFIED, MVP-27; the Class B route is deferred).

No repository, domain function or table is touched directly by the test. A back door would test
the back door. Every action a person takes in the workbench (a message to the Lead, an approval
card, an accept) is the route the web client calls.

### Two tiers, both required for release

| Tier | Where | Model and search providers | When |
| --- | --- | --- | --- |
| **A — stack acceptance** | CI, every PR once runnable | recorded, deterministic doubles **behind the `ModelGateway` and the retrieval gate**: the Lead, every worker, the AI respondents, the analysis modules, Deep Research | blocking once runnable |
| **B — live acceptance** | develop, deployed stack | the approved live providers, within the study's USD 25 | before every MVP release, run by a person |

Tier A proves the system; tier B proves the deployment.

Three states are kept apart: *tier A passed* (CI over HTTP, plus real browser journeys for the
criteria that are interactions), *tier B passed* (live on develop, a person, inside the allocation
the harness plan sets per category: model, tool and search spend, the Interpretation run and the
Deep Research evaluations each have a line) and *released* (production, after a restore, a rollback
rehearsal and the delete path). Tier B passing does not release anything.

## 3. Acceptance criteria

The authoritative wording is in `parity-matrix.json`; this is the same list, with the decisions
each one carries.

| Id | The acceptance run must show | Decisions |
| --- | --- | --- |
| AC-01 | Researcher and reviewer authenticate through the IdentityProvider seam (Cognito in the deployed stack); the study is provisioned as Organization -> Client -> Study and every call is study-scoped. A user of another organization gets 404, not 403, on every study route (ADR 0019: within an organization, membership is the access) | ADR 0019 |
| AC-02 | The study is worked in the Research Lead workbench: the Lead's conversation beside the eleven step artifacts of the canonical V2 prototype, the stage navigator on top, the interface in Czech; the Lead stays reachable at every screen width (a compact drawer or a stacked layout, never an alternate AI start). Every AI action is started through the Lead (no manual AI button on any stage), except a client-level source extraction in Client Knowledge, held to its client budget and approval (MVPQ-08); a paid step starts only inside what a person approved: an approval card, an approved plan whose steps the Lead runs inside the study's wallet, or a typed start by a person (the model never supplies a person's confirmation, and a gate the plan does not cover parks); every start is held to the study's budget and recorded in the approval ledger, and the spend limit stays a separate per-start confirmation threshold; the Lead's edits are proposals a person accepts, applied without a click only where the researcher chose (text edits, structural edits per stage). The Lead quotes no number its context does not hold | MVP-3, 8, 13, 14, 15; ADR 0026 |
| AC-03 | From the brief, the Lead's workers produce the research design, questionnaire, audience and dimensions as proposals; each accepted proposal becomes a Design Revision; tracked assumptions are design items with a stable id and a status (an explicitly unverified assumption needs no evidence yet), cited evidence where a status asserts something, and status changes a person accepts. Every worker's system prompt is editable in Settings and pinned on the job that used it; no silent provider fallback | MVP-12, 32; ADR 0020 |
| AC-04 | A run's cost ceiling is shown before it starts, reserved against the study's budget (budget_usd) under the study-row lock, held to the wallet when an approved plan starts it, and confirmed by a person when it reaches the spend limit (spend_confirm_usd: a confirmation threshold, never the cap); a deliberately exhausted budget parks in AWAITING_BUDGET without spending, and concurrent starts cannot exceed it | ADR 0019 gate 2 |
| AC-05 | Fieldwork draws AI respondents from LIVE v17_4_0 through the one canonical loader, after the integrity gate, as MODELLED_AI_PANEL: the audience filters and the selected dimensions reach the respondents, the weight is declared (removing it fails the run instead of reweighting), facts are answered by code, and the population version and weight identity are in provenance | ADR 0024 |
| AC-06 | Killing the worker mid-stage loses no paid work: each answered respondent and its paid-call identity are checkpointed, a restart resumes after them, and a possibly-billed call goes to RECOVERY_REQUIRED rather than being retried. An analysis-only retry reuses the frozen dataset | — |
| AC-07 | An edit after fieldwork reopens exactly the stages the impact preview names and reuses every other stage's artifacts | — |
| AC-08 | Every number in a result is an admitted claim: effective-n suppression on every client-facing number, intervals required, one field-policy authority (the population contract's 115 client-measurable fields), RELIGION refused client-facing. Every key finding of an analysis module cites admitted evidence or is refused. 18.6.6's run QC is shown as warnings, never a gate. Open answers are coded per answer under a versioned method and their counts are admitted claims, never produced from prose. A module with no supported finding blocks report composition, approval and export until resolved; a diagnostic is not a finding | MVP-23, 24, 25, 28, 29 |
| AC-09 | The results hold an object map, a respondent map and a segment map (segments defined by the sampler's stored descriptors, optionally clustered), each computed under the method pinned at run start and carrying the Sociomap register's status; the Sociomap artifact filters and drills down to one respondent's stored attributes and answers, never generated persona prose; a drag changes the displayed layout and nothing else | MVP-4, 16, 17 |
| AC-10 | The client's document, dataset and public web page are taken in, read and proposed as knowledge a person accepts; a client dimension is materialized as that client's owned child population and used by a run. A client dataset is used in analysis only under a data contract a person accepted, its personal columns dropped, its numbers graded client-reported and shown beside the modelled results or as a benchmark, never mixed into one number (ADR 0027) | MVP-7, 18, 19; ADR 0027 |
| AC-11 | Design Research runs live on the full study design through the approved search routes (Brave, public fetch, a connector probed live and the archive route, each named in the run's record) under the client's data posture: an OPEN client's run proceeds, a CLASSIFIED client's run is refused whole, the posture is pinned when the run is enqueued and a retry copies it; every finding is a quote grounded in a captured source; a person adds a checked source to the client's knowledge in one click; accepted findings appear as cited context in the report (through an Interpretation Research run, budgeted with the Design Research run), never as respondent evidence, and the run's sources are kept as a dataset | MVP-26, 27; ADR 0017, 0021 |
| AC-12 | The same client's past study is found in project memory and its design reused in the new study with its citation and labels; another client's studies cannot be found | PM-1 |
| AC-13 | The internal report and the client report (DOCX and PDF) pass the client deliverable's gate: no source marked "Interní dokument", no drill-down content, no number without an admitted claim, and an unsupported claim blocks approval (MVPQ-09). The internal report states each tracked assumption with its status and support and the admitted coded counts with their method, version and limits (raw answers and examples stay labelled source or context, never numerically admitted evidence); the client report carries them only as approved, labelled content, and carries only approved maps and labelled modelled and client-reported numbers, no analysis prose; a client receives only approved exports: the report and each map snapshot are approved separately, by the researcher or, where the client or the study turns self-approval off, by a different person, and a download of an unapproved or stale version is refused | MVP-2, 10 |
| AC-14 | Typed settings refuse a malformed value by name: the API and the worker do not start on one. Each run records its composition digest (the settings and the composition it ran under), served with the run. AIA has no edition file: 18.6.6's was replaced by typed configuration | D-09 |
| AC-15 | Every number in the report traces to provenance (fingerprints, provider, model, prompt version, population version, weight identity, data contract); model spend reconciles to AIA's usage ledger within USD 0.01 and agrees with the develop-tagged AWS cost record within USD 0.01; tool and search spend, open reservations, uncertain calls and non-provider infrastructure charges (compute, storage, database) are reported on their own lines, and cloud billing lag is recorded, never read as zero | MVP-30; W0Q5 (2026-10-28) |

### 3.1 What each tier proves

A criterion passes only when both tiers pass it. Tier A proves what recorded providers can;
tier B adds what only the live deployment shows. The machine-readable form is each criterion's
`tier_a` and `tier_b` in `parity-matrix.json`, and the tier-A tests that prove it are its `tests`.

| Id | Tier A (CI, over HTTP, recorded providers) | Tier B (develop, live, a person) |
| --- | --- | --- |
| AC-01 | The development identity provider behind the IdentityProvider seam; the study provisioned over HTTP after the declared operator bootstrap; every study route answers another organization's user 404, the same 404 a study that does not exist gets | Cognito sign-in for both people on develop; the same probe of every study route against the deployed API |
| AC-02 | The workbench's routes over HTTP on the recorded Lead and workers, and the browser journeys as a line of their own (harness chunk 10): every AI start through the Lead, every paid step from an approval card, an approved plan or a typed start, each in the approval ledger | A person works the study in the deployed workbench at every supported width, the Lead and the workers on the live route |
| AC-03 | Each worker's recorded answer becomes a proposal and an accepted one a Design Revision; the tracked assumptions and their status changes; each job pins the prompt it used; a refused route fails by name, never falls back | The live workers on the brief, each job's pinned prompt read back |
| AC-04 | On recorded calls at test prices: the ceiling shown before the start, reservations under the study-row lock, an exhausted budget parked in AWAITING_BUDGET with nothing spent, concurrent starts held to the budget, the spend-limit confirmation in the approval ledger | The same on live prices, inside the allocation's lines (tests/acceptance/allocation.json) |
| AC-05 | Fieldwork from the recorded population double (run-qc-and-checkpoint RQC10) through the one loader: filters and dimensions reach the respondents, a removed weight fails the run, the population version and weight identity in provenance | LIVE v17_4_0 on develop, its SHA256 verified, MODELLED_AI_PANEL respondents on the live route |
| AC-06 | A worker process killed mid-fieldwork resumes after the last checkpointed respondent; a possibly-billed recorded call goes to RECOVERY_REQUIRED; an analysis-only retry reuses the frozen dataset | An analysis-only retry on develop (allocation line A09). The kill is not repeated live: until RQC0 a restart repays fieldwork (OI-64), and the record says so |
| AC-07 | An edit after recorded fieldwork: exactly the stages the impact preview names reopen, every other stage's artifacts reused by fingerprint | The same edit on the live study |
| AC-08 | On the recorded run: every number an admitted claim (suppression, intervals, the one field-policy authority, RELIGION refused), every key finding cited or refused, coded counts admitted, a module without a supported finding blocking the report | The same rules held on the live run's results and reports |
| AC-09 | Object, respondent and segment maps from the recorded run under the pinned method, each with the register's status; drill-down to stored attributes; a drag (browser journey) changes the view and nothing else | The live run's maps, and their approved snapshots |
| AC-10 | The document, dataset and page taken in over HTTP and proposed by a recorded extraction, then accepted; a dimension materialized over the recorded population double and used by a run; the dataset under an accepted contract, its personal column dropped, its numbers client-reported | The same on develop, the extraction on the live route charged to the client's budget |
| AC-11 | Recorded retrieval behind RetrievalGate: the posture pinned at enqueue and copied by a retry, a CLASSIFIED client's run refused whole, every finding a quote in a captured snapshot, a checked source added in one click, an Interpretation run's cited context in the report | Live Design and Interpretation runs through Brave, public fetch, a connector and the archive route, each named in the run's record, inside allocation lines A06-A08 |
| AC-12 | Project memory's search and the design's reuse over HTTP, with its citation and labels; another client's studies not found | The fictional past study found and its design reused on develop, over the deployed API |
| AC-13 | The internal and client reports (DOCX and PDF) of the recorded run pass the deliverable's gate; the report and each map snapshot approved separately; an unapproved or stale download refused | The live run's reports, approved by the researcher or, with self-approval off, by another person |
| AC-14 | The API and the worker each refuse a malformed setting at start, by name and with a non-zero exit; a run read over HTTP carries its composition digest | The live run's composition digest equals the deployment's |
| AC-15 | Every ledger ref of the recorded run's reports resolves to its provenance; recorded model spend reconciles to the usage ledger within USD 0.01; tool spend, open reservations and uncertain calls on their own lines | Model spend agrees with the develop-tagged AWS cost record within USD 0.01 (the owner, 2026-10-28, W0Q5), billing lag recorded and never read as zero; infrastructure charges on their own line; each allocation line's actual beside its ceiling |

## 4. Outcome

The run produces its own evidence, stored as artifacts of the study:

- the delivered reports, the approved map snapshots and their approval records,
- an acceptance record — one line per criterion: `PASS` / `FAIL` with the observation that decided it,
- the `parity_status.py` report from the same commit, as information.

Any `FAIL`, or any criterion not observed, fails the acceptance. There is no partial acceptance.

## 5. Where it lives

`tests/acceptance/test_mvp_acceptance.py`, marked `acceptance`, driven over HTTP against the
stack `tests/acceptance/conftest.py` starts: PostgreSQL (`AIA_ACCEPTANCE_DATABASE_URL`), the API
and the worker as processes of their own, after one declared operator bootstrap (`alembic upgrade
head`, then the develop seed: no route creates an organization or its owner). The worker runs
the production composition over recorded model answers (`aia_executors.acceptance_recorded`).
The tree imports nothing it drives. CI runs it in a step of its own and writes its JUnit;
`parity_status.py` gives each criterion its tier-A verdict from the tests it lists (`tests` in
`parity-matrix.json`): `NOT_RUNNABLE` while it lists none, `PASS` only when all of them passed. A
criterion's test lands with the work that makes it runnable, never as a runtime-skipped
placeholder. Tier B is recorded by the person who runs it.

## 6. Not in this test

| Left out | Why | Decided |
| --- | --- | --- |
| Simulation and every scenario / what-if | Out of the MVP | MVP-1 (resolves D9) |
| A client login or client-facing surface | Client View is the approved exports | MVP-2 |
| Report depth tiers | After the MVP | MVP-6 |
| Client-facing analysis prose | Waits on the respondents' holdout validation | MVP-10 |
| The Lead's autopilot and Deep Research from every stage | After the MVP; the autopilot needs an ADR | MVP-3 |
| Promotion of a client's dimension into the shared LIVE population | The data library ends at an owned child | MVP-7 |
| Parity with 18.6.6 as a gate | Information only | MVP-21 |
