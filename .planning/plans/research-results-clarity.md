---
status: done
chunks:
  - "[x] 1. Readable results (e6d0fd5): the Data panel as searchable measure cards with each card's support and uncertainty and the compiled question wording; AI analysis outcomes (COMPLETED / BLOCKED / pending) apart from workflow step status, one module at a time, validation codes in a disclosure; Literature separates captured sources from accepted findings, a no-evidence run said plainly; the report with literature offered only over a complete analysis, its approval tied to the selected review's download"
  - "[x] 2. A reading layer (lib/result-reading.ts, pure): a measure read in words that never states an order the intervals do not support (audit F9's rule: an order only where 95 % intervals part; a missing interval is unknown, never an order); a set's objects compared on their mean with the top and bottom groups named; an analysis claim's evidence_ref resolved to its measure, metric and option; textBlocks: a model's long text as paragraphs and lists, every word kept"
  - "[x] 3. Data panel: cards in questionnaire order (the compiled specification's), each reading from chunk 2 with the scale it was asked on; per comparable set a comparison of its objects (sorted, interval bars on the set's scale, suppressed objects left out and named, the top and bottom groups in words); every card addressable as #measure-<id>, which opens the Data view, clears the filters and opens the card"
  - "[x] 4. AI analysis: Hlavní zjištění first -- every completed module's key findings together, each with its module and the numbers its claims cite (question, what was measured, value, orientační where indicative), each number linking to its card in Data; then every module's full text, formatted (textBlocks), its answers with their cited numbers; nothing the API returns is dropped"
  - "[x] 5. Literature: every word of the bundle shown, formatted: accepted findings with source, source class and quote; the draft synthesis (still labelled unapproved) as summary, findings each naming the accepted findings it rests on, gaps and limitations; every gap with its reason; every rejected finding with its reason and detail"
---
# Research results that read clearly

PR #403. Started by Codex (chunk 1, e6d0fd5); continued here at the product owner's request
(2026-10-14): "the idea is to make the results page more interpretable".

## Why

The owner (2026-10-14): keep all the raw text from the deep research and the AI analysis,
formatted to read better; the key findings are the most useful part.

A researcher on Výsledky has to answer three questions before reading any number: is this
number supported, is this difference real, and where did this sentence of the AI analysis
come from. Before this plan the page answered none of them in words:

- The aggregate listed questions by their ids, in the aggregate's key order, each a table.
- Chunk 1 added a one-line summary per card, but it names the largest share as "the most
  frequent answer" whatever its interval. On the test fixture's q2, Čaj 38,4 % (33,0–43,2)
  and Kávu 34,8 % (30,1–39,9) overlap, and the card still says Čaj wins.
- The AI analysis' findings cite claims by id (`C1 → q1.mean`) in a technical disclosure; a
  reader cannot see which number a sentence rests on without decoding the reference.

## Rules this plan keeps

- **Never state an order the intervals do not support.** Two estimates are ordered only when
  one's 95 % interval lies wholly above the other's: the rule the Sociomap engine already uses
  for objects (`domain/sociomap/metrics.py` `rank_with_ties`, RANK_WITH_TIES_RULE
  `audit-f9-rank-where-intervals-do-not-overlap-v1`). It is conservative: overlapping
  intervals do not prove equality, so the words are "nelze potvrdit", never "stejné".
- **Unknown is never good.** A missing interval makes the order unknown and the words say so.
- **Suppressed means no number**, in the reading as in the table; a comparison leaves a
  suppressed object out and says how many it left out.
- **Indicative is said every time** a number is indicative.
- **No text is lost.** Every word the API returns for the analysis and the deep research is
  on the page; formatting splits and groups it, never shortens or rewrites it.
- **Presentation only.** No aggregate, support rule, admission, analysis or report changes.
  The reading layer reads the stored aggregate and specification; nothing is written.

## Progress notes

- Chunk 1 (Codex, e6d0fd5): 52 focused results tests, 1,438 web tests, tsc, eslint, webpack
  build (its commit message). Its card summary is replaced by chunk 2's reading.

- Chunks 2-5 (2026-10-14, this session): `lib/result-reading.test.ts` (23: separation,
  readMeasure incl. the overlapping-leader case, compareObjects, citedMeasure, textBlocks keeping
  every word and a line-leading date); ExecutionSteps.test.tsx "opens data with pinned question
  wording…" (questionnaire order, the overlap reading), "compares a set's objects in words and on
  one scale, and opens a card from its link", "puts every module's key findings first…", "shows
  every word of the review, formatted…". Web 1,464 tests, tsc, eslint clean.

## Findings

- **F1 (hypothesis: not reproduced on demand).** `ResearchScreen.test.tsx` "keeps one study
  session while each step's page mounts afresh, as Next mounts them" failed once in a full
  `npx vitest run` (role="list" "Kontrola připravenosti" not found) and passed alone twice and in
  the next full run. Likely a default 1 s `findBy` under full-suite load. Not in this plan's
  code. Reproduce under load before budgeting a fix.

## Doc follow-up

- CLAUDE.md § 2 map, apps/web: `src/lib/result-reading.ts  How a run's results read in
  words: readMeasure (a measure's reading; an order only where 95 % intervals part, audit
  F9; unknown never ordered), compareObjects (a set's objects on their mean, top and bottom
  groups), citedMeasure (an analysis claim's evidence_ref resolved to its measure), textBlocks (a model's
  long text as paragraphs and lists, every word kept)`.
- CLAUDE.md § 2 map, rehome/research: ExecutionSteps' Data view "measure cards in
  questionnaire order, each read in words, a comparison per set, #measure-<id> opens one";
  the analysis view "Hlavní zjištění across modules first, each answer and finding with the
  numbers it cites, linked to Data"; InterpretationResearch "the bundle in full: accepted
  findings, the draft synthesis by section, gaps with their reasons, rejected findings with
  theirs".
