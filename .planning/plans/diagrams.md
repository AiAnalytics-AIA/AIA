---
status: planned
chunks:
  - "[ ] DG0. The spike, before any dependency is added: every MVP visual type in the coverage table below rendered server-side through its proposed engine, on fictional data, with IBM Plex, the design tokens' palette and Czech number formats (7,2 %, 41 000); bytes equal on a second render; each engine's licence and the map boundaries' data licence read and recorded; all six stacks are in the MVP (ADR 0046 A13, \"All six in MVP\"), so the spike proves each for its types and reports a type it cannot render, never dropping a stack (no product code, zero paid calls)"
  - "[ ] DG1. The visual as a type: kind (chart, diagram, table, framework template), engine, spec, a source reference on every element that states a fact or a number, alt text and long description, spec version; validated per engine (the Vega-Lite and Vega schemas, the Mermaid parser, bpmn-moddle against BPMN 2.0, the template's own schema) before anything is shown; one fixture read by Python and TypeScript"
  - "[ ] DG2. The renderer in the worker: deterministic SVG and PNG from a stored spec (vl-convert for Vega-Lite and Vega; Graphviz; a pinned headless renderer for Mermaid, bpmn-js and ECharts, refused by name when absent); fonts and palette from the tokens; stored as artifacts keyed by the spec's hash; the same spec renders the same bytes"
  - "[ ] DG3. Charts on Vega-Lite and Vega: every chart type of the coverage table as a tested preset (forest plot, tornado, waterfall, fan chart, Gantt, heat map, strategy canvas, quadrant bubble matrix, treemap, radar, choropleth and flow map), each number a reference; Sankey and chord on ECharts only if DG0 finds Mermaid's Sankey insufficient"
  - "[ ] DG4. Process and system diagrams: BPMN 2.0 (pools, lanes, gateways, events) on bpmn-js; flowchart, state, sequence, entity-relationship, mind map, timeline, Gantt, C4 and Sankey on Mermaid; data-flow diagrams, causal loops with polarity and decision trees on Graphviz; free node diagrams on React Flow with elkjs layout"
  - "[ ] DG5. Framework templates: typed data drawn by AIA's own deterministic SVG layout, one template per shape (SWOT 2×2, PESTEL six factors, Porter's five forces, Ansoff 2×2, value chain, McKinsey 7S, business model canvas, ERRC grid, Ishikawa, DuPont tree, SIPOC, capability map, current and target state); BCG and GE-McKinsey drawn as DG3 quadrant charts"
  - "[ ] DG6. Tables as one typed spec: plain, cross-tab, matrix (RACI), heat table, comparison with conditional marks, financial statement with indented subtotals; every cell a reference; the same table on screen (TanStack Table) and in the DOCX (report_docx tables)"
  - "[ ] DG7. The Lead's visual tools: it proposes a visual as a typed spec, per change, through the edit vocabulary (ADR 0026); the spec is validated before the researcher sees it; a number enters only as a reference it was given, never typed by the model; read tools for the visuals that exist"
  - "[ ] DG8. Editors on screen: the bpmn-js modeller, Mermaid text with a live preview, a chart form over the Vega-Lite spec, a form per framework template, React Flow for free node diagrams; every edit a working-copy operation, revision-checked"
  - "[ ] DG9. Into the report: each figure from its stored render, never browser bytes (the map snapshot's rule, report-delivery RD4); caption with its sources, alt text, numbered with the outline; the X-ray links each element to its source (research-findings-stage FND2)"
  - "[ ] DG10. Accessibility and the design system: alt text and a long description on every visual, the palette's contrast and colour-vision checks (scripts/check-design.mjs) extended to diagram and template colours, print sizes for the DOCX"
  - "[ ] DG11. After the MVP: ArchiMate notation (no open-source web renderer found; a symbol set on React Flow, or Archi's exchange format), value stream maps, customer journey maps, Sociomap-style overlays on diagrams"
---
# Diagrams, charts and tables the Lead can draw

Written 2026-11-02 on the product owner's request, in the PM coordinator's chat: "we need to be able to
draw bpmn diagrams, data flow diagrams, state diagrasm, any type of graph, and table. is there an
opensource tool that we can use and implement for the lead researcher to be able to control". On the
proposed stack: "sounds good, do one more control round to ensure this plan covers all the types of
diagrams we want".

**The rule.** The Lead never draws pixels:
1. It writes a typed spec (BPMN XML, Mermaid text, a Vega-Lite or Vega JSON, a framework template's
   data), with a source reference on each element that states a fact.
2. Code validates the spec.
3. The researcher accepts it per change.
4. The server renders it deterministically for the report.

This is the report X-ray's rule ([ADR 0046](../../docs/architecture/adr/0046-business-decisions-pivot.md)
decision 3) applied to visuals: `research-findings-stage` FND4-FND6 and `analysis-frameworks` AF6 build on
this plan.

