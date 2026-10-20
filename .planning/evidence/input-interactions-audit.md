# Input interactions: a system-wide audit

**Written:** 2026-10-20 against `develop` @ `44b66ef` · **Asked by:** Nigel Blount (product owner),
2026-10-20 21:10 UTC · **Plan:** [`../plans/input-interactions.md`](../plans/input-interactions.md)
(proposed for the scope baseline) · **Read-only evidence:** nothing here changes code.

> "I absolutely hate the way most input boxes work. Either I want to edit straight in the artifact,
> or there are different options, like counters for numbers, multiple choice for predetermined
> questions. We need to revise all the interactions where a user inputs any information, even
> creating new folders for the user file: everything overlays a small text box over the whole
> screen for the text input." — the product owner

Every anchor below is `apps/web/src/<path>:<line> @ 44b66ef` unless it names another root. Paths
are shortened: `rh/` = `components/rehome/`, `rs/` = `components/rehome/research/`, `cl/` =
`components/aia/clients/`, `st/` = `components/aia/settings/`, `wb/` = `components/workbench/`.

## 0. What the owner saw, exactly

"Nová složka" (`cl/KnowledgeArea.tsx:319-327`) calls `setAsk({ kind: "prompt" })`. That renders
`AskDialog` (`rh/ui.tsx:140`), a `<dialog>` opened with `showModal()` (`rh/ui.tsx:150`), 32 rem
wide, centred, with a dimmed backdrop over the whole page (`rh/ui.tsx:168`), holding one sentence
and one `TextInput` (`rh/ui.tsx:197`). AskDialog's own comment says why it exists: it is
"confirm() and prompt(), as a modal <dialog>: the classic screen's questions, word for word"
(`rh/ui.tsx:136-139`). It is a faithful port of 18.6.6's `window.prompt`, and it is the pattern the
owner is objecting to.

The same modal prompt is used **11 times** across the product:

| # | Where | Asks for |
|---|---|---|
| P1 | `cl/KnowledgeArea.tsx:319` (button :435) | Název nové složky |
| P2 | `cl/KnowledgeArea.tsx:328` (button :478) | Nový název složky |
| P3 | `cl/KnowledgeArea.tsx:345` (button :504) | Nový název štítku |
| P4 | `cl/ClientDirectory.tsx:65-77` (button :83) | Název klienta |
| P5 | `cl/ClientContext.tsx:83-98` (buttons :135, :137) | Název nového výzkumu / simulace |
| P6 | `rs/QuestionnaireStep.tsx:500` (Škála 1–10) | Co chcete změřit na škále 1–10? |
| P7 | `rs/QuestionnaireStep.tsx:500` (Otevřená) | Na co se chcete zeptat otevřeně? |
| P8 | `rs/QuestionnaireStep.tsx:500` + `:502` (Jedna odpověď) | the question, then its options **as a comma-separated string** in a second modal |
| P9 | `rs/QuestionnaireStep.tsx:509` + `:511` (Sledovaná sada) | the set's type, then **4–15 items as a comma-separated string** in a second modal |

(P8 and P9 are two chained modals each, so 11 modal text boxes in all.) AskDialog's **confirm**
form is used 14 more times: delete folder and label (`cl/KnowledgeArea.tsx:337`, `:354`), leave
the plan with unsaved edits (`rs/PlanStep.tsx:100`), three cancels (run `rs/ExecutionSteps.tsx:1150`,
interpretation `rs/InterpretationResearch.tsx:120`, AI job `rs/ResearchScreen.tsx:274`) and eight
spend confirmations (§2.3).

## 1. Counts

About **250 entry points** in 34 files. Settings has no modal at all; every modal text box is in
the client workspace or the questionnaire.

**By area** (rows in §3; a per-item control counts once):

| Area | Entry points | Modal prompts | Modal confirms | Other overlays | Researcher meets it |
|---|---:|---:|---:|---:|---|
| A. Study design stages (Zadání, Návrh, Dotazník) | 66 | 6 | 1 | 2 (drop overlay, floating comment button) | every study |
| B. Sample, audience, run, results | 47 | 0 | 11 | 3 (JobPanel, AgentProposalDialog, narrow AI-help drawer) | every study |
| C. Workbench and the Lead | 13 | 0 | (1, shared with B) | 0 | every study, workbench on |
| D. Client workspace: knowledge, intake, studies | 46 | 5 | 2 | 2 (intake `<dialog>` sheet, page drop overlay) | daily |
| E. Client profile, contacts, budget, memory | 21 | 0 | 0 | 0 | per client, rare |
| F. Settings | 49 | 0 | 0 | 0 | admins, rare (searches: any member) |

**By control today** (all areas):

| Control | Count | Notes |
|---|---:|---|
| Free-text field (`TextInput`, raw `<input>`) | ~75 | ~14 of them search boxes; ~11 inside AskDialog |
| Multi-line (`TextArea`, raw `<textarea>`) | ~30 | 4 hold a **list, one per line** (ProposalEditor ×3, MeasurementEditor) |
| `<select>` / `Select` | ~45 | **7 used as one-shot actions** that save on change; 5 are ≤5 fixed values |
| Number (`type=number`, numeric text) | 12 | 2 silently clamp or accept min>max (§2.2); 3 money |
| Range slider | 2 | n (200–2000), map relief (0.5–2) |
| Segmented / pressed-button groups | ~25 | `Segmented` primitive used only 2×; ~20 hand-rolled `aria-pressed` groups |
| `RadioCard` / radio | ~12 | `RadioCard` primitive used only in AudienceStep |
| `Switch` / checkbox | ~14 | 3 hand-rolled `role=switch` (ProfileArea, technical.tsx, …) |
| `ChipInput` | 3 | the only list-entry primitive; good |
| File pickers / drop zones | 6 | |
| `InlineConfirm` / inline confirm panels | ~14 | good: the pattern the rule keeps |
| AskDialog prompt / confirm | 11 / 14 | |

## 2. What the inventory shows

1. **AskDialog prompt is the one thing to remove.** Each of its 11 uses names or renames a thing
   that is then shown in a list (folder, label, client, study) or creates an artifact item
   (question, tracked set) — exactly I1/I5's cases. P8 and P9 also make a person type a **list
   as a comma string** into a one-line box, then parse it (`addTrackedSet`, `addGuidedQuestion`),
   and an invalid count is reported by a toast after the modal is gone.
