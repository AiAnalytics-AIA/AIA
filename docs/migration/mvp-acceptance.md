# MVP acceptance test — `MVP-ACCEPT-1`

**The MVP is done when one representative study is created and delivered
through the production stack, and every capability that path touches has
verified parity with the reference.** Not before, and not on the strength of
green unit tests.

This document defines that test. It does not exist as code yet, because most of
what it drives has not been built. Its criteria are machine-readable in
[`parity-matrix.json`](parity-matrix.json) under `mvp_acceptance`, and each names
the capabilities it exercises. **A capability is a release blocker if and only
if an acceptance criterion names it** — `test_parity_matrix.py` enforces that
equivalence, so the blocker list cannot drift from the test that justifies it.

Run `python tools/parity_status.py` to see how many blockers stand between the
current tree and a runnable acceptance test.

## 1. The representative study

A Research-lifecycle study, because that lifecycle is the product's primary
deliverable and exercises the largest share of the methodology.

| | |
| --- | --- |
| Client | `acceptance-client` — an AIA-internal client record created for this test. **No client work, no client data, no client names.** |
| Study | `mvp-acceptance`, budget USD 25, self-approval **disallowed** |
| Brief | *"How do Czech adults aged 18–65 rate five proposed changes to municipal library services, and which groups would use them?"* Neutral by design: a public-interest topic with no brand, so brand-knowledge gates are exercised by refusal rather than by content |
| Tracked objects | five fictitious service concepts, `service_a` … `service_e` — enough for a Sociomapa |
| Audience | population mode, age 18–65 |
| Sample | n = 300 |
| Population | `v17_4_0`, imported losslessly, SHA256 verified |
| Weighting | declared explicitly: `vaha_strukturalni_2025` |
| Deliverable | client report, reviewed and approved by a second person |

The brief and its fixed inputs are committed with the test when it lands. A
reference demo study may later be added as a second comparison — see "Not in
this test".

## 2. The production stack

Driven **over HTTP only**, against the same process topology production runs:

- the API behind the `IdentityProvider` seam (Cognito in the deployed tier),
- the worker process draining the PostgreSQL queue,
- PostgreSQL 16 as the source of truth,
- the artifact store (S3 in the deployed tier, EU region),
- the `ModelGateway`, through an egress route approved under
  [ADR 0008](../architecture/adr/0008-eu-data-residency.md).

No repository, domain function or table is touched directly by the test. A
back door would test the back door.

### Two tiers, both required for release

| Tier | Where | Model provider | When |
| --- | --- | --- | --- |
| **A — stack acceptance** | CI, every PR once runnable | a recorded, deterministic double **behind the `ModelGateway` protocol** | blocking once the first capability on the path is `IMPLEMENTED` |
| **B — live acceptance** | staging, deployed stack | the approved live provider | before every MVP release, run by a person |

Tier A proves the system; tier B proves the deployment. Tier A alone would let
a provider-contract or residency mistake ship; tier B alone would make the
system testable only by spending money.

## 3. Acceptance criteria

The authoritative wording is in `parity-matrix.json`; this is the same list.
Each criterion names the capabilities it needs.