**Owner:** S1 (editors and the Lead's tools) and S2 (specs, renderer, report). Proposed; the session that
takes it reviews this plan first.

## The engines

| Engine | Licence (to be confirmed in DG0) | Renders server-side | Used for |
|---|---|---|---|
| Vega-Lite / Vega + vl-convert | BSD-3 | yes, no browser | charts |
| Mermaid | MIT | headless browser | flow, state, sequence, ER, mind map, timeline, Gantt, C4, Sankey |
| bpmn-js + bpmn-moddle | bpmn.io licence (logo stays visible) | headless browser | BPMN 2.0 |
| Graphviz | EPL | yes, binary | data flow, causal loops, decision trees, large graphs |
| React Flow + elkjs | MIT / EPL-2.0 | through the renderer | free node diagrams, editing |
| ECharts | Apache-2.0 | yes (its own SSR) | Sankey and chord, only if needed |
| AIA templates | ours | yes, Python and React | framework-shaped visuals |
| TanStack Table + report_docx | MIT / ours | yes | tables |

**Avoided:**
- tldraw and GoJS, which are commercial licences.
- draw.io: Apache-2.0, but a whole app in an iframe, and its BPMN shapes carry no BPMN semantics.

## Coverage: every visual the MVP asks for

The control round's sources:
- the owner's list;
- the 42 frameworks of `analysis-frameworks`;
- the charts already drawn on the prototype's M boards;
- the X-ray's visuals.

**Status:** MVP, or after the MVP (DG11).

| Visual | Asked by | Engine | Status |
|---|---|---|---|
| BPMN process (pools, lanes, gateways, events) | the owner; SIPOC, gap analysis, operating model | bpmn-js | MVP |
| Data-flow diagram | the owner; systems and data flows | Graphviz, or React Flow + elkjs | MVP |
| State diagram | the owner; order and return lifecycles | Mermaid | MVP |
| Flowchart, decision tree | process maps, the X-ray's plan of execution | Mermaid / Graphviz | MVP |
| Sequence diagram | integrations with the 3PL | Mermaid | MVP |
| Entity-relationship diagram | data contracts, systems | Mermaid | MVP |
| C4 / system context | enterprise architecture | Mermaid (C4) | MVP |
| Mind map | PESTEL drafts, issue trees | Mermaid | MVP |
| Timeline, roadmap, Gantt | plan of execution, pilot | Vega-Lite / Mermaid | MVP |
| Causal loop diagram | Sociomapa systémů's reading, drivers | Graphviz | MVP |
| Organisation and ownership chart | ownership and group structure, RACI | Mermaid / Vega tree | MVP |
| Bar, grouped, stacked, 100 %, diverging | everywhere | Vega-Lite | MVP |
| Line, area, cumulative | cash flow, forecasts | Vega-Lite | MVP |
| Forest plot (median and interval) | Rozhodnutí | Vega-Lite | MVP |
| Tornado | sensitivity | Vega-Lite | MVP |
| Break-even lines with crossings | CVP, bod zvratu | Vega-Lite | MVP |
| Histogram, density, box plot | Monte Carlo distributions | Vega-Lite | MVP |
| Fan chart (forecast bands) | demand forecast against capacity | Vega-Lite | MVP |
| Waterfall / bridge | plan against actual, P&L bridge | Vega-Lite | MVP |
| Scatter and bubble with quadrants | BCG, GE-McKinsey, benchmark | Vega-Lite | MVP (portfolio frameworks after) |
| Heat map | risk register (likelihood × impact), cost-to-serve | Vega-Lite | MVP |
| Strategy canvas (value curves) | Blue Ocean | Vega-Lite | MVP |
| Pareto | ABC/XYZ | Vega-Lite | MVP |
| Pie, donut | shares (used sparingly) | Vega-Lite | MVP |
| Small multiples | any comparison by option | Vega-Lite | MVP |
| Choropleth and flow map of Czech regions | cost-to-serve by zone, network and location | Vega-Lite + TopoJSON (boundary data licence in DG0) | MVP |
| Treemap, sunburst | market structure, cost structure | Vega | MVP |
| Radar | option profiles | Vega | MVP |
| Network graph | ownership links, supplier network | Vega / Graphviz | MVP |
| Sankey | cost flows, order flows | Mermaid, else ECharts (DG0 decides) | MVP |
| SWOT 2×2 | SWOT | template | MVP |
| PESTEL six factors | PESTEL | template | MVP |
| Porter's five forces | Porter | template | MVP |
| ERRC grid | Blue Ocean | template | MVP |
| Ishikawa (fishbone) | bottlenecks, risk causes | template | MVP |
| DuPont tree | ratios and DuPont | template | MVP |
| SIPOC | process map | template | MVP |
| Capability map | enterprise architecture | template | MVP |
| Current and target state | gap analysis | template | MVP |
| Ansoff 2×2, value chain, McKinsey 7S, business model canvas | portfolio frameworks | template | after the MVP |
| Tables: plain, cross-tab, RACI matrix, heat table, comparison, financial statements | everywhere | typed table spec | MVP |
| ArchiMate notation | enterprise architecture, if required | none found | after the MVP |
| Value stream map, customer journey map | operations, customers | template | after the MVP |
| Sociomap terrain and maps | Sociomapa systémů | its own engine (not this plan) | MVP, `sociomapa-systemu` |

**What the control round added:**
- **The framework templates (DG5).** Generic diagram tools draw SWOT, Porter, 7S and the value chain
  badly. A fixed layout from typed data is more readable and easier to check.
- **Maps of Czech regions,** whose boundary data needs its licence recorded.
- **Causal loops,** which Sociomapa systémů's reading needs.
- **The financial statement table,** with indented subtotals.

**What it leaves after the MVP:** ArchiMate notation, value stream maps and customer journey maps.
