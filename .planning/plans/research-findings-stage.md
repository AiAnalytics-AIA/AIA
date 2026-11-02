---
status: planned
chunks:
  - "[ ] FND0. The report outline (Osnova zprávy) as data, and the ADR it needs: the report's structure (chapters and sections in the report's own order) where each section holds points, not prose; a point is a claim or a number with its kind (finding, data point, method point, conclusion, recommendation), its visual (table, graph, process diagram, map or none) and its provenance link; the stage after Sociomapa and before Zpráva on the study's working project (revision-checked saves); a stop as a named checkpoint the researcher closes; the ADR 0026 decision-4 record for this new kind of report material (W1, a contract before any code)"
  - "[ ] FND1. The one study's stage track (ADR 0046 decision 3, A2 \"One merged study\"): the canvas's nine steps in five groups (Zadání; Data, Rešerše, Předpoklady; Model; Výsledky, Sociomapa; Osnova zprávy, Zpráva), the model steps shown only when Zadání says a model is needed; the survey stages (Dotazník to Analýza) left out of new studies and read-only on a study that holds survey content or runs, the routes refusing a write by name (survey_lane_frozen), nothing deleted before the lane is archived (mvp-master-plan#MP19)"
  - "[ ] FND2. The provenance link: every number and claim in the report outline is a hyperlink to what stands behind it, resolved by code from stored ids: a Deep Research finding's quote in its captured snapshot, a typed value and its route response, a client dataset's column under its accepted contract version, a model run's result and its method entry in Metodika, a map and its method; a point whose link does not resolve shows as unverified and cannot reach Zpráva"
  - "[ ] FND3. Findings in: every accepted Design Research and Interpretation Research finding and every typed value (deep-research-v2 DRV3) offered as a point; the researcher's check per finding (kept, set aside, needs checking) recorded in the approval ledger, never changing the sealed bundle; a point whose source is set aside goes stale, named"
  - "[ ] FND4. Tables: built from accepted points, every cell a ref with its link, units and periods carried; never a number written by a model or typed without a source"
  - "[ ] FND5. Graphs from those tables (bar, line, stacked, scatter), drawn with the viz tokens, every mark linked to its point; the same drawing on screen and in the DOCX (report_docx charts)"
  - "[ ] FND6. Process diagrams and other visuals: a registry of visual kinds; a process diagram as typed data (steps, actors, decisions, flows) edited in place (input standard I1-I11), each element that states a fact linked to its point; rendered as SVG in the stage and the report"
  - "[ ] FND7. The Lead in the stage: it reads the report outline, the findings and the data through its read tools, proposes the outline, a point, a visual or a move per change, and a person accepts (ADR 0026); a paid lookup only through the card (lead-orchestration)"
  - "[ ] FND8. Stops: the researcher opens, names and closes each; the closed stops are what Zpráva receives; reopening one marks the report draft stale and names the points that moved"
  - "[ ] FND9. Zpráva written from the report outline: the report's prose around the closed points in the same outline, every printed number and claim keeping its provenance link (with artifact-report RPT8a's tagged content controls); the report states no point the report outline does not hold, checked before approval; an external finding labelled as external context"
  - "[ ] FND10. The Sociomapa stage, before the report outline: the scenario map (cost-model-study CS1-CS5) when the study has a model, an expert map (situation-reports EX1-EX2), or a unit or period map once sociomapa-systemu SYS11 passes; its option clusters and hedges (ADR 0046 A6) offered to the report outline as points with their method link"
  - "[ ] FND11. The journey: a fictional research study from the brief to an approved report through a report outline holding one table, one graph, one process diagram and an expert map, every link resolving, over recorded Deep Research; zero paid calls"
---
# Osnova zprávy, the report outline: every point of the report, its visual and its source, before the prose

Written 2026-11-02 on the product owner's answers, in the PM coordinator's chat. After the survey lane's
freeze ([ADR 0046](../../docs/architecture/adr/0046-business-decisions-pivot.md)), a research study
keeps Zadání, Návrh with Design Research, and Zpráva, and gains this stage. In his words:

> "there needs to be another step before, where the user goes through the findings, checks the outcomes
> of the deep research, build tables, graphs, processs maps. basically a stop or more if needed wheere
> the user discusses with the lead the outcome of the deep research and builds what goes into the report
> which will be shown in the zprava section. ofcourse we still need a step for the sociomaps."

> "i basically want a stage where the bare bone findings are presented in a structure of the report.
> Instead of having all the words written out as we do in the report, this stage will be a structured
> flow of all the findings, data and points made in the report, with their corresponding graphs, tables,
> or process diagrams or whatever visual we neeed. its almost as if you had the report but took out all
> hte claims and data and got an xray view of the report with all the main points. everything should be
> verifiable and ideally numbers or claims have hyperlinks connected to see what the source or
> methodology for that claim/figure is"

**Owner:** S1 (the stage and the Lead) with S2 (findings, typed values, links and maps). Proposed;
the session that takes it reviews this plan first.

## What the stage is

The report outline is the report with its prose taken out:
- the report's own outline;
- under each section, the points it will make: a claim or a number;
- each point with its visual (a table, a graph, a process diagram, a map), where it has one;
- every number and every claim a link to its source or its method.

The researcher and the Lead build it in one stop or several. Zpráva then writes the prose around exactly
these points.

**The order of the study** (the owner's later answer, A2: "One merged study", as on the canvas "AIA
Obchodní model – prototyp"): Zadání → Data → Rešerše (Design Research) → Předpoklady → Model → Výsledky →
**Sociomapa** (Sociomapa systémů, FND10) → **the report outline** (one stop or several) → Zpráva. The model steps
appear only when Zadání says a model is needed. Sociomapa comes before the report outline, so the map's points can
enter it. The stage is called **Osnova zprávy** (the report outline; the owner, 2 Nov, ADR 0046 A15),
which replaces the working name "X-ray" (Rentgen zprávy) he first gave it.

## Rules

- **Every point is verifiable.** A number or claim without a resolving link shows as unverified, and it
  cannot reach the report (FND2).
- **Models propose, a person accepts.** A built item never holds a number a model wrote.
- **An external finding is labelled external context**, never respondent evidence or client data
  (ADR 0021).
- **A stop is closed by a person.** Nothing reaches Zpráva from an open stop.
- **The report says what the report outline holds, and nothing more** (FND9).

## What is reused

- **Deep Research's sealed bundle and accepted findings.** These are `deep_research/bundle.py`,
  `application/deep_research.py` and `components/rehome/research/InterpretationResearch`. The stage
  reads them and never writes them.
- **The report's evidence model.** Every printed number is a ref (`domain/report/model.py`), and the
  section-source manifest is `domain/report/sources.py`. The report editor's tagged content controls
  come from `artifact-report` RPT8a.
- **The Lead's per-change accept** (ADR 0026) and its read tools.
- **The stage frame of the research workbench** (`research-lead-workbench`).
