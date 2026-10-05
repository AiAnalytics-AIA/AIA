---
status: planned
chunks:
  - "[x] 0. This plan: the design and the provider choice (DR-2, Class C)"
  - "[ ] 1. Sign-off: the design, Brave and its written terms, D8, the run budget"
  - "[ ] 2. Brave search adapter over the existing SearchAdapter seam"
  - "[ ] 3. The API key as a credential reference (D8, for this route)"
  - "[ ] 4. Public-web fetch: any public host, robots.txt, identified user agent, links kept"
  - "[ ] 5. Documents as sources: PDF and XLSX snapshots, grounded by page and sheet"
  - "[ ] 6. The agent-directed investigator: action contract, loop, refs, refusals, transcript"
  - "[ ] 7. Budgets and the run's cost ceiling for agent-directed tracks"
  - "[ ] 8. Composition, switches and dated price"
  - "[ ] 9. Czech source table (DR-5 input)"
  - "[ ] 10. Quality evaluation: planned queries against agent-directed, on real search"
  - "[ ] 11. Develop activation and one live fictional acceptance"
---
# Deep Research on the open web — agent-directed, code-gated

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
next: one of
  search  {query, purpose}            # a new query in Czech or English
  open    {ref: R<n> | L<n>, purpose} # a result or a link from a captured source
  finish  {gaps: [...]}               # the track is answered, or cannot be
```

What code does with each:

| Action | Code |
|---|---|
| `search` | classify the query (Class A refused, B refused without a B route, C allowed); duplicate of an earlier query refused; reserve, journal, send through the provider; store the hits as new `R<n>` |
| `open` | resolve the ref to the URL code stored (the model never writes a URL); classify the URL's path and query string like a query; check the address on every hop; obey `robots.txt`; fetch, snapshot, extract text and links (`L<n>`) |
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
- **Allowances per track** (proposal; chunk 10 measures and the owner sets them): Standard
  preset 6 searches, 15 opens, 12 turns. **Estimate, to be measured:** a turn reads up to about
  8,000 tokens of page text, so about $0.04 at the develop policy's prices; 12 turns, about $0.50
  a track; 8 tracks, about $4 a run, plus under $0.25 of searches. That is above the $2 cap of the
  first acceptance: chunk 1 asks the owner for a run budget.
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
These are hypotheses about terms until chunk 1 records the signed plan and its date.

## Chunks

Each chunk is one PR into `develop`, green on `make verify`, with this file ticked. Chunks 2–9
build and test entirely offline on recorded doubles; only chunks 10 and 11 send anything.

### 1. Sign-off (human; no code)

- The data owner approves this design and the ADR 0017 amendment text (Doc follow-up).
- DR-2 (Class C) recorded as Brave, with the date. The account is bought on a plan whose terms
  allow storing results and using them in an AI application; record the plan, its terms URL and
  date, the price per request, whether a failed request is billed, and the retention that applies.
- D8 decided for this key (chunk 3's proposal, or Secrets Manager).
- A run budget for chunks 10 and 11 (the estimate above is about $4 a run).

### 2. Brave search adapter

`infrastructure/web_retrieval_brave.py`: `BraveSearch(SearchAdapter)`, `RetrievalMode.LIVE`,
adapter id `brave-web-search-1`. One `GET` with `q`, `country=CZ`, `search_lang=cs`, `count` ≤ the
gate's `max_results`, safe search on. Hits map to `SearchHit(url, title, snippet, rank)`; a hit
whose URL fails `check_url` is dropped and counted. Failures map to `ToolCallFailed` with a
`Delivery`: rejected before processing (bad key, quota) is `RESPONDED`, a timeout or reset after
sending is `UNKNOWN` (closed uncertain, never resent). No retry inside the adapter. The transport
is the pinned HTTPS client scoped to the provider's API host. Tests: a captured response shape
with fictional content, every failure mode, the key never in a log line or exception. No network.

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
100) for the `L<n>` refs. The Wikipedia route keeps its narrower transport.

### 5. Documents as sources

`ALLOWED_CONTENT_TYPES` gains `application/pdf` and the XLSX type, each with its own size, page
and ZIP bounds; text through `document_text.py`; locators by page or sheet and range; grounding
and the instruction screen run on the extracted text. Tests: fictional PDF and XLSX fixtures,
oversized and malformed files refused, a quote found on the right page.

### 6. The agent-directed investigator

The `InvestigatorTurn` contract and prompt (versioned; the old contract stays readable for
stored runs); the loop in `investigate.py`; ref resolution; URL classification; refusal feedback
and `STOP_REFUSALS`; the transcript artifact. Recorded tests, with fictional pages: a lead
followed from a news page to the PDF it cites; a gap searched; a page instructing the agent to
search a client's name, refused three times and ended; a link to a private address refused; an
uncertain search never resent; a retry replaying answered turns without paying twice; a reused
track costing nothing.

### 7. Budgets and the run's cost ceiling

Per-track allowances in `DepthPreset` (searches, opens, turns); the turn reservation; the search
price in `run_cost_ceiling`; tests that a study's spend limit asks before a run that could pass it.

### 8. Composition, switches and price

- `AIA_DEEP_RESEARCH_WEB_SEARCH`: `off` (default) or `brave`; needs `AIA_DEEP_RESEARCH_ENABLED`,
  the key, `AIA_DEEP_RESEARCH_SEARCH_USD_PER_CALL` and `AIA_DEEP_RESEARCH_SEARCH_PRICE_DATE`.
- `AIA_DEEP_RESEARCH_AGENT_DIRECTED`: `off` (planned queries, as today) or `on`.
- Route: `ProviderRoute(route_id="brave-web-search", zone=US, eu_processing_approved=False,
  approved_for={CLASS_C_INTERNAL})`.
- Anything missing or invalid stops the worker at start, naming the key. Settings shows each as
  configured or off, never "connected" (`lib/ai-runtime.ts`).

### 9. Czech source table (DR-5 input)

Unknown hosts score lowest (`domain/deep_research/sources.py`). A versioned extension of
`SOURCE_TABLE_V1` for the hosts a Czech market study meets (official statistics, regulators,
ministries, major Czech news, trade bodies), approved by the data owner; off until approved.

### 10. Quality evaluation on real search

On develop, a fixed set of 5 fictional-client research questions, each run twice: planned
queries, then agent-directed. Record per run: accepted findings, the share from primary sources
(official, regulator, the publisher of the number), quarantined by reason, searches, opens,
turns, money per accepted finding, and a researcher's blind grade of the two briefs. The owner
sets the allowances from these numbers. Agent-directed becomes the default only if it wins.

### 11. Develop activation and one live fictional acceptance

Parameters set, deployed, the worker's start-up log read, one Deep Research pass for a fictional
client within the owner's budget. Record the run id, every count and the spend (model and search
separately). Then tick the parent plan's chunk 13 for Class C.

## Dependencies

- **Tool spend in the ledger** (deep-research.md chunk 4) before chunk 10 spends money.
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
  the result to open and the link to follow, by ref; code classifies, sends and journals every
  call, and grounds every finding in the track's own snapshots. Sources include PDF and XLSX."
- `CLAUDE.md` § 2: `web_retrieval.py` and `deep_research_runtime.py` entries corrected to name the
  live Wikipedia route (`web_retrieval_live.py`, `deep_research_live.py`) and, after chunk 8, the
  Brave route and its switches.
- `docs/architecture/deep-research.md` § 12 item 1: point to this plan.
