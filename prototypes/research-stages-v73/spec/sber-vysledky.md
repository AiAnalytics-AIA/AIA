# Sběr dat, its respondent disc, and Výsledky: from prototype to product

> **Board updated 26 Oct (v64):** the disc board now follows this section. The invented live and parked batches and the hollow "replayed" dots are gone. It adds "Nový pokus" (a new attempt counts from 0) and "Fiktivní" (fills only when the step ends). §3.1 below describes the board as it was before that change.

Prototype boards: `canvas/project/Fieldwork.dc.html` (Kontrola, Průběh), `FieldworkDisc.dc.html`,
`Results.dc.html`, plus decisions in `Main.dc.html`. Code anchors are `path:line @ bd0d1ad6`. `R/` is
`apps/web/src/components/rehome/research/`. The boards' "Dnes v AIA" critiques were anchored at
d5d36b25. I checked each one used here again on bd0d1ad6, and the differences are noted.

Visual tokens are left out on purpose, because a unified look contract is coming. Missing layout
primitives are listed in §5.

---

## 0. Decisions this section depends on

- **R6: two views of one stage, Kontrola a spuštění and Průběh. Still open (Main.dc.html:159, "Zatím
  nerozhodnuto vámi").** The prototype puts both in one stage, with a header segment that switches
  between them. When a run is running, the stage opens on Průběh. On develop they are two routes,
  `run` and `progress`, under one workbench stage (`lib/workbench-stages.ts:28,63`). The navigator's
  tone reads Průběh while a run moves (`:81-83`), but its link always goes to `run`
  (`stageHref`, `:47`, with `STAGES.fieldwork.step = "run"` at `:28`). Opening Kontrola also
  **submits a Design Revision on every visit** (`R/ExecutionSteps.tsx:710`). The d5d36b25 critique
  still holds. Chunks F1/F2 below assume R6 = yes. If R6 = no, keep the two routes and still make
  F1's link fix.
- **R11: "AI model" / "kód" as the step tag, not technical names (Main.dc.html:164).** Today the
  tags read `stepWork.ai = "AI · ModelGateway"` and `running = "deterministické"`
  (`apps/web/src/i18n/cs.ts:3497-3500`), shown at `R/ExecutionSteps.tsx:1473`. Which tag applies is
  already decided per step by `researchStepWork` (`lib/activity-orb.ts:76-81`). Only the words change
  (chunk F6).
- R10 (state colours), R13 (the amount comes first in money buttons, "+10 USD a pokračovat"), R14 and
  R16 are look-contract decisions. They are named here only where they change markup. R15 ("a card
  shows only what the backend reports") is the rule every chunk below follows.

---

## 1. Sběr dat · Kontrola a spuštění

### 1.1 What the prototype shows (Fieldwork.dc.html, view `check`)

1. **Header row:** h1 "Sběr dat". A segmented tab group labelled "Pohled" with "Kontrola a spuštění" and
   "Průběh" (`role=tablist`, `aria-selected`). The forward button "Výsledky ›".
2. **Section "Co spustíte"**, with the pill "Lze spustit" (or not-ready). A two-column fact list:
   - **Návrh:** "Revize 8 · 23 otázek, 1 sada o 7 značkách · Dotazník" (a link to the stage).
   - **Kdo odpovídá:** a radio segment, "AI respondenti z populace" | "Fiktivní respondenti", with a
     caption that changes with the choice. Default: "Výchozí. Odpovědi modeluje AI podle profilů z
     panelu; zpráva je tak označí." Fictional: "Jen pro zkoušku: vymyšlení respondenti, nic se
     neplatí, výsledky nejsou zjištění."
   - **Populace:** "Česko 18+, živá verze · Pijáci ležáku 18–65 · N 400".
   - **Cena nejvýše:** the ceiling in large type, captioned "horní mez, ne odhad · nad prahem potvrzení
     10,00 USD". It reads 0,00 USD for fictional respondents.
   - **Rozpočet studie:** "zbývá 38,80 USD z 50,00".
   - Action row: a caption giving the non-blocking warnings in one line ("2 upozornění neblokují: VO3
     nic neměří; 2 dvojice na mapě budou slabé.") and the primary button "Spustit výzkum".
3. **`<details>` "Všechny kontroly (9)"**, with the summary caption "7 v pořádku · 2 upozornění · 0
   brání". Collapsed by default. One row per check: status glyph, text, and "Opravit" (a link to the
   fixing stage) when the check is not a pass.
4. **Spend dialog** (modal, `aria-modal`), titled "Spustit výzkum za nejvýše {ceiling}?". Body: "Částka
   dosahuje prahu potvrzení studie. Je to horní mez, ne odhad; platí se jen skutečně zodpovězené
   dotazy." Four named amounts: Strop běhu, Rozpočet studie: zbývá, Práh potvrzení, Peněženka ("nečerpá
   se"). Buttons "Zrušit" and the primary "Spustit · nejvýše **{ceiling}**" (R13). With fictional
   respondents the run starts without the dialog.
5. **Lead pane (shared shell):** the run as a card, "Běh AI respondentů · revize 8", with a state pill
   (Čeká na vás / Běží / Čeká na rozpočet / Hotovo). Facts: Cena nejvýše (with "horní mez, ne odhad"),
   Utraceno, Kroky "n z 16". While running, a line "Krok {k} z 16: {step} · odpovědělo x z N". Actions
   by state: "Teď ne" + "Spustit výzkum **14,60 USD**"; parked: "Navýšit rozpočet"; done: "Výsledky".
   The "+" menu offers "Spusť výzkum".
6. **Navigator slot:** "Sběr dat", with tone and line run / park / done ("Běží · 5 z 16", "Čeká na
   rozpočet", "Běh hotov").

### 1.2 Today on develop

- `RunStep` (`R/ExecutionSteps.tsx:643-927`). It renders about ten cards in this order:
  - the readiness card with every check (`:836-857`);
  - AnswerabilityGate (`:858-868`);
  - ResearchTraceCard (`:870`);
  - QuestionOutlookCard (`:877`);
  - Receipt (`:878`);
  - CostCard (`:879`);
  - RespondentChoice (`:881`);
  - PopulationChoice (`:887`);
  - the AI-runtime notice or the synthetic banner (`:889-893`);
  - RunList (`:897`).

  An ActionDock follows, with back "5. Dimenze" (`:899`) and an `AiButton` Start (`:919`).
- Confirmation is a text message through `useResearch().confirm` (`:755-756`). `SpendDialog`
  (`components/ui/SpendDialog.tsx:60`) exists and nothing on the research screens uses it.
- Differences from the prototype:
  - There is no one-glance "co · kdo · kolik" summary. The money and the respondents sit below three
    answerability and trace cards.
  - The checks are not collapsed.
  - Visiting the stage submits a revision (`:710`). The prototype reads readiness only.
  - The population line is not composed. Today it is PopulationChoice, shown only when the client has
    materialized children (`:887`).
  - The budget remainder is not on the page until the confirm text (`withBudget`).
- **Kept, but missing from the prototype.** These enforce rules, so they must stay:
  - `AnswerabilityGate`, the "start with limitations" acknowledgement (`:858-868`), required by the
    server when `answerability.acknowledgement_required`.
  - PopulationChoice for a materialized child (`:887`).
  - The `found` / "found by start" notices (`:844-849`; PC13).

  They go inside "Co spustíte" (F3).

### 1.3 Build chunks

| # | Change (files) | Backed by | Plan | Proving test |
|---|---|---|---|---|
| F1 | **One stage, two views (R6).** The workbench stage `fieldwork` links to `progress` while `stageState` reads Průběh (running / fault / you), else to `run`. Add a "Pohled" tab segment to the stage header that switches the route. Files: `lib/workbench-stages.ts` (`stageHref` gains the lane), `components/workbench/*` header slot, `R/ExecutionSteps.tsx`. | Web only. The run state comes from `GET …/research/runs/{id}` (`apps/api/src/aia_api/routers/research.py:1750`). | new (depends on R6) | `workbench-stages.test.ts`: the fieldwork href is `progress` while the lane's progress tone is running, else `run`. `ExecutionSteps.test.tsx`: the segment's `aria-selected` follows the route. |
| F2 | **Kontrola reads, never submits.** Read readiness from the working copy (`GET …/research/readiness/working`, `routers/research.py:1386`). Submit the revision only inside Start. Files: `R/ExecutionSteps.tsx` (`:704-724`, `start`). | Backed: the working readiness route, and `submitWorkingDesign`, which becomes the first step of `start()`. | new | `ExecutionSteps.test.tsx`: mounting RunStep makes no `submit` call; Start submits, then calls `research.start` with the returned revision id. |
| F3 | **"Co spustíte" summary.** One section: Návrh (revision · `readiness.questions` / `batteries` / `objects` · link), Kdo odpovídá (`persona_sources` as a radio segment, the caption keyed by source), Populace (`run.population` label via `lib/population.ts labelOf`, plus the audience description from the working copy, plus `readiness.n`), Cena nejvýše (`cost_ceiling_usd`, or the unknown reason, never 0), Rozpočet studie (remainder via `lib/budget-line.ts`). Then a one-line warnings caption (the WARN checks, counted, first two named) and Start. AnswerabilityGate and PopulationChoice render inside the section when they apply. Files: `R/ExecutionSteps.tsx` (replaces `Receipt` and `CostCard` and the respondent / population cards), `src/i18n/cs.ts`. | Backed: `Readiness` (`apps/web/src/lib/api.ts:997-1031`) carries checks, counts, n, `cost_ceiling_usd` / `_unknown`, `spend_confirm_usd`, `confirmation_required`, `persona_source(s)`, `answerability`. The remainder comes from the study (`readBudget`). | artifact-fieldwork **FLD6** (partly) | `ExecutionSteps.test.tsx`: the summary shows the ceiling, or "nelze určit" when `cost_ceiling_usd` is null (never "0,00"); choosing a source rereads readiness; the gate appears only when `acknowledgement_required`. |
| F4 | **The checks collapsed:** `<details>` "Všechny kontroly (n)", the summary "x v pořádku · y upozornění · z brání", rows with "Opravit" via `fixStep` (`R/ExecutionSteps.tsx:428`). Open it by default when any check FAILs. Move ResearchTraceCard and QuestionOutlookCard **into** this details block: Vzorek already shows the outlook (SampleView §2). Drop RunList (`:897`): earlier runs are Lead cards. | Backed: `readiness.checks`. | FLD6 | `ExecutionSteps.test.tsx`: the summary counts match the checks; a FAIL opens it; "Opravit" links to `fixStep(id)`. |
| F5 | **SpendDialog on Start.** Replace `ask()` (`:755-756`) with `SpendDialog` kind "Potvrzení útraty", showing four lines: Strop běhu, Rozpočet studie (zbývá), Práh potvrzení, Peněženka. The primary button reads "Spustit · nejvýše {ceiling}". No dialog when the ceiling is below the threshold, or for fictional respondents (`confirmation_required` false). Also use it for the retry / new-run confirms (`:1153,:1226,:1269`). | Backed: `confirmation_required`, `spend_confirm_usd`, `cost_ceiling_usd`. Wallet via `GET /studies/{id}/wallet` (`available:false` → "nečerpá se"). | FLD6 ("one spend dialog") | `ExecutionSteps.test.tsx`: Start with `confirmation_required` opens a dialog naming all four amounts; Esc cancels and nothing starts; confirming sends `confirm_cost_usd` = ceiling. |
| F6 | **R11 words.** Change `stepWork.ai` to "AI model" and `stepWork.running` to "kód" (`i18n/cs.ts:3497-3500`). | Web only. | FLD2 follow-up | `ExecutionSteps.test.tsx` (the FLD2 test): a model step tag reads "AI model", aggregate reads "kód". |
| F7 | **The Lead card agrees with Průběh.** In `lib/lead-cards.ts`, the steps done exclude `needsRepair` steps (`:136`, which today counts SUCCEEDED+SKIPPED, while Průběh at `R/ExecutionSteps.tsx:1403` also excludes repairs). The cost reads `run.spend.spent_usd` as "Utraceno" and `cost_ceiling.usd` as "Cena nejvýše", not `actual_cost_usd` (`:142`). | Backed: `spend` and `cost_ceiling` come only on the single-run read (`routers/research.py:1750`; CLAUDE.md §2: null on a listed run), so the card needs a single-run read per live card. | new (with R15 / LeadCards) | `lead-cards.test.ts`: a run whose analysis step needs repair counts the same done steps as Průběh; the cost is the spend, and unknown spend reads unknown. |

---

## 2. Sběr dat · Průběh

### 2.1 What the prototype shows (view `progress`)

1. **No run on this revision:** a note, "Na revizi 8 zatím běh není.", with buttons "Kontrola a spuštění"
   and "Přehrát ukázku běhu (fiktivní, zdarma)". The demo button is prototype-only. In the product it is
   a fictional-source start, F3.
2. **Four KPI tiles:** Utraceno · Drženo pro běžící krok · Strop běhu · Zbývá v rozpočtu studie.
3. **Budget park note** (amber, shown only when parked): "**{step} čeká na rozpočet.** Potřebuje nejvýše
   **0,90 USD**, ve studii zbývá 0,32 USD. Nic se neztratilo." It has a "Nový rozpočet" money stepper
   (±10 USD, its minimum the first amount above today's budget) and the primary "**+{delta}** a
   pokračovat" (R13).
4. **Section "Respondenti":** the disc (§3). The "Ukázka: N 400 / N 1 600" segment and the "obnovený
   běh" checkbox are prototype demo controls. **Do not build them.**
5. **Section "Kroky běhu"** ("{done} z 16 hotovo"): an ordered list of every step. Each row has its
   number, a state glyph, its Czech name, a detail ("odpovědělo x z N" on fieldwork), a tag ("AI model"
   / "kód", R11) and a state word (Hotovo / Běží / Čeká na rozpočet / Čeká na předchozí).
6. The Lead card and navigator as in §1.1 (5, 6).

### 2.2 Today on develop

`ProgressStep` (`R/ExecutionSteps.tsx:1366-1500`). Its parts:

- **Inspector:** `ProgressActions` (`:1246-1330`): to Results, Zrušit, Zkusit znovu, Obnovit, the new-run
  offer, and the gate.
- **Banners:** "found" (`:1410`), OriginBanners (`:1411`), RespondentsReceipt (`:1412`).
- **SpendCard** (`:1336-1364`, rows from `lib/run-spend.ts:28-59`): Utraceno, Drženo, Strop běhu, Bez
  známé ceny, Zbývá ve studii. All five are backed; the prototype's four tiles are a subset, and "Bez
  známé ceny" must stay whenever `uncertain_calls > 0`.
- **Run head card** (`:1415-1458`): state chip, revision, times, a progress bar plus "x z y kroků hotovo"
  (`:1423-1428`), the runtime park with Obnovit (`:1430-1441`), and the budget wait with `BudgetLift`
  (`:1442-1449`). The lift is a free-amount form with a note (`R/BudgetLift.tsx:25-50`). It neither
  states what the step needs nor requires an amount above today's budget (`valid` at `:44` accepts
  `total >= budget`).
- **Step list** (`:1459-1497`): chip, label, `data-step-work` tag (`:1473`), origin chip, times,
  attempts, `waitingDetail`, `lastReported` (FLD3), `QuotaFillTable` (RQC7b), and `StepActivityPanel`
  (64 px orb, the latest line, facts, a log).

Differences from the prototype:

- The steps differ. The prototype has 16 steps, including "Zpráva ve formátu PDF" and "Kontrola zprávy".
  The real graph is compile → preflight → run → {aggregate, sociomap} → 8 analysis modules (parallel,
  all depending only on `aggregate`) → report, plus the experimental sociomapping pair
  (`packages/aia_core/src/aia_core/domain/workflow_templates.py:113-119,225-259`;
  `domain/analysis/steps.py:44`). The PDF is rendered inside the report step. **Build from the run's
  steps, never a fixed 16.** Because steps run in parallel, "Krok k z N" on the card is not a single
  index (§1.1(5)). Show the running step names instead (`lib/lead-cards.ts:130-135` already does).
- There are no KPI tiles. Náklady is a definition list.
- The fieldwork step shows no disc. Its count appears only as the activity panel's facts while running,
  and as `lastReported` once it stops.
- The log prints raw codes (§4 G4).

### 2.3 Build chunks

| # | Change | Backed by | Plan | Proving test |
|---|---|---|---|---|
| P1 | **Náklady as tiles.** Render `spendRows` (`lib/run-spend.ts:28`) as a tile row. Keep "Bez známé ceny" as a fifth tile only when present. Label "Drženo pro běžící krok" (`i18n/cs.ts:3596`). | Backed: `run.spend`, `run.cost_ceiling` (FLD4a / d), `readBudget`. | FLD4b (re-layout) | `ExecutionSteps.test.tsx`: the four tiles show; with `uncertain_calls>0` a fifth appears; unknown spend reads `spend.unknown`, never 0. |
| P2 | **Kroky běhu as one ordered list from `run.steps`.** Each row has its number, state glyph, `stepLabel`, fieldwork detail ("odpovědělo x z N" from `activity.progress`, or `lastReported`), the R11 tag, and a state word. Keep `waitingDetail`, attempts and origin under the row. Move the run head's state chip and "x z y kroků hotovo" into the section header. | Backed: `run.steps` (`routers/research.py:1108-1134`), the step feed. | FLD2 (re-layout) | `ExecutionSteps.test.tsx`: as many rows as `run.steps` in the listed order, with no "PDF" or "Kontrola zprávy" row; a waiting step shows its `waitingDetail`. |
| P3 | **Budget park note: the need, and a lift that must go up.** Show "{step} čeká na rozpočet. Potřebuje nejvýše {requested}, ve studii zbývá {remaining}." The lift becomes a `Stepper` (whole USD, minimum budget+1) and a button "**+{delta} USD** a pokračovat". Use SpendDialog kind "Zvýšení rozpočtu studie" when the lift crosses the threshold. Keep the note field (it goes to the ledger). Say "Nic se neztratilo" **only when the fieldwork checkpoint was on for that attempt**, otherwise "Odpovědi rozpracované dávky se po navýšení zaplatí znovu". Neither is knowable today: G2 and G3. | **NO BACKEND** for the need. `requested_usd` / `remaining_usd` / `budget_usd` are written to the attempt's error (`apps/worker/src/aia_worker/worker.py:389-398`), but `_step` serves only `error_message` / `error_reason` (`routers/research.py:1124-1126`). Lift: `POST …/runs/{id}/budget` (`:1831`). | FLD6 / CR-3 follow-up, new | API: `test_research_api` gives a step parked at budget `budget_need: {requested_usd, remaining_usd}`. Web: the lift button is disabled at ≤ the current budget and names the delta. |
| P4 | **The respondent disc** in "Respondenti" (§3). | See §3. | run-qc-and-checkpoint **RQC7c** (re-scoped: counts, not a per-respondent grid) | See §3. |
| P5 | **Feed words, no raw codes.** In `describe()`, STEP_RECOVERY reads the coded reason through `codeWords("research.exec.wait", reason)`, so "budget_exceeded" becomes "Krok čeká, protože by překročil rozpočet studie." (`i18n/cs.ts:3538`). STEP_RESUMED gets a line ("Rozpočet navýšen z {before} na {after} USD"). "Worker krok převzal" becomes "Krok začal" (`i18n/cs.ts:3264`). | Backed: STEP_RECOVERY payload `{action, reason, error_reason?}` (`packages/aia_core/src/aia_core/infrastructure/workflow_repository.py:2043-2068`); STEP_RESUMED payload `budget_before_usd` / `after` (`:2453-2470`). | new (FLD3 follow-up) | `step-activity.test.ts`: a STEP_RECOVERY with message "run: budget_exceeded" yields a line without the token `budget_exceeded`; a STEP_RESUMED yields the lift line. |
| P6 | **Open Průběh on a run.** The R6 header segment (F1). After a start, route to Průběh (already `router.push(stepHref("progress"))`, `R/ExecutionSteps.tsx:796-798`). | Web only. | F1 | Covered by F1. |

---

## 3. FieldworkDisc: the respondents, 1:1 with the run's reports

### 3.1 What the prototype shows (FieldworkDisc.dc.html; the same component in Fieldwork.dc.html "Respondenti")

- **The canvas disc.** N dots on a golden-angle ("sunflower") spiral:
  - `r = c·√(k+0.5)`, `a = k·GA`, `GA = π(3−√5)`, `c = R/√N`, dot radius `max(2.4–3, c·0.5)`.
  - Dot k is the k-th respondent **in answer order**. The first answers sit at the centre.
- **Five dot states, in order of k:**
  1. replayed from the journal: hollow ring;
  2. done in this attempt: filled;
  3. live: the next ≤10, pulsing (the next report's batch);
  4. parked: the next ≤10, amber;
  5. waiting: small grey.

  The pulse stops under `prefers-reduced-motion`. The canvas is `aria-hidden`.
- **Legend panel beside the disc:**
  - an eyebrow with a live dot and the phase (Živě z běhu / Zastaveno na rozpočtu / Sběr dat hotov /
    Čeká na sestavení dotazníku / Běh zatím neběží);
  - a big count "{done} z {N} AI respondentů" (`aria-live=polite`);
  - a sub-line: "{sent} dotazů modelu · {k} z deníku bez platby", or "x % · další hlášení běhu přidá
    nejvýše 10", or the parked or fictional sentence;
  - a stacked bar (paid / replayed / live);
  - three groups with counts: **Hotovo** (Odpověděli · dotaz modelu; Převzato z deníku · bez platby),
    **Probíhá** (Rozpracovaná dávka, do dalšího hlášení), **Zbývá** (Čekají na řadu; Zastaveno na
    rozpočtu). A row whose count is zero is dimmed.
- **Truth note:** "Přesně podle běhu, 1 : 1." It explains the 10-respondent / 30 s cadence and the
  1.5 s poll, and says position is answer order only. A developer line names the contract.
- **Future (RQC7b) sketch:** the same disc split into sectors per quota group (age bands), each filling
  separately. Captioned as a proposal.

### 3.2 The contract, exactly (bd0d1ad6)

**What `fieldwork_progress` carries.** A `STEP_PROGRESS` event with message `fieldwork_progress`
(`packages/aia_core/src/aia_core/domain/fieldwork_events.py:55`), payload keys
`version, respondents, of, sent, replayed, cells` (`:60`), version `aia-fieldwork-events-2` (`:50`):

| Key | Meaning | Unit |
|---|---|---|
| `respondents` | answered so far in **this attempt** (replayed ones included) | respondents |
| `of` | `len(plans)`, the respondents this attempt will answer | respondents |
| `sent` | blocks this attempt **sent** to a model | blocks |
| `replayed` | blocks answered from the journal at no cost | blocks |
| `cells` | answered per quota cell **since the previous report**, or `null` | respondents |

Notes on the counts:

- `sent` and `replayed` are cumulative per attempt (`apps/executors/src/aia_executors/ai_fieldwork.py:396,488-491`).
- `cells` is `null` unless `AIA_AI_FIELDWORK_QUOTA_FILL` is on and the run is a panel run (`:388-389,402-410`).
- `fieldwork_sample` (`fieldwork_events.py:56,61,95-111`) comes once per attempt, before the first
  respondent: `{quota_fields, cells:[{key, values, n}]}`.

**Cadence.**

- `progress_every = 10` (`ai_fieldwork.py:159`). No composition overrides it (`ai_runtime.py:1030-1046`).
- A report is due at every multiple of 10 and at the last respondent (`fieldwork_events.py:85-92`),
  checked after each respondent (`ai_fieldwork.py:500-507`).
- **Heartbeat**, only with `AIA_AI_FIELDWORK_HEARTBEAT` on (`ai_fieldwork.py:178`). It fires between
  one respondent's blocks once `HEARTBEAT_SECONDS = 30` (`fieldwork_events.py:51`) have passed, and
  reports `respondents = index`, the same count as before (`ai_fieldwork.py:492-498`). A single long
  model call writes nothing until it returns. So the board's "nejpozději po 30 s" holds only with the
  switch on, and only between blocks.
- The switch is **off on develop** (`deploy/develop/docker-compose.yml:300`); checkpoint (`:299`) and
  quota fill (`:301`) are off too.

**Fictional fieldwork** (the workbench, `fictional_roster`) writes **no** `fieldwork_progress`. It writes
one final sentence with `respondents` and no `of` (`apps/executors/src/aia_executors/research.py:580-584`),
which `foldActivity` ignores (`apps/web/src/lib/step-activity.ts:187-190`). The disc there jumps from
empty to full when the step succeeds.

**The poll.**

- The event feed is read every `ACTIVITY_POLL_MS = 1500` (`R/useStepActivity.ts:15`), only while some
  step is RUNNING (`R/ExecutionSteps.tsx:1373,1376`).
- Up to 8 pages of 500 events per tick (`R/useStepActivity.ts:17,22`).
- The feed is read once more to its end when the step stops (`:68-75`).
- The run itself is polled every 2 s, or 10 s while WAITING (`lib/research-execution.ts:114-115`).
- So a dot fills at most about 1.5 s after the worker writes its report, in jumps of up to 10.

**A resumed run's replayed respondents.**

- A new attempt of the same step (after a park, a lease loss or recovery) starts its counts from 0. The
  web resets progress, replays and quota on `ATTEMPT_CLAIMED` (`step-activity.ts:185`).
- A **retry run** is a new run id, so a new feed key and a new count.
- With `AIA_AI_FIELDWORK_CHECKPOINT` on, journaled blocks (keyed by the run lineage's first run and the
  request fingerprint) are replayed at no cost (`ai_fieldwork.py:413-434`), counted in `replayed`
  **blocks**, and reported at the same 10-respondent cadence. They are not reported faster: the board's
  "40 per tick" for replays is wrong.
- **There is no count of replayed respondents.** A respondent may be part-replayed, part-sent when the
  stop fell mid-respondent. The hollow-dot count cannot be derived exactly (G1). Replay follows plan
  order because the loop is ordered (`:412`), so if a respondent count existed, hollow dots would be the
  first k. Whether every replayed respondent precedes every paid one is a **hypothesis**: it holds when
  the earlier attempt answered in order and nothing in the plan moved.

**Whether a budget park is visible in the events.** Yes, but not inside `fieldwork_progress`:

- `BudgetExceeded` ends the attempt (`apps/worker/src/aia_worker/worker.py:389-398`).
- The engine writes `STEP_RECOVERY` on the fieldwork step with message `"run: budget_exceeded"` and
  payload `{action: "PARK_BUDGET", reason: "budget_exceeded", attempt_number, consumes_attempt: false}`
  (`workflow_repository.py:2043-2068`; `domain/workflow.py:578-584`).
- The step's status becomes `AWAITING_BUDGET`, with `waiting_reason: "budget_exceeded"` on the run
  read.
- The lift writes `STEP_RESUMED` (`workflow_repository.py:2453-2470`). The next attempt's
  `ATTEMPT_CLAIMED` resets the counts.
- The amount the step needed is **not** in the event or the step response (G2).
- Without the checkpoint, the answered blocks of the parked attempt are paid again on resume.

**What "live" and "parked" dots really are.** There is no in-flight batch in the data. The board's
"next ≤10" equals `progress_every`, which **the event does not carry** (G3). A parked attempt has
stopped, so nothing is in flight.

**What per-quota reporting (RQC7b) needs.** It is **built** behind `AIA_AI_FIELDWORK_QUOTA_FILL`:
`fieldwork_sample` cells plus `cells` deltas on each report. The web already folds them into
`quota.cells[].answered` (`step-activity.ts:193-212`) and shows `QuotaFillTable`
(`R/StepActivityPanel.tsx:130-154`). For the sector disc, the web needs:

- (a) the switch on;
- (b) sectors laid out from `fieldwork_sample.cells[].n`, one sector per **cell**. Cells can number in
  the hundreds (sex × age × region, plus education from n 700), so an age-band disc means grouping cells
  by one `quota_field`. That grouping is a web rule over `values`, and `quota_fields` names the fields;
- (c) roster runs and samples without quota fields have no cells, so they fall back to the plain disc.

No backend change is needed for sectors, but the switch is off on develop (`docker-compose.yml:301`)
and has not been measured there.

### 3.3 Build chunks

| # | Change | Backed by | Plan | Proving test |
|---|---|---|---|---|
| D1 | **Pure model `lib/fieldwork-disc.ts`.** `discModel(activity, step, specN)` returns `{N, done, replayed, paid, waiting, parked, phase, sent}`. Rules: `N` = the latest `of`, else the compiled specification's `n` (before the first report), else unknown (no disc, words only). `done` = `progress.done`. `phase` comes from the step status (RUNNING / AWAITING_BUDGET / SUCCEEDED / RUNNABLE before fieldwork / FAILED / CANCELLED). Waiting dots are `N − done`, all amber when the step is AWAITING_BUDGET. The live batch is **not** invented: nothing pulses until G3. Hollow dots come only from G1, else 0, with the replayed **blocks** said in the legend. A heartbeat report that repeats a count changes nothing. | `StepActivity` (`step-activity.ts:16-36`); the step status. | RQC7c (new scope) | `fieldwork-disc.test.ts`: a fold of the contract fixture (`packages/aia_core/tests/fixtures/fieldwork_events/contract.json`) gives `done = respondents`; ATTEMPT_CLAIMED resets to 0; AWAITING_BUDGET makes waiting dots parked; unknown `of` and no spec n gives no N (never 0). |
| D2 | **`FieldworkDisc.tsx` (canvas).** Sunflower layout as §3.1. Redraw on model change, not in a constant rAF loop. If G3 lands, a pulse rAF runs only while live dots exist and never under reduced motion. Device-pixel-ratio aware, `aria-hidden`. Performance budget: N ≤ 10,000 (`SAMPLE_SIZE_BOUNDS`, `domain/research_design.py:98`) in one draw under 16 ms. | Web only. | RQC7c | `FieldworkDisc.test.tsx` (jsdom with a canvas mock): it draws N arcs, the first `done` filled, and draws no new frame without a model change; a perf test of `layout(10000)` in under 5 ms in node. |
| D3 | **Legend and truth note** beside the disc: the phase eyebrow, "{done} z {N} AI respondentů" (live polite), "{sent} dotazů modelu" from `sent` (never `paid × 3`), "{replayed} bloků z deníku bez platby", the three groups. The truth note's cadence text is **built from facts**: "po 10 respondentech" only once G3 carries `every`, "nejpozději po 30 s" only once the heartbeat state is known (G3). Until then it says "v dávkách" without a number. For a fictional run: "Fiktivní respondenti: odpovědi vylosuje kód, nic se neplatí", and the disc fills when the step succeeds. | `sent`, `replayed`, `respondents`, `of` (§3.2). | RQC7c | `ExecutionSteps.test.tsx`: the count text equals the latest event; the replayed line appears only when `replayed > 0`; a fictional run shows the fictional sentence. |
| D4 | **Mount it in Průběh's "Respondenti".** It replaces the fieldwork row's activity facts and `lastReported` as the primary display. The step list row keeps one line. `QuotaFillTable` stays under the disc. | — | RQC7c / FLD3 | `ExecutionSteps.test.tsx`: Respondenti renders on a run with a `run` step; a run read without its steps renders no disc. |
| D5 | **Sector disc (RQC7b)**, shown when `quota` is present: sectors from `fieldwork_sample.cells[].n`, grouped by one chosen `quota_field` (the first by default). Each sector fills from its cells' `answered`. A cell answered past its `n` is drawn full and said, never clipped silently. | Backed behind `AIA_AI_FIELDWORK_QUOTA_FILL` (`ai_fieldwork.py:179-183`); web fold `step-activity.ts:193-212`. | RQC7b follow-up, new | `fieldwork-disc.test.ts`: two cells of one age band sum into one sector; with no `quota`, the plain disc. |
| D6 | **Journey.** The disc at 1440 / 1100 / 768 / 390 on a recorded panel run with the switches on (`sample_panel_journey.mjs` fixture world), with zero paid jobs. | — | FLD8 extension | `tools/ui_workbench/research_journey.mjs` (or a new `fieldwork_disc_journey.mjs`): the disc's count equals the last `fieldwork_progress.respondents` read from the DB. |

---

## 4. Výsledky

### 4.1 What the prototype shows (Results.dc.html)

1. **Header:** h1 "Výsledky"; a pill "Běh z 21. 10. · revize 7"; a caption link "návrh je teď v revizi 8
   →" (to Návrh) when the design has moved; the forward button "Sociomapa ›". **No inner tabs and no
   overview** ("Žádné vnitřní záložky").
2. **Note "Modelováno:"** "odpovědi 400 AI respondentů z populace, ne měření skutečných lidí. Tak je
   označí i zpráva."
3. **Research-question tiles VO1…VOn**, one per research question:
   - the id, its wording, and a status glyph;
   - the measures that answer it, with their combined support ("Q1, Q2 a sada S1 · podložené");
   - a partial answer ("S1 podle věku · bez srovnání segmentů");
   - or "běh to neměřil · mezera ze spuštění", linking to Analýza.
4. **Three KPI tiles:** Podložená čísla 18 · Orientační 3 ("málo lidí, jen naznačují") · Skrytá 1
   ("příliš málo dat, číslo neukazujeme").
5. **Section "Celkové hodnocení značek"** (one per rated set), with a segment "Podle průměru | Podle
   dotazníku":
   - a lead sentence: "Škála 1–10. Nejvýše: …; pořadí mezi nimi nelze potvrdit, intervaly se
     překrývají.";
   - a table: Značka · Průměr · "95% interval na škále 1–10" (a bar with a mean marker plus "lo–hi")
     · **Efektivní n** (tooltip "Kolika lidem odpovídá vážený vzorek");
   - a hidden row: "—", plus "Skryto: odpovědělo jen 18 lidí, kteří značku znají", with its n shown;
   - a row the Lead's "Ukázat" points at is highlighted.
6. **Section "Otázky"**, with a filter segment Vše | Podložené | Orientační | Skryté: question cards,
   each with id, wording, support pill (Podložené / Orientační neutral / Skryté), a reading in words,
   and "efektivní n {n}". Q9 notes a filtered base ("ptali jsme se jen těch, kdo …").
7. **`<details>` "Technické údaje"** (metody, identifikátory, původ dat): aggregation method, sociomap
   method, run id, artifact id and SHA-256.
8. **Lead pane:** a reply reading stored results, with view buttons "Ukázat: Zlatá Hora 12°" / "Ukázat:
   Pilsner Urquell" that highlight the row, and follow-ups ("Jak to vypadá podle věku?", "Kde leží na
   mapě?"). The "+" action is "Zeptej se na klientské znalosti" ("odpověď se zdroji · do 0,20 USD").

### 4.2 Today on develop

- `ResultsStep` → `RunResults` (`R/ExecutionSteps.tsx:1607-1722`) → `ResultsWorkspace`
  (`R/ResultsWorkspace.tsx:24-137`). Notices come first: RevisionMoved (RES4a), OriginBanners,
  RespondentsReceipt (`R/ExecutionSteps.tsx:1682`).
- The `CompleteReport` lead card shows on overview and report only (`R/ResultsWorkspace.tsx:89`).
- A run card follows: "Výsledky studie", its own heading, a link to Průběh, state, revision, Utraceno
  (`spentWords`, `:13-19,100`), the methodology names with IDs (`:101-106`), the 18.6.6 deviation note
  (`:108-112`), and a run-id `<details>` (`:113`).
- **A tablist** follows: Přehled · Data · Sociomapy · AI analýza · Rešerše a zpráva (`:115-122`), with a
  "Co chcete prozkoumat?" overview (`:123-131`). The workbench maps the hash to stages
  (`lib/workbench-stages.ts:56-61`) but still renders this tablist.
- **Data** (`AggregateView`, `R/ExecutionSteps.tsx:2122-2224`):
  - an optional Deviation;
  - "Nejdřív posuďte sílu podkladů" with the planned n and three support counts (`:2164-2173`);
  - "Srovnání hodnocených objektů": per set, `ObjectComparison` (`:2067-2120`), always ranked by mean,
    columns Objekt / Průměr / Interval / bar / **Kish n** (`:2101`). A withheld row reads "Potlačeno ·
    podpora dat nestačí ({donors} unikátních dárců)" (`:2108-2110`). Rows carry `data-object`, **not**
    `data-aia`.
  - search "Najít otázku nebo objekt" plus a `<select>` support filter (`:2179-2190`);
  - measure cards in questionnaire order, each with title, a support chip, reading, support note, open
    answers, and a details block "Odpovědi, intervaly a původ otázky" that shows **"ID otázky", "platných
    odpovědí", "unikátních dárců", "efektivní n"** (`:2215`);
  - a "Původ agregace" details block (`:2220`).
- Support words: "Podložené v rámci běhu" / "Orientační" / "Potlačené" (`supportLabel`, `:2016-2020`).
  The filter says "Podložené" (`:2186`).
- The VO tiles exist only on Analýza (`lib/analysis-coverage.ts:68`, `AnalysisCoverage.tsx`) and the
  Run stage. Results has none.
- Two different n values: `effective_n_kish` (Kish) and `effective_n` (the support size after the donor
  adjustment, "can be far smaller", `lib/result-reading.ts:105-107`). The prototype has one "Efektivní n".

### 4.3 Build chunks

| # | Change | Backed by | Plan | Proving test |
|---|---|---|---|---|
| V1 | **No inner tabs in the workbench.** When `useLeadOwnsAiStarts()` (the workbench) applies, `ResultsWorkspace` renders only the panel the stage's hash names: no tablist, no overview, no "Výsledky studie" card. The classic layout keeps its tabs until the workbench is the only layout. The run card's state, revision and spend move out: state to the header pill, spend to Průběh only (the prototype: "náklady jen v Průběhu"). | Web only. | artifact-results (new; sits with `research-lead-workbench` stage routing) | `ResultsWorkspace.test.tsx`: in the workbench with hash `#data`, no `role=tablist` and no "Co chcete prozkoumat?"; in classic, unchanged. |
| V2 | **Header:** pill "Běh z {date} · revize {n}" (`run.created_at`, `design_revision`); `RevisionMoved` collapses to the caption link "návrh je teď v revizi {m} →" (`revisionNote`, `lib/result-reading.ts:177`); forward "Sociomapa ›" via FrameNavigation (`R/../step.tsx`). | Backed: run, `GET …/research/revisions`. | RES4a follow-up | `ExecutionSteps.test.tsx`: with study revisions [7, 8] and run revision 7, the caption link shows with its href to Návrh; with [7], none. |
| V3 | **"Modelováno" note:** one origin note from `runOriginKinds` / `originKind` (`lib/research-execution.ts:190-238`) and `RespondentsReceipt`, in one sentence. It says "fiktivní" for SIMULATED, the modelled sentence for MODELLED, and unknown for UNKNOWN (never modelled). The full receipt stays under Technické údaje. | Backed: `step.data_origin_kind`, `run.persona_source`, `run.population`. | FLD7 / RES4b | `ExecutionSteps.test.tsx`: a MODELLED run shows "Modelováno" with N from the dataset step; a fictional run never shows "Modelováno". |
| V4 | **VO tiles:** for each research question of the run's frozen design, list the measures that declare it (`research_questions` on the compiled questions and batteries, `domain/research_design.py:307-310,373`), the support of those measures from the aggregate, and the gap the run recorded at start (`run.answerability.gaps`, `apps/web/src/lib/api.ts:1152-1179`). States: podložené (any REPORTABLE) / orientační (only INDICATIVE) / skryté (only SUPPRESS) / "běh to neměřil · mezera ze spuštění" (a recorded gap or no measures) / unknown (no links declared, never a gap: CLAUDE.md's `coverageOf` rule). Tiles link to the first measure (`#measure-…`) or to Analýza. The comparison words ("bez srovnání segmentů") come from the design's `research_question_comparisons`. Put the pure part in `lib/result-coverage.ts`, reusing `research/trace.ts linkKey`. | Backed by a client-side join of the compile artifact, aggregate and run. The research-question **list** of the frozen design: it is a **hypothesis** that the compiled specification carries the RQ texts; `analysis-coverage` takes `questions` from its caller. Verify before building; if absent, read the run's Design Revision (`GET …/research/revisions`). | new (artifact-results; pairs with ANL2) | `result-coverage.test.ts`: an RQ with one REPORTABLE measure is podložené; a recorded gap reads "neměřil"; an RQ no item links to reads unknown, not a gap. |
| V5 | **KPI tiles** Podložená / Orientační / Skrytá from the existing counts (`R/ExecutionSteps.tsx:2147-2151,2170-2172`), with the prototype's captions. One support vocabulary everywhere: change `supportLabel` "Podložené v rámci běhu" to "Podložené", and "Potlačené" to "Skryté" (`:2016-2020`), plus the filter labels. | Backed: the aggregate's `support`. | RES3 | `ExecutionSteps.test.tsx`: the tile counts equal the per-measure support counts; no text "Podložené v rámci běhu". |
| V6 | **Rated-set table as V2 draws it:** a section per set titled by the set; a sort segment "Podle průměru | Podle dotazníku" (`inOrder` with the spec objects, `lib/research-execution.ts:384`); the lead sentence from `compareObjects` top / bottom (`lib/result-reading.ts:131`); columns Objekt · Průměr · "95% interval na škále a–b" (bar plus "lo–hi") · **Efektivní n** = `kishN` (Kish, `result-reading.ts:136`), "—" when not stored. A withheld row keeps its n and says why in words: "Skryto: {reason}", using the stored respondents count. The prototype's "lidí, kteří značku znají" needs the familiarity base, which is not on the object result (**hypothesis**: only `donors` / `kishN` are). Each row gets `data-aia={measureTarget(set, object)}` (`result-reading.ts:207`) so the Lead's "Ukázat" highlights the row, and the card keeps a `#measure-` anchor without the duplicate `data-aia` (one element per target, ANL1 rule). | Backed for mean, interval, Kish n, suppression. The familiarity base is a hypothesis / gap G6. | RES3 | `ExecutionSteps.test.tsx`: toggling the sort reorders the rows to spec order; a suppressed row shows no number and shows "Skryto"; the Lead target `measure:S1/zh` is on exactly one element, the row. |
| V7 | **Otázky:** the filter becomes a 4-way segment (Vše / Podložené / Orientační / Skryté) and the search is dropped (the prototype has none; keep it only if more than 30 measures). Each card shows its wording, a support pill (Orientační neutral, R10), the `readMeasure` reading, and "efektivní n {kishN}". The details block shows the answer table only. Its "ID otázky / platných odpovědí / unikátních dárců / efektivní n" line (`:2215`) moves to Technické údaje. A filtered base is said in words when the question has a display condition (`SpecQuestion.condition`). | Backed: aggregate plus spec. Effective n is G5. | RES3 | `ExecutionSteps.test.tsx`: the "Skryté" filter shows only SUPPRESS measures; a card's visible text has no "dárců" and no "ID otázky". |
| V8 | **Technické údaje:** one `<details>` at the end holding the methodology names and stored-or-code markers (from the run card `:101-106`), the response-process deviation note, run id, design revision id, the aggregate artifact id and SHA (`Provenance`, `:1531`), and the measure-level n's. | Backed: `run.methodology`, artifact. | RES4b | `ExecutionSteps.test.tsx`: the run id and SHA appear only inside the closed details. |
| V9 | **Admitted rows from the server.** The page today reads the raw aggregate artifact (`useArtifact(run, "aggregate")`, `:1625`). | **NO BACKEND:** RES2 (results read admitted rows; suppression decided on the server). | artifact-results **RES2** | `test_research_api`: the results route returns no number for a SUPPRESS measure. |
| V10 | **Lead "Zeptej se na klientské znalosti"** moves from the stage body (`knowledgeContext`, `:1676-1680`) to the Lead's "+" menu, with its price ("do 0,20 USD"). The price is **NO BACKEND**: no quote route for `answer_memory` was found (**hypothesis**: unverified beyond `routers/research.py`). | Partly backed: `askAssistance("answer_memory")`. | artifact-results **RES6** | `ExecutionSteps.test.tsx`: in the workbench, no "Zeptat se na klientské znalosti" button in the stage body. |

---

## 5. Backend gaps (anchored)

- **G1. No count of replayed respondents.** `fieldwork_progress` counts replayed **blocks**
  (`fieldwork_events.py:60`; `ai_fieldwork.py:488-491`). The disc's hollow dots need
  `replayed_respondents`: respondents of this attempt none of whose blocks were sent. Fix: count a
  respondent whose `sent` did not move across its blocks, and add the key under
  `aia-fieldwork-events-3`, with the web fixture `contract.json` updated in step. Test:
  `test_ai_fieldwork_answer_plans.py`: a replayed attempt reports `replayed_respondents == respondents`.
- **G2. The budget need is stored but not served.** `requested_usd` / `remaining_usd` / `budget_usd` are
  in the attempt error (`worker.py:389-398`). `_step` drops them (`routers/research.py:1124-1126`), and
  `STEP_RECOVERY`'s payload omits them (`workflow_repository.py:2043-2058`). Fix: serve
  `budget_need {requested_usd, remaining_usd}` on a step in `AWAITING_BUDGET`. Test: an API test on a
  parked step.
- **G3. Cadence facts are not in the feed.** `progress_every` (`ai_fieldwork.py:159`) and whether the
  heartbeat / checkpoint switches were on for the attempt (`:169-183`) are worker config, invisible to
  the web. The disc's "next ≤10" batch, the truth note's "po 10 / nejpozději po 30 s", and "nic se
  neztratilo" (checkpoint) all depend on them. Fix: `fieldwork_sample` (or a first `fieldwork_progress`)
  carries `{every, heartbeat, checkpoint}`, written once per attempt. Test:
  `test_fieldwork_events.py`: the payload keys include them.
- **G4. Raw codes in the feed's words.** `describe()` prints `reason(event.message)`, so a budget park
  reads "Krok se zotavuje: budget_exceeded" (`apps/web/src/lib/step-activity.ts:46,96-97`).
  STEP_RESUMED is dropped (`:102-103`). Web-only fix: P5.
- **G5. Which "Efektivní n".** The aggregate stores both `effective_n_kish` and `effective_n` (support
  after the donor adjustment), and support is decided on the latter (`lib/result-reading.ts:105-107`).
  Showing one number named "Efektivní n" needs the methodology owner to choose. The proposal is Kish,
  matching the prototype's tooltip, with the support n under Technické údaje. Not a code gap; a
  decision.
- **G6. The familiarity base for a hidden object** ("odpovědělo jen 18 lidí, kteří značku znají") is not
  known to be on the object result. **Hypothesis**: only `donors` and `effective_n_kish` are read today
  (`R/ExecutionSteps.tsx:2108-2111`).
- **G7. Fictional fieldwork writes no progress** (`research.py:580-584`), so the disc cannot be shown
  live on the workbench. Fix: the synthetic source reports `progress(respondents, of, sent=0, replayed=0)`
  every 10, which makes the D6 journey possible without a recorded panel run.
- **G8. RES2** (V9): there is no server-side admitted-rows read for Results.
- **Steps the prototype invents:** "Zpráva ve formátu PDF" and "Kontrola zprávy" are not workflow steps
  (`workflow_templates.py:113-119,225-259`). Do not build them. The PDF stays inside `report`.

## 6. Missing layout primitives (no tokens)

- **Segmented control** (`seg`): a 2–4 option tab, radio or pressed group with roving focus. `ChoiceChips`
  (`components/ui/ChoiceChips.tsx`) is the nearest. Used by Pohled, Kdo odpovídá, sort, and filter.
- **KPI tile row** (`kpis`): label, value and caption, wrapping at narrow widths. Nothing like it exists
  in `R/../ui.tsx` (exports at `:33-271`).
- **Two-column fact list** (`dl.facts`, label column plus value) that stacks below `@sm`. `SpendCard` has
  an ad-hoc one (`R/ExecutionSteps.tsx:1352-1357`).
- **Disc plus legend** two-column layout (`.fwd`: a fixed 320 px canvas and a flexible legend) that stacks
  at 390 px.
- **Collapsible section** whose summary carries a count caption (`details.sec`).
- **Table interval bar** (a mean marker on a range bar) as a shared cell. Today it is inline in
  `ObjectComparison` (`:2097-2100`).
