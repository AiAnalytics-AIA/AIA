# Build spec · Návrh výzkumu: Zadání, Návrh, Dotazník

Source: the approved boards `canvas/project/Brief.dc.html`, `Design.dc.html` and `Questionnaire.dc.html`
(the `renderVals()` data and the `crit` lists), and decisions R7, R8 and R9 in `Main.dc.html`.
Every code anchor is `path:line @ bd0d1ad6`. Paths are relative to the repository root.
`R/` is `apps/web/src/components/rehome/research/`. An unverified claim is labelled
**hypothesis**. Visual tokens are out of scope here. Where the boards need a component or layout
primitive that does not exist, this spec says so.

---

## 0. Shared to all three stages

### 0.1 Primitives the boards need that do not exist

| Primitive | Board use | Today |
|---|---|---|
| **Numbered section sheet** (`.sec` > `.sh`: `num` "01"/"B1"/"S1", `h2`, grow, right cap "povinné / volitelné / 3 otázky") | every section of all three stages | `StepSection` takes `n`, but does not render it: `n` is in the props type and missing from the destructure (`apps/web/src/components/rehome/step.tsx:24-38`). Its "optional" is a suffix to the title (`step.tsx:51`), not a right-hand cap. |
| **"Needs you" section state** (`.sec.need`: coral inset edge, plus a "chybí" pill in the header) | Zadání 03 when the decision is empty | none |
| **Well item** (`.li`: one row in a section, a tone below the sheet, no border; mono id at left, actions at right) | objectives, research questions, hypotheses, materials, comments, the S1 statement | ad-hoc rows per screen (`R/BriefStep.tsx:303`, `R/PlanStep.tsx:740`, `R/PlanNarrative.tsx:106`) |
| **Stage header action slot** (`.ahd`: h1, Uloženo, grow, stage cap or counts, stage actions, primary "next stage ›") | all three stages | The workbench header has a fixed set of actions: the inspector toggle and focus mode (`apps/web/src/components/workbench/Workbench.tsx:822-835`). The way on is each stage's bottom `ActionDock` (`apps/web/src/components/rehome/step.tsx:80`). Nothing lets a stage put an action or a cap in the header. |
| **Readiness chip row** under the header (`nav.row` "Připravenost", one chip per section, in page order, each a link to its section) | Zadání | Zadání draws a panel with a percentage in the inspector instead (`R/BriefStep.tsx:140-178`, `354-403`). |
| **Per-item proposal block with checkboxes** (`.edits` > `.chg` with a checkbox, where, text, why, kind tag; "Odložit", "Přijmout vybrané (n)") | Dotazník | The pattern exists only in `R/DesignResearchReview.tsx:125-140` (Design Research items). `ProposalReview` is whole-proposal (`R/ProposalReview.tsx:183-190`). |
| **Decided edit row** (Přijato / Zahozeno pill and "Vrátit" kept in the edits bar after a decision) | Návrh | `EditsBar` lists open edits only, and a decided one leaves the bar (`apps/web/src/components/workbench/Workbench.tsx:879-910`). |

Existing primitives to reuse: `InlineText`, `InlineCreateRow`, `ChoiceChips`, `Switch`, `MenuButton`,
`UndoToast`/`useUndo` (`apps/web/src/components/ui/`), `Segmented` (`apps/web/src/components/rehome/step.tsx:157`),
the workbench `EditsBar`, and `LeadCards`.

### 0.2 Chunk X1 (new): the header slot and the section sheet

- **What changes.**
  - `Workbench.tsx` takes a stage-provided header node through context. The pattern is the same as
    `FrameNavigation`: a `StageHeader` context provided around `children` (`Workbench.tsx:851`).
    The node renders between `{save}` and the inspector toggle.
  - `StepSection` renders `n` as a mono number. It also takes `cap` (right-hand text), `need` (the
    coral state plus a "chybí" pill), and a `num` override for the "B1" and "S1" labels.
  - A `WellItem` primitive goes in `rehome/ui.tsx`.
- **Backend:** none needed (display only).
- **Plan id:** new. It serves `artifact-brief#BRF2`, `artifact-design#DSN3` and `artifact-questionnaire#QST2`.
- **Tests (vitest):**
  - `step.test.tsx` › "StepSection prints its number and cap, and the need state names what is missing";
  - `Workbench.test.tsx` › "a stage's header actions render in the artifact header and remount nothing across 1100 px".

### 0.3 Cross-stage decisions on these stages

- **R7: one tracked set for Návrh and Dotazník.**
  - Today there are two copies.
    - Návrh edits `analysis.tracked_sets` (`apps/web/src/research/plan.ts:43`, `93`).
    - Dotazník edits `sections[]` entries with `metadata.tracked_set` (`apps/web/src/research/questionnaire.ts:517-532`).
    - Only the sections compile (`packages/aia_core/src/aia_core/domain/research_design.py:1172`).
    - `analysis.tracked_sets` is only the input to `build_questionnaire`.
    - Nothing syncs them afterwards. The labels also differ ("Položky" vs "Objekty", critique d).
  - Shape:
    - Before a questionnaire exists, Návrh edits the plan's set, as today.
    - Once a set section exists, Návrh's section 04 reads and writes **that section**, by its
      section id. It goes through the same `questionnaire.ts` writers Dotazník uses (`setSectionField`,
      the scale writers) and the same `object_ids` (`packages/aia_core/src/aia_core/domain/item_ids.py:82-84`).
    - Both stages show "S1 · sdílená s Návrhem / Stejná sada je v Dotazníku jako S1".
  - Needs `working-copy-edit-ops#WCE8b`, so that `build_questionnaire` and `optimize_questionnaire`
    keep a baseline set under its id. Today `proposal_result` gives every proposed section a fresh
    `ai_*` id (`.planning/plans/working-copy-edit-ops.md:267`).
  - Also needs `set_edit`, which is only DECLARED today (`packages/aia_core/src/aia_core/domain/edit_ops.py:845`, chunk WCE3a), so the Lead cannot edit a set yet.
  - **Owner question.** The boards disagree on the set's scale range. Návrh 04 offers presets
    1–5/1–7/0–10/1–10. Dotazník S1 shows "Škála 1–10" fixed, and today's ScaleEditor fixes a set's
    range (`R/QuestionnaireStep.tsx:1216-1222`, `rangeFixed`). The compiler takes any valid range
    (`research_design.py:1065`). Whether the Sociomap needs 1–10 for a set is a **hypothesis**
    (`coerce_declared_1_10`, F5, CLAUDE.md map).
