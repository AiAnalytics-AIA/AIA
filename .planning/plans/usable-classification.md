---
status: done
chunks:
  - "[x] 1. Class rules in one module, read by the design agents and the Research Lead; provenance names each part's source"
  - "[x] 2. Fieldwork and analysis classify a run's design by the same rule (Deep Research and validation checked)"
  - "[x] 3. A client source marked \"Interní dokument\" (who, when, audited): Class C for its AI proposals; API and source card"
  - "[x] 4. ADR 0008 and ADR 0010 amendments: the owner's class rules; develop's EU route may carry A, B and C"
  - "[x] 5. Runbook: the AI route parameters for A, B and C, with the commands that set them"
---
# Usable classification

**Status:** done · **Drafted:** 2026-10-19 · **Branch:** `feature/usable-classification`
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

**F1. Deep Research cannot take the design rule without losing every web track.** (Decision
needed; not changed here.)

1. *Claim.* Deep Research's plan step classifies a run's design by the operator's exact-bytes
   record alone and gives every web query that class; its web routes carry Class C only. Raising
   every design to Class B by rule, with an operator unable to lower it, would refuse every web
   track of every run, the synthetic fixtures an operator classified Class C included.
2. *Anchor.* `apps/executors/src/aia_executors/deep_research/plan.py:163` (the classification)
   and `:260` (`gate.refusal_for_class(dclass)`) @ `6c5cd620`;
   `apps/executors/src/aia_executors/deep_research_live.py:115` and
   `deep_research_recorded.py:69` (`approved_for=frozenset({DataClass.CLASS_C_INTERNAL})`) @
   `6c5cd620`.
3. *Reproduction.* Replace the plan step's `classify_material(...)` with
   `classify_by_rule(..., MaterialRule.DESIGN, ...)` and run
   `pytest apps/executors/tests/test_deep_research_journey.py`: the web tracks are blocked
   `SEARCH_ROUTE_REFUSED` (hypothesis on the exact count; the gate's rule at
   `packages/aia_core/src/aia_core/application/web_retrieval.py:618-632 @ 6c5cd620` is not).
4. *Consequence.* Today a Deep Research run on an edited design still parks
   (`egress_unclassified_material`) unless an operator classifies its bytes.
5. *Smallest fix.* The owner decides whether a query a model writes from a Class B design may be
   sent to a Class C search route (a query class of its own, by rule), or whether Deep Research
   stays operator-classified.
6. *Test.* `test_deep_research_journey.py` with a design classified by rule.

**F2. Validation arms keep the operator's classification.** `validation.py:265 @ 6c5cd620`
classifies the confirmation's specification, built from the public item bank, not a study's
design (`holdout/bank.py`). The rule covers a study's design only, so this is unchanged.

**F3. The Lead's `runs` and `study` budget layers are sent unclassified.** Observed, not changed:
`freeze_context` puts the runs' ids and statuses and the study's budget numbers into the context
(`packages/aia_core/src/aia_core/domain/research_lead.py:761-763 @ 6c5cd620`,
`application/research_lead.py:826 @ 6c5cd620`) and `context_data_class` never classified them.
They are AIA's own state, not client material, so nothing is owed; a hypothesis until someone
finds client text there.

**F4. Analysis records the design's class source only where it parks.** The module's turn
artifact is a closed contract (`domain/analysis/artifact.py:269 @ 6c5cd620`); adding the source
there is a contract version of its own. A park's error carries `design_class` (`data_class`,
`source`); a completed module's ledger rows carry the class.

**F5. A marked source's mark is now checked per request and kept per answer** (fixed on this
branch, after review of #487). A person who unmarks a source mid-run stops the requests not
yet sent (`source_class_changed`; `ClientSourceRepository.marked_internal`, read before each
request); each journaled answer keeps the class it was sent as (`class_source`), so a replay
after the mark changed is recorded under its own class (test
`test_a_replayed_answer_keeps_the_class_it_was_sent_as_when_the_mark_changes`); marking locks
the row (test `test_a_mark_and_an_unmark_sent_together_end_in_the_state_the_later_one_answered`,
PostgreSQL).

