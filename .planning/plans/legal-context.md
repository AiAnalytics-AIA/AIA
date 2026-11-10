---
status: planned
chunks:
  - "[ ] LGL0. Scope and the disclaimer, written with the legal counsel the owner names: what AIA flags (tax, contract and employment law; Czech and EU), the report's \"not legal advice\" text, the researcher's acceptance of each legal point; recorded before any legal point reaches a study"
  - "[ ] LGL1. e-Sbírka and EUR-Lex as gate routes (public-data-routes): a provision fetched by its identifier in the version in force on a stated date, captured content-addressed, its licence and rate limits in the source register"
  - "[ ] LGL2. The legal point as a type: the law, the provision, the version date, the verbatim quote and its snapshot hash; a quote must be literally in the captured provision (Deep Research's grounding rule)"
  - "[ ] LGL3. Legal parameters and constraints: a point becomes a Předpoklady parameter (corporate tax rate, depreciation groups and methods, VAT, minimum wage, overtime premium, notice periods) or a Model constraint, each accepted by the researcher; the after-tax view (cost-model-study#CM7) reads them"
  - "[ ] LGL4. Version watch: a study's legal points re-checked against the version in force at the report's date; a changed provision marks the results that depend on it stale (deep-research-v2 DRV7, DRV8)"
  - "[ ] LGL5. The legal point in the report outline and the report: a kind and a grade of its own, the disclaimer printed wherever one is used"
  - "[ ] LGL6. The journey: the fictional Velis study's after-tax view from the cited corporate tax rate and depreciation provisions, and a notice period as a timing constraint, on recorded doubles; zero paid calls"
---
# Legal context: the law as cited parameters and constraints

Written 2026-11-02 on the product owner's words in the walkthrough: "we might need to incorporate some
legal context for this softare, as optiizing taxes and or contract law, employment law, we need perfect
understanding and recall of the legal environement". His answers the same day, recorded in
[ADR 0046](../../docs/architecture/adr/0046-business-decisions-pivot.md) W19 and decision 7:

- **Role:** cited rules and constraints. A legal point is a verbatim quote of a specific provision in the
  version in force on a stated date; it becomes a model parameter or a constraint a person accepts. AIA
  flags what applies and never gives legal advice.
- **Areas in the MVP:** tax, contract law, employment law.
- **Sign-off:** the researcher accepts legal points like any other finding; every report that uses one
  carries the disclaimer.
- **Jurisdictions:** Czech law (e-Sbírka) and EU law (EUR-Lex).

**What it cannot promise.** No system has perfect recall of the law. What this plan gives is narrower and
checkable: every legal statement is a quote of a provision, in a stated version, from the official source,
accepted by a named person, and re-checked when the version changes.

**Owner:** S2 (routes, capture, the type), with the legal counsel the owner names for LGL0. Proposed; the
session that takes it reviews this plan first.
