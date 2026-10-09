---
status: in-progress
chunks:
  - "[x] 0. This plan"
  - "[ ] 1. Sign-off: design, Brave and its written terms, D8, budgets, the light model, quotas"
  - "[x] 2. Structured output with thinking on (no forced tool choice) for Deep Research agents"
  - "[x] 3. Brave search adapter"
  - "[ ] 4. The search key as a credential reference"
  - "[x] 5. Public-web fetch: any public host, robots.txt, links, run snapshot cache"
  - "[ ] 6. Documents: PDF, XLSX, CSV, read in parts, tables kept as tables"
  - "[x] 7. Measures: every number with its unit, scale, period, geography, population, denominator"
  - "[ ] 8. Source tiers and the reputation register"
  - "[x] 9. The investigator: parallel actions, refs, refusals, transcript"
  - "[x] 10. The acquisition ladder: every lawful way to reach a needed source"
  - "[x] 11. The lead researcher: effort scaling, delegation, waves, re-planning"
  - "[x] 12. Verification: adversarial verifiers, primary tracing, triangulation, conflicts"
  - "[x] 13. Confidence by code, gaps, acquisition gaps, the brief"
  - "[x] 14. Connectors I: ČSÚ DataStat and the national open-data catalogue"
  - "[x] 15. Connectors II: Eurostat, OpenAlex, Wayback CDX"
  - "[x] 16. Connectors III: ARES (legal entities), public procurement"
  - "[x] 17. Focused crawler for authoritative hosts"
  - "[x] 18. Common Crawl URL index and archived pages"
  - "[x] 19. Code filters: near-duplicates, language, relevance"
  - "[x] 20. Triage readers on the light model"
  - "[x] 21. Fan-out: parallel tracks, per-host politeness, model concurrency"
  - "[x] 22. Presets, budgets and the run's cost ceiling"
  - "[ ] 23. Composition, switches, prices (per-kind reservations first); Settings after the purpose model"
  - "[ ] 24. The operator surface, for both purposes (after 29–32)"
  - "[ ] 25. Accuracy evaluation on a truth set of public Czech facts"
  - "[ ] 26. Quality evaluation: design and interpretation use cases, three arms, rubric judge, blind grade"
  - "[ ] 27. Develop activation and the live acceptance (last)"
  - "[x] 28. Purpose, target and frozen lineage (ADR 0021, AIA-83 Step 1)"
  - "[x] 29. Design Research integration: proposals from a design run, accepted into a revision (gate 1)"
  - "[x] 30. Interpretation Research integration: mission from the target, then enqueue and the route"
  - "[ ] 31. The Sociomap Research Lens: an annotation sidecar beside the canonical map"
  - "[ ] 32. The report evidence graph: five evidence families, every claim's support"
  - "[ ] 33. Structured capture: schema.org data, microdata, OpenGraph and HTML tables kept beside a snapshot"
  - "[ ] 34. Records: schemas and presets, cells grounded in captures, identity by code, the personal-data screen"
  - "[ ] 35. Extractors: code first (structured data, tables), the light-model extractor second, every value verbatim"
  - "[ ] 36. Inventory subjects: the lead asks for records, investigators choose hosts, code admits and crawls them"
  - "[ ] 37. The run's dataset: sealed beside the bundle, cited by findings, exported, proposed to Client Knowledge"
  - "[ ] 38. Pages that need a browser: headless rendering behind its own switch (after 37)"
  - "[ ] 39. Extraction accuracy: record precision and recall on known catalogues (with 25)"
  - "[x] 40. Settings catalogue (ADR 0022): every policy value typed, bounded, with its proposed default"
  - "[x] 41. Settings store and service: immutable versions, append-only approvals, audit, the admin route"
  - "[x] 42. The Deep Research settings page: values, origins, history, approval, live readiness"
  - "[x] 43a. Runs pin their settings: the pin and its digests on the run at enqueue, read back verified; the plan step fails a pin that does not hash to itself"
  - "[x] 43b. The approved method digest in the engine request and every cross-run reuse key (harness 3); a pin that is not the request's method fails the run"
  - "[x] 43c. The engine reads the pin's values where it reads constants: presets, allowances, request limits, register, weights, and the API's ceiling"
  - "[ ] 44. Live needs approval: a run that would go live is refused until its organization approves every required setting"
  - "[x] 45. Injection evaluation: a held-out set of hostile and look-alike pages; the detector's recall and false alarms measured; a hostile page steers nothing"
  - "[x] 46. Retracted sources: a cited work's retraction read from OpenAlex and Crossref; a finding resting on a retracted work quarantined"
  - "[x] 47. The coverage ledger: what a run found, opened, refused, quarantined and accepted, by reason, counted by code"
  - "[x] 48. Verifier calibration: a gold set of claims and excerpts, miss and false-alarm rates with thresholds, NOT_CALIBRATED until measured live"
  - "[x] 49. Search playbooks: where each kind of subject is best found, from the register, as hints the investigator may use"
  - "[x] 50. A commercial comparison arm in chunk 26: Gemini Deep Research on the public fictional topics only"
---
# Deep Research — wide, precise, and defensible

