# Scope freeze: every proposed master-plan edit, in one list

Written 2026-10-20 by the planning session, on the coordinator's request (freeze step 4, part 1b).
It collects every "Proposed master-plan edit" (and the plan-edit parts of each Doc follow-up) of
the five freeze inputs, deduplicated across them, so part 2 applies each once. Read against:

| PR | Head | Input |
|---|---|---|
| #510 | `798d87a` | methodology packet: proposed chunks E-1 to E-9 and its Doc follow-up |
| #512 | `bf3f733` | ADRs 0028-0038: each ADR's *Unblocks* and the PR's Doc follow-up |
| #513 | `08ef5cf` | reverse scope audit: proposed edits 1-14 |
| #514 | `36d009c` | client pages + Settings: proposed edits 1-12 (§9) and stale copy (§7) |
| #515 | `35aaf52` | cross-check of tracks 5-7: G58-G78, new chunks, register and text changes, stale statements (§4) |

and the decision list, `.planning/evidence/scope-freeze/decision-list.md` (#516 @ `c7d5bbe`), whose
D-numbers are cited below.

**Tags**

- **(a) no decision.** A gap fix, a correction or a consequence of something already decided; apply
  after sign-off.
- **(b) D-nn.** Its content depends on that answer in #516. The edit's wording is given for the
  recommended option; another answer changes or removes it.
- **(m) MQ-nn.** It waits on the methodology owner (A. Bahbouh) in the packet, not on Nigel. Added
  to the three tags asked for, because folding these into (a) would apply them before he answers.
- **(c) new question.** A product call none of the 48 decisions covers. Two of them, at the end
  (C-1, C-2).

**Count: 102 edits after deduplication**; a row proposed by more than one PR names every source.
By tag: (a) 53, (b) 44, (m) 4, (c) 1 (S-09; S-02 also waits on C-1). Two new questions, C-1 and C-2.

An edit's *Where* is the file part 2 changes. "Master" is `.planning/plans/mvp-master-plan.md`;
"contracts" is `.planning/mvp-execution-contracts.md`; "docs PR" marks a shared file (CLAUDE.md §1)
that part 2 does not edit but lists under Doc follow-up.

---

## 1. `aia-sociomap-5` reaches a run, a screen and a report

Proposed by four PRs at once (#510 E-1 to E-9; #512 ADR 0038; #513 edits 1-2; #514 edits 5, 8 and
§5; #515 G58-G60). One row per edit, every source named.

| # | Edit | Where | Tag | Sources |
|---|---|---|---|---|
| S-01 | Register `signed-off-sociomap-method` in master §3.1 (owner S2 plus the methodology owner, gate I-2); `master_check` fails without it | master §3.1 | (a) | #514 5; #515 G58 |
| S-02 | New `signed-off-sociomap-method#8`: `-5` pinned **by its own name** as the code's default (`default_methods`), a run that pinned `-3` keeping it; tests: a new run pins `aia-sociomap-5` at `8b0b4864…`, a `-3` run recomputes byte for byte, `require_client_facing` passes with the register entry and refuses `-5+e1`. W1, before E13. Pins `-1` beside it per D-13; when it lands per C-1 | plan; contracts E13 | (b) D-13, (c) C-1 | #510 E-1; #512 0038; #513 1 (`#0b`); #514 5, N9b; #515 G58 |
| S-03 | Same chunk: Metodika's in-force method becomes `aia-sociomap-5`, the module note stops saying every run pins `-3`, and the editor starts from the preset in force, not `presets[0]` (`-4`); the pinned test (`MethodologyVersions.test.tsx:258`) changes with it | `signed-off-sociomap-method#8` | (a) | #510 E-2; #514 §5.3 |
| S-04 | Metodika warns before activating an edit of `-5` that its maps are internal until registered | `signed-off-sociomap-method#8` | (b) D-14 | #514 N10 |
| S-05 | The `-5` register entry itself, at its fingerprint, scoped to the map kinds it covers | `signed-off-sociomap-method#8` | (m) MQ-01 | #510 MQ-01; #512 0038; #514 N9a; #515 G58 |
| S-06 | New `signed-off-sociomap-method#9`: the report's `-5` object-map figure (z from `heights.relative`, the caption from the terrain method, `objects_not_placed` listed) and credibility in place of Stress-1 in the map chapter. W2, before E15 | plan; contracts E15 | (a) | #510 E-4; #515 G60 |
| S-07 | The web draws `-5`: the method named in `OBJECT_MAP_METHODS`, relative-height terraces, the credibility banner, split-half share and uncertainty circles, "Neumístěno", the respondent map, taste segments, following `ui_app.html`'s drawing. **One owner:** #513 proposes a new `research-lead-workbench#28`; #510 gives it to `#20` with `segment-maps-and-drilldown#8`. Proposed: widen `#20` (W2, already E15) rather than add `#28`, so E15's predecessors stay one row | `research-lead-workbench#20`, `segment-maps-and-drilldown#8` | (a) | #510 E-3; #513 2 |
| S-08 | Name `-5`'s fields in `lead-orchestration#LO8` (the ResultsContext) and in `segment-maps-and-drilldown#9`, `#10`; add unplaced objects to the report | those chunks | (a) | #513 2 |
| S-09 | Metodika's comparison (`MapSummary`) carries credibility, respondents and segments | `methodology-tab` | (c) C-2 | #510 E-5 |
| S-10 | The worker image's `NUMBA_CACHE_DIR` and library versions recorded with the map | `signed-off-sociomap-method#8` | (a) | #510 E-6 |
| S-11 | How the report re-derives a `-5` map (`verified_map`) | `signed-off-sociomap-method#9` | (m) MQ-04 | #510 E-7 |
| S-12 | Measure a `-5` map with respondents and segments on the develop worker image at 1,500, 5,000 and 20,000 respondents, before MQ-06 is answered | a measurement line in `signed-off-sociomap-method#8` | (a) | #510 E-9 |
| S-13 | Re-point `sociomap-formula-corrections#3` and `segment-maps-and-drilldown#1-3` onto `-5`'s stored fields; rewrite contracts E14, E29, E30, E31 for `-5`; add `#8`/`#9` to AC-09's §3.4 row and `#8` to AC-13's | those plans; contracts; master §3.4 | (m) MQ-02, MQ-05 | #510 E-8, Doc follow-up; #513 1; #515 G59 |
| S-14 | Mark `segment-maps-and-drilldown#0`, `#3` and `sociomap-formula-corrections#3` superseded or answered by `-5` once MQ-02 and MQ-05 are answered | those plans | (m) MQ-02, MQ-05 | #510 Doc follow-up |
| S-15 | Every W2 engine chunk (`sociomap-formula-corrections`, `segment-maps-and-drilldown`, `run-qc-and-checkpoint#RQC1`) names its Metodika catalogue re-pin | those chunks | (a) | #514 8 |
| S-16 | Master text: `:126` "the MVP uses `aia-sociomap-3`" → `-5` (MVPQ-13); `:337` the register approves `-3`, `-5` pending MQ-01; §11.1 gains the MVPQ-13 row; §11.4 points MVPQ-12 at the packet's MQ-05 table | master | (a) | #510; #514 5; #515 §3.2 |
| S-17 | `mvp-owner-decisions.md`: MVPQ-13 SETTLED 2026-10-20 with the hybrid rejected; each of MVPQ-03/05/09/10/12/02b gets "Answer-ready form: packet MQ-xx"; `:69-71` "#504 open" → merged `18d59ea`. `mvp-cohesion.md`: MVPQ-13 with the affected chunks | those files | (a) | #510; #515 §4 |
| S-18 | E30's "the map figure carries Stress-1" is wrong under `-5` (`report_maps.py:243-250` already handles it) | contracts E30 | (a) | #515 §4 |
| S-19 | `parity-matrix.json:3485` `sociomapping.core` says `-3` INTERNAL_ONLY "while D6 is open" (approved 2026-10-13). Not a shared file: changes with `test_parity_matrix.py`, so the PR that carries it runs the full suites | `docs/migration/parity-matrix.json` | (a) | #515 §4 |
| S-20 | CLAUDE.md §2's Sociomap paragraph says what a new run pins; `ARCHITECTURE.md:508` gets the numpy/scipy/numba exception bounded to `domain/sociomap/` | docs PR | (a) | #512 Doc follow-up; #513 Doc follow-up |

## 2. Money, the plan card and the Lead (S1)

| # | Edit | Where | Tag | Sources |
|---|---|---|---|---|
| L-01 | `lead-orchestration#LO0`: the four Czech money names. The wallet rename itself is done (#511, merged `125db46d`) | `lead-orchestration` | (b) D-01 | #514 4, N3; #512 0028 |
| L-02 | `LO4` / `LO9a`: the card shows each step's ceiling against the threshold; approval records a confirmation per shown ceiling; a ceiling that grew parks. AC-04's wording follows | `lead-orchestration`; acceptance | (b) D-02 | #512 0028 Q1 |
| L-03 | `LO1`'s test: a raise above the client ceiling is refused, naming who can raise the ceiling (no approver queue) | `lead-orchestration#LO1` | (b) D-03 | #512 0028 Q2; #514 N2 |
| L-04 | `LO3` / `LO10`: on a revision move the plan finishes steps tied to its immutable revision and stops the rest | `lead-orchestration` | (b) D-04 | #512 0028 Q3 |
| L-05 | The wallet charges a Deep Research run at its ceiling until M11 reconciles tool spend | `lead-orchestration#LO1`; `deep-research#4` | (b) D-05 | #512 0028 Q4 |
| L-06 | New `lead-orchestration#LO5a` (W1, in E26 with E12): Deep Research as a plan-step kind and a typed chat start, with chunk 55's ceiling; I22 names it | plan; contracts; master I22 | (b) D-12 | #515 G69 |
| L-07 | New `lead-orchestration#LO17` (W1): cancel a running turn, withdraw an approved plan, with a workbench build line | plan; contracts | (b) D-18 | #513 5 |
| L-08 | New `lead-orchestration#LO12c` (W1, after LO12b): the composition digest stored on each run. #513's `mvp-master-plan#MP6b` is the same record: one chunk, not two | plan; contracts | (b) D-09 | #513 8; #515 G74 |
| L-09 | `LO11`: client notes copied on handover; an admin starts it; OWNER/ADMIN read files and notes under Settings → Přístup (audited, never turns); the page for file revisions named | `lead-orchestration#LO11` | (b) D-32, D-33, D-34 | #512 0030; #514 10, N12 |
| L-10 | `LO11` also carries F14's learning rules | `lead-orchestration#LO11` | (a) | #513 13 |
| L-11 | `LO12a`: every API error in Czech, a no-leak test and a native copy review; the words for a refused Deep Research run | `lead-orchestration#LO12a` | (a) | #513 13; #515 G68 |
| L-12 | New `research-lead-workbench#29`: older-message paging (with its route) and copy | plan; contracts | (b) D-38 | #513 7 |
| L-13 | `research-lead-workbench#15`: mount `ItemInspector` (imported only by its test) and fix provider waits reading as inert (`research/lane.ts:134`) | `research-lead-workbench#15` | (a) | #513 6 |
| L-14 | `research-lead-workbench#26`: no Deep Research button survives as an exception (follows L-06) | `research-lead-workbench#26` | (b) D-12 | #515 G69 |
| L-15 | `system-prompts-settings#14`: also remove `prompt_version` and its two refusals from `POST …/agent-jobs` | `system-prompts-settings#14` | (b) D-15 | #514 6, N8 |
| L-16 | MVP-13 superseded by ADR 0028; ADR 0026's status line amended (0028-0030) | docs PR (`overview.md`, ADR 0026) | (b) D-08 | #512 Doc follow-up |

## 3. Working copy (S1)

| # | Edit | Where | Tag | Sources |
|---|---|---|---|---|
| W-01 | `WCE0` / `WCE5`: conflicts per `(item_key, field)` | `working-copy-edit-ops` | (b) D-06 | #512 0029 Q1 |
| W-02 | `WCE7` / `WCE9`: an unaccepted change is `REJECTED`, `DROPPED_STALE` on conflict | `working-copy-edit-ops` | (b) D-07 | #512 0029 Q2 |
| W-03 | `WCE4` and the target architecture name one change feed, `…/workspace/ops?since=` | `working-copy-edit-ops#WCE4`; `mvp-target-architecture.md` §5 | (a) | #512 0029 Q3 |
| W-04 | `WCE8`: the lock covers the declared inputs and the sets they rate | `working-copy-edit-ops#WCE8` | (b) D-30 | #512 0029 Q4 |
| W-05 | `WCE11`: a named server path accepts under the person's standing choice; the switch per stage on Můj Vedoucí, off by default | `working-copy-edit-ops#WCE11` | (b) D-31 | #512 0029 Q5; #514 N7 |
| W-06 | `WCE1` gains decision, expected-answer and done-when kinds | `working-copy-edit-ops#WCE1` | (b) D-44 | #513 13 |

## 4. Evidence and reports (S2, S3)

| # | Edit | Where | Tag | Sources |
|---|---|---|---|---|
| E-01 | AC-08's §3.4 row gains `evidence-integrity#5` and `segment-maps-and-drilldown#10`; chunk 5's test reads "one authority per evidence source" | master §3.4; `evidence-integrity#5` | (a) | #515 G61 |
| E-02 | Move `evidence-integrity#1` from E20 to E32 (or a W0 row), 9b staying in E20; a `master_check` rule: no chunk later than a row that needs it (`mvp-master-plan#MP8`) | contracts; master MP8 | (a) | #515 G62 |
| E-03 | `report-delivery#RD0` defines result numbers (ledger refs) apart from design and method facts (typed blocks from the specification); the validator checks every other prose number; both deliverables | `report-delivery#RD0` | (a) | #515 G63 |
| E-04 | Freeze "Interní dokument" on the frozen `KnowledgeSource` (`client-knowledge-lifecycle#K8`, with ADR 0021's defect note); RD0 checks both deliverables; AC-13 says which reports it means | `client-knowledge-lifecycle#K8`; RD0; acceptance | (a) | #515 G64 |
| E-05 | New `mvp-acceptance-harness#16` (W3): the per-number provenance walk; AC-15's row gains it and `run-qc-and-checkpoint#RQC12` | plan; master §3.4 | (a) | #515 G65 |
| E-06 | `report-delivery#RD3`: the approve response and review state carry the report's kind (`internal_only: false` for the client report); RD2's reader states it | `report-delivery#RD3` | (a) | #515 G66 |
| E-07 | New `run-qc-and-checkpoint#RQC12` (W1): `weight_role` and `weight_column` in `_population_note` and "Respondenti a výpočet" | plan; contracts | (a) | #515 G78 |
| E-08 | `run-qc-and-checkpoint#RQC9`: the valid-n authority is the organization's readiness methodology in force, not a code constant | `run-qc-and-checkpoint#RQC9` | (a) | #514 7 |
| E-09 | `RQC4` / `RQC5`: after a replacement the report and the Lead read the newer run and name both | `run-qc-and-checkpoint` | (b) D-36 | #512 0036 Q2 |
| E-10 | `report-delivery#RD6`: client report chapters fixed except where a template marks them movable; no paragraph merge | `report-delivery#RD6` | (b) D-35 | #512 0035 |
| E-11 | New `report-delivery#RD11`: Deep Research accepted findings as cited context in the client report (MVP-26) | plan; contracts | (a) | #513 10 |
| E-12 | `assumptions-and-open-answer-coding#AOC0` / `#AOC2`: SUPPORTED and CONTRADICTED need an admitted respondent claim; status set UNTESTED / SUPPORTED / CONTRADICTED / RETIRED | that plan | (b) D-16 | #512 0033 |
| E-13 | `AOC2` names its producer: an assumption inherits its linked research question's EVIDENCE items, no engine change | `assumptions-and-open-answer-coding#AOC2` | (a) | #515 G72 |
| E-14 | `client-data-in-analysis#0` (G51): the methodology owner decides a client number's support, metric and interval (MQ-18) | `client-data-in-analysis#0` | (a) | #510 Doc follow-up |
| E-15 | Data-contract acceptance and quality report in the Brief drawer, the Data tab read-only: a new S3 W3 UI chunk with `client-data-in-analysis#2` | `client-data-in-analysis`; contracts E17 | (b) D-37 | #514 3, N4 |
| E-16 | `report-delivery`: settle RD0-RD4's wave (W2 in `report-delivery.md:75`, W3 in E20) | plan; contracts | (a) | #514 11 |

## 5. Deep Research (S2)

| # | Edit | Where | Tag | Sources |
|---|---|---|---|---|
| R-01 | New `deep-research-web-search#51a` (W1, E12): `by_route` in `CoverageLedger` and `composed_routes` on the run's record | plan; contracts | (a) | #515 G67 |
| R-02 | `deep-research-web-search#53`: one refusal behaviour, a terminal failure retryable under fresh pins; AC-11's negative case and I-R follow | `#53`; acceptance | (b) D-10 | #515 G68 |
| R-03 | `#54` / `mvp-acceptance-harness#11`: the acceptance study cites a known dead URL so the run meets the archive | those chunks | (b) D-11 | #515 G70 |
| R-04 | §4 gains a row for `aia_deep_research_lead` (needs agent-directed mode; evidence: the plan records `versions.lead`); AC-11's row gains `#36`, `#37`, `#51a` | master §4, §3.4 | (a) | #515 G71 |
| R-05 | ADR 0032's *Open for Nigel* 1 reads the struck-out MVP-27 text; the release route is decided (MVP-27 as amended, #500). Correct the ADR before it is accepted; AC-11's wording to the amended text | ADR 0032 (#512); acceptance | (a) | #516 (dropped item); #512 0032 |
| R-06 | "Frozen retrieval" wording in CLAUDE.md §2 and ADR 0021 | docs PR | (b) D-08 | #512 0032 Q2 |
| R-07 | Master §11.3 S4 cites `deep-research-web-search#54`; it should be `#53` | master §11.3 | (a) | #513 14 |

## 6. Client pages and Settings (S3)

| # | Edit | Where | Tag | Sources |
|---|---|---|---|---|
| K-01 | Fold `client-workspace` C6-C9 (MP3): C6 → K2f/K3; C7 closed, superseded by `client-budget`; C8 → `client-data-in-analysis#2/2a/3` plus E-15's UI chunk; C9 → K6. Drop "[C6, C7, C8]" from K2's completion line | master §3.2; `client-workspace`; `client-knowledge-lifecycle` | (a) | #514 1, N5 |
| K-02 | New S3 W1 UI chunk: the posture and the wallet ceiling edited on Profil → Pravidla (OWNER/ADMIN), listed read-only in Settings; added to I15 | plan (with `#53`, `LO1`); master I15 | (b) D-17 | #514 2, N1, N2, N12 |
| K-03 | Hide the Simulace tab and "Nová simulace" (MVP-31). #513 proposes `client-workspace#C10`, but `C10` is taken (`[x]`): use `C11` | `client-workspace` | (a) | #513 11; #514 N11 |
| K-04 | `study-data-lifecycle#SDL3`: the entry points (an admin deletes a client from Settings with a typed confirmation; a researcher deletes a source from its card; knowledge is retired); new `#SDL4b` (one source). Export and erase-one-person stay an operator procedure | `study-data-lifecycle` | (b) D-29 | #513 12; #514 9, N6 |
| K-05 | A read-only OWNER/ADMIN spend view over MVPQ-07's content-free rows, in Settings | `develop-spend-attribution` or `two-roles-human-ai-gates` | (b) D-47 | #513 Q22; #514 N12 |
| K-06 | `develop-spend-attribution#5b` gains the infrastructure-charges line | that chunk | (a) | #513 13 |
| K-07 | New `two-roles-human-ai-gates#8`: deactivate a member from Settings → Přístup | plan; contracts | (b) D-27 | #513 9 |
| K-08 | "Settings is read-only" (`lead-orchestration.md:91,104`; `mvp-development-plan.md:89`) → "AI route configuration is read-only" | those files | (a) | #514 §7 |
| K-09 | Stale UI copy, to the owning plans' next chunk: `cs:513` (Data Library "not in AIA"), `cs:3099` (client report "missing"), `cs:175,242` (role grants), `cs.ts:1563` (respondents always fictional), `aia.research.lead` / `STUDY_LEAD` labels, `settings-guide.ts:3`, `cs.ts:1404`, `DeepResearchSettingsPanel.tsx:8-9`, the draft-test copy (with L-15) | owning plans | (a) | #514 §7 |

## 7. Production (S3)

| # | Edit | Where | Tag | Sources |
|---|---|---|---|---|
| P-01 | `production-environment#PE4`: a proxy blocking private and metadata ranges only, the application's per-hop checks the boundary | `#PE4` | (b) D-19 | #512 0031 Q2 |
| P-02 | `PE0`-`PE3`: the hostname and the confirmed sizes and quota | those chunks | (b) D-20 | #512 0031 Q1 |
| P-03 | `PE7`: tagged application inference profiles in production | `#PE7` | (b) D-21 | #512 0031 Q3 |
| P-04 | New `PE10`: an audited operator command that creates the first organization and owner; production starts empty | plan; contracts | (b) D-22 | #513 3, Q3 |
| P-05 | New `PE11`: an external security review before the first client | plan | (b) D-23 | #513 3, Q1 |
| P-06 | `PE1` gains a CSP | `#PE1` | (a) | #513 3 |
| P-07 | `PE9b`'s alarms named: uptime probe, oldest queued step's age, Bedrock spend, the production error tracker; a named on-call person | `#PE9b` | (b) D-26 | #513 3, Q5 |
| P-08 | `PE9a` and `study-data-lifecycle#SDL5`: RPO 24 h / RTO 4 h, the database and S3 restored together, proved once | those chunks | (b) D-25 | #513 3, Q4 |
| P-09 | New `architecture-enforcement#12`: per-member rate limits | plan | (b) D-24 | #513 4, Q2 |
| P-10 | A release-checklist line: terms, privacy notice, client DPA, the data owner's panel-licence yes; the first-sign-in notice screen | master §9 (release checklist) | (b) D-28 | #513 Q6 |

## 8. Acceptance (S3)

| # | Edit | Where | Tag | Sources |
|---|---|---|---|---|
| A-01 | AC-01: "a user of another organization gets 404, not 403, on every study route" in both acceptance files; `mvp-acceptance-harness#14` lists AC-01 | acceptance; `parity-matrix.json`; harness#14 | (a) | #515 G73 |
| A-02 | AC-14 reworded to typed settings plus the per-run composition digest (L-08); harness#14 lists AC-14 | acceptance; harness#14 | (b) D-09 | #513 8; #515 G74 |
| A-03 | New `mvp-acceptance-harness#17` (W0, E01): the acceptance verdict from its own JUnit, parity beside it; `parity-matrix.json:2573` `project.memory` corrected | plan; matrix | (a) | #515 G75 |
| A-04 | `mvp-acceptance-harness#3`: a declared operator bootstrap named in the record (pairs with P-04), everything after it over HTTP, the worker as a subprocess; an import-linter contract for `tests/acceptance` | `#3` | (a) | #515 G76 |
| A-05 | Each criterion's tier-A and tier-B projection in both acceptance files; the record per criterion per tier (`#6`, `#14`); AC-15's AWS clause given its tier-A meaning | acceptance; harness | (a) | #515 G77 |
| A-06 | `mvp-acceptance-harness#5`'s front matter: only AC-12 is an existing path; settle its wave (W1-W4 in its plan, W5 in E24) | harness#5; contracts | (a) | #514 11; #515 A7 |
| A-07 | `mvp-acceptance-harness#14`: refresh the three 18.6.6 ledgers and remove the L-04 / L-29 contradiction | harness#14 | (a) | #513 13 |
| A-08 | `mvp-acceptance-harness#10` gains axe (serious and critical) | harness#10 | (b) D-48 | #513 13, Q23 |

## 9. ADRs and the register

| # | Edit | Where | Tag | Sources |
|---|---|---|---|---|
| X-01 | `mvp-master-plan#MP5`: the ADRs exist as Proposed (#512); the chunk stays open until each is accepted, and its text names 0028-0038, with 0033-0036 the four ADR 0026 decision 4 requires | master MP5 | (a) | #512 |
| X-02 | G41's row ("two settled features have no ADR yet") points at 0035 and 0036, Proposed | master §6.1 | (a) | #512 |
| X-03 | The ADR index rows for 0028-0038, ADR 0009's status line and the index's "Production compute" item (0031), ADR 0008's amendments list (0032), when each is accepted | docs PR | (b) D-08 | #512 Doc follow-up |
| X-04 | G58-G78 added to master §6.1 as written in #515, each with the chunks above | master §6.1 | (a) | #515 |
| X-05 | G10's anchor `pyproject.toml:276-282` → `:279-288`; trace 5 B2's "Failed" → parks | master §6.1; `.planning/evidence/` trace (evidence stays dated: a note, not an edit) | (a) | #515 §4 |
| X-06 | On the design artifact: accepting the working copy is `WCE7` and discarding it `WCE9` (not `#15`); `#43` does not exist; bare `#3`, `#5`, `#7` name their plan | the design session's artifact | (a) | #513 14 |

## 10. Docs PR only (not plan edits)

Listed so nothing is lost; part 2 writes them under Doc follow-up, a docs PR applies them.

| # | Edit | Tag | Sources |
|---|---|---|---|
| D-PR-1 | `docs/product/README.md`: 11 stages, not 13 (ADR 0026); one Researcher role plus OWNER/ADMIN, no grants (ADR 0019); no classic interface (ADR 0018); the three dead links at `:171-173` | (a) | #513 |
| D-PR-2 | `overview.md:557` V2 not V3 (MVPQ-01); `:557` and `:598` "the Class B route is deferred" | (a) | #513 |
| D-PR-3 | Finding F-1 into `open-items.md`: `tools/ui_workbench/capture.mjs:61-75 @ 854c209` imports CommonJS `playwright/index.js` as ESM | (a) | #514 |
| D-PR-4 | ADR 0020's draft-test paragraph, gone with `system-prompts-settings#14` | (b) D-15 | #514 §7 |

---

## New questions for Nigel (C)

Neither is among the 48. Each would join the answer page as D-49 and D-50 if the coordinator agrees.

### C-1. When do new runs switch to `-5`: now, or when its register entry exists?

- **Question.** Should new runs pin `-5` as soon as `signed-off-sociomap-method#8` is built, with
  every `-5` map internal until the methodology owner registers it, or only once his entry exists?
- **Context.** #512's ADR 0038 pins `-5` at once and keeps it `INTERNAL_ONLY` meanwhile. #510's E-1
  lands it only "together with, or after, MQ-01's answer, so new runs are never pinned to a method
  the register does not approve while the web cannot draw it". The two inputs disagree; D-13 settles
  whether `-1` is computed beside it, not when the switch happens.
- **Example.** The W1 build is done on 2026-11-02; Arigamaru's entry comes on 2026-11-20. Under (a),
  runs between those dates have `-5` maps marked "Interní" (no client report map), and `-3` is no
  longer computed for them. Under (b), they still pin `-1` + `-3`, whose `-3` maps are approved for
  clients, and switch on the 20th.
- **Options.** (a) Pin `-5` when built (ADR 0038); (b) pin `-5` only with MQ-01's entry (#510 E-1);
  either changes S-02's landing condition and ADR 0038's text.
- **Recommendation.** (b). Until the entry exists, `-3` is the only map a client may receive, and
  W1-W2 study work should not lose that. The switch is a one-line change once the entry lands.

### C-2. Metodika's comparison for `-5` in the MVP

- **Question.** Should Metodika's comparison (an edit beside what is in force) show `-5`'s
  credibility, respondent map and segments in the MVP, or is the in-force label and editor start
  enough until after the MVP?
- **Context.** Metodika is formally after the MVP (#514 §4.1), yet `-5` changes it: S-03 makes `-5`
  the method in force (needed for correctness). The comparison's `MapSummary` carries none of `-5`'s
  new outputs (#510 E-5), so an edit of a credibility or segment parameter shows "no difference". If
  D-14 allows editing `-5`, that comparison misleads.
- **Example.** An admin raises the split-half repetitions from 50 to 200 and presses Porovnat. Without
  E-5, the comparison shows identical maps and no change; with it, the credibility line moves from
  "0,81" to "0,83".
- **Options.** (a) E-5 in the MVP (a `methodology-tab` chunk, W2); (b) after the MVP, and Metodika
  says the comparison covers object positions only; (c) after the MVP, and editing `-5` disabled
  (D-14 (b)).
- **Recommendation.** (b): one sentence on the screen instead of a W2 chunk outside the critical path.
