---
status: in-progress
chunks:
  - "[x] 0. Audit, standard and this plan (docs only; .planning/evidence/input-interactions-audit.md)"
  - "[ ] 1. Shared primitives with tests: InlineText, Stepper, ChoiceChips (+ Segmented and Switch adopted everywhere), InlineCreateRow, SwatchPicker, MenuButton, UndoToast, SpendDialog; retire AskDialog's prompt form"
  - "[x] 2. Knowledge library: folders and labels created in the list, renamed in place, recoloured by swatch; bulk and item filing by menu; search debounced (audit D1-D13)"
  - "[x] 3. Questionnaire: questions, options, blocks and sets created and edited in place; comparisons as segmented; deletes with undo (audit A1-A8, A11-A21)"
  - "[x] 3b1. Scales, server side: the domain compiling a scale's labels (two ends or one per point; labels that break the rule left out with a readiness WARN, scale_labels_ignored; the compiler aia-research-compile-2) and refusing a non-integer end (invalid_scale); the labels reaching respondents behind AIA_AI_SCALE_LABELS_IN_PROMPT (off), the respondent prompt's identity moving with it; the report printing them; the editor's pure rule (apps/web/src/research/scale-labels.ts) (audit IA-2, IA-7)"
  - "[x] 3b2. Scales, the editor: range presets 1-5, 1-7, 0-10, 1-10 and Vlastní; a verbal label on every point, on chunk 1's primitives (#532); the range-change rule with its undo toast (audit A9, A10)"
  - "[ ] 3b3. Scale labels switched on for respondents: AIA_AI_SCALE_LABELS_IN_PROMPT on for develop once the methodology owner has approved the wording rule; the moved respondent-system fingerprint recorded; deployment evidence (a run whose respondents read the labels); before any holdout confirmation binds to a fingerprint"
  - "[ ] 4. Brief and plan: the narrative's questions, objectives and hypotheses as items edited in place; the measurement folded into the set card; autosave replaces the explicit editors (audit A22-A36)"
  - "[ ] 5. Sample and audience: one n stepper 50-5000 with the recommendation, no silent clamp; factor ranges as bounded steppers; subpanels and values as chips or combobox (audit B1-B11)"
  - "[ ] 6. Run, spend and results: one SpendDialog for every money confirmation; cancels as inline confirms; report approval as a modal naming the document; JobPanel non-modal (audit B12-B28, C1-C8)"
  - "[ ] 7. Clients and studies: new client and new study as inline rows; study and client rename in place (API: rename routes; a client rename under EDIT_CLIENT_PROFILE, audited); intake sheet non-modal, creating folders and labels inline (audit D14-D26, E9)"
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
comma string. Numbers are plain fields, two of them silently clamp or accept min > max (IA-1, IA-2; the server then truncates a decimal scale end).
Known sets are typed (industry, market) or chosen from dropdowns that fire on change. The same
screen creates a label inline and a folder in a modal.

## The AIA input standard (I1–I11)