- **R8: AI questionnaire proposal accepted item by item; "Odložit" instead of "Ponechat / Zahodit".**
  - Today:
    - the decision is one for the whole proposal (`R/ProposalReview.tsx:7-9`, `183-190`);
    - accepting replaces own blocks (`R/ProposalReview.tsx:64-65`);
    - the accept body carries no item selection (`apps/api/src/aia_api/routers/research.py:3719-3725`);
    - the application passes the job's recorded `touched` whole (`packages/aia_core/src/aia_core/application/research.py:2069`).
  - `accept_into_working_copy` already takes `touched` (`packages/aia_core/src/aia_core/application/proposal_accept.py:113-124`),
    and Design Research already accepts by `item_ids` (`apps/api/src/aia_api/routers/deep_research.py:266-275`).
  - The plan of record is `working-copy-edit-ops#WCE6` (per-change accept, `proposal_change_decisions`)
    plus `#WCE8b` (stable ids, so a reworded item is one change), landing in `artifact-questionnaire#QST5`.
  - Per-change "why" text has **NO BACKEND**: `QuestionnaireProposal` has one `message` and no
    per-section rationale (`packages/aia_core/src/aia_core/domain/research_agents.py:158-162`).
- **R9: what a run cannot do is shown disabled, with the reason.** Two features here:
  - **Display condition (Q2).**
    - With `AIA_ROUTING_ENABLED` off (develop: unset), `QuestionCondition` draws nothing for a
      question without a condition (`R/QuestionCondition.tsx:72-75`).
    - The board wants the condition line, its reason ("Běh s podmínkou zatím neumí AIA odeslat…")
      and a disabled "Zapnout".
    - Backed by `/config`'s `routing` (`apps/web/src/lib/public-config.ts:45`).
  - **Familiarity on a set (S1).**
    - Today a switch turns it on (`R/QuestionnaireStep.tsx:1225-1226`), and readiness then FAILs
      `battery_familiarity` (`research_design.py:1497-1503`).
    - The board removes the switch and shows a note. A set stored with
      `familiarity_required: true` still says so, with a way to switch it off.

### 0.4 The Lead's contract for these stages

The contract is `packages/aia_core/src/aia_core/domain/lead_artifacts.py:240-296`, mirrored in
`apps/web/src/lib/workbench-artifacts.ts:56-83`. The live view ops are open_stage, focus, inspect and
show_diff (`lead_artifacts.py:82-83`). Typed commands are listed in
`packages/aia_core/tests/fixtures/lead_commands/commands.json:3-13`.

| Board shows | Stage | Contract has it? |
|---|---|---|
| Reply view "Ukázat: Rozhodnutí" / "Ukázat: Podklady" (focus) | Zadání | Yes. `focus` plus target `brief:decision_use` / `brief:files` (`apps/web/src/lib/artifacts/brief.ts:23-35`). The coral highlight of the empty field is new display (0.1). |
| "Analyzuj zadání" card (Teď ne / Spustit úlohu, ceiling 0,40 USD, then "Posoudit na Návrhu") | Zadání | Yes. Start `agent_job:analyze_brief` (`lead_artifacts.py:246`) and the typed command (`commands.json:4`). |
| Header "Požádat Vedoucího o analýzu" inserts the command | Zadání | Backed. `LeadAskContext` sends text as typed (`R/AskLead.tsx:22-23`), and the exact phrase is stored as a command, with no model turn (CLAUDE.md, `domain/lead_commands.py`). |
| "+ › Zeptej se na klientské znalosti" | Zadání | Yes. `agent_job:answer_memory` (`lead_artifacts.py:235`, `commands.json:11`). |
| "+ › Hledat na webu · připravujeme" (disabled) | all | Not built: `lead-orchestration#LO20`. The disabled state is correct. |
| Edits bar: H2 `list_replace` of a hypothesis, VO3 `list_replace` of a research question, "Přijmout vše / Zahodit vše" | Návrh | Yes. `list_replace` is applied (`packages/aia_core/src/aia_core/domain/edit_ops.py:811`), and `EditsBar` has accept-all and dismiss-all (`Workbench.tsx:891-892`). Board extras with no backend: "Vrátit" after an accept or a dismiss (WCE9), and re-opening a dismissed edit (the ledger decision is final). |
| Reply view "Změny: Návrh" | Návrh | `show_diff` is live (`lead_artifacts.py:256`). |
| Plan card "Od návrhu ke sběru dat" (4 steps, one approval, stops at the questionnaire gate) | Návrh | **NO BACKEND**: `lead-orchestration#LO3`, `#LO4`, `#LO21e` are open. The board labels it "backend zatím nemá (LO4)". |
| Lead names a set (`set:<id>`) | Návrh | Yes in the contract (`workbench-artifacts.ts:67`). The set card has no `data-aia` (`R/PlanStep.tsx:526`), so it cannot be pointed at. |
| "Úprava dotazníku" job card, done, "3 změny · Stálo 0,38 USD · Posoudit" | Dotazník | Yes. `agent_job:optimize_questionnaire` (`lead_artifacts.py:284`) and `workerCard` (`apps/web/src/lib/lead-cards.ts:82-108`). The change count on the card is new (from `proposal-diff`). |
| "Rešerše k návrhu" card (Spustit rešerši, 1,20 USD) | Dotazník | In the contract (`lead_artifacts.py:286`), but **NO BACKEND to start it from a card**: `approve_request` accepts only `agent_job` requests and raises `NotAPaidRequest` otherwise (`packages/aia_core/src/aia_core/application/research_lead.py:1094-1096`, `1140`). No typed command exists: "Spusť rešerši k návrhu" is a listed non-match (`commands.json:31`). Plans: `lead-orchestration#LO5a.2`, `#LO5a.3`. |
| Questionnaire edits: S1 new statement, Q3 scale change, Q14 removed | Dotazník | Via the agent proposal (R8). As Lead edits: `question_remove` is applied (`edit_ops.py:819`). `set_edit` (`:845`) and `scale_set` (`:837`) are DECLARED only (WCE3a/WCE3b). |
| Contract target kinds `option`, `set` on Dotazník | Dotazník | Not in the row (`lead_artifacts.py:281` has section and question). `artifact-questionnaire#QST1` adds them. |

