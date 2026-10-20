---
status: planned
chunks:
  - "[ ] 0. Audit, standard and this plan (docs only; .planning/evidence/input-interactions-audit.md)"
  - "[ ] 1. Shared primitives with tests: InlineText, Stepper, ChoiceChips (+ Segmented and Switch adopted everywhere), InlineCreateRow, SwatchPicker, MenuButton, UndoToast, SpendDialog; retire AskDialog's prompt form"
  - "[ ] 2. Knowledge library: folders and labels created in the list, renamed in place, recoloured by swatch; bulk and item filing by menu; search debounced (audit D1-D13)"
  - "[ ] 3. Questionnaire: questions, options, blocks and sets created and edited in place; scale ends as steppers or presets; comparisons as segmented; deletes with undo (audit A1-A21)"
  - "[ ] 4. Brief and plan: the narrative's questions, objectives and hypotheses as items edited in place; the measurement folded into the set card; autosave replaces the explicit editors (audit A22-A36)"
  - "[ ] 5. Sample and audience: one n stepper 50-5000 with the recommendation, no silent clamp; factor ranges as bounded steppers; subpanels and values as chips or combobox (audit B1-B11)"
  - "[ ] 6. Run, spend and results: one SpendDialog for every money confirmation; cancels as inline confirms; report approval as a modal naming the document; JobPanel non-modal (audit B12-B28, C1-C8)"
  - "[ ] 7. Clients and studies: new client and new study as inline rows; client and study rename in place (API: rename routes); intake sheet non-modal, creating folders and labels inline (audit D14-D26, E9)"
  - "[ ] 8. Client profile: fields edited in place, contacts as an inline table with undo, brands and competitors as list rows, self-approval three-way, budget stepper (audit E1-E12)"
  - "[ ] 9. Settings: money and rule numbers as steppers, known sets as segmented, rows edited in place; methodology parameters typed by their bounds (API: bounds and enums per parameter) (audit F1-F16)"
  - "[ ] 10. Verify: a Playwright input journey at 1440/1024/768/390 (keyboard only, Esc, undo, field errors, zero modal prompts); ux, client, settings and workbench journeys green"
---
# Input interactions: edit in place, count, choose

**Status: proposed for the scope baseline (MP16).** Nothing here is built until the owner signs the
baseline and planning folds it in. Written 2026-10-20 against `develop` @ `44b66ef` at the product
owner's request. Evidence: [`../evidence/input-interactions-audit.md`](../evidence/input-interactions-audit.md)
(inventory of ~250 entry points, fix list, findings IA-1…IA-6).

## Problem

> "Either I want to edit straight in the artifact, or there are different options, like counters
> for numbers, multiple choice for predetermined questions. … even creating new folders for the
> user file: everything overlays a small text box over the whole screen." — the product owner,
> 2026-10-20

AIA asks for a name or a list through `AskDialog`'s prompt, a full-screen modal holding one text
field (`apps/web/src/components/rehome/ui.tsx:140 @ 44b66ef`), 11 times: new, renamed folder and
label, new client, new study, and four questionnaire quick-adds, two of which take a list as a
comma string. Numbers are plain fields, two of them silently clamp or accept min > max (IA-1, IA-2).
Known sets are typed (industry, market) or chosen from dropdowns that fire on change. The same
screen creates a label inline and a folder in a modal.

## The AIA input standard (I1–I11)

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

## Approach

**Chunk 1 first, everything else on it.** The primitives live beside today's in
`apps/web/src/components/rehome/` (`step.tsx`, `ui.tsx`), each with a Vitest file
(`step.test.tsx` pattern): `InlineText` (single and multi-line; Enter/Ctrl+Enter, blur, Esc, save
state, field error), `Stepper` (bounds, step, Shift ×10, out-of-range refused with words,
optional unit), `ChoiceChips` (single and multi, roving tabindex, wrap at phone width),
`InlineCreateRow` (focus, Enter-and-next, Esc, uniqueness check callback), `SwatchPicker` (the six
`client-*`/`hue-*` colours a label takes), `MenuButton` (replaces select-as-action), `UndoToast`
(8 s, one at a time, on `z-toast`), and `SpendDialog` (ceiling, limit, remaining, what it buys;
the one modal for money). `Segmented`, `Switch`, `RadioCard`, `ChipInput` and `InlineConfirm`
already exist and are adopted wherever the audit shows a hand-rolled copy. AskDialog keeps only its
confirm form until chunk 6 replaces the spend confirms with `SpendDialog`; the prompt form is
deleted in the chunk that removes its last caller.

**Then one chunk per area, in the order a researcher meets them** (audit §3): knowledge library
(the owner's own example), questionnaire, brief and plan, sample and audience, run and results,
clients and studies, profile, Settings. Each chunk's PR lists the audit rows it closes.

**API changes** (audit §5), each inside the chunk that needs it: rename a client and rename a study
(chunk 7, `PUT` routes, audited); methodology parameter bounds, steps and enumerations in the
catalogue response (chunk 9); the industry/market list read from the organization's own clients
(chunk 8). Everything else is web-only.

## Decisions for the owner

1. **One revision per inline commit** on a knowledge item, or batch an open-item session into one
   revision (audit §5.5). Recommended: batch, web-side.
2. **Scale range**: free min/max steppers, or presets (1–5, 1–7, 0–10, 1–10) with "Vlastní" opening
   the steppers. Recommended: presets first; 18.6.6 allowed 0–11.
3. **Report approval as a modal** (I7b): today a single click. Recommended: a modal naming the
   document, since it cannot be undone.

## Where this touches other plans

Planning should fold these together rather than build twice:

- [`research-lead-workbench.md`](research-lead-workbench.md) — chunk 7 (agent proposals inline in
  the artifact) is I1/I8 for proposals and replaces `AgentProposalDialog` (audit B24); the
  workbench's artifact bodies (chunks 14–22, the V3 artifacts) should be built on chunk 1's
  primitives, so chunks 3–6 here become "apply to the artifact bodies" if those land first.
- [`client-workspace.md`](client-workspace.md) — C6 (review queue with editable folder/labels), C7
  (intake), C9 (retire and restore) overlap chunks 2, 7 and the undo rule; C9 owns real deletion.
- [`settings-workspace-ux.md`](settings-workspace-ux.md) (done) and
  [`desktop-ux-overhaul-handoff.md`](desktop-ux-overhaul-handoff.md) chunks 2 and 4 ("a coherent
  interaction model", Settings) — this plan is that interaction model; chunk 9 here supersedes 4's
  input parts.
- [`contextual-research-settings-ux.md`](contextual-research-settings-ux.md) and
  [`prompt-proposal-ux.md`](prompt-proposal-ux.md) — their editors (ProposalEditor, prompt
  workspace) are rows A30, F13.
- The Settings prototype and the design-system artifact sessions received this standard on
  2026-10-20 and apply it to their prototypes.

## What this does not do

No visual redesign beyond the controls; no change to what is saved or to any rule the server
enforces; no soft delete (C9 owns it); no new route except the three named.

## Findings

IA-1 … IA-6, with all six parts, in the audit's §6. For the docs PR to number in `open-items.md`.