2. **Numbers are not counters, and two of them lie.**
   - Sample size n has three controls for one value on `rs/PersonaStep.tsx` (presets :277/:284,
     slider :380 at 200–2000, field :407 at 50–5000); the slider cannot reach what the field
     allows, and `setSampleSize` silently clamps (`research/persona.ts:180`): typing 20 stores 50,
     typing nothing stores the recommendation.
   - A scale question's Minimum/Maximum (`rs/QuestionnaireStep.tsx:777`, `:779`) are uncontrolled
     `type=number` with `min=0 max=11`, no `step`, saved on blur through `setScaleEnd` with `+raw`:
     min > max, a decimal or an empty field (stored as 0) are all saved. Compile refuses
     min ≥ max as `invalid_scale`, but `_scale` truncates a decimal with `int()`
     (`packages/aia_core/src/aia_core/domain/research_design.py:405`), so 2.5 runs as 2.
   - Audience factor ranges (`rs/AudienceStep.tsx:379`, `:382`) state the population's range in a
     hint but set no bounds on the field.
   - Deep Research numeric rules (`st/DeepResearchSettingsPanel.tsx:422-426`) and methodology
     parameters (`st/MethodologyVersions.tsx:669`, ~142 parameters, booleans typed as text) leave
     every bound to the server's check.
3. **Known sets are typed or hidden in dropdowns.** Profile "Odvětví" and "Trh" are free text
   (`cl/ProfileArea.tsx:74`, `:77`); a label's colour is chosen by colour *name* from a `<select>`
   with no swatch (`cl/KnowledgeArea.tsx:241`, `:494`); the five research-question comparison
   methods are a `<select>` (`rs/QuestionnaireStep.tsx:615`); the question type is a hand-rolled
   radio group (`:707`) rather than `Segmented`.
4. **`<select>` as a button.** Seven selects fire an action on change: bulk move, bulk add/remove
   label (`cl/KnowledgeLibrary.tsx:241`, `:259`, `:268`), the open item's add label (`:406`) and
   folder (`:382`), the intake sheet's add label (`cl/IntakeSheet.tsx:339-355`), label recolour.
   A keyboard user arrowing through the list fires the action on the first arrow in some browsers.
5. **Creating is inconsistent within one screen.** "Nový štítek" is an inline form
   (`cl/KnowledgeArea.tsx:213-253`); "Nová složka" beside it is a modal (P1). Folder and label
   actions appear only while that folder or label is the active filter (`:476`, `:483`). The intake
   sheet can file into folders and labels but cannot create one.
6. **Lists typed one per line.** The narrative editor's research questions, objectives and
   hypotheses (`rs/ProposalEditor.tsx:28-31`) and a measurement's items (`rs/PlanStep.tsx:572`) are
   textareas parsed by line, behind an explicit "Použít…" button — while the same set's items on
   the card are a `ChipInput` (`rs/PlanStep.tsx:510`). The prototype edits each as an item
   (`prototypes/research-lead-v2/src/components/ui.tsx:52`).
7. **Save behaviour is mixed on one card.** In the questionnaire most fields autosave on change,
   but seven save only on blur (scale labels, min/max, set ends, price bands, the option group,
   `rs/QuestionnaireStep.tsx:757-997`) and give no visible state until then.
8. **Deletes without a way back.** A question (`rs/QuestionnaireStep.tsx:720`), an attachment
   (`rs/BriefStep.tsx:518`), a comment (`rs/PlanStep.tsx:714`) and a contact
   (`cl/ProfileArea.tsx:260`, a server DELETE) are removed with no confirm and no undo.
9. **Knowledge search sends a GET per keystroke** (`cl/KnowledgeLibrary.tsx:85-88`, no debounce);
   memory search waits 300 ms (`components/aia/MemorySearch.tsx:43`).
10. **Modals that are right.** The eight spend confirmations (§3.B) are modal and should stay
    modal: they interrupt for money and record the yes in the approval ledger (ADR 0019 gate 2).
    Settings already does every approval and activation as an inline panel with a reason; that is
    acceptable and stays (I7 permits a modal there, it does not require one).

## 3. Inventory and fix list

One table per area, rows ranked by how often a researcher meets them (**F1** every study or daily,
**F2** some studies or per client, **F3** rare or admin). "→" is the control the rule (§4) calls
for. **API**: ✓ = today's route takes the edit as the new control would send it; **new** = needs
an endpoint or field (listed in §5).

### A. Study design stages

