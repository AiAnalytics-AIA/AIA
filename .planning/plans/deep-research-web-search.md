---
status: planned
chunks:
  - "[x] 0. This plan: the design and the provider choice (DR-2, Class C)"
  - "[ ] 1. Sign-off: the design, Brave and its written terms, D8, the run budgets"
  - "[ ] 2. Brave search adapter, with operators (site, freshness, language) and 20 results"
  - "[ ] 3. The API key as a credential reference (D8, for this route)"
  - "[ ] 4. Public-web fetch: any public host, robots.txt, user agent, links kept, run snapshot cache"
  - "[ ] 5. Documents as sources: PDF, XLSX and CSV, read in parts, grounded by page, sheet and cell"
  - "[ ] 5a. Thinking between results: structured output without a forced tool choice"
  - "[ ] 6. The agent-directed investigator: parallel actions per turn, loop, refs, refusals, transcript"
  - "[ ] 7. Leads and recovery: citation chase, result annotations, search feedback"
  - "[ ] 8. The lead researcher: effort scaling, delegation contract, waves, gaps, conflicts, budget"
  - "[ ] 9. Official-data retrieval: Czech open-data catalogue and statistics office (verify first)"
  - "[ ] 10. Budgets, presets and the run's cost ceiling"
  - "[ ] 11. Composition, switches and dated prices"
  - "[ ] 12. Czech source table (DR-5 input)"
  - "[ ] 13. Quality evaluation on real search: three arms, rubric judge and human grade"
  - "[ ] 14. Develop activation and one live fictional acceptance"
  - "[ ] 15. Scale sign-off: the funnel, the boundaries, the Exhaustive budget, quotas"
  - "[ ] 16. Fan-out: parallel investigators, per-host politeness, model concurrency limits"
  - "[ ] 17. Focused crawler for authoritative hosts: sitemaps, bounded breadth-first"
  - "[ ] 18. Common Crawl URL index and archived pages, from AIA's own AWS account"
  - "[ ] 19. Deep-web connectors, one per source after its terms check"
  - "[ ] 20. The funnel's code filters: near-duplicates, language, relevance ranking"
  - "[ ] 21. Triage readers on a light model (second model policy entry, ADR 0010)"
  - "[ ] 22. Subject leads, adversarial verifiers, independent-publisher triangulation"
  - "[ ] 23. The Exhaustive preset: long runs, progress, storage retention"
  - "[ ] 24. Evaluation at scale: does Exhaustive beat Deep by enough to pay for it"
---
# Deep Research on the open web — agent-directed, code-gated, at web scale

**Status:** planned · **Owner:** research-engine + ai-runtime · **Started:** 2026-10-05 ·
**Base:** `develop` @ `b2d43f7`
**Parent:** [deep-research.md](deep-research.md) chunk 13 (*Live enablement, blocked on DR-2*).
**Decides (proposed, needs the data owner):** DR-2 for **Class C** queries, and an amendment to
ADR 0017: investigators choose their next search and the next page to open; code still sends
every call. Class B stays refused (see *What this plan does not do*).

## Problem

Deep Research has no web search. The production composition blocks every web track; the only
live route is fee-free Czech Wikipedia (`apps/executors/src/aia_executors/deep_research_live.py`
@ `b2d43f7`, behind `AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED`), and its fetch transport refuses every
other host (`infrastructure/web_retrieval_live.py:71-74` @ `b2d43f7`). Everything else runs on
recorded doubles: `aia_executors.deep_research_recorded` and `fixtures/deep_research/web.json`,
whose pages are invented `.example` sites. On 2026-10-05 a demonstration report produced locally
from the recorded composition presented that replay as research.

Even with a search provider, the current investigator would research badly, for three reasons
read from the code @ `b2d43f7`:

1. **Queries are fixed before anything is read.** The planner writes every query of a track up
   front (`domain/deep_research/agents.py:90`, at most 12); each round runs the next one
   (`apps/executors/src/aia_executors/deep_research/investigate.py:447-451`). An investigator's
   `gaps` are recorded and never searched (`investigate.py:397`).
2. **No investigator chooses what to read.** Code fetches a query's results within the track's
   allowance; nothing follows a link from a page to the source it cites, which is how a number is
   traced to the statistics office that published it.
3. **Documents are refused.** `ALLOWED_CONTENT_TYPES` is HTML and plain text only
   (`domain/deep_research/web.py:50`). Czech official statistics, regulators' reports and trade
   bodies' studies are mostly PDF or XLSX, so the strongest sources are the ones never captured.

The data owner's instruction (2026-10-05): **the best results; open it up.**

## The architecture: modelled on Anthropic's multi-agent Research system

The owner's instruction (2026-10-05): *research so wide and precise; mimic Claude's own deep
research.* Anthropic has published how its Research feature works
([How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system)).
Its measured findings, and what AIA takes from each:

