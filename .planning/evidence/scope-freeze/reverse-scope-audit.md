# Reverse scope audit: from the product to the plan

Written 2026-10-20 for the scope freeze (the coordinator's request, on Nigel's worry that the plan does
not yet cover the full scope). Against `develop` @ `854c209`. Read-only analysis: nothing in the code or
any plan was changed. **Evidence, not a plan**: proposals are in the pull request body, and the master
plan is edited only through `mvp-master-plan#MP3`/`MP13` by its owner.

## Method

The existing checks ran plan → code (`mvp-master-plan` §6, §7, the traces, MP12). This one runs
product → plan. Four sources were walked, each by a read-only pass, and every item was looked up in
every plan file's front-matter and body (including `plans/done/`) under synonyms before being called
MISSING:

1. **Product scope**: `docs/product/README.md`, `mvp-cohesion.md` (F1-F19, Q1-Q29),
   `mvp-owner-decisions.md` (MVPQ-01-12), master §11.1, `overview.md` § MVP roadmap (MVP-1-33),
   `docs/migration/mvp-acceptance.md`.
2. **Canonical design**: `prototypes/research-lead-v2/src` (MVPQ-01), and the owner's design artifact
   (claude.ai artifact `JrWZXosJtKVLckHhArngeV`, read 2026-10-20 with the Artifact read action; its
   POSTAVENO / PLÁN / OTEVŘENO marks were checked against the plans).
3. **18.6.6**: `docs/migration/interface-screens.json`, `legacy-route-ledger.json`,
   `legacy-ui-functions.json`, `parity-matrix.json`.
4. **Cross-cutting needs** of a real first release.

Plus one decision that arrived during the audit: **the MVP ships `aia-sociomap-5`** (Nigel,
2026-10-20, relayed by the coordinator), so its user-visible capabilities get their own section (§5).

**Statuses.** COVERED (plan#chunk; "built" = a done chunk or code, anchored), PARTLY (what is
missing), MISSING (no chunk; what was searched), OUT (decided out, with the anchor). Code anchors are
`file:line @ 854c209` unless stated. Plan#chunk is `plan#chunk-id`.

**Limits.** Nothing was run. A COVERED row means a chunk is written for it, not that the chunk is
sufficient; the master plan's traces judge sufficiency. Row counts are per grouped capability, not per
route or function.

## 0. Headline

- **The research engine is thoroughly planned; operating a product for users is not.** Every
  acceptance criterion has chunks (§3.4), but no plan creates the first organization in production,
  deactivates a member, rate-limits the API, states RPO/RTO, restores S3 with the database, runs a
  security review, or provides user documentation, terms or a support channel (§4).
- **`aia-sociomap-5` is built in the domain and reaches no one.** No run pins it
  (`domain/research_sociomap.py:323-329`), the register approves only `-3`
  (`domain/sociomap_register.py:54`), the web reads it as an unnamed method
  (`apps/web/src/lib/object-map-view.ts:20`) and draws none of its credibility, respondent map, taste
  segments or unplaced objects. `signed-off-sociomap-method` lists "making `-5` the default" as not in
  that plan (`signed-off-sociomap-method.md` § Not in this plan), and no other plan picks it up (§5).
- **The Lead's conversation controls have no build chunk.** Stop a turn, stop an approved plan, page
  older messages, copy, edit and resend: `research-lead-workbench#12` only *verifies* them, and the API
  has no cancel or paging route (`apps/api/src/aia_api/routers/lead.py:350-440`).
- **A built component is not mounted.** `ItemInspector.tsx` (with `lib/inspector-stack.ts`,
  `research-lead-workbench#2` ticked) is imported only by its own test; the workbench's inspector is the
  readiness panel (`components/workbench/Workbench.tsx:475-481`).
- **The 18.6.6 ledgers are stale in the other direction**: many items they mark LEGACY or NOT_STARTED
  are built (the gateway, usage ledger, project memory, reports, run cost, cancel and retry, population
  and audience routes). Nobody owns refreshing them, and two of them still map out-of-scope capabilities
  to MVP criteria (L-04, L-29).
- **The authoritative product document is stale.** `docs/product/README.md` describes 13 lifecycle
  stages (the workbench has 11), a reviewer role and grants (ADR 0019 retired both), a reachable
  classic interface (ADR 0018), and links three documents that never existed (`README.md:171-173`).

Counts across the 313 rows below (a row with a split status counts under both): COVERED 158 (56 of them
built), PARTLY 84, MISSING 49, OUT 23, OPEN 1.

## 1. Product scope