| # | Anchor | What is entered | Real type & range | Today | F | → Rule | API |
|---|---|---|---|---|---|---|---|
| A1 | `rs/QuestionnaireStep.tsx:730` | Znění otázky, per question | free text, required | raw `<textarea>`, autosave | F1 | I1 edit in place on the question as shown | ✓ store |
| A2 | `rs/QuestionnaireStep.tsx:707` | Typ otázky: Jedna / Více / Škála / Otevřená, per question | one of 4 | hand-rolled `role=radio` pills | F1 | I3 `Segmented` (the primitive) | ✓ |
| A3 | `rs/QuestionnaireStep.tsx:858`, `:870`, `:885` | Možnosti, per option; add, remove | ordered list of short texts | raw input rows, saved on blur of the group | F1 | I1 per option + I5 inline "+ možnost" (Enter = next) + I6 undo; autosave per commit | ✓ |
| A4 | `rs/QuestionnaireStep.tsx:660`, `:661` | Název bloku, Proč se ptáme, per block | short name; one line | `InlineField` (raw input), autosave | F1 | I1 (already close; add save state + Esc) | ✓ |
| A5 | `rs/QuestionnaireStep.tsx:676` | "Otázka do tohoto bloku" | — (creates "Nová otázka?") | Button | F1 | I5 inline new row, wording focused | ✓ |
| A6 | `rs/QuestionnaireStep.tsx:500` (P6, P7) | Quick add Škála / Otevřená: the wording | free text | **AskDialog prompt** | F2 | I5 inline new question row in the outline, type preset, wording focused | ✓ |
| A7 | `rs/QuestionnaireStep.tsx:500`+`:502` (P8) | Quick add Jedna odpověď: wording, then options as "Ano, Ne" | free text + list | **2 chained AskDialog prompts**, comma string | F2 | I5 inline new question row; options as I5 rows (default Ano / Ne) | ✓ |
| A8 | `rs/QuestionnaireStep.tsx:509`+`:511` (P9) | Sledovaná sada: type, then 4–15 items as a comma string | short name + list 4–15 | **2 chained AskDialog prompts**; count error by toast | F2 | I5 inline new set card: name (I1) + `ChipInput` items with "4–15" counter at the field (I9) | ✓ |
| A9 | `rs/QuestionnaireStep.tsx:777`, `:779` | Škála: Minimum / Maximum | integers, min < max; today 0–11 | uncontrolled `type=number`, no step, blur; **min>max, decimals, empty→0 accepted** | F2 | I2 two steppers bounded by each other (min ≤ max−1), or I3 presets 1–5 / 1–7 / 0–10 / 1–10 | **new**: the domain refuses a non-integer end (§5.7) |
| A10 | `rs/QuestionnaireStep.tsx:757`, `:767`, `:973`, `:977` | Scale end labels, per question / per set | short labels | uncontrolled input, blur | F2 | I1 on the scale preview's end labels, where they are shown | ✓ |
| A11 | `rs/QuestionnaireStep.tsx:615` | "Jak výzkumné otázky zodpovíme", per research question | one of 5 (Neurčeno, Popis, Pořadí, Segmenty, A/B) | raw `<select>` | F2 | I3 `Segmented` (or chips at phone width); disable with reason where the measures can't serve it | ✓ |
| A12 | `rs/QuestionnaireStep.tsx:808`, `:819` | Odpovídá na výzkumné otázky, per question/set | several of N | pressed pills | F2 | I3 toggle chips (keep; adopt the shared component) | ✓ |
| A13 | `rs/QuestionnaireStep.tsx:916`, `:930`, `:935`, `:941` | Set: name, object type, goal, common question with `{object}` | short texts; template must contain `{object}` | inputs, autosave; warning border | F2 | I1 each; I9 the `{object}` rule said in words at the field | ✓ |
| A14 | `rs/QuestionnaireStep.tsx:961` | Objekty 4–15 | list of short names | `ChipInput` | F2 | keep (I5-compliant); add "n / 15" counter | ✓ |
| A15 | `rs/QuestionnaireStep.tsx:981`, `:986` | Ověřovat znalost; A/B test | boolean | `Switch` | F2 | keep (I4) | ✓ |
| A16 | `rs/QuestionnaireStep.tsx:997` | Cenová pásma | list of prices (Kč) | comma text, blur | F3 | I5 `ChipInput` of prices, each parsed as a number with unit (I9) | ✓ (stored as strings today) |
| A17 | `rs/QuestionnaireStep.tsx:720` | Odebrat otázku | — | button, **no confirm, no undo** | F2 | I6 delete + "Vrátit" toast | ✓ |
| A18 | `rs/QuestionnaireStep.tsx:663`, `:921` | Smazat blok / sadu | — | `InlineConfirm` | F3 | keep (I6), add undo | ✓ |
| A19 | `rs/QuestionnaireStep.tsx:205`, `:218`, `:318` | Způsob (Excel / ručně / AI); Upravit / Náhled | one of 3; one of 2 | `Segmented`; hand-rolled cards | F1 | keep `Segmented`; cards = `RadioCard` | ✓ |
| A20 | `rs/QuestionnaireStep.tsx:390` | Načíst dotazník (XLSX/CSV) | one file | hidden file input + drop button | F2 | keep; drop zone inline (no overlay) | ✓ |
| A21 | `rs/QuestionnaireStep.tsx:561` | Nový blok | — | Button, named later | F2 | I5 inline new block row, name focused | ✓ |
| A22 | `rs/BriefStep.tsx:139` | Cíl výzkumu | free text, ≥40 chars "ready" | raw `<textarea>`, autosave | F1 | I1 on the brief as shown; length hint at the field (I9) | ✓ |
| A23 | `rs/BriefStep.tsx:170`, `:172` | Název projektu; "Navrhnout z cíle" | short name | `TextInput` | F1 | I1 on the title in the artifact header | ✓ |
| A24 | `rs/BriefStep.tsx:189` | Typ problému | several of 10 | pressed-button grid | F1 | I3 toggle chips (shared component) | ✓ |
| A25 | `rs/BriefStep.tsx:317`, `:305`, `:330` | Kontext ×5 (optional fields) | free text | raw textareas, opened by chips | F2 | I1 per field; keep "+ field" chips (I5) | ✓ |
| A26 | `rs/BriefStep.tsx:481`, `:490` | Odkaz | URL `^https?://` | input + "Přidat odkaz" | F2 | I5 inline row; I9 URL check at the field | ✓ |
| A27 | `rs/BriefStep.tsx:451`, `:108`, `:213` | Soubory (≤8 per pick); drop anywhere | files | file input; full-stage drop overlay | F2 | keep; the drop overlay is a drag cue, not an input box (allowed) | ✓ |
| A28 | `rs/BriefStep.tsx:518` | Odebrat přílohu | — | button, no undo | F2 | I6 undo toast | ✓ |
| A29 | `rs/PlanStep.tsx:289`, `:167` | Rozsah projektu (≤3 variants); replace confirm | one of ≤3 | hand-rolled radio cards; `InlineConfirm` | F2 | `RadioCard`; keep `InlineConfirm` | ✓ |
| A30 | `rs/ProposalEditor.tsx:26-31`, `rs/PlanStep.tsx:363` | Shrnutí; Výzkumné otázky / Cíle / Hypotézy **one per line** | free text; 3 lists of lines | 4 textareas behind "Upravit text návrhu", explicit "Použít úpravy" | F2 | I1 on each item of the plan as shown; I5 "+ otázka / cíl / hypotéza" rows; autosave; drop the separate editor | ✓ store |
| A31 | `rs/PlanStep.tsx:412`, `:425`, `:434` | Přidat sadu: Název | short name | inline form | F2 | I5 (already inline; Enter = create, add next) | ✓ |
| A32 | `rs/PlanStep.tsx:490`, `:510` | Set name (rename); Položky ≤15 | short name; list 4–15 | input on blur; `ChipInput` | F2 | keep; add I1 save state and "n / 15" | ✓ |
| A33 | `rs/PlanStep.tsx:570-577` | MeasurementEditor: name, compares, **items one per line**, question `{object}`, scale ends | texts; list 4–15 unique | separate form, explicit "Použít změny sady" | F2 | fold into the set card: I1 per field, items as `ChipInput` (A32), uniqueness at the field | ✓ |
| A34 | `rs/PlanStep.tsx:610`, `:626` | Odpověď na otázku AI, per follow-up | free text | input + paid "Doplnit a aktualizovat návrh" | F2 | keep explicit send (it spends); inputs stay inline | ✓ |
| A35 | `rs/PlanStep.tsx:667`, `:728`, `:714`, `:746` | Comment on selected text | free text | floating button → inline input (Enter/blur) | F3 | keep (inline, anchored to selection); add undo on remove | ✓ |
| A36 | `rs/PlanStep.tsx:100` | Leave with unsaved edits | yes/no | AskDialog confirm | F3 | disappears with A30/A33 (autosave); else I10 guard as `InlineConfirm` | ✓ |

### B. Sample, audience, run, results