**Plan conflict to resolve.** R12 and the board put Design Research as a Lead card while on Dotazník.
`artifact-questionnaire#QST6` and `artifact-design#DSN5` say the panel *moves to Návrh*. The board
does not say on which stage the card lives, so the plans need one line: the card is shown wherever
the person asks; its proposal is reviewed on Dotazník (S1 statements).

---

## 1. Zadání (Brief)

### 1.1 What the prototype shows (artifact pane, in order)

1. **Header.** "Zadání", "Uloženo", and an AI button "Požádat Vedoucího o analýzu" that inserts the
   command and prepares the "Analýza zadání" card. Then the primary "Návrh ›".
2. **Readiness chip row "Připravenost".** Six chips in page order: Cíl, Cíle, Rozhodnutí, Typ problému,
   Kontext (volitelné), Podklady (volitelné).
   - Done is green, missing-required is coral, optional is inert. There is no percentage.
   - Each chip jumps to its section.
3. **01 "Co potřebujete zjistit?"** (povinné).
   - Textarea "Cíl vlastními slovy · 1–3 věty".
   - Input "Název studie" (plain; no "Navrhnout z cíle").
4. **02 "Cíle"** (povinné · kliknutím upravíte · Návrh je čte odsud).
   - A numbered list, 01, 02, 03. Each item is click-to-edit in place, shows "→ VO1" (the research
     question it leads to), and has a trash button.
   - Below: "Přidat cíl…" plus "Přidat".
   - Removing an item gives the toast "Cíl odebrán." with "Vrátit" (5 s).
5. **03 "Rozhodnutí, které má výzkum podpořit"** (povinné).
   - Textarea "Mezi čím budete podle výsledku volit".
   - When empty: coral section, a "chybí" pill, and "Začít od" chips (Volba kampaně, Cena, Portfolio)
     that fill an example sentence.
   - A note under it changes with state: "Návrh i analýza budou mířit k tomuto rozhodnutí." /
     "Prázdné. Bez rozhodnutí navrhne Vedoucí jen obecné otázky."
6. **04 "O jaký typ problému jde?"** (povinné · více možností). Toggle chips, more than one at a time.
7. **05 "Kontext"** (volitelné). A two-column grid: "Trh a situace" and "Co už víme".
8. **06 "Podklady"** (volitelné).
   - Rows: an icon, the name, then a class sentence ("Důvěrné klienta: smí jen k modelu v EU. Vedoucí
     z něj cituje jen to, co přijmete." or "Veřejný odkaz.") and a class pill (Důvěrné / Veřejné).
   - One button: "Přidat soubor nebo odkaz".

Lead pane (for context only):
- a greeting that names the missing decision, with the view button "Ukázat: Rozhodnutí";
- follow-ups "Analyzuj zadání" and "Co ještě chybí?";
- the "Analýza zadání" card. Its states are ask, running, done ("Posoudit na Návrhu") and kept
  ("Nic se nespustilo ani nezaplatilo.").

### 1.2 Today on develop

Rendered by `BriefStep` (`R/BriefStep.tsx:94-274`).

- **Order and sections.**
  - The goal is section 1 (`:182-220`).
  - Objectives are 2 (`:281-340`), already in place with undo and `objective:<id>` marks (`:303`).
  - Decision is 3 (`:409-422`).
  - Context is 4, with **four** fields: product_description, situation, what_is_known, constraints (`:65-70`, `:429-451`).
  - Types are **5** (`:228-256`) and files are 6 (`:556-726`).
  - The board swaps types and context (04 types, 05 context).
- **Goal.**
  - The title asks "Co potřebujete zjistit a rozhodnout?" and the hint asks for the decision again
    (`apps/web/src/i18n/cs.ts:2300-2301`). The board asks only "Co potřebujete zjistit?".
  - Sentence starters are on the goal and append to existing text (`R/BriefStep.tsx:190-204`). The
    board moves its starters to the decision.
  - "Navrhnout z cíle" (`:216-218`) is dropped on the board.
- **Readiness.**
  - Today it is an inspector panel with a percentage (`:140-178`). It scores goal ≥ 40 characters,
    types, files and context, each 25 % (`:122-124`, `:62`).
  - It omits objectives and decision, and it counts `decision_use` into "Kontext" (`:122`).
  - The workbench variant shows "Pokračovat na Návrh" even for an unfinished brief, plus the AskLead
    text (`:162-175`), and no AI button.
- **Decision.** No empty-state starters, no need state (`:409-422`).
- **Types.**
  - Ten `PROBLEM_TYPES` from 18.6.6 (`apps/web/src/research/model.ts:127-138`). Toggling one fills an
    empty goal with that type's default (`R/BriefStep.tsx:248-253`).
  - The board shows six other labels (Image značky, Srovnání konkurence, …). **Owner question:** the
    board's labels look illustrative. Keep `PROBLEM_TYPES` (parity-tested) unless the owner wants the
    taxonomy changed.
- **Podklady.**
  - Today: a drop zone, a file button, a link input (`:618-657`), rows with download and remove plus
    undo (`:687-705`), and a class chip `classLabel` such as "A · důvěrné…" (`:678-686`,
    `apps/web/src/lib/material-class.ts:25-27`).
  - The leaks the critique names: the aside "třída dat určuje, kam smí" and the tooltip "rule:design …
    operátor" (`cs.ts:2356-2357`).
  - The server classes a brief file **and** a link as Class B, `rule:design`
    (`packages/aia_core/src/aia_core/domain/brief_material_classes.py:55-69`). So the board's
    "Důvěrné" (A) for the xlsx and "Veřejné" for the link do not match the server (see 1.4).
- **Requiredness.** The only server-side gate on analysing is a goal or product description
  (`apps/web/src/research/brief.ts:133-135`). "povinné" on objectives, decision and type is a new
  UI rule; nothing refuses without them.

### 1.3 Build chunks

**B1. Section order, numbers and caps.**
- What changes in `R/BriefStep.tsx`:
  - reorder to goal, objectives, decision, **type, context**, files;
  - pass `n` and `cap` (povinné / volitelné / "povinné · kliknutím upravíte · Návrh je čte odsud")
    through X1's `StepSection`;
  - goal title and hint become "Co potřebujete zjistit?" / "Cíl vlastními slovy · 1–3 věty" (`cs.ts:2300-2301`);
  - the title is a plain field; remove "Navrhnout z cíle" and `titleFromGoal` (`:80-90`, `:216-218`).
- Backend: none (working content, `PUT …/workspace/content`).
- Plan: `artifact-brief#BRF2`.
- Test: `BriefStep.test.tsx` › "sections render in the board's order with their numbers and caps".

**B2. Readiness chip row.**
- What changes:
  - replace `Readiness` (`:140-178`, `:354-403`) with the chip row under the header, one chip per
    section in page order;
  - required states: goal non-empty, objectives ≥ 1, decision non-empty, ≥ 1 type;
  - optional chips are never coral;
  - drop the percentage and `GOAL_SENTENCE`;
  - put the pure rule in `research/brief-readiness.ts`.
- Backend: none (client rule over the working copy). **Owner check:** "povinné" adds requirements that
  `canAnalyse` (`brief.ts:133`) does not enforce. The proposal is advisory: a coral chip, not a block.
- Plan: `artifact-brief#BRF2`.
- Test:
  - `brief-readiness.test.ts` › "a chip per section in page order; optional never coral; no percentage";
  - `BriefStep.test.tsx` › "a chip moves focus to its section".

**B3. Decision with its need state and starters.**
- What changes:
  - `Decision` (`:409-422`) gets X1's `need`, the "chybí" pill, the "Začít od" chips (three example
    sentences, written into an empty field only), and the state note;
  - remove the goal's starters (`:190-204`).
