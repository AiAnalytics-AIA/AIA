# MVP consolidation — the open plans against the scoped MVP (2026-10-19)

**What this is.** A dated, cross-feature analysis requested by the product owner on 2026-10-19:
every plan that is not `done`, set against the MVP scope, with the overlaps, the stale entries,
the conflicts between scope sources and the dependency order. It is **not a backlog**. A
feature's status stays in its own plan's front-matter (CLAUDE.md §4); where this file disagrees
with a plan, the plan wins and this file is stale. It is written against `develop` @ `0b4e05e`;
every claim about code carries `file:line @ 0b4e05e` or a test name, and an unanchored entry is a
**hypothesis**.

**Sources of scope it reconciles.**

| Source | Date | Says the MVP is |
|---|---|---|
| `docs/migration/mvp-acceptance.md` (`MVP-ACCEPT-1`) | 2026-09 | One research study, created and delivered over HTTP, every touched capability at parity. Simulation out (D9); "project memory, copilot, results dialogue" out (§6) |
| `.planning/plans/mvp-workflow-assurance.md` | 2026-10-07 | Four areas: Simulation studio, Sociomapping, Data library / social intelligence, Project memory; research is the first path, not a smaller MVP |
| ADR 0026 + `research-lead-workbench.md` | 2026-10-19 | The study screen is the Research Lead's conversation beside the stage's artifact |
| The product owner's deck *NPC Panel — jak funguje celý analytický systém* (15. 10. 2026), slide 46 "MVP priority" | 2026-10-15 | P0: core workflow brief → plan → data → analysis → map → scenario → report; data & evidence; map engine; scenario engine; report + Client View. P1+: breadth of catalogues |
| The product owner, in session | **2026-10-19** | **Simulation is excluded from the MVP** |

The deck is not committed: its case study is a real client's. It is cited here by slide number.

---

## 1. The MVP this analysis assumes

Until the decisions in §2 say otherwise:

1. **Research lifecycle, end to end,** brief → design → questionnaire → audience → dimensions →
   sample → fieldwork → results → Sociomap → analysis → report, run from the **Research Lead
   workbench** (ADR 0026), on AI respondents from the population, with every gate a person's.
2. **Sociomapping** as the main analytical interface (deck slides 5, 25, 48): the object map
   (`aia-sociomap-3`, approved, D6) and the respondent map, with what each mark means.
