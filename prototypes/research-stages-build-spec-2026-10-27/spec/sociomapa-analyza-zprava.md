# Sociomapa, Analýza, Zpráva: from the approved prototype to the product

> **Board updated 26 Oct (v65):** Zpráva now follows amended ADR 0035. "Uložení odmítnuto" and "Vrátit 56" are replaced by an "Upraveno ručně" note and a line in the approval dialog. `modifyContentControl` is now `ano`. §3.1 below describes the board as it was before that change. Z5 and Z6 stand as written.

Scope: the three stages after Výsledky, as the approved boards show them (`Sociomap.dc.html`, `Analysis.dc.html`,
`Report.dc.html`; decisions R1, R3, R5, R12, R15 in `Main.dc.html`). Code anchors are `path:line @ bd0d1ad6`
(develop). `R/` = `apps/web/src/components/rehome/research/`. Board critiques cite d5d36b25. Every anchor below
was re-read at bd0d1ad6, and stale ones are called out. This spec defines no visual tokens: the unified look contract
covers them. The Lead's cross-stage chat parts ("+" menu, Akce, Přidat, Kontext, Vidí, Zapamatovat si) belong to
the Lead spec and are not repeated here.

What moved since d5d36b25 (505 commits):
- #815 (`sociomapa-map-first`) merged. SOC9–SOC13 and sociomap-5-web 1–8 are ticked.
- On the editor:
  - RPT8b, RPT8c, RPT8d and RPT8f are built (#862, #864, #865, #875, #877, #880).
  - RPT8e is built but stays unticked until activation (#895, #906).
  - report-editor-hosting 1–4a are done; activation (chunk 4) is open.
- #911 records AUD-2: the Lead edits the report only as proposed versions that a person approves (`.planning/plans/report-delivery.md`).

---

## 1. Sociomapa (decision R1: the approved workshop, unchanged)

### 1.1 What the prototype shows
1. **Frame.** The workbench header shows the client, the study and the budget meter. The stage navigator shows
   Sociomapa in the Evidence phase, muted: it has no state of its own yet and its tooltip repeats Výsledky's line (R2).
2. **Stage body.** It is an exact snapshot of the approved Sociomap workshop, with a link "Otevřít živou dílnu"
   (`https://claude.ai/artifact/QWDidu8ztrcuiBNL5Sa4Vy`). The image's alt text gives the order:
   - a 3D object map with an Objekty | Respondenti bar;
   - below it, Co mapa ukazuje, Nejsilnější vztahy, Objekty, Respondenti a segmenty, Jak spolehlivá je mapa, and Jak
     byla spočtena.

   The board says: "Mapa, její ovládání a výklad pod ní se v tomto prototypu nepřekreslují; na develop je přináší PR #815."
3. **Lead conversation, the only new interaction.**
   - The person asks "Proč leží Zlatá Hora tak blízko Budvaru?".
   - The Lead answers from the stored map only (+0,41, interval, reliable). It adds that the map does not say why,
     and that Rešerše k výkladu can look it up without changing the map or the data.
   - Chips: "Vybrat: Zlatá Hora × Budvar" (select a pair) and "Detail dvojice" (inspect).
4. **Card "Hloubkový výzkum k výkladu · mapu nezmění".**
   - Title: "Rešerše k výkladu: Zlatá Hora × Budvar".
   - Facts: Cena nejvýše 1,20 USD; Cíl "dvojice na mapě běhu 21. 10., zmrazená podle SHA-256"; Smí "jen číst mapu".
   - Buttons: Teď ne / Spustit rešerši **1,20 USD**.
   - States:
     - ask (Čeká na vás);
     - run (Běží, with the latest report: "Sloučeno: 11 kandidátů, 1 v karanténě · 8 volání webu");
     - done (Hotovo: "4 zjištění se zdrojem, 1 odmítnuté · 0,58 USD", then "Použít ve zprávě").
   - R12: research is started only from this card; the stage has no start of its own.
5. **Critique items that remain after #815:**
   - the map's taste segments are descriptive, while readiness says "srovnání segmentů AIA zatím neumí";
   - the internal-map help cites "PROGRESS D6";
   - jargon on the stage: Stress-1, "Top vztahy", "potvrzené v kroku 3", "Deterministický výsledek".

### 1.2 Today on develop
- **The stage is the map.**
  - `R/SociomapStage.tsx:40-97 @ bd0d1ad6` renders the stage. Each mapped set gets `ObjectMapPanel` and then
    `MapExplained`, at `R/SociomapStage.tsx:84-90`.
  - A set stored under an older method says so and draws nothing (`R/SociomapStage.tsx:66-75`).
  - A map that is not signed off falls back to `ObjectMapView` (`R/SociomapStage.tsx:78-81`).
  - The stage is selected at `R/ExecutionSteps.tsx:1670-1674 @ bd0d1ad6`, only in the workbench (`leadOwns`).
  - This matches the board's snapshot; strings from the workshop such as "Kvalita mapy", "Sbalit panel ke kraji" and
    "Vycentrovat" are in `apps/web/src/i18n/cs.ts`.
- **Workshop-only controls (hypothesis).** The live workshop also holds a theme tuner ("Upravujete motiv",
  "Sytost za sklem", "Text v oknech"). None of these strings is on develop. They look like design-tool controls rather than
  product controls.
- **Lead targets exist.**
  - `objectTarget` and `pairTarget` are in `apps/web/src/lib/artifacts/sociomap.ts:34,41`.
  - A pair's detail is marked at `R/ObjectMapPanel.tsx:903-908 @ bd0d1ad6`.
  - The contract declares the targets, the view operations and the start: object/pair; select, filter, inspect;
    `interpretation_research` (`packages/aia_core/src/aia_core/domain/lead_artifacts.py:363-372 @ bd0d1ad6`).
- **The pair target exists in the engine.** `SOCIOMAP_RELATIONSHIP` is at
  `packages/aia_core/src/aia_core/domain/deep_research/integration.py:179 @ bd0d1ad6`.
- **Differences from the prototype:**
  - **No Lead start for Interpretation Research.**
    - The typed commands are listed at `packages/aia_core/src/aia_core/domain/lead_commands.py:75-86 @ bd0d1ad6` and
      have no interpretation command.
    - The web starts Interpretation Research only from the Zpráva panel, and only with an `ANALYSIS_MODULE` target
      (`apps/web/src/lib/api.ts:1556-1559 @ bd0d1ad6`; `R/InterpretationResearch.tsx:106-123, 152`).
    - So the pair card has no backend.
  - **Pair and object detail open in the panel's own windows** (sociomap-5-web chunk 6), not in the item inspector.
    SOC4 is open.
  - **Copy leftovers, re-verified:**
    - Stress-1: `apps/web/src/i18n/cs.ts:1238, 1242, 3882, 3924-3925` (used at `R/ObjectMapView.tsx:299, 570`, the
      fallback view).
    - "PROGRESS D6": `apps/web/src/i18n/cs.ts:3692`, used at `R/ObjectMapView.tsx:98`.
    - "Top vztahy na mapě": `apps/web/src/i18n/cs.ts:3974`, used at `R/ObjectMapPanel.tsx:49`.
    - "potvrzené v kroku 3": `apps/web/src/i18n/cs.ts:3970`, used at `R/ObjectMapPanel.tsx:476`.
    - "Deterministický výsledek": `apps/web/src/i18n/cs.ts:3986`. The key has no component consumer; it is dead.
    - "Chuťové segmenty" is at `apps/web/src/i18n/cs.ts:4051` (used at `R/ObjectMapPanel.tsx:768`), against
      `segments_unavailable` at `apps/web/src/i18n/cs.ts:3394`.
    - The board's anchors `i18n/cs.ts:2888, 3186, 3315…` are stale.
  - **Outside the workbench**, Výsledky's maps tab still carries the old guide ("Jak používat mapu a AI pomoc"),
    an amber notice card and `mapToolNotInAia` (`R/ExecutionSteps.tsx:1692-1711 @ bd0d1ad6`). That is SOC2's.

### 1.3 Build chunks
| # | Change | Backend | Plan | Test |
|---|---|---|---|---|
| S1 | Copy pass on the stage. <br>• Replace Stress-1 with credibility words in `ObjectMapView` (`R/ObjectMapView.tsx:98, 299, 570`). <br>• Drop the "PROGRESS D6" citation (`cs.ts:3692`). <br>• Rename "Top vztahy" (`cs.ts:3974`) and "potvrzené v kroku 3" (`cs.ts:3970`). <br>• Delete the dead `registerComputed` (`cs.ts:3986`). | backed (copy only) | artifact-sociomap SOC11 (reopen; follow-up) | `ObjectMapPanel.test.tsx`, `ObjectMapView.test.tsx`: no "Stress-1" or "PROGRESS" text; `make web_unused` |
| S2 | One sentence under the segments legend saying the map's taste segments are descriptive, so they do not contradict readiness's "srovnání segmentů AIA zatím neumí". Files: `R/ObjectMapPanel.tsx:768`, `R/MapExplained.tsx:143`. | backed | new (SOC6 neighbour) | `MapExplained.test.tsx` |
| S3 | The Lead's "Vybrat" and "Detail dvojice" chips on a pair. `readMapOp` (`lib/artifacts/sociomap.ts:111`) is routed to the panel's selection and to `useItemInspector().open` with the pair body from `relationDetail` (`R/ObjectMapPanel.tsx:903-908`). | backed (stored map only) | artifact-sociomap SOC4 | `ObjectMapPanel.test.tsx`: a `pair:` op selects and opens; a write op is refused |
| S4 | Typed start "Rešerše k výkladu" with a pair, object or battery target. <br>• Server: a new `lead_commands` entry and a Lead card carrying the ceiling quote. <br>• Server: `approve_chat_start` builds a `SOCIOMAP_RELATIONSHIP` / `SOCIOMAP_OBJECT` target from the focused `pair:` id. <br>• Web: the card in `LeadCards.tsx` / `lib/lead-cards.ts` with three states (ask, run with event feed words, done) and "Použít ve zprávě". <br>• Web: `InterpretationResearch`'s own start goes. | **NO BACKEND** (no command; `api.ts:1556-1559` sends `ANALYSIS_MODULE` only) | artifact-sociomap SOC5 + artifact-report RPT10 | `test_lead_commands.py` (fixture `commands.json`); `test_lead_chat_start.py`: the pair target is frozen by SHA-256; `lead-cards.test.ts` |
| S5 | Sociomapa's own stage state in the navigator (R2), instead of Výsledky's line. Files: `lib/workbench-stages.ts:30`, `research/lane.ts`. | backed (run steps) | new (R2, cross-stage) | `lane.test.ts` |
| S6 | Journey: `tools/ui_workbench/sociomap_journey.mjs` adds the pair chip and the card at 1440, 1100, 768 and 390 px, with zero paid jobs. | n/a | SOC8 | the journey |

Not built, by R1: no redesign of the map. The workshop's theme tuner is not product.

### 1.4 Backend gaps
- **No typed Interpretation Research start, and no pair target from the web.**
  - The command list `domain/lead_commands.py:75-86 @ bd0d1ad6` has none.
  - The web sends only `ANALYSIS_MODULE` (`apps/web/src/lib/api.ts:1558 @ bd0d1ad6`).
  - The engine already accepts the pair target (`integration.py:179`).
- **No pre-start ceiling for Interpretation Research outside a 409.**
  - The web learns the ceiling only from `cost_confirmation_required` (`R/InterpretationResearch.tsx:113-117 @ bd0d1ad6`).
  - The card needs "Cena nejvýše" before the click, through `POST …/deep-research/quote` (CLAUDE.md §2) with an
    interpretation target. Hypothesis: the quote route accepts that target. Verify before S4.

---

## 2. Analýza (decision R5: findings reviewed Přijmout / Upravit / Vyřadit)

### 2.1 What the prototype shows
1. **Lead message.**
   - Text: "Sedm z osmi částí je hotových. Hypotézy citovaly číslo, které analýza nepřipustila (62 % … efektivní n jen 21)…".
   - Chips: "Ukázat: Hypotézy" and "Zopakuj analýzu".
2. **Typed-command card "Váš příkaz · opakování analýzy · Hypotézy".**
   - Facts: Cena nejvýše **0,90 USD** ("pod prahem potvrzení · z rozpočtu studie"); Co se stane: "Znovu jen modul
     Hypotézy … 7 hotových modulů se převezme bez platby."
   - Buttons: Teď ne / Zopakovat analýzu 0,90 USD.
   - States: ask, then run ("AI analyzuje modul Hypotézy, kolo 2"), then done ("Stálo 0,41 USD"); Teď ne leads to kept
     ("Ponecháno · nic nespuštěno").
3. **Stage header.** "Analýza", "Běh z 21. 10. · interní · modelováno", and "Přijato N z M zjištění".
4. **Blocked note at the top**, coral.
   - Text: "Hypotézy potřebují opravu." plus the refused sentence quoted, with its reason ("efektivní n 21, málo dat").
   - Button "Opakovat analýzu" prepares the Lead card in item 2.
   - After the retry the note changes to "Hypotézy jsou hotové v novém kole (0,41 USD). Všech 8 částí je hotových."
5. **Odpovědi na výzkumné otázky**: a table with columns Otázka | Odpověď | Stav.
   - Each row shows VO id, the question, **the answer text itself**, where it comes from ("Srovnání objektů 1", or
     "při spuštění zaznamenáno jako mezera · doplňte výroky v Dotazníku"), and a state.
   - Three states in words:
     - **Odpovězeno**;
     - **Orientačně** (VO2: a difference without a statistical segment comparison);
     - **Bez dat** (VO3: not measured).
   - Coral is used only for what waits on the person.
6. **Zjištění.**
   - A single list with a module filter (Vše / Srovnání objektů / Cílová skupina / Dopady pro rozhodnutí / Omezení),
     and the note "Do zprávy jde jen to, co přijmete. Vyřazené zjištění zůstane tady, přeškrtnuté."
   - Each finding shows its module, a bold head plus body, and number chips (value + label) that lead to Výsledky.
   - Its state is one of: Čeká na vás / Přijato / Upraveno a přijato / Vyřazeno (struck through).
   - Actions: Vyřadit · Upravit · Přijmout. Once decided, a finding shows Vrátit.
   - Upravit opens an inline "Upravené znění" with "Uložit a přijmout", and the rule "Čísla v textu musí zůstat ta
     připuštěná; jiné číslo kontrola odmítne."
   - No ids anywhere.
7. **Externí kontext** ("rešerše k návrhu, ne data respondentů"): a claim with its source chip.
8. **Critique fixes in the board's list (e):**
   - one list instead of the doubled findings;
   - no run or claim ids;
   - the retry is reached from here, not from Průběh;
   - the coverage table shows the answer, not "ano".

### 2.2 Today on develop
- **Analýza is still a Výsledky tab.**
  - The workbench stage maps to `view: "analysis"` (`apps/web/src/lib/workbench-stages.ts:31 @ bd0d1ad6`).
  - The tab is labelled "AI analýza", and its description says findings "čeká na posouzení výzkumníkem"
    (`R/ExecutionSteps.tsx:1712 @ bd0d1ad6`).
  - The run frame and its tab bar stay above (`R/ResultsWorkspace.tsx:89`). There is no stage of its own, as Sociomapa
    has (`R/ExecutionSteps.tsx:1670`).
- **`AnalysisResults` (`R/ExecutionSteps.tsx:1849-1995 @ bd0d1ad6`) renders, in order:**
  1. a Card with `tone="notice"` (amber with nothing waiting, `:1912`);
  2. milestones, with the run id printed (`R/AnalysisCoverage.tsx:82 @ bd0d1ad6`: `run.run_id`);
  3. coverage, with columns Otázka | Odpověď | Zjištění | Co chybí (`R/AnalysisCoverage.tsx:97`). Odpověď is a
     state word ("ano", …) from `STATE_WORDS` (`R/AnalysisCoverage.tsx:25-31`), with six states:
     answered, unsupported, gap, blocked, pending, unanswered;
  4. "x z 8 částí" (`:1932-1941`);
  5. `AnalysisBlocked` (`:1942`);
  6. Hlavní zjištění across modules (`:1943-1962`);
  7. `AnalysisExternal` (`:1964`);
  8. "Analýza po částech", which repeats the findings per module (`:1965-1991`) and prints claim_id → evidence_ref
     (`:1989`).
- **The retry points away.** `R/AnalysisBlocked.tsx:15 @ bd0d1ad6`: "spouští se u běhu na stránce Průběh", with a link
  (`:67`). The file is 70 lines now; the board's anchors `:165-218` are stale.
- **The retry backend exists:**
  - the typed "Zopakuj analýzu" (`domain/lead_commands.py:85`);
  - `approve_chat_start` → `retry_failed_modules`, with no wallet charge
    (`packages/aia_core/src/aia_core/application/lead_chat_start.py:225-235 @ bd0d1ad6`);
  - the web request kind `analysis_retry` (`apps/web/src/lib/lead.ts:62-78`).
- **No ceiling before the start.** `GET …/analysis/retryable` answers only modules and stale
  (`apps/api/src/aia_api/routers/research.py:2048-2052 @ bd0d1ad6`). The ceiling is computed inside
  `retry_failed_modules` (`application/analysis_results.py:1211-1232`) but never answered.
- **Inspector copy** still says "čeká na posouzení výzkumníkem" (`R/AnalysisInspect.tsx:93-94 @ bd0d1ad6`) and prints
  "Připuštěné číslo běhu {runId}" with `<code>` evidence_ref (`:104`).
- **No finding review exists anywhere:**
  - no approval-ledger subject (`packages/aia_core/src/aia_core/domain/approval_ledger.py:39-59 @ bd0d1ad6`);
  - no plan chunk (artifact-analysis ANL1–ANL8 has none);
  - the report includes every key finding of every module (`application/report.py:483-491 @ bd0d1ad6`).

### 2.3 Build chunks
| # | Change | Backend | Plan | Test |
|---|---|---|---|---|
| A1 | Analýza as a stage of its own in the workbench, as SOC9 did for Sociomapa: no Výsledky tabs and no run card above. Files: `R/ExecutionSteps.tsx:1670` pattern → new `R/AnalysisStage.tsx`, `R/ResultsWorkspace.tsx:89`. The `tone="notice"` frame goes (amber only when a person is waited on). | backed | new (ANL "stage" twin of SOC9/SOC12) | `ExecutionSteps.test.tsx`: Analýza stage has no tablist; `analysis_journey.mjs` |
| A2 | Header line "Běh z {date} · interní · {origin}" from `resultOriginKind`. Remove the run id from the milestones (`R/AnalysisCoverage.tsx:82`), the claim-id dump (`R/ExecutionSteps.tsx:1989`) and the inspector's run id and `<code>` (`R/AnalysisInspect.tsx:104`). | backed | new (SOC11-style "no ids") | `AnalysisCoverage.test.tsx`, `AnalysisInspect.test.tsx`: no `RUN-` or `ART-` text |
| A3 | Coverage table as Otázka \| Odpověď (the module's answer text, `research_question_answers[].answer`) \| Stav. Origin line under the answer ("Srovnání objektů 1", or the start's recorded gap with "doplňte výroky v Dotazníku"). Three words: Odpovězeno / Orientačně / Bez dat. "Orientačně" comes from the comparison the research question asked that the run could not make (`compare_segments` unavailable, `research_trace.comparisons_of`). The extra states are mapped in `lib/analysis-coverage.ts:20,86`. | backed (answer text, gaps, comparisons are stored) | artifact-analysis ANL2 (rework) | `analysis-coverage.test.ts`: the state mapping, unknown never Odpovězeno |
| A4 | One findings list with a module filter, replacing both Hlavní zjištění and "Analýza po částech" (`R/ExecutionSteps.tsx:1943-1991`). Number chips (value + label) link to Výsledky through the existing `CitedNumbers` / `useOpenAnalysisItem`. The per-module summary goes into the inspector. | backed | artifact-analysis ANL3 (rework) + ANL5 | `ExecutionSteps.test.tsx`: each finding rendered once; the filter |
| A5 | Blocked note at the top. The quoted refused sentence and its reason come from `blockedModules` (`lib/analysis-blocked.ts`). "Opakovat analýzu" posts the typed `analysis_retry` to the Lead (`lib/lead.ts:62-78`) instead of linking to Průběh (`R/AnalysisBlocked.tsx:15,67`). Other routes: "stejná data selžou" gets its next step (fix in Dotazník or Data), and "run unfinished" links to Průběh. | backed (retry); ceiling gap below | artifact-analysis ANL4 + ANL6 | `AnalysisBlocked.test.tsx`: the button sends `analysis_retry`; no Průběh link for a retryable module |
| A6 | The Lead's retry card shows "Cena nejvýše" before the click. The server answers the ceiling `retry_failed_modules` already computes, in `GET …/analysis/retryable` (`routers/research.py:2048-2052`) and on the Lead's card. The card states ask, run, done and kept come from the run's events (R15: no percentage). | **NO BACKEND** (ceiling not answered) | artifact-analysis ANL6 | `test_research_api.py`: retryable answers `ceiling_usd` (null when unknown, never 0); `lead-cards.test.ts` |
| A7 | **Finding review**, server side. <br>• A new approval-ledger subject `analysis_finding` (`domain/approval_ledger.py:39-59`), with subject_id `<run>:<module>:<index>` and a decision of `accepted` / `edited` / `dropped`, plus `undo` as a newer row. <br>• An edit stores the new wording beside it after `draft.check` (`domain/analysis/draft.py:274-277`): the cited claim ids stay the same, and another number is refused with its sentence. <br>• Routes: `PUT …/runs/{id}/analysis/findings/{module}/{index}` and `GET …/analysis/findings`, under APPROVE_GATE. <br>• A migration admits the subject. | **NO BACKEND** | new (R5: "Potřebuje nový záznam v ledgeru") | `test_analysis_findings.py`: a changed number is refused, undo is newest-wins, scope comes from the path; migration test |
| A8 | **Finding review**, web. Přijmout / Upravit (inline "Upravené znění", "Uložit a přijmout") / Vyřadit (struck through, kept on the stage) / Vrátit, with "Přijato N z M zjištění" in the header. Files: new `lib/analysis-review.ts` (pure) and the findings list from A4. | needs A7 | new | `analysis-review.test.ts`; `analysis_journey.mjs` accept, edit, drop, undo |
| A9 | **The report reads the review.** `compose_internal_report` prints only accepted or edited findings, edited wording included (`application/report.py:483-491`); `client_report.py` does the same. A run with no review recorded keeps today's report and says "zjištění neposouzena" in Záznam pokrytí (`lib/report-coverage.ts`). | **NO BACKEND** | new; touches artifact-report RPT4 | `test_report_composition.py`: a dropped finding is absent, an edited one prints the new text with the same refs; unknown is never treated as accepted |
| A10 | Journey: Analýza at 1440, 1100, 768 and 390 px, recorded analysis, zero paid jobs. | n/a | ANL8 | `analysis_journey.mjs` |

### 2.4 Backend gaps
- **No finding-decision record.**
  - `domain/approval_ledger.py:39-59 @ bd0d1ad6` lists no such subject.
  - The report prints every key finding (`application/report.py:483-491 @ bd0d1ad6`).
  - **Settled (B2, Nigel, 26 Oct): yes.** The client report carries only accepted findings, as the approval
    dialog says ("Klientovi jdou jen přijatá zjištění (5)").
- **No pre-start ceiling for an analysis retry.** See `routers/research.py:2048-2052 @ bd0d1ad6` versus
  `application/analysis_results.py:1232` (computed internally).
- **"Orientačně" has no state.** `CoverageState` has six values and none of them is "answered without the comparison
  asked" (`apps/web/src/lib/analysis-coverage.ts:20 @ bd0d1ad6`). This is web-only if comparisons reach the page.
  Hypothesis: the design read through `useDesignQuestions` carries `research_question_comparisons`. Verify.

---

## 3. Zpráva (decisions R3, R12: one doc bar; the real ONLYOFFICE editor)

### 3.0 Layout (Nigel, 27 Oct: "i want the doc editor to be the main focus"; prototype v78)

The editor is the whole stage. Nothing is shown twice: coverage stays on Analýza and in the report's Omezení chapter, the literature
choice on the Lead's card. The editor theme work is its own board, **11b · Editor zprávy** (`ReportEditor.dc.html`).

- **One header row**, left to right:
  - "Zpráva" and the state ("Čeká na schválení" / "Schváleno · <who>, <when>" / "Nepřipravená");
  - chips: **"Zjištění n/m"** (coral while findings wait) and **"1 ruční úprava"** (neutral, only when there is one), each opening a
    small popover with the detail and its way out ("Posoudit na Analýze");
  - Interní / Pro klienta;
  - an icon button for "Osnova a zdroje";
  - **"Stáhnout ▾"**, one menu with DOCX and PDF that names the version it hands over;
  - the primary "Schválit" (or "Připravit klientskou zprávu" before the client report exists).
- **The editor fills the rest**, full width and height, no sheets around it.
- **"Osnova a zdroje"**: a right panel, closed by default: every part of the report with its source (`report_sources`, CHN1), a part
  not in this version shown "–", and a clicked number's detail at its top (Z7).
- **The approval dialog carries the checklist "Než schválíte"**: findings accepted (with "Posoudit na Analýze"), research questions'
  coverage (with "Záznam pokrytí"), hand edits, whether the literature review is in. Nothing there blocks; only a server refusal does,
  in words.
- **Pro klienta before preparing**: one sheet saying how the client report differs (accepted findings only, numbers labelled
  modelled, approved maps only, design and questionnaire appended, the client gate on every save).

### 3.1 What the prototype shows
1. **Lead conversation.**
   - The done card "Rešerše k výkladu: Zlatá Hora × Budvar":
     - facts: 4 findings with sources, 1 rejected, a sealed bundle, 0,58 USD;
     - a toggle between "Použít ve zprávě" and "Odebrat ze zprávy"; using it switches the document to **S rešerší**.
   - A self-update card "Zapamatovat si · zdarma" with two notes, one personal for all clients and one for this client
     only (Lead spec).
2. **The one doc bar**, the only place for these controls (R3):
   - **document segmented control:** Interní zpráva / Pro klienta / S rešerší;
   - **status pill:** Koncept · čeká na schválení / Schváleno · {name}, dnes / Nepřipravená;
   - **"Připravit klientskou zprávu"** for Pro klienta before it is prepared;
   - **approve button:** "Schválit pro interní použití" or "Schválit k předání klientovi";
   - **DOCX and PDF downloads**, disabled until prepared.
3. **Approval dialog.**
   - Text: "Schvalujete tuto verzi: {doc}, vytvořenou {date time}. Schválení se zapíše pod vaším jménem a stáhnete
     přesně tuto verzi."
   - Plus: "Čísla jsou modelovaná… Klientovi jdou jen přijatá zjištění (5)."
   - Buttons: Zrušit / Schválit.
4. **Editor surface: real ONLYOFFICE Docs 9.4.0.1 with the AIA theme and icons.**
   - A view switcher: Otevřený dokument / Titulní strana / Zamčené číslo / Číslo v textu.
   - A look switcher: AIA / Výchozí ONLYOFFICE.
   - **Locked number:** typing into "150" does nothing; a control handle shows. Clicking the number opens an AIA detail:
     Číslo 150 · Co je to · Základ (n = 48, modelováno) · Síla dat (orientační…) · V editoru (zamčený prvek, štítek
     zdroje) · Odkud (Výsledky · Mandlový nápoj). No ids.
   - **Number in prose:** the banner "Uložení odmítnuto: v části 8 Cílová skupina se změnilo číslo 56 na 596. … Vrátit 56".
5. **"Co zpráva obsahuje 7 z 8 částí"**: the parts, each "ve zprávě" or "není v této verzi" (Rešerše only when used).
   For Pro klienta before it is prepared: "Klientská zpráva … se otevře ve stejném editoru, se stejnými zamčenými čísly."
6. **"Co jsme na skutečném editoru ověřili"** (`finds`, 8 items):
   1. Locked numbers hold: 159 controls in the internal report.
   2. A real save (callback, status 6) keeps all 159 controls, locked, with their tags (59 characters).
   3. A number in model prose is not locked: 56 → 596 is saved. The save check must catch it.
   4. A save drops embedded fonts (3,97 → 2,55 MB). Proposal: install the fonts on the editor server, and embed them only
      at DOCX download, through `embed.py`. The PDF already embeds.
   5. The theme: 105 variables in `resources/themes/aia.json`, `uiTheme theme-aia`. The ONLYOFFICE logo stays (§7 terms).
   6. Icons: 375 ids redrawn, 13 taken from AIA's set, PNG at five scales.
   7. The docs gate must seed the theme into localStorage before the editor loads. Without it, the first load shows the
      default look and a reload loses icon offsets.
   8. Out of a theme's reach: the logo, the header layout, the UI font, and 297 symbols for formats, charts and equations.
7. **"Co AIA editoru posílá"** (`cfg`):
   - permissions: edit, comment, review yes; **download and print no**; **modifyContentControl no**;
   - `mode edit · lang cs · region cs-CZ · unit cm · zoom 90`;
   - `uiTheme theme-aia · compactHeader, compactToolbar, toolbarHideFileName`, with no plugins, chat or help;
   - server files: `resources/themes/aia.json`, `resources/img/aia-icons/` (3 SVG + 15 PNG), and IBM Plex Sans, Plex Mono
     and Source Serif 4 in `/usr/share/fonts`;
   - the docs gate seeds `ui-theme-id` and `ui-theme`;
   - autosave and forcesave, with callbackUrl to AIA;
   - the user's id and name come from the AIA session.
8. **Critique (e).**
   - One bar; the same version is approved and downloaded.
   - The editor is the main surface.
   - The editor itself may not download or print.
   - The client report is prepared, then approved.
   - A number opens a detail in words, without ids.

### 3.2 Today on develop
- **Zpráva is still a Výsledky tab.**
  - Stage `view: "report"` (`apps/web/src/lib/workbench-stages.ts:32 @ bd0d1ad6`).
  - The tab is labelled "Rešerše a zpráva" (`R/ExecutionSteps.tsx:1713-1718 @ bd0d1ad6`). Its body is
    `ReportDocumentView`, the run's report step card, `InterpretationResearch` (with its own start, `R/InterpretationResearch.tsx:152`)
    and a knowledge-context `<details>`.
  - Above the tabs sits the **CompleteReport card** (`R/ResultsWorkspace.tsx:89`, mounted at `R/ExecutionSteps.tsx:1683`).
- **Two independent document choices and two places to download.**
  - The CompleteReport card has a version Segment Interní / Pro klienta (`R/CompleteReport.tsx:423-432 @ bd0d1ad6`).
    It also has a Varianta select that lists `S rešerší · {run_id}` (`:438-452`), a Formát control (`:457-466`), and
    "Stáhnout zprávu" (`:475-483`). Other controls: downloads of approved edits (`:484-491`), "Vytvořit PDF"
    (`:511-515`), and "approve over there" copy (`:518-520`).
  - The pane has its own document chooser (`R/ReportDocumentView.tsx:317-334 @ bd0d1ad6`) and a doc bar that prints
    `report_artifact_id` (`:379-391`). When the editor is open, `EditorDocBar` takes over approval (`:395-401`;
    `R/EditorDocBar.tsx:190`).
  - The read-only draft's footer prints review_state, run id and artifact id (`R/ReportDocumentView.tsx:368`).
- **The editor is built and stays off.**
  - `R/ReportEditor.tsx` handles the ticket first, then api.js under SRI (`:59-72, 153-164`); `lib/report-editor.ts:47-79`.
  - The editor is used from 768 px and view mode below (`lib/report-editor.ts:38-44`).
  - The internal report and the report with literature only. The **client report is refused** server-side,
    `409 client_report_not_editable` (`apps/api/src/aia_api/routers/report_editor.py:136-137 @ bd0d1ad6`), and is
    read as HTML (`R/ReportDocumentView.tsx:406`).
- **The config differs from the board** (`apps/api/src/aia_api/routers/report_editor.py:154-190 @ bd0d1ad6`):
  - permissions are `edit`, **`download: True`, `print: True`**, `comment` (`:179`);
  - `lang: cs` only (`:183`), with no region, unit or zoom;
  - `customization` holds **only `forcesave`** (`:186`): no `uiTheme`, no compact header or toolbar, no hidden file name,
    no chat, help or plugins flags;
  - no `modifyContentControl`.
- **Prose numbers are shown, never refused.**
  - `domain/report/saved_changes.py:1-17 @ bd0d1ad6` classifies "a number typed outside every control (`typed`)" as
    "Upraveno ručně". A save is never refused, per ADR 0035 as amended on 2026-10-22, and artifact-report RPT8b is
    ticked.
  - The board's red "Uložení odmítnuto … Vrátit 56" banner **conflicts with that decision**; see Z6.
- **Saved versions lose their fonts at download.**
  - Downloads go through `export_docx` (`packages/aia_core/src/aia_core/application/report_export.py:151 @ bd0d1ad6`),
    reached from `download_report_editor_version` (`apps/api/src/aia_api/routers/report_editor.py:644-677 @ bd0d1ad6`).
    No font is re-embedded: the composer embeds only at render (`infrastructure/report_docx/renderer.py:129`;
    `embed.py:148`), so a saved version downloads without fonts.
- **Pieces still open.** Locked controls: RPT8a parts 1–2 are landed, part 3 is open
  (`.planning/plans/artifact-report.md:14, 293`).
- **Approval copy.**
  - Approval runs in the pane: `askApproval`, using `research.exec.report.approveAsk` (`R/ReportDocumentView.tsx:205`;
    `cs.ts:3560-3564`).
  - The dialog does not state the version's time or the accepted-findings count.

### 3.3 Build chunks
| # | Change | Backend | Plan | Test |
|---|---|---|---|---|
| Z1 | Zpráva as a stage of its own in the workbench, as A1: no Výsledky tabs, no CompleteReport card above. The card's parts list moves into the "Osnova a zdroje" panel (3.0), each part with its source (`reportParts`, `R/CompleteReport.tsx:52`; `domain/report/sources.py`). The knowledge `<details>` (`R/ExecutionSteps.tsx:1717`) leaves the stage. | backed | new (RPT twin of SOC9) | `ExecutionSteps.test.tsx`; `report_journey.mjs` |
| Z2 | **One doc bar** (R3), a new `R/ReportDocBar.tsx` holding: document (Interní / Pro klienta; the literature review is a part toggled from the Lead card, P3), status pill, the chips "Zjištění n/m" and "n ruční úprava", the Osnova toggle, one "Stáhnout" menu (DOCX, PDF), Připravit, Schválit (3.0). Into it go: CompleteReport's Segment, Varianta and Formát (`R/CompleteReport.tsx:421-483, 511-515`), the pane chooser (`R/ReportDocumentView.tsx:317-334`), and `EditorDocBar`'s approve (`R/EditorDocBar.tsx:190`). Downloads stay free before approval (RPT3b, Q73 (c)). Approved-edit downloads become the version list's (RPT5). | backed (existing routes: `…/report/download`, `…/report/pdf/download`, `…/report/client/prepare`, `…/editor/versions/{id}/download`, `/pdf`, `…/report/approve`) | artifact-report RPT3 (follow-up), RPT5 | `ReportDocBar.test.tsx`: one chooser; approve and download target the same `version_artifact_id`; `CompleteReport.test.tsx` removed or shrunk |
| Z3 | No ids on the stage. Remove the `report_artifact_id` (`R/ReportDocumentView.tsx:385`), the footer's review_state, run and artifact ids (`:368`), and `S rešerší · {run_id}` (`R/CompleteReport.tsx:446-449`). Show the review in words (`lib/report-status.ts:23-25`). | backed | new (SOC11-style) | `ReportDocumentView.test.tsx`: no `RUN-`, `ART-` or `APPROVED_INTERNAL` text |
| Z4 | Approval dialog copy: the document's name and the version's saved time (`saved_at`, from `GET …/editor/versions/{id}`), "stáhnete přesně tuto verzi", the modelled note, and the checklist "Než schválíte" (3.0): findings accepted, coverage (`lib/report-coverage.ts`), hand edits (the version's `changes`), literature in or not. Files: `cs.ts:3560-3564`, `R/ReportDocumentView.tsx:205`. | backed except the count (needs A7) | RPT3a follow-up | `ReportDocumentView.test.tsx` |
| Z5 | Editor config per the board, in `_config` (`apps/api/src/aia_api/routers/report_editor.py:154-190`). <br>• Set `permissions.download=False` and `print=False`, so the bar is the only exit. <br>• Set `editorConfig.region="cs-CZ"`. <br>• `customization`: `uiTheme="theme-aia"`, `compactHeader`, `compactToolbar`, `toolbarHideFileName`, `unit="cm"`, `zoom=90`, `plugins=False`, `chat=False`, `help=False`, `forcesave` kept. <br>• **Do not set `modifyContentControl: False`**; see the decision below. | backed | artifact-report RPT8c follow-up | `test_report_editor_api.py`: the signed config's keys; download and print false |
| Z6 | A prose-number change, inline, per ADR 0035 as amended. The board's banner becomes a non-blocking "Upraveno ručně: v části 8 Cílová skupina se změnilo číslo 56 na 596" at the sentence, from the version's `changes` (`typed`, `saved_changes.py`). It is not "Uložení odmítnuto". "Vrátit 56" is **NO BACKEND**: AIA cannot write into an open co-editing session without ONLYOFFICE's Automation API connector. Hypothesis: the connector is Developer Edition only, so Community cannot do it. Until a spike says otherwise, the inline note tells the person what to retype. | backed (detection); revert not | RPT8b follow-up; decision | `report-editor.test.ts` `changeWords`; `EditorDocBar.test.tsx` |
| Z7 | Number detail in words. A click on a locked number in the editor reaching AIA is **NO BACKEND** (hypothesis: with plugins off, Community gives no host event for a content-control click). Build the detail from the bar instead: the "Upraveno ručně" list and a "Čísla ve zprávě" list keyed by control tag (`domain/report/control_tags.py`). Each opens its detail at the top of the "Osnova a zdroje" panel (3.0) with Co je to / Základ / Síla dat / Odkud from the stored document model's ledger (`lib/artifacts/report.ts`). | backed (ledger) / spike for in-editor click | RPT8d follow-up, new | `report.test.ts` (artifacts): tag → ledger entry; no id in the body |
| Z8 | Client report in the editor. Today it is refused (`report_editor.py:136-137`) and read as HTML (`R/ReportDocumentView.tsx:406`). The board shows "se otevře ve stejném editoru". **Settled (B2, 26 Oct): editable**, with only accepted findings, and the client gate re-run on every saved version. This needs `variant=client` lines and sessions in `application/report_editor.py`, and the client gate (`domain/report/client_gate.py`) re-run on each saved version before approval. | **NO BACKEND** | new; decided B2 (RD0 gate on edited bytes) | `test_report_editor_api.py`: a client save is stored; approval is refused when the gate refuses the saved version |
| Z9 | Literature only from the Lead card (R12). Remove `InterpretationResearch`'s start, depth and refresh (`R/InterpretationResearch.tsx:149-153, 168`). "Použít ve zprávě" / "Odebrat ze zprávy" goes onto the card and selects the S rešerší document in the bar. The bundle stays readable beside the text. | needs S4 | artifact-report RPT10 | `lead-cards.test.ts`; `report_journey.mjs` |
| Z10 | Lead edits as proposed versions (AUD-2, #911): a Lead version in the bar's version list, approved by a person. | after activation | artifact-report RPT9 | per RPT9 |
| Z11 | Journey at 1440, 1100, 768 and 390 px: the bar, approve then download the same SHA, the theme visible on first load. | n/a | RPT7 | `report_journey.mjs`, `report_editor_journey.mjs` |

**Decision needed (Z5).** The board's `modifyContentControl: no` stops a person from unlocking a control. That
contradicts ADR 0035 as amended ("the researcher may unlock, retype or delete anything",
`domain/report/saved_changes.py:4-5 @ bd0d1ad6`). This spec keeps the amended ADR. The owner should confirm.

### 3.4 Editor theming and fonts in production
The facts are the ones verified this session. Custom themes are read from a file on the server. A custom theme uses
the classic icon layout, which is why the PNG sprites were re-rendered. A save drops embedded fonts. Locked controls and
their tags survive a save. Prose numbers are not controls. The sources are in
`scratchpad/aia-editor-theme/` (`aia.json`: id `theme-aia`, 105 colours, `icons.sprite-buttons-base-url`
`/web-apps/apps/common/main/resources/img/aia-icons/`; `aia-icons/`: 15 PNG + 3 SVG, 1.7 MB; `tools/build.py`,
`merge.py`, `raster.mjs`, `seedshot.mjs`).

| # | Change | Anchor today | Test |
|---|---|---|---|
| T1 | **Bring the theme into the repo.** Commit `aia.json`, `aia-icons/` and the generator `tools/` under `deploy/develop/docs/theme/`. Colours come from `apps/web/src/design/tokens.json`, through a check (or generation in `scripts/build-tokens.mjs`) that fails on drift. | none in the repo | new `test_editor_theme.py`: the colours equal the tokens; every sprite id of 9.4.0.1 is present (`build.py`'s assertion as a test) |
| T2 | **Mount the theme and icons read-only** in the Document Server compose: <br>• `./theme/aia.json:/var/www/onlyoffice/documentserver/web-apps/apps/common/main/resources/themes/aia.json:ro` <br>• `./theme/aia-icons:/var/www/onlyoffice/documentserver/web-apps/apps/common/main/resources/img/aia-icons:ro` <br>The exact themes path is a hypothesis taken from the board's cfg ("resources/themes/aia.json"); verify it against 9.4.0.1. After a restart, check that **api.js's SRI digest is unchanged**: if the theme needs `documentserver-flush-cache.sh`, api.js is rebuilt (`.planning/plans/artifact-report.md:597-605 @ bd0d1ad6`). | `deploy/develop/docs/docker-compose.yml:54-63 @ bd0d1ad6` (today `local-production-linux.json` is the only bind) | `test_develop_host_configuration.py`: both mounts present and `:ro`; the post-deploy SRI check from artifact-report.md:603-605 rerun after a restart |
| T3 | **Install the fonts.** Mount `fonts/` read-only at `/usr/share/fonts/truetype/aia`: IBM Plex Sans (4 weights + italics), Plex Mono and Source Serif 4, the files in `packages/aia_core/src/aia_core/infrastructure/report_docx/fonts/` with their `SHA256SUMS` and OFL licences. The deploy bundle copies them into `docs/fonts/` (`.github/workflows/deploy-develop.yml:169-181 @ bd0d1ad6` copies only `deploy/develop/<dir>`). The start script regenerates the font cache: the first start takes about a minute (`docker-compose.yml:69-70`). Leave the `docs_fonts` volume (`:58`) as is. | `.planning/plans/report-editor-hosting.md:180-182 @ bd0d1ad6` (planned "optional", never built) | `test_develop_host_configuration.py`: mount + bundle step; after deploy, `docker exec … fc-list \| grep -c "IBM Plex Sans"` > 0 (runbook) |
| T4 | **The docs gate seeds localStorage.** The ticket is spent by a credentialed CORS fetch whose `next` is api.js (`apps/web/src/lib/report-editor.ts:68-79`; `apps/api/src/aia_api/routers/session.py:288-337 @ bd0d1ad6` answers a 302 to `next`). So no page runs on the editor's origin, and the 302 cannot seed anything. Add a page on the editor's origin: <br>• `GET /__aia/theme` served by Caddy (`handle /__aia/theme` before the gate, `file_server` from the mounted `theme/seed.html`; no secret in it). <br>• It writes `ui-theme-id` and `ui-theme` (`{id, type, text, colors, icons:{basepath}}`, as `tools/seedshot.mjs` does) and then `postMessage("aia-theme-ready")` to AIA's origin. <br>• It sends its own `Content-Security-Policy` with `script-src 'sha256-…'` and keeps `frame-ancestors https://{$AIA_PUBLIC_HOSTNAME}`. <br>`ReportEditor.tsx` loads it in a hidden iframe after the ticket and before `new DocsAPI.DocEditor` (`R/ReportEditor.tsx:153-164, 198-202`). Its storage is the editor iframe's own partition (same origin under the same top-level site). It times out into the default look, which is never an error. | `deploy/develop/Caddyfile:154-230 @ bd0d1ad6` (no such route; `@editor_script` at `:166-172`, ticket at `:175-178`) | `test_caddy_routes.py`: `/__aia/theme` is the only ungated non-cache path and serves a static file; `ReportEditor.test.tsx`: order ticket → theme → api.js; `report_editor_journey.mjs`: the first load shows the AIA header, and a reload keeps the icon offsets |
| T5 | **The config asks for the theme:** `customization.uiTheme="theme-aia"` (Z5). | `apps/api/src/aia_api/routers/report_editor.py:186 @ bd0d1ad6` | `test_report_editor_api.py` |
| T6 | **Update `deploy/develop/docs/NOTICE`.** Its line "nothing in this repository changes, replaces or adds to its code" becomes untrue. <br>• Name the mounted files: the theme JSON, the icon sprites and the fonts with their OFL licences. <br>• The sprites are **re-drawn from ONLYOFFICE's own AGPL sprites** (`tools/build.py` edits their SVG symbols; `merge.py` pastes over their PNG rows). That makes them a modified work of the program's assets, so §13's source offer applies. The NOTICE must point users to the sprites' corresponding source: the generator and its inputs, from T1. Because the repository is private, the source must be served, for example as a tarball under `/__aia/source/` on the editor origin. <br>• The logo and §7 terms are unchanged (board finding 5). <br>• Update the hosting plan's AGPL paragraph to match. | `deploy/develop/docs/NOTICE:14-22 @ bd0d1ad6`; `.planning/plans/report-editor-hosting.md:69-77 @ bd0d1ad6` | `test_develop_host_configuration.py`: the NOTICE names every bind mount under `docs/` (a parity test between the compose binds and the NOTICE lines). **Owner or legal decision on T6 before T2.** |
| T7 | **Fonts in the downloaded DOCX.** **Settled (B6, Nigel, 26 Oct): re-embed at download.** Re-embed them in `export_docx` (`packages/aia_core/src/aia_core/application/report_export.py:151 @ bd0d1ad6`), only for an editor-saved version that has no `w:embedTrueTypeFonts`, using `embed_fonts` (`infrastructure/report_docx/embed.py:148 @ bd0d1ad6`) over the same `FONTS` the renderer uses (`renderer.py:129`). <br>• This follows the approval stamp's precedent: the export already rewrites footers and leaves every other byte as stored (`report_export.py:1-24`). <br>• Stored versions stay small (2,55 MB) and the editor never re-reads embedded fonts. <br>• The export's bytes are not the stored SHA. The response headers carry the stored version's id and SHA; the export's own SHA is recorded as the stamp's is. <br>• The PDF needs nothing: the worker has the fonts. <br>• The alternative is to not embed: the editor server and the PDF have the fonts, but a client opening the DOCX without Plex sees substitutions. | `apps/api/src/aia_api/routers/report_editor.py:644-677 @ bd0d1ad6` (download serves `_export` as is) | `test_report_export.py`: a version without fonts exports with all FONTS embedded; text, controls and tags are byte-equal outside `fontTable` and `settings`; the approved stamp still applies |
| T8 | **Activation** (report-editor-hosting 4; RPT8e tick). It covers T2–T5, the runbook section in `deploy/develop/README.md` § Report editor, and the theme's first-load and reload check on the real server. | `.planning/plans/report-editor-hosting.md` chunk 4 (open) | smoke rows for `docs.<hostname>` (4a, done) and `/__aia/theme` |

Out of the theme's reach (board finding 8): the ONLYOFFICE logo and header layout, the UI font (Plex would need the
editor's code changed) and the 297 format, chart and equation symbols. Changing them would patch the image, which
reverses the hosting plan's AGPL decision. Not proposed.

### 3.5 Backend gaps
- **The client report cannot be edited:** `409 client_report_not_editable`
  (`apps/api/src/aia_api/routers/report_editor.py:136-137 @ bd0d1ad6`). This blocks Z8.
- **No reverting a number in an open session.** No AIA path writes into a live document; the save check only reports
  (`domain/report/saved_changes.py:1-17 @ bd0d1ad6`). This blocks "Vrátit 56". Hypothesis: it needs the paid Automation
  API.
- **No host event for a click on a locked control** (hypothesis, Community with plugins off). This blocks the
  in-editor number detail (Z7).
- **The accepted-findings count and "only accepted findings reach the client"** depend on A7 and A9
  (`application/report.py:483-491 @ bd0d1ad6`).
- **The editor config** lacks the theme and UI flags, and still allows download and print
  (`apps/api/src/aia_api/routers/report_editor.py:179-187 @ bd0d1ad6`). Fixed by Z5 and T5.
- **Fonts at download:** none re-embedded (`application/report_export.py:151 @ bd0d1ad6`). Fixed by T7.
- **RPT8a part 3**: the map, design, run and bundle spans are not yet locked
  (`.planning/plans/artifact-report.md:14, 293 @ bd0d1ad6`). The board's 159 controls count parts 1–2 only.