- Backend: none (`decision_use`).
- Plan: `artifact-brief#BRF2`.
- Test: `BriefStep.test.tsx` › "an empty decision shows chybí and starters; a starter fills it and the chip turns green".

**B4. Objectives: "→ VO n" link.**
- What changes: each objective shows the research question(s) it leads to.
- **NO BACKEND.** No objective-to-research-question link exists. The plan lists carry only id
  sidecars (`packages/aia_core/src/aia_core/domain/item_ids.py:76-80`), and research questions carry
  no `objective_ids`.
- Needs:
  - a link field on `research_plan.research_questions` (by `objective_ids`), an edit op to set it
    (`edit_ops`), and `analyze_brief` proposing it;
  - until then, show nothing. **Never** pair by position.
- Plan: new (`artifact-design`, a chunk beside DSN3).
- Test: `brief-objectives.test.ts` › "an objective with no linked research question shows no link".

**B5. Context grid.**
- What changes: `Context` (`:429-451`) as a two-column grid of fields.
- Backend: none.
- **Owner question:** the board shows two fields (situation, what_is_known). Today there are four, and
  `product_description` gates analysis (`brief.ts:134`). Keep all four in the grid unless the owner
  drops two.
- Plan: `artifact-brief#BRF2`.
- Test: `BriefStep.test.tsx` › "context fields render in a grid and save on blur".

**B6. Podklady rows with their class in words.**
- What changes:
  - rows as X1 well items (icon, name, class sentence, pill);
  - one "Přidat soubor nebo odkaz" button opening the existing picker and link field (a `MenuButton`
    with two items); the drop on the stage stays (`:133-139`);
  - keep download and remove plus undo as row actions (the board does not show them, but there is no
    reason to lose them);
  - the copy comes from the server's class (`classOf`, `material-class.ts:40-51`), never guessed;
  - drop "rule:" and "operátor" from the copy (`cs.ts:2356-2357`).
- Backend: `GET /studies/{id}/workspace/materials` (`apps/api/src/aia_api/routers/workspace.py:2123`).
  Gaps are in 1.4.
- Plan: `artifact-brief#BRF3`.
- Test: `BriefStep.test.tsx` › "a material's pill and sentence follow the server's class; an unanswered class says neznámá".

**B7. Header actions and the Lead's analysis.**
- What changes:
  - in the X1 header slot: "Požádat Vedoucího o analýzu" sends `Analyzuj zadání` through
    `useAskLead()` (`R/AskLead.tsx:23`);
  - add "Návrh ›" via `FrameNavigation`;
  - remove the inspector-panel "Pokračovat na Návrh" and the AskLead paragraph (`:156-176`);
  - the stage's own `AiButton` stays only outside the workbench (`:156-160`).
- Backend: `POST …/lead/turns` (`apps/api/src/aia_api/routers/lead.py:566`) and the typed command
  (`commands.json:4`), then the card approved through `POST …/lead/turns/{turn_id}/request`
  (`lead.py:719`).
- Plan: `artifact-brief#BRF4`, `research-lead-workbench#26f`.
- Test:
  - `BriefStep.test.tsx` › "in the workbench the header button asks the Lead 'Analyzuj zadání' and the stage starts nothing";
  - `lead_journey.mjs`: the card appears with its ceiling.

**B8. The Lead's focus marks the empty decision.**
- What changes: a `focus` on `brief:decision_use` while it is empty also sets X1's need state.
  `Workbench`'s focus resolves `#brief-decision_use` (`apps/web/src/lib/artifacts/brief.ts:49-51`).
- Backend: focus view op (`lead_artifacts.py:82-83`).
- Plan: `artifact-brief#BRF4`.
- Test: `lead_journey.mjs`: a scripted reply view on Rozhodnutí focuses section 03 at 1440 and 390 px.

### 1.4 Backend gaps (Zadání)

1. **Objective-to-research-question link.** It does not exist (`packages/aia_core/src/aia_core/domain/item_ids.py:76-80`). See B4.
2. **Material class in the board's words.**
   - The server answers Class B `rule:design` for every file and link
     (`packages/aia_core/src/aia_core/domain/brief_material_classes.py:65-69`).
   - The board's "Důvěrné klienta" pill on a brief file, and "Veřejné" on a link, are not what the
     server says.
   - "smí jen k modelu v EU" needs a served answer for where a class may go. No route serves this;
     that it can be read from `residency` is a **hypothesis**.
   - "Vedoucí z něj cituje jen to, co přijmete" is unbacked copy. **Hypothesis.**
   - Fix: print the served class. Ask the owner whether a brief file should rule as A (a change to
     `material_rules.py`, ADR 0008 territory).
