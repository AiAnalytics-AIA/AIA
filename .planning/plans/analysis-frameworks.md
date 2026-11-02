---
status: planned
chunks:
  - "[ ] AF0. The catalogue as data: every framework with its id, group, the question it answers, how it is produced (computed by code, cited Deep Research points, synthesis, named experts), its inputs (client data, Deep Research, experts), its grade, its X-ray chapter kind and its MVP flag; versioned, one fixture read by Python and TypeScript; a framework point is a typed reference (an accepted finding, an admitted client-data claim, a model result, an expert's score), never free text (W1)"
  - "[ ] AF1. The default sets: decision type to the frameworks Ada proposes, as data the owner approves; the Lead proposes a set with one reason per framework, the researcher accepts per change (ADR 0026); a framework that needs register fields naming persons is never proposed before its balancing test (W2)"
  - "[ ] AF2. The Zadání picker (prototype board Z4): the groups, a toggle per framework, what each needs, the Deep Research cost ceiling of the selection, the X-ray chapters and the expert forms it creates; saved on the study's working copy; post-MVP frameworks shown and disabled (W2)"
  - "[ ] AF3. The selection drives Deep Research: each framework that needs research becomes subjects of the Design Research plan, its ceiling pinned at enqueue; a deselected framework takes its subjects out of the next run (W2, after deep-research-v2 DRV0)"
  - "[ ] AF4. The selection drives the model: each computed framework switches on its view on Výsledky (Finance, Účetnictví, Provoz, Logistika, Trh) through cost-model-study and quantitative-families; a framework whose data contract is missing says which file it waits for (W3)"
  - "[ ] AF5. The selection drives the experts: each expert-scored framework (the Blue Ocean strategy canvas, the risk register, RACI, the architecture frameworks) creates a scoring form for named raters, through situation-reports EX1's expert panel (W3)"
  - "[ ] AF6. The selection drives the report X-ray: each framework a chapter or a part of one, with its point slots (SWOT's four quadrants, PESTEL's six factors, Porter's five forces); a point without a resolving source link is refused (research-findings-stage FND2) (W2)"
  - "[ ] AF7. Logistics frameworks: cost-to-serve, make-or-buy and 3PL total cost of ownership, network and warehouse location (centre of gravity), service level and OTIF, transport cost by zone, warehouse sizing, each computed by code from client data under its contract and public inputs (W3)"
  - "[ ] AF8. Corporate governance and enterprise architecture frameworks: ownership and group structure (after register-personal-data RPD2), RACI, risk management (COSO ERM, ISO 31000), compliance obligations, internal control; the capability map, current and target state with the gap, systems and data flows, the operating model; expert-scored or cited, never written by a model (W3)"
  - "[ ] AF9. The journey: a fictional study picks its frameworks in Zadání and gets an X-ray with SWOT, PESTEL, Porter, TAM/SAM/SOM and cost-to-serve chapters, every point linked to its source; recorded doubles, zero paid calls (W4)"
  - "[ ] AF10. After the MVP: the portfolio frameworks (Ansoff, BCG, GE-McKinsey, VRIO, value chain, McKinsey 7S) enabled in the picker"
---
# Analysis frameworks: chosen in Zadání, each point with its source

Written 2026-11-02 on the product owner's request, in the PM coordinator's chat:

> "In the zadani step, i want the user to be able to chose whether to include SWOT, PESTEL, BLUE OCEAN.
> TAM SAM SOM, and any and all relevant business/ operations/ accounting frameworks for the deep
> research and lead researcher to include into the report. lets analyze what all types of analysis we
> want to include"

**His answers the same day:**
- The groups are strategy and market, finance and accounting, operations, and portfolio (later), and he
  added "Corporate givernance, and corporate architecture frameworks, logistics too".
- Qualitative frameworks take "Sourced points only".
- How the frameworks are picked: "Ada proposes per decision".

The design is drawn on the "AIA Obchodní model – prototyp" canvas: Z4 (the picker) and MV6 (the
catalogue, 42 frameworks in seven groups, 36 in the MVP). The X-ray's SWOT chapter on MV4 is the worked
example. The rule behind it is
[ADR 0046](../../docs/architecture/adr/0046-business-decisions-pivot.md) decision 3.

**Owner:** S1 (the picker and the Lead's proposal), S2 (Deep Research and the computed frameworks) and
S4/S5 (the model views). Proposed; the session that takes it reviews this plan first.

## The rule

A framework point is a reference, never prose. It is one of four things:
- a Deep Research finding with its quote;
- a client-data number under an accepted contract;
- a model result with its method version;
- a named expert's score.

The Lead proposes and sorts points; it never writes one without a source. The X-ray refuses an
unsourced point, so it cannot reach the report.

## Out of the MVP

These are customer-voice methods (Kano, conjoint, NPS, willingness to pay). They need respondents, and
the survey lane is frozen (ADR 0046 decision 2). What client data shows (cohorts, customer value, price
response) is in the finance and operations frameworks.
