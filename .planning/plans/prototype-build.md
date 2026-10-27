---
status: in-progress
chunks:
  - "[ ] PB1. Finish what is open and decide: the open PRs in flight landed or closed, Nigel's decisions of 25-26 Oct 2026 recorded in the plans (this docs PR), OQ13 to legal and the methodology owner's two items asked (W0)"
  - "[ ] PB2. The look and the frame in apps/web: lane A's PBA1-PBA7 and lane B's Settings frame (W1)"
  - "[ ] PB3. W1: the design stages (Zadání, Návrh, Dotazník, Vzorek, Sběr dat), the working copy, the first Lead cards, money on the cards, the remaining Settings pages (W1)"
  - "[ ] PB4. W2: the audience and results stages (Cílová skupina, Dimenze, Výsledky, Sociomapa), the Lead's money and actions (W2)"
  - "[ ] PB5. W3: Analýza, Zpráva and the report editor, the Lead's identity (W3)"
  - "[ ] PB6. Data class gates advisory in the MVP deployments: develop-class-advisory's AIA_DATA_CLASS_GATES=advisory allowed in staging and production too, every class still computed and recorded; accept gates, spend confirmations, the budget stop, evidence gates, the Sociomap register, EU residency and the licence gate stay (Nigel, 26 Oct; W1; owner: the Lead worker, with the AI-runtime lane)"
  - "[x] PBA1. Lane A, the AppShell Dock rail: 64 px of icons at rest, 240 px on hover or focus, the motion as the Settings prototype draws it, on every page (W1)"
  - "[x] PBA2. Lane A, Můj Vedoucí on the rail on every page, opening Vypěstovat when no Lead exists, else Můj Vedoucí (lead-identity LI7 widened; W1)"
  - "[ ] PBA3. Lane A, the Nastavení flyout opened from the rail item: nine sections in three groups, Reference gone into Stav systému (after #900 and settings-redesign F17; W1)"
  - "[x] PBA4. Lane A, the hero component (eyebrow, serif title, lede, edit chip, figures), on top-level pages only (UI-1; W1)"
  - "[x] PBA5. Lane A, Phosphor icons across apps/web except the rail's navigation icons (UI-2, @phosphor-icons/core, MIT; W1)"
  - "[x] PBA6. Lane A, the primitives to the look contract: radii 6/8/10, chips 24/6, switch 40x24, dialog 560/10, toast, table header on sunken, no font weight 700 (W1)"
  - "[x] PBA7. Lane A, the Lead chat's radii 10/12, the same as the rest of the product (UI-3; W1)"
  - "[ ] PBA8. Lane A, the rail's collapsed badge dot (a needs-you dot on an item while the rail is collapsed) and the active item's ring (follows PBA1; W1)"
  - "[ ] PBA9. Lane A, the Nastavení flyout's fourth column: an animated Můj Vedoucí card (follows PBA3; lane H's words, lead-identity#LI9; W1)"
---
# Prototype build: from the approved prototypes to the product

**Sources** (each read as data):
- the plan draft, <https://claude.ai/artifact/WAXfK9cLPacjqxmDV6qWiM> (the five steps and the eight lanes);
- the research build spec, <https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy> (version 1792975852-7e8b;
  135 chunks in `00-overview`, `navrh`, `vzorek`, `sber-vysledky`, `sociomapa-analyza-zprava`, `lead`);
- the look contract, <https://claude.ai/artifact/1iuneZ5EAYJTfr854VRHPM>;
- the Settings prototype, <https://claude.ai/artifact/8W9LR8Ju9BWnR5JACmiWv7> (v91, 11 artboards).

**To land:** `prototypes/` will hold the exported prototypes and `prototypes/shared/aia-core.css`, with
`prototypes/LOOK.md`, in a separate PR by the PM coordinator. Until it lands, those paths are named here as the
design reference and the artifacts above are the source.

