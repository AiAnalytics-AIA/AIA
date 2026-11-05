---
status: planned
chunks:
  - "[ ] DB0. The business Zadání as data: the eight parts (decision and goal; options and constraints; rule and risk; customers; data and uncertainties; execution and output; analyses, through analysis-frameworks; the model's parts), each with its source citation and the step it hands to; the decision core's fields and the model switch \"Potřebuje rozhodnutí výpočet?\"; revision-checked on the study's working copy (artifact-brief, working-copy-edit-ops); one fixture read by Python and TypeScript"
  - "[ ] DB1. Popis (board Z1): the one required field, files kept as the client's sources in the study's Vstupy folder (study-files#SF6), Ada's \"Co ještě pomůže\" suggestions; a missing file stays an open item and later becomes a wide-range assumption"
  - "[ ] DB2. Triage as an ordinary Lead turn (board Z2): the eight parts proposed with their sources, each accepted, edited or dropped (ADR 0026); options Ada adds marked as hers; every question that matters, ordered by importance, the first three open and the rest under \"Další otázky (n)\" (W2); each question's reason in words, never a crown amount (W3)"
  - "[ ] DB3. The decision core (board Z3): decision, owner, deadline and goal; options and constraints, which become the model's variants; the rule (measure, threshold, risk limit) recorded before the first computation, any change recorded and marked in the report (cost-model-study#CR7, M-4); objectives that each serve the decision; how certain the answer must be; the model switch, Ada proposing and the researcher confirming, the model steps shown only on yes (W4)"
  - "[ ] DB4. Readiness R1-R7 (board Z7): R1-R5 checked by code and holding the hand-off, R6-R7 the Lead's advice holding nothing; chips under the stage header, each opening its detail"
  - "[ ] DB5. The hand-off: what Data, Předpoklady, Model and Zpráva take over, each as a proposal, nothing overwritten; a later edit of Zadání offered to the steps downstream as a proposal"
  - "[ ] DB6. The journey: the fictional Velis brief from one sentence to its hand-off at 1440, 1100, 768 and 390 px on the scripted Lead; zero paid calls"
---
# The business Zadání: a decision that can be tested

Written 2026-11-02 on the product owner's walkthrough of the canvas "AIA Obchodní model – prototyp"
(boards Z0-Z7), recorded in [ADR 0046](../../docs/architecture/adr/0046-business-decisions-pivot.md)
§ The owner's walkthrough (W1-W5). Before this plan the business Zadání existed only on the canvas; the
repository had its pieces (`artifact-brief`, `cost-model-study#CR7`, `analysis-frameworks#AF2`,
`study-files#SF6`) and no plan that builds the stage.

**Owner:** S1 (the stage and the Lead's triage) with S4 (the rule and the model's parts). Proposed; the
session that takes it reviews this plan first.

## What the stage does

Zadání turns a client's loosely worded problem into a decision that can be tested before any data or
computation, and hands each later step exactly what it needs. Six sub-steps: Popis, Triáž, Rozhodnutí,
Analýzy, Model (only with a model) and Připravenost.

## Rules

- **Models propose, a person accepts.** Ada proposes parts, options and questions; nothing is accepted on
  its own.
- **The rule comes first.** The measure, threshold and risk limit are recorded before the first
  computation, and the report says which way the result fell.
- **No number Ada made up.** Triage gives its reasons in words; a value of information in Kč appears only
  on Výsledky, computed by the model (W3).
- **The model only when needed.** The model steps and the Model sub-step appear only when the decision
  core says a computation is needed (W4).

## What is reused

- `artifact-brief`'s working copy and edit operations (`working-copy-edit-ops`).
- `cost-model-study#CR7`, the decision rule.
- `analysis-frameworks#AF1`-`#AF2`, the framework picker on board Z4.
- `study-files#SF6`, files kept as the client's sources.
