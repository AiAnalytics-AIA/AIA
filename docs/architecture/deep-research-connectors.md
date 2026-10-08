# Deep Research dataset connectors: terms, interfaces and limits

Plan: [`.planning/plans/deep-research-web-search.md`](../../.planning/plans/deep-research-web-search.md)
§ 5.3 (the `dataset` and `archive` tools), § 7 rungs 4, 7 and 9, § 8.2, chunks 14, 15 and 16
("each connector chunk starts with its recorded terms, interface and limits"). Companion to [deep-research.md](deep-research.md).

This file records what is known about each public data interface a connector reads, **with
where each fact came from and on what date**, before any connector is registered (chunk 23).
It is the connector chunks' record; terms change, so every fact carries its source and date.

## How to read the labels

- **VERIFIED**: seen on an official page of the publisher or operator, fetched on the date given.
- **UNVERIFIED**: anything else: a search engine's excerpt of an official page that could not be
  fetched, a third-party package or article, or an inference from a standard. An unverified fact
  is a hypothesis (CLAUDE.md § 4). The code built on it fails closed: an answer in another shape
  is refused (`response_contract`), never read loosely.

**Method, 2026-10-05.** From the session that wrote this, outbound fetches to `csu.gov.cz`,
`data.csu.gov.cz`, `data.gov.cz` and `data.europa.eu` were refused by the network egress proxy, so
none of their pages could be read first-hand. What is recorded below came from a web search tool
(excerpts of the official pages, paraphrased by the tool), from `pypi.org`, and from
`github.com/datagov-cz`, the Digital and Information Agency's (DIA) own repositories. The web
fetch tool returns a model's reading of a page, not its bytes; where a URL is quoted from such a
reading it is marked so.

**Method, 2026-10-06 (chunk 15).** Outbound fetches to `ec.europa.eu`, `api.openalex.org`,
`docs.openalex.org` and `web.archive.org` were refused by the network egress proxy (`CONNECT`
403); no live answer of any of the three interfaces was seen. Two operators publish their
documentation's source on GitHub, and those files were read **as bytes** (`curl` of
`raw.githubusercontent.com`, not the web fetch tool's reading): the Internet Archive's
`internetarchive/wayback` repository (`wayback-cdx-server/README.md`, branch `master`) and
OurResearch's `ourresearch/openalex-docs` repository (branch `main`; its GitBook markup matches
the published `docs.openalex.org`). Facts read there are VERIFIED with the file named. Nothing
of Eurostat's own documentation could be read first-hand: its facts are search excerpts or a
third party's, and UNVERIFIED.

## 1. ČSÚ DataStat

DataStat is the Czech Statistical Office's (ČSÚ) dissemination database that replaces the
Veřejná databáze (VDB).