**What this plan is.** An index and an order. Every lane's work is a chunk in its owning plan, listed below as
`plan#ID`; this plan's own chunks are the five steps (PB1-PB5, each ticked when its listed chunks are) and lane A
(PBA1-PBA7), which has no other home that its builder can see. It is registered **core** in master §3.1, with
wave rows in `.planning/mvp-execution-contracts.md`, because lane A's chunks are build work with no other plan and
an MVP gate (the workbench and Settings frame) waits on them.

## The order

1. **PB1. Finish what is open and decide (W0).** Land or close what is in flight; this docs PR records the
   decisions; legal answers OQ13; the methodology owner answers the two items below.
2. **PB2. The look and the frame (W1).** Lane A in apps/web: the Dock rail, Můj Vedoucí on the rail, the Nastavení
   flyout from the rail item, breadcrumb, hero, radii, chips, switch, Phosphor. Lane B's Settings frame with it.
3. **PB3. W1.** The design stages (Zadání, Návrh, Dotazník, Vzorek, Sběr dat), the working copy, the first Lead
   cards, money on the cards (the ceiling before a start and a parked step's need, moved here from step 4 by the
   register §6.3), the remaining Settings pages.
4. **PB4. W2.** The audience and results stages, the Lead's money and actions.
5. **PB5. W3.** Analysis, report, the Lead's identity.

## The lanes and who owns them

