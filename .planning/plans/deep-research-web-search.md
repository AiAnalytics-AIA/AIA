---
status: planned
chunks:
  - "[x] 0. This plan: the provider choice (DR-2, Class C) and its chunks"
  - "[ ] 1. Data owner signs the choice; Brave terms confirmed in writing"
  - "[ ] 2. Brave search adapter over the existing SearchAdapter seam"
  - "[ ] 3. The API key as a credential reference (D8, for this route)"
  - "[ ] 4. Public-web fetch: any public host, robots.txt, identified user agent"
  - "[ ] 5. Composition, switch and dated price"
  - "[ ] 6. Czech source table (DR-5 input) for the hosts a real search returns"
  - "[ ] 7. Develop activation and one live fictional acceptance"
---
# Deep Research web search — a real search route (DR-2, Class C)

**Status:** planned · **Owner:** research-engine + ai-runtime · **Started:** 2026-10-05 ·
**Base:** `develop` @ `b2d43f7`
**Parent:** [deep-research.md](deep-research.md) chunk 13 (*Live enablement, blocked on DR-2*).
**Decides (proposed, needs the data owner):** DR-2 for **Class C** queries only. Class B stays
refused (see *What this plan does not do*).

## Problem

Deep Research has no web search. The production composition blocks every web track; the only
live route is fee-free Czech Wikipedia (`apps/executors/src/aia_executors/deep_research_live.py`
@ `b2d43f7`, behind `AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED`), and its fetch transport refuses every
other host (`infrastructure/web_retrieval_live.py:71-74` @ `b2d43f7`). Everything else runs on
recorded doubles: `aia_executors.deep_research_recorded` and `fixtures/deep_research/web.json`,
whose pages are invented `.example` sites.

That showed up on 2026-10-05: a demonstration report produced locally from the recorded
composition presented its Deep Research appendix as research. It was a replay of a fixture. A
researcher cannot get a real external source from AIA today.

The rest of the pipeline is built and tested offline: classification of every query, egress per
route, journaling before a call leaves, grounding of every quote in a snapshot the same track
captured, verification and the sealed bundle (deep-research.md §11). What is missing is one
provider behind `SearchAdapter` (`infrastructure/web_retrieval.py:97-110`) and a fetch transport
that may reach the pages it points to.

## The choice

### What the route has to satisfy

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

Each chunk is one PR into `develop`, green on `make verify`, with this file ticked.

### 1. Sign-off and terms (human; no code)

- The data owner records DR-2 (Class C) as Brave, in this file, with the date.
- The account is bought on a plan whose terms allow storing results and using them in an AI
  application. Record the plan name, its terms URL and date, the price per request, whether a
  failed request is billed, and the retention that applies.
