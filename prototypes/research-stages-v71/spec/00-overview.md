# Research stages: build spec for the approved UX

**Scope.** Nigel, 26 Oct: "i am super happy with the design of the research steps, we need to aim to build out this exact UX design."

This spec maps the prototype onto develop:
- **Prototype:** https://claude.ai/artifact/3dkKPTDoa1yvK4GCV7PLtJ, version 65.
- **Develop:** bd0d1ad6, 26 Oct 01:19.

It covers the eleven stages, the respondent disc and the Lead pane with its cards.

**Base.** Every code claim is anchored `file:line @ bd0d1ad6`. A claim that could not be verified is labelled "hypothesis".

**No visual tokens here.** The unified look contract (the coordinator's) decides colours, type and spacing. This spec names only the layout primitives the prototype needs and develop lacks.

**Read-only.** Nothing was changed in the repository.

## Sections

| File | Stages | Chunks |
|---|---|---|
| `navrh.md` | Zadání, Návrh, Dotazník | 27: X1, B1–B8, D1–D10, Q1–Q8 |
| `vzorek.md` | Cílová skupina, Dimenze, Vzorek | 25: A1–A9, D1–D7, V1–V8, H1 |
| `sber-vysledky.md` | Sběr dat (Kontrola and Průběh), the respondent disc, Výsledky | 29: F1–F7, P1–P6, D1–D6, V1–V10 |
| `sociomapa-analyza-zprava.md` | Sociomapa, Analýza, Zpráva, plus the editor theme in production | 35: S1–S6, A1–A10, Z1–Z11, T1–T8 |
| `lead.md` | The Lead pane, the composer's "+" menu, every card type, streaming | 19: LP-1 to LP-19 (B1–B16 are the backend gaps) |

Each stage has four parts: what the prototype shows, today on develop, build chunks, and backend gaps. Each chunk lists its files, whether it is backed (or "NO BACKEND"), its plan or chunk id (or "new"), and the test that proves it.

## What is already there

- **The frame:** the workbench, the split, the stage navigator and the Lead pane.
- **The approved Sociomapa** (map-first, #815).
- **The report editor's backend:**
  - RPT8b: saved changes, "Upraveno ručně".
  - RPT8c/d/f: the editor routes and pane.
  - Editor hosting chunks 1–4a.
- **The run event feed,** used by the disc and the streaming cards.
- **The audience preview,** with per-filter counts.
- **The edit vocabulary for N** (`set_n`).
- **The "+" menu's actions** match `lead_artifacts.py` on all eleven stages.

Much of the work is laying out and wording what is already served.

## Biggest gaps (no backend)

1. **R8 partial accept** of an AI proposal: no item selection on accept. Needs WCE8b, then WCE6.
2. **R7 one shared set:** Návrh's `analysis.tracked_sets` and Dotazník's compiled sections share no id until WCE8b.
3. **R5 findings review** (Přijmout / Upravit / Vyřadit):
   - no ledger subject;
   - no plan chunk;
   - the report prints every finding (`application/report.py:483-491`).
4. **Money on cards:**
   - a design job's or analysis retry's ceiling is not served before start (only inside the 409);
   - a parked step's need (`requested_usd`) is stored but never served (`worker.py:389-398` vs `routers/research.py:1124-1126`);
   - "+N USD a pokračovat" must be computed;
   - `SpendDialog` is not used anywhere.
5. **Deep Research in the conversation:**
   - no in-chat card;
   - no typed command for Interpretation Research;
   - `approve_request` takes only agent jobs (`application/research_lead.py:1140`).
6. **The plan card** (LO3/LO4) is not built.
7. **Links the boards show but nothing stores:**
   - goal → research question;
   - hypothesis → measure;
   - which research questions a dimension supports;
   - the brand-pair support note on Vzorek.
8. **The Lead cannot edit filters or dimensions:** those edit operations are declared but not built (`domain/edit_ops.py:851-854`).
9. **Kontext toggles** in the composer: a message has no field for per-turn context choices (`routers/lead.py:101-108`).

## The prototype corrected against develop (done 26 Oct)

- **Respondent disc (version 64).** It now draws only what `fieldwork_progress` and the step status carry.
  - Removed:
    - the invented "in progress" batch;
    - the amber parked batch;
    - "replayed people" (the reports count blocks);
    - the faster replay.
  - Added:
    - "Nový pokus" (a new attempt counts from 0);
    - "Fiktivní" (fictional fieldwork reports nothing until the step ends);
    - the RQC7b sectors as built behind `AIA_AI_FIELDWORK_QUOTA_FILL`.
- **Zpráva (version 65).** It now follows amended ADR 0035 (22 Oct, "the researcher decides, code shows"):
  - "Uložení odmítnuto" and "Vrátit 56" are replaced by a neutral "Upraveno ručně" note and a line in the approval dialog;
  - the lock is a guard the researcher may undo, so `modifyContentControl` becomes `ano`.

## Prototype against backend: other contradictions left as owner questions

- **The study budget as a blocker on Vzorek** ("Brání spuštění"). The start never checks it (`domain/money.py:333-336`). See Q-V2.
- **"Efektivní n" on Výsledky.** There are two different numbers (Kish, and the smaller support n); the proposal is Kish.
- **Editing the client report.** The board opens it in the editor, but the server refuses (`report_editor.py:136-137`).
- **Brief file classes.** The server classes every brief file as Class B, but the board shows "Důvěrné" and "Veřejné" pills.
- **The set's scale range.** The two boards disagree: presets on Návrh, fixed 1–10 on Dotazník.
- **R3:** applying a scope variant writes `n` today (`plan.ts:171`), while the board only recommends it to Vzorek.
- **The Design Research start.** Its own button on the panel has no Lead gate (`DeepResearchPanel.tsx:125`). Two plans (QST6, DSN5) move it to Návrh, while R12 makes it a Lead card.

## Owner questions (all, deduplicated)

1. ~~Signal colour~~ **Settled.** Develop's `tokens.json` already has signal `#4b48ce` (commit 1d7eae81, "Move the interface palette to Indigo"); `#3557e0` is only the `hue-blue` wayfinding tint. The editor theme and its icons were corrected to develop's tokens on 26 Oct, and the audit is still clean.
2. **R6:** should Sběr dat have two views? Today Kontrola also creates a design revision on every visit (`ExecutionSteps.tsx:710`).
3. **Q-V2:** should the study budget become a FAIL readiness check?
4. **Q-V1:** should the brand-pair note be a disabled-with-reason line under R9, or wait for familiarity?
5. **Q-A1:** the audience description vs filters check: provable only, or drop it? **Q-A2:** Předpoklady (AUD4) are not on the board.
6. **Q-D1:** ship the client's own dimension toggle before master plan G28 is closed?
7. **Efektivní n:** Kish (proposed) or the support n? This is a methodology owner's call.
8. **The set's scale:** presets or fixed 1–10?
9. **Client report:** may it be edited in the editor, and does it also require accepted findings?
10. **Lead Kontext:** can "Aktuální krok" be switched off? Should "Moje poznámky" be off or on by default?
11. **`AIA_AI_STEP_EVENTS` on develop.** Without it, a running design job shows nothing between "převzato" and "dokončeno".
12. **Editor theme licensing.** The AIA icon sprites are redrawn from ONLYOFFICE's own AGPL sprites. That is a modified covered work: the NOTICE must say so, and the AGPL source offer probably applies. Owner or legal decision before mounting.
13. **Editor fonts:** re-embed when a saved version is downloaded (`report_export.py:151`, where the approval stamp already rewrites the file), or accept DOCX without embedded fonts?

## Suggested order

1. **Primitives and frame:** X1 (header slot, numbered section sheet) and the look contract.
2. **Fully backed re-layouts,** stage by stage, in pipeline order.
3. **Money and streaming:** serve the parked step's need and the pre-start ceilings; SpendDialog everywhere.
4. **Lead cards,** the Deep Research card in chat.
5. **Editor theming (T1–T8),** after question 12.
6. **The no-backend chunks** (R5, R7, R8, links, Lead edits of filters and dimensions), each waiting on its plan chunk.

Each section ends with its own order.
