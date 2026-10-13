---
status: in-progress
chunks:
  - "[x] 1. Stage status as data: src/research/lane.ts derives each stage's state (done / needs you / running / not started) and one line from the working content; unit-tested"
  - "[x] 2. Study shell: AppShell `study` mode -- icon-only global navigation, one-row header (breadcrumbs, save state, AI pomoc), the stage track under it replacing ResearchRail; the stage title moves into the page"
  - "[x] 3. Inspector: the right column holds this stage's readiness and what still blocks a run; AI pomoc becomes its second tab (ResearchAssistance content, same jobs and contracts)"
  - "[x] 4. Zadání: denser sections, AI actions on the card they change, drop files anywhere on the stage, per-file reading state; readiness moves to the inspector"
  - "[x] 5. Návrh: an AI proposal is reviewed inline as changes, accepted per item or all (AgentProposalDialog stays for jobs from other stages until 6-8)"
  - "[x] 6. Dotazník: one toolbar (add, Excel, AI), outline beside the editor, the invalid question marked where it is"
  - "[x] 7. Cílová skupina and Dimenze: one source/population/strategy card; dimensions as a checklist grid; sample beside them"
  - "[x] 8. Kontrola, Průběh, Výsledky: problems first with a fix link, the run's steps as one list, the complete-report card at the top of Výsledky"
  - "[x] 9. Browser pass on the workbench (ux_journey at 1440/1024/768/390), screenshots in the PR"
  - "[ ] B1. Complete internal report: compose_internal_report gains the design summary, a method / AI-respondent provenance section, per-question aggregate tables and the questionnaire appendix; the Deep Research variant is stored as an artifact with a review_state"
  - "[ ] B2. Approve a report: a researcher-only route over ArtifactRepository.approve and the button on Výsledky (APPROVED_INTERNAL)"
  - "[ ] B3. PDF beside the DOCX: headless LibreOffice in the worker image, one artifact per report, its cost and time measured"
  - "[ ] B4. Sociomap methodology registry (OI-17) replacing D6_OPEN: per (methodology version, spec fingerprint) status; the owner's 2026-10-13 decision recorded as its first row (aia-sociomap-3 as computed today); a client branch in compose_map_sections"
  - "[ ] B5. Client report composer (client_report recipe, CLIENT_FACING ledger) admitting MODELLED_AI_PANEL evidence under the owner's 2026-10-13 decision, every modelled number labelled modelováno; after chunks 6-8 (owner's order)"
  - "[ ] B6. Audience filters in a run: not new code -- AIA_AI_POPULATION_PERSONAS_ENABLED (operator call) and audience-catalogue-cpu chunk 4 (owned there); dimensions applied to respondents stay with sociomap-formula-corrections I0/I1"
---
# Research lane redesign