3. **Requiredness.** No server rule for objectives, decision or type (`apps/web/src/research/brief.ts:133-135`). This is advisory UI only, unless the owner wants `analyze_brief` gated.

---

## 2. Návrh (Design)

### 2.1 What the prototype shows (artifact pane, in order)

1. **Header.** "Návrh", "Uloženo", the cap "3 cíle · 3 výzkumné otázky · 2 hypotézy · 1 sada", and the
   primary "Dotazník ›".
2. **Edits bar "Vedoucí navrhuje 2 změny · nic se nezmění, dokud je nepřijmete".**
   - Header actions: "Zahodit vše", "Přijmout vše".
   - Per change: where, then Zahodit / Přijmout. Below that, the struck-through before, the after,
     and "Proč: …".
   - After a decision the row stays, with a Přijato / Zahozeno pill and "Vrátit".
   - The title becomes "Návrhy Vedoucího rozhodnuty".
3. **01 "Rozsah".**
   - Segmented control Základní / Rozšířený, with a text per choice ("…Vzorku doporučí N 400").
   - Cap: "Délku dotazníku spočítá Metodika, až bude pravidlo nastavené; do té doby ji AIA neodhaduje."
4. **02 "Výzkumné otázky a co je měří"** (cap: "cíle upravíte na Zadání" with a link).
   - One well per question:
     - id VO1, VO2, VO3 and the text;
     - "k cíli 01 · …";
     - a coverage glyph (green / coral) with "měří Q1, Q2 · zodpověditelné" or "zatím nic neměří";
     - a comparison tag ("Pořadí v sadě", "Popis");
     - optionally a link "Návrh výroků čeká v Dotazníku →";
     - icon buttons Komentovat and Upravit.
5. **03 "Hypotézy".** Wells H1 and H2, each with "ověří S1 · ověřitelná" or, coral, "zatím nic neověří"
   plus a link to the pending statement in Dotazník.
6. **04 "Sada k porovnání: Značky ležáků".**
   - Cap link "Stejná sada je v Dotazníku jako S1".
   - "Objekty · 7" chips plus "Přidat".
   - "Otázka sady · {objekt} se nahradí značkou".
   - Scale segmented 1–5 / 1–7 / 0–10 / 1–10, with "Konce: …".
7. **05 "Co potřebuji ještě vědět"** (ukládá se hned). One labelled input per question.
8. **06 "Komentáře"** (n komentáře).
   - Wells with the text and "k sadě … · Jana Malá", plus trash. A removal gives the toast
     "Komentář smazán." with Vrátit.
   - Note: "Komentář nic nemění. Změnu udělá Vedoucí až na vaši žádost a ukáže ji v liště nahoře."

Lead pane: a reply with "Změny: Návrh" (show_diff); the plan card (R13 / LO4).

### 2.2 Today on develop

Rendered by `PlanStep` (`R/PlanStep.tsx:88-296`).

- **Header.** A tinted header with "workspace" title, hint, a counts `dl` and a manual note (`:224-230`).
  Then `JumpChips` (`:231`, `:298-316`). The way on is the bottom `ActionDock` (`:148-167`). The board
  drops the jump chips and the intro, and puts the counts and the next button in the header.
- **Edits.** `EditsBar` (`Workbench.tsx:879-910`) already matches the board's open state. It lacks
  the decided rows and "Vrátit".
- **Variants.**
  - Radio cards with N=, complexity and trade-off (`:318-371`).
  - Applying a variant **writes `n`** (`apps/web/src/research/plan.ts:160-183`, `171`).
  - The board shows a segmented control, and N is only a recommendation to Vzorek (R3).
- **Coverage.** A separate block (`R/DesignCoverage.tsx:25-60`) above the narrative (`:239`). The board
  puts coverage on each research question's row.
- **Narrative.**
  - `Understanding` hosts `PlanNarrative` (`:375-391`): summary, research questions, **objectives** and
    hypotheses, all edited in place (`R/PlanNarrative.tsx:99-150`; lists at
    `apps/web/src/research/plan-narrative.ts:19`).
  - The board: objectives are not on Návrh ("cíle upravíte na Zadání"); hypotheses are their own
    section; there is no problem-summary row on the board (**owner check**: keep the summary in the
    Rozsah sheet or drop it); research-question text is edited via the "Upravit" pencil.
- **Sets.**
  - `SetCard` (`:495-605`): name, purpose, items ("Položky"), object question, scale **ends only**
    (`:570-577`), example, remove.
  - No `data-aia` (`:526`).
  - No scale presets; the range is fixed by default 1–10 (critique d).
- **Follow-ups.**
  - Answers are held in local state (`:134`) and submitted as one block appended to
    `briefing.what_is_known` (`apps/web/src/research/plan.ts:189-195`). They are lost on leave.
  - In the workbench: "Uložit odpovědi" plus `SavedForLead` (`:256-266`).
- **Comments.**
  - Stored in `ui_state.plan_comments26` as `{quote, comment}`, with no author and no target
    (`plan.ts:197-214`).
  - Removing one has no undo (`R/PlanStep.tsx:748`).
  - "Uložit komentáře" marks `plan_changed26` even with no change (`:276-279`).

### 2.3 Build chunks

**D1. Header: counts and the way on.**
- What changes:
  - move the counts (`:224-230`) to X1's header cap, plus "Dotazník ›" (calls the existing `next`, `:144-148`);
  - remove the tinted intro, `JumpChips` and the workbench dock.
- Backend: none.
- Plan: `artifact-design#DSN3`.
- Test: `PlanStep.test.tsx` › "the header counts objectives, research questions, hypotheses and sets from the working copy".

**D2. Rozsah as a segmented choice that recommends N.**
- What changes:
  - `Variants` (`:318-371`) becomes a `Segmented` over `projectVariants`, with the chosen variant's
    summary and "Vzorku doporučí N n";
  - `applyVariant` stops writing `n` (`plan.ts:171`); the recommendation is shown on Vzorek;
  - add the Metodika length line;
  - the existing confirm before replacing manual changes stays (`:184-189`).
- Backend: none for the choice. N as a recommendation that Vzorek reads has **NO BACKEND field**;
  storing it, e.g. in `research_plan.recommended_n`, is a new working-content key, **hypothesis**:
  needs a decision under R3.