3. **Data and evidence**: a client's sources taken in, read, proposed as knowledge, accepted by a
   person, and usable by a study, with origin and allowed use kept (deck slides 18-23, P0 "Data &
   evidence").
4. **Project memory**: the same client's past designs found and reused, cited (PM-1, done).
5. **Delivery**: the internal and client reports, approved by a person, and exported.

**Out:** Simulation (owner, 2026-10-19), real-respondent data collection (product scope "Out of
scope"), the catalogue breadth the deck marks P1+ (~80 analysis templates, 80 map templates, 320
perspectives, 120 dimensions, slide 16).

## 2. Decisions the owner needs to make

**Answered by the owner on 2026-10-19:** M1 all scenarios out · M2 approved exports · M3 the
redesign before release (autopilot and Deep Research from every stage after) · M4 the respondent
map in · M5 rewrite `mvp-acceptance.md` · M6 depth tiers after · M7 an owned child is enough · M8
superseded: every AI action goes through the Research Lead. Recorded as MVP-1 to MVP-10 in
`overview.md` § MVP roadmap, which is now the cross-plan list; §4.1's front-matter corrections are
applied in the same PR.

Each one changes which plans are MVP-critical. They are listed before the plans because the plan
map in §4 depends on them.

| # | Question | Why it is open | What it decides |
|---|---|---|---|
| **M1** | **Does "Simulation out" also take out the deck's P0 Scenario engine?** | The deck lists *Scenario engine — baseline, zásah, delta, assumptions, uncertainty* as P0 (slide 46). Its example is a what-if layer over a research result: the respondent map's positions kept, a modelled response recoloured on it (slide 66), variants against one baseline (slides 67-69). In AIA that is the simulation core (`domain/simulation/`, `done/simulation-deterministic-core.md`), which only `simulation-studio.md` brings to a person (0/8, S0 waits on D9) | Whether any of `simulation-studio.md` is MVP. A narrow option: "what-if over a frozen research run" as one artifact, without the 13-stage simulation lifecycle |
| **M2** | **What is "Client View" in the MVP?** | Deck P0 *Report + Client View* (slides 39, 41, 46): only approved maps and results, by permission. The product scope says "Clients are **not** users of this system … There is no client-facing login" (`docs/product/README.md`, *Users*) | Either Client View = the approved client deliverables (client report DOCX/PDF, approved map snapshots), which AIA mostly has; or a client-facing surface, which is a product-scope change and an ADR |
| **M3** | **Is the Research Lead workbench the MVP's study screen?** | `MVP-ACCEPT-1` §6 leaves "copilot, results dialogue" out as needing a product-scope change; ADR 0026 (accepted 2026-10-19) makes the Lead central. The deck says "Není to chatbot … pracuje v definovaném workflow a podle kontraktů" (slide 10), which ADR 0026's "the Lead proposes; a person decides" satisfies | Whether `research-lead-workbench.md` chunks 12-25 are release-blocking, and whether `mvp-acceptance.md` gains a Lead criterion |
| **M4** | **Is the respondent map in the MVP?** | The deck's respondent map (R01) carries the case study (slides 26, 29, 62, 66). AIA computes object maps only: "respondent placement is chunk 3 (ideal points against this object map, audit F10)" (`domain/sociomap/engine_v2.py:93 @ 0b4e05e`), owned by `sociomap-formula-corrections.md` chunk 3, which waits on the method owner (0b) | Whether the method owner's 0b decisions are on the MVP's critical path |
| **M5** | **One acceptance contract.** | Three documents define done differently (table above). `MVP-ACCEPT-1` is research-only and parity-based; the four-area contract now loses Simulation (2026-10-19) | Rewrite `mvp-acceptance.md` (a docs PR) as the one contract, with `mvp-workflow-assurance.md` A4/A5 as its runs |
| M6 | Report depth tiers (Light / Normal / Deep / Super Deep, slide 39) in the MVP? | AIA has four recipes by audience: `client_report`, `final_report`, `internal_report`, `study_documentation` (`domain/report/templates.py:172-213 @ 0b4e05e`), not by depth | A report recipe parameter, or P1 |
| M7 | Promotion of a client's materialized dimension into a new LIVE population revision | The four-area contract asks for "explicitly create a new LIVE population revision"; `materialize_child` "Never promotes" (`application/population.py:817 @ 0b4e05e`) by design (owned children are never shared versions) | Whether the data-library acceptance ends at an owned child (today) or at promotion |
| M8 | Lead-prepared work and the spend limit for a person's own design-job button | `research-lead-workbench.md` F1: `ResearchAgentJobs.start` reads no spend limit; the Lead's approve path does (`application/research_lead.py:721-735 @ 0b4e05e`) | Whether F1 is a fix or intended |

## 3. How the deck's P0 maps onto AIA today

| Deck P0 (slide 46) | AIA has | Gap | Owning plan(s) |
|---|---|---|---|
| **Core workflow** brief → plan → data → analysis → map → (scenario) → report | The research run end to end: design revision → compile → fieldwork → aggregate → Sociomap → eight analysis modules → internal report; `test_analysis_executor.py::test_native_ai_study_connects_a_populated_map_to_admitted_report_inputs` | The diagnostic brief (slides 14-15, 35-37: decision, KPIs, unknowns, what the client must still supply) is a free-text brief today; deployed acceptance is unrecorded | `research-lead-workbench` 18 (Brief, Design artifacts); release acceptance (§5, track A) |
| **Data & evidence** import, metadata, origin status, evidence register, versions | Client sources kept and read with locators (lifecycle K2), AI proposals from a document (K2d), knowledge revisions with provenance; `origin_kind` on every result; `AdmittedClaim` the only way a number enters | Web intake (K2e), review payload with evidence (K2f), typed revisions against the reviewed base (K3), a study's knowledge snapshot (K4) | `client-knowledge-lifecycle` K2-K7; `client-workspace` C6-C9; `client-budget` CB5 |
| **Map engine** several maps per project, meaning contract, filters, export | Contract-3 object map per tracked set, pair statuses, "how to read this map", top / 3D, PNG snapshot; the Sociomap register | Respondent map (M4); region tests (F14/F15); maps from audience/dimension changes proven end to end (I0-I5); hybrid and segment maps (slide 26) | `sociomap-formula-corrections` 3, 4d, I0-I5; `sociomapping-engine` (SOMECS, post-MVP) |
| **Scenario engine** | Simulation core (domain only) | Everything above the domain (M1) | `simulation-studio` (excluded unless M1 says otherwise) |
| **Report + Client View** modular report, approval, export, permissions | Internal report, report with literature, client report for a modelled run, DOCX + PDF, approval once (`application/report_approval.py`, `client_report.py`) | Client View (M2); depth tiers (M6); lineage and reading notes | `research-integrity-report` 6-8; `two-roles-human-ai-gates` 5b |
| Six human gates (slide 43) | ADR 0019 gates: the approval ledger, accept of proposals, spend confirmation, report approval | Gates 4 (interpretation) and 5 (scenarios) as recorded decisions | `two-roles-human-ai-gates` 5b.1-5b.4 |
| AI Autopilot vs Analyst + AI (slide 42) | Analyst + AI: every proposal a person's accept | Autopilot = the Lead's "continue until you need me" | `research-lead-workbench` 24 (needs an ADR, §6) |
| Evidence grades A-D (slide 23) | Evidence roles and print grades (`domain/report/evidence.py`); modelled labelled every time | C "scenario output" and D "hypothesis" have no grade while scenarios are out | none needed unless M1 brings scenarios in |
| Three knowledge levels NPC / Firma / Projekt (slide 19) | AIA shared intelligence / Client Knowledge / study context (`docs/product/README.md`) | The deck's middle level is the firm's own know-how; AIA's is the client's. The firm's know-how lives in Metodika (ADR 0023), prompts (ADR 0020) and each researcher's Lead notes | none: a vocabulary note for the owner |

## 4. Every open plan, classified

**Legend.** **MVP** on the critical path · **MVP-verify** built, needs the release run · **Post** not
MVP under §1 · **Close** done or superseded, front-matter stale (tick or set `done` in a docs PR) ·
**Tooling** keeps the repo healthy, not product scope.

### 4.1 Built or superseded: their front-matter should be corrected

| Plan | Open chunks per front-matter | What is actually true | Evidence |
|---|---|---|---|
| `research-lane-redesign` | B1-B6 | B1-B5 were built under `complete-study-report` (B1a-B5c ticked there); B6 is owned there too | `complete-study-report.md` front-matter; `application/report_approval.py`, `application/client_report.py`, `domain/sociomap_register.py` exist @ `0b4e05e` |
| `report-docx` | R4-R11 | The renderer, styles, tables, charts, figures, templates and the report step exist | `infrastructure/report_docx/{styles,blocks,tables,charts,figures,renderer}.py`, `domain/report/templates.py`, `aia_executors/report.py`, `tools/report_preview.py` @ `0b4e05e` |
| `internal-report-composition` | "Wire the report into the research results stage and verify a full live run" | Wired: `CompleteReport.tsx` is the report card on Výsledky; the live run is the release run (§5 A) | `apps/web/src/components/rehome/research/CompleteReport.tsx` @ `0b4e05e` |
| `ai-workflow-completion` | 2-6 | 2 (material review) is `usable-classification` (#487, done); 3-5 are `complete-study-report` and `evidence-backed-analysis`; 6 is the release run | its own Findings 3 ("the client report has no AIA counterpart") is no longer true: `application/client_report.py` @ `0b4e05e` |
| `run-recovery-and-truth` | 5c | The code landed: the selected dimensions are the persona topic allowlist | commit `bc61041` (2026-10-15, on `develop`); `domain/panel_persona.py:72, 136-138 @ 0b4e05e`; its plan line 668 still says open |
| `evidence-backed-analysis` | none (9/9), status in-progress | All chunks done | front-matter |
| `legacy-phase-out` | none (12/12), status in-progress | Code done; the host's content migration is unrecorded (overview, *Where the code is*) | an operator answer, not code |
| `interface-skin`, `design-system`, `legacy-strangler`, `interface-rehome`, `research-flow-rehome`, `ui-workbench` | various | Superseded by ADR 0018 (no 18.6.6 in the product) and the client-first and workbench screens; their own headers say "superseded" (`interface-skin.md`, `design-system.md`) | their headers; `research-flow-rehome` 10 (ideal group, propensity, child project) should be re-filed under the workbench artifacts or dropped, not carried |
| `deep-research` | 4, 12, 13 | 12 (API and screen) exists: `routers/deep_research.py`, `InterpretationResearch.tsx`; 13 moved to `deep-research-web-search` 27; 4 is half true: priced tool calls are held and settled against the budget (`infrastructure/workflow_repository.py:1184-1206 @ 0b4e05e`), but they are not rows of `ai_usage_events` (hypothesis: no tool column found) | as cited |

### 4.2 MVP-critical, still to build

| Track | Plan → open chunks | Depends on |
|---|---|---|
| **B. Workbench and Lead** | `research-lead-workbench` 12, 11, 14-25 (V3 artifacts) | M3; §6 below for the backend each artifact needs |
| **C. Population → respondents → maps** | `audience-catalogue-cpu` 4 → `complete-study-report` B6 (operator: `AIA_AI_POPULATION_PERSONAS_ENABLED` on develop) → `sociomap-formula-corrections` I0-I5, 3 (respondent map, M4), 4d (regions) | the method owner's 0b answers for 3 and 4c |
| **D. Data and evidence** | `client-budget` CB5 → `client-knowledge-lifecycle` K2e, K2f, K3, K4, K5, K6, K7 → `client-workspace` C6 (needs K3), C7-C8 (need K2), C9 (needs K6) | M7 for how far K5 goes |
| **E. Delivery and gates** | `research-integrity-report` 6-8; `two-roles-human-ai-gates` 5b.1-5b.3 (5b.4 waits on M2) | M2, M6 |
| **F. Deep Research live** | `deep-research-web-search` 1 (sign-off: Brave's written terms, D8), then 27 (develop activation); 6, 8, 25-26 quality | DR-2 (live search waits on Brave's answer, overview *Decisions needed*) |

### 4.3 MVP-verify: one release acceptance instead of seven

Seven plans each end in a "deploy and verify live" chunk over the same path. They should be run
**once**, as the release acceptance of §5 A, and each ticked from that one record:
`ai-research-activation` 4, `ai-workflow-completion` 6, `connected-research-assurance` 5,
`contextual-research-settings-ux` 5, `research-agent-workflows` 8, `research-integrity-report` 5,
`mvp-workflow-assurance` A4 / A5.

### 4.4 Post-MVP or blocked outside engineering

| Plan | Why |
|---|---|
| `simulation-studio` (S0-S7) | Excluded 2026-10-19, unless M1 brings a narrow what-if in |
| `sociomapping-engine` (SOMECS, 14 open) | Waits on the method owner's reference exports E1-E9 and decisions M6-M14; the MVP map is `aia-sociomap-3` |
| `methodology-tab` S4d, W1c, X1 | S4d waits on the audit author's inputs; X1 is simulation; W1c follows panel fieldwork |
| `panel-grounded-respondents` 7f-7h (holdout validation) | Needed for client-facing **analysis prose** (ANL-1); the client **report** already carries modelled numbers under the owner's lift. MVP only if the MVP promises interpreted prose to the client |
| `deep-research-web-search` 31-39 (lens, records, extractors, browser rendering) | Breadth beyond the MVP's design and interpretation research |
| `desktop-ux-overhaul-handoff` 2-5 | Its Research-flow part (3) is now the workbench's V3 artifacts; Settings (4) and journeys (5) can continue on their own |
| `productization-coherence` PC5, PC16 | Small coherence fixes; take them with the artifact they touch (PC5 → Fieldwork/Results, PC16 → Design) |

### 4.5 Tooling

`architecture-enforcement` 6, 7, 9, 10 · `system-prompts-settings` 7 · `ui-workbench` 3.

`ci-skip-docs-only` belongs in §4.1: its chunk 1 is built. The `changes` job sends a change to
`.planning/*`, `docs/architecture/adr/*`, `CLAUDE.md`, `AGENTS.md` or `ARCHITECTURE.md` to
*Documentation checks* only (`.github/workflows/ci.yml:64 @ 0b4e05e`); this file's own PR ran that
route. `prototypes/` is not on the list, so a change there (#491) runs every suite.

## 5. Order

```
A. Release acceptance (once)        <- tracks B-E feed it; F is optional for MVP-ACCEPT
   |
B. Workbench + Lead ----------------+--> needs C for Results/Sociomap/Analysis artifacts to show real maps
   12 journey -> 11 paid work -> 14-16 frame -> 17-22 artifacts -> 23-25 cards, autopilot, DR anywhere
C. Population -> respondents -> maps
   audience-catalogue-cpu 4 -> B6 operator flag -> I0-I5 -> (M4) respondent map 3 -> regions 4d
D. Data and evidence
   CB5 -> K2e/K2f -> K3 -> K4 -> (C6, C7, C8) -> K5 (M7) -> K6 -> C9 -> K7
E. Delivery and gates
   integrity 6-8 -> two-roles 5b.1-5b.3 -> (M2) Client View / 5b.4
```

B, C and D are independent of one another until the artifacts read their outputs: the Audience and
Dimensions artifacts (B 22) want C's I0-I1, and the Brief artifact's materials (B 18) want D's K4.
Everything in §4.1 is a docs-PR correction and can happen now.

## 6. The Research Lead workbench: backend dependencies

This is the architecture pass the plan's Design V3 section asked for (`research-lead-workbench.md`
chunks 14-25), across the layers.

### 6.1 The Lead → artifact path today

| Layer | What exists | Anchor @ `0b4e05e` |
|---|---|---|
| Domain contract | `LeadOutput.view`: `OpenStage` (eleven stages) or `FocusItem` (any `kind:id`), at most 3 a turn | `domain/research_lead.py:142-154, 192-202, 416` |
| What a person may point at | `FOCUS_ID`: `question|section|brief|plan` only | `domain/research_lead.py:176` |
| Prompt | The view rule in the task text; prompt version `"1"`, harness `aia-research-lead-1` | `domain/research_lead.py:110-111, 706-707` |
| What the Lead sees | study (budget, spend, limit), design (working content and analysis), runs (**id, status and design revision only**), view (stage, focus, message), conversation | `application/research_lead.py:858-891` |
| Paid work | `approve_request`: `EDIT_STUDY` + `RUN_WORKFLOW` + `APPROVE_GATE`, the study's spend limit, Design Revision submitted, job started and ledger row written in one transaction; other request kinds only open a stage | `application/research_lead.py:678-760` |
| Web | `LeadView`, `focusSelector`, `targetOfElement`; the workbench applies `onView` | `apps/web/src/lib/lead.ts:30, 301, 341`; `Workbench.tsx:185-207` |

### 6.2 What chunks 14-25 need from the backend

| Need | For | Today | Change | Size |
|---|---|---|---|---|
| A wider, closed view vocabulary (tab, revision, results view, map object or pair, report section, show changes) | 14 | two operations | New `ViewOp` members in `domain/research_lead.py`, refused when the target is not the artifact's; the prompt's view rule and `LEAD_PROMPT_VERSION` move; `lib/lead.ts` mirrors it. No table, no route | S |
| Pointing at any artifact element | 16 | `FOCUS_ID` four kinds | Widen `FOCUS_ID` to the artifacts' declared kinds; the id stays an identifier, the label stays classified | S |
| **The Lead seeing results** | 20, 21 (explain a map, a finding) | runs layer has no results | A results layer in the frozen context: the run's admitted numbers and map pair statuses, bounded, classified by `context_classification`; `lead_contract` already refuses a number the context lacks | M, design first |
| Quotas before a run | 19 (Sample) | the preview returns status, donors, effective n only (`domain/population/audience_preview.py:74-79`); `SampleAudit` already holds the compositions (`domain/population/sampling.py:403-415`) | Return the quota composition from the preview | S |
| Live fieldwork counts | 19 (Fieldwork) | `progress("AI respondenti odpověděli", respondents=done, of=…)` (`aia_executors/ai_fieldwork.py:325`) | Per-quota-cell fill would need the draw's cells in the event; counts alone exist | S-M |
| A run's cost before it starts | 22 (Audience "Odhad nákladů") | `ResearchRuns.cost_ceiling` and `run_cost_ceiling` (`application/research.py:456-468`) | Expose it beside the audience's impact preview; a time estimate does not exist and stays "neposkytnuto" (D13) | S |
| Item duration in the Questionnaire outline | 17 | no duration anywhere in the design domain (searched `research_design.py`, `questionnaire_import.py`) | A deterministic estimate by item type, code not a model (product rule "No LLM for deterministic computation") | S |
| Assumptions carried across stages (A1 …) | 18, 22 | no domain concept | Part of the working content (a list on the brief), so no table; accepted like any edit | M |
| A respondent map | 20 | not built (`domain/sociomap/engine_v2.py:93`) | `sociomap-formula-corrections` 3 (M4) | L, method owner |
| "Continue until you need me" | 24 | a person's `APPROVE_GATE` starts every paid job; `WORKER_PERMISSIONS` holds `RUN_WORKFLOW` but no `APPROVE_GATE` (`domain/scope.py:202-213`) | An orchestration scope for the Lead (enqueue and read, never approve or spend beyond a standing, recorded wallet), and the wallet itself | **ADR** |
| Deep Research from every stage | 25 | Design Research from the design stages, Interpretation Research from Results | The enqueue boundary already freezes purpose and target (`application/deep_research.py`); what is new is a target per stage | M, ADR 0021 amendment |
| Map interpretation and report wording workers | 21 | none | New closed tasks on a results-worker job keyed on a run and a target (`lead-orchestration#LO9c`), not today's design-keyed job (corrected 2026-10-20) | M each |

**Chunk 11 is mostly built.** `approve_request` already holds a Lead-prepared design job to the spend
limit and the ledger (`application/research_lead.py:678-760 @ 0b4e05e`); D7 deliberately sends runs
and Deep Research through their own stage's start. What remains under 11 is the command registry
that 24 builds on.

## 7. Follow-ups for a docs PR

- Correct the front-matter of every plan in §4.1.
- Record decision D9 as resolved (Simulation out of the MVP, 2026-10-19) in `overview.md` *Decisions
  needed*, and M1-M8 above as open.
- Rewrite `mvp-acceptance.md` once M1-M5 are answered (M5).
- Add `prototypes/` to the documentation path list in `.github/workflows/ci.yml` (`ci-skip-docs-only`).