| # | Capability | Source | Status | Where | Note |
|---|---|---|---|---|---|
| P-01 | Org → Client → Study isolation; 404 across clients | README:30-53 | COVERED (built) | `two-roles-human-ai-gates#3`; `mvp-acceptance-harness#5`; AC-01 | |
| P-02 | Scope never from model arguments | README:50-53 | COVERED (built) | `domain/ai_tools.py:56` | |
| P-03 | Roles: researcher, reviewer, admin | README:21-25 | COVERED (built, reshaped) | `two-roles-human-ai-gates#1-4,7` | ADR 0019: one Researcher + OWNER/ADMIN; README stale |
| P-04 | Admin manages clients, studies, access, budgets | README:25 | COVERED (built) | `routers/scope.py:311-583` | |
| P-05 | No client login | README:27,161 | OUT | `mvp-acceptance.md:119` (MVP-2) | |
| P-06 | Client-first navigation | README:57-74 | COVERED (built) | `done/client-first-ia` | README:64 "grant" stale |
| P-07 | Hide Simulace until simulation is built | overview:602 (MVP-31) | **MISSING** | — | Still offered: `ClientContext.tsx:137`; searched "MVP-31", "Simulace", "hide" |
| P-08 | Client overview: work, results, knowledge, approvals | README:111 | COVERED (built) | `client-workspace` C1-C5 | |
| P-09 | Cross-client portfolio, "what needs me" | README:72,112 | **PARTLY** | per-client tables only | Projektová paměť asks a client first (`GlobalPages.tsx:163-199`) |
| P-10 | Project memory: design reuse with citation | README:119; AC-12 | COVERED (built) | `project-memory-reuse`; `client-knowledge-lifecycle#K7a` | |
| P-11 | Memory over approved reports and findings | README:119 | **PARTLY** | — | Search matches designs only (`application/project_memory.py:12-17`) |
| P-12 | Knowledge layers; propose → approve → revision | README:76-80 | COVERED | `two-roles#5a`; `client-knowledge-lifecycle#K3`, `#K4` | |
| P-13 | Knowledge kinds | README:117 | COVERED (built) | `domain/knowledge.py:175-187` | |
| P-14 | Intake: documents, datasets, web, Deep Research | MVP-18; AC-10 | COVERED | `client-knowledge-lifecycle#K2`, `#K2e`, `#K2f`, `#K8` | web intake open |
| P-15 | Client-level source extraction (AC-02 exception) | MVPQ-08 | COVERED | `client-knowledge-lifecycle#K8`; `lead-orchestration#LO13` | |
| P-16 | Review queue grouped by source | README:68-69 | COVERED | `client-workspace#C6` (needs K3) | |
| P-17 | Data tab | README:70 | **PARTLY** | `client-workspace#C8` | C8 contradicts F19 / ADR 0027; re-scope pending MP3 |
| P-18 | Owned materialized child | MVP-7 | COVERED | `client-knowledge-lifecycle#K5`; `research-lead-workbench#22` | G28: read by nothing yet |
| P-19 | Promote client dimension to shared LIVE | README:118 | OUT | `mvp-acceptance.md:123` | |
| P-20 | Shared intelligence never takes client data | README:80 | COVERED (built) | `domain/population/errors.py:77` | |
| P-21 | Population registry, read-only | README:71 | COVERED (built) | `population-operations` | |
| P-22 | Research lifecycle (13 stages) | README:91-97 | **PARTLY (doc drift)** | 11 stages, `lib/workbench-stages.ts:22-32` | README never reconciled with ADR 0026 |
| P-23 | Simulation lifecycle and Studio | README:99-114 | OUT | `mvp-acceptance.md:118` | |
| P-24 | An edit reopens only affected stages | README:88-89; AC-07 | COVERED | `working-copy-edit-ops#WCE7` | |
| P-25 | Workbench, V2 canonical | MVP-3; MVPQ-01 | COVERED | `research-lead-workbench#12,14-23` | overview:557 "V3" stale |
| P-26 | Every AI action through the Lead; server spend check | MVP-8; F5 | COVERED | `research-lead-workbench#17-22`; `lead-orchestration#LO15`; `system-prompts-settings#14` | |
| P-27 | Lead at every width | MVPQ-11 | COVERED | `research-lead-workbench#26`, `#27` | |
| P-28 | Eleven workers | MVP-12 | COVERED | `lead-orchestration#LO9a-c`; `report-delivery#RD6`; `run-qc-and-checkpoint#RQC3-4` | |
| P-29 | Prompts editable and pinned | MVP-32 | COVERED | `system-prompts-settings#7`, `#13` | |
| P-30 | Envelope, plan card, chat start, continuation | F13; Q14; Q25 | COVERED | `lead-orchestration#LO0-LO6`, `#LO16` | |
| P-31 | Standing autopilot; Deep Research from every stage | MVP-3 | OUT | `mvp-acceptance.md:122`; `research-lead-workbench#24-25` | |
| P-32 | Lead sees all stored results | MVP-15; F4 | COVERED | `lead-orchestration#LO7`, `#LO8`; `research-lead-workbench#20-21` | |
| P-33 | Edit vocabulary, stable ids, per-change accept | F11 | COVERED | `working-copy-edit-ops#WCE0-WCE3c`, `#WCE6` | |
| P-34 | Item chip in Lead prose renders current number ("Q9, now Q7") | cohesion:366-368 | **MISSING** | — | searched "current number", "chip", "Lead's prose" |
| P-35 | Two researchers on one study | F12; Q16 | COVERED | `working-copy-edit-ops#WCE4-6`, `#WCE12` | |
| P-36 | Sociomap input lock and recorded unlock | F13.4 | COVERED | `working-copy-edit-ops#WCE8`, `#WCE8b` | |
| P-37 | Structural auto-accept per stage | MVP-14 | COVERED | `working-copy-edit-ops#WCE11` | |
| P-38 | Own Lead: self-updates, rollback, handover | F14; Q26 | **PARTLY** | `lead-orchestration#LO11` | F14's periodic review, proposal size bound and "no client data in a Class C file" test absent |
| P-39 | Routing end to end | X8 | COVERED | `working-copy-edit-ops#WCE13`; `run-qc-and-checkpoint#RQC11`; `evidence-integrity#10` | |
| P-40 | Tracked assumptions | MVPQ-02 | COVERED | `assumptions-and-open-answer-coding#AOC0-3`; `report-delivery#RD9` | |
| P-41 | Open-answer coding | MVPQ-02 | COVERED (method open) | `assumptions-and-open-answer-coding#AOC4-9`; `report-delivery#RD10` | MVPQ-02b |
| P-42 | Respondents from LIVE; audience and dimensions reach them | F15; AC-05 | COVERED | `audience-catalogue-cpu#4`; `complete-study-report#B6`; `sociomap-formula-corrections#I0-I1`; `run-qc-and-checkpoint#RQC6,8,10` | |
| P-43 | Quotas, support forecast, one valid n | G23; G29 | COVERED | `run-qc-and-checkpoint#RQC6`, `#RQC7`, `#RQC9` | |
| P-44 | Worker kill loses no paid work | AC-06 | COVERED | `run-qc-and-checkpoint#RQC0` | |
| P-45 | No fake progress | README:144-145 | COVERED (built) | `step-activity` | |
| P-46 | Run QC warns; replace is a new run | MVP-24; F18 | COVERED (method open) | `evidence-integrity#2-4`; `run-qc-and-checkpoint#RQC1-5` | MVPQ-10 |
| P-47 | Every number admitted; findings cite | MVP-23/28/29; AC-08 | COVERED | `evidence-integrity#1`, `#5`, `#6` | |
| P-48 | Module with no finding blocks the report | MVPQ-04 | COVERED | `evidence-integrity#9a`, `#9b` | |
| P-49 | Segment evidence | X1 | COVERED | `segment-maps-and-drilldown#10` | |
| P-50 | Object map | README:116 | COVERED (built) | `domain/sociomap/engine_v2.py:845` | now `-5` per §5 |
| P-51 | Respondent and segment maps | MVP-4/16/17; AC-09 | **PARTLY** | `sociomap-formula-corrections#3`; `segment-maps-and-drilldown#0-4`, `#9` | built as `-5`; see §5 |
| P-52 | Map filters; internal drill-down | MVP-16; MVPQ-03 | COVERED | `segment-maps-and-drilldown#5-8` | |
| P-53 | Node drag saves a view override, never truth | README:147-148; AC-09 | **MISSING** | — | `apply_view_overrides` is contract 2 only (`domain/sociomap/view.py:170`); camera only today |
| P-54 | Sociomapa matrix and comparison modes | README:116 | **MISSING (undecided)** | — | searched "matrix mode", "comparison", "compare maps" |
| P-55 | Sociomapa what-if | README:116 | OUT | `mvp-acceptance.md:118` | |
| P-56 | Results: headline, findings, evidence | README:115 | COVERED | `evidence-integrity#6`; `research-lead-workbench#20` | |
| P-57 | Charts on Results | README:115 | **PARTLY** | report charts built (`report_docx/charts.py`) | no Results chunk |
| P-58 | Result data export (CSV/XLSX) | README:115 | **MISSING (undecided)** | — | report downloads only |
| P-59 | Client dataset in analysis under a contract | MVP-19; MVPQ-05; AC-10 | COVERED (method part open) | `client-data-in-analysis#0-9`; `evidence-integrity#8a-b` | |
| P-60 | Client data in Brief; own-dimension Build | F19; Q23 | COVERED | `client-data-in-analysis#8`; `research-lead-workbench#18,22` | |
| P-61 | Live Design Research, open posture | MVP-27 (#500); AC-11 | COVERED | `deep-research-web-search#1,27,51-54` | |
| P-62 | Class B search provider | MVP-27; Q29 | OUT (deferred) | master §3.3 | overview:557,598 still say otherwise |
| P-63 | "Ověřeno, přidat zdroj" | AC-11 | COVERED (built) | `application/verified_sources.py:47` | |
| P-64 | Deep Research context in the **client** report | MVP-26 | **PARTLY** | internal built (`application/contextual_report.py`) | `client_report.py` has no context path; no chunk |
| P-65 | Deep Research sources as a dataset | MVP-26 | COVERED | `deep-research-web-search#37` | |
| P-66 | Evaluations 25/26/39 | MVPQ-06 | COVERED (thresholds open) | `deep-research-web-search#25,26,39`; `mvp-acceptance-harness#11` | |
| P-67 | Budget before paid calls; AWAITING_BUDGET | AC-04 | COVERED | `lead-orchestration#LO0,LO1,LO15`; `client-budget#CB5` | |
| P-68 | Two meters, Czech names written once | F16; Q20 | **PARTLY** | `lead-orchestration#LO1`; `research-lead-workbench#15` | names unassigned |
| P-69 | No silent provider fallback | AC-03 | COVERED (built) | `domain/ai_models.py:424` | |
| P-70 | Route-class refusal says who fixes it | G1; G3 | COVERED | `lead-orchestration#LO12a-b`; `run-qc-and-checkpoint#RQC8` | |
| P-71 | Human sign-off; deliverable gate | MVPQ-09; AC-13 | COVERED | `report-delivery#RD0`, `#RD7` | |
| P-72 | Report and map approved separately | F17 | COVERED | `report-delivery#RD2-RD4` | |
| P-73 | Client DOCX + PDF | AC-13 | COVERED | `report-delivery#RD1` | |
| P-74 | Report revisions, stored model, writer edits | MVP-12; G50 | COVERED | `report-delivery#RD5`, `#RD5a`, `#RD6`, `#RD8` | |
| P-75 | Respondent/segment figures in reports | G54 | COVERED | `segment-maps-and-drilldown#9` | method per §5 |
| P-76 | Lineage matrix; every number traced | AC-15 | COVERED | `research-integrity-report#6-8` | |
| P-77 | Client-facing analysis prose | MVP-10 | OUT | `mvp-acceptance.md:121` | |
| P-78 | Report depth tiers | MVP-6 | OUT | `mvp-acceptance.md:120` | |
| P-79 | Spend reconciles; infrastructure charges line | MVP-30; AC-15 | **PARTLY** | `develop-spend-attribution#1-5b`; `deep-research#4`; `production-environment#PE7` | no chunk produces the infrastructure line |
| P-80 | Immutable usage ledger | README:120 | COVERED (built) | `infrastructure/ai_usage_repository.py` | |
| P-81 | Typed config recorded on the run; malformed edition refuses | AC-14 | **PARTLY** | typed + fail-fast built (`apps/api/src/aia_api/config.py:282`); `mvp-master-plan#MP6` | recorded on the run: no chunk; no edition file exists (= L-25) |
| P-82 | Delete path, 30-day residual | MVPQ-07 | COVERED | `study-data-lifecycle#SDL0-6` | |
| P-83 | Cognito + Google | README:165 | COVERED | `production-environment#PE0-1` | |
| P-84 | Harness tiers A and B | MVP-5/20/21 | COVERED | `mvp-acceptance-harness#1-15` | |
| P-85 | Classic interface reachable | README:83-84 | OUT (superseded) | ADR 0018 | README stale |
| P-86 | Real panels, signup, billing | README:161-165 | OUT | README:159-165 | |
| P-87 | `scope-model.md`, `research-lifecycle.md`, `methodology-contract.md` | README:171-173 | **MISSING (dead links)** | — | never in git history |

## 2. Canonical design (V2 and the design artifact)

Prototype anchors are under `prototypes/research-lead-v2/src`, built anchors under `apps/web/src`.
"Mark" is the design artifact's: B POSTAVENO, P PLÁN, Q OTEVŘENO, — unmarked.

### 2a. Frame and header

| # | Element | Prototype | Mark | Status | Where | Note |
|---|---|---|---|---|---|---|
| D-01 | Study header (client, study) | Shell.tsx:28-33 | B | COVERED (built) | `components/workbench/Workbench.tsx:574-579` | |
| D-02 | One-line study state | Shell.tsx:34 | — | PARTLY | `Workbench.tsx:580` readiness only | run/report wording unowned |
| D-03 | "Fiktivní data a zdroje" chip + panel | Shell.tsx:36 | — | **MISSING** | results label origin only | searched "Fiktivní data a", "synthetic chip" |
| D-04 | "Čeká na vás: N" popover list | Shell.tsx:37-44 | — | PARTLY | `Workbench.tsx:582` jumps to first | |
| D-05 | Budget meter with breakdown | Shell.tsx:45-48 | P | PARTLY | `Workbench.tsx:583-587` | `lead-orchestration#LO1,LO14`; override S2 |
| D-06 | Deep Research permission panel in header | Shell.tsx:49 | P #53 | PARTLY | Settings built | master §11.3 S4 points to `#54` (connector probing): wrong pointer |
| D-07 | Study menu | Shell.tsx:50-60 | — | PARTLY | `Workbench.tsx:589-600` | |
| D-08 | Phase navigator, 11 stages | Shell.tsx:65-100 | B | COVERED (built) | `Workbench.tsx:608-636` | |
| D-09 | 13 stage states | model/status.ts:12-58 | — | PARTLY | 6 tones; provider wait reads inert (`research/lane.ts:134`) | defect |
| D-10 | "Přehled fází" popover | Shell.tsx:94-128 | — | **MISSING** | — | searched "Přehled fází", "lifecycle overview" |
| D-11 | Rail badges | Shell.tsx:130-141 | — | PARTLY | `Workbench.tsx:638-645` | |
| D-12 | Split, focus modes, keys | Split.tsx | B | COVERED (built) | `components/workbench/Split.tsx:58` | |
| D-13 | Skip link | App.tsx:46 | — | COVERED (built) | `Workbench.tsx:442` | |
| D-14 | "Desktop only" under 1100 px | App.tsx:45 | P | OUT (superseded) | MVPQ-11 → `research-lead-workbench#26-27` | |
| D-15 | Studies table: Krok / Pozornost / Poslední činnost | Shell.tsx:143-173 | — | PARTLY | `components/aia/clients/StudyList.tsx:92-97` | no chunk |
| D-16 | Prototype docs, scenario panel | DocsView.tsx | — | OUT | prototype only | |

### 2b. Conversation

| # | Element | Prototype | Mark | Status | Where | Note |
|---|---|---|---|---|---|---|
| D-17 | "Vidí" chip with revision/run/draft | Conversation.tsx:87-92 | P #16 | PARTLY | `LeadPane.tsx:224` | `research-lead-workbench#16` |
| D-18 | "Co Vedoucí čte" panel | Conversation.tsx:93 | — | COVERED | `research-lead-workbench#15`; `lead-orchestration#LO7-8` | |
| D-19 | Conversation focus toggle | :94 | — | COVERED (built) | `LeadPane.tsx:227` | |
| D-20 | "N nové zprávy" | :40-78 | — | PARTLY | `LeadPane.tsx:297-298` | |
| D-21 | Load older messages | :98 | — | **MISSING** | no paging API | `#12` only verifies |
| D-22 | Fold finished activities | :99-138 | — | **MISSING** | — | |
| D-23 | Streaming text | lead.ts:22-34 | — | **MISSING** | typing dots only | owner question |
| D-24 | Copy a message | :150 | — | **MISSING** | — | `#12` only verifies |
| D-25 | "Proč tato odpověď" | :171 | — | COVERED | `research-lead-workbench#15`; `lead-orchestration#LO8` | |
| D-26 | "Platilo pro revizi X · aktuálně Y" | :159 | — | PARTLY | `LeadPane.tsx:348` | |
| D-27 | Source chips under replies | :167 | — | **MISSING** | `LeadOutput` has no sources | |
| D-28 | "Otevřít v artefaktu" chips | :168 | — | COVERED (built) | `LeadPane.tsx:353` | |
| D-29 | Follow-up suggestions | :175-179 | — | COVERED (built) | `LeadPane.tsx:360` | |
| D-30 | Edit and resend own message | :144-153 | — | PARTLY | badge only | |
| D-31 | "Zastaveno vámi…" | terms.ts:92 | — | **MISSING** | no turn cancel | |
| D-32 | Day dividers, notices | :142-143 | — | PARTLY | `LeadPane.tsx:339` | |
| D-33 | Activity card types | :198-230 | P #23 | PARTLY | `LeadPane.tsx:387-410` | compute/lookup types unowned |
| D-34 | Research card line | :219 | P #53 | COVERED | `research-lead-workbench#23`; `deep-research-web-search#53` | |
| D-35 | Fieldwork card updated in place | lead.ts:48-64 | P | COVERED | `lead-orchestration#LO6`; `run-qc-and-checkpoint#RQC7` | |
| D-36 | Decision card with alternatives | :232-257 | B | PARTLY | `LeadPane.tsx:468-487` | `lead-orchestration#LO4` |
| D-37 | Run-start card | scenarios.ts:233-250 | P | COVERED | `lead-orchestration#LO2,4,5,10,15` | |
| D-38 | Budget-stop card | scenarios.ts:309 | — | PARTLY | `BudgetLift.tsx` outside chat | |
| D-39 | Keep / flag / replace card | scenarios.ts:323 | P; Q MVPQ-10 | COVERED (blocked) | `run-qc-and-checkpoint#RQC1-5` | |
| D-40 | Method change routed to Metodika (X6) | scenarios.ts:381 | — | PARTLY | `research-lead-workbench#14`; `mvp-acceptance-harness#13` | no routing chunk |
| D-41 | Enter / Shift+Enter, IME | Composer.tsx:74-87 | — | COVERED (built) | `LeadPane.tsx:510-515` | |
| D-42 | ArrowUp recall | Composer.tsx:85 | — | **MISSING** | — | |
| D-43 | Queue: send now / edit | Composer.tsx:46-58 | — | PARTLY | remove only | |
| D-44 | Esc / stop the Lead | Composer.tsx:86,93 | — | **MISSING** | no cancel route (`routers/lead.py:350-440`) | |
| D-45 | Typed @ mention | Composer.tsx:22-36 | P #16 | PARTLY | pick mode only | `#16` |
| D-46 | Reference chip | :71 | — | COVERED (built) | `LeadPane.tsx:507` | |
| D-47 | Attach a file from the composer | :65-70 | — | **MISSING** | intake only on client pages | owner question |
| D-48 | Autopilot / stop an approved plan | :59,91 | — | OUT (standing, D16) / **MISSING** (stop a plan) | `lead-orchestration#LO3-6` | no "withdraw plan" chunk |
| D-49 | "Kde jsme?" structured | scenarios.ts:489 | — | PARTLY | free text today | `lead-orchestration#LO7` |
| D-50 | Return summary | :259-275 | P | COVERED | `research-lead-workbench#15`; `lead-orchestration#LO7,LO11` | |
| D-51 | Lead comments after you pause | App.tsx:20-28 | — | **MISSING** | `LO6` is finished steps only | owner question (paid) |

### 2c. Artifact frame and inspector

| # | Element | Prototype | Mark | Status | Where | Note |
|---|---|---|---|---|---|---|
| D-52 | Header version line | ArtifactPane.tsx:51-67 | — | PARTLY | `Workbench.tsx:451` | `#15`, `WCE7` |
| D-53 | Historie / Podrobnosti / Kontrakt AI | :70-73 | — | PARTLY | focus only | `#15` |
| D-54 | Proposal bar | :85-93 | P WCE6 | PARTLY | `Workbench.tsx:490-520` | `#7`, `#17`, `WCE6` |
| D-55 | "Dopad a pokrytí" | :94-101 | P WCE7 | COVERED | `#7`, `WCE6`, `WCE7` | |
| D-56 | Stale proposal bar | :77-84 | — | COVERED (built) | ProposalReview | |
| D-57 | Working-copy bar | :102-110 | P #15 | PARTLY | autosave only | artifact pointer wrong: accept is `WCE7`, discard `WCE9` |
| D-58 | Frozen bar | :111-113 | — | PARTLY | origin labels | |
| D-59 | Auto-accepted bar + Vrátit | — | B | COVERED (built) | `Workbench.tsx:526-556` | |
| D-60 | Scroll kept per artifact | :41-48 | — | **MISSING** | — | trivial |
| D-61 | Item tools (edit, @, move, remove, protected) | ui.tsx:52-119 | P | PARTLY | per-stage editors | `WCE3a-c`, `WCE8`, `#16` |
| D-62 | Change blocks at the item | ui.tsx:34-48 | P | PARTLY | listed at top | `#7`, `#17` |
| D-63 | Overlay inspector with back stack | Inspector.tsx:42-70 | — | **PARTLY: built, not mounted** | `ItemInspector.tsx` imported only by its test | `#2` ticked, no effect |
| D-64 | Source inspector | :75-86 | — | PARTLY | VerifiedSourceButton | `#20-21` |
| D-65 | Finding / claim chain inspector | :87-112 | P | COVERED | `evidence-integrity#6-7`; `report-delivery#RD7` | |
| D-66 | Pair / object inspector, "Proč jsou blízko?" | :113-137 | B | PARTLY | `ObjectMapView.tsx:421,469` | `LO9b` |
| D-67 | History inspector | :138-148 | — | COVERED | `#15`, `WCE9` | |
| D-68 | Details: inputs, feeds, workers, command log | :214-234 | — | PARTLY | `#15` | command log unowned |
| D-69 | "Jak číst mapu" | :156-163 | — | COVERED (built) | `ObjectMapView.tsx:345` | |
| D-70 | Kontrakt AI panel | :164-175 | — | **MISSING (UI)** | contract in `WCE0` | owner question |
| D-71 | Activity details | :151-155 | — | COVERED | `#23` | |

### 2d. The eleven artifact bodies

| # | Element | Prototype | Mark | Status | Where | Note |
|---|---|---|---|---|---|---|
| D-72 | Brief: objectives, decisions, context, materials | DesignStages.tsx:12-31 | P / Q | PARTLY | `BriefStep.tsx:79` | `WCE1` has no decision/context kinds |
| D-73 | Question chain: decision → … → done-when | :37-76 | P | PARTLY | research_trace | expected answer and done-when not stored anywhere |
| D-74 | Hypotheses, open questions | :77-85 | — | PARTLY | `PlanStep.tsx:78` | `#18` |
| D-75 | Tracked assumptions | SampleStages.tsx:36-59 | P | COVERED | `AOC0-3`; `#18` | |
| D-76 | Questionnaire length ≈ minutes | DesignStages.tsx:103 | — | **MISSING (producer)** | — | no per-item duration |
| D-77 | Sections, types, routing | :108-131 | P | PARTLY | `QuestionnaireStep.tsx:746` | `#17`, `WCE13` |
| D-78 | Sociomap inputs locked | fixture.ts:115 | P | COVERED | `WCE8`, `WCE8b` | |
| D-79 | Locked attention check + exclusion | fixture.ts:125 | — | **MISSING** | — | searched "attention check", "kontrola pozornosti" |
| D-80 | Dependencies | :132-139 | — | PARTLY | `#15` | |
| D-81 | Presence and item conflict | — | P | COVERED | `WCE4-6`, `WCE12` | |
| D-82 | Audience with LIVE counts | SampleStages.tsx:26-35 | — | COVERED (built) | `AudienceStep.tsx:116` | |
| D-83 | Dimensions, persona-topic chip | :64-82 | B | PARTLY | `PersonaStep.tsx:84` | `#22` |
| D-84 | Own client dimension | :83-85 | P | COVERED | `K5`, `#22`, `seg#0a` | |
| D-85 | Quotas | :97-104 | P | PARTLY | `SampleView.tsx:13` | `RQC6`, `#19` |
| D-86 | Support forecast | :105-108 | — | PARTLY | roster only | `RQC6`, `RQC9` |
| D-87 | Readiness list | :109-123 | — | COVERED (built) | `ExecutionSteps.tsx:589` | |
| D-88 | Persona source | :124-128 | — | COVERED (built) | `ExecutionSteps.tsx:908` | |
| D-89 | Fieldwork actions | EvidenceStages.tsx:42-58 | P | COVERED (built) | `ExecutionSteps.tsx:1183` | start → `LO4-5` |
| D-90 | Steps marked AI / code | :17-25 | — | COVERED (built) | StepActivityPanel | |
| D-91 | Cost: spent, reserved, cap | :63-71 | P | PARTLY | `lib/budget-line.ts:21` | `LO0-1` |
| D-92 | Quality and intervention | :72-79 | P / Q | COVERED | `RQC0-5`, `RQC7` | |
| D-93 | "Kdo odpovídal" | :80-87 | B | COVERED (built) | `ExecutionSteps.tsx:182` | |
| D-94 | Results: means, intervals, suppression | :124-143 | B | COVERED (built in browser) | `lib/result-reading.ts:87` | `evidence-integrity#6` moves it server-side |
| D-95 | Open answers; coding | :153-158 | P / Q | COVERED (blocked) | `AOC4-8` | MVPQ-02b |
| D-96 | Segment comparison unavailable | :165 | — | COVERED | `seg#10` | |
| D-97 | Origin and quality; reopened | :123,167 | — | PARTLY | `WCE7` | |
| D-98 | Map toolbar and filter bar | :205-216 | B | PARTLY | `ObjectMapView.tsx:171` | `#14`, `#20` |
| D-99 | Clickable pairs, context marker | :217-246 | B / P | PARTLY | `ObjectMapView.tsx:282` | `DR#31` |
| D-100 | Four-way legend | :249-254 | — | COVERED | `#15`, `#20-21` | |
| D-101 | Objects by height, unplaced, fit | :255-268 | B | COVERED (built for `-3`) | `ObjectMapView.tsx:287-293` | not for `-5` (§5) |
| D-102 | Milestones strip | InterpretStages.tsx:15-29 | — | **MISSING** | — | data exists |
| D-103 | Coverage per research question | :47-68 | P | COVERED | `evidence-integrity#1,7`; `#21` | |
| D-104 | Blocked claims | :69-73 | P | COVERED | `evidence-integrity#9a-b` | |
| D-105 | Coding view | :74-90 | P / Q | COVERED (blocked) | `AOC4-8` | |
| D-106 | Modules, new round | :91-98 | B | COVERED (built) | `ExecutionSteps.tsx:1033` | |
| D-107 | Report bar | :111-118 | P | PARTLY | `CompleteReport.tsx:282` | `RD3`, `RD5` |
| D-108 | Document body with claim chips | :119-144 | P | COVERED | `RD4`, `RD5`, `RD5a`, `RD7` | |
| D-109 | Coverage record outside the text | :145-149 | — | PARTLY | `RD9-10` | |
| D-110 | Semantic edit buttons | :150-156 | — | COVERED (needs ADR) | `RD6` | G41 |
| D-111 | Client report refused for fictional run | :157 | B | COVERED (built) | `CompleteReport.tsx` | |
| D-112 | Scenarios A-M, X1-X7 | scenarios.ts:572-592 | — | COVERED | `mvp-acceptance-harness#13` | L is a standing continue (D16) |

### 2e. Flags against the design artifact's marks

- The working-copy bar's "Přijmout jako revizi" is marked P `#15`; accept is `working-copy-edit-ops#WCE7`, discard `#WCE9`.
- An OTEVŘENO item names "chunk 0: APPROVE_GATE nebo PROPOSE_CLIENT_KNOWLEDGE" (`client-data-in-analysis#0`, G36); it is not in `mvp-owner-decisions.md`.
- "Postaveno (#40-#44)": `deep-research-web-search` has no chunk 43.
- The meter name "Studie" is left open "(F16)"; F16 in the owner packet is a Sociomap audit item, so it is untracked.
- The Analysis section omits `segment-maps-and-drilldown#10` (X1 settled segment evidence).
- Bare `#3`, `#5`, `#7` are ambiguous between `client-data-in-analysis` and `segment-maps-and-drilldown`.
- No PLÁN mark points to a ticked chunk; every OTEVŘENO item (MVPQ-02b, 03, 05, 10, 12) is still open.

## 3. What 18.6.6 does

Ledger counts from their own fields: interface screens 19 of 28 not done (16 NOT_IN_AIA, 3
REBUILDING); routes 157 of 157 not PORTED (138 LEGACY, 19 PORTING); UI functions 89 of 89 (86 LEGACY,
3 PORTING); parity capabilities 63 of 78 (41 NOT_STARTED, 22 PARTIAL). **These counts overstate the
gap**: rows marked "stale" below are built in AIA. Grouped into 30 rows:

| # | 18.6.6 item(s) | Ledger | MVP needs? | Status | Where / decision | Note |
|---|---|---|---|---|---|---|
| L-01 | `route-run`, `/api/project/check`, `/final-review`, `/preflight`; `cost.*`, `workflow.config` | REBUILDING / LEGACY | yes (AC-02, 04) | COVERED | built Run stage, `domain/run_cost.py`; `research-lead-workbench#19`; `lead-orchestration#LO0-2,4,15` | AI final check not carried |
| L-02 | `route-research_progress`, jobs/workflows, cancel, retry | REBUILDING / LEGACY | yes (AC-06) | COVERED (ledger stale) | built; `run-qc-and-checkpoint#RQC0`, `#RQC7` | |
| L-03 | `route-results`, history, results registry, `analysis.modules` | REBUILDING / LEGACY | yes (AC-08, 13) | COVERED | `evidence-integrity#1,6,9a-b`; `research-lead-workbench#20-21` | screen note on D6 stale |
| L-04 | `route-verify`, results verify, calibration addenda | NOT_IN_AIA | no | OUT, **contradicted** | `research-flow-rehome.md:15` | `parity-matrix.json:4049` still maps it to AC-08 |
| L-05 | `route-next`, discovery | NOT_IN_AIA | no | OUT | `research-flow-rehome.md:14` | |
| L-06 | `route-command`, command center | NOT_IN_AIA | no | OUT | `interface-screens.json:176` | |
| L-07 | `route-data`, library upload, ingest, proposal decide | NOT_IN_AIA | yes (AC-10) | COVERED (re-homed) | `client-knowledge-lifecycle#K2`, `#K2e-f`, `#K3` | per client |
| L-08 | Library "society insights" (ask, brief, segment ask) | LEGACY | no | OUT (notice only, **no recorded decision**) | `interface-screens.json:189` | owner question |
| L-09 | Dimension materialize/spec, persona suggest | LEGACY | yes (AC-10) | PARTLY | `client-knowledge-lifecycle#K5`; `research-lead-workbench#22`; `working-copy-edit-ops#WCE10` | G28, G23 |
| L-10 | Population calibration overlay | LEGACY | no | OUT | `mvp-acceptance.md:123` | |
| L-11 | Populations, panel values, weighting | LEGACY / PARTIAL | yes (AC-05) | COVERED (ledger stale) | `complete-study-report#B6`; `audience-catalogue-cpu#4`; `run-qc-and-checkpoint#RQC10` | |
| L-12 | `population.readiness` | NOT_STARTED | yes (AC-05) | PARTLY | `support_forecast.py` built; `RQC6`, `RQC8` | no chunk names the port |
| L-13 | Audience routes, subpanels, factor editor | LEGACY | yes | COVERED (built) | `research-lead-workbench#22`; `WCE10`, `WCE3c` | |
| L-14 | Own audiences, special panels | LEGACY | no | OUT | `panel-grounded-respondents.md:1181` | |
| L-15 | `audience.segments`, segment viz functions | LEGACY | yes (AC-09) | COVERED | `segment-maps-and-drilldown#0a-10` | see §5 |
| L-16 | `route-visualization`, object map, study module | NOT_IN_AIA | yes (AC-09) | PARTLY | object map built; `research-lead-workbench#20`; `lead-orchestration#LO9b-c` | node drag unowned (= P-53) |
| L-17 | Map compare, dialogue, scenarios | LEGACY | no | OUT | MVPQ-03; `mvp-acceptance.md:118` | compare = P-54 question |
| L-18 | 18.6.6 map renderer functions (47) | LEGACY | no | OUT (superseded) | `object-map-3d-redesign`; MVP-21 | the methodology owner's standing rule wants the panel's *look* (§5) |
| L-19 | Map manager snapshot/restore | LEGACY | yes (AC-13) | COVERED | `report-delivery#RD4`; `segment-maps-and-drilldown#9` | |
| L-20 | `impactRows66`, `artifacts.registration` | LEGACY | yes (AC-07) | COVERED | `working-copy-edit-ops#WCE7` | |
| L-21 | Questionnaire and research design routes | LEGACY | yes (AC-03) | COVERED (largely built) | `research-lead-workbench#11,17,18`; `AOC0-3` | instrument library: owner question |
| L-22 | `questionnaire.conditionals` | NOT_STARTED | yes (X8) | COVERED | `WCE13`, `RQC11`, `evidence-integrity#10` | |
| L-23 | `respondents.context` (stimuli, task conditions) | NOT_STARTED | unclear | PARTLY | producer only (`deep_research/quarantine.py`) | owner question |
| L-24 | `/api/run`, respondent layers, factual layer | LEGACY / PARTIAL | yes | COVERED (built) | `complete-study-report#B6` | |
| L-25 | `config.edition`, `config.environment` | NOT_STARTED | yes (AC-14) | **MISSING** | AC-14 → `MP6`, `harness#5` only | no run records its config; no edition file (= P-81) |
| L-26 | `governance.anchors` | NOT_STARTED | unclear | PARTLY / unplanned | `parity-matrix.json:4049` | owner question |
| L-27 | `analysis.qc`, diagnostics, evidence gates, policy | NOT_STARTED | yes (AC-08) | COVERED | `evidence-integrity#2,3,5,6`; `RQC1-2` | |
| L-28 | Evidence audit, legal, report generation, export | NOT_STARTED | yes (AC-13) | COVERED (report built) | `report-delivery#RD0-3,7` | legal OUT (MVPQ-09) |
| L-29 | Calibration, benchmarks, holdout, ablation | LEGACY | no | OUT, **contradicted** | `panel-grounded-respondents.md:1952`; master §3.2 | `parity-matrix.json:4015` maps calibration to AC-05 |
| L-30 | The rest: simulation (5 screens, 20 routes), demos, assistant/copilot, providers, support, dashboard, schedules/pause, approvals | mixed | mostly no | mostly OUT; gateway, ledger, approvals built (stale) | MVP-1; `legacy-phase-out.md:61,146`; ADR 0026 | schedules/pause: no decision; **ledgers have no refresh owner: MISSING** |

## 4. Cross-cutting needs

| # | Need | Sub-capability | Status | Where | Note |
|---|---|---|---|---|---|
| X-01 | Onboarding | First sign-in, not-a-member refusal | COVERED (built, develop) | `routers/session.py:86-121`; prod `PE1` | |
| X-02 | Onboarding | **First organization and owner in production** | **MISSING** | only `develop_seed.py:229` creates one | searched "bootstrap", "first user", "onboard" |
| X-03 | Onboarding | First client, empty state | COVERED (built) | `ClientDirectory.tsx:65-83` | |
| X-04 | Onboarding | First study | COVERED (built) | `routers/scope.py:410` | |
| X-05 | Onboarding | Inviting members | PARTLY | `scope.py:583-611` adds a row | no notice to the invitee |
| X-06 | Onboarding | Lead hatching | COVERED (built) | `research-lead-workbench#6b` | |
| X-07 | Onboarding | First-run help for research | PARTLY | Settings guide only | |
| X-08 | Permissions | Members, role change | COVERED (built) | `scope.py:577-611` | |
| X-09 | Permissions | **Remove / deactivate a member** | PARTLY | `scope_repository.py:252` exists, no route or UI | |
| X-10 | Permissions | OWNER/ADMIN vs Researcher | COVERED (built) | `two-roles-human-ai-gates` | |
| X-11 | Permissions | What a non-permitted person sees | COVERED (polish) | `ControlPanel.tsx:386` | prints `VIEW_COSTS` code (`cs.ts:1498`) |
| X-12 | Permissions | Self-approval | COVERED (built) | `scope.py:526-575` | |
| X-13 | Permissions | Report / map approval gates | COVERED | `two-roles#5b.4`; `RD2-4` | |
| X-14 | Error/empty | Shared states | COVERED (built) | `components/aia/states.tsx:16-46` | |
| X-15 | Error/empty | Empty state for every area and stage | PARTLY | 14 components | no inventory |
| X-16 | Error/empty | **API errors in Czech** | PARTLY | `lib/api.ts:41-52` passes English server text | |
| X-17 | Error/empty | Parked/blocked run explained | COVERED | `run-state.ts`; `LO12a-b`; `MP6` | |
| X-18 | Error/empty | Session expiry | COVERED (built) | `auth.ts:212-222` | unsaved edit on 401 unverified |
| X-19 | Error/empty | Offline | **MISSING** | — | |
| X-20 | Czech | `t()` / `cs.ts` | COVERED (built) | `i18n/cs.ts` | some hard-coded strings |
| X-21 | Czech | No-English-leak test | PARTLY | — | |
| X-22 | Czech | Native copy review | **MISSING** | — | |
| X-23 | A11y | Contrast | COVERED (built, CI) | `scripts/check-design.mjs:48` | |
| X-24 | A11y | Keyboard, focus | COVERED | journeys; `#12`, `#26`; `harness#10` | |
| X-25 | A11y | Screen reader pass | PARTLY | aria present | no pass planned |
| X-26 | A11y | Reduced motion | COVERED (built) | 8 sites | |
| X-27 | A11y | **Automated audit (axe)** | **MISSING** | — | |
| X-28 | Lifecycle | Delete study / client | COVERED | `study-data-lifecycle#SDL0-3` | |
| X-29 | Lifecycle | **Delete one source** | PARTLY | `SDL4` covers attachment bytes only | |
| X-30 | Lifecycle | Retention horizons | COVERED (decided) | MVPQ-07; `SDL0` | |
| X-31 | Lifecycle | Restore keeps deletions | COVERED | `SDL5-6`; `PE9a` | |
| X-32 | Lifecycle | **Subject requests (one person)** | **MISSING** | — | |
| X-33 | Lifecycle | **Export a client's data** | **MISSING** | — | |
| X-34 | Lifecycle | Lead files on departure | COVERED | `lead-orchestration#LO11` | |
| X-35 | Backups | DB dumps, develop | COVERED (built) | `deploy/develop/bin/backup.sh` | |
| X-36 | Backups | RDS PITR, snapshot before migration | COVERED | `PE1`, `PE2` | |
| X-37 | Backups | **S3 restore matching the DB** | PARTLY | versioning only; `restore.sh` is PostgreSQL | |
| X-38 | Backups | Restore exercised | PARTLY | `restore.sh --test`; `PE9a` | |
| X-39 | Backups | **RPO/RTO stated** | **MISSING** | — | |
| X-40 | Cost | Study budget in UI | COVERED (built) | `lib/budget-line.ts` | |
| X-41 | Cost | Client budget | COVERED | `client-budget#CB1-5` | |
| X-42 | Cost | Header meters | COVERED | `LO1` | |
| X-43 | Cost | Organization / monthly spend | **MISSING** | — | |
| X-44 | Cost | AWS cost alarms | PARTLY | develop Budget (`infra/develop/main.tf:597`); `PE9b` | no Bedrock alarm |
| X-45 | Cost | Ledger vs AWS | COVERED | `develop-spend-attribution#3,5b` | |
| X-46 | Observability | Error tracking | COVERED (develop) / PARTLY (prod) | `error-tracking` | no prod chunk |
| X-47 | Observability | Logs | COVERED (develop) | CloudWatch | prod implied by `PE1` |
| X-48 | Observability | Metrics / tracing | **MISSING** | `docs/architecture/security.md:222-230` | |
| X-49 | Observability | **Uptime probe** | **MISSING** | — | |
| X-50 | Observability | On-call | PARTLY | SNS to one e-mail | |
| X-51 | Observability | Worker health, queue age | PARTLY | `mvp-target-architecture.md:316` ◇ | no chunk |
| X-52 | Cutover | Environment | COVERED | `PE0`, `PE1` | |
| X-53 | Cutover | Hostname | PARTLY | owner/operator | |
| X-54 | Cutover | Callbacks | COVERED | `PE1` | |
| X-55 | Cutover | **Production starts empty or migrates?** | **MISSING (undecided)** | `aia_executors.legacy_workspace` exists | |
| X-56 | Cutover | Rollback | COVERED | `PE2`, `PE9b` | |
| X-57 | Cutover | Release process | COVERED | `PE2`, `PE8` | |
| X-58 | Cutover | **Security review / pen test** | **MISSING** | — | |
| X-59 | Cutover | Secrets | COVERED | `PE1` | |
| X-60 | Cutover | Activation profile READY in prod | COVERED | `MP6`, `PE5`, `PE9b` | |
| X-61 | Other | Idle session timeout | PARTLY | refresh 30 days (`identity.tf:93-95`) | |
| X-62 | Other | **CSP header** | PARTLY | other headers in Caddyfile | |
| X-63 | Other | Audit log visible | COVERED (built) | `scope.py:614-632` | |
| X-64 | Other | **Rate limiting** | **MISSING** | `security.md:109,208` known gap | |
| X-65 | Other | Browser matrix | **MISSING** | — | |
| X-66 | Other | Performance budgets | **MISSING** | — | |
| X-67 | Other | User documentation / training | **MISSING** | — | |
| X-68 | Other | Support channel | **MISSING** | — | |
| X-69 | Other | **Terms / privacy notice / client DPA** | **MISSING** | — | |
| X-70 | Other | **Population licence for paid deliverables** | PARTLY | `licence_determinations.py` covers the model route only | |

## 5. `aia-sociomap-5` as the MVP's map engine (decided 2026-10-20)

`signed-off-sociomap-method` chunks 0-7 are built (`engine_v2._credibility`, `_respondents`,
`signed_off_segments.py`). What a user sees of it:

| # | Capability | Status | Where | Note |
|---|---|---|---|---|
| S5-01 | Engine computes `-5` (inputs, positions, terrain, credibility, respondents, segments) | COVERED (built) | `signed-off-sociomap-method#0-7` | |
| S5-02 | **A new run pins `-5`** | **MISSING** | `default_methods()` pins `-1`, `-3` (`domain/research_sociomap.py:323-329`) | "Making `-5` the default" is out of that plan; no other chunk |
| S5-03 | **Register entry for `-5` (client-facing approval)** | **MISSING** | register approves `-3` only (`domain/sociomap_register.py:54`) | `segment-maps-and-drilldown#4` registers new methods INTERNAL_ONLY; nothing approves `-5` |
| S5-04 | Web draws a `-5` object map as `-5` | PARTLY | read as an unnamed method (`apps/web/src/lib/object-map-view.ts:20`); relative heights drawn on absolute terraces | the methodology owner's drawing rules (26× relief, node size, panel look) are "Web follow-up" prose, not chunks |
| S5-05 | Map credibility on the web (banner, split-half in HUD, uncertainty circles) | **MISSING** | typed, "Not drawn yet" (`object-map-view.ts:60-62`) | |
| S5-06 | Map credibility in the report | COVERED (built) | `application/report_maps.py:77-93,184` | |
| S5-07 | Objects not placed, listed ("Neumístěno …") | **MISSING** | neither web nor report reads `objects_not_placed` | silently dropped today |
| S5-08 | Respondent map on the web (placed / faded, density, indicative note) | **MISSING** | — | `sociomap-formula-corrections#3` plans a different respondent map |
| S5-09 | Respondent map in the report | PARTLY | `segment-maps-and-drilldown#9` | says "reconcile with `-5` first" |
| S5-10 | Taste segments on the web | **MISSING** | — | `segment-maps-and-drilldown#2-3` plan segments through a different path |
| S5-11 | Taste segments in the report and as evidence | PARTLY | `segment-maps-and-drilldown#9`, `#10` | `#10`'s admitted claims must read `-5`'s profiles, not a new clustering |
| S5-12 | The Lead reads `-5` results (credibility, segments, unplaced) | PARTLY | `lead-orchestration#LO8` (maps generically), `#LO9b-c` (map interpreter) | no chunk names the `-5` fields |
| S5-13 | Metodika comparison shows credibility and respondent map | PARTLY | `MapSummary` lacks them | `methodology-tab` is POST |
| S5-14 | Open method points: context objects, weighted relations, platform-dependent BB1 | OPEN (methodology owner) | `signed-off-sociomap-method.md` § Not in this plan | |

**Consequence for existing plans.** `sociomap-formula-corrections#3` (respondent map) and
`segment-maps-and-drilldown#1-3` (segments via the existing engine / clustering) were written before
`-5`. With `-5` shipping, they are either superseded or must be re-scoped onto `-5`'s stored fields.

## 6. Missing or partly covered, ranked

Ranked by how badly the MVP or its first release needs it. "Owner" is a proposal; new chunks are named
`<plan>#<new id>` and are not yet written.

| Rank | Gap | Rows | Proposed owner |
|---|---|---|---|
| 1 | `-5` pinned on run start, registered, and the old respondent/segment chunks re-scoped onto it | S5-02, S5-03, P-51 | new `segment-maps-and-drilldown#0b` (pin + register entry + re-scope `SFC#3`, `seg#1-3`); register approval by the methodology owner |
| 2 | Web draws `-5`: method named, relative terrain, credibility, unplaced objects, respondent map, taste segments, the panel's drawing rules | S5-04, -05, -07, -08, -10 | new `research-lead-workbench#28` (map) or `segment-maps-and-drilldown#8b`, before `#20` |
| 3 | First organization and owner in production | X-02 | new `production-environment#PE10` |
| 4 | Security review and rate limiting | X-58, X-64, X-62 | new `production-environment#PE11`; `architecture-enforcement#12`; CSP into `PE1` |
| 5 | Stop a Lead turn; withdraw an approved plan | D-44, D-31, D-48 | new `lead-orchestration#LO17` (backend) + workbench build line |
| 6 | Mount the item inspector | D-63, D-64, D-68 | `research-lead-workbench#15` (explicit line) |
| 7 | AC-14 "recorded on the run"; edition file | P-81, L-25 | new `mvp-master-plan#MP6b`, or amend AC-14 via `mvp-acceptance-harness#14` |
| 8 | Report and Lead read `-5`: unplaced objects in the report, respondent/segment figures, Lead fields | S5-07, -09, -11, -12 | `segment-maps-and-drilldown#9`, `#10`; `lead-orchestration#LO8` (name the fields) |
| 9 | RPO/RTO, S3 + DB restore, restore exercised | X-37, -38, -39 | widen `production-environment#PE9a`, `study-data-lifecycle#SDL5` |
| 10 | Uptime, on-call, queue-age alarm, production error tracker | X-46, -49, -50, -51 | `production-environment#PE9b` named list |
| 11 | Conversation controls: paging, copy, edit/resend, ArrowUp, queue edit | D-21, -24, -30, -42, -43 | new `research-lead-workbench#29` (and an API paging route) |
| 12 | Member deactivation | X-09 | new `two-roles-human-ai-gates#8` |
| 13 | Node drag as a view override | P-53, L-16 | `research-lead-workbench#20` + `harness#10` line |
| 14 | Deep Research context in the client report | P-64 | new `report-delivery#RD11` |
| 15 | Hide Simulace | P-07 | new `client-workspace#C10` |
| 16 | Stage states; provider wait reads inert (defect) | D-09 | `research-lead-workbench#15`; `WCE7` |
| 17 | Czech API errors, leak test, copy review | X-16, -21, -22 | widen `lead-orchestration#LO12a` |
| 18 | Terms, privacy notice, client DPA; population licence for paid deliverables | X-69, X-70 | master §11.5 operator/owner rows |
| 19 | Subject requests, client export, single-source delete | X-29, -32, -33 | new `study-data-lifecycle#SDL7-8`, `#SDL4b` |
| 20 | Infrastructure-charges line for AC-15 | P-79 | widen `develop-spend-attribution#5b` |
| 21 | Ledgers refreshed; L-04/L-29 contradictions removed | L-30, L-04, L-29 | widen `mvp-acceptance-harness#14` |
| 22 | Lead learning rules | P-38 | widen `lead-orchestration#LO11` |
| 23 | Question chain (decisions, expected answer, done-when) | D-72, D-73 | widen `working-copy-edit-ops#WCE1`, then `research-lead-workbench#18` |
| 24 | Product README and overview drift; dead links | P-22, -03, -06, -85, -62, -87 | docs-only PR |
| 25 | Smaller UI: fictional-data chip, pending list, lifecycle popover, milestones, card types, source chips, scroll, rail, meters' names, studies columns | D-02-04, -10, -11, -15, -20, -22, -27, -32, -33, -60, -102, P-68 | `research-lead-workbench#15`, `#21`, `#23`; `client-workspace` |
| 26 | a11y audit, offline, browser matrix, performance budgets, docs, support | X-15, -19, -25, -27, -65-68 | a new `launch-readiness` plan, or `mvp-acceptance-harness#10` (axe) |
| 27 | Decided-by-question items | P-09, -11, -54, -57, -58; D-23, -47, -51, -70, -76, -79; L-08, -21, -23, -26; X-43, X-55 | owner questions (PR body) |
