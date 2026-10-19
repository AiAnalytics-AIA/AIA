---
status: in-progress
chunks:
  - "[x] 1. Class rules in one module, read by the design agents and the Research Lead; provenance names each part's source"
  - "[ ] 2. Fieldwork and analysis classify a run's design by the same rule (Deep Research and validation checked)"
  - "[ ] 3. A client source marked \"Interní dokument\" (who, when, audited): Class C for its AI proposals; API and source card"
  - "[ ] 4. ADR 0008 and ADR 0010 amendments: the owner's class rules; develop's EU route may carry A, B and C"
  - "[ ] 5. Runbook: the AI route parameters for A, B and C, with the commands that set them"
---
# Usable classification

**Status:** in progress · **Drafted:** 2026-10-19 · **Branch:** `feature/usable-classification`
from `develop` @ `6c5cd620`

## Decision (the product owner, 2026-10-19)

A model request classified a study's design, its name and the Research Lead's chat messages only by
an operator's exact-bytes approval (`AIA_AI_MATERIAL_CLASSIFICATIONS`); anything else was unknown
and refused (`egress_unclassified_material`). The Research Lead and the AI design jobs could never
run on an edited design (OI-126). The owner decided:

| Material | Class |
|---|---|
| Methodology texts, AIA's own prompts, public sources | C (unchanged) |
| A study's design (brief, research questions, questionnaire, audience, the attachment excerpts the design carries) and the study's and client's names | **B by rule**: derived client information |
| A researcher's chat message and focus label to the Lead, in a study | **B by rule**: takes the study's class |
| The Lead's personal notes and its SOUL/USER files and name | **C by rule** (they change only on the researcher's explicit "Pamatovat si") |
| The Lead's client-scoped notes | A (unchanged) |
| Approved client knowledge | A (unchanged) |
| Client uploaded sources/datasets | A, **unless a person marks a source "Interní dokument"**, which makes it C |
| Anything no rule covers | still refused: ADR 0008's fail-closed rule stays |

An operator's exact-bytes approval still works and can only make a class stricter, never looser,
as `prompt_data_class` takes the most restrictive of a declaration and an operator classification.

## Chunks

1. **Class rules.** One module names each rule and its class; `agent_request` and
   `context_data_class` read it; `most_restrictive_material` still lets knowledge and client notes
   raise a request to A. Executors record each part's class and source (`rule:<name>`,
   `operator`, `declared`).
2. **Fieldwork, analysis, Deep Research.** The same rule where a run's design is sent to a model,
   and only there. Licence and residency gates untouched.
3. **"Interní dokument".** `client_sources.internal_marked_by` / `internal_marked_at`; audited;
   `PUT /clients/{id}/sources/{source_id}/internal`; the source card's toggle; a marked source's AI
   proposals go as Class C.
4. **ADR amendments.** ADR 0008 (the rules; unknown still refuses; a rule is the code's and the
   owner's decision, never a default) and ADR 0010 (develop's EU route may carry A, B and C once an
   operator sets the parameters and the account's retention is confirmed).
5. **Runbook.** `deploy/develop/README.md`'s AI parameter table and the commands that set it.

## Findings

(filled in as chunks land)

## Doc follow-up

(filled in as chunks land)
