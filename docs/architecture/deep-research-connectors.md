# Deep Research dataset connectors: terms, interfaces and limits

Plan: [`.planning/plans/deep-research-web-search.md`](../../.planning/plans/deep-research-web-search.md)
§ 5.3 (the `dataset` tool), § 7 rung 4, § 8.2, chunk 14 ("each connector chunk starts with its
recorded terms, interface and limits"). Companion to [deep-research.md](deep-research.md).

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

## 3. The shared contract (both connectors, and every later one)

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
  call.
- `infrastructure/dataset_connectors.py`: `DatasetConnector` (raises only `ToolCallFailed` with
  a `Delivery`), `HostScopedClient` (one host, checked addresses, no redirect, byte cap,
  declared type, fixed error text), `RecordedDatasetConnector` (test double; `layer_check`).

## 4. Before a composition names either connector (chunk 23)

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
   in the plan's § 13.