- Decide D8 for this key (chunk 3's proposal, or Secrets Manager).

Done when: every row above is recorded here with a date; nothing else proceeds without it.

### 2. Brave search adapter

`infrastructure/web_retrieval_brave.py`: `BraveSearch(SearchAdapter)`, `RetrievalMode.LIVE`,
adapter id `brave-web-search-1`.

- One `GET` to the web search endpoint with `q`, `country=CZ`, `search_lang=cs`, `count` ≤ the
  gate's `max_results`, safe search on; no other parameter the provider would use to personalise.
- Hits: `url`, `title`, `description` → `SearchHit(url, title, snippet, rank)`, in the provider's
  order. A hit whose URL fails `check_url` is dropped and counted, never fetched.
- Every outcome mapped to `ToolCallFailed` with a `Delivery`: 4xx before processing (bad key,
  quota) is `RESPONDED`, timeout or reset after sending is `UNKNOWN` (the journal closes it
  uncertain and it is never resent, `test_a_search_left_in_flight_…`). No retry inside the
  adapter (the gate owns that).
- The transport is the pinned HTTPS client (checked IP, TLS to the host, no redirects, no proxy),
  scoped to the provider's API host.
- Tests: a captured response shape (fictional queries and results), every failure mode, the
  credential never in a log line or an exception message. No network.

### 3. The key as a credential reference (D8 proposal for this route)

The adapter holds a reference (`CredentialSource`, `model_adapters/transport.py:245-270`), never
the key. Proposal: an SSM `SecureString` `/aia/develop/aia_deep_research_brave_api_key`, which
`deploy/develop/bin/write-env.sh` already decrypts into the host's `.env`; the worker reads it,
the API and the web client never do (Compose passes it to the worker service only). A missing key
with the route on stops the worker at start, naming the key. Trade-off: the key sits in a root-only
file on the host, as every other develop secret does today; Secrets Manager would add rotation and
a second IAM grant. Production will need its own answer (D8 stays open there).

### 4. Public-web fetch

Brave's hits point anywhere, and the only live fetch transport refuses every host but
`cs.wikipedia.org`. Generalise it into `PublicHttpsTransport`:

- every public host that passes `check_url` and `check_resolution`, every hop re-checked;
  private, link-local and metadata addresses refused (the existing tests apply unchanged);
- `robots.txt` read once per host per run and obeyed for the AIA user agent; a fetch it disallows
  is refused and recorded, not attempted;
- an identifying user agent (`AIA-research/1 (+contact)`), no cookies, no credentials;
- the existing body, time and redirect caps; one request at a time per host.

The Wikipedia route keeps its narrower transport.

### 5. Composition, switch and price

- `AIA_DEEP_RESEARCH_WEB_SEARCH`: a closed set, `off` (default) or `brave`. `brave` needs
  `AIA_DEEP_RESEARCH_ENABLED`, the key from chunk 3, and
  `AIA_DEEP_RESEARCH_SEARCH_USD_PER_CALL` with `AIA_DEEP_RESEARCH_SEARCH_PRICE_DATE`; anything
  missing stops the worker at start, naming the key. It may not be combined with the Wikipedia
  switch in this chunk (one search route per run).
- Route: `ProviderRoute(route_id="brave-web-search", zone=US, eu_processing_approved=False,
  approved_for={CLASS_C_INTERNAL})`, so `evaluate_egress` refuses every Class B or A query before
  it is journaled as sent.
- Settings shows the route as configured or off, never as "connected" (`lib/ai-runtime.ts`).
- Tests: the production registry with the switch on composes the route; with it off, nothing
  changes; a Class B query is refused and nothing is sent.

### 6. Czech source table (input to DR-5)

Unknown hosts score lowest (`domain/deep_research/sources.py`), so a real search over the Czech
web would accept little. Propose a versioned extension of `SOURCE_TABLE_V1` for the hosts a Czech
market study meets: official statistics and regulators, major Czech news, trade bodies, the
companies named in the brief. The data owner approves the table; until then it ships off.

### 7. Develop activation and one live fictional acceptance

On develop, with the AI runtime and research agents already on: set the parameters, deploy, read
the worker's start-up log, and run one Deep Research pass for a fictional client within a budget
the data owner sets. Record here the run id, the searches and fetches sent, the findings accepted
and quarantined, the money spent (model and search separately), and anything refused. Then tick
the parent plan's chunk 13 for Class C.

## Dependencies

- **Tool spend in the ledger** (deep-research.md chunk 4): searches must be metered against the
  study's budget before chunk 7 spends money.
- **The AI runtime on develop** (ai-research-activation.md chunk 4): Deep Research's agents are
  Bedrock calls.
- Chunks 2–6 build and test entirely offline; only chunk 7 sends anything.

## What this plan does not do

- **Class B.** No query carrying a client's identity or confidential terms leaves. Linkup under a
  signed EU-processing, zero-retention agreement is the candidate to evaluate; that is a separate
  decision (DR-2, Class B; with D6 for the model route and DR-2b for the design digest).
- **Answer engines or provider browsing.** Rejected by criterion 1 and ADR 0017.
- **Production.** Develop only, fictional studies only, as ADR 0010 accepts.
- **Freshness** (deep-research.md §12 item 6): live results are reused by fingerprint as today.

## Findings

- `CLAUDE.md` § 2 says of `infrastructure/web_retrieval.py` "no live adapter exists (DR-2)", and
  of `deep_research_runtime.py` "no web retrieval exists"; `web_retrieval_live.py` and the
  Wikipedia switch exist @ `b2d43f7`. Stale map entry; see Doc follow-up.

## Doc follow-up

For the docs PR after chunk 0 merges:

- `.planning/overview.md` decision table, DR-2 row: "Proposed for Class C: Brave Search API, see
  `.planning/plans/deep-research-web-search.md`; Class B open (candidate: Linkup under an EU
  agreement)."
- `CLAUDE.md` § 2: `web_retrieval.py` and `deep_research_runtime.py` entries corrected to name the
  live Wikipedia route (`web_retrieval_live.py`, `deep_research_live.py`) and, after chunk 5, the
  Brave route and its switch.
- `docs/architecture/deep-research.md` § 12 item 1 and ADR 0017 *Consequences*: point to this plan.