| Their finding | AIA's design |
|---|---|
| An orchestrator-worker pattern: a **lead researcher** plans with extended thinking, saves the plan to memory, and spawns subagents, each with its own context window; multi-agent beat single-agent by 90.2 % on their internal eval | The planner and the director become one **lead researcher** (chunk 8). Its plan is an artifact of the run (the memory that survives a long run and a retry). Each subagent is a track with its own context. |
| **Effort scaling**: a simple fact gets 1 agent and 3–10 tool calls; a comparison 2–4 subagents with 10–15 calls each; complex research more than 10 subagents with clearly divided responsibilities | The lead classifies each subject's complexity and sizes it by those rules, inside the preset's ceiling. Code enforces the caps, so "50 subagents for a simple query" (their early failure) cannot happen. |
| **Delegation is the hard part**: vague task descriptions made subagents duplicate each other | `SubagentTask`, a closed contract: objective, the output wanted, sources and tools to prefer, explicit boundaries ("not prices: another subagent has them"), budget. Code refuses a wave whose tasks overlap by subject and measure. |
| **Two levels of parallelism**: the lead starts 3–5 subagents at once; each subagent runs 3+ tool calls at once; research time fell by up to 90 % | Waves of 3–5 tracks per subject in parallel (chunk 16 adds the worker fan-out). An investigator turn returns **up to 5 actions** (`search`, `open`, `read`, `chase`), which code checks one by one and sends concurrently. |
| **Start wide, then narrow**: short broad queries first, then focus | Prompt heuristic for every investigator, and the lead's first wave is broad by design. |
| **Interleaved thinking**: subagents think after each tool result to judge quality, find gaps and refine the next query | Investigators reason between turns about what they read. This needs the model's thinking on, which Claude does not allow with a forced tool choice, and AIA's Bedrock adapter forces one for structured output (`model_adapters/bedrock.py:199-209` @ `b2d43f7`) and sends no thinking setting today. Chunk 5a moves structured output off the forced tool. |
| **Condensed returns**: subagents return the important tokens, not everything they read | A track returns its grounded findings, gaps and a short summary to the lead; pages and transcripts stay in artifacts. |
| **Citations by a dedicated agent** | AIA is stricter: code grounds every quote in a captured snapshot; a model never attaches a citation. |
| **What explains quality**: token usage (80 % of variance), number of tool calls and model choice; multi-agent research uses about 15× the tokens of chat | The budget is the quality lever, so presets are budgets; the lead runs on the strongest model the EU route offers (a policy entry, chunk 8), investigators on a strong model, triage on a light one. The cost estimates already assume this multiple. |
| **Their failure modes**: endless searches for sources that do not exist; SEO content farms chosen over authoritative sources; serial execution | The stop rule (saturation, allowance) ends a hopeless track; the source table, result annotations and the source-class score push authoritative hosts; fan-out is parallel. |
| **Evaluation**: start small (about 20 queries) at once; an LLM judge on a rubric of factual accuracy, citation accuracy, completeness, source quality and tool efficiency; plus human review | Chunk 13 starts with 20 fictional questions, judged on that rubric by a separate model (its own policy entry) and graded blind by a researcher; chunk 24 repeats it at scale. |

What AIA keeps that Claude's Research does not have to: code sends every request (classified,
journaled, reserved), every quote is grounded in AIA's own snapshot, and nothing non-public is
touched. Those are the price of research a client pays for and can audit.

## The design: agent-directed, code-gated

Agents get the freedom that makes research good: they decide what to search next, which result
to open, which link to follow, and when they are done. Code keeps the four things that make a
finding defensible to a client, unchanged from ADR 0017:

- **Code sends every call.** A query or a page request leaves only through `RetrievalGate`:
  classified, judged against the route's approved classes, reserved, journaled before it leaves,
  outcome journaled after. The model never holds a network tool.
- **A finding is a quote in a snapshot this track captured.** Grounding, the verifier, the
  leakage screen and the sealed bundle are unchanged.
- **Every action is recorded.** Each move, its stated reason and what code did with it is an
  artifact of the track, readable by a researcher.
- **Spend is bounded before it is spent.** Per-track allowances, a stop rule and the run's cost
  ceiling against the study's spend limit (ADR 0019 gate 2).

Rejected: giving the model a provider's own search tool (Claude's server-side web search, or
any browsing agent). It researches well, but queries leave without AIA's classification or
ledger, the tool is not offered on the Bedrock route AIA is approved for, and the answer it
returns is not grounded in AIA's own snapshots. Agent-directed, code-gated keeps most of the
quality gain without those losses.

### The investigator loop

One web track is a loop of **turns**. A turn is one governed model request (RESEARCH_REASONING,
Bedrock EU, structured output as today: one closed contract, checkpointed, a retry replays and
never pays twice). The turn's input:

- the track's sub-question and the run's Class C research digest;
- what the track has: every search so far (query, hits as `R<n>` refs with title and snippet),
  every captured source (`S<n>`: title, host, date, source class), the links found in captured
  sources (`L<n>`: anchor text and host, never a raw URL the model can edit);
- the newest captured text, marked untrusted, with `detect_instructions` flags;
- the grounded findings so far, the stop rule's state and the remaining allowance;
- the refusals since the last turn, each with its reason.

The turn's output, `InvestigatorTurn` (a closed contract, replacing `ExtractionProposal` for web
tracks):

```text
evidence: [ProposedEvidence]          # as today; grounded by code against S<n> snapshots
summary: str                          # what this turn learned, for the lead (condensed return)
next: up to 5 of, sent concurrently
  search  {query, purpose}            # a new query in Czech or English
  open    {ref: R<n> | L<n>, purpose} # a result or a link from a captured source
  read    {ref: S<n>, part}           # another part of a long captured document
  chase   {name, what, from: S<n>}    # a source a page cites by name, resolved by code
  finish  {gaps: [{need, why, tried}]} # the track is answered, or cannot be
```

What code does with each:

