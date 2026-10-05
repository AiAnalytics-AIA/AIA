---
status: planned
chunks:
  - "[x] 0. This plan"
  - "[ ] 1. Sign-off: design, Brave and its written terms, D8, budgets, the light model, quotas"
  - "[ ] 2. Structured output with thinking on (no forced tool choice) for Deep Research agents"
  - "[ ] 3. Brave search adapter"
  - "[ ] 4. The search key as a credential reference"
  - "[ ] 5. Public-web fetch: any public host, robots.txt, links, run snapshot cache"
  - "[ ] 6. Documents: PDF, XLSX, CSV, read in parts, tables kept as tables"
  - "[ ] 7. Measures: every number with its unit, scale, period, geography, population, denominator"
  - "[ ] 8. Source tiers and the reputation register"
  - "[ ] 9. The investigator: parallel actions, refs, refusals, transcript"
  - "[ ] 10. The acquisition ladder: every lawful way to reach a needed source"
  - "[ ] 11. The lead researcher: effort scaling, delegation, waves, re-planning"
  - "[ ] 12. Verification: adversarial verifiers, primary tracing, triangulation, conflicts"
  - "[ ] 13. Confidence by code, gaps, acquisition gaps, the brief"
  - "[ ] 14. Connectors I: ČSÚ DataStat and the national open-data catalogue"
  - "[ ] 15. Connectors II: Eurostat, OpenAlex, Wayback CDX"
  - "[ ] 16. Connectors III: ARES (legal entities), public procurement"
  - "[ ] 17. Focused crawler for authoritative hosts"
  - "[ ] 18. Common Crawl URL index and archived pages"
  - "[ ] 19. Code filters: near-duplicates, language, relevance"
  - "[ ] 20. Triage readers on the light model"
  - "[ ] 21. Fan-out: parallel tracks, per-host politeness, model concurrency"
  - "[ ] 22. Presets, budgets and the run's cost ceiling"
  - "[ ] 23. Composition, switches, prices; Settings"
  - "[ ] 24. The Deep Research screen: plan, progress, findings, gaps, transcript"
  - "[ ] 25. Accuracy evaluation on a truth set of public Czech facts"
  - "[ ] 26. Quality evaluation: 20 questions, three arms, rubric judge, blind grade"
  - "[ ] 27. Develop activation and the live acceptance"
---
# Deep Research — wide, precise, and defensible