**F6. An operator's exact-bytes classification of a source batch raises it** (fixed on this
branch; Codex and an independent review of #487). `batch_classification` classifies what a batch
sends by the source's rule and the operator's record, the most restrictive winning, as every
other rule-classified request; the step's configuration carries the worker's
`material_approvals` (`SourceProposalsConfig.from_settings`, the one constructor the registry and
the tests share). Tests:
`test_an_operator_classification_raises_a_marked_batch_and_never_lowers_one`,
`test_an_operator_classification_keeps_a_marked_batch_off_a_route_for_class_c`.

**F7. AI output written into the design is Class B by the design rule** (a question for the
product owner). A design job's request is Class A when the client has approved knowledge (its
snapshot carries it), and what it writes into the study -- the brief analysis, an accepted
questionnaire -- is then design, Class B, in later requests
(`domain/research_lead.py` `_part("design_analysis", …, MaterialRule.DESIGN)`;
`ai_fieldwork.py`, `analysis.py` `classify_by_rule(design, MaterialRule.DESIGN)` @ `6de30744`).
The owner's table names the brief, research questions, questionnaire, audience and attachment
excerpts; whether AI-derived design text from Class A knowledge is B ("derived client
information") or keeps A is the owner's to confirm. Brief attachment excerpts (a client's
file) are B as design, while the same bytes as a client source are A: consistent with the
decision as written, to confirm with it.

## Doc follow-up

For the docs PR (CLAUDE.md §1); anchors are on this branch's commits.

**CLAUDE.md § 2, the map.**

- Under `domain/`, after `ai_contracts.py`: "`material_rules.py` -- the class a study's material
  takes by rule (the product owner, 2026-10-19; ADR 0008 amendment): a design, the study's names
  and a researcher's messages, focus labels and job instructions Class B; the Lead's files and
  personal notes C; client notes, approved knowledge and a client's sources A; a source a person
  marked "Interní dokument" C. `classify_by_rule`: an operator's exact-bytes classification can
  only raise a rule (source `rule:<name>` or `operator`); material no rule names still refuses."
- `domain/research_agents.py`: append "a design and a nonempty instruction classified by rule
  (`design_classification`, `instruction_classification`); `prompt_class_source`".
- `domain/client_sources.py`: append "`InternalMark` (who and when a person marked a source
  "Interní dokument")"; `domain/source_proposals.py`: "`proposal_request(…, internal=)`: Class C
  for a marked source, else A".
- `routers/` client_sources: add "PUT …/{source_id}/internal (`{internal: bool}`): mark a source
  "Interní dokument" or unmark it, PROPOSE_CLIENT_KNOWLEDGE, audited; every source answers
  `internal: {by, at} | null`".
- `infrastructure/client_source_repository.py`: append "`mark_internal`: who and when on the row
  (`internal_marked_by`, `internal_marked_at`, migration c7e9a1b3d5f2), each change audited
  (`CLIENT_SOURCE_MARKED_INTERNAL` / `…_UNMARKED_INTERNAL`)".
- `components/aia/clients/SourceFile.tsx`: "SourceCard: the "Interní dokument" toggle (what it
  does; who marked it, when)".
- `aia_executors/ai_fieldwork.py`, `analysis.py`: "the run's design classified by rule
  (`rule:design`)"; `client_source_proposals.py`: "a marked source's requests Class C, each
  proposal recording `data_class` and `class_source`".
- § 2's "A research run executes a Design Revision" paragraph: the classes of its material come
  from `material_rules.py`, not from an operator's hash alone.

**`.planning/open-items.md`.**

- **OI-126** (How is Research Lead chat material classified on develop?): **answered** by the
  product owner, 2026-10-19: a chat message and focus label take the study's class (B), the
  design and names are B, the Lead's files and personal notes C, client notes A
  (`packages/aia_core/src/aia_core/domain/material_rules.py:78` @ `bc1cd3fc`,
  `domain/research_lead.py:835` `context_classification` @ `bc1cd3fc`; test
  `test_the_design_names_and_a_message_are_class_b_by_rule_with_no_operator_step`). The Lead
  answers on develop once the route carries Class B with its retention stated
  (`deploy/develop/README.md` § AI route classes). Close it.
- New, from F1: "Deep Research's design classification under the owner's rules" (a question for
  the product owner), with F1's six parts.

**`docs/architecture/adr/README.md`.** ADR 0008 and ADR 0010: "amended 2026-10-19".
