# MVP execution contracts and evidence

Planning reconciliation, 2026-10-20, against master-plan head `0d525bc8` and the
acceptance-only PR #503 at `ac92b3a3`. This document makes the master register and
child chunks executable together. It neither marks implementation done nor
replaces a child plan's progress or an accepted methodology decision.

The master owns scope/dependencies; each child owns implementation and status.
If one changes, edit both in the same planning PR. Product/methodology choices
stay in [the owner packet](mvp-owner-decisions.md), indexed by master §11.4.
An unanswered decision blocks its consumers; it does not block independent
contract proposals, refusal tests or fixture preparation. No provisional rule
may become an approved numerical result because other work is ready.

## Predecessors across plans

`Needs` contains row ids from this table. These are merge/integration prerequisites,
not a command to build every lane serially. The development plan's wave gates still apply globally. A contract may be proposed while a
decision is open; a runtime consumer requires the contract accepted and its
producer implemented. Wave numbers are earliest integration waves, not dates.

| ID | Wave | Deliverable and owner | Needs | Consumer and observable proof |
|---|---|---|---|---|
| E01 | W0 | S3: `mvp-acceptance-harness#3`, `mvp-acceptance-harness#4`, `mvp-acceptance-harness#9`, `mvp-acceptance-harness#14` | — | One collected acceptance tree, registered marker and shared recorded providers; #503's prose/machine statements are reconciled; deliberately failing coverage fails CI |
| E02 | W0 | S1/S3: `lead-orchestration#LO0`, `working-copy-edit-ops#WCE0`, `mvp-master-plan#M4` | — | Money, authority, complete text/structural edit vocabulary and M3 ledger-subject contract reviewed before dependent migrations; default automatic acceptance is text-only |
| E03 | W0 | S1: `lead-orchestration#LO9a`, `lead-orchestration#LO15`; S3: `develop-spend-attribution#5` compatibility contract | E02 | Worker spec fixture and server confirmation rule; direct agent start/rebuild cannot evade the threshold or forge a human confirmation |
| E04 | W0 | S2: `run-qc-and-checkpoint#RQC9`, `run-qc-and-checkpoint#RQC10`; S3: `client-data-in-analysis#8a` | E01 | Single n authority, HTTP population double and proposed Brief-material signature; no client dataset admitted by attaching it |
| E05 | W0 | Operator/S3: `mvp-master-plan#M6`, `mvp-master-plan#M7`; S2: `deep-research-web-search#51`, `deep-research-web-search#54` | E01 | Separate no-call composition readiness from approved live route probes; operator evidence remains required; early probes prove reach only |
| E06 | W1 | S1: `working-copy-edit-ops#WCE1`, `working-copy-edit-ops#WCE2`, `working-copy-edit-ops#WCE5`, `working-copy-edit-ops#WCE6` | E02 | Stable ids, one writer including import/reuse/autosave, item conflicts and atomic dependent groups; locked-write refusal tested from every writer |
| E07 | W1 | S1: `lead-orchestration#LO1`, `lead-orchestration#LO2`, `lead-orchestration#LO3`, `lead-orchestration#LO10` | E02, E03 | Atomic envelope/holds, issued authority, immutable start pins and card revision; stale card and concurrent overspend refuse before dispatch |
| E08 | W1 | S2: `run-qc-and-checkpoint#RQC0`, `run-qc-and-checkpoint#RQC1`, `run-qc-and-checkpoint#RQC2`, `run-qc-and-checkpoint#RQC4a`, `run-qc-and-checkpoint#RQC7` | E03, E04 | Durable respondent/paid-call recovery, deterministic QC flags and event payload before Fieldwork UI; uncertain dispatched calls never replay automatically |
| E09 | W1 | S3: `client-knowledge-lifecycle#K3`, `client-knowledge-lifecycle#K4`, `client-knowledge-lifecycle#K8`; S1: `lead-orchestration#LO13` | E02 | Reviewed revisions, frozen eligible context and capture/import semantics; accepted client-level paid-work exception recorded separately from study-stage starts |
| E10 | W1 | S1: `lead-orchestration#LO4`, `lead-orchestration#LO5`, `lead-orchestration#LO6`, `lead-orchestration#LO7`, `working-copy-edit-ops#WCE4`, `working-copy-edit-ops#WCE10`, `working-copy-edit-ops#WCE12` | E06, E07, E08, E09 | Minimum plan card in the existing Lead pane, direct typed human start, continuation and two-person journey; no wait for W4's richer cards |
| E11 | W1 | S1: `lead-orchestration#LO8`; S2: `evidence-integrity#6`, `evidence-integrity#8`, `run-qc-and-checkpoint#RQC3` | E02, E08 | Bounded ResultsContext, admitted/suppressed result API, proposed two-origin contract, run-derived MaterialRule/lineage; unapproved module prose stays unapproved |
| E12 | W1 | S2/S3: `deep-research-web-search#52`, `deep-research-web-search#53`, `deep-research-web-search#55` | E02, E05 | OPEN posture pinned at enqueue/retry, one cost ceiling used by API and worker, live I-R record with required archive/connector evidence; missing archive leaves I-R BLOCKED |
| E13 | W1 | Method owner/S2: `sociomap-formula-corrections#0b`, `sociomap-formula-corrections#I0`, `segment-maps-and-drilldown#0a` | — | Approved decisions and pinned input/descriptor contract before affected W2 numerical behavior; proposal/fixture preparation may proceed, approval cannot be inferred from completed code |
| E14 | W2 | S2/S3: `sociomap-formula-corrections#I1`, `sociomap-formula-corrections#I3`, `sociomap-formula-corrections#3`, `segment-maps-and-drilldown#1`, `segment-maps-and-drilldown#5`, `client-knowledge-lifecycle#K5` | E10, E11, E12, E13 | Actual population/own-dimension values reach respondents, descriptors, filters and map consumers; missing inputs refuse; changing only a hash is insufficient proof |
| E15 | W2 | S1/S3: `working-copy-edit-ops#WCE8`, `working-copy-edit-ops#WCE9`, `working-copy-edit-ops#WCE11`, `report-delivery#RD3`, `report-delivery#RD4`, `research-lead-workbench#20`, `research-lead-workbench#22` | E06, E11, E12, E14 | Declare/unlock editor, recorded undo before structural auto-accept, real Results/Sociomap/Audience/Dimensions consumers and approved stored snapshot; view operations preserve numerical hash |
| E16 | W2 | S1: `lead-orchestration#LO11` | E06, E09, E10 | Persistent Lead-file history/handover; admin file access tested separately from private turns; private proposal text cannot leak through shared activity |
| E17 | W3 | S2/S3: `client-data-in-analysis#0`, `client-data-in-analysis#2`, `client-data-in-analysis#3`, `client-data-in-analysis#8`, `client-data-in-analysis#9`, `evidence-integrity#8` | E04, E09, E11 | Accepted ADR 0027 and contract before runtime; pinned analysis copy excludes personal/unnamed columns; client data and modelled evidence stay distinct through run node and fingerprint |
| E18 | W3 | S3/S2: `report-delivery#RD6`, `run-qc-and-checkpoint#RQC4`, `run-qc-and-checkpoint#RQC5`; S1: `lead-orchestration#LO9b` | E03, E08, E11, E17 | First the semantic-edit/replacement ADRs and accept-result contracts; then worker bindings/proposals; replacement additionally waits for approved weighting/support and preserves the original run |
| E19 | W3 | S1/S2: `system-prompts-settings#7`, `system-prompts-settings#13` | E03, E11, E18 | Eight analysis pins reach assembly, reuse identity, repairs and usage; all eleven worker slots wired; queued work keeps its pin, new activation changes new work only |
| E20 | W3 | S2/S3: `evidence-integrity#1`, `evidence-integrity#7`, `client-data-in-analysis#5`, `report-delivery#RD0`, `report-delivery#RD1`, `report-delivery#RD5`, `research-lead-workbench#21` | E15, E17, E18, E19 | Admitted findings plus separately labelled external/client context; full Report artifact hosts approval/export; revised wording invalidates approval without recollecting fieldwork; no-finding behavior follows MVPQ-04 |
| E21 | W3 | S2/S3: `deep-research#4`, `develop-spend-attribution#5`, `production-environment#PE7` | E02, E12 | Tool ledger/migration M11 and profile accounting complete before final accounting; E03 already supplies model identity versus invocation-target compatibility before early configuration; legacy reservations stay explicit and no call is charged twice |
| E22 | W4 | S2/S3: `deep-research-web-search#25`, `deep-research-web-search#26`, `deep-research-web-search#39`, `deep-research-web-search#27`; S1: `research-lead-workbench#23` | E12, E20, E21 | Approved evaluation metrics/thresholds and separate allowance precede final live 27; Design and Interpretation paths use captured sources and budget; mature conversation cards consume working contracts |
| E23 | W4 | S3: `study-data-lifecycle#SDL0`, `study-data-lifecycle#SDL1`, `study-data-lifecycle#SDL5`, `study-data-lifecycle#SDL6`, `production-environment#PE9` | E21 | Accepted residual-retention/audit policy before M12; delete/restore exercise proves the independent journal is replayed before serving restored traffic |
| E24 | W5 | S3/all: `mvp-acceptance-harness#5`, `mvp-acceptance-harness#10`, `mvp-acceptance-harness#13`, `client-knowledge-lifecycle#K7a` | E10, E15, E16, E20, E22, E23 | All fifteen full criteria, all eleven browser artifacts and negative cases at one pinned release candidate; research intake→knowledge→dimension→report→reuse proven without a hidden Simulation prerequisite |
| E25 | W5 | S3/operator: `mvp-acceptance-harness#1`, `mvp-acceptance-harness#6`, `mvp-acceptance-harness#7`, `mvp-acceptance-harness#11`, `mvp-acceptance-harness#12`, `production-environment#PE8`, `production-environment#PE9` | E24 | Budget approved before paid dispatch, candidate held stable for tier B, costs/unknowns reconciled and production checklist evidenced; production release remains a separate recorded act |