**Status:** planned · **Owner:** research-engine + ai-runtime · **Started:** 2026-10-05 ·
**Base:** `develop` @ `b2d43f7`
**Parent:** [deep-research.md](deep-research.md) chunk 13 (*Live enablement, blocked on DR-2*).
**Decides (proposed; chunk 1 is the data owner's sign-off):** DR-2 for Class C (Brave Search API),
an amendment to ADR 0017 (agents direct the research; code still sends every call), a second
model policy entry under ADR 0010 (a light triage model), and the boundaries in § 4.

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
reached is reported as a gap, with what it would take a person to close it.

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

## 4. Boundaries (non-negotiable)

"Every trick in the book" means every **lawful, public** route to a source. Never:

- logging in, using anyone's credentials, or reaching anything behind a paywall, CAPTCHA or
  registration wall; using an archive or mirror to get round a paywall;
- ignoring `robots.txt` or a site's terms on automated access; disguising the user agent;
  rotating addresses or proxies to evade a rate limit;
- the dark web or Tor; pirate mirrors;
- collecting personal data: extraction keeps legal-entity and aggregate facts and drops
  person-level data before storage (GDPR);
- republishing: snapshots stay internal; a report quotes short excerpts with their source;
- Class A or B material in any query or URL: Class C only until an EU-processing search route and
  D6 exist.

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
| Verify | strong model, independent | every finding the brief would use | supported, overstated, unsupported, superseded |
| Synthesize | strong model | 1 | the brief: answers, conflicts, gaps, acquisition gaps |

Standard and Deep presets (§ 9) skip triage and the crawlers and run fewer investigators.

### 5.2 Agents

| Role | Model | Contract (closed, versioned) | Can |
|---|---|---|---|
| Lead researcher | strongest on the EU route (own policy entry) | `ResearchPlan`, `Wave`, `Replan` | plan, size, delegate, move budget, open tracks for gaps and conflicts |
| Investigator | strong | `InvestigatorTurn` | propose up to 5 actions a turn; propose evidence and leads |
| Triage reader | light (`RESEARCH_TRIAGE`) | `TriageVerdict` | judge one page; propose ≤ 3 candidate quotes |
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
reason three times (`STOP_REFUSALS`).

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

## 9. Presets and cost (estimates; measured in chunks 25–26)

A turn reads up to about 8,000 tokens of page text, about $0.04 at the develop policy's prices;
multi-agent research uses about 15× the tokens of chat (Anthropic's measurement).

| Preset | Agents and allowances | Triage, crawl, Common Crawl | Estimate per run | Time |
|---|---|---|---|---|
| Standard | 1 lead; ≤ 12 tracks; per track 8 searches, 20 opens, 15 turns | no | about $5–7 | minutes |
| Deep | 1 lead, 3 re-plans; ≤ 20 tracks; per track 15 searches, 40 opens, 30 turns | no | about $12–18 | under an hour |
| Exhaustive | 1 lead, subject leads; 20–50 investigators | yes | about $60–100 | 1–3 hours |

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
measurements in § 13. Chunks 2–24 build and test offline on recorded doubles (each connector chunk
starts with a written check of its terms); only 25–27 send anything. Within a phase, chunks may run
in parallel unless an order is stated.

### Phase 0 — decide

**1. Sign-off (human; no code).** The data owner approves: this design and § 4; the ADR 0017
amendment (§ 16); Brave on a plan that grants storage and AI use (plan, terms URL and date, price,
failed-request billing, retention, recorded here); D8 for the key (chunk 4's proposal or Secrets
Manager); run budgets per preset; the lead's model and the light model's ADR 0010 policy entries; a
Bedrock quota request for chunk 21; the snapshot retention period; the tiers, the register and the
confidence weights (§§ 8.6–8.7). *Done when:* each item is recorded in § 13 with a date.

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
fictional site with a crawler trap and an off-host redirect.

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
`AIA_DEEP_RESEARCH_CRAWL`, `AIA_DEEP_RESEARCH_COMMON_CRAWL`, `AIA_DEEP_RESEARCH_TRIAGE`; dated prices
for each paid route; every route `approved_for={CLASS_C_INTERNAL}`. Anything missing or invalid
stops the worker at start, naming the key. Settings shows each as configured or off, never
"connected" (`apps/web/src/lib/ai-runtime.ts`).

**24. The Deep Research screen.** The plan; live progress (stage, tracks, counts, spend so far);
findings with measure, source, tier, primary or secondary, confidence and verdict; conflicts; gaps;
acquisition gaps with how to obtain each; the transcript per track; cancel at any point, keeping
what was captured; the snapshot retention job.

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

**27. Develop activation and the live acceptance.** Parameters set, deployed, the worker's start-up
log read; one run per preset for a fictional client within the owner's budget; run ids, counts and
spend (model, search, connectors, Athena separately) recorded in § 13. Then tick the parent plan's
chunk 13 for Class C.

## 12. Dependencies

- Tool spend in the ledger (deep-research.md chunk 4) before chunk 25 spends money.
- The AI runtime and research agents on develop (ai-research-activation.md chunk 4).
- Chunk 2 before every agent chunk (9–13, 20).

## 13. Measurements and decisions log

(Empty. Each chunk records its measurements here, and chunk 1 each decision with its date.)

## 14. What this plan does not do

- Class B queries. They would research better; they need an EU-processing search route, D6 and
  DR-2b. Candidate: Linkup under a signed agreement.
- Anything on § 4's never list.
- Production. Develop only, fictional studies only, as ADR 0010 accepts.
- Freshness of reused tracks (deep-research.md § 12 item 6).

## 15. Findings

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

## 16. Doc follow-up

For the docs PR after chunk 0 merges:

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