Design: the Claude Design canvas "AIA desktop research studio" (owner's, 2026-10-13),
artboards Main … Report. Owner's brief: the UI is bulky, AI triggers are detached
from what they change, drag and drop is weak, stages show no status, the flow reads
as a wizard, the shell takes too much width, and run/results feel bolted on.

## Rules this plan keeps

- Presentation only in chunks 1-9: no API, job, contract or validation changes. Every
  AI action keeps its existing job (`useResearchAgents`, `runJob`) and its cost line.
- Every "V AIA zatím není" notice stays where a person meets it.
- Token utilities only (`apps/web/src/design/tokens.json`); no new colours.
- Each chunk keeps the existing tests green; a test that asserts the old layout is
  changed only to assert the same behaviour in the new one, never loosened.

## Owner decisions

- **2026-10-13, the Sociomap in client material (D6).** The owner (nigelblount) in the
  design session: "just assume the current sociomapping methodology in this design …
  we should be able to just use the current unfinished sociomap version." Read as:
  maps computed with the methodology in force today (aia-sociomap-3) may appear in the
  complete report and the client version, labelled with the version that computed
  them. Engineering consequence: B4. The switch is one constant today
  (`D6_OPEN`, research_sociomap.py:216-218 @ b05b698) and global -- flipping it would
  also release aia-sociomap-1 -- so B4 replaces it with a per-version registry (OI-17)
  rather than flipping it. The docs PR carries the decision into overview.md (D6) and
  OI-16.

- **2026-10-13, modelled data in the client report (ANL-1 / ADR 0024).** The owner, in
  the same session: "allow modelled data in client report". Read as: the client version
  of the complete report may carry numbers from AI respondents drawn from the population
  (MODELLED_AI_PANEL) before the panel holdout validation (panel-grounded-respondents
  7e2-7h) has passed, provided every such number keeps the modelled disclosure
  ("modelováno: AI respondenti z populace", `report/evidence.py` modelled_panel). It does
  not admit fictional data (SYNTHETIC_*), which stays non-evidence. Engineering
  consequence: B5. Today `lifts_internal_only` (evidence/validation.py) admits MODELLED
  only under a current holdout, and `CLIENT_ADMISSIBLE_ORIGINS` (fieldwork.py) is the
  allowlist every client-facing gate reads; B5 changes that rule in one place, recorded
  as this decision, not by bypassing a gate. The docs PR carries it into overview.md
  (ANL-1) and ADR 0024.
- **2026-10-13, order of work.** The owner: "finish the stages first" -- chunks 6-8
  before B1-B5.

## Backend gaps the design shows

From the assessment of 2026-10-13 (anchors @ b05b698):

- Only `compose_internal_report` is used in production (application/report.py:117);
  `client_report` / `final_report` (domain/report/templates.py:172, :181) have no
  production caller. The report carries module prose, not per-question tables, the
  design or the questionnaire.
- No route approves a report: `ArtifactRepository.approve`
  (infrastructure/artifact_repository.py:523) has no report caller, so "Koncept čeká
  na schválení" cannot change.
- DOCX only; LibreOffice exists only in tools/report_preview.py.
- ANL-1 / ADR 0024: modelled panel evidence is INTERNAL_ONLY until a holdout
  validation (panel-grounded-respondents 7e2-7h). This, not D6, is what keeps a client
  report from existing; the owner's D6 decision does not lift it.
- Audience filters are applied on the panel path already (domain/panel_source.py:76-91);
  the run takes it only with AIA_AI_POPULATION_PERSONAS_ENABLED, off by default
  (apps/api/src/aia_api/config.py:91-95). Dimensions have no consumer anywhere.
- OI-61 is decided (licence_determinations.py:58-92); its Status line in open-items.md
  still says Open (stale; docs PR).

## Progress notes

- Chunk 5: the decision stays one for the whole proposal -- accept per item would change
  the gate-1 contract (`ResearchAgentJobs.accept`, one acceptance per job). The review is
  inline (ProposalReview) with the changes listed (src/research/proposal-diff.ts).
- Chunk 4: only AI actions that exist as jobs are drawn; the canvas's "Zpřesnit" and
  "Doplnit z podkladů" have no job and were not built.
- Chunk 8: the complete-report card at the top of Výsledky (CompleteReport.tsx;
  each part claimed only from the run's own steps), Kontrola's checks first with
  failures on top.
- Chunk 6: the toolbar holds the method, the edit/preview switch and "Optimalizovat s AI";
  the questionnaire's readiness is in the inspector; a question without wording is
  marked on its card (aria-invalid, the reason beside it). The three-path chooser stays
  as the empty questionnaire's screen: which screen draws is parity-tested
  (questionnaireView).
- Chunk 7: the audience summary and the chosen dimensions are in the inspector; the
  sample is a card in the page (it is an input, not a summary); strategies and the
  dimension catalogue are grids.
- Chunk 8, finished: Průběh has the run's finished-step count and bar in its header,
  and its actions (results, cancel, retry, refresh) with the actual cost in the
  inspector.
- Chunk 9: `ux_journey.mjs` passes (84 layout checks at 1440/1024/768/390, 4 interaction
  checks) on the workbench after chunks 1-8; screenshots in the PR.

## Findings

- **F1. ux_journey.mjs had drifted from develop, twice.** (1) The 3D camera controls moved
  into a closed disclosure in 1eb36ab (ObjectMapView.tsx:302), after the journey's last
  update (19d1179); the journey clicked a hidden "Otočit vpravo" and timed out. (2)
  DesignSourceNote (213d491) asks `/design/source`, whose 404 means "not reused"; the
  journey counted it as an error. Reproduction: `node tools/ui_workbench/ux_journey.mjs`
  on develop @ b05b698 with the workbench up. Fixed on this branch: the journey opens the
  disclosure, names the expected 404, and judges a logged 404 by its request.
- **F2. A report can never be approved.** `ArtifactRepository.approve`
  (infrastructure/artifact_repository.py:523 @ b05b698) has no report caller, so
  `review_state` stays DRAFT_UNAPPROVED. Fix: B2.
- **F3. OI-61's Status line says Open** (open-items.md:2108 @ b05b698) under a "Decision,
  closed" heading (:2080). Docs PR.

## Doc follow-up

- CLAUDE.md § 2 map, src/components/rehome/research/: `ResearchRail` is gone; `StageTrack`
  (every stage with its state, Průběh its own stage), `Inspector` (InspectorProvider /
  InspectorSlot: a stage's readiness beside it, then AI pomoc, then "Do spuštění
  zbývá"), `ProposalReview` (a design proposal reviewed inline, its changes listed),
  `CompleteReport` (the report card on Výsledky); src/research/lane.ts (each stage's
  state from working content and runs), src/research/proposal-diff.ts.
- CLAUDE.md § 2 map, src/components/aia/AppShell: a `track` puts the shell in study
  mode (icon-only global navigation, one-row header, the title in the page).
- overview.md D6 and OI-16: the owner's 2026-10-13 decision (above).
- open-items.md: F1-F3 to be numbered there.
