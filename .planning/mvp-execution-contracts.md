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
| E01 | W0 | S3: `mvp-acceptance-harness#1`, `mvp-acceptance-harness#3`, `mvp-acceptance-harness#4`, `mvp-acceptance-harness#9`, `mvp-acceptance-harness#14` | — | The USD 25 allocation table, one ceiling per category, owner-approved before any paid dispatch (a paid probe or run names its line); one collected acceptance tree, registered marker and shared recorded providers; #503's prose/machine statements are reconciled; deliberately failing coverage fails CI |
| E02 | W0 | S1/S3: `lead-orchestration#LO0`, `lead-orchestration#LO16`, `working-copy-edit-ops#WCE0`, `mvp-master-plan#MP4` | — | Money, authority, complete text/structural edit vocabulary and M3 ledger-subject contract reviewed before dependent migrations; default automatic acceptance is text-only |
| E03 | W0 | S1: `lead-orchestration#LO9a`, `lead-orchestration#LO15`; S3: `develop-spend-attribution#5a` compatibility contract | E02 | Worker spec fixture and server confirmation rule; direct agent start/rebuild cannot evade the threshold or forge a human confirmation |
| E04 | W0 | S2: `run-qc-and-checkpoint#RQC9`, `run-qc-and-checkpoint#RQC10`; S3: `client-data-in-analysis#8a` | E01 | Single n authority, HTTP population double and proposed Brief-material signature; no client dataset admitted by attaching it |
| E05 | W0 | Operator/S3: `mvp-master-plan#MP6`, `mvp-master-plan#MP7`; S2: `deep-research-web-search#1` (the owner's Brave sign-off), `deep-research-web-search#51`, `deep-research-web-search#54` | E01 | Separate no-call composition readiness from approved live route probes; operator evidence remains required; a live probe runs only after the sign-off and a named allocation line; early probes prove reach only |
| E06 | W1 | S1: `working-copy-edit-ops#WCE1`, `working-copy-edit-ops#WCE2`, `working-copy-edit-ops#WCE5`, `working-copy-edit-ops#WCE6` | E02 | Stable ids, one writer including import/reuse/autosave, conflicts per `(item_key, field)` (D-06) and atomic dependent groups; locked-write refusal tested from every writer |
| E07 | W1 | S1: `lead-orchestration#LO1`, `lead-orchestration#LO2`, `lead-orchestration#LO3`, `lead-orchestration#LO10` | E02, E03 | Atomic wallet/holds, issued authority, immutable start pins and card revision; stale card and concurrent overspend refuse before dispatch |
| E08 | W1 | S2: `run-qc-and-checkpoint#RQC0`, `run-qc-and-checkpoint#RQC1`, `run-qc-and-checkpoint#RQC2`, `run-qc-and-checkpoint#RQC4a`, `run-qc-and-checkpoint#RQC7` | E03, E04 | Durable respondent/paid-call recovery, deterministic QC flags and event payload before Fieldwork UI; uncertain dispatched calls never replay automatically |
| E09 | W1 | S3: `client-knowledge-lifecycle#K3`, `client-knowledge-lifecycle#K4`, `client-knowledge-lifecycle#K8`; S1: `lead-orchestration#LO13` | E02 | Reviewed revisions, frozen eligible context and capture/import semantics; accepted client-level paid-work exception recorded separately from study-stage starts |
| E10 | W1 | S1: `lead-orchestration#LO4`, `lead-orchestration#LO5`, `lead-orchestration#LO6`, `lead-orchestration#LO7`, `working-copy-edit-ops#WCE4`, `working-copy-edit-ops#WCE10`, `working-copy-edit-ops#WCE12` | E06, E07, E08, E09 | Minimum plan card in the existing Lead pane, direct typed human start, continuation and two-person journey; no wait for W4's richer cards |
| E11 | W1 | S1: `lead-orchestration#LO8`; S2: `evidence-integrity#6`, `evidence-integrity#8a`, `run-qc-and-checkpoint#RQC3` | E02, E08 | Bounded ResultsContext, admitted/suppressed result API, proposed two-origin contract, run-derived MaterialRule/lineage; unapproved module prose stays unapproved |
| E12 | W1 | S1/S2/S3: `lead-orchestration#LO12b`, `deep-research-web-search#52`, `deep-research-web-search#53`, `deep-research-web-search#55` | E02, E05 | The worker's published composition record, read by Settings, the Reach panel and the Lead pane (so a route refusal names its cause); OPEN posture pinned at enqueue/retry, one cost ceiling used by API and worker, live I-R record with required archive/connector evidence; missing archive leaves I-R BLOCKED |
| E13 | W1 | Method owner/S2: `sociomap-formula-corrections#0b`, `sociomap-formula-corrections#I0`, `segment-maps-and-drilldown#0a` | — | Approved decisions and pinned input/descriptor contract before affected W2 numerical behavior; proposal/fixture preparation may proceed, approval cannot be inferred from completed code |
| E14 | W2 | S2/S3: `sociomap-formula-corrections#I1`, `sociomap-formula-corrections#I3`, `sociomap-formula-corrections#3`, `segment-maps-and-drilldown#1`, `segment-maps-and-drilldown#5`, `client-knowledge-lifecycle#K5` | E10, E11, E12, E13 | Actual population/own-dimension values reach respondents, descriptors, filters and map consumers; missing inputs refuse; changing only a hash is insufficient proof |
| E15 | W2 | S1/S3: `working-copy-edit-ops#WCE8`, `working-copy-edit-ops#WCE9`, `working-copy-edit-ops#WCE11`, `report-delivery#RD3`, `report-delivery#RD4`, `research-lead-workbench#20`, `research-lead-workbench#22` | E06, E11, E12, E14, E29 | Declare/unlock editor, recorded undo before structural auto-accept, real Results/Sociomap/Audience/Dimensions consumers and approved stored snapshot; view operations preserve numerical hash |
| E16 | W2 | S1: `lead-orchestration#LO11` | E06, E09, E10 | Persistent Lead-file history and rollback (no handover or admin read: D-32 to D-34; a departed member's Lead sealed, then deleted: Q14); private turns and proposal text cannot leak through shared activity |
| E17 | W3 | S2/S3: `client-data-in-analysis#0`, `client-data-in-analysis#2`, `client-data-in-analysis#3`, `client-data-in-analysis#8`, `client-data-in-analysis#9`, `evidence-integrity#8b` | E04, E09, E11 | Accepted ADR 0027 and contract before runtime; pinned analysis copy excludes personal/unnamed columns; client data and modelled evidence stay distinct through run node and fingerprint |
| E18 | W3 | S3/S2: `report-delivery#RD6`, `run-qc-and-checkpoint#RQC4`, `run-qc-and-checkpoint#RQC5`; S1: `lead-orchestration#LO9b` | E03, E08, E11, E17 | First the semantic-edit/replacement ADRs and accept-result contracts; then worker bindings/proposals; replacement additionally waits for approved weighting/support and preserves the original run |
| E19 | W3 | S1/S2: `system-prompts-settings#7`, `system-prompts-settings#13` | E03, E11, E18 | Eight analysis pins reach assembly, reuse identity, repairs and usage; all eleven worker slots wired; queued work keeps its pin, new activation changes new work only |
| E20 | W3 | S2/S3: `evidence-integrity#7`, `evidence-integrity#9b`, `client-data-in-analysis#5`, `report-delivery#RD0`, `report-delivery#RD1`, `report-delivery#RD5`, `research-lead-workbench#21` | E15, E17, E18, E19, E32 | Admitted findings plus separately labelled external/client context; full Report artifact hosts approval/export; revised wording invalidates approval without recollecting fieldwork; a module with no supported finding blocks composition and export (MVPQ-04, settled) |
| E21 | W3 | S2/S3: `deep-research#4`, `develop-spend-attribution#5b`, `production-environment#PE7` | E02, E12 | Tool ledger/migration M11 and profile accounting complete before final accounting; E03 already supplies model identity versus invocation-target compatibility before early configuration; legacy reservations stay explicit and no call is charged twice |
| E22 | W4 | S2/S3: `deep-research-web-search#24`, `deep-research-web-search#25`, `deep-research-web-search#26`, `deep-research-web-search#39`, `deep-research-web-search#27`; S1: `research-lead-workbench#23` | E12, E20, E21, E27, E28 | The operator screen for both purposes (24) comes first; approved evaluation metrics/thresholds and separate allowance precede final live 27; Design and Interpretation paths use captured sources and budget; mature conversation cards consume working contracts |
| E23 | W4 | S3: `study-data-lifecycle#SDL0`, `study-data-lifecycle#SDL1`, `study-data-lifecycle#SDL5`, `study-data-lifecycle#SDL6`, `production-environment#PE9a` | E21 | Accepted residual-retention/audit policy before M12; delete/restore exercise proves the independent journal is replayed before serving restored traffic |
| E24 | W5 | S3/all: `mvp-acceptance-harness#5`, `mvp-acceptance-harness#10`, `mvp-acceptance-harness#13`, `mvp-acceptance-harness#15`, `assumptions-and-open-answer-coding#AOC9`, `client-knowledge-lifecycle#K7a` | E10, E15, E16, E20, E22, E23, E26, E30, E31, E34 | All fifteen full criteria, all eleven browser artifacts and negative cases at one pinned release candidate; research intake→knowledge→dimension→report→reuse proven without a hidden Simulation prerequisite |
| E25 | W5 | S3/operator: `mvp-acceptance-harness#6`, `mvp-acceptance-harness#7`, `mvp-acceptance-harness#11`, `mvp-acceptance-harness#12`, `production-environment#PE8`, `production-environment#PE9b` | E24 | Budget (E01's allocation) respected by every paid dispatch, candidate held stable for tier B, costs/unknowns reconciled and production checklist evidenced; production release remains a separate recorded act |
| E26 | W1 | S1: `research-lead-workbench#7`, `research-lead-workbench#11`, `research-lead-workbench#12`, `research-lead-workbench#14`, `research-lead-workbench#15`, `research-lead-workbench#16`, `research-lead-workbench#17`, `research-lead-workbench#18`, `research-lead-workbench#19`, `research-lead-workbench#26a`, `research-lead-workbench#26b`, `research-lead-workbench#26c`, `research-lead-workbench#26d`, `research-lead-workbench#26e`, `research-lead-workbench#26f`, `research-lead-workbench#27a`, `research-lead-workbench#27b`, `research-lead-workbench#27c`, `research-lead-workbench#27d`, `working-copy-edit-ops#WCE3a`, `working-copy-edit-ops#WCE3b`, `working-copy-edit-ops#WCE3c`, `working-copy-edit-ops#WCE7` | E03, E06 | The canonical V2 frame and the first artifacts (Brief, Design, Questionnaire, Sample and Fieldwork; Audience and Dimensions are in E15), the command registry on the worker row, the Lead reachable at every width and availability stated honestly on switch-off and rollback with a disabled backend kept disabled (MVPQ-11), the web store on the server vocabulary and readiness on a working revision; each removes its stage's manual AI starts only with the Lead able to call that stage's worker; browser journey at 1099, 1100, 768 and 390 px with keyboard, focus and Escape and a return to the artifact, a stale card, switch off, kill switch off and a direct request |
| E27 | W2 | S2, in this order: `deep-research-web-search#8`, `deep-research-web-search#20`, `deep-research-web-search#16`, `deep-research-web-search#6`, `deep-research-web-search#33`, `deep-research-web-search#34`, `deep-research-web-search#35`, `deep-research-web-search#36`, `deep-research-web-search#37` | E03, E12 | Source tiers and the register, built and shipped off until the owner approves it, before any quality rate is measured; the light model's key and `RESEARCH_TRIAGE` (20) before the extractors that use it (35), through E03's model-identity contract; procurement built against the interface E05's probes found, or closed with the probe's evidence that none is reachable (16: G5's exclusion is then recorded, never silent); documents, structured capture, records, extractors, inventory subjects and the sealed dataset in the plan's order; recorded exchanges, nothing live beyond I-R's approved routes |
| E28 | W3 | S2: `deep-research-web-search#31`, `deep-research-web-search#32` | E15, E20, E27 | The Lens as an annotation sidecar that never changes a canonical coordinate (a view operation preserves the map's numerical hash), then the report evidence graph over the five evidence families, each claim's support resolving to an admitted claim, a captured source or a knowledge item; Interpretation Research reads and never writes; before the evaluations and the final live run |
| E29 | W2 | S2: `sociomap-formula-corrections#2d` | E13 | After I0, I2 and I4 of the second table: the preset and artifact contract, `methodology_status` stays INTERNAL_ONLY; consumed by Results and the map approval (E15) |
| E31 | W2 | S2 and the method owner: `sociomap-formula-corrections#4c` | E13 | Gated by MVPQ-12's F16 and R-adapter disposition; a separate research product, not the respondent map; built or retired with the reason recorded, and the final acceptance waits for that disposition rather than for a build; approving a method stays the owner's |
| E32 | W1 | S1/S2/method owner: `assumptions-and-open-answer-coding#AOC0`, `assumptions-and-open-answer-coding#AOC1`, `assumptions-and-open-answer-coding#AOC4`, `evidence-integrity#1`, `evidence-integrity#9a` | E02, E06 | The assumption item kind's contract and fixture on the shared vocabulary; the coding method (`MVPQ-02b`) written for the owner's approval before any count is produced, and the assumptions contract with UNTESTED tracking usable at once (an evidence-backed status waits for AOC2's ADR); the empty-module diagnostic stored and shown (MVPQ-04, settled) |
| E33 | W2 | S2: `assumptions-and-open-answer-coding#AOC2`, `assumptions-and-open-answer-coding#AOC5` | E08, E12, E32 | The ADR and admission rule ADR 0026 decision 4 requires for assumption evidence and for coding, then Design Research evidence attachable to an assumption by a person's accept, and the coding node, per-answer artifact and deterministic counts with an impact root that never reruns fieldwork |
| E34 | W3 | S1/S2/S3: `assumptions-and-open-answer-coding#AOC3`, `assumptions-and-open-answer-coding#AOC6`, `assumptions-and-open-answer-coding#AOC7`, `assumptions-and-open-answer-coding#AOC8`, `report-delivery#RD9`, `report-delivery#RD10` | E19, E20, E33 | Assumptions and coded counts reach the Design artifact, the Lead's context, the analysis payload, Results and the report as admitted or cited support only; a coder worker exists only if the method permits one, as a twelfth row beyond AC-03's eleven; raw text is never admitted evidence |
| E30 | W2 | S2/S3: `sociomap-formula-corrections#5b` | E15 | Verified, not assumed: `report_maps.py:159-180` and `figures.py:76-95` already print Stress-1 and the internal status, so 5b is ticked with a test that the internal report's map figure carries both on RD4's snapshot path, or the gap it closes is listed |

The table names the earliest contract and consumer waves. W0 cost planning and
record schema work in E25's chunks begin earlier; E25 is the final combined proof.
Production infrastructure PE0/PE1/PE2/PE3/PE4 can progress alongside W1, with
PE5/PE6/PE7 completing before a release candidate needs them. No paid or write
operation is performed by this planning PR.

**Scope freeze (2026-10-20).** The owner's D-13 makes `aia-sociomap-5` the only method of new runs, so
E14, E29, E30 and E31, written for the contract-3 route, are re-aimed at the `-5` engine (segments stay
defined by descriptors, MVPQ-03) once the methodology owner answers MQ-02 and MQ-05 (`signed-off-sociomap-method#8`, master § The scope
baseline). E30's "the map figure carries Stress-1" does not hold for `-5`, which computes none.

**The Lead conversation's UI overlap (2026-10-21).** `research-lead-workbench#29` (copy, edit and
resend, ArrowUp, a queued message's send-now and edit; D-38) is the UI of `lead-conversation#LC5` and
`#LC10`. It stays the UI owner and takes LC10's replacement-turn rule and LC5's server queue as
acceptance conditions; LC5 and LC10 own the server side.

## Every other open chunk of a core plan

The table above names the cross-plan predecessors. This one gives every remaining open chunk of the
plans in master §3.1 an explicit wave, so none is silently unscheduled: the wave of the development plan
where it says one, a child plan's own note, or "proposed here" where nothing did (a proposal, to be
confirmed by the plan's owner). **UNSCHEDULED** is also an assignment: the chunk is in no wave, is not
in the MVP by a decision on record, and needs a scope call from the plan's owner; it is never counted as
done or as dropped. `tools/master_check.py` fails when an open chunk of a core plan is in neither table. **A wave's gate passes only when every open chunk assigned to that wave in either table is ticked, or a disposition is recorded in its plan and in the acceptance record**; a chunk outside the predecessor graph is not thereby optional. A recorded `[-]` (dropped) chunk needs the owner's or the method owner's name.

| Chunk | Wave | Basis |
|---|---|---|
| `evidence-integrity#2` | W1 | development plan §3 |
| `lead-orchestration#LO9c` | W2 | cross-check G47: after LO9a, before LO9b (E18) |
| `segment-maps-and-drilldown#10` | W2 | cross-check G48, owner 2026-10-20: after 1 (E14); before `evidence-integrity#9b` |
| `working-copy-edit-ops#WCE8b` | W2 | cross-check G49: with WCE8, before `research-lead-workbench#17` (E26) is accepted on a map study |
| `report-delivery#RD5a` | W2 | cross-check G50: before RD5 and RD7 |
| `client-data-in-analysis#3a` | W3 | cross-check G52: before 2a and 3 (E17) |
| `client-data-in-analysis#3b` | W3 | cross-check G52: with 3 (E17) |
| `client-data-in-analysis#2a` | W3 | cross-check G52: after 3a, before the contract is accepted |
| `working-copy-edit-ops#WCE13` | W1 | cross-check G53, owner 2026-10-20: with `research-lead-workbench#17` (E26) |
| `run-qc-and-checkpoint#RQC11` | W1 | cross-check G53: after WCE13, with RQC0 (E08) |
| `evidence-integrity#10` | W2 | cross-check G53: after RQC11 |
| `segment-maps-and-drilldown#9` | W2 | cross-check G54: before `report-delivery#RD4` (E15) |
| `system-prompts-settings#14` | W1 | cross-check G55, owner 2026-10-20: with the stage buttons' removal (E26) |
| `evidence-integrity#3` | W1 | development plan §3 |
| `evidence-integrity#4` | W3 | development plan §3 |
| `evidence-integrity#5` | W0 | development plan §3 |
| `sociomap-formula-corrections#I2` | W2 | development plan §3 (I0-I5) |
| `sociomap-formula-corrections#I4` | W2 | development plan §3 (I0-I5) |
| `sociomap-formula-corrections#I5` | W2 | development plan §3 (I0-I5) |
| `sociomap-formula-corrections#4d` | W2 | development plan §3 |
| `segment-maps-and-drilldown#0` | W1 | method-owner decisions (`MVPQ-03`); blocks W2 numerical behavior (E13) |
| `segment-maps-and-drilldown#2` | W2 | development plan §3 (1-6) |
| `segment-maps-and-drilldown#3` | W2 | development plan §3 (1-6); AC-09 says "optionally clustered" |
| `segment-maps-and-drilldown#4` | W2 | development plan §3 (1-6) |
| `segment-maps-and-drilldown#6` | W2 | development plan §3 (1-6): the respondent drill-down AC-09 requires |
| `segment-maps-and-drilldown#7` | W2 | proposed here: needs the W1 `ResultsContext` (`lead-orchestration#LO8`) |
| `segment-maps-and-drilldown#8` | W2 | development plan §3, with `research-lead-workbench#20` |
| `audience-catalogue-cpu#4` | W0 | development plan §3 |
| `complete-study-report#B6` | W0 | development plan §3 |
| `deep-research-web-search#38` | W4 | development plan §3 |
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
| `lead-orchestration#LO12a` | W0 | development plan §3: the stage error says who can fix it, as static copy that reads no route |
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
| `signed-off-sociomap-method#8` | W1 | scope freeze, D-13 and Q1: `-5` the only method of new runs, merged when built; before E13 |
| `signed-off-sociomap-method#9` | W2 | scope freeze, D-13: the report draws `-5`; before E15 |
| `signed-off-sociomap-method#10` | W1 | scope freeze, D-14 and Q4: the Metodik mark gates storing and activating |
| `signed-off-sociomap-method#11` | W2 | scope freeze, Q8: Metodika's comparison shows all of `-5`'s outputs; after 8 |
| `lead-orchestration#LO9d` | W2 | scope freeze, Q12: after LO9a and `working-copy-edit-ops#WCE7` |
| `lead-orchestration#LO19` | W2 | scope freeze, Q5: the study's context file; after LO8 and `working-copy-edit-ops#WCE4` |
| `lead-orchestration#LO20` | W3 | scope freeze, Q6: Hledat na webu; after `deep-research-web-search#56`; an ADR first |
| `deep-research-web-search#56` | W3 | scope freeze, Q6: the Lead's quick lookup through RetrievalGate |
| `research-lead-workbench#32` | W3 | scope freeze, Q5 and Q6: with `lead-orchestration#LO19` and `#LO20` |
| `deep-research-web-search#51a` | W1 | cross-check G67: with E12 |
| `lead-orchestration#LO5a` | W1 | scope freeze, D-12: with `research-lead-workbench#26f` (E26) and E12 |
| `lead-orchestration#LO5a.1` | W1 | lead deep research plan (2026-10-21, Q44-Q46): the Lead's Deep Research requests and layers; with E26 |
| `lead-orchestration#LO5a.2` | W1 | lead deep research plan: a Lead card starts Deep Research on the server; after `lead-orchestration#LO10` and `deep-research-web-search#55` (E12) |
| `lead-orchestration#LO5a.3` | W1 | lead deep research plan: typed Deep Research starts; after `lead-orchestration#LO5` (E10; landed on the server, #574) and DRL-0 (`deep-research-web-search#55`, landed in #555); still waits for `lead-orchestration#LO5a.1` |
| `lead-orchestration#LO5a.4` | W1 | lead deep research plan (Q47): Deep Research plan-step kinds; after `lead-orchestration#LO3`, `#LO4` and `#LO17` |
| `research-lead-workbench#7b` | W1 | lead deep research plan: Design Research proposal review (F-DRL-1); with `research-lead-workbench#7` (E26) |
| `research-lead-workbench#12a` | W1 | lead deep research plan: Deep Research on recorded web in the UI workbench (F-DRL-6); with `research-lead-workbench#12` (E26) |
| `research-lead-workbench#23b` | W1 | lead deep research plan: Deep Research request and running cards; after #550 (chunk 23 brought forward) |
| `research-lead-workbench#23c` | W1 | lead deep research plan: the finished Deep Research card; after 23b |
| `research-lead-workbench#26f.1` | W1 | lead deep research plan (Q48): the Deep Research half of 26f; after 23b and `lead-orchestration#LO5a.3` |
| `lead-orchestration#LO12c` | W1 | scope freeze, D-09: after LO12b (E12) |
| `lead-orchestration#LO17` | W1 | scope freeze, D-18: after LO4 (E10) |
| `lead-orchestration#LO18` | W3 | scope freeze, D-39: after LO6; an ADR 0026 amendment in its PR |
| `research-lead-workbench#29` | W2 | scope freeze, D-38 |
| `research-lead-workbench#30` | W3 | scope freeze, D-39: with `lead-orchestration#LO18` |
| `research-lead-workbench#31` | W3 | scope freeze, D-41: with `report-delivery#RD12` |
| `report-delivery#RD11` | W3 | MVP-26, chunk missing until the scope freeze: after RD0 |
| `report-delivery#RD12` | W3 | scope freeze, D-41: after RD0 |
| `segment-maps-and-drilldown#11` | W3 | scope freeze, D-42: after 8 and `research-lead-workbench#20` (E15) |
| `working-copy-edit-ops#WCE14` | W2 | scope freeze, D-45 |
| `run-qc-and-checkpoint#RQC12` | W1 | cross-check G78 |
| `run-qc-and-checkpoint#RQC13` | W2 | scope freeze, D-45: after WCE14 |
| `mvp-acceptance-harness#16` | W3 | cross-check G65: after `system-prompts-settings#7` |
| `mvp-acceptance-harness#18` | W4 | scope freeze, D-48: the budget values are open in the baseline |
| `client-knowledge-lifecycle#K9` | W3 | scope freeze, D-47 |
| `client-knowledge-lifecycle#K10` | W3 | scope freeze, D-47 |
| `client-knowledge-lifecycle#K11` | W1 | scope freeze, D-17: with `deep-research-web-search#53` and `lead-orchestration#LO1`; I15 |
| `client-knowledge-lifecycle#K12` | W1 | MVP-31, chunk missing until the scope freeze |
| `develop-spend-attribution#6` | W3 | scope freeze, D-47: after 5b |
| `develop-spend-attribution#7` | W3 | owner, Q40 (2026-10-21): per-researcher spend; after `lead-orchestration#LO1`'s wallet holds, with chunk 6; its actor columns are migration M13 |
| `production-environment#PE10` | W1 | scope freeze, D-22: before the first production sign-in |
| `production-environment#PE11` | W4 | scope freeze, D-23: before the release candidate |
| `two-roles-human-ai-gates#8` | W2 | scope freeze, D-27 |
| `study-data-lifecycle#SDL4b` | W4 | scope freeze, D-29: with SDL3 |
| `architecture-enforcement#12` | W3 | scope freeze, D-24 (a SUPPORT plan) |
| `client-data-in-analysis#10` | W3 | scope freeze, D-37: with 2 and 2a (E17) |
| `research-lead-workbench#33` | W1 | owner, page Q19: the editor spike before LO19 and RD6 build their surface |
| `deep-research-web-search#57` | W2 | owner determination 2026-10-20, page Q20: with chunk 53 (E12) |
| `deep-research-web-search#57a` | W2 | owner, page Q22: with chunk 57 (E12) |
| `deep-research-web-search#58` | W2 | owner, page Q23: with chunk 57 |
| `input-interactions#0` | W0 | done by #528's merge (the audit, standard and plan); its owner ticks it |
| `input-interactions#1` | W1 | the shared primitives before the artifact bodies (E26: `research-lead-workbench#14`-22) build on them |
| `input-interactions#2` | W1 | the owner's own example; with `client-workspace` C6 and C7; batched revisions (Q31) |
| `input-interactions#3b2` | W1 | the scale editor on chunk 1's primitives; 3b1 (the server side, IA-7) landed in #538 behind `AIA_AI_SCALE_LABELS_IN_PROMPT`, off: switching it on moves the respondent-system fingerprint, so before any holdout confirmation (`panel-grounded-respondents` 7f-7h) binds to one, on the methodology owner's wording rule |
| `input-interactions#3b3` | W2 | the scale labels switched on for respondents after the methodology owner's wording rule, with the moved fingerprint and develop evidence; before `panel-grounded-respondents` 7f-7h binds to a fingerprint |
| `input-interactions#3` | W2 | applied to the Questionnaire artifact (`research-lead-workbench#17`) |
| `input-interactions#4` | W2 | applied to the Brief and Design artifacts (`research-lead-workbench#18`) |
| `input-interactions#5` | W2 | with `research-lead-workbench#19` and `#22` |
| `input-interactions#6` | W2 | one SpendDialog: the card path's money prompts (`lead-orchestration#LO4`, `#LO10`) render through it; report approval a modal (Q33) |
| `input-interactions#7` | W2 | rename routes in the api-contract list; a client rename by any member under EDIT_CLIENT_PROFILE, audited (Q34) |
| `input-interactions#8` | W2 | with `client-knowledge-lifecycle#K11` (the wallet ceiling stepper) |
| `input-interactions#9` | W3 | after `system-prompts-settings` and `signed-off-sociomap-method#10` (the Metodik mark) |
| `input-interactions#10` | W4 | beside `mvp-acceptance-harness`'s journeys |
| `lead-conversation#LC0` | W0 | the owner accepts ADR 0041; nothing below is built before it |
| `lead-conversation#LC1` | W1 | the plan's own: with E10, after `lead-orchestration#LO7`'s first layer; no model call |
| `lead-conversation#LC2` | W1 | the plan's own: with E10, after `lead-orchestration#LO7`'s first layer; no model call |
| `lead-conversation#LC3` | W1 | the plan's own: with E10, after `lead-orchestration#LO7`'s first layer; no model call |
| `lead-conversation#LC5` | W1 | the plan's own: with E10, after `lead-orchestration#LO7`'s first layer; no model call |
| `lead-conversation#LC6` | W1 | the plan's own: with E10, after `lead-orchestration#LO7`'s first layer; no model call |
| `lead-conversation#LC4` | W2 | the plan's own: with `lead-orchestration#LO19`, after LC1 |
| `lead-conversation#LC7` | W2 | the plan's own: with `lead-orchestration#LO19`, after LC1; behind its own kill switch |
| `lead-conversation#LC7a` | W2 | the plan's own: with `lead-orchestration#LO19`, after LC1 |
| `lead-conversation#LC8` | W2 | the plan's own: with `lead-orchestration#LO19`, after LC1 |
| `lead-conversation#LC9` | W2 | the plan's own: with `lead-orchestration#LO19`, after LC1 |
| `lead-conversation#LC10` | W2 | the plan's own: with `lead-orchestration#LO19`, after LC1 |
| `lead-conversation#LC11` | W2 | the plan's own: with `lead-orchestration#LO19`, after LC1 |
| `lead-conversation#LC12` | W3 | the plan's own: with `lead-orchestration#LO18` |
| `lead-conversation#LC13` | W3 | the plan's own: with `lead-orchestration#LO18` |
| `lead-conversation#LC14` | POST | the plan's own: after the MVP |
| `lead-conversation#LC15` | POST | the plan's own: after the MVP |
| `lead-conversation#LC16` | POST | the plan's own: after the MVP |
| `lead-conversation#LC17` | POST | the plan's own: after the MVP |
| `lead-conversation#LC18` | POST | the plan's own: after the MVP |
| `client-knowledge-lifecycle#K4b` | W1 | with K4 (E09): the consumers read the frozen context behind a switch |
| `client-knowledge-lifecycle#K4c` | W1 | with K4b: the web's Použít v této studii |
| `sociomap-5-web#6` | W2 | the methodology owner's lane (#517); hosted by `research-lead-workbench#20` |
| `sociomap-5-web#7` | W2 | the methodology owner's lane; the report figure with `signed-off-sociomap-method#9` |
| `artifact-questionnaire#QST1` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#17` (E26) |
| `artifact-questionnaire#QST2` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#17` (E26) |
| `artifact-questionnaire#QST3` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#17` (E26) |
| `artifact-questionnaire#QST4` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#17` (E26) |
| `artifact-questionnaire#QST5` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#17` (E26) |
| `artifact-questionnaire#QST6` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#17` (E26) |
| `artifact-questionnaire#QST7` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#17` (E26) |
| `artifact-questionnaire#QST8` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#17` (E26) |
| `artifact-questionnaire#QST9` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#17` (E26) |
| `artifact-brief#BRF1` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#18` (E26) |
| `artifact-brief#BRF2` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#18` (E26) |
| `artifact-brief#BRF3` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#18` (E26) |
| `artifact-brief#BRF4` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#18` (E26) |
| `artifact-brief#BRF5` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#18` (E26) |
| `artifact-brief#BRF6` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#18` (E26) |
| `artifact-design#DSN1` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#18` (E26) |
| `artifact-design#DSN2` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#18` (E26) |
| `artifact-design#DSN3` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#18` (E26) |
| `artifact-design#DSN4` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#18` (E26) |
| `artifact-design#DSN5` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#18` (E26) |
| `artifact-design#DSN6` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#18` (E26) |
| `artifact-design#DSN7` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#18` (E26) |
| `artifact-design#DSN8` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#18` (E26) |
| `artifact-sample#SMP1` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#19` (E26) |
| `artifact-sample#SMP2` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#19` (E26) |
| `artifact-sample#SMP3` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#19` (E26) |
| `artifact-sample#SMP4` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#19` (E26) |
| `artifact-sample#SMP5` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#19` (E26) |
| `artifact-sample#SMP6` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#19` (E26) |
| `artifact-fieldwork#FLD1` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#19` (E26) |
| `artifact-fieldwork#FLD2` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#19` (E26) |
| `artifact-fieldwork#FLD3` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#19` (E26) |
| `artifact-fieldwork#FLD4` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#19` (E26) |
| `artifact-fieldwork#FLD5` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#19` (E26) |
| `artifact-fieldwork#FLD6` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#19` (E26) |
| `artifact-fieldwork#FLD7` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#19` (E26) |
| `artifact-fieldwork#FLD8` | W1 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#19` (E26) |
| `artifact-results#RES1` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#20` (E15) |
| `artifact-results#RES2` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#20` (E15) |
| `artifact-results#RES3` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#20` (E15) |
| `artifact-results#RES4` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#20` (E15) |
| `artifact-results#RES5b` | W3 | artifact plans: the coded counts, after `assumptions-and-open-answer-coding#AOC8` (RES5a landed) |
| `artifact-results#RES8` | W2 | the per-question CSV/XLSX export, moved from `report-delivery#RD12` by the coordinator (2026-10-21); umbrella `research-lead-workbench#20` (E15) |
| `artifact-results#RES6` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#20` (E15) |
| `artifact-results#RES7` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#20` (E15) |
| `artifact-sociomap#SOC1` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#20` (E15) |
| `artifact-sociomap#SOC2` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#20` (E15) |
| `artifact-sociomap#SOC3` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#20` (E15) |
| `artifact-sociomap#SOC4` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#20` (E15) |
| `artifact-sociomap#SOC5` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#20` (E15) |
| `artifact-sociomap#SOC6` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#20` (E15) |
| `artifact-sociomap#SOC7` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#20` (E15) |
| `artifact-sociomap#SOC8` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#20` (E15) |
| `artifact-audience#AUD1` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#22` (E15) |
| `artifact-audience#AUD2` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#22` (E15) |
| `artifact-audience#AUD3` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#22` (E15) |
| `artifact-audience#AUD4` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#22` (E15) |
| `artifact-audience#AUD5` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#22` (E15) |
| `artifact-audience#AUD6` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#22` (E15) |
| `artifact-dimensions#DIM1` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#22` (E15) |
| `artifact-dimensions#DIM2` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#22` (E15) |
| `artifact-dimensions#DIM3` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#22` (E15) |
| `artifact-dimensions#DIM4` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#22` (E15) |
| `artifact-dimensions#DIM5` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#22` (E15) |
| `artifact-dimensions#DIM6` | W2 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#22` (E15) |
| `artifact-analysis#ANL1` | W3 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#21` (E20) |
| `artifact-analysis#ANL2` | W3 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#21` (E20); landed in #575 |
| `artifact-analysis#ANL3` | W3 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#21` (E20) |
| `artifact-analysis#ANL4` | W3 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#21` (E20) |
| `artifact-analysis#ANL5` | W3 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#21` (E20) |
| `artifact-analysis#ANL6` | W3 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#21` (E20) |
| `artifact-analysis#ANL7` | W3 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#21` (E20) |
| `artifact-analysis#ANL8` | W3 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#21` (E20) |
| `artifact-report#RPT1` | W3 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#21` (E20) |
| `artifact-report#RPT2` | W3 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#21` (E20) |
| `artifact-report#RPT3` | W3 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#21` (E20) |
| `artifact-report#RPT4` | W3 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#21` (E20) |
| `artifact-report#RPT5` | W3 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#21` (E20) |
| `artifact-report#RPT6` | W3 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#21` (E20) |
| `artifact-report#RPT7` | W3 | artifact plans (#560, 2026-10-21): umbrella `research-lead-workbench#21` (E20) |
| `artifact-chain-to-draft-report#CHN1` | W3 | artifact plans (#560): a hand-off into the internal draft, with `research-lead-workbench#21` (E20) |
| `artifact-chain-to-draft-report#CHN2` | W3 | artifact plans (#560): a hand-off into the internal draft, with `research-lead-workbench#21` (E20) |
| `artifact-chain-to-draft-report#CHN3` | W3 | artifact plans (#560): a hand-off into the internal draft, with `research-lead-workbench#21` (E20) |
| `artifact-chain-to-draft-report#CHN4` | W3 | artifact plans (#560): a hand-off into the internal draft, with `research-lead-workbench#21` (E20) |
| `artifact-chain-to-draft-report#CHN5` | W3 | artifact plans (#560): a hand-off into the internal draft, with `research-lead-workbench#21` (E20) |
| `artifact-chain-to-draft-report#CHN6` | W3 | artifact plans (#560): a hand-off into the internal draft, with `research-lead-workbench#21` (E20) |
| `artifact-chain-to-draft-report#CHN7` | W3 | artifact plans (#560): a hand-off into the internal draft, with `research-lead-workbench#21` (E20) |
| `artifact-chain-to-draft-report#CHN8` | W3 | artifact plans (#560): a hand-off into the internal draft, with `research-lead-workbench#21` (E20) |
| `artifact-chain-to-draft-report#CHN9` | W3 | artifact plans (#560): a hand-off into the internal draft, with `research-lead-workbench#21` (E20) |
| `artifact-chain-to-draft-report#CHN10` | W3 | artifact plans (#560): a hand-off into the internal draft, with `research-lead-workbench#21` (E20) |
| `artifact-chain-to-draft-report#CHN11a` | W4 | artifact plans (#560): before CHN11 |
| `artifact-chain-to-draft-report#CHN11` | W4 | artifact plans (#560): the chain's acceptance journey, after CHN2-CHN10 and every artifact plan |
| `artifact-chain-to-draft-report#CHN12` | W4 | artifact plans (#560): the chain's acceptance journey, after CHN2-CHN10 and every artifact plan |
| `lead-client-knowledge#LK0` | W1 | owner Q60 (2026-10-21): the licence determination, a live defect (every Lead turn refused for a client with a dataset, artifact or finding); its own fix PR |
| `lead-client-knowledge#LK1` | W2 | owner Q59: the knowledge index; ADR 0042 (Proposed) with it; with `lead-conversation#LC1`'s layer table |
| `lead-client-knowledge#LK2` | W2 | after LK1: the index frozen at enqueue |
| `lead-client-knowledge#LK3` | W2 | after LK2, with `lead-conversation#LC4`'s budgets: the read in the closed contract inside 96 KB |
| `lead-client-knowledge#LK4` | W2 | after LK3: the read round behind `AIA_AI_RESEARCH_LEAD_KNOWLEDGE_READS`, off; cost and latency measured |
| `lead-client-knowledge#LK5` | W2 | owner Q62: a dataset read as its preview; after LK0 and LK4 |
| `lead-client-knowledge#LK6` | W2 | after LK4: what the Lead read, in the API and on screen |
| `lead-client-knowledge#LK7` | W3 | after LK4-LK6 and the measurement: switched on for develop |
| `research-lead-workbench#24` | POST | development plan D16: after the MVP |
| `research-lead-workbench#25` | POST | development plan D16: after the MVP |

## Gate records

| Gate | Required evidence | Does not establish |
|---|---|---|
| I-0 | Owners, accepted prerequisites for the next work, one migration head, collected/working harness and current acceptance statements, the approved allocation table, the AI route classes and population switch reported READY by the activation profile (`MP6`, `MP7`, B6) | Full AC-06 recovery, AC-07 impact or AC-03 worker completeness |
| I-1 | Available design workers, shared edits, card/wallet/human authority, checkpoints, run QC stored and shown as warnings, the Lead reachable at 1099, 768 and 390 px, the empty-module diagnostic stored, the assumption item's contract, a client-charged paid step proven (CB5) and frozen study context; HTTP plus the relevant browser journey | Remaining W3 worker bindings, analysis pins or every artifact |
| I-R | Required live reach probes, OPEN/CLASSIFIED/retry tests, effective composition/status; archive remains required until explicitly changed | Retrieval/verification quality or final Deep Research acceptance |
| I-2 | Approved pinned methods, actual descriptor/dimension consumers, Results/map UI, the respondent drill-down (internal, never exported) and snapshot proof | Methodology approval from a passing fixture, or report delivery from a component test |
| I-3 | Evidence/client-data admission, all worker/prompt contracts, report version/approvals, assumptions and coded open answers carried as admitted or cited support only, a blocked or empty module refusing composition and export, and DOCX/PDF proof | Tier B or a production release |
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