The table names the earliest contract and consumer waves. W0 cost planning and
record schema work in E25's chunks begin earlier; E25 is the final combined proof.
Production infrastructure PE0/PE1/PE2/PE3/PE4 can progress alongside W1, with
PE5/PE6/PE7 completing before a release candidate needs them. No paid or write
operation is performed by this planning PR.

## Gate records

| Gate | Required evidence | Does not establish |
|---|---|---|
| I-0 | Owners, accepted prerequisites for the next work, one migration head, collected/working harness and current acceptance statements | Full AC-06 recovery, AC-07 impact or AC-03 worker completeness |
| I-1 | Available design workers, shared edits, card/envelope/human authority, checkpoints and frozen study context; HTTP plus the relevant browser journey | Remaining W3 worker bindings, analysis pins or every artifact |
| I-R | Required live reach probes, OPEN/CLASSIFIED/retry tests, effective composition/status; archive remains required until explicitly changed | Retrieval/verification quality or final Deep Research acceptance |
| I-2 | Approved pinned methods, actual descriptor/dimension consumers, Results/map UI and snapshot proof | Methodology approval from a passing fixture, or report delivery from a component test |
| I-3 | Evidence/client-data admission, all worker/prompt contracts, report version/approvals and DOCX/PDF proof | Tier B or a production release |
| I-4 | Final Deep Research evaluations and the full Design/Interpretation/source/knowledge/report path | Complete AC-01–15 or total study billing from model-only AWS costs |
| I-5 | Full tier A including browser, live tier B within its approved allocation, production readiness and recorded release | Any unknown/skipped/refused requirement being counted as PASS |