| Fact | Status | Source (all 2026-10-05) |
|---|---|---|
| DataStat replaces the Veřejná databáze step by step; it offers CSV and JSON downloads of whole datasets and an API for data and metadata | UNVERIFIED (search excerpt) | [csu.gov.cz/produkty/datastat-postupne-nahrazuje-verejnou-databazi](https://csu.gov.cz/produkty/datastat-postupne-nahrazuje-verejnou-databazi) |
| DataStat was described as in pilot operation ("ověřovací provoz") | UNVERIFIED (search excerpt) | [csu.gov.cz terms page](https://csu.gov.cz/podminky_pro_vyuzivani_a_dalsi_zverejnovani_statistickych_udaju_csu) |
| Concepts: *datová sada* (dataset: indicators × dimensions), *výběr* (selection: a subset of a dataset for a table or the API), *předdefinovaný výběr* (an official selection), *ukazatel* (indicator), *dimenze* (dimension) | UNVERIFIED (search excerpt) | [csu.gov.cz/zakladni-informace-pro-pouziti-api-datastatu](https://csu.gov.cz/zakladni-informace-pro-pouziti-api-datastatu); PDF [datastatapi_prehled.pdf](https://csu.gov.cz/docs/107516/a6c39427-2c14-c06f-a016-e5aaf08e6e5a/datastatapi_prehled.pdf?version=2.0) |
| Catalogue API base `https://data.csu.gov.cz/api/katalog/v1`; Swagger at `…/katalog/v1/swagger-ui/index.html`; lists at `…/sady` (datasets with version and name), `…/vybery` (predefined selections), `…/ukazatele` (indicators) | UNVERIFIED (search excerpt of the official page; also named by `mcp-csu`) | same as above; [pypi.org/project/mcp-csu](https://pypi.org/project/mcp-csu/) |
| Data API base `https://data.csu.gov.cz/api/dotaz/v1`; Swagger at `…/dotaz/v1/swagger-ui/index.html` | UNVERIFIED (search excerpt; also named by `mcp-csu`) | same |
| `GET https://data.csu.gov.cz/api/dotaz/v1/data/vybery/{selection code}` returns a predefined selection's data in JSON-stat; `?format=CSV` returns CSV | UNVERIFIED (search excerpt) | official API page, as above |
| The JSON-stat version is 2.0 | UNVERIFIED, low confidence (one search excerpt; may be the tool's inference) | as above |
| A custom selection is `POST …/data/sady/{sadaKod}/vlastni` with a JSON body whose required fields are `sloupce`, `radky`, `filtryTabulky`; answers CSV, JSON-stat, XLSX or HTML | UNVERIFIED (search excerpt); the codes the body takes are not established | as above |
| Whole datasets download only as CSV or JSON-stat | UNVERIFIED (search excerpt) | as above |
| A local open-data catalogue exists at `https://data.csu.gov.cz/opendata/katalog` | UNVERIFIED (search excerpt; not reachable) | as above |
| No API key or registration | UNVERIFIED (third party: `mcp-csu` says "no authentication is required") | [pypi.org/project/mcp-csu](https://pypi.org/project/mcp-csu/) |
| Rate limits: none found on an official page. `mcp-csu` throttles *itself* to 3 parallel requests and 150 ms between requests; that is the package's choice, not ČSÚ's stated limit | UNVERIFIED | as above |
| Terms: the statistical information on csu.gov.cz is under CC BY 4.0, on conditions: cite ČSÚ as the source (without implying ČSÚ endorses the user), do not change the data's meaning, and state the licence (preferably by a link) when distributing. Whether these terms are stated for DataStat and its API is not established | UNVERIFIED (search excerpt) | [csu.gov.cz/podminky_pro_vyuzivani_a_dalsi_zverejnovani_statistickych_udaju_csu](https://csu.gov.cz/podminky_pro_vyuzivani_a_dalsi_zverejnovani_statistickych_udaju_csu) |

**What chunk 14 built on it** (`packages/aia_core/src/aia_core/infrastructure/dataset_datastat.py`,
unregistered): `DataStatConnector`, connector id `csu-datastat-1`, one `GET
/api/dotaz/v1/data/vybery/{code}` to `data.csu.gov.cz` only (code `[A-Za-z0-9_-]{1,64}`, else
never sent), `Accept`/content type `application/json` only, 5 MB cap, read as JSON-stat 2.0 by
`infrastructure/jsonstat.py` and refused in any other shape. Filters and a period are applied to
the answer by category code; nothing is written into the request but the code. The result's
`licence` is `None` ("not stated by the provider") until the terms above are verified. The test
fixture (`packages/aia_core/tests/fixtures/dataset_connectors/datastat_selection_fictional.json`)
is fictional, in the JSON-stat 2.0 shape; **no real DataStat answer has been captured.**

## 2. NKOD, the national open-data catalogue

NKOD (Národní katalog otevřených dat) is the Czech national catalogue of open data, run by the
Digital and Information Agency (DIA) at `data.gov.cz`. Its records are DCAT-AP-CZ.

| Fact | Status | Source (all 2026-10-05) |
|---|---|---|
| NKOD's public interfaces are a SPARQL endpoint at `https://<base>/sparql`, a Triple Pattern Fragments endpoint at `https://<base>/tpf`, a GraphQL endpoint at `https://<base>/graphql` and the web interface at `https://<base>`; `<base>` is `data.gov.cz` in production and `pod-test.dia.gov.cz` in test; all communication is HTTPS | VERIFIED (DIA's own repository; URLs quoted from the fetch tool's reading of the page) | [github.com/datagov-cz/nkd, "integrační dokumentace.md"](https://github.com/datagov-cz/nkd/blob/main/integra%C4%8Dn%C3%AD%20dokumentace.md) |
| An older endpoint `https://nkod.opendata.cz/sparql` and dump `https://nkod.opendata.cz/soubor/nkod.trig` | UNVERIFIED (search excerpts of older material; may be retired) | search results citing data.gov.cz conference material |
| DCAT-AP-CZ is the Open Formal Norm for catalogue interfaces, based on DCAT-AP 2.0.1 | UNVERIFIED (search excerpt) | [ofn.gov.cz/rozhraní-katalogů-otevřených-dat/2021-01-11/](https://ofn.gov.cz/rozhran%C3%AD-katalog%C5%AF-otev%C5%99en%C3%BDch-dat/2021-01-11/) |
| A record states its dataset's terms of use ("podmínky užití"); their RDF shape in DCAT-AP-CZ is not established here | UNVERIFIED | DIA annual reports (search excerpts) |
| Request and answer formats: the SPARQL 1.1 Protocol (`GET ?query=`) and SPARQL 1.1 Query Results JSON (`application/sparql-results+json`) are W3C standards; whether `data.gov.cz/sparql` serves that results format to such a GET is not established | UNVERIFIED (inference from the standards) | [W3C SPARQL 1.1 Protocol](https://www.w3.org/TR/sparql11-protocol/), [Query Results JSON](https://www.w3.org/TR/sparql11-results-json/) |
| Licence of the catalogue's own metadata | Not found | none |
| Rate limits, query timeouts, keys | Not found; no key is mentioned in the integration document's reading | none |

**What chunk 14 built on it** (`packages/aia_core/src/aia_core/infrastructure/dataset_nkod.py`,
unregistered): `NkodConnector`, connector id `nkod-sparql-1`, one fixed SELECT (`nkod_query`)
to `data.gov.cz/sparql` only, the dataset IRI its only variable part (a public `https` URL; the
query contract excludes every character that could close an IRIREF). It asks for W3C DCAT and
DCMI terms only: `dct:title`, `dct:publisher`, and per `dcat:distribution` `dct:format`,
`dcat:mediaType`, `dcat:downloadURL`, `dcat:accessURL`, `dct:license`. Answers of type
`application/sparql-results+json` or `application/json`, 1 MB cap, at most 399 bindings (400 is
refused, not cut). The result's `licence` is `None`. The fixture
(`…/fixtures/dataset_connectors/nkod_dataset_fictional.json`) is fictional; **no real NKOD
answer has been captured.**

## 3. Eurostat (API Statistics)

| Fact | Status | Source (all 2026-10-06) |
|---|---|---|
| Data endpoint `https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/<DATASET_CODE>` | UNVERIFIED (search excerpt of the official page) | [ec.europa.eu/eurostat/…/api-introduction](https://ec.europa.eu/eurostat/fr/web/user-guides/data-browser/api-data-access/api-introduction) |
| The answer is JSON-stat 2.0; labels in English, French or German (`lang=EN`) | UNVERIFIED (search excerpt) | as above |
| Filters are `<DIMENSION_CODE>=<VALUE>`, case-insensitive; several values of one dimension are repeated parameters (`geo=CZ&geo=SK`) | UNVERIFIED (search excerpt) | [ec.europa.eu/eurostat/…/api-statistics](https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-detailed-guidelines/api-statistics) |
| Time: `time=<period>`; or `sinceTimePeriod`, `untilTimePeriod` (together allowed), `lastTimePeriod=<n>`; no other combination of time parameters is accepted | UNVERIFIED (search excerpts) | as above |
| `geoLevel=aggregate\|country\|nuts1\|nuts2\|nuts3` | UNVERIFIED (search excerpt) | as above |
| A request the API decides to answer asynchronously is answered `{"warning":{"status":413,"label":"ASYNCHRONOUS_RESPONSE. …"}}`; datasets over 500,000 cells are asynchronous | UNVERIFIED (search excerpt) | as above |
| Eurostat's JSON-stat documents carry no `role`; Eurostat uses standardised dimension names (`geo`, `time`, `unit`, `freq`) | UNVERIFIED (third party: the JSON-stat author's EuroJSONstat library README, read as bytes) | [github.com/jsonstat/euro](https://github.com/jsonstat/euro) |
| At most 50 categories per request, not counting time and (usually) geo | UNVERIFIED (third party: EuroJSONstat API reference) | [github.com/jsonstat/euro/…/API.md](https://github.com/jsonstat/euro/blob/master/docs/API.md) |
| A status symbol's label is carried in a JSON-stat `extension` | UNVERIFIED (search excerpt citing EuroJSONstat) | as above |
| Reuse of statistical data is authorised, commercial or not, provided the source is acknowledged (Commission Decision 2011/833/EU); editorial content is CC BY 4.0 | UNVERIFIED (search excerpt) | [ec.europa.eu/eurostat/help/copyright-notice](https://ec.europa.eu/eurostat/help/copyright-notice) |
| Content type of the JSON answer; a key; rate limits | Not found | none |

**What chunk 15 built on it** (`packages/aia_core/src/aia_core/infrastructure/dataset_eurostat.py`,
unregistered): `EurostatConnector`, connector id `eurostat-statistics-1`, one GET to
`ec.europa.eu` only: `…/statistics/1.0/data/{code}?format=JSON&lang=EN`, then the query's
filters sorted by dimension (one parameter per value), then `time=<period>`. The code is
`[A-Za-z0-9_]{1,64}`; a dimension is `[A-Za-z0-9_]{1,64}` and may not be one of the parameters
the connector writes itself (`format`, `lang`, `time`, `sinceTimePeriod`, `untilTimePeriod`,
`lastTimePeriod`, `geoLevel`); a category is `[A-Za-z0-9_.-]{1,64}`; anything else is never sent.
`application/json` only, 5 MB cap. The answer is read by `jsonstat.py` with `time` named as the
time dimension when the document declares no role (a declared role wins; a document without
`time` is refused), and the filters are checked again on it: an asked category the answer lacks
is `filter_category_unknown`, never a silently wider table. The `unit` dimension is a note or a
part of a row's label, never a unit stamped on a cell. The asynchronous warning is
`dataset_asynchronous` (provider answered, no table, nothing polls). `licence` is `None`. The
fixture (`…/fixtures/dataset_connectors/eurostat_dataset_fictional.json`) is fictional; **no real
Eurostat answer has been captured.** A dimension code is matched exactly as the answer spells it
(`geo`, not `GEO`): Eurostat is recorded as case-insensitive, the reader is not.

## 4. OpenAlex (works and their open-access locations)

| Fact | Status | Source (all 2026-10-06, `ourresearch/openalex-docs@main`) |
|---|---|---|
| `GET https://api.openalex.org/works/<id>` answers one `Work`; external ids in URN form, among them `doi:` (`/works/doi:<DOI>`), or URL form (`/works/https://doi.org/<DOI>`) | VERIFIED | `api-entities/works/get-a-single-work.md`, `how-to-use-the-api/get-single-entities/README.md` |
| An incorrect id gets no result; an id containing `,` or `&` fails with 403 | VERIFIED | `api-entities/works/get-a-single-work.md` |
| A merged entity's id redirects to the entity it was merged into | VERIFIED | `how-to-use-the-api/get-single-entities/README.md` |
| `select=` keeps only the listed **root-level** fields, on a single entity or a list | VERIFIED | `how-to-use-the-api/get-lists-of-entities/select-fields.md`, `get-a-single-work.md` |
| `GET /works?search=<text>` searches titles, abstracts and fulltext; `AND`, `OR`, `NOT` are operators only in UPPER CASE; results are sorted by `relevance_score` | VERIFIED | `api-entities/works/search-works.md`, `how-to-use-the-api/get-lists-of-entities/search-entities.md` |
| A list answers `{"meta": {…, "count", "per_page"}, "results": […]}`; 25 per page by default, `per-page` 1–200; `filter=publication_year:2020` | VERIFIED | `how-to-use-the-api/get-lists-of-entities/README.md`, `…/paging.md` |
| `Work` fields: `id`, `doi` (`https://doi.org/…`, the published version's DOI), `title`, `publication_year`, `type`, `open_access` {`is_oa`, `oa_status` ∈ diamond/gold/green/hybrid/bronze/closed, `oa_url`, `any_repository_has_fulltext`}, `best_oa_location`, `locations`, `authorships` (≤ 100 authors) | VERIFIED | `api-entities/works/work-object/README.md` |
| `Location`: `is_oa` ("a URL where you can read the fulltext of this work without needing to pay money or log in"), `landing_page_url`, `pdf_url`, `license` (e.g. `cc-by`; null when undetermined), `version` ∈ `publishedVersion`/`acceptedVersion`/`submittedVersion`, `source` {`display_name`, `type` …}, `is_accepted`, `is_published` | VERIFIED | `api-entities/works/work-object/location-object.md` |
| `best_oa_location` is scored: `is_oa` required; publisher over repository; published over accepted over submitted; a PDF link over none; major repositories ranked higher | VERIFIED | `work-object/README.md` |
| No authentication required; 100,000 credits a day free, 100 requests a second; a singleton costs 1 credit, a list 10; over the limit is HTTP 429; `X-RateLimit-*` headers on every answer | VERIFIED | `how-to-use-the-api/rate-limits-and-authentication.md` |
| Polite pool: `mailto=you@example.com` as a parameter, or `mailto:` in the User-Agent | VERIFIED | as above |
| "Our complete dataset is free under the CC0 license" | VERIFIED | `README.md` |
| Content type of the answer (`application/json` assumed) | UNVERIFIED (not stated) | none |
| That `docs.openalex.org` publishes this repository unchanged | UNVERIFIED (the GitBook markup matches; the site was not reachable) | none |

**What chunk 15 built on it** (`…/infrastructure/dataset_openalex.py`, unregistered):
`OpenAlexConnector`, connector id `openalex-works-1`, one GET to `api.openalex.org` only. The
answer is search-like metadata, not a statistical cube, and it is modelled as a table of records
(like NKOD's distributions):

- `doi:<DOI>` (`10.\d{4,9}/…`, no whitespace, `,` or `&`): `GET /works/doi:<DOI>?select=id,doi,
  title,publication_year,type,open_access,best_oa_location,locations`; 1 credit. One row per
  location (`loc1` …, labelled by its source's name), columns `is_oa`, `version`, `license`,
  `landing_page_url`, `pdf_url`, source name and type, and whether it is `best_oa_location`; the
  title, DOI, OpenAlex id, year, type and `open_access` are notes. An answer for another DOI is
  refused. `open_access_copies(result)` is the ladder's reading (plan § 7 rung 7): only `is_oa`
  locations, the PDF else the landing page, OpenAlex's best first. A paywalled version of record
  is never offered as a copy.
- `works` with filter `search` (1–10 words of `[A-Za-z0-9-]`, sent lower case so that none is an
  operator) and optionally `publication_year` (one year): `GET /works?search=…&filter=
  publication_year:<y>&select=id,doi,title,publication_year,open_access&per-page=25`; 10 credits.
  One row per work in the provider's order; `meta.count` is a note. A free-text phrase (with
  diacritics, quotes, operators) is not a dataset query: it is the search tool's.
- No author, affiliation or abstract is asked for (`select`), so nothing person-level is received
  or stored (plan § 4). `mailto` is a constructor value (an email address, or `None`; never
  guessed, never in code); it is sent and kept out of the stored `source_url`. No key. A merged
  work's redirect is not followed (`redirect_refused`). `licence` is `CC0` (OpenAlex's data); a
  location's `license` is the work's, and a cell. The credits are the `DatasetResponse.credits`
  the gate journals. Fixtures `openalex_work_fictional.json` and `openalex_search_fictional.json`
  are fictional; **no real OpenAlex answer has been captured.**

## 5. Wayback Machine CDX index (archived captures)

| Fact | Status | Source (all 2026-10-06, `internetarchive/wayback@master`, `wayback-cdx-server/README.md`) |
|---|---|---|
| `GET http://web.archive.org/cdx/search/cdx?url=<url>`; `url` is the only required parameter and is URL-encoded if it carries a query | VERIFIED | § Basic Usage |
| Public fields: `urlkey`, `timestamp`, `original`, `mimetype`, `statuscode`, `digest`, `length`; `fl=` picks and orders them | VERIFIED | § Basic Usage, § Field Order |
| `output=json` answers a JSON array whose first row names the fields | VERIFIED | § Output Format (JSON) |
| The answer is gzip-encoded by default; `gzip=false` turns it off | VERIFIED | as above |
| `matchType=exact` is the default; `prefix`, `host`, `domain` widen it | VERIFIED | § Url Match Scope |
| `from=` / `to=`: 1 to 14 digits (`yyyyMMddhhmmss`), inclusive | VERIFIED | § Filtering |
| `collapse=digest` drops **adjacent** captures with the same digest | VERIFIED | § Collapsing |
| `limit=N` the first N rows, `limit=-N` the last N (slow); a server maximum of 150,000 per query by default | VERIFIED | § Query Result Limits |
| An API key cookie grants access to restricted data; none is needed for public captures | VERIFIED (a feature of the software; whether `web.archive.org` restricts anything is not stated) | § Access Control |
| HTTPS serves the same as the documented `http://` URL | UNVERIFIED | none |
| Content type of the JSON answer (`application/json` or `text/plain`) | UNVERIFIED (not stated; both accepted) | none |
| An empty answer is `[]` (no header row) | UNVERIFIED (not stated; read as "no capture") | none |
| A capture's replay URL is `https://web.archive.org/web/<timestamp>/<original>` (and `…/<timestamp>id_/<original>` for the original bytes) | UNVERIFIED (the README shows only the calendar's `/web/*/<url>`) | § Collapsing |
| The Internet Archive's terms of use, and any rate limit of the CDX server | Not read | none |

**What chunk 15 built on it** (`…/infrastructure/dataset_wayback.py`, unregistered):
`WaybackCdxConnector`, connector id `wayback-cdx-1`, **tool kind `archive_lookup`**. One GET to
`web.archive.org` only: `/cdx/search/cdx?url=<page>&output=json&gzip=false&fl=timestamp,original,
mimetype,statuscode,digest,length&collapse=digest&limit=200`, plus `from` and `to` set to the
query's period (4–14 digits, whole date parts). The page is a public `http(s)` URL under AIA's own
fetch rules (`web.check_url`); filters are refused. The header row must be exactly the six fields
asked for; every row is checked (a real 14-digit timestamp, a 3-digit status or `-`, a digest, a
length); 200 rows or more is `dataset_too_large`, never read as every capture. One row per
capture (`c1` …), its fields as published plus the replay URL (unverified form).
`nearest_capture` picks the HTTP 200 capture nearest a cited date (a capture of a redirect or an
error is no copy); `licence` is `None`. Fixture `wayback_cdx_fictional.json` is fictional.
**Fetching an archived page is not built**: no public-web fetch is on this branch's base (plan
chunk 5, PR #143); the replay host would go through that fetch path, on the archive's own route,
when it lands.

**The archive is used only for a dead or moved page** (`domain/deep_research/archive.py`, plan
§ 4 and § 7 rung 9). `decide_archive_use(LiveAttempt, needed_quote)` is the only issuer of an
`ArchivePermit` (a module-private issuer; `layer_check` forbids constructing one elsewhere), and
`RetrievalGate.archive` asks an `archive_lookup` connector only with a permit for the same URL,
refusing and journaling `archive_not_permitted` otherwise; `RetrievalGate.dataset` cannot reach
an archive at all. Allowed: `dead` (404, 410, the host no longer resolves), `moved` (redirected
elsewhere and the quote is gone), `changed` (same URL, quote gone). Refused: the live page holds
the quote (`live_has_quote`); a barrier on the page, or 401/402/403/451
(`live_access_restricted`; an unstated barrier counts as one); 408/429/5xx/connection failures
(`live_transient`); an uncertain delivery (`live_uncertain`); AIA's own refusal of the URL
(`live_refused`); any failure not named (`live_failure_unrecognised`).
`application.web_retrieval.live_attempt` builds the attempt from the gate's `FetchOutcome`.

## 6. ARES, the register of economic subjects (chunk 16)

ARES (Administrativní registr ekonomických subjektů) is the Ministry of Finance's register that
gathers a subject's public facts from the source registers (public register, RES, trade
licences, VAT …), by IČO.

**Method, 2026-10-06.** `ares.gov.cz`, `mf.gov.cz` and `www.mfcr.cz` were refused by the egress
proxy, so nothing of the Ministry's own could be read first-hand. The facts below come from a web
search tool's excerpts and from third-party clients on GitHub, read as raw files (bytes, not a
model's reading). Nothing here is VERIFIED.

| Fact | Status | Source (all 2026-10-06) |
|---|---|---|
| REST base `https://ares.gov.cz/ekonomicke-subjekty-v-be/rest`; one subject is `GET /ekonomicke-subjekty/{ico}`; the answer is `application/json` | UNVERIFIED (third party: a PHP client generated from ARES's OpenAPI document; a search excerpt names the same base, and another client's changelog records dropping a wrong `/v3` suffix) | [github.com/JanBukva/ares-gov-cz-swagger](https://github.com/JanBukva/ares-gov-cz-swagger) `README.md`, `lib/Api/EkonomickeSubjektyApi.php`; [vzeman/ares-mcp-server](https://github.com/vzeman/ares-mcp-server) (search excerpt) |
| The OpenAPI document is at `…/rest/v3/api-docs` | UNVERIFIED (search excerpt) | as above |
| The subject's JSON field names: `ico`, `obchodniJmeno`, `sidlo`, `pravniForma` (a code of the `PravniForma` list), `financniUrad`, `datumVzniku`, `datumZaniku`, `datumAktualizace`, `dic`, `czNace` (a list), `adresaDorucovaci`, `seznamRegistraci` (`stavZdrojeVr`, `stavZdrojeRes`, `stavZdrojeDph`, …), `primarniZdroj`, `dalsiUdaje`, `icoId`, `subRegistrSzr`, `dicSkDph` | UNVERIFIED (third party: the generated client's `attributeMap`) | `lib/Model/EkonomickySubjekt.php`, `lib/Model/EkonomickySubjektZaklad.php` in the repository above |
| The seat (`sidlo`, model `Adresa`): `kodStatu`, `nazevStatu`, `nazevKraje`, `nazevObce`, `nazevUlice`, `cisloDomovni`, `psc` (an integer), `textovaAdresa`, … | UNVERIFIED (as above) | `lib/Model/Adresa.php` |
| Separate endpoints per source register (`/ekonomicke-subjekty-vr/{ico}` for the public register, `-res`, `-rzp`, …); the public-register record carries persons (statutory bodies, members) | UNVERIFIED (as above: model names `AngazovanaOsoba…`, `AngazmaFyzickaOsobaVr`) | `README.md` of the repository above |
| Terms: anyone may use the services who keeps to the operating conditions; the Ministry may restrict or block a user who sends more than 500 requests a minute, repeatedly malformed requests, or many simultaneous requests | UNVERIFIED (search excerpt) | [mf.gov.cz/cs/ministerstvo/informacni-systemy/ares](https://mf.gov.cz/cs/ministerstvo/informacni-systemy/ares) |
| Licence of the data (open data or other) | Not found | none |
| Legal-form codes recorded as legal persons ("právnická osoba") in the ROS code list: 111 v.o.s., 112 s.r.o., 113 k.s., 121 a.s., 205 družstvo, 325 organizační složka státu, 331 příspěvková organizace zřízená ÚSC, 801 obec; code 100 is a natural person ("podnikající fyzická osoba tuzemská") | UNVERIFIED (search excerpts of the code list) | [ROS code list (szrcr.cz)](https://www.szrcr.cz/images/dokumenty/ROS/Ciselnik%20pravnich%20forem.pdf), [ČSÚ 2022 list](https://csu.gov.cz/docs/107516/0395cbd0-ee10-3bab-ecd6-8de0df13ff55/ciselnik_pravnich_norem_ros_2022.pdf) |

**What chunk 16 built on it** (`packages/aia_core/src/aia_core/infrastructure/dataset_ares.py`,
unregistered): `AresConnector`, connector id `ares-subject-1`, one `GET
/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/{ico}` to `ares.gov.cz` only. The dataset id
is the IČO, checked (eight digits, mod-11 check digit) before anything is sent; no filter, no
period; `application/json` only, 512 KB cap. The table is one row (`subjekt`, labelled `IČO
<ico>`) of an **allowlist** of legal-entity fields: IČO, business name, legal-form code, dates of
establishment, dissolution and update, DIČ, CZ-NACE codes, the seat's text address, municipality,
postcode, region and country code, and the subject's state in the public register, RES and the
VAT register. Licence `None`. The fixtures (`…/fixtures/dataset_connectors/ares_*_fictional.json`)
are fictional; **no real ARES answer has been captured.**

## 7. Public procurement: ISVZ, VVZ and NEN (chunk 16)

**Method, 2026-10-06.** `isvz.nipez.cz`, `www.isvz.cz`, `nen.nipez.cz`, `vvz.nipez.cz` and
`podpora.nipez.cz` were refused by the egress proxy. The facts come from a web search tool's
excerpts and from one third-party reader of the ISVZ open data on GitHub (raw files). Nothing
here is VERIFIED.

| Fact | Status | Source (all 2026-10-06) |
|---|---|---|
| ISVZ publishes open data on public contracts at `https://isvz.nipez.cz/opendata`; from February 2024 the "new" open data are JSON, with a documentation of the structure per category (public contract, dynamic purchasing system, design contest …) | UNVERIFIED (search excerpt) | [isvz.nipez.cz … nova-open-data-dokumentace-json-formatu](https://isvz.nipez.cz/centrum-podpory/napoveda/webovy-portal-isvz/open-data/nova-open-data-dokumentace-json-formatu) |
| Earlier open data (ZZVZ 2016–2024, VVZ 2006–2016, e-marketplaces) were yearly gzip-served XML files under `https://isvz.nipez.cz/sites/default/files/content/opendata-predchozi/` (e.g. `ODZZVZ/{year}.xml`), with one `VZ` element per form whose children include `EvidencniCisloVZnaVVZ`, `CisloFormulareNaVVZ`, `DruhFormulare`, `PlatnyFormular`, `DatumUverejneni`, `ZadavatelUredniNazev`, `ZadavatelICO`, `NazevVZ`, `DruhVZ`, `DruhRizeni`, `CPVhlavni`, `OdhadovanaHodnotaVZbezDPH`, `OdhadovanaHodnotaVZmena`, `CelkovaKonecnaHodnotaVZ`, `CelkovaKonecnaHodnotaVZmena`, `LhutaProDoruceniNabidek`, and personal ones: `ZadavatelKontaktniOsoba`, `ZadavatelEmail`, `ZadavatelTelefon`, `OteviraniNabidekOpravneneOsobyDalsiInfo`; suppliers (`DodavatelICO`, `DodavatelNazev`, their address) in a separate `Dodavatele` element | UNVERIFIED (third party: `kokes/od`, `data/zakazky/main.py` and `mapping.json`) | [github.com/kokes/od](https://github.com/kokes/od) |
| Whether the 2024+ JSON open data use the same names | Not found | none |
| A contract's evidence number on the VVZ has the form `Z{yyyy}-{nnnnnn}` | UNVERIFIED (search excerpt of the VVZ interface methodology) | [cms.vvz.nipez.cz, Metodika pro připojování elektronických nástrojů](https://cms.vvz.nipez.cz/wp-content/uploads/2023/03/Priloha-c.-4-Metodika-pro-pripojovani-elektronickych-nastroju-na-rozhrani-VVZ_v1_1_final.pdf) |
| NEN numbers a procedure `N006/{yy}/V{nnnnnnnn}` (N: NEN, 006: its identifier, V: public contract); its public detail pages carry the number with dashes, `nen.nipez.cz/…/detail-zakazky/N006-23-V00006611` | UNVERIFIED (search excerpt; URLs seen in search results) | [nen.nipez.cz](https://nen.nipez.cz/en/verejne-zakazky) |
| NEN has a public API documented at `podpora.nipez.cz/…/verejne-api-systemu-nen`; the VVZ form interface is on SwaggerHub (`sne/vvzxml-formulare`) with hosts `api.vvz.nipez.cz` and `ref.api.vvz.nipez.cz`; the Register of Public Contracts has Swagger documents in its reference and test environments. Whether any offers an anonymous read of one notice is not established | UNVERIFIED (search excerpts) | as above |
| Licence and rate limits of any of these | Not found | none |

**What chunk 16 built on it**
(`packages/aia_core/src/aia_core/infrastructure/dataset_procurement.py`, unregistered):
`ProcurementNoticeConnector`, connector id `isvz-notice-1`. The dataset id is the VVZ evidence
number (`Z{yyyy}-{nnnnnn}`, else never asked; a NEN number is refused, since no record field
linking it is known). Records come through a `NoticeSource` seam, and **no live source exists**,
because no per-notice read interface could be established; the only source is
`RecordedNoticeSource`, a test double that `layer_check` keeps out of every composition. The table
is one row per form (key: the form number), labelled `<evidence number> formulář <form>`, of an
**allowlist** read under the ISVZ field names above; every record must carry the evidence number
asked for. Values as published, as text; a JSON float, an amount or a date in another form, or an
IČO with letters is refused. Licence `None`. The fixture
(`…/fixtures/dataset_connectors/procurement_notice_fictional.json`) is fictional; **no real
answer has been captured.**

## 7a. Crossref and OpenAlex: a cited work's retraction (chunk 46)

**Method, 2026-10-08.** `api.crossref.org` and `api.openalex.org` were refused by the network
egress proxy (`CONNECT` 403); no live answer was seen. Two documentation files were read **as
bytes** from `raw.githubusercontent.com`: OurResearch's `openalex-docs@main`
(`api-entities/works/work-object/README.md`) and Crossref's `rest-api-doc@master`
(`api_format.md`).

| Fact | Status | Source |
|---|---|---|
| A `Work` has `is_retracted`, a boolean, "True if we know this work has been retracted", identified from the Retraction Watch database | VERIFIED | `openalex-docs@main`, `work-object/README.md` |
| Crossref's `Update` object: `updated` (a Partial Date, `date-parts` with only the year required), `DOI`, `type` (e.g. `retraction`, `correction`), `label` optional; a work's `update-to` is an array of them | VERIFIED | `rest-api-doc@master`, `api_format.md` |
| `GET https://api.crossref.org/works/{doi}` answers `{"status", "message-type": "work", "message": {...}}`; `mailto=` asks the polite pool | UNVERIFIED (Crossref's README, search excerpt) | github.com/CrossRef/rest-api-doc |
| A retracted work lists its notices under `message["updated-by"]`, each an `Update` with a `source` (`publisher` or `retraction-watch`); the notice itself carries `update-to` | UNVERIFIED (Crossref blog "Retraction Watch retractions now in the Crossref API"; Crossref's Retraction Watch documentation; its GitLab tutorial) | crossref.org, crossref.gitlab.io |
| The update types beyond `retraction` and `correction` (`withdrawal`, `removal`, `partial_retraction`, `expression_of_concern`, `corrigendum`, `erratum`, `addendum`, `clarification`) | UNVERIFIED (the schema's list as third parties quote it) | none first-hand |

**What chunk 46 built on it.** `CrossrefConnector` (`crossref-works-1`, one GET to
`api.crossref.org`, `doi:<DOI>` only, `mailto` the deployment's contact, kept out of the stored
URL): one row per `updated-by` entry, an update type no table maps read as `unknown`, never
guessed; an answer for another DOI, or `updated-by` in another shape, is refused. OpenAlex's DOI
lookup asks `is_retracted` too and states it as a note (`true`, `false`, or `not stated`). The
merge step asks both about each distinct DOI a run's sources name in their own metadata
(`domain/deep_research/works.py`); the most severe status either states stands; neither
answering is `UNKNOWN`. **No real answer of either has been captured**; the live acceptance
(chunk 27) checks the unverified rows against one.

## 8. The shared contract (every connector)

- `domain/deep_research/datasets.py`: `DatasetQuery` (connector, dataset id, filters by
  category code, period) and `DatasetResult` (a table: title, publisher, licence or `None`,
  source URL, columns and rows with labels, units and periods, values as published text).
  Rendering `aia-dataset-table-1`: one line per cell, `[<dataset>!<row>/<column>] <row label> |
  <column label> | period <p> | unit <u> = <value>[ | status <s>]`. Refused, never truncated,
  over 5,000 cells or 200,000 characters.
- `SourceSnapshot.dataset`: the table beside its rendering (the snapshot's text). Omitted from
  the serialised form when absent, so page snapshots keep their bytes and hashes.
- `grounding.ground_cell`: a quote is exactly one cell's line, or it does not ground.
- `ToolKind.DATASET_QUERY`; `RetrievalGate.dataset`: classified like a search (the query text is
  the dataset id, filters and period), **Class C only**, egress, metering, journaled around the
  call. `ToolKind.ARCHIVE_LOOKUP`; `RetrievalGate.archive`: the same path on an archive's own
  route, after an `ArchivePermit` for the URL. A connector's class fixes its `tool_kind`, and a
  `DatasetAccess` whose route is of another kind is refused at construction.
- `DatasetResponse.credits`: the provider's own unit of charge, journaled (OpenAlex: 1 or 10).
- `infrastructure/dataset_connectors.py`: `DatasetConnector` (raises only `ToolCallFailed` with
  a `Delivery`), `HostScopedClient` (one host, checked addresses, no redirect, byte cap,
  declared type, fixed error text), `RecordedDatasetConnector` (test double; `layer_check`).

## 9. Personal data in the register and procurement connectors (plan § 4)

| Decision | Where |
|---|---|
| Fields are read from an **allowlist**; nothing outside it is read, copied, rendered or stored. A field the provider adds later is ignored, never stored | `ARES_FIELDS`, `ARES_SEAT_FIELDS`, `ARES_REGISTRATION_FIELDS`; `NOTICE_FIELDS` |
| The raw answer is kept only as its SHA256 and byte length | `DatasetResponse`, `SourceSnapshot.raw_sha256` |
| **A sole trader (OSVČ) is refused whole.** An ARES subject is read only when its legal-form code is in `LEGAL_ENTITY_FORMS` (codes recorded as legal persons); any other code, none, or one not yet recorded is `not_a_legal_entity` (delivery `RESPONDED`, so journaled as answered), with fixed text that carries nothing of the answer. A legal form missing from the list costs a refused query; a natural person's form on it would store a person's name, so the list stays short until the code list is read first-hand | `dataset_ares.py` |
| A legal entity's business name and registered seat are stored: they are the entity's own public identity, even when the name contains a person's name (e.g. "Novák s.r.o.") | `dataset_ares.py` |
| ARES persons (statutory bodies, members, partners) and the delivery address are never read; the public-register endpoint that carries the persons is not used | `dataset_ares.py` |
| Procurement: the contact person, e-mail and telephone, the persons at the opening of tenders, the free-text description and every supplier field are never read (a supplier can be a sole trader) | `NOTICE_FIELDS` |
| Procurement: in the two free-text fields read (authority name, contract title), e-mail addresses and telephone numbers are replaced by `[osobní údaj odstraněn]`, and a note says so. A nine-digit run in a title is redacted as if it were a phone number | `dataset_procurement.py` |
| A query's text (an IČO, an evidence number) is journaled like any query, so the IČO of a refused sole trader stays in the tool journal | `RetrievalGate.dataset` |

## 10. Before a composition names a connector (chunk 23)

Each item is a check to make first-hand, recorded here with its date and the page it was seen on:

1. Read the DataStat API page and Swagger (`…/dotaz/v1/swagger-ui/index.html`) and record the
   selection-data endpoint, its content type and the JSON-stat version; capture one real answer
   (a public selection) as a fixture beside the fictional one.
2. Read ČSÚ's terms for DataStat data and its API, and record the licence string and URL the
   connector should state (today `DATASTAT_LICENCE = None`).
3. Find any stated rate limit or fair-use rule for DataStat and for `data.gov.cz/sparql`; size
   the per-host politeness of chunk 21 to it.
4. Send `nkod_query` for one known public dataset IRI to `data.gov.cz/sparql`, record the
   content type and shape of the answer, and capture it as a fixture.
5. Establish DCAT-AP-CZ's terms-of-use structure from the OFN specification and decide whether
   the NKOD connector reads it (a new column, a new query version).
6. Record the price of each route (expected zero) and its ADR 0008 route facts (zone, retention)
   in the plan's § 13, for Eurostat, OpenAlex and the Wayback Machine as for the two above.
7. Eurostat: read the API Statistics pages first-hand; confirm the endpoint, `format=JSON`,
   `lang`, the filter and `time` syntax, the content type, the asynchronous warning and that
   documents carry no `role`; capture one real answer; read the copyright notice and record the
   licence string the connector should state (today `EUROSTAT_LICENCE = None`).
8. OpenAlex: capture one real `/works/doi:` answer and one `/works?search=` answer with the
   connector's `select`; confirm the content type; decide the polite-pool contact (an operator
   mailbox, configured, never a person's own address) and record it as a setting, not code.
9. Wayback: confirm the HTTPS endpoint, the JSON content type, the empty answer and the replay
   URL form; read the Internet Archive's terms of use and any stated rate limit; capture one real
   CDX answer. Then wire the archived-page fetch through the public-web fetch path (chunk 5) on
   the archive's own route.

## 11. Before a composition names the ARES or procurement connector (chunk 23)

1. Read ARES's developer page and OpenAPI document first-hand; record the subject endpoint, its
   content type, its field names and its error shape (an unknown IČO), and capture one real
   answer for a public company as a fixture beside the fictional ones.
2. Read the Ministry of Finance's ARES terms (request limits, conditions, any licence) and record
   them; size chunk 21's per-host politeness below the stated limit.
3. Read the ROS legal-form code list first-hand; confirm that each code in `LEGAL_ENTITY_FORMS`
   is a legal person, and decide which further legal-person forms to add, each one checked.
4. Read the ISVZ open-data documentation and NEN's public API documentation; decide which offers
   an anonymous read of one notice; record its endpoint, shape and terms; write the live
   `NoticeSource` against a captured real answer, and check the record field names.
5. Decide whether a NEN system number is accepted, once a field linking it to the VVZ evidence
   number (or a NEN-native source) is established.
6. Record each route's price (expected zero) and its ADR 0008 route facts in the plan's § 13.