| # | Anchor | What is entered | Real type & range | Today | F | → Rule | API |
|---|---|---|---|---|---|---|---|
| B1 | `rs/PersonaStep.tsx:407`, `:380`, `:277`/`:284` | **Velikost vzorku n** | integer 50–5000 (`research/persona.ts:180`) | 3 controls: number field (**silent clamp**, empty → recommended), slider 200–2000, 4 preset pills | F1 | one I2 stepper 50–5000 (step 50, Shift ×10 = 500) with the recommended n as a marked chip beside it; out of range said at the field, not clamped | ✓ store |
| B2 | `rs/PersonaStep.tsx:351`, `:174`, `:221` | Dimensions | several of N (catalogue) | pressed rows; × remove; "Použít doporučené" | F1 | I3 toggle rows (keep) in a searchable list (B3) | ✓ |
| B3 | `rs/PersonaStep.tsx:208` | Hledat dimenzi | search | raw input | F1 | keep as the list's filter field | — |
| B4 | `rs/PersonaStep.tsx:296`, `:298` | Vlastní dimenze: name | short name | input + "Přidat jako požadavek" | F3 | I5 inline row at the end of the list | ✓ |
| B5 | `rs/AudienceStep.tsx:153`, `:178`, `:214` | Odkud / Která populace / Koho reprezentovat | one of 2 / 3 / 3 | `RadioCard` | F1 | keep (I3) | ✓ |
| B6 | `rs/AudienceStep.tsx:379`, `:382` | Numeric factor Od / Do, per factor | numbers within the factor's population range; blank = open | `type=number`, **no min/max**, blur | F2 | I2 range: two steppers bounded by the catalogue min–max, "bez omezení" as an explicit empty state | ✓ (catalogue gives bounds) |
| B7 | `rs/AudienceStep.tsx:405` | Categorical factor values | several of N, with counts | checkboxes | F2 | I3 toggle chips with counts (≤15), else checklist with filter | ✓ |
| B8 | `rs/AudienceStep.tsx:344`, `:351` | Category; Hledat faktor | one of N; search | pressed buttons; input | F2 | I3 chips + combobox (I3, >15 factors) | ✓ |
| B9 | `rs/AudienceStep.tsx:464` | Vestavěný subpanel | one of 18 | `RadioCard` ×18 | F2 | I3 searchable list or chips (18 > 15): combobox with the counts | ✓ |
| B10 | `rs/AudienceStep.tsx:298`, `:299`, `:311` | Popis vlastními slovy → AI | free text | input + paid AI button (JobPanel) | F2 | keep (a prompt to AI, not a value) | ✓ |
| B11 | `rs/AudienceStep.tsx:485`, `:488` | Discover: product; success criterion | free text | textareas | F3 | I1 | ✓ |
| B12 | `rs/ExecutionSteps.tsx:924` | **Kdo bude odpovídat** (persona source) | one of 2, unoffered disabled with reason | radio list | F2 | `RadioCard` (each needs its sentence) | ✓ |
| B13 | `rs/ExecutionSteps.tsx:886`, `:894` | Populace běhu | one of 1+k | radio list | F3 | `RadioCard` / combobox when k > 4 | ✓ |
| B14 | `rs/ExecutionSteps.tsx:312`, `:324` | Spend limit on/off; amount USD | USD 0–1,000,000 (`routers/scope.py:147`) | `Switch` + `type=number`, blur | F2 | I4 switch + I2 money stepper (step 1, Shift ×10), saved on commit with state | ✓ |
| B15 | `rs/AnswerabilityGate.tsx:93`, `:105` | Pokračovat s omezeními + reason | boolean; text 10–1000 (`lib/answerability.ts:19`) | checkbox + textarea | F2 | keep (a decision recorded with the run); live "n / 10 min" at the field (I9) | ✓ |
| B16 | `rs/ExecutionSteps.tsx:858` (+`:695`, `:704`, `:730`) | **Spustit výzkum** | paid action | AskDialog confirm when ceiling ≥ limit | F1 | **keep modal (I7a)**; replace AskDialog with a purpose-built spend dialog: ceiling, limit, remaining, what it buys | ✓ |
| B17 | `rs/ExecutionSteps.tsx:1160`, `:1174`, `:1089`; `rs/DeepResearchPanel.tsx:124`, `:139`; `rs/InterpretationResearch.tsx:145`, `:161`; `wb/Workbench.tsx:275` | Retries, analysis retry, DR and interpretation start/retry, Lead job approval | paid actions | AskDialog confirm on the server's ask | F2 | keep modal (I7a), the same spend dialog as B16 | ✓ |
| B18 | `rs/ExecutionSteps.tsx:1153`; `rs/InterpretationResearch.tsx:160`; `rs/ResearchScreen.tsx:274` | Zrušit běh / rešerši / úlohu | action | AskDialog confirm | F3 | I6 `InlineConfirm` at the button ("Hotové kroky zůstanou uložené") — not money, not beyond the item | ✓ |
| B19 | `rs/DeepResearchPanel.tsx:140` | Zrušit běh (Deep Research) | action | **no confirm** | F3 | I6 `InlineConfirm` (match B18) | ✓ |
| B20 | `rs/BudgetLift.tsx:66`, `:69` | Nový rozpočet studie (USD), note | USD ≥ current, ≤1,000,000; text ≤500 | inline `type=number` + textarea, explicit | F3 | keep inline (it is already where the stop is shown) but I2 money stepper starting at current + the step's need; this is money: I7a allows a modal, inline is acceptable because the step is parked, nothing spends until submit | ✓ |
| B21 | `rs/CompleteReport.tsx:355`, `:389`, `:369` | Verze zprávy; Formát; Varianta | one of 2; one of 2; one of 1+N | `Segment` ×2; `Select` | F1 | keep `Segment`s; variant = `RadioCard` when ≤3 | ✓ |
| B22 | `rs/CompleteReport.tsx:438` | **Schválit zprávu** | action, once, ledger | Button, **no confirm** | F1 | I7b: a modal naming which document (version, format, variant) is approved — it is recorded and cannot be undone | ✓ |
| B23 | `rs/ResearchAssistance.tsx:131`, `:119`, `:149` | Co chcete zjistit? (≤8000) | free text | textarea in aside; narrow: `<dialog>` drawer | F2 | keep; narrow = full-height sheet carrying the task (I8, already) | ✓ |
| B24 | `rs/AgentProposalDialog.tsx:22-32` | Použít / Ponechat návrh | one of 2 | `<dialog>` | F2 | inline review in the artifact (`rs/ProposalReview.tsx` pattern; research-lead-workbench chunk 7) | ✓ |
| B25 | `rs/JobPanel.tsx:45` | (job progress) | — | modal overlay `role=dialog` | F2 | non-modal panel beside the stage (I8): a running job must not block reading | ✓ |
| B26 | `rs/ExecutionSteps.tsx:1844`, `:1847`; `rs/SociomappingView.tsx:65`, `:194`; `rs/InterpretationResearch.tsx:150` | Results filters: search, Podpora dat (4), battery, object, rešerše | view choices | input; `<select>` ×4 | F2 | Podpora dat → `Segmented`; battery/object → combobox when >8 | — |
| B27 | `rs/ObjectMapView.tsx:300-347`, `:327`, `:446`, `:508` | Map view toggles; relief 0.5–2 | display | pressed buttons; range | F2 | keep (display only; I2 allows a slider for a continuous feel) | — |
| B28 | `rs/VerifiedSourceButton.tsx:45` | Ověřeno, přidat zdroj | action, per source | Button | F2 | keep; result inline | ✓ |