| Action | Code |
|---|---|
| `search` | classify the query (Class A refused, B refused without a B route, C allowed); duplicate of an earlier query refused; reserve, journal, send through the provider; store the hits as new `R<n>` |
| `open` | resolve the ref to the URL code stored (the model never writes a URL); classify the URL's path and query string like a query; check the address on every hop; obey `robots.txt`; fetch, snapshot, extract text and links (`L<n>`) |
| `read` | serve the requested part of a snapshot the track already holds; nothing leaves |
| `chase` | resolve the name in the source table to a site-restricted search, else a plain search for name and topic; then as `search` |
| `finish` | end the track; the gaps go to the synthesizer as stated gaps, never as findings |
| `evidence` | ground each item against the track's snapshots (quote present, numbers in the quote, source in this track); accepted or quarantined with the reason |

A refused action costs a turn and is reported back with its reason, so the agent can rephrase.
The same refusal reason three times ends the track (`STOP_REFUSALS`), so a page that tries to
steer the agent into sending client terms buys nothing.

**Why refs, not URLs.** A model that writes URLs can be steered by a page into putting data in a
URL to a host the page chose. With refs, the model can only open what a search returned or what a
captured page links to, and every URL is still classified before it leaves. Opening an injected
link sends no client data: the URL was written by the page, and classification refuses one that
carries a client term.

**The planner** stays: it writes the track's sub-questions and its first two or three queries,
and turns the brief into the Class C digest. Agents widen from there.

**Stop rule**, checked before every turn: the evidence target met (`DepthPreset.evidence_target`);
saturation (no newly grounded evidence for `saturation_window` turns); the allowance spent
(searches, opens, turns, reservation); `finish`; an uncertain delivery (journal closed, never
resent); `STOP_REFUSALS`.

### The four gains, pushed as far as they go

The loop above is the minimum. Each gain below is taken to its strongest form that still keeps
code sending every call. Together they are what separates a researcher from a search box.

**1. Following leads.**

- **Links** from every captured page, as `L<n>` refs (above).
- **Citation chase.** Pages cite sources by name more often than by link ("podle ČSÚ", "data
  Eurostatu", "studie Svazu obchodu"). The investigator may answer `chase {name, what, from: S<n>}`.
  Code looks the name up in the source table: a known publisher becomes a search restricted to its
  own site (ČSÚ → `site:czso.cz`); an unknown one becomes an ordinary search for the name and the
  topic, classified like any query. The model never chooses the host.
- **Long documents read in parts.** A 200-page report is captured once; the investigator sees its
  outline and asks `read {ref: S<n>, part}` for the section it needs, so the table on page 143 is
  reachable without reading pages 1–142.
- **Tables.** XLSX and CSV are captured, and a number is grounded to its sheet and cell, the
  strongest citation a number can have.
- **One fetch per run.** Snapshots are content-addressed and cached for the run: a page one track
  captured costs another track nothing to open, and is still grounded per track.

**2. Filling gaps.**

- **Structured gaps.** `finish` and every turn may record `{need, why, tried}`, not free text.
- **The lead researcher** (chunk 8; it also plans the run, between waves of tracks).
  It reads every track's findings, gaps and **conflicts** (two accepted sources disagreeing on the
  same measure) and proposes, within the run's budget:
  - a new track for an unanswered gap or a sub-question the plan missed;
  - a *resolve* track for a conflict: find the primary source both numbers came from;
  - more allowance for a track that is still finding evidence, and an early stop for one that is
    not (budget moved, never added beyond the run's ceiling);
  - routing a finding from one track to another track's gap instead of searching for it again.
  Code checks every proposal: a new track's sub-question is classified like a query and inherits
  the Class C digest only; at most 2 lead rounds (Standard) or 3 (Deep).

**3. Better result choice.**

- **Annotated results.** Each hit shows its host, source class and score from the source table,
  date, file type, and whether the run already holds it or a near-duplicate (syndicated copies
  collapse to one). 20 results per search instead of 10.
- **More than one way to search.** Web search (Brave); site-restricted search on official hosts;
  Wikipedia as an entry point (low source class); and, once verified, the Czech national open-data
  catalogue and the statistics office's own data search (chunk 9). The agent picks the tool;
  code sends it.
- **Choice is visible.** Opening a low-class page when a higher-class hit for the same claim was on
  the list is allowed, recorded, and counted by the evaluation.

**4. Recovering from bad queries.**

- **Explicit search feedback.** Code tells the agent why a search was weak: no hits, every hit
  already held, every hit low-class, every hit outside the date range.
- **Operators.** Site, freshness or date range, and language (Czech or English: Eurostat and
  international bodies publish in English); file type if the provider supports it (verified in
  chunk 2).
- **A weak search is not a wasted round.** It spends search allowance, never the saturation window.
- **Duplicates refused**, so rephrasing is real rephrasing.

**What this costs, honestly.** Each addition widens what an injected page can try: a chase is
steered only by a name, resolved by code against the source table; a lead's proposal is
classified like a query; every action still passes the gate and the refusal limit. The path a
track takes is no longer reproducible, but its evidence is: every snapshot is content-addressed
and the transcript records every step. And it costs more (below).

### Documents as sources

Snapshots accept `application/pdf` and the XLSX type, bounded by size, page count and ZIP limits,
with text extracted by the readers AIA already uses for brief attachments
(`infrastructure/document_text.py`). A PDF source's locator is its page; an XLSX source's is
sheet and cell range. Grounding works on the extracted text exactly as it does for HTML. This is
the change most likely to move a run from news articles to primary sources.

### Reuse, audit and cost

- **Reuse** is by the track's inputs (sub-question, digest, preset, prompt and contract versions,
  provider and source table), never by the queries the agent happened to write. A second pass
  over an unchanged track reuses it whole and pays nothing; a changed track runs again.