I-0–I-3 may contain coverage of an AC without completing that AC. The final
record reports each entire criterion PASS / FAIL / NOT_EXECUTED / BLOCKED with
its reason. The full AC-03 proof waits for W3; final acceptance waits for W5.
This preserves the release scope while making intermediate gates attainable.

Each proof pins the application/deployment SHA, acceptance version, fixture and
artifact hashes, methodology/data/contract versions and prompt/model identities.
Keep the relevant HTTP trace, browser trace/screens and ledger/cost evidence under
the acceptance record's existing artifact mechanism. Evidence from a changed
candidate is re-evaluated for affected criteria; a live smoke or model-generated
audit never substitutes for the relevant proof.

## Starting work and estimating delivery

Start bounded W0 work whose policy is already settled: server confirmation,
worker/edit contracts, fixtures/harness, current configuration visibility and
operator evidence preparation. In parallel, route MVPQ-03/MVPQ-10/MVPQ-12 to the methodology
owner and the remaining product choices to the product owner. The scope and
decision owners are roles until an actual person/session accepts the lane.

Before promising end-Q1-2027, S1/S2/S3 each record capacity, remaining chunk-group
effort ranges, reviewer/migration availability, owner-decision response dates and
operator provisioning dates. The plan currently has no measured delivery estimate.
The critical sequence is shared contracts → W1 working-copy/Lead → method-backed
maps/dimensions → admitted evidence/report/workers → final research/acceptance →
release. An unresolved methodology or operator predecessor moves the forecast;
it never silently reduces scope.

## Planning readiness

Planning ownership/dependencies are ready for bounded work only when references
resolve, no integration dependency points to a later wave, and the relevant
decision/ADR/contract is accepted. The full plan is ready for implementation when
every affected decision has a recorded disposition, the parallel crosscheck's
verified final findings have a disposition, and lane owners accept their chunks.
This planning PR does not claim those external decisions or that audit are done.