**Status:** in-progress (the engine, chunks 2–22, is on `develop` @ `579b7ab`; re-cut 2026-10-06 around ADR 0021,
§ 0) · **Owner:** research-engine + ai-runtime · **Started:** 2026-10-05 ·
**Base:** `develop` @ `b2d43f7`
**Parent:** [deep-research.md](deep-research.md) chunk 13 (*Live enablement, blocked on DR-2*).
**Decides (proposed; chunk 1 is the data owner's sign-off):** DR-2 for Class C (Brave Search API),
an amendment to ADR 0017 (agents direct the research; code still sends every call), a second
model policy entry under ADR 0010 (a light triage model), and the boundaries in § 4.

## 0. Re-cut after the engine landed (2026-10-06, ADR 0021)

The engine this plan set out to build is on `develop` @ `579b7ab`: chunks 2, 3, 5, 7 and 9–22,
each against its *Tests* / *Done when* (chunk 21 by #166, which also made a released planned track
recover without sending a call twice). Its boundary is now **frozen** (ADR 0021 decision 7):
acquisition, retrieval and readers, investigators, the lead, fan-out, the recovery log, pacing,
model concurrency, verification, grounding, confidence and the bundle change only on a defect or
an evaluation finding.

The plan was written as if Deep Research were one standalone operation. ADR 0021 places it at two
methodological checkpoints instead (`DESIGN_RESEARCH` before the methodology freeze,
`INTERPRETATION_RESEARCH` over immutable results), so the remaining order is:

```
28 purpose / target / frozen lineage            (done: ADR 0021)
→ 23 backend, per-kind reservations             (done: #168, harness 2)
→ 40–43 Deep Research settings (ADR 0022)       (the owner, 2026-10-07: the sign-off's values
                                                  on a settings page, approved values in force,
                                                  pinned per run; before 23 so its switches,
                                                  routes and prices read them)
→ 23 backend, the rest: composition, switches, routes, dated prices
→ 29 Design Research integration                (done: proposals → gate 1 → a new revision)
→ 33–37 structured extraction                    (records from captured pages: a market's
                                                  products, prices, stores, organisations,
                                                  events, as a dataset beside the bundle;
                                                  recorded/offline like the rest)
→ 30 Interpretation Research integration        (mission from the target → engine request →
                                                  enable enqueue → result-side route)
→ 31 Sociomap Research Lens                      (a sidecar; see the invariant below)
→ 32 report evidence graph                       (POPULATION/RESPONDENT, DETERMINISTIC, SOCIOMAP,
                                                  DEEP_RESEARCH, CLIENT_KNOWLEDGE)
→ 24 operator surface, for both purposes         (not a generic Deep Research screen)
→ 25/26 accuracy and quality evaluation          (design and interpretation use cases)
→ 27 live activation                             (last; needs chunk 1's sign-offs)
```

**Deep Research settings (40–44, added 2026-10-07 at the owner's request, ADR 0022).** Chunk 1's
sign-off moves from this file's prose into the product: every policy value -- the search
provider's terms and price, presets and caps, request limits, retention, the register and weights,
the denylist, personal-data patterns, record presets -- is a setting with a proposed default (the
code's constant today), which an Admin approves on a Settings tab. Approved values are what runs:
a run pins its effective settings at enqueue. Switches, secrets and the model route stay in the
deployment; rails stay code. Offline runs use the effective values (proposed ones labelled);
a run that would go live is refused, at enqueue and again before any live call, until its own
organization has approved every required setting (44, with 27).

**Structured extraction (33–39, added 2026-10-07 at the owner's request).** When the research
needs an inventory rather than a figure -- every product in a category, every price a retailer
shows, every store, organisation or event in a market -- the same run extracts records from the
pages it captures: a dataset whose every cell is a value found in a captured page, beside the
bundle and cited by its findings. It is part of this engine, not a second one: the same lead,
investigators, gate, transport, crawler, snapshots, grounding, budgets and fan-out (§§ 5, 8.9).
It runs after 29 because a market's inventory is first of all design context (what exists, what
it costs, who sells it) and later a benchmark for interpretation (30). The owner's choices: a
dataset and evidence; the agents choose which hosts to scrape and code admits them; static pages
first, a browser later (38); hundreds of pages per run (§ 9). Because it adds steps, artifacts
and request kinds to the frozen engine, it opens ADR 0021 decision 7 for exactly these chunks,
under a new harness (§ 16).

The Sociomap invariant, with its actors named so it cannot be inverted: **Interpretation Research may read the frozen canonical Sociomap. Deep Research and external evidence are never inputs to the canonical Sociomap calculation.**
The Lens (31) is a sidecar beside the frozen map; an externally enriched map would be a separate,
derived artifact.

Chunk 23 is split: its backend (real route composition, switches, dated prices, **per-kind
reservations** — today every call reserves the full research reservation, so a run's ceiling sits
far above the § 9 estimates — and corrected ceilings) goes first, before Deep Research becomes a
routine part of a study; its Settings surface waits for the purpose model. Chunk 24 is no longer
the immediate next task: it is redesigned around the two purposes once 29–32 exist. The open
sign-offs (chunk 1: Brave terms, the register, the weights, presets, the light model, quotas;
Common Crawl's `us-east-1` exception; the truth set's facts) block live activation (27), not the
integration (28–32), which stays under the same fail-closed, recorded/offline posture.

Still open, with what is missing: **1** (no decision recorded in § 13); **4** (no SSM parameter,
`write-env.sh` entry or start-up refusal; chunk 23 composes it); **6** (PDF tables are not
extracted: an extractor and its licence are the owner's call, `eb1f9b8`); **8** (the register is
`RegisterStatus.PROPOSED`, not approved); **23**, **24**, **26**, **27** (above); **25** (the
harness exists, `tools/dr_accuracy.py`; `truth-set-pins.json` has no pins and no run is scored).

## 1. What we are building

A research run that works like a good human research team, at machine scale. A **lead
researcher** reads the study's objectives, decides how much effort each question needs and
delegates precise tasks to many **investigators** working in parallel. Each investigator searches,
opens, reads and follows leads, and uses every lawful way to reach the source a number really
came from. **Code** discovers widely underneath them (search, crawls of authoritative sites,
public databases, Common Crawl's archive), screens thousands of pages with a cheap model, and makes
every network call itself. Every finding is a quote AIA captured; every number carries its unit,
period, geography, population and denominator, is traced to its primary publisher, attacked by an
independent verifier, and scored for confidence by code, not by a model. What could not be
reached is reported as a gap, with what it would take a person to close it. When the question is
an inventory -- what is on the market, at what price, where -- the run also **extracts records**
from what it captured, code first and a light model only where code cannot, and returns them as a
**dataset**: every cell a value in a page AIA captured, every record's identity decided by code.

## 2. The problem today

- **No web search.** The production composition blocks every web track. The only live route is
  Czech Wikipedia (`apps/executors/src/aia_executors/deep_research_live.py` @ `b2d43f7`), whose
  transport refuses every other host (`infrastructure/web_retrieval_live.py:71-74`). Everything
  else replays `fixtures/deep_research/web.json`, invented `.example` pages. On 2026-10-05 a
  locally produced demonstration report presented that replay as research.
- **Queries fixed before anything is read.** The planner writes every query up front
  (`domain/deep_research/agents.py:90`, at most 12 per track); each round runs the next
  (`apps/executors/src/aia_executors/deep_research/investigate.py:447-451`); gaps are recorded and
  never searched.
- **No choice of what to read, no lead-following.** Code fetches each query's results; nothing
  follows a page to the source it cites.
- **Documents refused.** `ALLOWED_CONTENT_TYPES` is HTML and plain text
  (`domain/deep_research/web.py:50`); most official statistics and industry studies are PDF or XLSX.
- **Structure is thrown away, and nothing returns records.** A page keeps its visible text: every
  `<script>`, and so every schema.org JSON-LD block, is skipped
  (`infrastructure/web_retrieval.py:196` @ `d2e038a`), microdata is not read, and an HTML table
  becomes running text. A run's only output is quoted findings; there is no record or dataset, so
  "every product on the market" cannot be asked.
- **A number is checked only as digits.** Grounding checks that a claim's numbers occur in its
  quote (`domain/deep_research/grounding.py:190-192`), not that its unit, period, geography or
  denominator are the source's.

## 3. Design principles

1. **Modelled on Anthropic's multi-agent Research system**
   ([engineering post](https://www.anthropic.com/engineering/multi-agent-research-system)). Its
   measured findings set the shape: a lead researcher with parallel subagents beat a single agent
   by 90.2 %; effort scaled to the question; two levels of parallelism cut research time by up to
   90 %; subagents think between tool results; token usage explains 80 % of quality variance
   (with tool calls and model choice, 95 %). Its early failures each get a guard here: vague
   delegation (closed task contract, overlap refused), too many agents for simple questions
   (effort caps in code), endless searches for sources that do not exist (stop rule, ladder caps),
   SEO farms over authoritative sources (tiers, reputation register), serial execution (fan-out).
2. **Agents decide; code acts.** A model proposes; only code sends a query, fetches a page, reads
   a database or writes evidence. Every outbound call passes `RetrievalGate`: classified, judged
   against its route's approved classes, reserved, journaled before it leaves.
3. **A finding is a quote in a snapshot AIA captured, or it is nothing** (ADR 0017).
4. **Crawl wide with code, read narrow with models.**
5. **Confidence is computed, never self-reported.**
6. **Precision before breadth.** Fewer numbers, each exactly right and traced to its publisher,
   beat many approximate ones.
7. **A record cell is a value in a page AIA captured, or it is nothing.** Code extracts first
   (structured data, tables); a model extracts only where code cannot, and only values that occur
   verbatim in the page. Identity, deduplication and normalisation are code; no model computes or
   merges a number.

## 4. Boundaries (non-negotiable)

"Every trick in the book" means every **lawful, public** route to a source. Never:

- logging in, using anyone's credentials, or reaching anything behind a paywall, CAPTCHA or
  registration wall; using an archive or mirror to get round a paywall;
- ignoring `robots.txt` or a site's terms on automated access; disguising the user agent;
  rotating addresses or proxies to evade a rate limit;
- the dark web or Tor; pirate mirrors;
- collecting personal data: extraction keeps legal-entity and aggregate facts and drops
  person-level data before storage (GDPR). A record schema has no personal field (no person's
  name, e-mail, phone or home address), and every extracted value passes a code screen that drops
  and counts e-mails, phone numbers and person-level values before anything is stored;
- republishing: snapshots and extracted datasets stay internal; a report quotes short excerpts
  and aggregates with their source, never a site's catalogue wholesale;
- Class A or B material in any query or URL: Class C only until an EU-processing search route and
  D6 exist.

**Hosts chosen by agents, admitted by code.** For an inventory the agents choose which hosts to
crawl (the owner's choice, 2026-10-07); code admits a host only if its `robots.txt` allows the
paths, it is not on the operator's denylist (hosts whose terms forbid automated collection, kept
as versioned data with the date and source of each entry), and its pages show no login, paywall,
CAPTCHA or registration barrier (`detect_barrier`, a block here rather than a signal). A run
admits a capped number of hosts; every page is paced per host and journaled like any fetch.

A source only those routes would reach becomes an **acquisition gap** (§ 8.6): what it is, who
publishes it, why it was unreachable, and how a person could obtain it (buy it, ask the publisher,
upload it to Client Knowledge, where it becomes usable like any approved source).

## 5. Architecture

### 5.1 The run as a funnel

| Stage | Who | Exhaustive preset, per run (proposal) | Output |
|---|---|---|---|
| Plan | lead researcher | 1 plan, re-planned after each wave | subjects, questions, effort per subject, task briefs |
| Discover | code | ~500 searches; crawls of authoritative hosts (≤ 5,000 pages); connector queries; Common Crawl index | candidate sources |
| Filter | code | tens of thousands → ~2,000 | deduplicated, ranked candidates |
| Triage | light model, parallel | ~2,000 pages | relevant pages with candidate quotes, per sub-question |
| Investigate | strong model, 20–50 investigators | waves of 3–5 per subject | grounded findings, leads followed, gaps |
| Extract (inventory subjects) | code, then the light model | the admitted hosts' pages, hundreds per run (§ 9) | records, every cell grounded; a dataset per subject |
| Verify | strong model, independent | every finding the brief would use | supported, overstated, unsupported, superseded |
| Synthesize | strong model | 1 | the brief: answers, conflicts, gaps, acquisition gaps |

Standard and Deep presets (§ 9) skip triage and the crawlers and run fewer investigators; an
inventory subject crawls its admitted hosts at Deep and Exhaustive only, within § 9's page caps.

### 5.2 Agents

| Role | Model | Contract (closed, versioned) | Can |
|---|---|---|---|
| Lead researcher | strongest on the EU route (own policy entry) | `ResearchPlan`, `Wave`, `Replan` | plan, size, delegate, move budget, open tracks for gaps and conflicts; mark a subject an inventory and give it a record schema |
| Investigator | strong | `InvestigatorTurn` | propose up to 5 actions a turn; propose evidence and leads; on an inventory task, propose hosts to crawl |
| Triage reader | light (`RESEARCH_TRIAGE`) | `TriageVerdict` | judge one page; propose ≤ 3 candidate quotes |
| Extractor | light (`RESEARCH_TRIAGE`'s entry, request kind `extractor`) | `RecordProposal` | propose records for one page under the subject's schema, each value a verbatim span; send nothing |
| Verifier | strong, independent prompt | `Verification` | attack one finding; propose a search for a newer or primary figure |
| Synthesizer | strong | `SynthesisProposal` (extended) | write the brief from accepted evidence only |

Stored runs stay readable under their own contract and prompt versions.

### 5.3 Tools (all executed by code)

| Tool | Reaches | Route |
|---|---|---|
| `search` | Brave web search with site, phrase, language, freshness and (if supported) file-type operators | `brave-web-search` |
| `open` | a result or a link by ref (`R<n>`, `L<n>`) | public fetch |
| `read` | a part of a captured document (`S<n>`: section, pages, sheet) | none, local |
| `chase` | a source cited by name, resolved by the reputation register | search or connector |
| `ladder` | the acquisition ladder for a needed source (§ 7) | several |
| `dataset` | a connector query (DataStat, NKOD, Eurostat, …) | the connector's route |
| `archive` | a dated archived copy of a dead or moved page (Wayback CDX, Common Crawl) | the archive's route |
| `crawl` | an inventory task's host, proposed by the investigator and admitted by code (§ 4): sitemap, listings and pagination, within the task's page cap | public fetch |
| `extract` | records from a captured page (`S<n>`) under the subject's schema: structured data and tables by code, the extractor for the rest | none, local; the extractor's request |

The model never writes a URL: it names refs code created, or a publisher and a description code
resolves. Every query string, and every URL's path and query, is classified like a query.

## 6. The investigator

A track is a loop of turns. A turn is one governed model request with thinking on (chunk 2),
checkpointed: a retry replays answered turns and never pays twice.

**Input:** the task brief (objective, wanted output, sources to prefer, boundaries, budget); the
track's state: searches and hits (`R<n>`: title, host, tier, date, file type, held or
near-duplicate), captured sources (`S<n>`: title, publisher, tier, date, outline), links found
(`L<n>`: anchor text, host, tier); the newest captured text, untrusted, with `detect_instructions`
flags; grounded findings so far; the stop rule's state and remaining allowance; refusals, search
feedback and ladder outcomes since the last turn.

**Output, `InvestigatorTurn`:**

```text
evidence: [ProposedEvidence]          # quote, claim, source ref, and a measure per number (§ 8.1)
summary: str                          # what this turn learned, condensed for the lead
leads: [{need, publisher?, why}]      # sources it needs but has not reached; feed the ladder
next: up to 5 of, sent concurrently
  search  {query, operators, purpose}
  open    {ref: R<n> | L<n>, purpose}
  read    {ref: S<n>, part, purpose}
  chase   {name, what, from: S<n>}
  ladder  {lead, purpose}
  dataset {connector, query, purpose}
  crawl   {host, why}                 # inventory tasks only; code admits the host (§ 4)
  extract {ref: S<n>}                 # inventory tasks only; records under the subject's schema
  finish  {gaps: [{need, why, tried}]}
```

**Prompt heuristics:** start wide with short queries, then narrow; prefer the publisher of a number
to anyone repeating it; read the methodology note of any statistic used; prefer the latest complete
period and name it; never read a number off a chart without its table; Czech and English sources
both count.

**Feedback from code:** why a search was weak (no hits, all held, all low tier, out of date range);
why an action was refused; which leads the ladder resolved or exhausted.

**Stop rule** (before every turn): evidence target met; saturation (no newly grounded evidence for
`saturation_window` turns; weak searches do not count); allowance spent (searches, opens, turns,
reservation); `finish`; an uncertain delivery (journal closed, never resent); the same refusal
reason three times (`STOP_REFUSALS`). An inventory task also stops when its admitted hosts are
crawled out or its page cap is spent, and on record saturation: no new record identity for
`saturation_window` turns.

## 7. The acquisition ladder

When an investigator needs a specific source (a table a page cites, the report behind a press
release, a figure for a year not yet found), it raises a lead and `ladder` tries these rungs **in
order**, stopping at the first that yields a capture. Each rung is code, each request passes the
gate, each attempt is in the transcript.

| # | Rung | How |
|---|---|---|
| 1 | Direct link | the citing page links it: open it |
| 2 | Same release, other formats | from an HTML release, its PDF, XLSX or CSV twin on the same host (links, `alternate` tags, a file-type search on the host) |
| 3 | Publisher's own index | resolve the publisher in the reputation register; its sitemap, publication listing or feed; a `site:` search for the title or a distinctive phrase |
| 4 | Publisher's data interface | a connector where the publisher has one (DataStat for ČSÚ, Eurostat, NKOD datasets), queried by topic and period |
| 5 | Exact-phrase search | a distinctive phrase, table title or document number in quotes, with a file-type filter where supported |
| 6 | Language and edition | the same publication in English or Czech; the previous edition when the wanted one is not out yet (period recorded) |
| 7 | Scholarly identity | a DOI or title through OpenAlex to its legitimate open-access location (publisher, repository, preprint) |
| 8 | Official aggregators | Eurostat, OECD, EUR-Lex, NKOD republishing a national figure |
| 9 | Archived copy | for a dead or moved page only: the Wayback CDX or Common Crawl capture nearest the cited date, archive date recorded; never for a page live behind a paywall |
| 10 | Same-host path discovery | for a moved document: parent paths and the host's own listing pages, only paths `robots.txt` allows, at most 10 requests per lead |
| 11 | Acquisition gap | nothing worked: publisher, title, reason (paywall, login, not public, not found), how a person could obtain it |

Attempts count against the track's allowance, and the ladder has its own cap per lead (default 12
requests), so an unreachable source cannot consume a run.

## 8. Accuracy machinery

### 8.1 Every number is a measure

Each number an evidence item cites carries a structured **measure**: value; unit (`%`, `p. b.`,
`Kč`, `l`, `ks`, `osoby`…); scale (1, `tis.`, `mil.`, `mld.`); period (`2025`, `2025-Q2`, `2024/25`);
geography (`CZ`, `Praha`, `EU27`…); population (`domácnosti`, `osoby 15+`…); denominator; measure
name; basis (actual, estimate, forecast, preliminary). Code checks unit, scale and period against
the quote's context window (the paragraph, or a table cell's row and column headers, caption and
footnotes); a mismatch is quarantined as `MEASURE_NOT_IN_SOURCE` (a new reason). A household share
claimed as a share of people fails here.

### 8.2 Tables as tables

PDF tables are extracted with their structure (row and column headers, caption, footnotes); XLSX
and CSV are read as grids. A table number is grounded to its cell: the quote is the cell value with
its headers, the locator `page/table/row/col` or `sheet!cell`; a footnote attached to the cell
(e.g. "předběžné údaje") travels with the finding.

### 8.3 Primary tracing

Every finding is **primary** (captured from the number's publisher) or **secondary** (repeated by
someone else). A secondary finding raises a lead to its primary, and the ladder tries to reach it.
The brief uses the primary figure where found, notes any difference, and labels a figure left
secondary.

### 8.4 Verification

For every finding the brief would use, an **independent verifier** (separate prompt, none of the
investigator's reasoning) gets the claim, the measure and the source context and tries to break it:
wrong attribute, overstated generalisation, a newer figure, a different denominator, preliminary
data. It may propose a search, which code runs through the gate. Verdicts: `supported`,
`overstated`, `unsupported`, `superseded` (a newer figure from the same publisher, captured). A
superseding figure goes through §§ 8.1–8.3 itself.

### 8.5 Triangulation and conflicts

- **Independence is by publisher**, after near-duplicate collapse: two pages carrying one press
  release are one confirmation.
- **Conflicts** are found by code: same measure name, period, geography and population, values
  differing beyond rounding. The lead opens a *resolve* track to find each value's primary source
  and explain the difference (definition, revision, period). An unresolved conflict is shown as a
  conflict, never averaged.

### 8.6 Confidence, by code

Computed from source tier, primary or secondary, independent confirmations, the verifier's verdict,
recency of the period against the study's needs, and preliminary or final data, with versioned
weights approved alongside the tiers. The model's own `source_quality` stays recorded and decides
nothing.

### 8.7 Source tiers and the reputation register

`SourceClass` (`domain/deep_research/sources.py:50-61`) becomes tiered:

| Tier | Examples |
|---|---|
| T1 | official statistics (ČSÚ, Eurostat), the central bank, regulators, ministries, EU institutions |
| T2 | peer-reviewed research, international organisations (OECD, World Bank), academic institutions |
| T3 | industry bodies and associations, audited company reports, established research publishers' public releases |
| T4 | established national media |
| T5 | other identifiable publishers |
| Excluded | content farms, AI-generated aggregators; forums and social media (quarantined as today) |

The **reputation register** maps each publisher to its hosts, tier, data interfaces and name
variants ("ČSÚ", "Český statistický úřad", "Czech Statistical Office" → `csu.gov.cz`, `czso.cz`,
DataStat). It drives `chase`, ladder rungs 3–4 and the tier annotations. Versioned data approved by
the data owner. An unknown host is T5 at best (CLAUDE.md § 8: never score unknown as good).

### 8.8 The brief

The synthesizer writes only from accepted findings, per research objective: the answer; each
number with its full measure, source, tier, primary or secondary and confidence; conflicts and how
they were resolved; gaps; acquisition gaps. Every number cites its evidence id; the prose-number
coverage check applies.

### 8.9 Records and datasets (chunks 33–37)

**Schemas.** An inventory subject carries a `RecordSchema`: named fields of closed types -- text,
identifier (GTIN/EAN, IČO, a host's own product id), money (value and currency), quantity (a § 8.1
measure), URL, date, enum, address of a business -- each marked identity or not, and none
personal. Versioned presets cover the common inventories (product, price observation, store or
branch, organisation, event, listing); the lead may propose another schema, which code checks
against the same rules. A schema is frozen in the run's plan.

**Structured capture.** Beside every captured HTML page, code keeps what the page states in
structure: schema.org JSON-LD (`Product`, `Offer`, `AggregateOffer`, `ItemList`, `Place`,
`LocalBusiness`, `Organization`, `Event`), microdata, OpenGraph, and HTML tables as grids with
their header cells. It is a sidecar keyed by the snapshot id: the snapshot's text, id and every
existing fingerprint stay what they are.

**Extraction, in order.** (1) Structured data mapped to the schema by code; (2) tables mapped by
code, a header to a field; (3) the extractor, only for fields still empty, each value accepted
only if it occurs verbatim in the page's text (located like a quote) and refused and counted
otherwise. A cell records its snapshot id and either its structured-data path, its table cell or
its text span, and how it was extracted.

**Identity and consolidation, by code.** A record's identity is its identifier when it has one,
else its canonical URL, else its normalised identity fields; duplicates across pages and hosts
merge into one record whose differing values are kept side by side with their sources (a price
seen at two retailers is two observations, never an average). Money keeps its currency and the
page's date; a quantity its unit and scale (§ 8.1).

**The dataset.** Per inventory subject, a sealed `deep_research_dataset` artifact beside the
bundle: the schema, the records and cells, per-host coverage (pages crawled, records found,
refusals by reason), the personal-data screen's counts and gaps, with a seal like the bundle's.
It reaches the rest of the run as dataset sources (`DatasetResult`, chunked to its cell cap), so
investigators, the verifier and the brief cite a cell through `ground_cell` like any connector's
table. It is exported to CSV and XLSX for a researcher, never client-facing (ADR 0019 gate 3), and
may be proposed to Client Knowledge as a DATASET that a person accepts (gate 1). It is evidence
like the rest of the run: never a design, a respondent fact or an input to the canonical Sociomap
(ADR 0021).

## 9. Presets and cost (estimates; measured in chunks 25–26)

A turn reads up to about 8,000 tokens of page text, about $0.04 at the develop policy's prices;
multi-agent research uses about 15× the tokens of chat (Anthropic's measurement).

| Preset | Agents and allowances | Triage, crawl, Common Crawl | Estimate per run | Time |
|---|---|---|---|---|
| Standard | 1 lead; ≤ 12 tracks; per track 8 searches, 20 opens, 15 turns | no | about $5–7 | minutes |
| Deep | 1 lead, 3 re-plans; ≤ 20 tracks; per track 15 searches, 40 opens, 30 turns | no | about $12–18 | under an hour |
| Exhaustive | 1 lead, subject leads; 20–50 investigators | yes | about $60–100 | 1–3 hours |

Inventory subjects (proposed, DR-5): none at Standard; at Deep at most 3 admitted hosts, 300 pages
and 100 per host; at Exhaustive at most 6 hosts, 500 pages and 200 per host ("hundreds of pages
per run", the owner's choice). Extractor requests count as their own request kind
(`request_limits`); code extraction costs nothing.

Effort scaling inside a preset (Anthropic's rules): a simple fact, 1 track and 3–10 tool calls; a
comparison, 2–4 tracks of 10–15 calls; complex research, more than 10 tracks with divided
responsibilities. Code enforces the caps.

## 10. Search provider (DR-2, Class C)

Requirements: pointers, not answers (AIA grounds in its own captures); Czech; terms that allow
storing results and using them in an AI application; Class C may leave the EU, Class B may not;
metered per call; a plain HTTP API, no SDK.

| Provider | Verdict |
|---|---|
| **Brave Search API** | **Chosen for Class C.** Independent index; `country=CZ`, `search_lang=cs`; ranked results; about $5 per 1,000 requests; also sold through AWS Marketplace. US-based; query logs up to 90 days, zero retention on Enterprise only; storing results needs a plan that grants it. |
| Linkup (Paris) | Candidate for Class B later, only under a signed EU-processing, zero-retention agreement. |
| Staan (Qwant + Ecosia) | Rejected: no Czech (French, English, German). |
| Exa, Tavily, Parallel | Rejected for now: no confirmed EU route, no advantage over Brave for Class C. |
| Answer engines; a provider's own search tool (incl. Claude's server-side web search) | Rejected: answers, not pointers; queries leave without AIA's gate; not offered on the Bedrock route. |
| Google Custom Search JSON API | Rejected: closed to new customers, discontinued 2027-01-01. |
| Bing Web Search API | Rejected: retired August 2025. |

Sources: Brave [Search API](https://brave.com/search/api/),
[pricing and retention](https://costbench.com/software/ai-search-apis/brave-search-api/),
[storage rights](https://github.com/modelcontextprotocol/servers/issues/522),
[country and language codes](https://brave-search-python-client.readthedocs.io/en/latest/lib_reference.html);
Linkup [security FAQ](https://docs.linkup.so/pages/security-and-privacy/faq);
Staan [FAQ](https://staan.ai/faq); Google [shutdown](https://heise.de/-11152411);
Common Crawl [URL index](https://blog.commoncrawl.org/blog/the-columnar-index-is-now-the-url-index);
ČSÚ [DataStat](https://csu.gov.cz/produkty/datastat-postupne-nahrazuje-verejnou-databazi);
Bedrock [Claude Haiku 4.5](https://docs.aws.eu/bedrock/latest/userguide/model-card-anthropic-claude-haiku-4-5.html).
Every term and price is a hypothesis until chunk 1, and each connector's chunk, records the signed
terms with their date.

## 11. Chunks

Each chunk is one PR into `develop`, green on `make verify`, with this file ticked and its
measurements in § 13. Chunks 2–24 and 28–39 build and test offline on recorded doubles (each connector
chunk starts with a written check of its terms); only 25–27 send anything. Within a phase, chunks may run
in parallel unless an order is stated.

### Phase 0 — decide

**1. Sign-off (human; no code).** The data owner approves: this design and § 4; the ADR 0017
amendment (§ 16); Brave on a plan that grants storage and AI use (plan, terms URL and date, price,
failed-request billing, retention, recorded here); D8 for the key (chunk 4's proposal or Secrets
Manager); run budgets per preset; the lead's model and the light model's ADR 0010 policy entries; a
Bedrock quota request for chunk 21; the snapshot retention period; the tiers, the register and the
confidence weights (§§ 8.6–8.7); for structured extraction (§§ 4, 8.9): `robots.txt` as the
machine-readable form of a site's terms together with the operator's denylist, the record presets
and the personal-data screen's rules, the inventory caps (§ 9), the extractor on the light
model's entry, and the retention of extracted datasets. *Done when:* each item that is a value
is approved on the Deep Research settings page (chunks 40–42, ADR 0022), whose history records who
approved it and when; the rest (the design, § 4, the ADR 0017 amendment, the quota request) are
recorded in § 13 with a date.

### Phase 1 — retrieval foundations (chunk 2 first)

**2. Structured output with thinking on.** Claude does not allow a forced tool choice with thinking
on; the Bedrock adapter forces one (`model_adapters/bedrock.py:199-209` @ `b2d43f7`) and sends no
thinking setting. Add the thinking setting and a structured-output form that keeps strict
validation without forcing the tool (tool choice `auto` with a strict schema and the instruction to
answer through it, or the route's native structured output), for Deep Research contracts only;
other agents unchanged. Thinking tokens metered and reserved. *Tests:* schema-valid output with
thinking on; an off-schema reply is one counted repair; reservations cover thinking. *Done when:* a
recorded Deep Research turn runs with thinking on.

**3. Brave search adapter.** `infrastructure/web_retrieval_brave.py`: `BraveSearch(SearchAdapter)`,
`RetrievalMode.LIVE`, adapter id `brave-web-search-1`. `GET` with `q`, `country=CZ`, `search_lang`
(cs or en), `count` ≤ 20, freshness when asked, safe search on; `site:` and exact phrases in the
query; `filetype:` verified against the provider and refused if unsupported. Hits → `SearchHit`; a
hit failing `check_url` dropped and counted. Failures → `ToolCallFailed` with `Delivery` (rejected
before processing: `RESPONDED`; timeout or reset after sending: `UNKNOWN`, closed uncertain, never
resent). No retry inside the adapter. Pinned HTTPS client scoped to the API host. *Tests:* a
captured response shape with fictional content; every failure mode; the key never in a log line or
exception; no network.

**4. The search key as a credential reference.** A `CredentialSource` reference
(`model_adapters/transport.py:245-270`), never the key. Proposal: SSM `SecureString`
`/aia/develop/aia_deep_research_brave_api_key`, decrypted by `deploy/develop/bin/write-env.sh` into
`.env` and passed to the worker service only. Missing while the route is on: the worker stops at
start, naming the key. *Trade-off:* no rotation; production needs its own answer.

**5. Public-web fetch.** `PublicHttpsTransport`, generalised from the Wikipedia transport: any
public host passing `check_url` and `check_resolution`, every hop re-checked; private, link-local
and metadata addresses refused; `robots.txt` read once per host per run and obeyed, crawl-delay
included; an identifying user agent with a contact address; no cookies or credentials; the existing
size, time and redirect caps; one request at a time per host. Snapshots keep outbound links
(absolute, valid, deduplicated, ≤ 200) and `alternate` links. A run-level, content-addressed
snapshot cache: a URL fetched once in a run is not fetched again. *Tests:* a private address refused
on a redirect hop; a `robots.txt` disallow honoured; a cache hit sends nothing.

**6. Documents.** `ALLOWED_CONTENT_TYPES` gains PDF, XLSX and CSV, each bounded (size, pages, ZIP
entries and ratio). Text via `infrastructure/document_text.py`; an outline per document; `read` by
section, pages or sheet. PDF tables extracted with their structure by a table extractor added to the
`documents` extra (choice and licence recorded; measured on fictional fixtures). *Tests:* fictional
PDF, XLSX and CSV; oversized and malformed files refused; a quote found on the right page; a number
grounded to its cell with its headers and footnote.

**7. Measures.** The measure on every cited number (§ 8.1); attribute checks against the context
window; the `MEASURE_NOT_IN_SOURCE` quarantine; Czech scale words and units normalised. *Tests:* a
household share claimed as a people share quarantined; a value in thousands claimed as units
quarantined; a period absent from the context quarantined; a correct measure accepted.

**8. Source tiers and the reputation register.** Tiers T1–T5 and Excluded (§ 8.7) in
`domain/deep_research/sources.py`; the register as versioned data (publishers, name variants,
hosts, data interfaces); unknown hosts never above T5. *Tests:* every name variant resolves; an
unknown host is T5; an excluded host's findings quarantined. *Done when:* the owner approved the
register (shipped off until then).

### Phase 2 — agents and accuracy (in order: 9, 10, 11, 12, 13)

**9. The investigator.** `InvestigatorTurn` (§ 6), versioned; the loop in `investigate.py`; up to 5
actions per turn executed concurrently through the gate; refs; URL classification; refusals and
`STOP_REFUSALS`; search feedback; the condensed summary; the transcript artifact. *Tests (recorded,
fictional):* a lead followed from a news page to the PDF it links; a gap searched; parallel actions
all journaled before any leaves; a page instructing a client-name search refused three times and
ended; an uncertain search never resent; a retry replays without paying twice.

**10. The acquisition ladder.** `ladder` and its eleven rungs (§ 7), each rung a small, separately
tested function; the per-lead cap; secondary findings raising primary leads; acquisition gaps.
*Tests:* each rung reaches a fictional source the earlier rungs could not; a paywalled live page is
never fetched from an archive; the cap ends an unreachable lead; the gap names publisher, title and
reason.

**11. The lead researcher.** `ResearchPlan` (subjects, questions, complexity, effort), `Wave` (3–5
`SubagentTask`s: objective, wanted output, sources to prefer, boundaries, budget), `Replan` (tracks
for gaps, resolve tracks for conflicts, budget moved, findings routed). The plan is a run artifact,
the memory that survives a long run and a retry. Code checks effort caps by complexity, no two tasks
with the same subject and measure, the run's ceiling and the re-plan limit. The lead's model by its
own policy entry. *Tests:* a simple subject gets one track, a complex one many; overlapping tasks
refused; budget moved with the run's total unchanged.

**12. Verification.** The independent verifier (§ 8.4) with `superseded`; primary tracing (§ 8.3);
publisher independence after near-duplicate collapse; conflict detection and resolve tracks (§ 8.5).
*Tests:* a syndicated press release counts once; a newer figure supersedes; a conflict resolved to a
definition difference; an overstated generalisation caught.

**13. Confidence, gaps and the brief.** Confidence by code (§ 8.6) from versioned weights; the brief
(§ 8.8) with conflicts, gaps and acquisition gaps; Client Knowledge proposals for accepted sources
unchanged. *Tests:* confidence monotone in each input; the model's self-rating ignored; every
number in the brief cites an evidence id.

### Phase 3 — breadth (each connector chunk starts with its recorded terms, interface and limits)

**14. Connectors I.** ČSÚ DataStat (datasets, CSV/JSON, metadata) and the national open-data
catalogue NKOD (DCAT-AP, SPARQL). Results become snapshots with dataset id, query and cell as the
locator. *Tests:* recorded responses; a number grounded to its dataset cell with its period.

**15. Connectors II.** Eurostat's data API; OpenAlex (works, open-access locations); Wayback CDX
(captures by URL and date). *Tests:* recorded responses; the archive used only for dead or moved
pages.

**16. Connectors III.** ARES (legal-entity fields only; person-level fields dropped before storage);
public procurement (NEN / Věstník). *Tests:* a recorded ARES response stores no personal name;
procurement notices grounded by notice id.

**17. Focused crawler.** `SiteCrawl`: sitemap, then breadth-first inside one host; page, depth and
time caps; `robots.txt` and crawl-delay; a per-host rate; snapshots into the run cache. *Tests:* a
fictional site with a crawler trap and an off-host redirect. (Built; not yet called. Chunk 36 calls
it for inventory hosts, which code admits by § 4 rather than by tier: "authoritative" was only the
caller's choice, never a check.)

**18. Common Crawl.** Athena over the URL index from AIA's AWS account (IAM scoped to the public
bucket and a results bucket; cost metered from bytes scanned); archived pages by WARC byte range;
query text classified (data in `us-east-1`, Class C only). *Tests:* recorded Athena results; a WARC
record extracted and grounded.

**19. Code filters.** Exact and near-duplicate collapse (content hash, then shingled similarity),
language detection, tier, relevance ranking against each sub-question. *Measured:* recall and
precision on a hand-labelled fictional corpus, recorded in § 13.

**20. Triage readers.** The `RESEARCH_TRIAGE` capability on the light model (proposed: Claude Haiku
4.5 through its EU cross-region profile `eu.anthropic.claude-haiku-4-5-20251001-v1:0`), its policy
entry and prices; `TriageVerdict` (relevant, sub-question, ≤ 3 candidate quotes); candidate quotes
grounded before an investigator sees them; a triage reader can send nothing. *Tests:* recorded;
parallel under the limiter.

**21. Fan-out.** Tracks run concurrently across worker processes; a per-host politeness scheduler
shared by every fetcher in a run; a model concurrency limiter below the account's quota. *Tests:* 50
tracks never exceed either limit; every interrupted track recovers.

### Phase 4 — control and surface

**22. Presets, budgets, cost ceiling.** Standard, Deep and Exhaustive (§ 9) in `DepthPreset`; turn,
lead, verifier and triage reservations; search, connector and Athena prices in `run_cost_ceiling`
(`domain/run_cost.py`); a study's spend limit asks first (ADR 0019 gate 2). *Tests:* moving budget
never raises the ceiling; an Exhaustive run over the limit asks.

**23. Composition, switches, prices; Settings.** `AIA_DEEP_RESEARCH_WEB_SEARCH` (`off` | `brave`),
`AIA_DEEP_RESEARCH_AGENT_DIRECTED`, `AIA_DEEP_RESEARCH_LEAD`, `AIA_DEEP_RESEARCH_CONNECTORS` (a list),
`AIA_DEEP_RESEARCH_CRAWL`, `AIA_DEEP_RESEARCH_COMMON_CRAWL`, `AIA_DEEP_RESEARCH_TRIAGE`,
`AIA_DEEP_RESEARCH_EXTRACTION` (needs the crawl, the public fetch's contact address and the
denylist; composed once 33–37 land); dated prices
for each paid route; every route `approved_for={CLASS_C_INTERNAL}`. Anything missing or invalid
stops the worker at start, naming the key. Settings shows each as configured or off, never
"connected" (`apps/web/src/lib/ai-runtime.ts`).

**24. The Deep Research screen.** The plan; live progress (stage, tracks, counts, spend so far);
findings with measure, source, tier, primary or secondary, confidence and verdict; conflicts; gaps;
acquisition gaps with how to obtain each; the transcript per track; each inventory's dataset
(records, every cell's source, per-host coverage, export); cancel at any point, keeping what was
captured; the snapshot and dataset retention job.

### Phase 5 — proof

**25. Accuracy on a truth set.** 50 public Czech facts with known values and primary publishers
(population, prices, consumption, trade; Class C), fixed and recorded before any run. Measured per
preset: exact-value accuracy with the right unit, period and geography; primary-source rate; share
grounded to a table cell; false acceptances (a wrong number accepted); acquisition gaps. *Proposed
target for the owner:* zero false acceptances, at least 90 % exact accuracy at Deep.

**26. Quality on 20 research questions.** Fictional-client questions (simple, comparison, complex),
each run three ways (planned queries as today; agent-directed; agent-directed with the lead
researcher), then Deep against Exhaustive. Recorded: accepted findings; primary-source share;
cell-grounded share; conflicts found and resolved; quarantines by reason; searches, opens, turns;
money per accepted finding; a rubric score from a separate judge model (factual accuracy, citation
accuracy, completeness, source quality, tool efficiency); a researcher's blind grade. Each step
becomes a default only if it wins; the owner sets the presets from these numbers.
*A fourth arm (chunk 50):* Google's Gemini Deep Research, run by a person through Google's own
interface on the questions whose topic is public and fictional-client only -- never a client's
question, brief or name, which would leave AIA's egress gate. Its report is graded blind beside
ours on the same rubric and grade: citation accuracy is checked by the person opening each cited
page, since it has no sealed snapshot; money is what the person's plan charged, stated as such. It
is a measuring stick, never a route: no code calls it, and § 10's verdict on answer engines stands.

**27. Develop activation and the live acceptance.** Parameters set, deployed, the worker's start-up
log read; one run per preset for a fictional client within the owner's budget; run ids, counts and
spend (model, search, connectors, Athena separately) recorded in § 13. Then tick the parent plan's
chunk 13 for Class C.

### Chunk 29 — Design Research integration (designed 2026-10-07)

ADR 0021 decision 1: a `DESIGN_RESEARCH` run is advisory; what it found becomes a *proposal*, and
only a person turns a proposal into a new Design Revision (ADR 0019 gate 1). The engine stays
frozen (decision 7): no new step, no model call, no change to the bundle or its seal. The proposal
is built **by code** from the sealed bundle the run already published.

**What a proposal is.** One item per research subject of the run (`ResearchSubject`): an
`EVIDENCE` item carrying every accepted finding of that subject exactly as `design_input`
already exposes it (claim, verbatim quote, source, source class, confidence, whether it may
ever reach respondents), or a `GAP` item for a subject with none. Each item has a stable id
(`DRP-` + the bundle seal and the subject key, hashed), so the same run always proposes the same
items. The proposal names its run, the run spec's fingerprint, the bundle artifact and seal, and
the Design Revision it was frozen on: its baseline.

**What accepting writes.** A person picks the items to take (taking some and not others is the
"modify"; taking none is the "reject", which writes nothing). The new revision is the baseline's
content with one AIA-owned key added or extended, `design_research` -- the accepted items keyed
by their ids, each with its role `EXTERNAL_CONTEXT`, its findings and the provenance above -- and
**every other key byte-for-byte unchanged**. Deep Research therefore never writes the research
plan, questionnaire, audience, dimensions or sample plan: a person (or a design job, which already
reads the whole design) acts on the evidence afterwards. The key is not the unit's
`research_context` (a respondent-context toggle) and is never respondent context: that path
re-screens against the final questionnaire on its own (`quarantine.respondent_context`).

**Rules, each a refusal with a reason.**
- Only a governed, completed `DESIGN_RESEARCH` run with a verified bundle proposes; a legacy run,
  an interpretation run, a run without a bundle are refused.
- The run's lineage must still resolve (`resolve_lineage`), the caller's expected revision must be
  the lineage's revision and the Study's newest (`submit_if_current`): a proposal never lands on a
  design it was not researched from (`stale_proposal`).
- A bundle resting on recorded fixtures is admissible only for a fictional client
  (`bundle.fictional_client`): recorded evidence never enters a real client's design.
- The `design_research` block is bounded (32 KB), and an accept that would push the whole design
  past the design jobs' 64 KB context (`research_agents.context_snapshot`, built with the Study's
  knowledge before and after) is refused (`design_context_too_large`); a baseline already over it
  is not this accept's to refuse (Codex review on #178).
- `EDIT_STUDY` and `APPROVE_GATE` on an open Study: the worker's scope cannot accept. Each
  accept that writes is recorded once in the approval ledger (`subject_type = design_research`,
  the selection's id), with who produced the run and who accepted.

**Where the code lives.** Pure domain: `domain/deep_research/design_proposals.py` (the proposal,
its items, `apply_to_design`), naming no writer, as `layer_check` requires of the DR domain. The
writer is `application/design_research.py` (`DesignResearchProposals`), beside, not inside,
`application/deep_research.py`, which `layer_check` keeps from naming a design writer; it reads
the run through `DeepResearchRuns` and writes through `StudyDesignRepository.submit_if_current`, as
`ResearchAgentJobs.accept` does. API: `GET …/deep-research/runs/{run_id}/design-proposal` and
`POST …/design-proposal/accept` (`item_ids`, `expected_revision_id`), answering the new revision
and its content so the client can write its working copy, as the agent accept does. The screen is
chunk 24's.

*Tests:* a proposal from a recorded journey run lists every subject, its findings verbatim, its
gaps; the same run proposes the same ids; accepting a subset writes exactly those items and leaves
every other design key unchanged; once a revision is written, a second accept from the same run is
stale (a proposal never lands on a design it was not researched from; a new run over the new
revision proposes again, reusing the engine's unchanged tracks) and writes nothing; an accept that
changes nothing writes no revision and no ledger row; a stale baseline, an unknown item, an empty selection, an interpretation or legacy run, a run of
another Study, a recorded bundle on a real client and an oversized block are refused, and none
writes; the worker's scope cannot accept; the ledger row names producer and acceptor.

### Chunk 30 — Interpretation Research integration (designed 2026-10-08)

ADR 0021 left `INTERPRETATION_RESEARCH` frozen, never enqueued, because its engine request was
still the design's: a run would be labelled as interpreting a result while researching the
design's subjects (OI-88). Chunk 30 derives the run's **mission** from the exact target, builds
the engine request from it, and then enables enqueueing, the result-side retry and the route.
Taken on 2026-10-08 before 33-37 at the owner's request: nothing in 30 reads a record or a
dataset, so the order in § 0 is a preference, not a dependency.

**The engine stays frozen (ADR 0021 decision 7).** No step, artifact type, request field,
harness version, bundle field or seal changes. The mission is expressed in the request's
existing fields: `subjects` (code-built from the target, below) and the unchanged `brief`,
`questionnaire`, `knowledge` and `client_terms` frozen from the Design Revision the producing
run executed (`freeze`, as today). A different target is a different subject set, so a
different request fingerprint and a different run; two targets with the same subjects share the
engine's reusable tracks, as two purposes over one request already do.

**What the mission is, by target (pure: `domain/deep_research/interpretation.py`).** Each
subject's `origin` names the target (`interpretation:<KIND>:<entity>`), so the bundle says what
each track was researching. Texts are Czech, as the design's subjects are.

| Target | Subjects |
|---|---|
| `RESULT_QUESTION` | one `QUESTION`: the survey question's text (from the pinned `compile` specification), framed as the context and benchmarks of its answer |
| `RESULT_BATTERY_OBJECT` | one `OBJECT`: the object's label; one `QUESTION`: the battery's question about that object |
| `ANALYSIS_MODULE` | `research_questions`: each research question of the design; `objects`: each tracked object of the specification; any other module: one `QUESTION` framing the study's goal for that module |
| `SOCIOMAP` | one `OBJECT` per object of the battery; one `QUESTION`: what links the battery's objects for its family |
| `SOCIOMAP_OBJECT` | one `OBJECT`: the object's label |
| `SOCIOMAP_RELATIONSHIP` | one `QUESTION`: what connects the two objects; one `OBJECT` for each |

**No respondent number enters a mission.** A subject names what the result is *about*, never
what respondents answered: an observed share, a mean, a coordinate or a relation strength is
not in any subject text. Comparing external evidence with a result is code's work downstream,
reading both (the Lens, 31; the report graph, 32). This keeps fictional figures out of web
queries and keeps a real client's results inside the class rule that already holds every query
written from a real client's design (`design_class`, DR-2b): Class A, never sent.

**Enqueue, retry, route.**
- `freeze_interpretation` builds the request from the mission; an empty mission is
  `NothingToResearch`. `_enqueue` stops refusing interpretation specs: the boundary's check
  becomes "every subject of the request carries this target's interpretation origin"
  (`require_interpretation_mission`), so a spec whose request was frozen any other way -- the
  design's subjects under an interpretation label -- is still refused, without reading a store.
- `retry` of an interpretation run re-freezes the **stored target** (never re-chosen) with the
  store; its lineage must be the stored lineage, pin for pin, or the retry is `LineageChanged`
  and starts nothing.
- API: `POST …/deep-research/runs/interpretation` (`target`, `preset_name`, `channels`,
  `confirm_cost_usd`, `title`), answering the run as `POST …/runs` does; the retry route takes
  the artifact store for an interpretation row. Spend limit, cost ceiling and confirmation as for
  a design run.

*Tests:* each target kind's mission, deterministic (same target, same subjects); no subject
holds a digit that came from the result payload; the request's subjects differ from the design
run's for the same revision; a spec with a design-derived request under an interpretation
purpose is refused at enqueue; enqueue and the plan step through the recorded journey for one
result target; idempotent per spec; retry re-freezes the stored target and refuses a changed
lineage; the route answers 201, 404 for another Study's run, 422 for an entity the artifact does
not hold; the spend-limit confirmation applies; the design-proposal route still refuses an
interpretation run.

**Chunk 30 -- landed (2026-10-08).** The mission:
`domain/deep_research/interpretation.py:176` @ `68d284e` (`interpretation_mission`, built from the
pinned `compile` specification and the Design Revision only: the aggregate, analysis and Sociomap
payloads are not passed to it, so no respondent number can reach a subject); origins
`interpretation:<KIND>:<research run>/<ids>[#part]`, an over-long entity named by its SHA256. The
boundary: `application/deep_research.py:560` @ `68d284e` (`require_interpretation_mission`,
`interpretation.py:300`; refusal `interpretation_mission_mismatch`, 409, which also refuses a design
spec holding an interpretation subject). The retry: `deep_research.py:641-693` @ `68d284e`
(`resolve_lineage` first, then the stored target re-frozen and its lineage compared; the store is
required). The route: `routers/deep_research.py:403` @ `68d284e`. Tests:
`test_deep_research_interpretation.py` (each kind's exact subjects, determinism, no digit in any
subject, the enqueue rule, the 300-character origin bound),
`test_deep_research_lineage.py::test_interpretation_enqueues_its_mission_and_runs_to_a_sealed_bundle`,
`::test_every_result_targets_mission_holds_no_respondent_number`,
`::test_a_design_derived_request_under_an_interpretation_label_is_refused`,
`::test_a_retry_refreezes_the_stored_target_never_a_newer_result`,
`::test_a_retry_whose_result_no_longer_reads_as_pinned_starts_nothing`,
`::test_design_and_interpretation_share_the_engines_reusable_tracks`, and
`test_deep_research_interpretation_api.py` (201/200, 404, 422, spend confirmation recorded once,
the retry route, the design-proposal route's `not_design_research`). *Measured:* a
`SOCIOMAP_OBJECT` interpretation after a design run over the same revision reused both of the
object's tracks (internal and web, recorded journey) and bought neither; the run completes in the
six steps with a bundle that verifies. *Behaviour changed deliberately:* a design run and an
interpretation run over one revision are no longer one engine request (reuse is per track); the
row-level retry test now answers `lineage_changed`; `InterpretationNotReady` is gone. *Not done:*
an `ANALYSIS_MODULE` target is covered in the domain only -- no workflow in the tests runs the
analysis modules, so no service or API test freezes one; the screen is chunk 24's; the docs
follow-up is § 16.

### Chunk 23 — the rest of the backend: every built route composed (designed 2026-10-08)

**Why now.** The owner, 2026-10-08: "we need to reach as much data and information as possible."
The engine reaches far more than any deployment composes. At `develop @ 4d8f07d`:

- `DeepResearchRuntime` (`exec/deep_research/runtime.py:120-147`) carries one `retrieval` and
  nothing else, and both gates a step builds (`investigate.py:295`, `plan.py:192`) pass only it.
  The gate's `archive`, `datasets` and `archives` (`application/web_retrieval.py:532-572`) are
  reached by tests alone. So the connectors (14–16), Wayback (15) and Common Crawl (18) are
  unreachable in every composition, recorded included, and `runtime.ladder` is never set, so the
  ladder never has a register's data interfaces or a crawl to ask.
- The only live route is Czech Wikipedia (`deep_research_live.py`). `PublicHttpsTransport`
  (any public host, `robots.txt`, chunk 5) is constructed nowhere; Brave (chunk 3) has no route.
- `tools/layer_check.sh:376-382` forbids every composition from naming a connector "until chunk 23
  records their routes and prices".

**Decided here, for the owner to overrule.** Switches, the key and every route's price come from
the deployment, as the Bedrock route's do (ADR 0022 decision 6: the composition is process-wide
and reads no approval). The approved settings (`provider.search.*`, chunks 40–42) are what chunk
44 compares a live run against before it is enqueued; a run pinning them is chunk 43. So 23 does
not wait for 43, and nothing here makes a run go live: every switch is off by default, and live
activation stays chunk 27, after chunk 1.

**Slices, one PR each, in order:**

- **23a. The runtime carries every route.** `DeepResearchRuntime` gains `archive`
  (`ArchiveRetrieval | None`), `datasets` and `archives` (`tuple[DatasetAccess, ...]`); every gate
  a step builds receives them; the recorded composition may be given recorded connectors and a
  recorded archive. A route a composition does not give changes no fingerprint: the track inputs
  name the dataset and archive routes only when there are some. *Tests:* through the real worker
  on recorded exchanges, an agent-directed track's `dataset` action reaches a recorded connector
  and an `archive` action a recorded archive; with none given, every fingerprint equals today's.
- **23b. Free reach: any public host, the connectors, the archive.** Everything that costs
  nothing per call. `AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT` (one e-mail address) turns the fetch
  route into `PublicHttpsTransport` (any public host, every hop checked, `robots.txt` and
  crawl-delay obeyed, chunk 5), beside the search route the deployment has (Wikipedia today);
  `AIA_DEEP_RESEARCH_CONNECTORS`, a list of `datastat`, `nkod`, `eurostat`, `openalex`, `ares`,
  `wayback` (procurement has no live source, `dataset_procurement.py:9-15`, and is refused by
  name), each over `HostPinnedHttpsTransport` to its own host, paced under fan-out, Class C,
  fee-free, and needing a live search route (the gate refuses mixed modes) and the contact
  (OpenAlex's `mailto`); the ladder gets the reputation register's data interfaces.
  `layer_check`'s connector rule narrows to "only `deep_research_runtime.py` composes a
  connector". *Tests:* each name builds its connector on its own route; an unknown or unbuildable
  name, or a connector without the contact or a search route, stops the worker naming the key; a
  private address and a `robots.txt` disallow refused through the composed fetcher; with the keys
  unset nothing changes.
- **23c. Tool spend charged to the study.** The prerequisite for any priced route, found
  2026-10-08: `StepToolMeter` has a zero ceiling and does not charge the study
  (`exec/deep_research/runtime.py`), so the gate refuses every call on a route with a price
  (`tool_metering_unavailable`, `application/web_retrieval.py:614`). This is `deep-research.md`
  chunk 4 (tool usage in the ledger, one migration), taken up here: a priced tool call reserves
  against the study's budget before it leaves and settles once, like a model request.
- **23d. Brave.** `AIA_DEEP_RESEARCH_WEB_SEARCH` = `off` (default) | `wikipedia` | `brave`,
  replacing `AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED` (still read, refused beside the new key).
  `brave` needs `AIA_DEEP_RESEARCH_BRAVE_API_KEY` (a credential reference; the key is never read
  into settings), `AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000`, `AIA_DEEP_RESEARCH_BRAVE_PRICES_AS_OF` and
  the public fetch: search `NON_EU` (§ 10), Class C only, priced per call; the API prices the
  ceiling from the same keys. *Tests:* every missing or invalid key stops the worker naming it; a
  Class B query refused before it leaves; the key in no route, identity, log line or document.
- **23e. Common Crawl.** `AIA_DEEP_RESEARCH_COMMON_CRAWL` with `common_crawl_settings` (all
  `AIA_DEEP_RESEARCH_COMMON_CRAWL_*` keys required; `us-east-1`, `NON_EU`, Class C): the Athena
  index and the archive fetcher, the ladder's crawls; priced at the scan cutoff in the API too.
  The `us-east-1` exception stays chunk 1's sign-off, and the bucket, workgroup and IAM an
  operator's (`docs/architecture/deep-research-common-crawl.md:122-135`).
- **23f. Develop wiring.** `env.example`, `docker-compose.yml` (worker and API), `write-env.sh`
  reading the Brave key from SSM `SecureString` (chunk 4), the Settings document's switches. Every
  switch stays `false` on develop until chunk 27.

Not in 23: triage on the light model (its policy entry is chunk 1's), the focused crawl and
extraction (36–38 call them), documents (6).

**Landed, 2026-10-08** (`feature/dr-web-composition`): **23a** -- `DeepResearchRuntime.archive`,
`datasets`, `archives`, handed to both gates; a route joins `web_identity()` only when given
(`test_dataset_routes_join_a_track_s_inputs_only_when_given`); through the worker, a DOI lead
resolved by a recorded OpenAlex connector reaches the open-access table by rung 7
(`test_a_dataset_route_the_composition_gives_is_one_the_ladder_reaches`, which fails with the
gate wiring removed: the connector is never asked). **23b** -- `public_retrieval` and
`connector_accesses` (`deep_research_live.py`), the two keys and their refusals
(`deep_research_runtime.py`), the ladder given the register when the public fetch is on, the API
stating listed connectors free, Compose and `env.example` carrying both keys (unset on develop);
`test_deep_research_public_reach.py` (10). Building a route sends nothing; nothing here was
run against a live host.

### Phase 6 — structured extraction (33–39; after 29, § 0)

Recorded/offline like every chunk before 25: fictional sites with a known catalogue (one with
JSON-LD, one with only tables, one paginated listing, one behind a login, one disallowed by
`robots.txt`, one carrying personal data). A new harness version, since a run can now return
records (ADR 0021 decision 7, § 16).

**33. Structured capture.** JSON-LD, microdata, OpenGraph and HTML tables kept as a sidecar keyed
by the snapshot id (§ 8.9), parsed from the same response by the public fetch; size and depth
bounded; untrusted like any page text (`detect_instructions`). *Tests:* each form parsed from a
fictional page; the snapshot's text, id and every fingerprint unchanged with and without the
sidecar; a malformed or oversized block refused and counted.

**34. Records.** `RecordSchema` and its presets, `RecordCell`/`Record`, identity and consolidation
rules, the personal-data screen, the sealed `deep_research_dataset`; the artifact type disjoint
from the deterministic ones (checked at import, ADR 0021). Pure domain. *Tests:* a personal field
refused in a schema; an e-mail or phone value dropped and counted; two pages of one product
merge by GTIN, two retailers' prices stay two observations; the seal detects tampering.

**35. Extractors.** Structured data and tables mapped to a schema by code; the extractor
(`RecordProposal`, request kind `extractor` in `request_limits`) for the fields left, each value
located verbatim or refused. *Tests:* a JSON-LD catalogue extracted with no model request; a table
page extracted with none; an invented value refused; a retry replays without paying twice.

**36. Inventory subjects.** The lead marks a subject an inventory and gives its schema;
investigators propose hosts (`crawl`), code admits them (§ 4: `robots.txt`, denylist, barrier
block, the run's host cap) and crawls them with `SiteCrawl` (listing pages, pagination, product
pages; sitemap first), fanned out per host (chunk 21); `extract` on the captured pages; the stop
rule's record saturation; extractor reservations and the inventory caps (§ 9) in the run's cost
ceiling (`run_cost`). *Tests:* a login-walled host and a `robots.txt`-disallowed host never
crawled; a denylisted host refused before any request; the page caps held; a paginated listing
followed to its last page within the cap.

**37. The run's dataset.** Consolidation and sealing per inventory subject; the dataset beside
the bundle and in the run's provenance (ADR 0021); its cells as dataset sources the investigators,
verifier and brief cite; the API's read and CSV/XLSX export, found only through the Study; a
Client Knowledge DATASET proposal a person accepts. *Tests:* a brief number grounded to a dataset
cell; a second identical run reuses every page and record; nothing personal in storage.

**38. Pages that need a browser.** Headless rendering behind `AIA_DEEP_RESEARCH_BROWSER`, through
the same gate, transport rules, `robots.txt` and caps; no logins, no form submission, no CAPTCHA
solving; the rendered DOM captured like any page. After 37, and only if 39 shows static pages
miss what matters.

**39. Extraction accuracy.** On fictional catalogues with known contents, then (with 25) on a few
public Czech catalogues recorded before any run: record precision and recall, cell accuracy,
invented values (target: none), personal values stored (target: none), pages and money per record.

### Phase 7 — Deep Research settings (40–44; before the rest of 23, § 0)

ADR 0022. Development continues on the proposed defaults throughout; nothing here sends anything.

**40. The settings catalogue.** `domain/deep_research/settings.py` (pure): every policy value as a
`SettingDefinition` -- key, group (provider, budgets and presets, models and limits, quotas,
retention, sources, extraction, sign-off), type (integer, money with currency, days, URL, date,
text, host list, per-preset table, status), unit, bounds, its proposed default taken from today's
constant, and whether live requires it. A value is validated by code; a cap only lowers.
`effective(stored)` resolves each key to its approved value or its default, with its origin, and
a digest; `method_digest` covers only the method-shaping keys. *Tests:* every default equals the
constant it replaces; a value out of bounds or of the wrong type refused; a secret-like key cannot
be catalogued; the method digest moves with a cap and with each admission policy (denylist,
personal-data patterns, record presets) and not with a price or a retention.

**41. The store and the service.** Tables `deep_research_setting_versions` and
`deep_research_setting_approvals` (migration), `DeepResearchSettingsRepository` (ADR 0020's shape:
immutable versions, newest approval wins, `NULL` the default, `require_administer`, the
self-approval rule, `access_audit` in the change's transaction) and `/api/v1/deep-research/settings`
(catalogue, history, propose, approve, withdraw), organization-level. A `layer_check` rule keeps the
rows inside the repository. *Tests:* a member is refused; a version is never updated; withdrawing
returns the default; the self-approval setting holds; every change audited.

**42. The settings page.** A Deep Research tab in Settings: each group's settings with value,
origin (proposed default or approved, by whom, when), source link and history; propose and approve
forms over the route; a live-readiness list naming every required setting not yet approved; the
Settings document's Deep Research group and an `ai_runtime` activity whose switches read
configured or off (`lib/ai-runtime.ts`), never "connected"; secrets shown only as configured or
not. *Tests:* the panel renders the catalogue from the API; readiness lists exactly the missing
required keys (Vitest); the document's items name their control (API vs deployment).

**43. Runs pin their settings.** `DeepResearchRuns` resolves the effective settings at enqueue and
stores them, with their digest, on the run beside the run spec; the steps read the pin, never the
store; the engine takes presets, allowances, request limits, register and weights from the pin
where it took constants; the method digest joins every reuse key that crosses runs, so the harness
moves to 3 once; the API's cost ceiling reads the same resolution. *Tests:* with nothing stored,
every request, fingerprint and count equals harness 2's except the harness string (reproduced by
setting it back); an approval changes only runs enqueued after it; a lowered cap reuses no track
made under the old one, and a host added to the denylist or a personal-data pattern added reuses
no capture or dataset made before it; a pin that does not hash to itself fails the run closed.

**44. Live needs approval.** Checked against the run's organization, never at composition: the
worker's composition is process-wide and built before any run, so it builds a live route from the
deployment alone and reads no approval (ADR 0022 decision 6). `DeepResearchRuns` refuses to enqueue
a run that would use a live route until every setting required for live is approved in the
enqueuing organization, naming the missing keys; before any live call, a step parks a run whose pin
does not record every required setting as approved. Offline and recorded runs unaffected. Lands
with or before chunk 27. *Tests:* a start with one required setting unapproved is refused with its
key; approving it admits the next start; withdrawing it refuses again; a worker composed with a
live route starts with nothing approved anywhere; two organizations, one approved and one
not: only the approved one's run is enqueued; a pin missing an approval parks before any call.

### Phase 8 — robustness borrowed from other deep-research tools (45–50; the owner, 2026-10-08)

The owner asked, 2026-10-08, to "use the best ideas" of four public deep-research tools to make this
one more robust. Each was read first-hand (clones at the commits named) and compared in the
session; what follows is what fits AIA's rules, and nothing is copied: ARS is CC BY-NC 4.0, so its
ideas may be re-implemented and its code and text may not.

| Tool | What it is | Idea taken |
|---|---|---|
| [Weizhena/deep-research-skills](https://github.com/Weizhena/deep-research-skills) (MIT) | prompt skills: an outline of items × fields, one agent per item, JSON per item | items × fields is chunks 33–37 already; per-kind search playbooks (49) |
| [sanjay3290/ai-skills `deep-research`](https://github.com/sanjay3290/ai-skills/tree/main/skills/deep-research) (Apache-2.0) | a client for Google's hosted Gemini Deep Research agent | a commercial comparison arm for evaluation (50), never a route (§ 10) |
| openclaw `deep-research` (listings only; its source 404s) | a generic orchestration prompt | nothing |
| [imbad0202/academic-research-skills](https://github.com/imbad0202/academic-research-skills) (CC BY-NC 4.0, v3.23) | a governed academic pipeline: fail-closed gates, four-index citation existence, retraction flags, gold-set calibration with FNR/FPR targets, held-out injection evals | 45, 46, 47, 48 |

**This opens ADR 0021 decision 7 for 46 alone** (a new quarantine reason, retrieval of a work's
status), at the owner's request, as chunks 33–39 opened it; 45, 47 and 48 read or measure the engine
and change nothing in it unless a measurement finds a defect, which the decision already admits;
49 changes the investigator's prompt and so its version.

**45. Injection evaluation.** A held-out corpus of fictional pages under
`packages/aia_core/tests/fixtures/deep_research_injection/`, each labelled: hostile (an instruction
to the model, in English and Czech, direct, paraphrased, split across lines, in a table cell, in
alt text or a heading, aimed at a verdict, a search, a credential or the system prompt) and benign
look-alikes (a news story *about* prompt injection, a recipe saying "ignore the previous step", a
manual's "system message" menu). A runner scores `detect_instructions` on the set -- recall on
hostile, false alarms on benign -- and the set's hash is pinned. Then, through the recorded
journey, a hostile page cannot steer: no finding grounded on it is accepted, and every action an
investigator proposes after reading it still passes the gate (a query carrying a client term is
refused before it leaves). *Done when:* the rates are recorded in § 13; every miss is either fixed
in `INSTRUCTION_PATTERNS` (a defect, under decision 7) or recorded as a finding with its example.

**46. Retracted sources.** A finding is only as good as its source; a retracted paper is a known
bad one. OpenAlex's `is_retracted` is read where the connector already returns a work; a Crossref
connector (`api.crossref.org`, fee-free, its polite pool asked with the fetch contact) reads a DOI's
`updated-by` retraction and correction notices. A captured source whose DOI resolves to a retracted
work carries the status in its snapshot; grounding quarantines a finding resting on it
(`RETRACTED_SOURCE`); a correction is shown, not quarantined. *Tests:* recorded OpenAlex and
Crossref answers; a retracted work's finding quarantined with its notice; an unknown status is
unknown (never "not retracted"); nothing changes for a source without a DOI.

*Landed 2026-10-08* (`feature/dr-retracted-sources`): `domain/deep_research/works.py`
(`normalise_doi`, `WorkStatus`, `resolve_status`: the most severe status any index states stands;
no answer is `UNKNOWN`, never "not retracted"); a page's own DOI from its metadata
(`citation_doi`, `dc.identifier`, `prism.doi`, `bepress_citation_doi`) on its snapshot and its
source facts, omitted when absent; `infrastructure/dataset_crossref.py` (`updated-by`, **unverified**:
neither Crossref nor OpenAlex could be reached from the build environment, so the interface is
written from Crossref's documentation and checked live at chunk 27); OpenAlex's DOI lookup asks
`is_retracted`; the merge step asks each distinct DOI once per run (at most 40), storing each
answer before the next (`WorkStandingRecord`), a lookup left in flight read as unknown and never
re-sent; `RETRACTED_SOURCE` quarantines a retracted or withdrawn work's findings, a correction or a
concern does not. `MERGE_RULES_VERSION` carries `WORKS_VERSION`. Through the worker:
`test_a_finding_resting_on_a_retracted_work_is_quarantined_at_merge`, both ways.

**47. The coverage ledger.** What a run looked at, in the order a reader asks: searches sent and
their hits; pages opened, refused (`robots.txt`, class, host, barrier) and failed; sources captured;
candidate findings; quarantined, by reason; accepted; gaps and acquisition gaps -- per track and in
total, counted by code from the run's own journal and bundle, never by a model. Read through the
run (a view, not a new sealed field), shown beside the brief. The PRISMA flow is its model: a client
sees what was excluded and why, not only what was kept. *Tests:* every count reconciles with the
journal; a reused track counts as found once and costs nothing.

*Landed 2026-10-08* (`feature/dr-coverage-ledger`): `domain/deep_research/coverage.py`
(`coverage_ledger(bundle, journal)`: queries proposed, sent and refused by reason, hits, sources
captured, findings grounded, accepted and quarantined by reason, and per tool the journal's own
outcomes with refusals and failures by reason; per track the same funnel), read through the run
(`DeepResearchRuns.coverage`, `GET …/deep-research/runs/{run_id}/coverage`), never sealed. On the
recorded journey: 8 queries proposed, 6 sent, 2 refused (`class_a_query`,
`egress_route_not_approved_for_class`); 7 sources; 7 accepted, 6 set aside under six named reasons;
one fetch `address_not_public` (`test_deep_research_coverage.py`). The screen that shows it is 24's.

**48. Verifier calibration.** The verifier decides what is accepted; its error rates are unknown.
A gold set of fictional (claim, excerpt, verdict) rows -- supported, overstated, unsupported,
superseded -- and a runner in `tools/dr_accuracy.py` that scores a verifier over it: miss rate (a
bad finding accepted) and false-alarm rate (a good one quarantined), against proposed thresholds
(miss < 0.15, false alarm < 0.10, chunk 1 to approve). With a recorded verifier the runner proves
only the tooling and says so; the verifier stays `NOT_CALIBRATED` in the bundle's versions until a
live run is recorded in § 13 (with 25).

*Landed 2026-10-08* (`feature/dr-verifier-calibration`): `domain/deep_research/calibration.py`
(`GoldSet`, `VerifierAnswers`, `calibrate`, `CALIBRATION_VERSION = "aia-verifier-calibration-1"`) and
`tools/dr_accuracy.py calibrate --gold --answers --out`. The gold set
(`packages/aia_core/tests/fixtures/deep_research_verifier/gold.json`, `verifier-gold-fictional-1`,
pinned `4f09c32e…` in `test_deep_research_calibration.py`) is 28 fictional rows: 12 supported,
6 overstated, 6 unsupported, 4 superseded. Each row is shaped exactly as `verification.verifier_item`
shows a candidate (tested), and code's own supersession rules supersede the four superseded rows and
no supported one (tested). A miss is a bad row judged supported; a false alarm is a good row set
aside, or not judged at all, as code applies it. Each rate carries its Wilson 95 % upper bound, because
with 12 good rows a perfect score still only bounds the false-alarm rate below 0.24. `RECORDED`
answers report `TOOLING_ONLY`; only `LIVE` answers (their model named) meet or miss the proposed
thresholds. Every agent-directed run records `versions["verifier_calibration"] = "NOT_CALIBRATED"`
(`VERIFIER_CALIBRATION`): a person changes it, with the live measurement entered in § 13 (chunk 25).
The runner calls no model.

**49. Search playbooks.** For each subject kind, where its evidence is usually found -- official
statistics (ČSÚ, Eurostat), registers (ARES, procurement), scholarship (OpenAlex), trade and
industry press, the publisher's own site -- rendered from the reputation register into the
investigator's prompt as hints. Code still decides what may leave; a hint names no URL the model
could send. A prompt version.

*Landed 2026-10-08* (`feature/dr-search-playbooks`): `domain/deep_research/playbooks.py`
(`PLAYBOOK_VERSION = "aia-playbooks-1"`, six kinds of evidence: official statistics, ministries and
regulators, public registers, scholarship, industry bodies, the press), rendered by
`render_playbooks(REPUTATION_REGISTER_V1)` into the investigator's prompt, now version 3. Publishers
are named only from the register, by canonical name and a short variant. A name that reads as an
address is left out, and the press is a kind named by no title: follow it to the number's origin.
No hint carries a host, a URL or a query (`test_deep_research_playbooks.py`). The rendered hints are
pinned by hash, so a register change that moves them cannot ship under the old prompt version. Like
the register, the hints are proposed. A new prompt version changes `INVESTIGATOR_VERSION` and with
it every agent-directed track's fingerprint: tracks stored before it are not reused.

**50. A commercial comparison arm.** Chunk 26's arms gain Google's Gemini Deep Research, run by a
person on the public fictional topics only (never a client's), its report graded blind beside ours
on the same rubric. It is a measuring stick, not a route: § 10's verdict on answer engines stands.

*Landed 2026-10-08* (`feature/dr-search-playbooks`): plan text only, in chunk 26's arms. Nothing
in code calls Gemini; the arm runs when chunk 26 does.

## 12. Dependencies

- Tool spend in the ledger (deep-research.md chunk 4) before chunk 25 spends money.
- The AI runtime and research agents on develop (ai-research-activation.md chunk 4).
- Chunk 2 before every agent chunk (9–13, 20).
- Structured extraction: 33 before 35; 34 before 35–37; 36 after 17 (built) and 21; 37 after 36;
  38 after 37 and 39's first measurements; its switch joins chunk 23's composition, and nothing
  live before chunk 1 records § 4's extraction items and 27 activates.

## 13. Measurements and decisions log

**Chunk 1, decisions of the data owner, 2026-10-09** (in this session; the rest of chunk 1
stays open):

- **Search endpoint:** Brave's Web Search only, as chunk 3 built it; not the LLM Context
  endpoint, whose page text is Brave's extract and could not be grounded as a capture AIA
  made itself (§ 4, ADR 0017).
- **The key (D8):** an SSM SecureString, the develop host's existing pattern; proposed name
  `/aia/develop/deep-research/brave-api-key`, exported to the worker as
  `AIA_DEEP_RESEARCH_BRAVE_API_KEY` (chunk 4). The owner reports the key is stored in AWS;
  not verified from the agent session, which has no AWS access.
- **Brave's terms:** read from Brave's public pages (the terms pages themselves are blocked
  from the agent environment): Search plan $5 per 1,000 requests with $5 free credit a month;
  storing results needs a plan that explicitly grants storage rights; query logs up to 90
  days on standard plans, zero retention on Enterprise only. Whether keeping hit metadata
  (URL, title, snippet, rank) for audit and resume needs storage rights, and whether failed
  requests are billed, is for Brave support to answer (the question is drafted for the owner
  to send). **Live search stays off until Brave answers.**
- **The light model:** Claude Haiku 4.5 on Bedrock's EU route, Class C only, as the triage
  model (its ADR 0010 policy entry is chunk 23's).
- **PDF tables (chunk 6):** pdfplumber (MIT) may be added.
- **Budgets, retention, register, weights, near-duplicate threshold:** left as proposed
  defaults, to be approved on Settings → Deep Research; chunk 44 refuses live until they are.

**Chunk 43a, 2026-10-09** (`feature/dr-settings-pin`): `domain/deep_research/settings.py`
`pin` / `read_pin` (`SETTINGS_PIN_CONTRACT = "aia-dr-settings-pin-1"`): every key's value and
origin (approval version, who, when), `pin_digest` over the whole body, `settings_digest` and
`method_digest`; a pin from another catalogue, with a key missing or twice, or that does not
hash to every digest it states is `SettingsPinCorrupt` by reason (`pin_unreadable`,
`catalogue_changed`, `pin_altered`), never a default. `settings_in_force_for_study` reads the
organization's settings through the enqueuing Study's own scope (no administration context is
built). `DeepResearchRuns._enqueue` pins them on the run (`metadata.settings_pin`) and in the
plan step's input beside the request; `run_settings(metadata)` reads them back verified (`None`
for a run enqueued before pins). The plan step fails a pin that does not prove itself
(`settings_<reason>`) before anything is asked. The pin is about 8 KB per run. Nothing reads
its values yet, so with nothing approved every request, harness string and step fingerprint is
harness 2's, unchanged (43b moves the engine and the harness). Known and left to 43b: the
idempotency key is still the spec's alone, so a start repeated after an approval returns the
run already enqueued under the old pin; 43b adds the method digest to it. Tests:
`test_deep_research_settings_pin.py` (15), `test_deep_research_journey.py::
test_a_run_whose_settings_pin_was_altered_is_never_executed`.

**Chunk 43b, 2026-10-09** (`feature/dr-settings-engine`, stacked on 43a): `HARNESS_VERSION`
moves to `aia-deep-research-harness-3` (ADR 0022 decision 5). `DeepResearchRequest` gains
`settings_method`, the pinned settings' method digest once any method setting is approved
(`EffectiveSettings.approved_method`), else `None` and left out of the stored form; the
request's `method_identity()` -- the harness, and the digest when there is one -- replaces the
bare harness in the four cross-run reuse keys (track, both verification keys, synthesis,
brief). A changed approved method value is therefore another request, another run (the
idempotency key is the spec's, which holds the request's fingerprint) and reuses nothing made
under the old one; a non-method approval (retention) changes neither. The plan step fails a
run whose pin's method is not its request's (`settings_mismatch`). Measured: with nothing
approved, every track fingerprint under harness 3 equals harness 2's once only the harness
string is set back (`5ade329c...`, `test_harness_three_changes_nothing_but_its_name`); the
request-limit table is unchanged (`b5fa8690...`, pinned under both names). Captures and
datasets are run-scoped today, so the denylist and personal-data patterns have no cross-run
key to join yet; they join the dataset key when one crosses runs (chunk 37). Still constants
in the engine: presets, allowances, request limits, register, weights (43c).

**Chunk 43c, 2026-10-09** (`feature/dr-settings-values`): the engine reads the run's settings
where it read the code's tables. `settings.route_allowances` and `settings.request_limits`
build the two tables from an `EffectiveSettings`, each value capped at the code's (lower-only,
so a pin can never raise a cap) and the code's own where the catalogue holds no key; with
nothing approved both equal `ROUTE_ALLOWANCES` and `REQUEST_LIMITS` value for value.
`budgets.call_bounds` and `run_cost.deep_research_cost_ceiling` take `allowances`;
`DeepResearchRuns.cost_ceiling` takes the settings, and `_enqueue` reads them once for the pin
and the ceiling it asks about. The API prices that ceiling under the study's request limits
(`routers/deep_research._study_prices`), so the 409 a start answers is what the worker will
reserve. The worker: the plan step records the pinned limits on the plan
(`PlanRecord.request_limits`, left out of the stored form when they are the code's, so a plan
under defaults stores and hashes as before), and every step sizes its requests by them
(`DeepResearchConfig.under`, `_Step._planned_runtime`). Request limits are method settings, so
a changed one is already another run (43b). Presets, the register and the weights are status
keys -- a code-owned table approved as is -- with no value to read: their approval is chunk
44's live sign-off, not an input. `budgets.run_limit.<preset>` is read by nothing yet; chunk 44
decides whether it refuses a start. Tests: `test_deep_research_settings_values.py` (7),
`test_deep_research_spend_api.py::test_an_approved_request_limit_prices_the_ceiling_a_start_is_asked_about`,
`test_deep_research_journey.py::test_an_approved_request_limit_sizes_every_request_of_its_kind_and_only_it`
(verifier requests at 2,048 output tokens, every other kind unchanged).

- **Chunk 19, 2026-10-05** (`6309fe8`): near duplicates at the default 0.8, precision 11/11 and
  recall 11/24; at 0.7, precision 19/19 and recall 19/24; relevance R-precision 1.0, 0.8, 1.0, 1.0
  on the hand-labelled fictional corpus. The threshold is chunk 1's decision.
- **Chunk 21, 2026-10-06** (#166, `docs/architecture/deep-research-fan-out.md` § 6): 24 recorded
  tracks, 4 workers and 4 model slots investigate in 11.0 s against 32.6 s on one worker, with
  every planned round checkpointed.

- **Chunk 5 follow-up, 2026-10-07** (robots.txt off the standard library, § 15): 30,000 fuzzed
  robots.txt files from 58 line shapes (groups, blank lines, `*`/`$`, percent-encoding, `//`
  paths, schemes, crawl delays) × 6 of 39 URLs each, seed 11. The new `RobotsPolicy` against the
  old one on Python 3.12.3: 0 of 180,000 decisions and 0 of 30,000 crawl delays differ. The new
  one on 3.12.3 against 3.13.16: 0 and 0. The old one on 3.12.3 against 3.13.16: 6,073 decisions
  (2,398 files) and 127 crawl delays. The two inputs that raise on 3.12 are left out of the
  comparison and pinned by a test instead.

- **Chunk 29, 2026-10-07** (`feature/dr-design-proposals`): no measurement; the proposal is
  code over the sealed bundle and sends nothing. Over the recorded journey's first pass the
  proposal has one item per bundle subject, evidence and gaps both present, and an accept of one
  item writes one revision whose only change is `design_research` and one ledger row
  (`apps/executors/tests/test_design_research_proposals.py`, 9 tests). Decided here, for the
  owner to overrule: the accepted evidence is stored in the design (bounded to 32 KB) rather than
  referenced, so a revision carries its own context and the design jobs read it without a
  second lookup; a second accept from the same run is stale, so taking more evidence later is a
  new run over the new revision, which reuses the engine's unchanged tracks.

## 14. What this plan does not do

- Class B queries. They would research better; they need an EU-processing search route, D6 and
  DR-2b. Candidate: Linkup under a signed agreement.
- Anything on § 4's never list.
- Production. Develop only, fictional studies only, as ADR 0010 accepts.
- Freshness of reused tracks (deep-research.md § 12 item 6).
- Crawling at large scale (tens of thousands of pages, a market-wide index of our own): Common
  Crawl's archive (18) is the route to breadth; our own crawling stays hundreds of pages per run.
- Submitting forms, logging in, solving CAPTCHAs or reaching any account-only price, even with a
  browser (38).
- A client-facing dataset: extracted datasets stay internal until a client-facing report contract
  and ADR 0019 gate 3 exist.

- **Chunk 45, 2026-10-08** (`feature/dr-robustness`): the instruction detector on two fictional
  sets (`packages/aia_core/tests/fixtures/deep_research_injection/`, pinned in
  `test_deep_research_injection_eval.py`). Development set (30 hostile, 25 benign; EN and CS):
  `aia-instructions-1` caught 15/30 with 6 false alarms; `aia-instructions-2`, fixed against it,
  catches 30/30 with 2 false alarms (B01, B16: articles quoting an injection; kept, recall
  preferred). Held-out set (15 + 15), written after and scored once: **4/15 caught, 1 false alarm**
  (Y03, "must not share credentials"). One fix independent of the set followed -- the detector
  now reads NFKC text, as grounding does -- and catches 5/15; the set is spent.

## 15. Findings

**F-45-1 (chunk 45, 2026-10-08). The instruction detector does not generalise; it is a tripwire,
not the boundary.** 1. Claim: on pages written after its patterns were fixed it caught 4 of 15
instructions aimed at a model. 2. Anchor: `domain/deep_research/grounding.py` `INSTRUCTION_PATTERNS`,
`detect_instructions` (`aia-instructions-2`). 3. Reproduction:
`test_deep_research_injection_eval.py::test_the_held_out_rate_does_not_fall_below_what_was_measured`
(the misses are listed by `_scored("heldout.json")`). 4. Consequence: a hostile page on a host the
source table rates acceptable (media, a wiki, an official site's comment section) can carry text a
model reads as an order and a finding can quote; on an unknown host it cannot, because an unknown
host scores 0.2 against the 0.55 acceptance threshold
(`test_a_hostile_page_the_detector_misses_still_yields_no_accepted_evidence`). 5. Smallest fix:
none in the patterns -- more regexes fit the set they are written against. The structural answer is
what already holds (unknown hosts below acceptance, verbatim grounding, the gate on every query,
an independent verifier); the open part is user-written text on acceptable hosts, which the
register's tiers (chunk 8) and the verifier's calibration (48) bound. 6. Test: the held-out ratchet
above; a fresh measurement needs a new set, better one written by someone else (a red team).

- `CLAUDE.md` § 2 says of `infrastructure/web_retrieval.py` "no live adapter exists (DR-2)" and of
  `deep_research_runtime.py` "no web retrieval exists"; `web_retrieval_live.py` and the Wikipedia
  switch exist @ `b2d43f7`. Stale; see § 16.
- Grounding accepts a claim whose numbers occur in its quote even when the claim changes their
  population, unit, period or geography (`domain/deep_research/grounding.py:190-192` @ `b2d43f7`).
  Reproduced 2026-10-05: `ground(source_ref="S1", quote="kupuje rostlinné nápoje 45 % domácností",
  claim="Rostlinné nápoje kupuje 45 % všech dospělých lidí v Česku.", sources={"S1": …"45 %
  domácností v Česku."})` returns `Grounding(span=(15, 54), failure=None)`. Consequence: a
  household share can enter a brief as a share of adults unless the verifier happens to catch it.
  Smallest fix and the test that catches it: chunk 7 (`MEASURE_NOT_IN_SOURCE`; its first test is
  this case). Today's verifier (`Verdict.OVERSTATED`) is the only line of defence.
- **Structured data is discarded at capture** (2026-10-07). `_SKIP` drops every `<script>`
  (`infrastructure/web_retrieval.py:196` @ `d2e038a`), so schema.org JSON-LD -- the form most
  catalogues publish product, price and availability in -- never reaches a snapshot; microdata is
  not read and HTML tables are flattened. Consequence: an inventory could only be read back out of
  running text by a model. Fix: chunk 33's sidecar (snapshot text and ids unchanged). Test: chunk
  33's first test, a fictional product page whose price is only in JSON-LD.
- **"Authoritative hosts" is a docstring, not a check** (`application/site_crawl.py:1-6` @
  `d2e038a`): `SiteCrawl` accepts any host `CrawlScope` accepts. Harmless while nothing calls it;
  chunk 36 states the admission rule in code (§ 4) before anything does.
- **A barrier is detected, not refused** (`domain/deep_research/acquisition.py:466`
  `detect_barrier` @ `d2e038a`): the gate fetches a login or paywall page and only the ladder
  ignores it. For inventory hosts, chunk 36 makes it a block on admission.
- **No general personal-data filter exists** for pages: only the ARES and procurement connectors
  keep field allowlists. Chunk 34's screen is the first for page-derived values.

- **The robots.txt decision changed with the Python interpreter** (2026-10-07).
  1. *Claim:* `RobotsPolicy` asked `urllib.robotparser` for its second, stricter reading, and that
     module's answer changes between Python patch releases: 3.13.8 changed its normalisation
     (gh-138515), 3.13.14 replaced its first-match algorithm with RFC 9309's (gh-138907: longest
     match, allow on a tie, merged groups, `*` and `$`), and 3.13.0 changed `urlunparse`, which
     it re-joins paths with (gh-85110: `//x` becomes `////x`). On 3.13.14 or later the stricter
     reading the chunk 5 decision relies on was gone.
  2. *Anchor:* `domain/deep_research/robots.py:240-246` (parse, crawl delay) and `:282`
     (`can_fetch`) @ `4dce18f`.
  3. *Reproduction:* on Python 3.13.14 or later, `pytest
     packages/aia_core/tests/test_deep_research_robots.py` @ `4dce18f` fails 3 of 20
     (`test_groups_for_the_same_agent_are_merged`,
     `test_the_most_specific_rule_wins_and_allow_wins_a_tie`,
     `test_where_the_standard_library_is_stricter_its_answer_stands`); all pass on 3.12. One line:
     `RobotsPolicy.parse("User-agent: *\nDisallow: /\nAllow: /public\n").refusal("https://stats.example/public/a")`
     is `"robots_disallowed"` on 3.12.3 and `None` on 3.13.16.
  4. *Consequence:* a worker on 3.13.14+ requests pages the conservative policy refuses (`/public/a`
     above), and CI cannot see it: it runs 3.12 (`.github/workflows/ci.yml:22`), as the develop
     image does (`deploy/docker/python.Dockerfile:16`), while `requires-python = ">=3.12"` allows
     either. Latent on develop today; live for anyone running the suite on 3.13.
  5. *Fix:* AIA owns the second reading. `_FirstMatchReading` ports Python 3.12's `parse`,
     `can_fetch` and `crawl_delay`, and re-joins URLs with its own `_join`; `urllib.parse` only
     splits them. No `urllib.robotparser` import is left. Measured identical to the old code on
     3.12 and across interpreters (§ 13). *Trade-off:* about 160 lines that freeze a 1996
     reading's quirks (blank lines end a group; a group named by a substring of the token
     applies), kept because they are where the second reading is stricter.
  6. *Tests:* the three above, now the same on every interpreter; the stdlib-asserting lines in
     them now assert the same of `_FirstMatchReading`, and the third is renamed
     `test_where_the_first_match_reading_is_stricter_its_answer_stands` with its assertion kept
     and a substring-agent case added. New: `test_the_decision_does_not_ask_the_standard_librarys_parser`
     (fails if any `RobotFileParser` method is called) and
     `test_a_path_starting_with_two_slashes_is_compared_as_written` (fails on 3.13 if
     `urlunparse` replaces `_join`).
- **A host's robots.txt could make the parse raise** (2026-10-07). On Python 3.12 (CI and the
  develop image) `Crawl-delay: ²` (`isdigit` but not `int`) or `Disallow: //[x` (`urlparse`:
  "Invalid IPv6 URL") raised `ValueError` out of `RobotsPolicy.parse` (`robots.py:243` @
  `4dce18f`), and `_read_robots` catches only `ToolCallFailed` and `FetchRefused`
  (`infrastructure/web_retrieval_live.py:472` @ `4dce18f`). Reproduction: on 3.12,
  `policy_for_response(200, "User-agent: *\nCrawl-delay: ²\n".encode())` raises. Consequence: a
  fetch from that host fails with an unclassified `ValueError` instead of a reading or a
  journaled refusal. How a track reports it was not traced (hypothesis beyond the transport).
  Fix: the port ignores both lines, as 3.13.15 (gh-153417) and 3.13.8 (gh-138432) do. Test:
  `test_a_file_the_old_parser_could_not_read_is_read`.

## 16. Doc follow-up

*Applied 2026-10-06 by the ADR 0021 synchronisation PR, except the ADR 0017 amendment text, which
waits for chunk 1 as it said.* For the docs PR after chunk 0 merges:

- `.planning/overview.md`, DR-2 row: "Proposed for Class C: Brave Search API, within a
  lead-researcher, agent-directed, code-gated Deep Research; see
  `.planning/plans/deep-research-web-search.md`. Class B open (candidate: Linkup under an EU
  agreement)."
- ADR 0017 amendment (after chunk 1): "A lead researcher plans the run, scales effort per subject
  and delegates waves of parallel investigators through a closed task contract. Investigators choose
  their next searches, the results and links to open, the document parts to read and the sources to
  chase, by ref; an acquisition ladder reaches needed sources by lawful public routes only. Code
  classifies, sends and journals every call, grounds every finding in the track's own snapshot with
  its full measure, traces it to its primary publisher, verifies it independently and computes its
  confidence. Sources include PDF, XLSX, CSV, public datasets, archives and focused crawls."
- `CLAUDE.md` § 2: the `web_retrieval.py` and `deep_research_runtime.py` entries corrected; after
  chunk 23, the new routes, connectors and switches.
- `docs/architecture/deep-research.md` § 12 item 1: point to this plan.
- ADR 0017 amendment (after chunk 1), one more sentence: "Where the research needs an inventory,
  the run extracts records from the pages it captures -- structured data and tables by code, a
  light model only for values found verbatim in the page -- into a sealed dataset beside the
  bundle, whose every cell cites its capture; agents choose the hosts, code admits them by
  `robots.txt`, an operator denylist and the absence of any access barrier, and drops personal
  data before storage."
- ADR 0021 decision 7: "Opened once for structured extraction (`deep-research-web-search.md`
  chunks 33–39, the owner's request, 2026-10-07) under a new harness; the rest of the boundary
  stays frozen."
- `CLAUDE.md` § 2, after chunk 37: the dataset artifact, the `crawl` and `extract` tools, and the
  extraction switch.
- `docs/architecture/adr/README.md`: the ADR 0022 row ("Deep Research's policy values are data an
  Admin approves on a settings page; approved values are pinned per run; switches, secrets and the
  model route stay in the deployment; rails stay code" -- **Proposed**), and 0020's row: "its 'not
  decided' live-settings question taken up for Deep Research's policy values by 0022".
- `CLAUDE.md` § 2, after chunks 41–43: the settings module, the two tables and their repository,
  the route, the Settings tab, and "a run pins its Deep Research settings at enqueue".

*For the docs PR after chunk 29 merges:*

- `CLAUDE.md` § 2, `domain/deep_research/`: "`design_proposals.py` a Design Research run's
  proposal from its sealed bundle (an item per subject: its findings, or a gap) and
  `apply_to_design`: the accepted items under the design's `design_research` key, nothing else
  changed (chunk 29)". `application/`: "`design_research.py` DesignResearchProposals: a
  completed Design Research run's proposal; a person's accept (EDIT_STUDY + APPROVE_GATE) into a
  new Design Revision on the run's own baseline, recorded once per selection in the approval
  ledger (ADR 0019 gate 1)". `routers/`, under deep research: "a Design Research run's
  design proposal and its accept".
- `docs/architecture/deep-research.md`: the two routes (`GET …/runs/{run_id}/design-proposal`,
  `POST …/design-proposal/accept`) and the `design_research` design key as `EXTERNAL_CONTEXT`,
  never respondent context.
- ADR 0021, Consequences: "Design Research's proposals and their accept exist
  (`deep-research-web-search.md` chunk 29): built by code from the sealed bundle, applied only by
  a person into a new Design Revision on the run's own baseline."
- `ARCHITECTURE.md`, the approval ledger's subjects: `design_research` beside `ai_proposal`
  (migration `a7c3e9b1d5f2`).

*For the docs PR after chunk 30 merges:*

- ADR 0021, Consequences: the table's `INTERPRETATION_RESEARCH` row becomes "yes" for enqueue and
  execute, and the bullet "Interpretation Research is frozen, never executed, until chunk 30 …"
  is replaced by: "Interpretation Research enqueues and executes since
  `deep-research-web-search.md` chunk 30: its engine request's subjects are the target's
  mission, built by code (`domain/deep_research/interpretation.py`) from the pinned
  specification and the Design Revision the producing run executed, never from a respondent
  number; the enqueue boundary refuses a spec whose subjects do not carry its own target's
  origin (`interpretation_mission_mismatch`); a retry re-freezes the stored target and is
  `lineage_changed` when a pin no longer reads as pinned."
- `.planning/open-items.md`: OI-88 closed by chunk 30 (the anchors in its landed note).
- `CLAUDE.md` § 2, `domain/deep_research/`: "`interpretation.py` an Interpretation Research
  run's mission: subjects built by code from its target, the pinned specification and the
  Design Revision (no respondent number), each with an `interpretation:<KIND>:<entity>`
  origin; `require_interpretation_mission`, the enqueue boundary's check (chunk 30)".
  `application/deep_research.py`: replace "`_enqueue`, the one enqueue boundary, refuses every
  INTERPRETATION_RESEARCH spec until chunk 30 (start_interpretation and a stored row's retry:
  interpretation_not_ready, OI-88)" with "`_enqueue`, the one enqueue boundary, refuses a spec
  whose request is not its own purpose's (an interpretation request holds only its target's
  mission: `interpretation_mission_mismatch`); an interpretation retry re-freezes the stored
  target, `lineage_changed` when a pin moved". `routers/`, under deep research: "Interpretation
  Research's start (`POST …/deep-research/runs/interpretation`)".
- `docs/architecture/deep-research.md`: the route `POST …/runs/interpretation` (`target`,
  `preset_name`, `channels`, `confirm_cost_usd`, `title`; 201/200, 404 another Study's result,
  422 an entity the artifact does not hold), the mission table (§ 11 chunk 30 above) and the
  error codes `interpretation_mission_mismatch` and `lineage_changed`; `interpretation_not_ready`
  no longer exists.

*For the docs PR after the robots.txt fix (§ 15, 2026-10-07) merges:*

- `.planning/open-items.md`: the two robots.txt findings in § 15, each with its OI number, and
  both closed by that PR.
- `AGENTS.md`, a new section:

  ```markdown
  ## A standard-library parser's answer can change in a patch release (robots.txt, 2026-10-07)

  CI pins Python 3.12, and `requires-python = ">=3.12"`. `urllib.robotparser` read
  robots.txt by the 1996 first-match draft until Python 3.13.14 (gh-138907) gave it RFC 9309's
  algorithm, in a *patch* release; 3.13.8 (gh-138515) had already changed its normalisation,
  and 3.13.0 (gh-85110) changed `urllib.parse.urlunparse` (`//x` re-joins as `////x`). A
  policy that asks the module, or re-joins with `urlunparse`, changes answer with the
  interpreter, and a CI pinned to one version cannot see it. AIA's "never less strict than the
  first-match reading" guarantee was silently gone on 3.13.14+
  (`test_deep_research_robots.py`, 3 failures there).

  ```python
  # WRONG: the second opinion is whatever this interpreter's stdlib believes today
  from urllib.robotparser import RobotFileParser
  stdlib = RobotFileParser()
  stdlib.parse(lines)
  if not stdlib.can_fetch(AGENT_TOKEN, url):
      return ROBOTS_DISALLOWED

  # RIGHT: the reading is AIA's code, frozen and tested; urllib.parse only splits URLs
  first_match = _FirstMatchReading.parse(lines)          # a port of 3.12's reading
  if not first_match.allows(AGENT_TOKEN, url):           # re-joins with its own _join
      return ROBOTS_DISALLOWED
  ```

  The rule: when a decision is policy (what may be fetched, what is admitted), own the
  algorithm and pin it with tests. Use the standard library for formats (splitting a URL,
  decoding), not for judgements. To check that a port is faithful, compare decisions on fuzzed
  input against the original on the interpreter that has it, then across interpreters
  (`deep-research-web-search.md` § 13: 0 of 180,000 differ).
  ```
