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
| AC-01 | Researcher and reviewer authenticate through the identity seam; the study is provisioned as Organization → Client → Study; every call is study-scoped; another client's user gets **404, not 403**, on every study route | ADR 0019 |
| AC-02 | The study is worked in the **Research Lead workbench**: the Lead beside the eleven step artifacts of the canonical V2 prototype, navigator on top, Czech. **Every AI action is started through the Lead** (no manual AI button); a paid step starts only inside what a person approved: an **approval card**, an **approved plan** whose steps the Lead runs inside the study's envelope, or a typed start by a person (the model never supplies a person's confirmation; a gate the plan does not cover parks); every start is held to the study's budget and recorded in the approval ledger, and the spend limit stays a separate per-start confirmation threshold; the Lead's edits are proposals a person accepts, applied without a click only where the researcher chose; the Lead quotes no number its context does not hold | MVP-3, 8, 13, 14, 15; ADR 0026 |
| AC-03 | From the brief, the Lead's workers produce the design, questionnaire, audience and dimensions as proposals; each accepted proposal becomes a Design Revision. Every worker's prompt is editable and pinned on the job that used it; no silent provider fallback | MVP-12, 32; ADR 0020 |
| AC-04 | A run's cost ceiling is shown before it starts, reserved against the study's budget (`budget_usd`) under the study-row lock, held to the envelope when an approved plan starts it, and confirmed by a person when it reaches the spend limit (`spend_confirm_usd`: a confirmation threshold, never the cap); a deliberately exhausted budget **parks** in `AWAITING_BUDGET` without spending, and concurrent starts cannot exceed it | ADR 0019 gate 2 |
| AC-05 | Fieldwork draws AI respondents from LIVE `v17_4_0` through **one** canonical loader, after the integrity gate: audience filters and selected dimensions reach the respondents, the weight is declared (removing it **fails the run**), facts are answered by code, and the population version and weight identity are in provenance | ADR 0024 |
| AC-06 | Killing the worker mid-stage loses no paid work: each answered respondent and its paid-call identity are checkpointed, a restart resumes after them, and a possibly-billed call goes to `RECOVERY_REQUIRED` rather than being retried. An analysis-only retry reuses the frozen dataset | — |
| AC-07 | An edit after fieldwork reopens exactly the stages the impact preview names and reuses every other stage's artifacts | — |
| AC-08 | Every number in a result is an admitted claim: effective-n suppression, intervals, **one field-policy authority** (the population contract's 115 client-measurable fields), `RELIGION` refused client-facing. **Every key finding cites admitted evidence** or is refused; 18.6.6's run QC shows as warnings, never a gate | MVP-23, 24, 25, 28, 29 |
| AC-09 | The results hold an **object, a respondent and a segment map** (segments by the study's dimensions, optionally clustered), each under the method pinned at run start with the Sociomap register's status; the Sociomap artifact filters and drills down to one respondent; a drag changes the view and nothing else | MVP-4, 16, 17 |
| AC-10 | The client's document, dataset and web page are taken in, read and proposed as knowledge a person accepts; a client dimension is materialized as that client's owned child and used by a run. The client dataset is used in analysis only under an accepted **data contract**, personal columns dropped, its numbers graded **client-reported**, shown beside the modelled results or as a benchmark, never mixed into one number | MVP-7, 18, 19; ADR 0027 |
| AC-11 | Design Research runs live **on the full design** through the approved search routes (Brave, public fetch and the connectors) under the client's **data posture**: an OPEN client's run proceeds, a CLASSIFIED client's run is refused whole; the posture is pinned when the run is enqueued and a retry copies it; every finding is a quote in a captured source; a person adds a checked source to the client's knowledge in one click; accepted findings appear as cited context in the report (through an Interpretation Research run, budgeted with the Design Research run), never as respondent evidence; the run's sources are kept as a dataset | MVP-26, 27; ADR 0017, 0021 |
| AC-12 | The same client's past study is found in project memory and its design reused with its citation and labels; another client's studies cannot be found | PM-1 |
| AC-13 | The internal and client reports (DOCX and PDF) pass the evidence audit and the legal source-use gate. The client report carries only approved maps and labelled modelled and client-reported numbers, **no analysis prose**; the client receives only **approved exports**: the report and each map snapshot are approved separately, by the researcher or, where the client or the study turns self-approval off, by a different person, and a download of an unapproved or stale version is refused | MVP-2, 10 |
| AC-14 | Configuration is typed and recorded on the run; a malformed edition file refuses to start | — |
| AC-15 | Every number in the report traces to provenance (fingerprints, provider, model, prompt version, population version, weight identity, data contract); model spend reconciles to AIA's usage ledger within USD 0.01 and agrees with the develop-tagged AWS cost record; tool and search spend, open reservations and uncertain calls are reported on their own lines, and cloud billing lag is recorded, never read as zero | MVP-30 |

## 4. Outcome

The run produces its own evidence, stored as artifacts of the study:

- the delivered reports, the approved map snapshots and their approval records,
- an acceptance record — one line per criterion: `PASS` / `FAIL` with the observation that decided it,
- the `parity_status.py` report from the same commit, as information.

Any `FAIL`, or any criterion not observed, fails the acceptance. There is no partial acceptance.

## 5. Where it will live

`tests/acceptance/test_mvp_acceptance.py`, marked `acceptance`, driven over HTTP. It lands with the
first criterion that can pass end to end, and it is **not** a runtime-skipped placeholder before
then. Until it exists, `parity_status.py` reports the acceptance as `NOT_RUNNABLE`.

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