| Lane | What | Owner |
|---|---|---|
| A | The look and the frame | **"the second account"**: Nigel's art-chain organisation account. Its sessions see only the repository and cannot message sessions here, so lane A below is self-contained. |
| B | Settings pages | the Settings builder (`settings-redesign` F14 onward) |
| C | The study frame and the Lead pane | the stage sessions (S1) |
| D | The working copy | the stage sessions (S1) |
| E | The design stages | the stage sessions (S1) |
| F | The audience and results stages | the stage sessions (S1) |
| G | Analysis and report | the stage sessions (S1, S2 for the report editor's hosting) |
| H | The Lead's identity | the Lead session (S1) |

**Boundary.** Lane A touches the shell and the shared primitives, never a stage's content. The stage sessions keep
lanes C-G; the Settings builder keeps lane B. A chunk that needs both names the lane that merges first.

### Lane A: the look and the frame (owner: "the second account")

Design reference: `prototypes/shared/aia-core.css` and `prototypes/LOOK.md` (to land, the coordinator's export PR),
and the look contract above. Every chunk is one PR from a fresh `develop`, passes `make verify`, and keeps the
workbench's existing layouts below 1440 px (Nigel, 26 Oct 2026: "no narrower screens right now"; the prototypes are
drawn at 1440 only, and the product keeps its split, drawer and sheet at 1100 and 768 px). Each PR's screenshots at
1440 sit beside the prototype's. Wave W1.

**PBA1. The Dock rail.**
- Files: `apps/web/src/components/aia/AppShell.tsx` (its sidebar and study-mode rail become one rail), its test.
- Acceptance: 64 px of icons at rest on every page, 240 px with labels on hover or keyboard focus, the motion as
  the Settings prototype draws it (prefers-reduced-motion: no animation); the four global items, brand, avatar and
  sign-out kept; the study mode's icon-only rail is this rail.
- Tests: an AppShell test that the rail expands on focus and collapses on blur and that every item is reachable by
  Tab with a visible label when expanded; `tools/ui_workbench/ux_journey.mjs` with no page overflow.

**PBA2. Můj Vedoucí on the rail** (`lead-identity#LI7` widened: every page, not only Settings).
- Files: `AppShell.tsx` (a fifth rail item), `apps/web/src/lib/app-routes.ts`.
- Acceptance: the item on every page; it opens Vypěstovat (lane H's wording, `lead-identity#LI9`) when the
  researcher has no Lead, else Můj Vedoucí, from `GET /lead`'s hatched state; unknown opens Můj Vedoucí's own
  loading state, never the hatch. LI7 ticks when this lands.
- Tests: an AppShell test for both states and the unknown one.

**PBA3. The Nastavení flyout from the rail item** (after #900, the ⌘K section menu, `settings-redesign#F12b`).
- Files: `AppShell.tsx`, the section menu #900 adds under `apps/web/src/components/aia/settings/`,
  `ControlPanel.tsx`'s section list.
- Acceptance: the rail item opens the flyout instead of navigating; nine sections in three groups (Reference
  merged into Stav systému, `settings-redesign#F17`); keyword search, "Nic nenalezeno", Escape closes and returns
  focus to the rail item, Enter opens the first hit; ⌘K / Ctrl+K anywhere; the coral "Čeká na vás" total on the rail
  item only for those who can act. The breadcrumb is plain text.
- Tests: a flyout test for keyboard, search and focus return; `tools/ui_workbench/settings_journey.mjs`.

**PBA4. The hero, top-level pages only** (UI-1, Nigel, 26 Oct 2026).
- Files: a hero component under `apps/web/src/components/aia/` used by the top-level pages (Klienti, Společenská
  inteligence, Projektová paměť, each Settings section, Můj Vedoucí); never inside a study's stage.
- Acceptance: eyebrow, serif title, one-line lede, edit chip, and a figures row (`hero-meta`) whose values the page
  passes in; a figure with no value reads unknown, never 0. Settings' figures are lane B's (`settings-redesign#F18`).
- Tests: the component's test (unknown figure), and a guard test that no stage screen renders it.

**PBA5. Phosphor icons** (UI-2, Nigel, 26 Oct 2026).
- Files: `apps/web/package.json` (`@phosphor-icons/core`, MIT, an exact version), the icon sites across
  `apps/web/src`, `apps/web/src/components/workbench/Icons.tsx`; the rail's navigation icons stay as drawn.
- Acceptance: one icon set; every icon `aria-hidden` beside its text or with an accessible name; `make web_unused`
  clean after the old icons go.
- Tests: the existing component tests pass; `make web_unused`.

**PBA6. The primitives to the contract.**
- Files: `apps/web/src/design/tokens.json` (then `npm run tokens`), `apps/web/src/components/ui/*` (ChoiceChips,
  Switch, ConfirmDialog, SpendDialog, UndoToast, parts.tsx), the shared table header.
- Acceptance: radii 6 / 8 / 10; chips 24 px high with radius 6; the switch 40 x 24; a dialog 560 px wide with radius
  10; the toast as the contract draws it; a table header on the sunken surface; no font weight 700 anywhere.
- Tests: `make web_design` (token drift and contrast), the primitives' own tests, and a scan that no 700 weight
  remains in `apps/web/src`.

**PBA7. The Lead chat's radii** (UI-3, Nigel, 26 Oct 2026).
- Files: `apps/web/src/components/workbench/workbench.css` and `LeadPane.tsx`.
- Acceptance: the chat's bubbles and cards at radii 10 / 12, from the same tokens as the rest.
- Tests: `workbench-css.test.ts`; `tools/ui_workbench/lead_journey.mjs`.

### Lane B: Settings pages (owner: the Settings builder)

`settings-redesign#F8b`, `#F9`, `#F10`, `#F11`, `#F12`, `#F12a`, `#F12b`, `#F14`, `#F15`, `#F16`, `#F17`, `#F18`,
`#F19`, `#F20`, `#F21`, `#F22`; `system-prompts-settings#14`, `#15`, `#16`. Proposed: `settings-redesign` becomes
core with every open chunk W1 (master §3.1); Nigel may change it.

### Lane C: the study frame and the Lead pane

W1: `research-lead-workbench#36`, `#37`, `#41`, `#42`, `#44`, `#47`, `#23` (re-waved from W4), `#23b`, `#23c`,
`#26f.1`, `#35`; `lead-orchestration#LO23`, `#LO25`, `#LO3`, `#LO4`, `#LO17`; `deep-research-web-search#59`.
W2: `research-lead-workbench#38`, `#39`, `#40`, `#43`, `#45`, `#46`, `#49`, `#50`, `#51`, `#52`;
`lead-orchestration#LO24`, `#LO21e`; `lead-conversation#LC20`. W3: `research-lead-workbench#48`.

### Lane D: the working copy

`research-lead-workbench#7`; `working-copy-edit-ops#WCE8b` (re-waved to W1), `#WCE9` (W2).

### Lane E: the design stages

- Zadání: `artifact-brief#BRF2`, `#BRF3`, `#BRF4`, `#BRF7`.
- Návrh: `artifact-design#DSN3c`, `#DSN2b`, `#DSN14`, `#DSN12`, `#DSN13`, `#DSN10` (W1); `#DSN9`, `#DSN11`,
  `#DSN12b` (W2).
- Dotazník: `artifact-questionnaire#QST2`, `#QST4`, `#QST11`, `#QST6`, `#QST5` (W1); `#QST10` (W2).
- Vzorek: `artifact-sample#SMP7` (one PR with `artifact-dimensions#DIM3b`), `#SMP8`, `#SMP2b`, `#SMP5b`, `#SMP4b`,
  `#SMP10`, `#SMP3b`, `#SMP9`, `#SMP6b`.
- Sběr dat: `artifact-fieldwork#FLD6`, `#FLD2b`, `#FLD4e`, `#FLD2c`, `#FLD11`, `#FLD10`, `#FLD9`, `#FLD8b`;
  `run-qc-and-checkpoint#RQC7c` (W1), `#RQC7d` (W2).

### Lane F: the audience and results stages

- W1: `artifact-dimensions#DIM3b` (with SMP7).
- Cílová skupina: `artifact-audience#AUD2`, `#AUD7`, `#AUD9`, `#AUD8`, `#AUD10`, `#AUD5`, `#AUD6`, `#AUD11`.
- Dimenze: `artifact-dimensions#DIM2`, `#DIM8`, `#DIM5`, `#DIM6`, `#DIM4`, `#DIM7`.
- Výsledky: `artifact-results#RES9`, `#RES4c`, `#RES4b`, `#RES3`, `#RES10`, `#RES6`, `#RES2`.
- Sociomapa: `artifact-sociomap#SOC11b`, `#SOC14`, `#SOC4`, `#SOC5`, `#SOC8`.

### Lane G: analysis and report

- Analýza: `artifact-analysis#ANL9`, `#ANL10`, `#ANL2b`, `#ANL3b`, `#ANL4`, `#ANL6`, `#ANL11`, `#ANL12`, `#ANL8`;
  `artifact-chain-to-draft-report#CHN13`, `#CHN8` (kept).
- Zpráva: `artifact-report#RPT11`, `#RPT12`, `#RPT3c`, `#RPT8c.1`, `#RPT14`, `#RPT8b.1`, `#RPT8d.1`, `#RPT3d`,
  `#RPT10`, `#RPT9`, `#RPT13`, `#RPT15`, `#RPT7`.
- The editor's theme: `report-editor-hosting#5`, `#6`, `#7`, `#8`, `#9`, `#4`; `artifact-report#RPT8e`.

### Lane H: the Lead's identity

`lead-identity#LI0` to `#LI9`, W3, after `lead-conversation#LC5b` and `#LC10` (Nigel, 25 Oct 2026, kept; already on
develop through #908). `lead-orchestration#LO11` (seal-only).

## Nigel's decisions (26 Oct 2026 UTC unless noted; relayed by the PM coordinator)

- **P1.** N is set on Vzorek: "this stage has to do with setting up the AI respondents". `artifact-dimensions#DIM3b`
  and `artifact-sample#SMP7` are one PR, in W1.
- **P3.** No third document. Literature reaches the report only through "Použít ve zprávě"; "Zpráva s rešerší"
  leaves the pane (`artifact-report#RPT3c`; `artifact-chain-to-draft-report#CHN8` kept).
- **P4.** Five Lead marks: "i chose these five specifically" (`lead-identity#LI2`, `#LI3`).
- **P5.** Sběr dat is one stage with two views, Kontrola and Průběh: "once it starts, it automatically loads to the
  prubeh page" (`artifact-fieldwork#FLD9`).
- **P6.** Chat layout F (`research-lead-workbench#40`).
- **P7.** Keep the brand fonts in the editor DOCX (`artifact-report#RPT15`).
- **UI-1.** The hero goes on top-level pages only (`#PBA4`).
- **UI-2.** The product switches to Phosphor icons (`#PBA5`).
- **UI-3.** The Lead chat uses the same radii as the rest (`#PBA7`).
- **System prompts** are edited and switched on only with the Metodik mark: "metodik edits the prompts"
  (`system-prompts-settings#16`).
- **Departing members.** A departing member's Lead is sealed, never handed over: "lets seal it, a new user gets a new
  vedouci"; `lead-orchestration#LO11` is seal-only.
- **Retention.** 365 days for AI spend and the audit; a sealed Lead is deleted after 365 days: "lets do 365 days".
  This closes MVPQ-07.
- **Fronta práce** is post-MVP: "lets table this idea as a plan in the future" ([`fronta-prace.md`](fronta-prace.md)).
- **Widths.** 1440 only for now: "no narrower screens right now". The product keeps the workbench's existing
  narrower layouts.
- **Zdroj audience** stays as it is.
- **Hatch payer.** An "AIA" house entity for charges that belong to no single client; its ADR is drafted by the Lead
  session (`lead-identity#LI8`).
- **LEAD_HATCH** is Class C, and the acceptance step (Přijmout / Zadat znovu) stays.
- **Hatch wording** follows "grow their own from a test tube": vypěstovat / zkumavka, not Líhnutí / Vylíhnout
  (`lead-identity#LI9`).
- **RIR-5.** The literature check is paid, capped by the study budget.
- **Lead identity** is core MVP, W3, after LC5b/LC10 (25 Oct 2026, kept).
- **Lane A** is built by "the second account" (26 Oct 2026 ~01:25 UTC).

### The questionnaire: one editor, files through the Lead (26 Oct 2026 ~01:41 UTC)

Nigel, verbatim: "its important that in the questionnaire there is no nahrat excel, sestavit rucne, sestavit with ai, becuse we only need one interface to create the question, and the user can create it manually, but can also upload an excel to the lead researcehr and the lead researcehr will create the questionnaire, if no excel is used the user can still use the lead researcher to help create it based on the previous stage inputs, client knowledgebase and deep research."

- `artifact-questionnaire#QST12`: Dotazník's "Způsob" choice removed; one editor, empty or not (lane E, W1).
- `lead-orchestration#LO18a`-`LO18b`: any standard document to the Lead on any stage, worked with as the model reasons
  through the existing gated outputs (Nigel, ~01:47 UTC: "uploading a document to the lead agent, whether its a docx, pdf, csv, xlsx or whatever standard document types, it should be able to work with it within the context of the study, irregardless of the current stage open. this will be up to the models reasoning and instructions"). A questionnaire file is one such use: read by the
  questionnaire import and filed as a no-model questionnaire proposal. The file is the client's source, shown under
  the client's Data (Nigel's D-a); its class is recorded and, under PB6, never refused.
- `lead-orchestration#LO27` with `artifact-questionnaire#QST13`: without a file, the existing build/optimize
  questionnaire jobs from a Lead card, reading every verified finding of the newest Design Research run (Nigel,
  ~01:47 UTC: "All verified findings"; a prompt and harness bump).
- QST12 ships with LO18b or after it, so Excel import is never missing in between. Nigel named no order; this is
  planning's default.

### Data class gates out of the MVP (26 Oct 2026 ~01:52 UTC)

Nigel, verbatim: "i did also say lets leave the gates out of the MVP, maximizing functionality is the goal". Asked which gates, he chose **data class gates** only (relayed by the PM coordinator).

**PB6** (W1; owner: the Lead worker, with the AI-runtime lane). The switch exists: `AIA_DATA_CLASS_GATES=advisory`
(plan `develop-class-advisory`, done) makes every refusal made solely because of a data class a recorded pass, but it
is refused outside local, test and develop (`packages/aia_core/src/aia_core/domain/deployment.py:123-138 @ 2e7fc1dd`,
`data_class_gates_problem`). PB6 lets the MVP deployments run it: the refusal of advisory in staging and production
is lifted, and each deployment states its value (no default in a deployed environment). Every request still computes
its class by rule (`domain/material_rules.py`) and records it on the ledger row, with the advisory pass noted, as on
develop today; the gate's tests keep running under `enforce`, none loosened, and new tests prove the advisory path
records the class in production's configuration. Turning enforcement back on before clients' live data is one
setting.

- **In scope:** the class-only refusals, including the Lead's route reading a Class A file (`lead-orchestration#LO18a`-`LO18b`)
  and knowledge or sources on a route below their class; the operator classification a Deep Research run on an edited
  design waits for (OI-129; advisory already takes the design rule's class).
- **Stays:** the accept gates (Přijmout), the spend confirmations and the budget stop (B1), the evidence gates and the
  Sociomap register, EU-only hosting and residency (Bedrock EU), and the **licence gate** (panel-derived data to
  `bedrock-eu-primary` only, OI-61, `domain/licence_determinations.py`), read as a licence term, not a class gate.
- **The one change** (the Lead worker, 26 Oct, anchors at `2e7fc1dd`): allow advisory in staging and production in
  `data_class_gates_problem` (`domain/deployment.py:123-138`), enforced at start in the API
  (`apps/api/src/aia_api/config.py:464-467, 512`) and the worker (`apps/executors/src/aia_executors/ai_runtime.py:927-940`);
  `enforce` stays the default; the MVP deployments set `advisory`; the gate tests stay on `enforce`.
- **The class-only refusal sites it covers:** `application/model_gateway.py:356` (and `:907`, the ledger);
  `domain/residency.py:266-272, 280-290` (checks 2 and 4; checks 1, 3 and 5-7 stay); `application/web_retrieval.py:546-695`
  (a Class A or B query to a NON_EU route is still refused by residency; Brave is the stated exception);
  `domain/deep_research/plan.py:169-190` (OI-129); `application/validation.py:270-284`; and the display
  `domain/deep_research_reach.py:102-126`. Not a class gate: the population field policy (`population/policy.py:388`).
  The licence gate stays on (`application/model_gateway.py:374`; `:198` says advisory judges residency, licence and
  budget exactly as enforce).

### The plan page's answers, B1-B6 (26 Oct 2026, 01:21-01:24 UTC)

- **B1 (a).** The study budget stops a run before it starts, "as drawn": readiness FAILs while the run's ceiling
  exceeds what is left of Rozpočet studie; the remedy is raising the budget or lowering N (spec `vzorek/V5`, OQ3;
  `artifact-sample#SMP10`, on `lead-orchestration#LO23` in W1).
- **B2 (a).** The client report is editable in the editor. Only accepted findings reach it, and the client gate
  re-runs on every saved version before approval (spec `szz/Z8`, OQ10; `artifact-report#RPT13`, unblocked, W3).
- **B3 (a).** `AIA_AI_STEP_EVENTS` is on for develop; infra sets it (OQ12; `research-lead-workbench#44`).
- **B4 (a).** A brief's files are Class A by rule, like a client's sources; a person may mark one Veřejné, which
  makes it B (spec `navrh/B6`, OQ18; `artifact-brief#BRF7`). An ADR 0008 implication: its amendment note is that
  PR's Doc follow-up.
- **B5 (b).** Keep the ten problem types (18.6.6's, parity-tested); the board changes to the ten, not the code (spec
  `navrh/B1`, OQ15).
- **B6 (b).** Embed the fonts on download, as first chosen, not at save (spec `szz/T7` as written;
  `artifact-report#RPT15`). The accepted trade-off: a downloaded editor-saved DOCX differs from its stored bytes, so
  `X-AIA-Artifact-Id` and the SHA-256 describe the stored version, and the download says it re-embedded the fonts.

## Still open

- **Legal, OQ13.** The AIA editor icons are redrawn from ONLYOFFICE's AGPL sprites, a modified covered work, so the
  NOTICE and the AGPL §13 source offer apply. The editor goes live with ONLYOFFICE's own icons until legal decides
  (`report-editor-hosting#5`, `#6`, `#9`).
- **The methodology owner.** Výsledky's "Efektivní n" is Kish's, as `artifact-results#RES3` says (OQ8); a set's
  scale follows the board's presets (OQ9, `artifact-questionnaire#QST10`). Both await the methodology owner's
  confirmation.

## Decided by default by planning, open to Nigel's override

- A study budget may go to 1,000,000 USD.
- SOUL is bounded at 2,800 bytes.
- Skills are derived from the worker registry (`lead-identity#LI6`).
- Starting fieldwork keeps the answerability acknowledgement.
- The Lead asks before saving a client note.
- A variant recommends N and never applies it (`artifact-design#DSN10`).
- The own dimension is chosen on Dimenze, shipped after master G28 (`artifact-dimensions#DIM4`).
- Rešerše: the card lives on Návrh (`artifact-design#DSN5`), and its "+" items are disabled with a reason until
  `lead-orchestration#LO5a.3`.
- The brief's "povinné" is advisory.
- Kontext: "Aktuální krok" always goes to the Lead, "Moje poznámky" is on by default, client knowledge is chosen per
  message (`lead-conversation#LC20`).
- The brand pair is disabled with its reason (`artifact-sample#SMP3b`).
- AUD4 sits under §01 of Cílová skupina.
- There is no "Vrátit" inside the open editor (`artifact-report#RPT8b.1`).
- Methodology items go to the methodology owner.

## Re-waves this plan records (in `.planning/mvp-execution-contracts.md`)

- `working-copy-edit-ops#WCE8b`: W2 → W1 (the per-item accept, `artifact-questionnaire#QST5`, is W1).
- `research-lead-workbench#23`: W4 (E22) → W1 (the run and job cards that `#37` and `#45` sit on).
- The money APIs in W1: `lead-orchestration#LO23` (the ceiling before a start) and `artifact-fieldwork#FLD10`
  (`budget_need`).
- The composer's "+" menu, `research-lead-workbench#41`, W1, on today's contract (LO21b is prompt-only).

## Contradictions left open (from the research chunk register §4)

- `deep-research-web-search#59` changes the Deep Research tool event while the engine is frozen "except on a defect
  or evaluation finding" (contradiction 13): it lands only when recorded as one.
- `input-interactions#5` fixes "one n stepper 50-5000"; `artifact-sample#SMP7` takes its bounds from
  `/research/limits` (contradiction 14). The server's limits win; #5's text is to be amended by its owner.
- FLD6 promises one spend dialog in W1 while `input-interactions#6` is W2 (contradiction 5): FLD6 ships with today's
  confirmation and moves onto SpendDialog in W2.

## From the unplanned-features inventory (2026-10-27)

Source: the five inventories of 27 Oct 2026 (the Lead, the client pages, Settings, the research stages and the
prototypes, each compared with develop `dbaa7720`) and the product owner's decisions on them (Nigel, 27 Oct 2026,
~01:10-01:40 UTC, in the PM coordinator's chat: "lets turn these into chunks", then an answer to every decision
question). The research build spec cited is <https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy> (spec v6,
prototype v78); its ids carry their section prefix (`navrh/`, `vzorek/`, `sber/`, `szz/`, `lead/`). Waves are in
`.planning/mvp-execution-contracts.md`; a chunk marked **after the MVP** has the wave POST there. Ids are only
added, never renumbered; a ticked chunk a decision reopens gets a follow-up chunk.

**PBA8. The rail's badge dot and ring** (lane A, W1). The Settings prototype v99 draws, on the collapsed 64 px rail, a
coral dot on an item where something waits for the person (only for those who can act) and a ring on the active item.
PBA1 built the rail without them. Files: `AppShell.tsx`. Test: a collapsed rail shows the dot from real API state and the
ring on the current item; unknown state draws no dot.

**PBA9. The flyout's fourth column** (lane A, W1; after PBA3). An animated Můj Vedoucí card beside the three section
groups (the prototype's motion; none under prefers-reduced-motion), linking Můj Vedoucí, or Vypěstovat when no Lead
exists (PBA2's rule). Test: the card opens the right page in both states.