- **The transcript** (every turn's action, purpose, code's decision and cost) is a track
  artifact, shown on the Deep Research screen beside the findings it led to.
- **Presets** (proposal; chunk 13 measures and the owner sets them). **Estimates, to be
  measured:** a turn reads up to about 8,000 tokens of page text, about $0.04 at the develop
  policy's prices.

  | Preset | Per track | Lead researcher | Estimate per run |
  |---|---|---|---|
  | Standard | 8 searches, 20 opens, 15 turns | 2 rounds, up to 2 new tracks | about $5–7 |
  | Deep | 15 searches, 40 opens, 30 turns | 3 rounds, up to 4 new tracks | about $12–18 |

  Both are above the $2 cap of the first acceptance: chunk 1 asks the owner for run budgets.
- **The run's cost ceiling** (`domain/run_cost.py`) counts the agent-directed turns and the search
  price, so a study's spend limit asks before a run that could exceed it.

## Search provider (DR-2, Class C)

### What the provider has to satisfy

From ADR 0008, ADR 0017 and deep-research.md §12, in order of weight:

1. **Returns pointers, not answers.** A finding is a quote in a page AIA itself captured. The
   provider gives `url, title, snippet, rank` (`domain/deep_research/web.py:78-84`); AIA fetches
   and snapshots the page. An answer engine (a synthesised response with citations) is model
   recollection with links and breaks the grounding contract.
2. **Czech.** The studies are Czech-market. The index must take a Czech query and return
   Czech-market results.
3. **Terms that allow AIA's use.** Hits are passed to a model and recorded in the run's journal
   and artifacts; the terms must allow storing them and using them in an AI application.
4. **Residency per data class.** Class C may use a route outside the EU (the Wikipedia route is
   `ResidencyZone.UNKNOWN`, approved for Class C). Class B needs EU processing, training exclusion
   and stated retention (ADR 0008); no candidate is approved for it here.
5. **Metered per call, at a stated price.** `ToolRoute.price_usd_per_call` is reserved before a
   call leaves (`domain/deep_research/tooling.py:88-110`).
6. **A plain HTTP API** behind one adapter, no SDK (`make layer_check`), no provider-side browsing.

### Candidates (checked 2026-10-05; prices and terms are the providers' own, to be confirmed in writing)

| Provider | Pointers | Czech | Processing / retention | Storage terms | Price | Verdict |
|---|---|---|---|---|---|---|
| **Brave Search API** | Yes: ranked web results | Yes: `country=CZ`, `search_lang=cs` | US; query logs kept up to 90 days; zero retention on Enterprise only | Standard terms forbid storing results; needs a plan that grants storage/AI rights | $5 / 1,000 requests; also sold through AWS Marketplace | **Chosen for Class C** |
| Linkup (Paris) | Yes, plus an answer mode AIA would not use | Not established | EU-hosted; queries may be processed in US/EU/CA/APAC by default; guaranteed EU processing and zero retention by agreement; DPA available | To confirm | To confirm | **Candidate for Class B later**, under a signed EU-processing agreement |
| Staan (Qwant + Ecosia) | Yes | **No**: French, English, German only | EU | To confirm | €2 / 1,000 | Rejected: no Czech |
| Exa, Tavily, Parallel | Yes | Not established | None confirms EU residency; zero retention on enterprise or on request | Varies | Varies | Rejected for now: no advantage over Brave for Class C, no EU route for Class B |
| Perplexity Sonar, provider-native web search | Answers | Yes | Not EU | n/a | n/a | Rejected: answer engines (criterion 1); ADR 0017 already rejects provider-native search |
| Google Custom Search JSON API | Yes | Yes | US | Restrictive | n/a | Rejected: closed to new customers, discontinued 2027-01-01 |
| Bing Web Search API | n/a | n/a | n/a | n/a | n/a | Rejected: retired August 2025 |

**Recommendation: Brave Search API, for Class C queries, on develop, for fictional studies.**
It is an independent index, takes Czech country and language parameters, returns the pointers
AIA's design is built around, and costs about $0.005 a search. Pass 1 of the recorded journey
makes 6 searches (deep-research.md §11), so a run's search spend is cents beside its model calls.

What Brave costs us, stated plainly: queries go to a US company and are logged for up to 90 days
unless AIA buys Enterprise. That is acceptable only for Class C (public market terms, no client
identity), which code already enforces per query (`domain/deep_research/classification.py`).
It never becomes acceptable for Class B.

### Sources for the comparison