### C. Workbench and the Lead

| # | Anchor | What is entered | Real type & range | Today | F | → Rule | API |
|---|---|---|---|---|---|---|---|
| C1 | `wb/LeadPane.tsx:513`, `:523` | Lead composer | free text ≤4000 (`routers/lead.py:81`) | auto-growing textarea, Enter sends; **no maxLength** | F1 | keep; add the 4000 limit at the field (I9) | ✓ |
| C2 | `wb/LeadPane.tsx:520-522`, `:510` | @ focus; Kde jsme? / Navrhni úpravy | pick / fixed | icon + buttons | F1 | keep | ✓ |
| C3 | `wb/Workbench.tsx:502-514`, `:545`, `:536` | Accept / dismiss edits (all, per item); Vrátit | decisions | inline buttons | F1 | keep (the prototype's pattern, I1/I6) | ✓ |
| C4 | `wb/LeadPane.tsx:484`, `:485` | Spustit úlohu / Teď ne | paid decision | buttons (+ B17 spend modal when asked) | F2 | keep | ✓ |
| C5 | `wb/LeadPane.tsx:454-455` | Pamatovat si (cross-client) | decision reaching every client | inline buttons | F3 | I7b: a modal stating it reaches every client | ✓ |
| C6 | `wb/Split.tsx:38` | Split ratio 28–62 % | continuous | separator, keys | F1 | keep | — |
| C7 | `components/aia/LeadProfile.tsx:62` | Automaticky přijímat textové úpravy | boolean | checkbox, immediate API | F3 | I4 `Switch` (immediate effect) | ✓ |
| C8 | `wb/LeadPane.tsx:257` | Vylíhnout | once | button | F3 | keep | ✓ |

### D. Client workspace: knowledge, intake, studies

| # | Anchor | What is entered | Real type & range | Today | F | → Rule | API |
|---|---|---|---|---|---|---|---|
| D1 | `cl/KnowledgeArea.tsx:319` (P1), button `:435` | **Nová složka** | short name ≤80, unique in client (409 `name_taken`) | **AskDialog prompt** | F2 | I5 inline row in the folder list; Enter creates and opens the next row; uniqueness at the row | ✓ `POST …/knowledge/folders` |
| D2 | `cl/KnowledgeArea.tsx:328` (P2), `:478` | Přejmenovat složku | same | **AskDialog prompt**, only when the folder is open | F3 | I1 on the folder name in the tree (double-click / F2 / ⋯ menu) | ✓ `PUT …/folders/{id}` |
| D3 | `cl/KnowledgeArea.tsx:337`, `:479` | Smazat složku (items stay) | — | AskDialog confirm | F3 | I6: items are kept, so delete + "Vrátit" (recreate and refile) — or `InlineConfirm` at the row naming the n items | ✓ undo needs refiling: POST folder + PUT placement |
| D4 | `cl/KnowledgeArea.tsx:213-253`, `:467` | Nový štítek: name + colour | ≤80 unique; one of 6 colours | inline form, colour `<select>` by name | F2 | I5 inline row with a 6-swatch picker (I3) | ✓ |
| D5 | `cl/KnowledgeArea.tsx:345` (P3), `:504` | Přejmenovat štítek | ≤80 unique | **AskDialog prompt** | F3 | I1 on the label chip | ✓ |
| D6 | `cl/KnowledgeArea.tsx:494` | Barva štítku | one of 6 | `<select>` as action, only when filtered | F3 | swatch popover on the chip (I5) | ✓ |
| D7 | `cl/KnowledgeArea.tsx:354`, `:505` | Smazat štítek | — | AskDialog confirm | F3 | I6 delete + "Vrátit" / `InlineConfirm` naming n items | ✓ (undo: recreate + re-add) |
| D8 | `cl/KnowledgeArea.tsx:411-457`, `:515-527`, `:508` | Views (4), folders, labels, kinds (6) | one of N each | pressed buttons/chips | F1 | keep (I3) | ✓ |
| D9 | `cl/KnowledgeLibrary.tsx:104` | Hledat ve znalostech | search | input, **GET per keystroke** | F1 | keep; debounce 300 ms like memory search | ✓ |
| D10 | `cl/KnowledgeLibrary.tsx:133-160` | Select items | several of N | checkboxes | F1 | keep | — |
| D11 | `cl/KnowledgeLibrary.tsx:241`, `:259`, `:268` | Bulk move / add label / remove label | one of N | **`<select>` as action** | F2 | menu button → list (a popover menu, not a select) | ✓ `PUT …/placement` |
| D12 | `cl/KnowledgeLibrary.tsx:348`, `:351`, `:366` | Open item: Název, Shrnutí | ≤255; ≤10,000 | inputs in the side panel, explicit "Uložit jako revizi n" | F2 | I1 on the open item's title and text; commit = one revision (see §5 on batching) | ✓ `POST …/proposals` with `base_revision` |
| D13 | `cl/KnowledgeLibrary.tsx:382`, `:406`, `:396` | Open item: Složka; add / remove label | one of N; several of N | `<select>` as action; chip × | F2 | I3 combobox for folder; label chips with "+" popover | ✓ |
| D14 | `cl/KnowledgeArea.tsx:379`, `:161-182` | Napsat znalost: Druh, Název, Popis | one of 9; ≤255; ≤10,000 | inline card, `<select>` + inputs, explicit | F2 | I5 inline new item row in the library (kind as chips, then I1 fields); explicit "Uložit" acceptable as it creates a revision | ✓ |
| D15 | `cl/KnowledgeArea.tsx:114`, `:128` | Schválit / Zamítnout proposal | decision | inline buttons | F1 | keep (inline; per item) | ✓ |
| D16 | `cl/IntakeSheet.tsx:262-269` | (the sheet) | — | `<dialog>` showModal, right drawer 48 rem with backdrop | F2 | I8 non-modal sheet (keep the client page live; drop the backdrop) | ✓ |
| D17 | `cl/IntakeSheet.tsx:329-355`, `:478-489` | Folder for all / per file; labels for all | one of N; several of N | `<select>`s; select-as-action | F2 | I3 combobox **with "+ Nová složka / štítek" inline** (I5) — today none can be created here | ✓ |
| D18 | `cl/IntakeSheet.tsx:447-459` | Uložit jako: Datová sada / Dokument | one of 2 | pressed pair | F2 | `Segmented` | ✓ |
| D19 | `cl/IntakeSheet.tsx:474`, `:306-321` | Název znalosti per file; pasted text | ≤255; text | inputs | F2 | I1 on the row's name | ✓ |
| D20 | `cl/IntakeSheet.tsx:379-386` | Navrhnout znalosti z textu (paid) | boolean | checkbox | F2 | keep (form saved as a whole, I4) | ✓ |
| D21 | `cl/ClientContext.tsx:83-98` (P5), `:135`, `:137` | **Nový výzkum / simulace**: name | ≤255 | **AskDialog prompt** | F2 | I5 inline new row at the top of the Výzkumy table, name focused; Enter creates and opens the study | ✓ `POST /clients/{id}/studies` |
| D22 | `cl/ClientDirectory.tsx:65-77` (P4), `:83` | **Nový klient**: name | ≤255 | **AskDialog prompt** | F3 | I5 inline row in the client list | ✓ `POST /workspace/clients` |
| D23 | `cl/ClientDirectory.tsx:87`; `cl/StudyList.tsx:66-81` | Hledat klienta; status filter (5); Řadit (2) | search; one of 5; one of 2 | input; chips; `<select>` | F1 | keep; Řadit → `Segmented` | — |
| D24 | `cl/SourceFile.tsx:193-202` | Interní dokument | boolean | pressed button, immediate | F3 | I4 `Switch` (immediate, reversible, audited) | ✓ |
| D25 | `cl/SourceProposals.tsx:125-127` | Nový rozpočet klienta (USD) | decimal > 0 | `inputMode=decimal` text, explicit | F3 | I2 money stepper (as B20) | ✓ |
| D26 | `cl/ClientContext.tsx:142-176` | Drop files on the client page | files | full-page drop overlay → sheet | F2 | keep (a drag cue) | ✓ |

### E. Client profile, contacts, budget, memory

| # | Anchor | What is entered | Real type & range | Today | F | → Rule | API |
|---|---|---|---|---|---|---|---|
| E1 | `cl/ProfileArea.tsx:71`, `:86` | Zkratka | short code (UI 16, API 64) | input in a form, "Uložit profil" | F3 | I1 on the profile as shown; save on commit | ✓ `PUT /clients/{id}/profile` |
| E2 | `cl/ProfileArea.tsx:74`, `:77` | Odvětví, Trh | free text (UI 120, API 400); a closed list would fit | inputs, explicit | F3 | I1 + I3 combobox of known values with free entry allowed | ✓ (list: **new** vocabulary, §5) |
| E3 | `cl/ProfileArea.tsx:81` | O klientovi | ≤4000 (API 8000) | textarea, explicit | F3 | I1 multi-line (Ctrl+Enter) | ✓ |
| E4 | `cl/ProfileArea.tsx:148`, `:151`, `:156` | Brand / competitor: name, Druh | ≤255; one of 2 | input + `<select>`, "Přidat do Znalostí" | F3 | I5 inline row under each list (Vlastní značky / Konkurenti), so Druh is implied by the list | ✓ |
| E5 | `cl/ProfileArea.tsx:179-188`, `:216`, `:257` | Contact: Jméno, Role, E-mail, Dostává výsledky | ≤400; ≤400; e-mail; boolean | inline form replacing the row, explicit | F3 | I5 inline row in the contacts table; I1 per cell; e-mail checked at the field (I9); `Switch` for "Dostává výsledky" | ✓ |
| E6 | `cl/ProfileArea.tsx:260` | Odebrat kontakt | — | **immediate DELETE, no confirm, no undo** | F3 | I6 delete + "Vrátit" (re-POST the contact) | ✓ (undo by re-create; history shows both) |
| E7 | `cl/ProfileArea.tsx:303-312` | Vlastní schvalování znalostí | allow / forbid / **inherit** (API takes null) | hand-rolled switch, 2 states | F3 | I3 `Segmented` Povolit / Zakázat / Dědit, with the inherited value shown | ✓ `PUT /self-approval` |
| E8 | `cl/ProfileArea.tsx:395`, `:400` | Rozpočet klienta USD | 0–1,000,000, step 0.01 | button → inline `type=number` | F3 | I2 money stepper, I1 on the shown budget | ✓ `PUT /clients/{id}/budget` |
| E9 | — (no control) | Client name | ≤255 | **cannot be changed** (the profile says so) | F3 | I1 on the client's title | **new** `PUT /clients/{id}` name |
| E10 | `components/aia/MemoryStudy.tsx:212-237` | Použít tento design: new or empty study; name; which empty study | one of 2; ≤255; one of N | radio pair + input + `<select>` | F3 | `Segmented` + I1 name + combobox | ✓ |
| E11 | `components/aia/MemorySearch.tsx:43`; `components/aia/GlobalPages.tsx:174` | Memory search; Klient | search; one of N | input (300 ms); `<select>` | F2 | keep; client → combobox | ✓ |
| E12 | `components/aia/PopulationCharacteristics.tsx:43`, `:158`, `:161` | Verze; Hledat pole; Bloky | one of N; search; one of N | `<select>`, input, `<select>` | F3 | keep | — |

### F. Settings

Settings has **no modal**; every approval and activation is an inline panel with a reason, and every
write is an explicit button. The fixes are about numbers, known sets and editing in the row.

| # | Anchor | What is entered | Real type & range | Today | F | → Rule | API |
|---|---|---|---|---|---|---|---|
| F1 | `st/ControlPanel.tsx:403` | Strop rozpočtu studie (USD) | 0–1,000,000, step 0.01 | `type=number` in an "Upravit" row, explicit | F2 | I2 money stepper; I1 on the shown value in the row | ✓ |
| F2 | `st/ControlPanel.tsx:395` | Stav studie | one of 6 | `<select>` in an "Upravit" row, explicit | F2 | I3 status chips (or `<select>` kept as a listbox) saved on choice, with undo | ✓ |
| F3 | `st/ControlPanel.tsx:343` | Stav klienta | one of 3 | `<select>` + "Uložit" per row | F3 | I3 `Segmented` saved on choice; **Archivovaný** = I7c modal (hides the client's studies) | ✓ |
| F4 | `st/ControlPanel.tsx:309-319`, `:284` | Member: name, role; new member e-mail, name, role | text; one of 3; e-mail | inputs + `<select>` | F3 | I1 in the row; role `Segmented`; I5 inline new member row, e-mail checked at the field | ✓ |
| F5 | `st/ControlPanel.tsx:442`, `:466`, `:486-488` | Self-approval per level; new override | one of 3; one of N + one of 3 | `<select>` + "Uložit" per row | F3 | I3 `Segmented` per row; I5 inline override row with a combobox | ✓ |
| F6 | `st/DeepResearchSettingsPanel.tsx:422-426` | Numeric rule values (days, requests, tokens, USD prices, ceilings) | integers / USD with stated bounds (e.g. days 0–3650, USD 0–1000, ceilings 0–100,000; lower-only caps) | `type=text` `inputMode`, **no bounds on the field**, explicit "Uložit návrh" | F3 | I2 steppers with the bounds the panel already prints; lower-only as a max; explicit save kept (I10 draft) | ✓ |
| F7 | `st/DeepResearchSettingsPanel.tsx:411`, `:416` | Ano/Ne rules; proposed/approved | one of 2 | `<select>` | F3 | `Segmented` | ✓ |
| F8 | `st/DeepResearchSettingsPanel.tsx:420` | Host / pattern lists | list of lines | textarea | F3 | I5 `ChipInput` with per-item check | ✓ |
| F9 | `st/DeepResearchSettingsPanel.tsx:352`, `:303`, `:310` | Approve / withdraw with reason | decision + text ≤255 | inline confirm panel | F3 | keep inline or I7b modal — both comply; keep | ✓ |
| F10 | `st/MethodologyVersions.tsx:669` | ~142 parameters | numbers, booleans **typed as text**, strings, JSON lists | monospace `TextInput`, no client bounds | F3 | I2 steppers for numbers (bounds from the domain's slot properties, §5), I4 switch for booleans, I3 for enumerations ("Algoritmus rozložení", "Rámec mapy", "Výchozí role"), `ChipInput` for quantile lists; JSON only as the expert fallback | **new**: bounds/enums per parameter in the catalogue response |
| F11 | `st/MethodologyVersions.tsx:613`, `:551`, `:413` | Formula slot; note; base preset | expression; ≤500; one of presets | textarea mono; input; `<select>` | F3 | keep (an expression is text); base → `Segmented` | ✓ |
| F12 | `st/MethodologyVersions.tsx:236` | Activation reason | ≤500 | inline panel + "Potvrdit" | F3 | keep (I7b allows inline or modal) | ✓ |
| F13 | `st/SystemPromptsPanel.tsx:355`, `:369`, `:602`, `:635-640`, `:796-805` | Prompt text ≤12,000; note; activation reason; compare Z/Na; trial study/revision (paid) | text; one of N | textarea; inputs; `<select>`s | F3 | keep text; compare → two comboboxes; trial run = I7a when it costs | ✓ |
| F14 | `st/SystemPromptsPanel.tsx:123-126`, `:346-349` | Discard-draft guards | yes/no | hand-rolled inline alerts | F3 | `InlineConfirm` (the primitive) | ✓ |
| F15 | `st/ControlPanel.tsx:369`, `:728-730`, `:878`; `st/DeepResearchSettingsPanel.tsx:118`, `:183`; `st/MethodologyPanel.tsx:85`, `:89`, `:117`, `:133`; `st/FieldOriginPanel.tsx:63-95`; `st/SystemPromptsPanel.tsx:159-160` | 9 searches and filters | search; one of N | inputs, `<select>`s, pressed buttons | F2 | keep searches; ≤5-value filters → `Segmented`; actor/event (≈30) → combobox | — |
| F16 | `st/ControlPanel.tsx:922` → `st/technical.tsx:47` | Technické údaje | boolean | hand-rolled `role=switch` | F2 | the `Switch` primitive | — |

## 4. The rule: the AIA input standard (I1–I11)

The same text is the standard in the plan; it was sent to the Settings prototype and
design-artifact sessions on 2026-10-20 so their prototypes match.


**I1. Edit where it is shown.** A value the screen already displays (a study title, a question's
wording, an option label, a profile field, a folder name, a table cell) is edited in place: click
it, or focus it and press Enter/F2, and it becomes a field of the same size and type in the same
spot. Enter saves (Ctrl/Cmd+Enter in multi-line text), blur saves, Esc restores the old value. A
pencil/underline affordance shows on hover **and** on focus (touch has no hover). The save state
sits beside the value: *Ukládám… / Uloženo / Neuloženo – Zkusit znovu*. Reference: `Item`,
`prototypes/research-lead-v2/src/components/ui.tsx:52`.

**I2. Bounded numbers get a stepper.** `− [value] +`, the value typeable, bounds stated beside it
("50–5 000"), Shift+arrow or Shift+click ×10, buttons disabled at the bound. A typed value out of
range is shown at the field in words and **not saved — never silently clamped**. A slider only for
a continuous display setting or threshold where the feel matters more than the digit, always paired
with the number. Money is a stepper with the currency beside it and the step in whole dollars.

**I3. A known set is chosen, never typed.** One of ≤5 short values: a segmented control
(`Segmented`, `apps/web/src/components/rehome/step.tsx:139`). When each choice needs a sentence:
radio cards (`RadioCard`, `step.tsx:90`). Several of a small set: toggle chips. 6–15 values: chips
or a visible list. More, or a list the API supplies (factors, clients, studies, members, folders):
a searchable combobox (type to filter, arrows, Enter). A `<select>` never performs an action on
change; an action takes a menu button.

**I4. Booleans.** A `Switch` that takes effect at once when the effect is reversible and visible; a
checkbox only inside a form saved as a whole.

**I5. Create in the list.** "+ Nová složka / štítek / kontakt / možnost / otázka" becomes an inline
row where the new thing will appear, its input focused. Enter creates it and opens the next empty
row (ten options are ten Enters); Esc, or blur while empty, cancels. Uniqueness and length are
checked at the row as you type. Rename is I1 on the name. Recolour is a swatch popover anchored to
the item. Lists are entered item by item (`ChipInput`, rows), never as a comma or one-per-line
string. Reference: `AddItem`, `prototypes/research-lead-v2/src/components/ui.tsx:108`.

**I6. Delete and undo.** A reversible delete happens at once with a "Vrátit" toast for 8 s. An
irreversible one confirms inline at the row (`InlineConfirm`, `step.tsx:216`), naming what goes.

**I7. A modal only when it must interrupt, and never for a single text field.** Allowed:
(a) **money**: a spend confirmation, a run or job start whose ceiling reaches the study's limit, a
budget lift where it is not already inline at the stop; (b) **a decision recorded as one** in the
approval ledger or audit that cannot be undone: approve a report, activate a methodology version,
approve or withdraw a Deep Research policy, accept a Lead change that reaches every client;
(c) **an irreversible action reaching beyond the item in view**: archive a client. The modal states
the consequence and the cost in words, focuses the safe choice, and Esc cancels. (b) may stay an
inline panel where Settings already does it that way. AskDialog's prompt form is retired.

**I8. Multi-field work beside the list, not over it.** Editing an item's several fields uses a
non-modal side panel or sheet (the knowledge item, the intake sheet, the inspector, a running job);
the list behind stays visible and live, no backdrop. At phone width it becomes a full-height sheet
that carries the whole task.

**I9. Validation at the field, in words.** Shown from the first blur, then live. A server refusal
(422 by name, 409 stale) appears at the field that caused it, with the way out ("Načíst novější
verzi"). A Save button is never the only place an error shows; a toast never reports a field error.

**I10. Save model.** A study's working copy autosaves (the study store, 1.8 s, visible state).
Record edits (knowledge, profile, folder, contact) save on commit (I1) with undo. An explicit
"Uložit" only for a draft checked as a whole (methodology version, Deep Research rule, system
prompt) or a paid action; there the unsaved state is visible and leaving asks inline.

**I11. Keyboard, focus, size.** Tab reaches everything; Enter/Space operate; arrows move within
segmented controls, chips and comboboxes (roving tabindex); focus returns to the trigger after
cancel; outline in `focus-ring`. Targets at least `--control-height` (32 px comfortable, 24 px
compact, WCAG 2.2); 44 px for steppers and chips at 390 px, where a segmented control over three
options wraps to chips.

**Tokens** (`apps/web/src/design/tokens.json`; states in `design-system/reference/components.html`
and `state-gallery.html`): an editing field on `surface-raised` with `border-strong`; focus
`focus-ring`; the commit `signal`; an error at the field `status-fault` on `status-fault-wash`;
"yours to act on" `status-you`; state change at `duration-confirm` (120 ms), panels
`duration-panel` (180 ms); `radius-control`; popovers `z-overlay`, toasts `z-toast`; sizes from
`density` (`control-comfortable` 32 px, `row-comfortable` 36 px).

## 5. Where the API is not enough

Most fixes are web-only: the routes already take the value the new control would send (✓ above).
These need a server change, and each is a chunk of its own in the plan:

1. **Rename a client** (E9): there is no route; `cl/ProfileArea.tsx` says the name is fixed. Needs
   `PUT /api/v1/clients/{id}` `{name}`, audited. **No permission covers it today**:
   `ClientPermission.EDIT_CLIENT_PROFILE` excludes the name by its own comment
   (`packages/aia_core/src/aia_core/domain/scope.py:234-235`), and the client's status is an
   administrator's (ADR 0019). Owner decision: a rename is a profile edit (extend
   `EDIT_CLIENT_PROFILE`, any member) or a lifecycle change (administrator only). Until it is
   decided, E9 is out of the plan's build.
2. **Rename a study**: no route takes a Study's `name` after creation (`scope.py` has status and
   budget only, `routers/scope.py:457-503`). Inline rename of a study in Výzkumy (I1) needs one.
3. **Methodology parameter bounds and enumerations** (F10): the catalogue sends each parameter's
   original value; the editor guesses the type from it. Steppers and segmented choices need the
   bound, step and allowed values per parameter in the catalogue response (the domain already
   checks them: `packages/aia_core/src/aia_core/domain/methodology/expressions.py`, slot
   properties).
4. **Industry and market vocabulary** (E2): free text today; a combobox needs a list. Proposed: the
   organization's own values so far (a read over `clients.industry`/`market`, no new table) —
   free entry stays allowed.
5. **One revision per inline commit** (D12): editing a knowledge item in place commits each field
   as a new revision through `POST …/proposals` with `base_revision`. Two commits a second apart
   are two revisions. Decision for the owner: accept that (simple, honest history), or batch commits
   made within one open-item session into one revision (web-side, no API change).
6. **Undo of server deletes** (D3, D7, E6): undo by re-create is possible today but leaves two
   audit entries and new ids. Acceptable for the MVP; a soft delete with restore is out of scope
   (client-workspace C9 / lifecycle K6 own retirement).
7. **A non-integer scale end** (A9, IA-2): a stepper stops the web from sending 2.5, but a stored
   revision or a stale client still can, and `_scale` truncates it with `int()`
   (`packages/aia_core/src/aia_core/domain/research_design.py:405`). The domain must refuse a
   non-integer end as `invalid_scale` (a readiness FAIL), with a test, in the same chunk.

## 6. Findings

Six-part findings for the docs PR to number (CLAUDE.md §9). Each reproduces in the UI workbench
(`make ui-workbench` + `make ui-fixtures`).

- **IA-1. Sample size is silently clamped.** `research/persona.ts:180 @ 44b66ef`: typing 20 in
  "Počet respondentů" (`rs/PersonaStep.tsx:407`) stores 50; an empty field stores the
  recommendation, with no message. Repro: a Vitest on `setSampleSize(p, "20").project.n === 50`.
  Consequence: the researcher believes n is what they typed. Fix: refuse out-of-range at the field
  (I2, I9). Test: the stepper's unit test asserting 20 is shown as an error and not stored.
- **IA-2. Scale min/max accept nonsense.** `rs/QuestionnaireStep.tsx:777,779 @ 44b66ef`
  (`setScaleEnd` with `+raw`): min 8, max 3; 2.5; and an empty field (stored 0) are all saved
  to the working copy. Compile refuses min ≥ max (`invalid_scale`), so that one is caught late at
  readiness; but `_scale` turns 2.5 into 2 with `int()` (`packages/aia_core/src/aia_core/domain/
  research_design.py:405 @ 44b66ef`), and an empty Minimum becomes a 0–10 scale. Repro: a unit
  test compiling a scale question with `skala: [2.5, 10]` gets `(2, 10)` and no problem.
  Consequence: fieldwork asks a scale the researcher did not set. Fix: bounded steppers (A9) and
  the domain refusing a non-integer end (§5.7). Tests: a Vitest on `setScaleEnd`; a domain test
  that `[2.5, 10]` is `invalid_scale`.
- **IA-3. The n slider cannot reach the field's range.** `rs/PersonaStep.tsx:380` (200–2000) vs
  `:407` (50–5000): a stored n of 3000 puts the slider at its end, misrepresenting the value.
  Repro: type 3000. Fix: one stepper (B1). Test: as IA-1.
- **IA-4. Knowledge search requests on every keystroke.** `cl/KnowledgeLibrary.tsx:85-88`: typing
  "segmentace" sends ten GETs. Repro: the network panel. Consequence: wasted requests, results
  flicker. Fix: 300 ms debounce as `MemorySearch.tsx:43`. Test: a Vitest with fake timers counting
  requests.
- **IA-5. A contact is deleted with one click.** `cl/ProfileArea.tsx:260`: "Odebrat" DELETEs at
  once, no confirm, no undo. Fix: I6. Test: the client journey removing and restoring a contact.
- **IA-6 (hypothesis: not reproduced). Selects that act on change.** `cl/KnowledgeLibrary.tsx:241,259,268,382,406`,
  `cl/KnowledgeArea.tsx:494`: a keyboard user moving through the options can fire the action.
  Reproduce in Chrome on Windows, where a closed `<select>` changes on arrow keys, before budgeting. Fix: a menu button (D11). Test: a component test that arrow keys do not call the action.
