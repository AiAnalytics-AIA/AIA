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
| E03 | W0 | S1: `lead-orchestration#LO9a`, `lead-orchestration#LO15`; S3: `develop-spend-attribution#5a` compatibility contract | E02 | Worker spec fixture and server confirmation rule; direct agent start/rebuild cannot evade the threshold or forge a human confirmation |
| E04 | W0 | S2: `run-qc-and-checkpoint#RQC9`, `run-qc-and-checkpoint#RQC10`; S3: `client-data-in-analysis#8a` | E01 | Single n authority, HTTP population double and proposed Brief-material signature; no client dataset admitted by attaching it |
| E05 | W0 | Operator/S3: `mvp-master-plan#M6`, `mvp-master-plan#M7`; S2: `deep-research-web-search#51`, `deep-research-web-search#54` | E01 | Separate no-call composition readiness from approved live route probes; operator evidence remains required; early probes prove reach only |
| E06 | W1 | S1: `working-copy-edit-ops#WCE1`, `working-copy-edit-ops#WCE2`, `working-copy-edit-ops#WCE5`, `working-copy-edit-ops#WCE6` | E02 | Stable ids, one writer including import/reuse/autosave, item conflicts and atomic dependent groups; locked-write refusal tested from every writer |
| E07 | W1 | S1: `lead-orchestration#LO1`, `lead-orchestration#LO2`, `lead-orchestration#LO3`, `lead-orchestration#LO10` | E02, E03 | Atomic envelope/holds, issued authority, immutable start pins and card revision; stale card and concurrent overspend refuse before dispatch |
| E08 | W1 | S2: `run-qc-and-checkpoint#RQC0`, `run-qc-and-checkpoint#RQC1`, `run-qc-and-checkpoint#RQC2`, `run-qc-and-checkpoint#RQC4a`, `run-qc-and-checkpoint#RQC7` | E03, E04 | Durable respondent/paid-call recovery, deterministic QC flags and event payload before Fieldwork UI; uncertain dispatched calls never replay automatically |
| E09 | W1 | S3: `client-knowledge-lifecycle#K3`, `client-knowledge-lifecycle#K4`, `client-knowledge-lifecycle#K8`; S1: `lead-orchestration#LO13` | E02 | Reviewed revisions, frozen eligible context and capture/import semantics; accepted client-level paid-work exception recorded separately from study-stage starts |
| E10 | W1 | S1: `lead-orchestration#LO4`, `lead-orchestration#LO5`, `lead-orchestration#LO6`, `lead-orchestration#LO7`, `working-copy-edit-ops#WCE4`, `working-copy-edit-ops#WCE10`, `working-copy-edit-ops#WCE12` | E06, E07, E08, E09 | Minimum plan card in the existing Lead pane, direct typed human start, continuation and two-person journey; no wait for W4's richer cards |
| E11 | W1 | S1: `lead-orchestration#LO8`; S2: `evidence-integrity#6`, `evidence-integrity#8a`, `run-qc-and-checkpoint#RQC3` | E02, E08 | Bounded ResultsContext, admitted/suppressed result API, proposed two-origin contract, run-derived MaterialRule/lineage; unapproved module prose stays unapproved |
| E12 | W1 | S2/S3: `deep-research-web-search#52`, `deep-research-web-search#53`, `deep-research-web-search#55` | E02, E05 | OPEN posture pinned at enqueue/retry, one cost ceiling used by API and worker, live I-R record with required archive/connector evidence; missing archive leaves I-R BLOCKED |
| E13 | W1 | Method owner/S2: `sociomap-formula-corrections#0b`, `sociomap-formula-corrections#I0`, `segment-maps-and-drilldown#0a` | — | Approved decisions and pinned input/descriptor contract before affected W2 numerical behavior; proposal/fixture preparation may proceed, approval cannot be inferred from completed code |
| E14 | W2 | S2/S3: `sociomap-formula-corrections#I1`, `sociomap-formula-corrections#I3`, `sociomap-formula-corrections#3`, `segment-maps-and-drilldown#1`, `segment-maps-and-drilldown#5`, `client-knowledge-lifecycle#K5` | E10, E11, E12, E13 | Actual population/own-dimension values reach respondents, descriptors, filters and map consumers; missing inputs refuse; changing only a hash is insufficient proof |
| E15 | W2 | S1/S3: `working-copy-edit-ops#WCE8`, `working-copy-edit-ops#WCE9`, `working-copy-edit-ops#WCE11`, `report-delivery#RD3`, `report-delivery#RD4`, `research-lead-workbench#20`, `research-lead-workbench#22` | E06, E11, E12, E14 | Declare/unlock editor, recorded undo before structural auto-accept, real Results/Sociomap/Audience/Dimensions consumers and approved stored snapshot; view operations preserve numerical hash |
| E16 | W2 | S1: `lead-orchestration#LO11` | E06, E09, E10 | Persistent Lead-file history/handover; admin file access tested separately from private turns; private proposal text cannot leak through shared activity |
| E17 | W3 | S2/S3: `client-data-in-analysis#0`, `client-data-in-analysis#2`, `client-data-in-analysis#3`, `client-data-in-analysis#8`, `client-data-in-analysis#9`, `evidence-integrity#8b` | E04, E09, E11 | Accepted ADR 0027 and contract before runtime; pinned analysis copy excludes personal/unnamed columns; client data and modelled evidence stay distinct through run node and fingerprint |
| E18 | W3 | S3/S2: `report-delivery#RD6`, `run-qc-and-checkpoint#RQC4`, `run-qc-and-checkpoint#RQC5`; S1: `lead-orchestration#LO9b` | E03, E08, E11, E17 | First the semantic-edit/replacement ADRs and accept-result contracts; then worker bindings/proposals; replacement additionally waits for approved weighting/support and preserves the original run |
| E19 | W3 | S1/S2: `system-prompts-settings#7`, `system-prompts-settings#13` | E03, E11, E18 | Eight analysis pins reach assembly, reuse identity, repairs and usage; all eleven worker slots wired; queued work keeps its pin, new activation changes new work only |
| E20 | W3 | S2/S3: `evidence-integrity#1`, `evidence-integrity#7`, `client-data-in-analysis#5`, `report-delivery#RD0`, `report-delivery#RD1`, `report-delivery#RD5`, `research-lead-workbench#21` | E15, E17, E18, E19 | Admitted findings plus separately labelled external/client context; full Report artifact hosts approval/export; revised wording invalidates approval without recollecting fieldwork; no-finding behavior follows MVPQ-04 |
| E21 | W3 | S2/S3: `deep-research#4`, `develop-spend-attribution#5b`, `production-environment#PE7` | E02, E12 | Tool ledger/migration M11 and profile accounting complete before final accounting; E03 already supplies model identity versus invocation-target compatibility before early configuration; legacy reservations stay explicit and no call is charged twice |
| E22 | W4 | S2/S3: `deep-research-web-search#25`, `deep-research-web-search#26`, `deep-research-web-search#39`, `deep-research-web-search#27`; S1: `research-lead-workbench#23` | E12, E20, E21 | Approved evaluation metrics/thresholds and separate allowance precede final live 27; Design and Interpretation paths use captured sources and budget; mature conversation cards consume working contracts |
| E23 | W4 | S3: `study-data-lifecycle#SDL0`, `study-data-lifecycle#SDL1`, `study-data-lifecycle#SDL5`, `study-data-lifecycle#SDL6`, `production-environment#PE9a` | E21 | Accepted residual-retention/audit policy before M12; delete/restore exercise proves the independent journal is replayed before serving restored traffic |
| E24 | W5 | S3/all: `mvp-acceptance-harness#5`, `mvp-acceptance-harness#10`, `mvp-acceptance-harness#13`, `client-knowledge-lifecycle#K7a` | E10, E15, E16, E20, E22, E23, E26 | All fifteen full criteria, all eleven browser artifacts and negative cases at one pinned release candidate; research intake→knowledge→dimension→report→reuse proven without a hidden Simulation prerequisite |
| E25 | W5 | S3/operator: `mvp-acceptance-harness#1`, `mvp-acceptance-harness#6`, `mvp-acceptance-harness#7`, `mvp-acceptance-harness#11`, `mvp-acceptance-harness#12`, `production-environment#PE8`, `production-environment#PE9b` | E24 | Budget approved before paid dispatch, candidate held stable for tier B, costs/unknowns reconciled and production checklist evidenced; production release remains a separate recorded act |
| E26 | W1 | S1: `research-lead-workbench#7`, `research-lead-workbench#11`, `research-lead-workbench#12`, `research-lead-workbench#14`, `research-lead-workbench#15`, `research-lead-workbench#16`, `research-lead-workbench#17`, `research-lead-workbench#18`, `research-lead-workbench#19`, `research-lead-workbench#26`, `working-copy-edit-ops#WCE3a`, `working-copy-edit-ops#WCE3b`, `working-copy-edit-ops#WCE3c`, `working-copy-edit-ops#WCE7` | E03, E06 | The canonical V2 frame and the first six artifacts (Brief, Design, Questionnaire, Sample, Fieldwork, with Audience and Dimensions in E15), the command registry on the worker row, the layout rule, the web store on the server vocabulary and readiness on a working revision; each removes its stage's manual AI starts only with the Lead able to call that stage's worker; browser journey at 1099/1100 px, switch off and by a direct request |