**I1. Edit where it is shown.** A value the screen already displays (a study title, a question's
wording, an option label, a profile field, a folder name, a table cell) is edited in place: click
it, or focus it and press Enter/F2, and it becomes a field of the same size and type in the same
spot. Enter saves (Ctrl/Cmd+Enter in multi-line text), blur saves, Esc restores the old value. A
pencil/underline affordance shows on hover **and** on focus (touch has no hover). The save state
sits beside the value: *Ukládám… / Uloženo / Neuloženo – Zkusit znovu*. Reference: `Item`,
`prototypes/research-lead-v2/src/components/ui.tsx:52`. Where a person also selects the shown text
(Návrh's comments), `InlineText`'s opt-in `selectable` opens on a settled single click, so a drag or
a double-click selects instead of opening (#727); every other caller is unchanged.

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

**API and domain changes** (audit §5), each inside the chunk that needs it: rename a study and a
client (chunk 7, `PUT` routes, audited; the client's name joins `EDIT_CLIENT_PROFILE`); scale labels
compiled into the specification and sent to respondents, and a non-integer end refused (chunk 3b,
§ Scales below); methodology
parameter bounds, steps and enumerations in the catalogue response (chunk 9); the industry/market
list read from the organization's own clients (chunk 8). Everything else is web-only.

## Owner decisions (the product owner, 2026-10-20, 22:48–22:51 UTC, on #528)

1. **Knowledge edits in place are batched** (Q31 a): one open-item editing session writes one
   revision, web-side (audit §5.5).
2. **Scale range by presets** (Q32 a): 1–5, 1–7, 0–10 and 1–10, plus "Vlastní" opening the two
   steppers. His note adds a requirement: *"a researcher asked if we could assign word attributes to
   every number between 1-10"* — every point may carry its own verbal label (§ Scales).
3. **Report approval is a modal that names the document** (Q33 a): version, format and variant,
   since the approval cannot be undone (audit B22).
4. **Any member may rename a client, every rename audited** (Q34 a): the client's name becomes part
   of `EDIT_CLIENT_PROFILE` (its comment today excludes it, `packages/aia_core/src/aia_core/domain/
   scope.py:234 @ 44b66ef`). His note: "this seems like an edge case".

## Scales (chunk 3b)

**What is stored today** (`develop` @ `44b66ef`):

- A scale **question** stores `skala: [low, high]` and `popisky_skaly: [left, right]`, the two
  ends only (`apps/web/src/research/questionnaire.ts:254`, 18.6.6's format). **The compiler never
  reads `popisky_skaly`**: `SpecQuestion` has no labels (`packages/aia_core/src/aia_core/domain/
  research_design.py:474`), and the respondent's item is built without them
  (`packages/aia_core/src/aia_core/domain/ai_respondent.py:379-388`). AI respondents answer a scale
  question as bare numbers; the ends the researcher typed reach no one (IA-7).
- A tracked **set** stores `scale_labels: [left, right]`, compiled (`research_design.py:554-556`,
  defaulting to vůbec / velmi) and sent to respondents as "1 = …, 10 = …"
  (`ai_respondent.py:567-571`).
- Nothing stores a label per point.

**The rule:**

- One field for both: `popisky_skaly` on a question and `scale_labels` on a set hold **either the
  two ends or one label per point**, low to high. A list of any other length is refused at compile
  (`scale_labels_mismatch`, a readiness FAIL), as is an empty or a repeated label
  (`scale_label_invalid`), never padded or guessed. Each label ≤ 60 characters.
- `SpecQuestion` gains `scale_labels`, absent from the stored form and the fingerprint when none were
  declared (the spec's rule for a declaration not made). The respondent's item carries them; the
  prompt lists every labelled point ("1 = vůbec, 2 = …"); the report's question tables and the
  questionnaire appendix print them.
- A non-integer end is refused as `invalid_scale` (today `int()` truncates it, IA-2).
- **When the range changes:** a two-end scale keeps its two ends. A fully labelled scale keeps its
  labels only if the number of points is unchanged (1–5 to 0–4 shifts them); otherwise the end labels
  stay, every inner label is cleared, and an undo toast says how many ("Odstraněno 8 popisků bodů –
  Vrátit"). Labels are never redistributed by guess.
- **The editor (I1, I3):** the preset chips above the scale preview; each point of the preview is an
  inline label field (Tab moves to the next point); "Popsat každý bod" turns the ends-only scale into
  every point, prefilled with the two ends.
- The change alters what respondents are told, so it changes the respondent system's fingerprint
  (ADR 0024 §4); runs made before it keep their pinned specification and are not reinterpreted.

### Chunk 3b1, as delivered (feature/scale-labels, PR #538)

- **Compile.** `popisky_skaly` (question) and `scale_labels` (set) are read by one rule,
  `research_design._scale_labels`: absent, empty or all blank is *none declared*; two labels are
  the ends; one per point is every point. **No design that compiled on develop stops compiling
  for its labels** (review of #538, P2): labels of another length, a blank, repeated
  (case-folded) or over-60-character label, or anything but a list of texts, are left out --
  none declared, nothing sent, nothing printed -- and readiness WARNs `scale_labels_ignored`
  with the reason in words (`test_labels_that_break_the_rule_are_left_out_and_said_never_refused`).
  The strict refusal is the editor's, at the field (`scale-labels.ts` `labelProblem`, 3b2).
- **A set sends what it always sent while the switch is off** (re-review of #538, P3). Develop
  read a set's ends as its first two labels, else `vůbec` / `velmi`; `_develop_ends` keeps that
  reading exactly, as `SpecBattery.develop_ends` where it differs from `end_labels` (absent from
  the fingerprint otherwise) and `told_ends`, which the off prompt, the map's legend and the
  report's two-end wording read. The new reading (`scale_labels`) reaches respondents only with
  the switch on (`test_off_a_stored_sets_requests_are_develops_bytes`: seven stored label shapes
  against develop's request bytes; `test_on_a_set_is_read_by_the_new_rule`).
- **An analysis retry never compiles again** (re-review of #538, P2). `retry_failed_modules`
  names the original's specification by artifact id and SHA-256 beside its dataset
  (`FrozenDataset.specification_artifact_id` / `_sha256`); the retry's compile step takes it as
  stored and verifies it (`CompileExecutor._frozen`, `frozen_specification_mismatch`), so every
  completed module's reuse key holds and the ceiling counts only what is asked
  (`test_a_retry_of_a_run_an_earlier_compiler_compiled_reuses_its_specification`,
  `test_a_retry_naming_another_specification_is_refused_never_compiled_again`).
  `SpecQuestion.scale_labels` (empty, and absent from the fingerprint, when none were declared)
  and `SpecBattery.scale_labels` (two or one per point; `end_labels` on both).
- **The compiler is `aia-research-compile-2`** (review of #538, P1). Compiling the labels moves
  the fingerprint of every design that declares them, so the version moves too: a run whose
  compile step stored a compile-1 specification is read as stored, held to the revision it
  records and never recompiled (`analysis_results.native_sources`;
  `test_a_run_stored_before_scale_labels_compiled_reads_as_stored`, through `reconstruct_run`,
  `stored_analysis` and the question tables), and a compile-1 artifact is never reused for a new
  run (`aia_executors.research.compile_fingerprint`;
  `test_a_specification_the_earlier_compiler_stored_is_never_reused`). A compile-1 specification
  reads back to develop's fingerprint
  (`test_a_specification_stored_before_the_labels_reads_back_as_stored`).
- **IA-2.** `_scale_end` takes a whole number, a whole float (`5.0`) or a numeral (`"5"`); 2.5,
  `"1.5"` and a boolean are `invalid_scale`, never truncated: a compile refusal, so a readiness
  FAIL on Kontrola in words ("škála musí mít dvě celá čísla, od menšího k většímu"), never on
  reading a stored run (`test_a_scale_end_that_is_not_whole_is_refused_in_words`).
- **Respondents, behind `AIA_AI_SCALE_LABELS_IN_PROMPT`** (worker, off by default, off in test,
  `false` in the develop Compose file). Off, every request is byte for byte what develop sent
  (`test_off_the_requests_are_byte_identical_whatever_labels_a_question_declares` pins the SHA-256
  over a roster's requests). On, a scale question's item carries its labels in
  `ai_respondent.scale_label_wording` -- **PROVISIONAL**, one function, identity
  `SCALE_LABEL_WORDING = "aia-scale-labels-provisional-1"`; the methodology owner signs or changes
  it before the switch is turned on. A set's two ends read exactly as before either way.
- **The respondent system.** On, `respondent_prompt_sha256(scale_labels_in_prompt=True)` is the
  SHA-256 over the system prompt and the wording's identity, so `pinned_components` and every
  panel dataset's respondent system name another prompt and fingerprint
  (`test_scale_labels_in_the_prompt_are_another_respondent_system`,
  `test_a_panel_run_with_scale_labels_in_the_prompt_records_another_respondent_system`); the
  dataset's provenance adds `prompt.scale_labels` only when on, both read from the value the requests were built with (`Answered.scale_labels_in_prompt`), never the switch read again. Off, nothing recorded moves. The
  switch is read by the worker when fieldwork runs; a finished run keeps the dataset and system it
  recorded and is never reinterpreted.
- **Validation.** A holdout arm asks with the labels off whatever the switch
  (`AIFieldwork.answer_plans(scale_labels_in_prompt=False)`), because a validation's start pins
  `pinned_components` with them off (`application/validation.py`). Validating a labelled system
  needs the switch pinned at preregistration: decided with the methodology owner before it is on.
- **Report.** The questionnaire appendix prints a question's labelled points, a set's every point
  when it has them; each scale item's question table carries a note, `Škála: 1 = …, 10 = …`
  (`report_tables.scale_notes`; `test_a_scales_labels_are_printed_beside_its_values`).
- **Not done here (3b2):** the editor. #532 (chunk 1's primitives) was open when this landed; the
  pure rule it will call (presets, `rescaleLabels`, `describeEveryPoint`, `labelProblem`) is in
  `apps/web/src/research/scale-labels.ts` with its tests, wired to no screen yet.

### Chunk 3b2, as delivered (feature/scale-editor)

- **Where.** `apps/web/src/components/rehome/research/ScaleEditor.tsx` replaces the scale
  question's Minimum / Maximum fields and both end inputs, and a tracked set's two end inputs, on
  Dotazník (`QuestionnaireStep.tsx` `QuestionCard`, `TrackedSet`; audit A9, A10). The classic layout
  and the workbench's Dotazník are the same screen. The editor writes the range and the labels
  together through the study's working copy (`questionnaire.ts` `setQuestionScale`,
  `setSetScaleLabels`), so it autosaves (I10); no server change. The classic `setScaleEnd`,
  `setScaleLabel` and `setObjectLabel` stay for their parity tests and no screen calls them.
- **Range (I2, I3; Q32 a).** `ChoiceChips` 1–5, 1–7, 0–10, 1–10, Vlastní; Vlastní opens two
  `Stepper`s, each end bounded by the other (low ≤ high − 1) and by the domain's 0–100
  (`research_agents.py` `QuestionItem` / `BatterySection`), whole numbers only: 2,5 is "Jen celé
  číslo; neuloženo." at the field, the server's `invalid_scale`, and an end meeting the other is
  refused, never clamped. A stored range the editor cannot read (a decimal, reversed or out of
  bounds, as the old fields let through: IA-2) is said with its value and no chip chosen; its labels
  wait until a range is chosen (`readRange`), never rounded or swapped into one.
- **Labels (I1).** "Oba konce" / "Každý bod" (`ChoiceChips`); each label an `InlineText`, Tab from
  point to point; "Každý bod" prefills the two ends (`describeEveryPoint`). A label over 60
  characters or repeating another point's (case-folded, as the server compares) is refused at its
  field; anything else the server would leave out (`scale_labels_ignored`: a blank point, another
  length) is said under the scale, "Popisky se nepoužijí, dokud je neopravíte: …", in
  `labelProblem`'s words. Every point is offered up to 11 points (`DESCRIBED_POINTS_MAX`, the
  presets' largest); a wider scale keeps two ends, said beside the chips; one already labelled point
  by point is shown as it is.
- **The range-change rule** is the plan's (§ Scales), `rescaleLabels` from 3b1: two ends stay two
  ends; per-point labels stay only when the number of points is unchanged (0–4 to 1–5); otherwise
  the end labels stay, the inner ones are cleared and `UndoToast` says how many ("Odstraněno 8
  popisků bodů", Czech number agreement in `clearedWords`) with "Vrátit", which restores the range
  and the labels as they were. "Oba konce" on a per-point scale clears the same way, with the same
  undo. Arrowing over the presets (single-choice chips choose as they move) adds to the toast's
  count and Vrátit restores the state before the first loss. One toast for the questionnaire
  (`ScaleUndoProvider`).
- **A tracked set** shows its range (it is not edited today and stays 1–10 unless stored otherwise)
  and offers **its two ends only**, said beside it. See the finding below: with the labels off the
  prompt, a set labelled point by point would tell respondents its first two points as its ends.
- **Tests.** `scale-labels.test.ts` (readRange, endBounds, labelMode, withEnd / withPoint,
  endsOnly, repeatsAnother, clearedWords); `ScaleEditor.test.tsx` (presets, arrows and one Tab
  stop, Vlastní bounds and a decimal refused, an unreadable stored range, the set's fixed range,
  every point described, Tab order, repeated / over-long refused, another length said, the 11-point
  limit, the range-change rule with Vrátit, the chained undo, "Oba konce", the 8 s expiry);
  `QuestionnaireStep.test.tsx › saves a scale's preset and a label on every point through the
  working copy`; `tools/ui_workbench/workspace_journey.mjs` 2b: the imported first question on
  1–10 with a label on every point, reloaded and read back, the card within 390 px, screenshots
  `2b-scale-1440.png` / `2b-scale-390.png`.
- **Audit rows closed:** A9, A10 (the set's per-point labels excepted, below); IA-2's web half
  (no screen sends `+raw` any more). The switch `AIA_AI_SCALE_LABELS_IN_PROMPT` stays off (3b3).
- **Review of #559 (Codex, P1 + P2).** Every contract that rewrites a questionnaire carries a
  scale's two ends only: the classic optimiser's `_question_schema` (`maxItems: 2`) and the
  native agents' `Question.popisky_skaly: tuple[str, str]` (`research_agents.py`). A rewrite
  would drop the inner labels a person gave every point. Fixed by keeping, not by widening the
  contract (a new contract shape means a new prompt and harness version and re-validated
  fixtures; left to 3b3, when the labels reach the prompt): `keep_point_labels`
  (`research_design.py`) and `keepPointLabels` (`scale-labels.ts`), one rule. A rewritten scale
  with at most two labels and the same range as a stored question labelled validly on every
  point keeps the stored labels, when exactly one matches it by id, else by wording, else by its
  two ends; anything else stays as written. Applied in `proposal_result` (build and optimise),
  `merge_items` (every accept through `accept_into_working_copy`), and the web's `applyOptimized`
  and `applyBuilt`. The questionnaire import is not: a file is the person's own replacement, and
  its template has two label columns. The respondent preview shows a per-point scale's first and
  last label as its ends (`previewQuestion`, `previewBattery`). Tests:
  `test_point_labels_kept.py`, `test_proposal_accept_ids.py ›
  test_an_accept_keeps_a_scale_s_labels_on_every_point`, `point-labels-kept.test.ts`.

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

## Progress

**Chunk 0** landed with #528 (the audit, the standard and this plan).

**Chunk 1, primitives delivered (2026-10-20, `feature/input-primitives`); left open.** In
`apps/web/src/components/ui/` beside `rehome/`, each with its Vitest file, their pure part in
`apps/web/src/lib/` with its own:

| Primitive | Pure part | What it keeps of the standard |
|---|---|---|
| `InlineText` | `lib/inline-edit.ts` | I1: click, Enter or F2 opens in place; Enter (Ctrl/Cmd+Enter multi-line) and blur save, Esc restores; pencil on hover and focus; Ukládám… / Uloženo / Neuloženo – Zkusit znovu, the failed text kept; I9 refusal at the field, live once said |
| `Stepper` | `lib/number-input.ts` | I2: typeable, Czech decimal comma and thousands spaces, bounds stated and in the field's description, ↑/↓ and − / + by a step, Shift ×10, buttons disabled at the bound; a typed value out of range, empty or too precise is said and **not saved** (no clamp: IA-1, IA-2's web half); `onProblem` tells an action beside it the field holds a refused value |
| `ChoiceChips` | `lib/roving.ts` | I3, I11: single (radio group, arrows choose) or multiple (toggles, arrows only move), one Tab stop, wraps, 44 px below 640 px |
| `InlineCreateRow` | `lib/name-input.ts` | I5: a row where the thing appears, focused; Enter creates and opens the next; Esc or an empty blur cancels and gives focus back; empty / too long / taken checked at the row by the server's `organizer_name` / `organizer_key` rules; the server's refusal said at the row, the name kept |
| `SwatchPicker` | `lib/roving.ts` | I3, I5: named swatches on `hue-*`; inline (arrows choose) or `popover` for a recolour (arrows only move, a click chooses once and closes: IA-6) |
| `MenuButton` | `lib/roving.ts` | I3: an action is a menu, never a select on change; arrows move without acting (IA-6), Enter/click acts once and returns focus; Esc / outside closes |
| `UndoToast` + `useUndo` | — | I6: "Vrátit" for 8 s, one at a time, on `z-toast`; the time stops under the pointer or focus (WCAG 2.2.1) |
| `SpendDialog` | `lib/spend.ts` | I7a, screen 14 of the design artifact: four kinds (Potvrzení útraty, Zvýšení rozpočtu studie / klienta, Navýšení peněženky), four names (Rozpočet klienta, Rozpočet studie, Peněženka, Práh potvrzení), the ceiling "horní mez, ne odhad", an unknown sum "neznámé" and never 0, what is left at the highest price, a lift's amount by a money stepper, the act and price on the button, focus on the safe choice, Esc cancels |

Also in it: `Segmented` (`rehome/step.tsx`) got roving tabindex (IA-8 below); three icons
(`pencil`, `minus`, `chevron`); the proof call site: KnowledgeArea's "Nová složka" is an
`InlineCreateRow` in the folder list (audit D1, P1), with `KnowledgeLibrary.test.tsx` and
`tools/ui_workbench/client_journey.mjs` changed to type in the row instead of a dialog.

**Left in chunk 1:** adopting `Segmented` and `Switch` wherever the audit found a hand-rolled copy
(~20 `aria-pressed` groups, 3 `role=switch`), and retiring AskDialog's prompt form, which keeps 10
callers (P2–P9) until the area chunks 2, 3 and 7 replace them (the Approach: it is deleted with its
last caller). No other call site moved in this PR.

### Chunk 2, as delivered (2026-10-21, `feature/input-interactions-knowledge`)

The knowledge library on chunk 1's primitives, web only: **no route, schema or audit changed**.
Audit rows closed: D1–D11 and D13; D12 kept as it is (below).

- **Folders and labels are rows of the side panel** (`KnowledgeOrganizers.tsx`: `FolderRow`,
  `LabelRow`, `NewLabelRow`). Each row selects as before; its name is renamed **in place** (I1) on
  F2, a double click or its ⋯ menu ("Akce složky / štítku {name}": Přejmenovat, Smazat), as an
  `InlineText` in the row: Enter or blur saves, Esc restores and sends nothing, focus goes back to
  the row; a taken, empty or over-80-character name is said at the field by the server's own rule
  (`name-input.ts` `nameProblem`, the row's own name excepted) and never sent; a server refusal
  stays at the field as "Neuloženo – Zkusit znovu" (D2, D5; P2, P3 retired). A label is recoloured
  by its **swatch** at the start of its row, a `SwatchPicker` popover where the arrows only move
  and a click or Enter saves (D6). "+ Nový štítek" is an `InlineCreateRow` like "+ Nová složka",
  its swatch beside the name, starting on the first colour no label uses (`nextLabelColour`), so
  Enter alone creates (D4). The folder's heading and the label filter line lost their
  Přejmenovat / Smazat / colour select: one place for each action, the row.
- **Deletes happen at once with "Vrátit"** (I6, D3, D7; `UndoToast`, 8 s). The folder's or label's
  items are read first (`GET …/knowledge?folder=` / `?label=`); undo makes it again with its name
  (and colour) and files the same items back through `PUT …/placement`: new ids and two audit
  entries, which audit §5.6 accepts for the MVP. When the read is not every item the API counts
  there (`undoable`: a different count, or a full 200-item page), nothing is deleted yet and the
  row asks with `InlineConfirm`, naming what goes and that it cannot be undone; focus on Ponechat.
- **Filing is by menu** (I3, D11, D13; IA-6 moot here): the bulk bar's Přesunout do složky / Přidat
  štítek / Odebrat štítek and the open item's Změnit složku (its own folder offered disabled) and
  Přidat štítek (only labels it lacks) are `MenuButton`s; the arrows move without filing, Enter or
  a click files once.
- **Search is debounced** (D9, IA-4): asked 300 ms after typing pauses (`SEARCH_PAUSE_MS`, as
  `MemorySearch`), trimmed; ten letters are one request.
- **Primitives extended, each with its test:** `InlineText` `autoOpen` + `onSettled` (a rename
  opened from elsewhere; settled only once the save answered, never on a failed one);
  `MenuButton` `hideLabel` (a row's ⋯, named by what it acts on) and `align`, and `menuSide`
  flips a menu that would run off the viewport (a bar wrapped at 390 px); `SwatchPicker` `align`
  and one row of swatches (`w-max`); `InlineCreateRow` `adornment`, moving to it not leaving the
  row; `parts.tsx` `POPOVER_END`; the `more` icon.
- **D12 kept.** The open item's Název and Shrnutí stay fields with "Uložit jako revizi n": that
  button is already the batch the owner chose (Q31 a: one session, one revision). Turning the two
  fields into `InlineText` would only move the batch's commit; left for the workbench's item panel
  (research-lead-workbench) rather than built twice.
- **Tests:** `KnowledgeLibrary.test.tsx` (rename from the menu and on F2, Esc, a taken name, a
  refused save and its retry, recolour with arrows that only move, a new label's colour, delete
  and Vrátit for a folder and a label, the row's confirm when undo cannot be whole, bulk and item
  menus by keyboard, the debounced search, a reader offered none of it); `knowledge-library.test.ts`
  (`nextLabelColour`, `undoable`); the primitives' own files. `tools/ui_workbench/client_journey.mjs`
  types in place: folder and label created by Enter (the label's swatch chosen), the folder renamed
  on F2 (Esc restores), the label recoloured, bulk filing by menu (the label by keyboard), a folder
  deleted and brought back by Vrátit, then folder and label deleted for good; no `<dialog>` or
  `role=dialog` open at any step; a row's menu and the bulk menu opened at 390 px without overflow;
  zero paid jobs. Run at its four widths, green twice.

**AskDialog's prompt form after this chunk** (anchors @ `25f26232`): the knowledge area has none
(P1 went in chunk 1, P2 and P3 here). Left, for chunks 3 and 7: P4 `apps/web/src/components/aia/
clients/ClientDirectory.tsx:67` (Nový klient), P5 `apps/web/src/components/aia/clients/
ClientContext.tsx:85` (Nový výzkum / simulace), P6–P9 `apps/web/src/components/rehome/research/
QuestionnaireStep.tsx:510-521` through `ResearchScreen.tsx:327` (the questionnaire's quick adds).
The confirm form keeps its callers outside this area (plan leave, three cancels, the spend
confirmations; `Workbench.tsx:147`); the knowledge area's two delete confirms are gone.

## What this does not do

No visual redesign beyond the controls; no soft delete (C9 owns it). The server's rules change in
three places only: scale labels are compiled, validated and sent to respondents, with a non-integer
end refused (chunk 3b); a client's name joins `EDIT_CLIENT_PROFILE`. No new route except the three
named.

## Findings

IA-1 … IA-6, with all six parts, in the audit's §6. For the docs PR to number in `open-items.md`.

- **IA-7 fixed** (chunk 3b1): a scale question's `popisky_skaly` is compiled into
  `SpecQuestion.scale_labels` and, with `AIA_AI_SCALE_LABELS_IN_PROMPT` on, written into the
  respondent's item (`test_on_a_scale_questions_labels_reach_the_respondent`). Off by default
  until the methodology owner signs the wording.
- **IA-2 fixed, server side** (chunk 3b1): a non-integer scale end is `invalid_scale`, never
  truncated by `int()`. **Web side fixed in 3b2**: the range is a preset or two bounded steppers
  (`ScaleEditor.test.tsx › opens two steppers for Vlastní, each bounded by the other, a decimal
  refused at the field`); no screen calls `setScaleEnd` any more.

- **Finding (3b2; for the docs PR to number). A tracked set labelled point by point tells its
  respondents and its map legend the wrong ends while the labels are off the prompt.**
  1. Claim: `SpecBattery.told_ends` is develop's reading, the first two labels as written, so a set
     whose `scale_labels` describe every point is told "1 = bod 1, 10 = bod 2".
  2. Anchor: `packages/aia_core/src/aia_core/domain/research_design.py:534 @ 25f26232`
     (`_develop_ends`), read at `ai_respondent.py:611-614` and `research_sociomapping.py:206 @
     25f26232` (the map's legend); the report reads `scale_labels` instead
     (`report_tables.py:96`, `report_design.py:61`).
  3. Reproduction: `test_ai_respondent.py::test_on_a_set_is_read_by_the_new_rule` asserts
     `told_ends == ("bod 1", "bod 2")` for a ten-point set.
  4. Consequence: had the editor offered every point on a set, respondents would rate on a scale
     whose top end reads as its second point, and the map's legend would say so. 3b1's review kept
     the reading byte for byte for stored designs; no screen could write a per-point set before 3b2.
  5. Smallest fix: read a set labelled exactly one per point (valid by the new rule) as its first
     and last label in `_develop_ends`, a set no stored design holds; or keep sets to two ends until
     3b3 turns the labels on. 3b2 does the second: the editor offers a set its two ends only.
  6. Test: the reproduction's assertion, flipped to `("bod 1", "bod 10")` with the first fix.

- **IA-8 (found and fixed in chunk 1). `Segmented` had no arrow keys.**
  `apps/web/src/components/rehome/step.tsx:139 @ e09a6c99`: every option was its own Tab stop and
  ←/→ did nothing, against I11 (roving tabindex). Repro and test:
  `step.test.tsx › Segmented is one Tab stop whose arrows move and choose (input-interactions I11)`
  fails on `e09a6c99`. Consequence: a keyboard user tabs through every option of every segmented
  control. Fix: `lib/roving.ts` (`rovingIndex`, `tabStop`) in `Segmented`, the same as ChoiceChips.

- **IA-4 fixed** (chunk 2): the knowledge search asks once typing pauses for 300 ms
  (`KnowledgeLibrary.test.tsx › asks the API once the typing pauses, never letter by letter`).
- **IA-6 moot in the knowledge library** (chunk 2): no select there acts on change any more
  (bulk, the open item, the label colour). Still a hypothesis for the intake sheet's
  "Přidat štítek" select (`IntakeSheet.tsx:339-355`), chunk 7's.

### CJ-1 (chunk 2): the client journey's bulk filing check passed without filing anything

1. **Claim.** The journey's "the ticked item is moved into the folder" check matched the item's own
   title, so it passed whether or not the item was filed.
2. **Anchor.** `tools/ui_workbench/client_journey.mjs:136 @ 25f26232`:
   `row.getByText(names.folder)`; `names.item` is `` `Cesta ${stamp}: pobočky` `` and `names.folder`
   `` `Cesta ${stamp}` ``, and Playwright's `getByText` matches a substring by default.
3. **Reproduction.** Remove the bulk "Přesunout do složky" step from the journey @ `25f26232`
   and run it: the check at line 136 resolves at once, on the title (the run fails only later, at
   the folder view). Once the folder is on the row, the same locator fails in strict mode (two
   elements), which is how it showed up here.
4. **Consequence.** The browser evidence for bulk filing proved nothing; a broken bulk move would
   have shipped green.
5. **Fix.** `{ exact: true }` on the folder and label checks (the journey on this branch).
6. **Test.** The journey itself: the strict-mode failure is now the signal, and the folder name is
   matched only as the filed cell says it.

### WT-1: the web suite timed out on a loaded machine (fixed on `fix/web-test-timeouts-under-load`)

1. **Claim.** `npm test` (Vitest) failed 3 to 24 jsdom component tests whenever the host was
   busy, because two time budgets were sized for an idle machine: vitest's 5 s per test and
   testing-library's 1 s per `findBy*` / `waitFor`. No test shared or leaked state: the pool
   isolates each file, every fake-timer user restores real timers, and every failing file
   passes alone.
2. **Anchor.** `apps/web/vitest.config.mts` @ e09a6c99 (no `testTimeout`, no setup file);
   `apps/web/src/components/rehome/research/steps.tsx:16-22` @ e09a6c99 (the step screens
   behind `next/dynamic`: a file's first lookup includes the module's transform and import).
3. **Reproduction.** `cd apps/web && npx vitest run` on a 4-core host already running other
   work. At load average ~7: 3 failed (MethodologyVersions 2, QuestionnaireStep 1). At ~13:
   24 failed in 9 files (MethodologyVersions 14, ResearchScreen 3, QuestionnaireStep 2,
   MethodologyPanel, SystemPromptsPanel, AudienceStep, BriefStep, ExecutionSteps 1 each).
   Two shapes only: "Test timed out in 5000ms", and a `findBy*` that found nothing after
   ~1.1-1.8 s. Evidence it is CPU, not the code: MethodologyVersions' heaviest test takes
   2.9 s alone and 9.1 s inside the suite; a CPU profile of that file is jsdom, its selector
   engine and React (~70 %) and garbage collection (14 %); Temml is under 1 %.
4. **Consequence.** `make test-web` was red on a developer's or agent's machine whenever the
   host was busy, so it had stopped being a signal there. CI (ubuntu-latest, 4 vCPU, nothing
   else running) was green at e09a6c99: the Frontend job runs the same `npm test`, 82 s.
5. **Fix.** One budget each, set once: `testTimeout: 30_000` in `vitest.config.mts` (the size
   `test-native-agents.ts` already gave the research steps) and
   `configure({ asyncUtilTimeout: 10_000 })` in the new `vitest.setup.ts`. The 4-6 s
   per-lookup overrides that had accumulated one at a time are removed: under the new default
   each would have been tighter than it. A first try at 4 s still failed one Metodika test at
   load 18 (the panel's first render had not appeared after 4 s), hence 10 s. Vitest's own
   `vi.waitFor` keeps its 1 s default, so ResearchScreen's four save waits name 10 s where
   they are written. Worker count left at vitest's default (cores - 1, 3 on CI's 4 vCPU): the
   contention came from outside the suite, and fewer workers would not remove it. No
   assertion changed; a lookup that never matches still fails, later.
6. **Test.** The suite itself, three consecutive full runs on the same loaded host (load
   average 17.2 -> 10.1 across them): 2448 of 2448 passed each time, in 290 s, 272 s and
   207 s. The slowest test of each run took 15.8 s (MethodologyVersions, "switches areas…"),
   8.3 s and 7.3 s (PersonaStep), inside the 30 s budget.

**Doc follow-up (CLAUDE.md §7 Known flakes), in §7's shape:**

```
- `apps/web` jsdom component tests (MethodologyVersions, MethodologyPanel, QuestionnaireStep,
  ResearchScreen, IntakeSheet, AudienceStep, BriefStep, ExecutionSteps, FieldOriginPanel,
  ObjectMapView, SystemPromptsPanel) — symptom: "Test timed out in 5000ms", or a findBy*
  that finds nothing after ~1 s, only while the host is loaded.
  Confirmation: passes when run alone. Cause: CPU starvation against idle-sized budgets
  (vitest 5 s per test, testing-library 1 s per lookup); no shared state. Fix or waiver:
  testTimeout 30 s (apps/web/vitest.config.mts), asyncUtilTimeout 10 s
  (apps/web/vitest.setup.ts); vi.waitFor keeps 1 s and names its size where it needs more.
```

### Doc follow-up (for the docs PR)

- **CLAUDE.md § 2, the map**, under `apps/web/src/components/`: add
  `ui/  The input standard's shared controls (input-interactions I1-I11): InlineText, Stepper,
  ChoiceChips, InlineCreateRow, SwatchPicker, MenuButton, UndoToast (useUndo), SpendDialog (the one
  modal for money: four kinds, four sums by name, the ceiling "horní mez, ne odhad", unknown never
  zero); parts.tsx: their shared classes, SaveNote, useDismiss`; and under `src/lib/`:
  `number-input.ts (a bounded number read, never clamped), name-input.ts (organizer_name /
  organizer_key at the row), roving.ts (arrow keys in a group), inline-edit.ts, spend.ts`.
- **AGENTS.md, a Testing Library entry** (Czech text):
  ```ts
  // WRONG -- never matches: the default normalizer turns U+00A0 into a space before it compares
  screen.getByText(/50–5 000/);
  // RIGHT -- read the element and compare its textContent, or pass { normalizer: (s) => s }
  expect(el.textContent).toBe("50–5 000 · ↑ ↓ o krok, Shift ×10");
  ```
- **open-items.md**: number IA-8 (closed by this PR) beside IA-1 … IA-7.

### Doc follow-up (3b2, for the docs PR)

- **CLAUDE.md § 2, the map**, under `src/components/rehome/research/`: add `ScaleEditor (a scale's
  range and labels on Dotazník: presets 1–5, 1–7, 0–10, 1–10 or Vlastní with two bounded steppers,
  the two ends or a label on every point edited in place, labels the server would leave out said,
  a range change that clears labels undone by "Vrátit"; a tracked set its two ends only)`; and under
  `src/research/`: `scale-labels.ts (a scale's range and labels, the server's rule at the field:
  presets, readRange, rescaleLabels, endsOnly, labelProblem)`.
- **CLAUDE.md § 3, the commands**, the `make ui-workspace` row: the journey also sets a 1–10 scale
  with a label on every point and reads it back after a reload.
- **open-items.md**: number the 3b2 finding above (a per-point set's ends as develop read them).

### Chunk 3, as delivered (the Dotazník screen owner, in small PRs)

- **3a. Deletes with undo (audit A17, A18), feature/questionnaire-undo-deletes.**
  - A question is removed at once, and "Vrátit" on the editor's one toast puts it back in its place.
  - A block or a tracked set keeps its InlineConfirm and is then removed, also with "Vrátit".
  - The restore helpers are `research/questionnaire.ts` `restoreQuestion` and `restoreSection`. A question goes back by its section's id, never into another section, and nothing is restored twice.
  - The toast is ScaleEditor's provider, shared through `useEditorUndo`.
  - Tests: `questionnaire-undo.test.ts`, `QuestionnaireUndo.test.tsx`, and the journey step in `questionnaire_journey.mjs` (1440 px).
  - Merged as #640; Vrátit outlives the preview tab and the last block's delete on the upload or AI path (the provider wraps the stage).
- **3b. Segmented and chips (A2, A11, A12), #645.** A question's type, its research questions and a comparison are `ChoiceChips`; a dangling research-question link keeps its ×. Test: `QuestionnaireChoices.test.tsx`.
- **3c. Quick adds inline (A5-A8, A21), #651.** A question, a block and a tracked set are added in their own `InlineCreateRow`s (the outline's quick add with "Typ nové otázky", "Nový blok", "Sledovaná sada", each block's "Otázka do tohoto bloku"); the AskDialog prompts are retired. Tests: `questionnaire-adds.test.ts`, `QuestionnaireStep.test.tsx`.
- **3d. Prices as chips (A16), #652.** A concept test's price bands entered one at a time, each checked as an amount; `ChipInput` takes `refuse`, keeping the draft with its reason. Tests: `questionnaire-prices.test.ts`, `QuestionnairePrices.test.tsx`.
- **3e. A block's name and purpose and a set's name in place (A4, part of A13), feature/questionnaire-fields-in-place.** `InlineText` on each: Enter or blur saves, Esc restores, the change written to the working copy at once and saved with it, the header saying the save (as Návrh's narrative); a name is required, a purpose may be emptied. Each block and set is also a heading (visually hidden), which `lead.ts` `titleOf` names it by. Tests: `QuestionnaireFields.test.tsx`; the journey renames a block and reads it back after a reload.
- **3f. A set's object type, goal and common question in place (the rest of A13), feature/questionnaire-set-fields-in-place.** The same `InlineField`; the common question refuses a draft without `{object}` at the field, in words (I9), and "+ {object}" still appends it to a stored question that lacks it. Tests: `QuestionnaireFields.test.tsx`.
- **3g. A question's wording and options (A1, A3), feature/questionnaire-wording-in-place.** The wording stays the card's always-open field (it is the card's content, and `lead.ts` `wordingOf` reads it): Esc puts back the wording as it stood when the field took focus. An option is removed at once with Vrátit, which puts that one option back in its place (`restoreOption`: the question found by its ids, a choice question only, other options edited since kept); its × is a 24 px target. Esc restores only while the wording is still what the field typed. Rows already add the next on Enter and save on leaving the group. Tests: `QuestionnaireFields.test.tsx`; the journey measures the × at four widths.
- **3h. The objects' count beside their list (A14), #693.** The header's "n / 4–15" was not enough: at 390 px it scrolls out of view while objects are added, and a sixteenth object was dropped without a word (`updateObjects` sliced at 15). The count moves from the card's header to beside the list's label, one count per card; `ChipInput` refuses an add in words, keeping the draft, and shows a reason only while it holds. Nothing is cut: a set stored above 15 keeps every object (the classic's cut is the one stated departure in `questionnaire.parity.test.ts`). The four limits are defined once, in `research/questionnaire.ts`. Tests: `QuestionnaireFields.test.tsx` (A14, a 17-object set); checked in a browser at 390 px.
- **After chunk 3 (tracked in `artifact-questionnaire.md`):** Q75 (a) made 15 a recommendation: 16–40 objects allowed and warned, the 41st refused, the count "n / doporučeno 4–15" (#736, QF-8). A block's create row adds to its block by id, and every create row is shut on a study the person may not edit (#734).

Chunk 3 is complete: 3a–3h are merged (#640, #645, #651, #652, #681, #687, #691, #693). Every questionnaire A-item in the audit's fix list is addressed; A15 and A20 were "keep", and A19's path cards are the toolbar's `Segmented`.

### Chunk 5, as delivered (the Cílová skupina screen owner, in small PRs)

Split by owner (PM, 2026-10-22): B1–B4 sit on Dimenze (`PersonaStep.tsx`), B5–B11 on Cílová skupina
(`AudienceStep.tsx`). Chunk 5 is ticked once B5–B11 are in and B1–B4 name Dimenze's PRs.

- **B1. n as one stepper:** Dimenze's `artifact-dimensions#DIM3` (`PersonaStep.tsx`, `data-aia="sample:n"`):
  bounded by `…/research/limits`, steps of 50, the recommendation beside it, no slider or presets, no clamp.
- **B2–B4:** Dimenze's, not yet scheduled here.
- **B5, B10:** kept, as the audit says (`RadioCard`; a prompt to AI is not a value).
- **B6. A numeric factor's range as two bounded steppers, feature/audience-range-steppers.**
  - Od and Do are `Stepper`s bounded by the catalogue's range (`research/audience.ts` `rangeBounds`):
    whole numbers when both ends are, else two decimals, the ends rounded outward. A scale whose ends
    the catalogue states (`scale_hint`) takes two decimals.
  - Each end is also bounded by the other, so a crossed range is refused at the field. The population
    would swap it (`_interval`).
  - An unset end reads "Bez omezení", and a set one clears by its own button. `setRange` takes numbers
    and leaves an unset end out.
  - A stored end the population cannot read (`boundOf`, `endUnreadable`) is said at the field, never
    shown as no end.
  - Tests: `AudienceStep.test.tsx` "a numeric factor's range is two steppers…" and "says a stored end
    the population cannot read…"; `audience.live.test.ts` "a numeric factor's range bounds".
  - `audience_journey.mjs` checks the range at 1440/1100/768/390: no overflow, the clear button at
    least 24 px, and 999 refused and not saved.
- **B7+B8, B9, B11:** to come, one PR each.

### Chunk 3b3, added by planning (2026-10-21)

3b1 built the label path behind `AIA_AI_SCALE_LABELS_IN_PROMPT`, off, and 3b2 is the editor; no
chunk switched the path on, so every scheduled chunk could finish with respondents still reading bare
numbers (Codex on #548). **3b3** turns it on for develop once the methodology owner (A. Bahbouh)
approves the wording rule, records the respondent-system fingerprint it moves to, and shows a develop
run whose respondents read the labels. It lands before any holdout confirmation
(`panel-grounded-respondents` 7f-7h) binds to a fingerprint.