- Plan: new (R3 with `artifact-sample`).
- Test: `plan.test.ts` › "applying a variant leaves project.n unchanged and records the recommendation".

**D3. Research questions with their coverage inline.**
- What changes:
  - a new `ResearchQuestionRows`: one well per research question (`VO n` by position as a label only;
    the id is the item id), the text, a coverage glyph and words from `rqCoverage`
    (`apps/web/src/lib/design-coverage.ts`), and the comparison tag;
  - Upravit opens the `InlineText` used today, through `plan-narrative.setItem`;
  - Komentovat calls `onQuote`;
  - mark each row `rq:<id>` (`R/PlanNarrative.tsx:106`'s `itemTargets`);
  - retire the separate `DesignCoverage` block (`:239`), keeping its loading, failed and behind states
    in the row.
- Backend: `GET …/research/readiness/working?working_revision=n` (`apps/api/src/aia_api/routers/research.py:1386`).
  It carries `research_trace` and the comparisons (`packages/aia_core/src/aia_core/domain/research_trace.py:145`).
- Plan: `artifact-design#DSN2` (re-layout), `#DSN3`.
- Test:
  - `DesignCoverage`'s tests ported: "each research question shows its own coverage; unknown shows no green";
  - `analysis_journey`-style step in `proposal_prompt_journey.mjs`.

**D4. "k cíli" on research questions; objectives off Návrh.**
- What changes:
  - drop `objectives` from Návrh's `NARRATIVE_LISTS` use (`plan-narrative.ts:19`) and link to Zadání;
  - show "k cíli 0n · text" only from a stored link.
- **NO BACKEND:** the same link as B4. Until it exists, the line is absent.
- Plan: new (with B4).
- Test: `PlanStep.test.tsx` › "Návrh shows no objective editor and links to Zadání".

**D5. Hypotheses section with "ověří".**
- What changes: a numbered section of hypothesis wells, edited in place, marked `hypothesis:<id>`.
- The "ověří S1 · ověřitelná / zatím nic neověří" line has **NO BACKEND**:
  - items declare `research_questions` only (`edit_ops.py:835` `link_set`);
  - the trace has no hypotheses (no match for "hypothes" in `research_trace.py`).
  - Needs a hypothesis link on items, or a hypothesis-to-research-question link plus a trace verdict.
- Ship the section without the line until then.
- Plan: new.
- Test: `PlanStep.test.tsx` › "hypotheses render as their own section; no verdict without a server answer".

**D6. One set, shared with Dotazník (R7).**
- What changes:
  - `Sets` and `SetCard` (`:395-605`) read and write the questionnaire's set section once it exists
    (see 0.3);
  - "Objekty" wording;
  - `data-aia="set:<id>"` (`apps/web/src/lib/artifacts/design.ts:30-34`);
  - the scale as presets only if the owner answers the 0.3 question; else "Škála 1–10" read-only.
- Backend: working content only. Depends on `working-copy-edit-ops#WCE8b` for builds to keep the set,
  and on `#WCE3a` (`set_edit`) for Lead edits.
- Plan: new (R7), touching `artifact-design#DSN3` and `artifact-questionnaire#QST2`.
- Test: `PlanStep.test.tsx` › "after a questionnaire exists, renaming an object on Návrh changes the S1 section and Dotazník shows it".

**D7. Follow-up answers save themselves.**
- What changes: each answer is an `InlineText` saved into the working copy per question.
- **NO BACKEND field:** answers go only into `briefing.what_is_known` as one block (`plan.ts:189-195`).
  Needed: a keyed `questions_for_user` answer list in working content, which `analyze_brief` reads
  (harness bump). Whether workspace validation takes a new key is a **hypothesis** (not checked).
- Plan: new.
- Test: `PlanStep.test.tsx` › "an answer typed and left is in the saved copy after a reload".

**D8. Comments: undo, no false "upraveno", target and author.**
- What changes:
  - remove with `useUndo` (`:748`);
  - drop `plan_changed26` on save-only (`:276-279`);
  - the board's note copy.
- "k sadě … · Jana Malá" needs the comment's target and author. **NO BACKEND:** the store is
  `{quote, comment}` in `ui_state` (`plan.ts:197-214`). Needs `{target, author}` (the author from the
  session, never from the browser).
- Plan: new (critique items).
- Test: `PlanStep.test.tsx` › "a removed comment comes back with Vrátit; saving comments marks nothing changed".

**D9. Edits bar: decided rows and Vrátit.**
- What changes: `EditsBar` keeps decided edits for the turn, with a pill.
  - Vrátit on an **accepted text edit** reuses `AutoBar`'s revert (`Workbench.tsx:915-`): the replaced
    wording is written back as the person's edit.
  - Vrátit on a **dismissed** edit: **NO BACKEND.** A ledger decision is final; it needs an
    un-decide or a re-propose, which is `working-copy-edit-ops#WCE9`. Show no Vrátit there until then.
- Plan: `research-lead-workbench#7` / `working-copy-edit-ops#WCE9`.
- Test: `Workbench.test.tsx` › "an accepted edit stays as Přijato with Vrátit, and Vrátit restores the before text".

**D10. Plan card (Lead pane).**
- **NO BACKEND:** `lead-orchestration#LO3`, `#LO4`, `#LO21e`. Not built in this section; listed so the
  board's card is not faked.

### 2.4 Backend gaps (Návrh)

1. **Research-question-to-objective link.** None exists (`packages/aia_core/src/aia_core/domain/item_ids.py:76-80`).
2. **Hypothesis verification link and verdict.** None exists (`packages/aia_core/src/aia_core/domain/edit_ops.py:835`; `research_trace.py`).
3. **A recommended N from a variant.** No field; today `applyVariant` writes `n` (`apps/web/src/research/plan.ts:171`).
4. **Keyed follow-up answers.** Only an append to `what_is_known` (`apps/web/src/research/plan.ts:189-195`).
5. **Comment target and author.** Not stored (`apps/web/src/research/plan.ts:197-214`).
6. **Un-dismiss a Lead edit.** No route; `WCE9`.
7. **Lead edits of a set.** `set_edit` is declared only (`packages/aia_core/src/aia_core/domain/edit_ops.py:845`).
8. **Plan card.** `lead_plans` and its card are not built (LO3/LO4).

---

## 3. Dotazník (Questionnaire)

### 3.1 What the prototype shows (artifact pane, in order)

1. **Header.** "Dotazník", "Uloženo", the cap "22 otázek · 1 sada · 3 bloky", segmented "Upravit /
   Náhled respondenta", and the primary "Cílová skupina ›". There is no "Způsob" (Nahrát / Ručně / AI)
   control.
2. **Proposal block "Úprava dotazníku: 3 změny · vyberte, co přijmout; vaše bloky zůstanou"**
   (`#q-proposal`).
   - Header actions: "Odložit", "Přijmout vybrané (n)".
   - Per change: a checkbox, where ("S1 · nový výrok", "Q3 · rozsah škály", "B3 · otázka Q14"), the
     text, the why, and a kind tag (přidat / změnit / odebrat).
   - After accepting, a note: "Přijato n z 3 změn. Ostatní zůstávají v návrhu, dokud je nezahodíte."
     with Vrátit.
3. **Edit view.**
   - **B1 "Znalost a pití značek"** (cap "3 otázky"). Question cards, each with:
     - a header: Q id, a type tag, and "měří VO1" or "neměří žádnou výzkumnou otázku" (with a tooltip
       explaining why);
     - the wording input;
     - options as chips;
     - for Q2, a condition note: "Podmínka zobrazení · jen kdo v Q1 zvolil …" plus the reason and a
       disabled "Zapnout" (R9);
     - for Q3, a scale segmented control 1–5 / 1–7 / 1–10 / 0–10 / Vlastní, plus its ends.
   - **S1 "Sada: Značky ležáků"** (cap link "sdílená s Návrhem").
     - The set question input.
     - "Škála 1–10" with its ends.
     - "Měří": short toggles VO1, VO2, VO3, with the full text in a tooltip.
     - Object chips.
     - An accepted statement as a well: "výrok · … · přijato z návrhu · měří VO3 a ověří hypotézu H2".
     - A note that familiarity is not available (R9).
4. **Preview view "Náhled respondenta"** (cap "tak, jak otázku uvidí; škály v jejich rozsahu").
   - Each question as the respondent sees it.
   - Scales drawn at their **real range** (Q3 follows the selected range).
   - The condition shown "(zatím vypnuto)".
   - The set shown as one row, plus "a stejně pro dalších 6 značek".
   - A count of what was not shown: "+ 18 dalších otázek v blocích B2 a B3".

Lead pane:
- the "Úprava dotazníku" job card (done, "Posoudit" jumps to `#q-proposal`);
- a Lead reply;
- the "Rešerše k návrhu" card (Spustit rešerši 1,20 USD; then "4 výroky se zdrojem čekají v návrhu nahoře").

### 3.2 Today on develop

Rendered by `QuestionnaireStep` (`R/QuestionnaireStep.tsx:171-374`).

- **Toolbar.** "Způsob" segmented Nahrát / Ručně / AI, a view segmented, and "Upravit dotazník"
  outside the workbench (`:296-328`). Before a method is picked, a chooser (`:282`, `:415-446`). The
  board shows no method control. **Owner check:** keep the chooser for an empty questionnaire and move
  "Nahrát" into a header menu.
- **Extra pieces the board drops:** `Outline` (`:356`, `:661-752`), `QuestionnaireStrip` (`:763`),
  "Jak výzkumné otázky zodpovíme" (`:765`, `:794-822`), Závislosti (`:781`, done as QST8), and the
  final "Rešerše" section with `DeepResearchPanel` (`:358-363`). The panel has its own start button
  with no `leadOwnsAiStarts` gate (`R/DeepResearchPanel.tsx:125`). **Proposal:** Strip, Comparisons and
  Závislosti go to the inspector ("Připravenost a pomoc"); Outline stays as-is (**owner check**).
- **Question card.**
  - The type is chosen with chips; the Q id only appears in a tooltip (`:926`).
  - The research-question links repeat every question's full text as chips (`:1004-1046`).
  - The condition: hidden with routing off (`R/QuestionCondition.tsx:72-75`).
  - The scale: `ScaleEditor` with presets (`R/ScaleEditor.tsx:75-148`) already matches the board's
    five choices.
- **Set.**
  - Range fixed (`:1216-1222`).
  - The familiarity switch is enabled, and readiness then FAILs (`:1225-1226`;
    `packages/aia_core/src/aia_core/domain/research_design.py:1497-1503`).
- **AI proposal.**
  - `ProposalReview` is mounted at the stage top (`R/ResearchScreen.tsx:453`, `469`).
  - Whole-proposal "Ponechat současný návrh / Zahodit / Použít návrh" (`R/ProposalReview.tsx:183-190`).
  - It replaces own blocks (`:64-65`, `:117-128`).
  - Its "{size} položek" uses no Czech plural (`:105`).
- **Preview.**
  - Every scale is drawn 1–10: `ScaleBoxes` defaults to 1..10 and is called without a range
    (`R/QuestionnaireStep.tsx:641`, `616`, `627`).
  - It stops at 14 items (`apps/web/src/research/questionnaire.ts:124`, `130`), 8 options (`:140`),
    8 set rows (`:162`) and 2 drawn rows (`R/QuestionnaireStep.tsx:623`), with no word of what was cut.
  - Conditions are not shown.
- **Length.** It always reads "unset", because the API does not serve the rule
  (`R/QuestionnaireStrip.tsx:44`; CLAUDE.md map, `length.ts`).

### 3.3 Build chunks

**Q1. Header: counts, view switch and the way on.**
- What changes:
  - the cap from `questionnaireCounts` (`questionnaire.ts:64-68`) plus the block count;
  - "Upravit / Náhled respondenta" in the X1 header slot;
  - "Cílová skupina ›" calls `toAudienceStep` (`:189-192`);
  - remove the toolbar row (`:296-328`) and the workbench dock;
  - the method chooser stays only for an empty questionnaire.
- Backend: none.
- Plan: `artifact-questionnaire#QST2`.
- Test: `QuestionnaireStep.test.tsx` › "the header counts questions, sets and blocks and switches to the preview".

**Q2. Section sheets B n / S n and question cards.**
- What changes:
  - blocks and sets in X1 sheets numbered B1 / S1;
  - card header "Q n · type tag · Měří …";
  - the type tag opens the existing type chips in a `MenuButton` (the board shows no type control;
    the control must stay reachable);
  - options as chips (the existing `OptionRows` edit on click).
- Backend: none (working content; the `section:` / `question:` marks are kept, `:115-147`).
- Plan: `artifact-questionnaire#QST2`.
- Test: `QuestionnaireLeadTargets.test.tsx` still passes; `QuestionnaireStep.test.tsx` › "a block renders as B1 with its question count".

**Q3. "Měří" as short VO toggles.**
- What changes:
  - `ResearchQuestionLinks` (`:1004-1046`) shows `VO n` chips, with the full text in `title` and in an
    accessible name;
  - with none linked: "neměří žádnou výzkumnou otázku", with a tooltip saying why;
  - dangling links stay coral.
- Backend: `link_set` (`edit_ops.py:835`; the person's edit goes through the store) and the trace.
- Plan: `artifact-questionnaire#QST2`.
- Test: `QuestionnaireStep.test.tsx` › "a question's links show as VO chips named by the research question's text".

**Q4. R9: the condition and familiarity disabled, with the reason.**
- What changes:
  - `QuestionCondition`: with routing off and an eligible earlier choice question, render the
    condition line, its reason (the board's copy) and a disabled "Zapnout", instead of `null`
    (`:72-75`). A stored condition still shows and can be removed (`:98`).
  - `TrackedSet`: remove the familiarity `Switch` (`:1225-1226`) and show the note. A set already
    stored with `familiarity_required` shows "uloženo, běh ji odmítne" plus "Vypnout".
- Backend: `/config` `routing` (`public-config.ts:45`); readiness `battery_familiarity`
  (`research_design.py:1497-1503`).
- Plan: R9 under `artifact-questionnaire#QST4`.
- Test:
  - `QuestionCondition` test › "routing off: the condition is shown disabled with its reason";
  - `QuestionnaireStep.test.tsx` › "no familiarity switch is offered; a stored one can be switched off".

**Q5. Respondent preview at the real range, with what was left out.**
- What changes:
  - `previewQuestion` returns the stored range (`questionnaire.ts:135-149`);
  - `ScaleBoxes` takes it (`R/QuestionnaireStep.tsx:616`, `627`, `641`);
  - the condition line;
  - the set as one row plus "a stejně pro dalších n";
  - a count of the items not shown ("+ n dalších otázek v blocích …").
- Backend: none.
- Plan: new (critique d/e).
- Test: `questionnaire.preview.test.ts` › "a 1–7 scale previews seven boxes; a cut list says how many it left out".

**Q6. Proposal reviewed item by item (R8).**
- What changes:
  - for questionnaire jobs, a per-change block replaces `ProposalReview`, each change with a checkbox,
    where, text, kind and why;
  - "Odložit" leaves the proposal pending (the existing `false` decision, `R/ProposalReview.tsx:185`);
  - "Přijmout vybrané (n)" posts the selected change ids;
  - after the accept, the note plus Vrátit;
  - the statement accepted into S1 shows "přijato z návrhu · měří …".
- Backend: **NO BACKEND.**
  - The accept body has no selection (`apps/api/src/aia_api/routers/research.py:3719-3725`).
  - The application passes all recorded `touched` (`application/research.py:2069`).
  - There are no per-change ids or why (`domain/research_agents.py:158-162`).
  - Needs `working-copy-edit-ops#WCE8b` and then `#WCE6`.
  - The "Vrátit" after an accept needs `#WCE9`.
- Plan: `artifact-questionnaire#QST5`.
- Test:
  - `useResearchAgents.test.tsx` › "a change accepted alone posts its change id" (QST5's own test);
  - an API test that the unselected changes stay pending.

**Q7. The Lead owns the AI starts; Design Research as a card (R12).**
- What changes:
  - under `leadOwnsAiStarts`, remove `DeepResearchPanel`'s start (`R/DeepResearchPanel.tsx:125`); the
    panel stays a reader;
  - remove the AI build section's start (`R/QuestionnaireStep.tsx:340-347`, already AskLead);
  - the job card's "Posoudit" scrolls to `#q-proposal`;
  - the job card shows its change count.
- Backend:
  - `optimize_questionnaire` and `build_questionnaire` are started by the typed command
    (`commands.json:5-6`).
  - **NO BACKEND** to start Design Research from a card (`application/research_lead.py:1140`), so its
    card waits for `lead-orchestration#LO5a.2` / `#LO5a.3`.
- Plan: `artifact-questionnaire#QST6`, `research-lead-workbench#26f.1`.
- Test: the 26f static guard lists `DeepResearchPanel` with no start in the workbench; `lead_cards_journey.mjs`.

**Q8. Set: shared with Návrh (R7).** This is D6 seen from Dotazník: the "sdílená s Návrhem" cap and
the same section id. The test is shared with D6.

### 3.4 Backend gaps (Dotazník)

1. **Per-change accept of an agent proposal.** None exists (`apps/api/src/aia_api/routers/research.py:3719-3725`, `packages/aia_core/src/aia_core/application/research.py:2069`). Plans: WCE6 and WCE8b.
2. **Per-change rationale and sources** ("Zdroj: rešerše, 2 citace"). Not in `QuestionnaireProposal` (`packages/aia_core/src/aia_core/domain/research_agents.py:158-162`).
3. **Design Research started from a Lead card.** Refused as `NotAPaidRequest` (`packages/aia_core/src/aia_core/application/research_lead.py:1140`). No typed command (`commands.json:31`).
4. **Lead edits for a set or scale.** `set_edit` and `scale_set` are declared only (`packages/aia_core/src/aia_core/domain/edit_ops.py:837`, `845`).
5. **Questionnaire length.** Not served (`apps/web/src/components/rehome/research/QuestionnaireStrip.tsx:44`; `artifact-questionnaire#QST7`). The board does not show it, so no blocker.
6. **Routing.** Fieldwork does not route yet (`AIA_ROUTING_ENABLED`, RQC11), so the disabled state in Q4 is the build target.

---

## 4. Chunk count and order

X1, then B1–B8 (B4 blocked), D1–D10 (D4, D5, D7 partly blocked; D10 not built), and Q1–Q8 (Q6 blocked;
Q7 partly blocked). That is 27 chunks.

Unblocked UI-only first: X1, B1, B2, B3, B5, B6, B7, B8, D1, D3, D8, Q1–Q5.