Brave: [Search API](https://brave.com/search/api/), [pricing and retention summary](https://costbench.com/software/ai-search-apis/brave-search-api/),
[storage-rights terms](https://github.com/modelcontextprotocol/servers/issues/522),
[country and language codes](https://brave-search-python-client.readthedocs.io/en/latest/lib_reference.html),
[AWS Marketplace listing](https://aws.amazon.com/marketplace/pp/prodview-qjlabherxghtq).
Linkup: [security FAQ](https://docs.linkup.so/pages/security-and-privacy/faq),
[EU search APIs](https://www.linkup.so/blog/web-search-apis-in-europe).
Staan: [FAQ](https://staan.ai/faq), [launch](https://www.heise.de/en/news/Ecosia-and-Qwant-launch-web-search-via-European-index-10513567.html).
Exa/Tavily/Parallel: [comparison](https://www.linkup.so/blog/best-web-search-api-in-2026-top-providers-compared)
(a competitor's page; each provider's own terms decide).
Google: [Custom Search shutdown](https://heise.de/-11152411).
Part B: Common Crawl [URL index](https://blog.commoncrawl.org/blog/the-columnar-index-is-now-the-url-index),
ČSÚ [DataStat](https://csu.gov.cz/produkty/datastat-postupne-nahrazuje-verejnou-databazi),
Bedrock [Claude Haiku 4.5 model card](https://docs.aws.eu/bedrock/latest/userguide/model-card-anthropic-claude-haiku-4-5.html),
NKOD [DCAT-AP and SPARQL](https://data.gov.cz/p%C5%99%C3%ADlohy/2018-12-19/LOD%20in%20Czech%20Open%20Data%20Portal.pdf).
These are hypotheses about terms until chunk 1 (and, for Part B, each connector's chunk) records
the signed terms and their date.

## Part B: at web scale

The owner's instruction (2026-10-05): *a methodology that gets a very large number of agents and
crawls the entire internet, including the accessible deep web, for the relevant data.* Part A
(chunks 1–14) is the foundation and is built first; Part B scales it.

### The principle: crawl wide with code, read narrow with models

Nobody crawls the entire internet per study, and pointing thousands of model agents at raw pages
is the most expensive and least accurate way to try. The internet has already been crawled:
search providers' indexes and Common Crawl's open archive (billions of pages, monthly, free).
AIA **queries** those, **crawls** only the hosts that matter, **connects** to the public databases
search engines cannot see, and spends model calls only where judgement is needed. A run is a
funnel:

| Stage | Who | Scale per Exhaustive run (proposal) | What it does |
|---|---|---|---|
| 1. Discover | code | ~500 searches; Common Crawl index queries; focused crawl of up to ~5,000 pages on authoritative hosts; deep-web connectors | every candidate source the plan's subjects could have |
| 2. Filter | code | tens of thousands of candidates → ~2,000 | exact and near-duplicate collapse, language, source class, relevance ranking over extracted text |
| 3. Triage | light model, in parallel | ~2,000 pages | relevant or not, which sub-question, candidate quotes; cheap |
| 4. Investigate | strong model, ~20–50 agents in parallel | the triaged sources | the agent-directed loop of Part A: leads, gaps, chase, documents |
| 5. Verify | strong model, independent | every accepted finding | adversarial verifiers try to break each claim; triangulation across independent publishers |
| 6. Synthesize | strong model | the run | the brief, conflicts, gaps |

Every stage keeps Part A's rules: code sends every request, every quote is grounded in a
snapshot, every call is journaled and paid for from a reservation.

### Discover: four ways in

1. **Search providers**, many queries in parallel (Brave; a second index later if the
   evaluation shows Brave misses Czech sources).
2. **Common Crawl.** Its URL index (Parquet on S3, queryable with Athena) lists every page it
   captured by host and path; the archived page itself can be read from its WARC file without
   touching the origin site. Queried from AIA's own AWS account; the data sits in `us-east-1`, so
   only Class C (public topic terms, host names) goes into a query. This is the closest thing to
   "the entire internet" that is practical: finding every page on every Czech trade body's site
   that mentions a product category, including pages no search ranks.
3. **Focused crawler.** For hosts the source table rates authoritative (statistics, regulators,
   ministries, trade bodies, the companies a brief names), a bounded crawl: sitemap first, then
   breadth-first inside the host, `robots.txt` obeyed, rate-limited per host, page and depth caps.
4. **Deep-web connectors.** The *accessible* deep web is public data behind query interfaces,
   not behind logins. One adapter per source, each built only after its interface, terms and rate
   limits are recorded. Candidates, in order of value for Czech market research:
   - ČSÚ **DataStat** (the statistics office's API: 700+ datasets, CSV and JSON; replacing the
     Public Database from 2026);
   - the national open-data catalogue **NKOD** (data.gov.cz, DCAT-AP, SPARQL endpoint);
   - **Eurostat**'s data API, for EU comparisons;
   - **OpenAlex** or Crossref, for studies and their metadata;
   - the **Wayback Machine** CDX index, for how a page or a price looked before;
   - **ARES** (business register), legal-entity fields only;
   - public procurement (**NEN** / Věstník), for what public bodies buy.

### Read narrow: triage on a light model

Stage 3 is where scale is bought cheaply. A triage reader gets one page's extracted text and
returns a closed contract: relevant or not, to which sub-question, up to three candidate quotes.
It cannot search, open or send anything. Proposed model: Claude Haiku 4.5 on Bedrock through its
EU cross-region profile (`eu.anthropic.claude-haiku-4-5-20251001-v1:0`), bound to a new capability
(`RESEARCH_TRIAGE`) by a second policy entry under ADR 0010. Investigators, verifiers, the
lead researcher and the synthesizer stay on the strong model.

### Many agents, coordinated

- **Hierarchy.** The lead researcher (Part A) gains **subject leads**: one per subject of the
  plan (market size, prices, competitors, consumers, regulation, …). A lead owns its subject's
  tracks, reads their findings and gaps, and reports to the lead researcher; the lead moves budget
  between subjects. Investigators run in parallel under the leads.
- **Adversarial verifiers.** For every finding the run would publish, an independent verifier is
  told to disprove it: look for the primary source, a newer figure, a different denominator. A
  finding survives only if the attempt fails.
- **Triangulation.** A number confirmed by two independent publishers (not two pages copying one
  press release; independence is by publisher, after near-duplicate collapse) earns the
  confirmation bonus; a number with one source says so.
- **Fan-out limits.** The worker's concurrency, Bedrock's tokens-per-minute quota (a quota
  increase is an operator request) and per-host politeness bound how many agents run at once;
  the run's reservation bounds how many run in total.

### Boundaries (non-negotiable)

The data owner's research has to be defensible to the client who pays for it, and lawful:

- **Public only.** No login, no paywall, no CAPTCHA, nothing a site's terms forbid automated
  access to; `robots.txt` obeyed; nothing circumvented. "Deep web" means public databases and
  pages search engines do not index, never the dark web or Tor.
- **No personal data harvesting.** Registers and pages contain people's names; extraction keeps
  legal-entity and aggregate facts and drops person-level data before storage (GDPR). A source
  that is mainly about individuals is out of scope.
- **Excerpts, not republication.** Snapshots stay internal; a report quotes short excerpts with
  their source, as citation allows. A per-source terms register records what each connector's
  licence permits (DataStat and NKOD data are open data; others vary).
- **Class C only** in Part B, as in Part A.

### Cost and time, estimated (to be measured in chunk 24)

| Preset | Agents | Pages read by a model | Estimate per run | Run time |
|---|---|---|---|---|
| Standard (Part A) | 8 tracks | ~150 | about $5–7 | minutes |
| Deep (Part A) | 12 tracks + lead researcher | ~400 | about $12–18 | under an hour |
| **Exhaustive (Part B)** | ~20–50 investigators, subject leads, verifiers | ~2,000 triaged, ~500 investigated | **about $60–100** | about 1–3 hours |

The Exhaustive estimate: triage about 12M input tokens on the light model (about $12–15), 50
investigators × 20 turns (about $40), verification and synthesis (about $5–10), 500 searches
(about $2.50), Athena queries over a few columns (cents to dollars). Snapshots are about 1 GB a
run in S3; chunk 23 sets their retention.

## Chunks

Each chunk is one PR into `develop`, green on `make verify`, with this file ticked. Chunks 2–12
build and test entirely offline on recorded doubles (chunk 9 starts with a written check of
terms); only chunks 13 and 14 send anything.

### 1. Sign-off (human; no code)

- The data owner approves this design and the ADR 0017 amendment text (Doc follow-up).
- DR-2 (Class C) recorded as Brave, with the date. The account is bought on a plan whose terms
  allow storing results and using them in an AI application; record the plan, its terms URL and
  date, the price per request, whether a failed request is billed, and the retention that applies.
- D8 decided for this key (chunk 3's proposal, or Secrets Manager).
- Run budgets for chunks 13 and 14 (estimates: about $5–7 Standard, $12–18 Deep).

### 2. Brave search adapter

`infrastructure/web_retrieval_brave.py`: `BraveSearch(SearchAdapter)`, `RetrievalMode.LIVE`,
adapter id `brave-web-search-1`. One `GET` with `q`, `country=CZ`, `search_lang` (cs or en),
`count` ≤ 20, freshness when asked, safe search on; `site:` in the query; whether `filetype:`
works is verified here, and the action refused if not. Hits map to `SearchHit(url, title,
snippet, rank)`; a hit whose URL fails `check_url` is dropped and counted. Failures map to
`ToolCallFailed` with a `Delivery`: rejected before processing (bad key, quota) is `RESPONDED`,
a timeout or reset after sending is `UNKNOWN` (closed uncertain, never resent). No retry inside
the adapter. The transport is the pinned HTTPS client scoped to the provider's API host. Tests: a
captured response shape with fictional content, every failure mode, the key never in a log line
or exception. No network.

### 3. The key as a credential reference (D8 proposal for this route)

The adapter holds a reference (`CredentialSource`, `model_adapters/transport.py:245-270`), never
the key. Proposal: SSM `SecureString` `/aia/develop/aia_deep_research_brave_api_key`, decrypted
into the host's `.env` by `deploy/develop/bin/write-env.sh` as every develop secret is today, and
passed to the worker service only. A missing key with the route on stops the worker at start,
naming the key. Trade-off: no rotation, unlike Secrets Manager. Production needs its own answer.

### 4. Public-web fetch

`PublicHttpsTransport`, generalised from the Wikipedia transport: any public host passing
`check_url` and `check_resolution`, every hop re-checked; private, link-local and metadata
addresses refused; `robots.txt` read once per host per run and obeyed; an identifying user agent;
no cookies or credentials; the existing size, time and redirect caps; one request at a time per
host. Snapshots keep the page's outbound links (absolute, `check_url`-valid, deduplicated, at most
200) for the `L<n>` refs. A run-level, content-addressed snapshot cache: a URL fetched once in a
run is not fetched again. The Wikipedia route keeps its narrower transport.

### 5. Documents as sources

`ALLOWED_CONTENT_TYPES` gains `application/pdf`, the XLSX type and `text/csv`, each with its own
size, page and ZIP bounds; text through `document_text.py`; an outline per document; parts
readable by section or page range; locators by page, or by sheet and cell; grounding and the
instruction screen on the extracted text. Tests: fictional PDF, XLSX and CSV fixtures, oversized
and malformed files refused, a quote found on the right page, a number grounded to its cell.

### 5a. Thinking between results

Claude does not allow a forced tool choice with thinking on, and the Bedrock adapter gets
structured output from a forced tool. Move the Deep Research agents' contracts to a form that
keeps strict, schema-valid output with thinking on (tool choice `auto` with a strict schema and
the instruction to answer through it, or the model's structured-output form where the route
supports it), add the thinking setting to the adapter, and keep every other agent on its current
form until each is migrated and tested. Thinking tokens are metered and reserved like any output.
Recorded tests: a thinking turn's output validated exactly as before; a reply outside the schema
is one counted repair, as today.

### 6. The agent-directed investigator

The `InvestigatorTurn` contract and prompt (versioned; the old contract stays readable for
stored runs) with `search`, `open`, `read` and `finish`, up to 5 actions per turn sent
concurrently through the gate, and a condensed summary for the lead; the "start wide, then
narrow" heuristic; the loop in `investigate.py`; ref
resolution; URL classification; refusal feedback and `STOP_REFUSALS`; the transcript artifact.
Recorded tests, with fictional pages: a lead followed from a news page to the PDF it links; a
gap searched; a page instructing the agent to search a client's name, refused three times and
ended; a link to a private address refused; an uncertain search never resent; a retry replaying
answered turns without paying twice; a reused track costing nothing.

### 7. Leads and recovery

`chase` resolved through the source table; result annotations (source class, date, type, held,
near-duplicate); search feedback (no hits, all held, all low-class, out of range); operators and
language; a weak search kept out of the saturation window. Recorded tests: "podle ČSÚ" becomes a
`site:czso.cz` search; an unknown publisher becomes a classified plain search; a syndicated copy
collapses to the one already held; an all-held result list is said so and the next query differs.

### 8. The lead researcher

One agent role replaces the planner and the director: plans with thinking, writes the plan to a
run artifact, classifies each subject's complexity and sizes it by the effort-scaling rules,
delegates waves of 3–5 tracks per subject through `SubagentTask` (objective, output wanted,
sources to prefer, boundaries, budget), reads their condensed returns, and re-plans: new tracks
for gaps, resolve tracks for conflicts (found by code: same subject, measure and period, different
values), budget moved from starved tracks to productive ones, findings routed to another track's
gap. Code checks every task (classified, no overlap with another task's subject and measure,
within the ceiling and the round limit). The lead runs on the strongest model the EU route
offers, bound by its own policy entry. Recorded tests: a simple subject gets one track and a
complex one many; overlapping tasks refused; a gap becomes a track that answers it; a conflict
becomes a resolve track that finds the primary source; budget moved, the run's total unchanged.

### 9. Official-data retrieval (verify first)

Candidates: the Czech national open-data catalogue (data.gov.cz) and the statistics office's own
data search. First establish, in writing, each one's interface, terms, rate limits and whether it
needs a key; only then build an adapter behind `SearchAdapter` with its own route. If neither has
a usable public interface, this chunk closes with that finding and site-restricted web search
remains the way in.

### 10. Budgets, presets and the run's cost ceiling

The Standard and Deep presets in `DepthPreset` (searches, opens, turns per track; lead rounds
and new tracks per run); the turn and lead reservations; the search price in
`run_cost_ceiling`; tests that a study's spend limit asks before a run that could pass it, and
that moving budget between tracks never raises the run's ceiling.

### 11. Composition, switches and prices

- `AIA_DEEP_RESEARCH_WEB_SEARCH`: `off` (default) or `brave`; needs `AIA_DEEP_RESEARCH_ENABLED`,
  the key, `AIA_DEEP_RESEARCH_SEARCH_USD_PER_CALL` and `AIA_DEEP_RESEARCH_SEARCH_PRICE_DATE`.
- `AIA_DEEP_RESEARCH_AGENT_DIRECTED`: `off` (planned queries, as today) or `on`.
- `AIA_DEEP_RESEARCH_LEAD`: `off` or `on` (needs agent-directed).
- Route: `ProviderRoute(route_id="brave-web-search", zone=US, eu_processing_approved=False,
  approved_for={CLASS_C_INTERNAL})`.
- Anything missing or invalid stops the worker at start, naming the key. Settings shows each as
  configured or off, never "connected" (`lib/ai-runtime.ts`).

### 12. Czech source table (DR-5 input)

Unknown hosts score lowest (`domain/deep_research/sources.py`). A versioned extension of
`SOURCE_TABLE_V1` for the hosts a Czech market study meets (official statistics, regulators,
ministries, Eurostat, major Czech news, trade bodies), with the publisher names the citation
chase resolves; approved by the data owner; off until approved.

### 13. Quality evaluation on real search

On develop, a fixed set of 20 fictional-client research questions (simple facts, comparisons and
complex questions, as in effort scaling), each run three ways: planned
queries (today), agent-directed, agent-directed with the lead researcher. Record per run: accepted
findings, the share from primary sources (official, regulator, the publisher of the number),
numbers grounded to a table cell, conflicts found and resolved, quarantined by reason, searches,
opens, turns, money per accepted finding; a rubric score from a separate judge model (factual
accuracy, citation accuracy, completeness, source quality, tool efficiency); and a researcher's
blind grade of the three briefs. The
owner sets presets and defaults from these numbers; each step up becomes a default only if it
wins.

### 14. Develop activation and one live fictional acceptance

Parameters set, deployed, the worker's start-up log read, one Deep Research pass for a fictional
client within the owner's budget. Record the run id, every count and the spend (model and search
separately). Then tick the parent plan's chunk 13 for Class C.

**Part B (after Part A is built and evaluated):**

### 15. Scale sign-off (human; no code)

The funnel, the boundaries above, the Exhaustive budget, the light model's policy entry, a
Bedrock quota request, and an S3 retention period for snapshots.

### 16. Fan-out

Investigator tracks executed concurrently across worker processes; a per-host politeness
scheduler shared by every fetcher in a run; a model concurrency limiter below the account's quota;
tests that a run with 50 tracks never exceeds either limit and recovers every interrupted track.

### 17. Focused crawler

`SiteCrawl` over `PublicHttpsTransport`: sitemap, then breadth-first inside one host; page,
depth and time caps; `robots.txt`, crawl-delay and rate limit; every page a snapshot in the run
cache; recorded tests over a fictional site including a crawler trap and an off-host redirect.

### 18. Common Crawl

An adapter that queries the URL index with Athena from AIA's AWS account (IAM scoped to the
public bucket and a results bucket; cost metered per query from bytes scanned) and reads archived
pages from WARC by byte range; query text classified like a search; recorded tests.

### 19. Deep-web connectors

One sub-chunk per source, in the order listed above, each starting with its recorded terms,
interface and rate limits; DataStat and NKOD first. Results enter the run as snapshots with their
dataset identifier and query as locator, so a number is grounded to the dataset cell it came from.

### 20. Code filters

Exact and near-duplicate collapse (content hash, then shingled similarity), language detection,
source class, and relevance ranking over extracted text against each sub-question; measured
recall against a hand-labelled fictional corpus.

### 21. Triage readers

The `RESEARCH_TRIAGE` capability, its ADR 0010 policy entry and prices, the triage contract and
prompt; parallel execution under the concurrency limiter; tests that a triage reader can send
nothing and that its candidate quotes are grounded before an investigator sees them.

### 22. Leads, adversarial verifiers, triangulation

Subject leads between the lead researcher and the tracks; the adversarial verification step; publisher
independence after near-duplicate collapse; recorded tests for a syndicated press release (one
publisher, not two) and a claim disproved by a newer primary figure.

### 23. The Exhaustive preset

The preset, its reservation and cost ceiling; progress for runs of hours (stage, counts, spend
so far) on the Deep Research screen; cancel at any point without losing what was captured; the
snapshot retention job.

### 24. Evaluation at scale

The chunk 13 question set, run at Deep and at Exhaustive. Exhaustive becomes available to
researchers only if it finds materially more primary-source evidence per question, and the owner
judges the difference worth the cost.

## Dependencies

- **Tool spend in the ledger** (deep-research.md chunk 4) before chunk 13 spends money.
- **The AI runtime and research agents on develop** (ai-research-activation.md chunk 4).
- **The model route keeps structured output by a forced tool** (`model_adapters/bedrock.py:199-209`
  @ `b2d43f7`). The pinned develop profile accepts it; newer Claude models refuse a forced tool
  choice, so a model change must move this contract to their structured-output form first.

## What this plan does not do

- **Class B.** Queries carrying a client's identity or confidential terms would research better,
  and the owner's DR-2 intent asks for them, but they need an EU-processing search route. Linkup
  under a signed EU-processing, zero-retention agreement is the candidate; a separate decision
  with D6 (the model route) and DR-2b (the design digest).
- **A provider's own search or browsing agent.** Rejected above.
- **Production.** Develop only, fictional studies only, as ADR 0010 accepts.
- **Freshness** (deep-research.md §12 item 6): a reused track is reused by fingerprint as today.
- **Anything non-public**: logins, paywalls, CAPTCHAs, the dark web, personal-data collection.

## Findings

- `CLAUDE.md` § 2 says of `infrastructure/web_retrieval.py` "no live adapter exists (DR-2)", and
  of `deep_research_runtime.py` "no web retrieval exists"; `web_retrieval_live.py` and the
  Wikipedia switch exist @ `b2d43f7`. Stale map entry; see Doc follow-up.

## Doc follow-up

For the docs PR after chunk 0 merges:

- `.planning/overview.md` decision table, DR-2 row: "Proposed for Class C: Brave Search API, with
  agent-directed, code-gated investigators; see `.planning/plans/deep-research-web-search.md`.
  Class B open (candidate: Linkup under an EU agreement)."
- ADR 0017 amendment (after the owner's sign-off): "Web investigators choose their next search,
  the result to open, the link or named source to follow and the document part to read, by ref;
  a lead researcher plans the run, sizes it by effort-scaling rules, delegates waves of parallel
  tracks through a closed task contract, adds tracks for gaps and conflicts and moves budget between tracks within the
  run's ceiling; code classifies, sends and journals every call, and grounds every finding in the
  track's own snapshots. Sources include PDF, XLSX and CSV."
- `CLAUDE.md` § 2: `web_retrieval.py` and `deep_research_runtime.py` entries corrected to name the
  live Wikipedia route (`web_retrieval_live.py`, `deep_research_live.py`) and, after chunk 11, the
  Brave route and its switches.
- `docs/architecture/deep-research.md` § 12 item 1: point to this plan.