The table names the earliest contract and consumer waves. W0 cost planning and
record schema work in E25's chunks begin earlier; E25 is the final combined proof.
Production infrastructure PE0/PE1/PE2/PE3/PE4 can progress alongside W1, with
PE5/PE6/PE7 completing before a release candidate needs them. No paid or write
operation is performed by this planning PR.

## Every other open chunk of a core plan

The table above names the cross-plan predecessors. This one gives every remaining open chunk of the
plans in master §3.1 an explicit wave, so none is silently unscheduled: the wave of the development plan
where it says one, a child plan's own note, or "proposed here" where nothing did (a proposal, to be
confirmed by the plan's owner). **UNSCHEDULED** is also an assignment: the chunk is in no wave, is not
in the MVP by a decision on record, and needs a scope call from the plan's owner; it is never counted as
done or as dropped. `tools/master_check.py` fails when an open chunk of a core plan is in neither table.

| Chunk | Wave | Basis |
|---|---|---|
| `evidence-integrity#2` | W1 | development plan §3 |
| `evidence-integrity#3` | W1 | development plan §3 |
| `evidence-integrity#4` | W3 | development plan §3 |
| `evidence-integrity#5` | W0 | development plan §3 |
| `sociomap-formula-corrections#I2` | W2 | development plan §3 (I0-I5) |
| `sociomap-formula-corrections#I4` | W2 | development plan §3 (I0-I5) |
| `sociomap-formula-corrections#I5` | W2 | development plan §3 (I0-I5) |
| `sociomap-formula-corrections#4d` | W2 | development plan §3 |
| `sociomap-formula-corrections#2d` | UNSCHEDULED | not in the development plan; the MVP uses `aia-sociomap-3`; the method owner and S2 say: build in W2, or after the MVP |
| `sociomap-formula-corrections#4c` | UNSCHEDULED | build or retire behind F6 + F10: a method-owner decision (`MVPQ-12`); not in any wave |
| `sociomap-formula-corrections#5b` | UNSCHEDULED | the contract-3 map as a DOCX figure; S2 confirms whether `report-delivery#RD4` subsumes it |
| `segment-maps-and-drilldown#0` | W1 | method-owner decisions (`MVPQ-03`); blocks W2 numerical behavior (E13) |
| `segment-maps-and-drilldown#2` | W2 | development plan §3 (1-6) |
| `segment-maps-and-drilldown#3` | W2 | development plan §3 (1-6); AC-09 says "optionally clustered" |
| `segment-maps-and-drilldown#4` | W2 | development plan §3 (1-6) |
| `segment-maps-and-drilldown#6` | W2 | development plan §3 (1-6): the respondent drill-down AC-09 requires |
| `segment-maps-and-drilldown#7` | W2 | proposed here: needs the W1 `ResultsContext` (`lead-orchestration#LO8`) |
| `segment-maps-and-drilldown#8` | W2 | development plan §3, with `research-lead-workbench#20` |
| `audience-catalogue-cpu#4` | W0 | development plan §3 |
| `complete-study-report#B6` | W0 | development plan §3 |
| `deep-research-web-search#1` | W0 | development plan §3 |
| `deep-research-web-search#6` | W2 | development plan §3 |
| `deep-research-web-search#33` | W2 | development plan §3 (33-37 in order) |
| `deep-research-web-search#34` | W2 | development plan §3 (33-37 in order) |
| `deep-research-web-search#35` | W2 | development plan §3 (33-37 in order) |
| `deep-research-web-search#36` | W2 | development plan §3 (33-37 in order) |
| `deep-research-web-search#37` | W2 | development plan §3 (33-37 in order) |
| `deep-research-web-search#38` | W4 | development plan §3 |
| `deep-research-web-search#8` | UNSCHEDULED | source tiers and the reputation register: in no wave; S2 and the owner say whether the MVP needs it |
| `deep-research-web-search#16` | UNSCHEDULED | reopened in #500: procurement has no live source (`deep_research_live.py:364-366`); in or out of the MVP is a scope call, not an omission |
| `deep-research-web-search#20` | UNSCHEDULED | reopened in #500: triage readers have no caller and no key builds the light model; same call |
| `deep-research-web-search#24` | UNSCHEDULED | the operator surface, after 29-32, which are in no wave |
| `deep-research-web-search#31` | UNSCHEDULED | the Sociomap Research Lens (an annotation sidecar): in no wave; Interpretation Research reads the canonical map without it |
| `deep-research-web-search#32` | UNSCHEDULED | the report evidence graph: in no wave; overlaps `evidence-integrity#7` and `report-delivery#RD0` |
| `client-budget#CB5` | W1 | development plan §3 |
| `client-knowledge-lifecycle#K2` | W1 | umbrella: ticks when K2e and K2f do |
| `client-knowledge-lifecycle#K2e` | W1 | development plan §3 |
| `client-knowledge-lifecycle#K2f` | W1 | development plan §3 |
| `client-knowledge-lifecycle#K6` | W3 | development plan §3 |
| `client-knowledge-lifecycle#K7` | POST | the Simulation extension of the consumer proof; the MVP subset is K7a (E24) |
| `client-data-in-analysis#1` | W3 | development plan §3 (0-9) |
| `client-data-in-analysis#4` | W3 | development plan §3 (policy first: `MVPQ-05`) |
| `client-data-in-analysis#6` | W3 | development plan §3 (0-9) |
| `client-data-in-analysis#7` | W3 | development plan §3 (0-9) |
| `research-integrity-report#5` | W1 | proposed here: a USD 0 run on the existing fictional run, needs a deploy |
| `research-integrity-report#6` | W3 | development plan §3 (6-8) |
| `research-integrity-report#7` | W3 | development plan §3 (6-8) |
| `research-integrity-report#8` | W3 | development plan §3 (6-8) |
| `two-roles-human-ai-gates#5b` | W2 | umbrella: ticks when 5b.4 does |
| `two-roles-human-ai-gates#5b.4` | W2 | built by `report-delivery#RD2` to `#RD4` (E15); the development plan lists it in W2 and again in W3, and W2 governs |
| `develop-spend-attribution#1` | W0 | development plan §3, after 5a |
| `develop-spend-attribution#2` | W0 | development plan §3, after 5a |
| `develop-spend-attribution#3` | W5 | development plan §3 |
| `develop-spend-attribution#4` | W5 | development plan §3 |
| `mvp-acceptance-harness#2` | W0 | development plan §3 |
| `mvp-acceptance-harness#8` | W0 | development plan §3 |
| `lead-orchestration#LO12` | W0 | development plan §3: the stage error says who can fix it |
| `lead-orchestration#LO14` | W1 | development plan §3 (Exit I-1) |
| `run-qc-and-checkpoint#RQC6` | W1 | development plan §3 |
| `run-qc-and-checkpoint#RQC8` | W1 | development plan §3 |
| `report-delivery#RD2` | W2 | proposed here: the reader the approvals RD3 and RD4 need |
| `report-delivery#RD7` | W3 | proposed here: with the evidence audit (RD0) |
| `report-delivery#RD8` | W2 | proposed here: the producer rule precedes the first approvals |
| `study-data-lifecycle#SDL2` | W4 | proposed here: before SDL3 and SDL5 |
| `study-data-lifecycle#SDL3` | W4 | proposed here: before SDL5 |
| `study-data-lifecycle#SDL4` | W4 | proposed here |
| `production-environment#PE0` | W0 | proposed here: the ADR precedes PE1 |
| `production-environment#PE1` | W1 | development plan §3 (production applied) |
| `production-environment#PE2` | W1 | development plan §3 |
| `production-environment#PE3` | W0 | proposed here: precedes PE1 apply |
| `production-environment#PE4` | W1 | proposed here |
| `production-environment#PE5` | W3 | proposed here: before a release candidate |
| `production-environment#PE6` | W3 | proposed here: before a release candidate |
| `research-lead-workbench#24` | POST | development plan D16: after the MVP |
| `research-lead-workbench#25` | POST | development plan D16: after the MVP |

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