| Id | The acceptance run must show | Capabilities |
| --- | --- | --- |
| AC-01 | Researcher and reviewer authenticate through the identity seam; the study is provisioned as Organization → Client → Study; every call is study-scoped; another client's user gets **404, not 403**, on every study route | `api.http` |
| AC-02 | From the brief, Deep Research, Research Design and a Questionnaire are produced through the `ModelGateway`: provider and policy resolved per stage, credentials from Secrets Manager, every call on the immutable usage ledger, **no silent provider fallback** | `project.persistence`, `pipeline.stages`, `research.design`, `questionnaire.*`, `ai.gateway`, `ai.credentials`, `ai.provider_policy`, `ai.runtime_policy`, `ai.usage_ledger` |
| AC-03 | Cost is estimated before any paid stage, reserved under the study-row lock and capped per run; a deliberately exhausted budget **parks** in `AWAITING_BUDGET` without spending; cost-mode presets match the reference | `cost.*`, `workflow.config` |
| AC-04 | Fieldwork runs on `v17_4_0` through **one** canonical loader, after the integrity gate; population version and weight identity are in provenance; removing the weight declaration **fails the run** instead of reweighting it | `population.core`, `population.panel_loader`, `population.weighting`, `population.readiness`, `operability.integrity` |
| AC-05 | Audience sufficiency gates the run; segments reproduce the reference within tolerance | `audience.*` |
| AC-06 | Panel facts are never re-invented by a model; no implicitly injected context; raking within tolerance | `respondents.*`, `statistics.calibration` |
| AC-07 | Killing the worker mid-stage loses no work; a possibly-billed paid call goes to `RECOVERY_REQUIRED` rather than being retried; one executor | `workflow.engine`, `workflow.step_execution`, `workflow.dispatch`, `workflow.legacy_dispatch`, `orchestration.cli` |
| AC-08 | An edit after fieldwork reopens exactly the stages the impact preview names and reuses every other stage's artifacts | `pipeline.stages`, `project.persistence`, `artifacts.*` |
| AC-09 | QC, diagnostics and evidence gates fail closed; validation state bound to the system fingerprint; effective-n suppression on every client-facing number; no claim beyond the field policy or `CORE_JOINT_STATUS` | `analysis.*`, `statistics.diagnostics`, `statistics.uncertainty`, `governance.evidence_gates`, `governance.validation_state`, `governance.product_policy`, `governance.anchors`, `results.verification` |
| AC-10 | The results include a Sociomapa computed under a **declared** algorithm; a drag changes the displayed layout and nothing else | `sociomapping.core`, `sociomapping.study_module` |
| AC-11 | The report passes the evidence audit and the legal source-use gate and is delivered only after a reviewer other than its producer approves it | `reports.generation`, `governance.evidence_audit`, `governance.legal`, `results.registry` |
| AC-12 | Configuration is typed and recorded on the run; a malformed edition file refuses to start | `config.environment`, `config.edition` |
| AC-13 | Every number in the report traces to provenance (fingerprints, provider, model, population version, weight identity); spend reconciles to the ledger within USD 0.01 | `artifacts.registration`, `ai.usage_ledger`, `cost.estimation` |
| AC-14 | **In the same CI run**, every capability above reports `PASS` from executed gates and is `IMPLEMENTED` | all of the above |

AC-14 is what keeps the acceptance test honest: a study that happens to finish
while half its capabilities have never been compared with the reference is a
demonstration, not an acceptance.

## 4. Outcome

The run produces its own evidence, stored as artifacts of the study:

- the delivered report and its approval record,
- an acceptance record — one line per criterion: `PASS` / `FAIL` with the
  observation that decided it,
- the `parity_status.py` report from the same commit.

Any `FAIL`, or any criterion not observed, fails the acceptance. There is no
partial acceptance.

## 5. Where it will live

`tests/acceptance/test_mvp_acceptance.py`, marked `acceptance`, driven over
HTTP. It lands when the first capability on the path other than those already
built is `IMPLEMENTED`, and it is **not** a runtime-skipped placeholder before
then: a test that always skips is a signal nobody reads. Until it exists,
`parity_status.py` reports `MVP-ACCEPT-1` as `NOT_RUNNABLE` with its blocker
count.

## 6. Not in this test

| Left out | Why | What would bring it in |
| --- | --- | --- |
| The Simulation lifecycle | A second 13-stage lifecycle; the MVP is scoped to Research | **Decision D7** in `.planning/PROGRESS.md` |
| Data Library ingestion and demo seeding | The MVP uses the published `v17_4_0` population; the demo library's status is reference open decision D4 | D4 in the reference repository |
| A reference demo study as a second comparison | The ten demo studies are client work; comparing against one needs the withheld archive and a data-owner decision | `REF-WITHHELD-REFERENCE-ARCHIVE` |
| Project memory, copilot, results dialogue | No research output depends on them | Product scope change |
