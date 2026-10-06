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

## 5. ARES, the register of economic subjects (chunk 16)

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

## 6. Public procurement: ISVZ, VVZ and NEN (chunk 16)

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

## 7. Personal data in the register and procurement connectors (plan § 4)

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

## 8. Before a composition names the ARES or procurement connector (chunk 23)

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
