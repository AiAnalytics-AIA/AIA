# Deep Research: Common Crawl's URL index and archived pages

Plan chunk 18 of [`.planning/plans/deep-research-web-search.md`](../../.planning/plans/deep-research-web-search.md)
(§ 5.3 `archive`, § 7 ladder rung 9). Built and tested offline on 2026-10-06; composed by
`deep_research_live.common_crawl_archive` behind `AIA_DEEP_RESEARCH_COMMON_CRAWL` (chunk 23e,
#221); chunk 27 runs it live. Anchors are to commit `416733e` on
`feature/dr-common-crawl`.

## What it does

1. **Find captures.** `RetrievalGate.query_url_index`
   (`packages/aia_core/src/aia_core/application/web_retrieval.py:748 @ 416733e`) asks Common
   Crawl's columnar URL index where a URL, host or registered domain was captured, through
   Amazon Athena in `us-east-1`. The statement is written by code from a validated
   `UrlIndexQuery` (`domain/deep_research/common_crawl.py:213 @ 416733e`); no model writes SQL.
2. **Read one capture.** `RetrievalGate.fetch_archived` (`web_retrieval.py:840 @ 416733e`)
   requests exactly the byte range the index names from `https://data.commoncrawl.org/<warc_filename>`,
   inflates the one gzip member with a bound, reads the WARC `response` record strictly
   (`domain/deep_research/warc.py:153 @ 416733e`), checks it against its index row, and turns the
   body into a snapshot through `page_snapshot`, the path a live page takes. The snapshot carries an
   `ArchivedCapture` (crawl, capture date, WARC file, offset, length, record id, payload digest,
   `WARC-Truncated`) and an id of its own; it is never put in the run's snapshot cache, so it never
   answers a live fetch.

*When* an archived copy may be used is `decide_archive_use`'s (`domain/deep_research/archive.py`):
plan § 7 rung 9 allows it only for a dead, moved or changed page, never for a page live behind a
paywall. Since chunk 10 the gate enforces it: `fetch_archived` takes a required `permit`, and
`query_url_index` for one exact URL needs the permit for that URL; without it each is refused
before dispatch (`archive_not_permitted`) and journaled. A query by host or domain (discovery)
needs none. The acquisition ladder (`application/acquisition_ladder.py`) is the caller that
obtains the permit, from its own live attempt of the page.

## Residency and classification

- The index lives in `s3://commoncrawl/` in **us-east-1** (VERIFIED, below). Athena processes a
  query where the data is, so the query text leaves the EU. The statement is classified **as sent**
  (`classify_query` over the statement, in the caller's context class, with the client's terms and
  Class A texts): the host or URL in it is client-identifying when it names the client.
- The index route is a `ProviderRoute` with `zone=NON_EU` and `approved_for={CLASS_C_INTERNAL}`.
  `evaluate_egress` therefore refuses Class B (`route_not_approved_for_class`, or
  `residency_violation` even if someone approved the route for Class B) and the gate refuses Class
  A before egress (`class_a_query`). Tested: `test_common_crawl_gate.py::test_a_statement_written_from_client_material_never_leaves_the_eu`,
  `::test_a_client_s_name_in_the_host_raises_the_statement_and_it_is_refused`.
- The archive route (`data.commoncrawl.org`) is the same: NON_EU, Class C only. What is sent is the
  WARC file's path and a byte range, both taken from the public index.
- Athena writes each query's results to the workgroup's results bucket. Those results are index rows
  (public URLs and WARC locations): Class C. The bucket is in the account that runs the query, in
  `us-east-1` (see Human actions).

## Cost

- **Reserve the most a query can cost.** A query runs in a workgroup whose enforced
  `BytesScannedCutoffPerQuery` bounds its scan. The index route's `price_usd_per_call` must equal
  that cutoff billed at the configured price (`ArchiveRetrieval.__post_init__`,
  `web_retrieval.py:187 @ 416733e`); it is what every query reserves.
- **Settle on what it scanned.** The charge is `AthenaPricing.cost_usd(DataScannedInBytes)`
  (`common_crawl.py:358 @ 416733e`): the scan rounded up to the billing increment, at least the
  minimum, times the price per terabyte. The journal entry's `credits` is the bytes scanned.
- **Unknown is the ceiling.** A 5xx at start, a lost status answer or a timeout (after which the
  query is asked to stop) leaves the scan unknown: the call is journaled `UNCERTAIN` and charged
  the reservation. A 4xx at start scanned nothing. A `FAILED` or `CANCELLED` query is charged what it
  reports scanned. A scan beyond the cutoff is charged as reported, never capped in AIA's favour.
- **Charged to the study.** The route has a price, so the gate refuses it under a meter that
  cannot charge a study (`tool_metering_unavailable`; tested:
  `::test_a_paid_index_is_refused_while_tool_spend_cannot_be_charged_to_the_study`). The worker's
  `StepToolMeter` does charge one (#217): each query is held against the study's budget at the
  reservation before it starts, and the route needs its organization's sign-off (ADR 0022).
- **The price is configuration.** `common_crawl_settings` (`infrastructure/common_crawl.py:720 @ 416733e`)
  reads `AIA_DEEP_RESEARCH_COMMON_CRAWL_{WORKGROUP,DATABASE,TABLE,MAX_SCAN_BYTES,USD_PER_TB_SCANNED,MIN_BILLED_BYTES,BILLING_INCREMENT_BYTES,PRICES_AS_OF}`;
  every key is required and has no default. **Proposed** values for chunk 23, from an unverified
  source (below): `USD_PER_TB_SCANNED=5`, `MIN_BILLED_BYTES=10485760` (10 MB),
  `BILLING_INCREMENT_BYTES=1048576` (1 MB), `MAX_SCAN_BYTES` to be chosen with the owner once a
  representative query's scan is measured (chunk 25/27). Fetching from `data.commoncrawl.org` is
  priced 0 (proposed; Common Crawl's terms not yet recorded).

## The adapters

- `AthenaUrlIndex` (`infrastructure/common_crawl.py:278 @ 416733e`): `StartQueryExecution`
  (`QueryString`, a fresh `ClientRequestToken`, `WorkGroup`, `QueryExecutionContext.Database`; no
  `ResultConfiguration`: the workgroup enforces it), `GetQueryExecution` every second until a
  terminal state or the timeout, one page of `GetQueryResults` (`MaxResults` ≤ 1000). POST to
  `https://athena.us-east-1.amazonaws.com/` with `Content-Type: application/x-amz-json-1.1` and
  `X-Amz-Target: AmazonAthena.<Action>`, SigV4-signed for service `athena` by
  `InstanceRoleSigner(region="us-east-1", service="athena")` (instance or container role only). No
  boto3 client, no retry. **It has not been run against AWS.** It was written against botocore's
  Athena service model and is exercised offline over a scripted wire; chunk 27 is its first live use.
- `ArchiveRangeTransport` / `ArchiveFetcher` (`common_crawl.py:519`, `:584 @ 416733e`): HTTPS to the
  checked address of `data.commoncrawl.org` only, `Range: bytes=<offset>-<offset+length-1>`,
  `Accept-Encoding: identity`, the operator's contact in the user agent, one request at a time at
  least a second apart. Refused: a 200 (range ignored), another `Content-Range`, a short body, a gzip
  member that is cut, followed by more bytes or inflates past ~2.1 MB, a record that is not one
  `response` record, whose `Content-Length` disagrees, whose `sha1` payload digest does not match,
  whose body is still transfer- or content-encoded, whose target URI is not the row's URL, or whose
  archived status is not 2xx.
- Recorded doubles `RecordedUrlIndex` and `RecordedArchiveTransport` sit beside the adapters and are
  held to the recorded-retrieval rule in `tools/layer_check.sh`.

## Facts, and where they come from

The container that built this had no route to `commoncrawl.org`, `docs.aws.amazon.com` or
`aws.amazon.com`. Facts were read from the sources below; anything not read from a primary source is
UNVERIFIED and must be checked before chunk 27.

| Fact | Status | Source |
|---|---|---|
| Columnar index table: columns `url`, `url_host_name`, `url_host_registered_domain`, `url_path`, `url_query`, `fetch_time` (TIMESTAMP), `fetch_status` (SMALLINT), `content_digest`, `content_mime_type`, `content_mime_detected`, `content_languages`, `content_truncated`, `warc_filename`, `warc_record_offset` (INT), `warc_record_length` (INT), `warc_segment`; partitioned by `crawl`, `subset`; Parquet at `s3://commoncrawl/cc-index/table/cc-main/warc/` | VERIFIED | [cc-index-create-table-flat.sql](https://raw.githubusercontent.com/commoncrawl/cc-index-table/main/src/sql/athena/cc-index-create-table-flat.sql) |
| Athena setup: `CREATE DATABASE ccindex`, the create-table statement, `MSCK REPAIR TABLE ccindex` after new partitions; queries filter `crawl = 'CC-MAIN-…' AND subset = 'warc'` | VERIFIED | [cc-index-table README](https://raw.githubusercontent.com/commoncrawl/cc-index-table/main/README.md), [get-records-of-domain.sql](https://raw.githubusercontent.com/commoncrawl/cc-index-table/main/src/sql/examples/cc-index/get-records-of-domain.sql) |
| The `commoncrawl` bucket is in `us-east-1` | VERIFIED | [AWS Open Data Registry, commoncrawl.yaml](https://raw.githubusercontent.com/awslabs/open-data-registry/main/datasets/commoncrawl.yaml) |
| A record is fetched by `Range: bytes=<offset>-<offset+length-1>` from `https://data.commoncrawl.org/<warc_filename>` (HTTP 206), or from `s3://commoncrawl/` | VERIFIED | [cc-pyspark `sparkcc.py`](https://raw.githubusercontent.com/commoncrawl/cc-pyspark/main/sparkcc.py) |
| WARC grammar (`WARC/1.1` CRLF, named fields, CRLF, block, CRLF CRLF), mandatory `Content-Length`, `WARC-Date` UTC W3C-ISO8601, `WARC-Payload-Digest` labelled (e.g. `sha1:` Base32) over the entity body; record-at-time gzip compression, each record its own member | VERIFIED | [WARC 1.1 specification](https://raw.githubusercontent.com/iipc/warc-specifications/master/specifications/warc-format/warc-1.1/index.md) |
| Athena JSON protocol 1.1, target prefix `AmazonAthena`, endpoint prefix `athena`, SigV4; `StartQueryExecution` requires only `QueryString`, `ClientRequestToken` is an idempotency token that callers outside an SDK must supply; `QueryExecutionState` ∈ QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELLED; `Statistics.DataScannedInBytes` (Long); `GetQueryResults.MaxResults` 1–1000; `BytesScannedCutoffPerQuery` ≥ 10,000,000 | VERIFIED | [botocore Athena service model](https://raw.githubusercontent.com/boto/botocore/develop/botocore/data/athena/2017-05-18/service-2.json) |
| Endpoint `https://athena.{Region}.amazonaws.com` | VERIFIED | [botocore Athena endpoint rule set](https://raw.githubusercontent.com/boto/botocore/develop/botocore/data/athena/2017-05-18/endpoint-rule-set-1.json) |
| JSON-protocol headers `X-Amz-Target: <prefix>.<Action>`, `Content-Type: application/x-amz-json-<version>` | VERIFIED | [botocore `serialize.py`](https://raw.githubusercontent.com/boto/botocore/develop/botocore/serialize.py) |
| Athena price $5 per TB scanned, rounded up to the nearest MB, 10 MB minimum per query | UNVERIFIED (search-result summary of aws.amazon.com/athena/pricing; page not reachable) | — |
| A TB in Athena's price is 10^12 bytes (the code's assumption) | UNVERIFIED | — |
| Cancelled queries (including a cutoff cancellation) are billed for the data scanned; DDL and failed queries are not | UNVERIFIED | — |
| `GetQueryResults` repeats the column names as the first row of a SELECT's first page | UNVERIFIED (the adapter drops a first row equal to the column names, and only then) | — |
| `fetch_time` comes back from Athena as `YYYY-MM-DD HH:MM:SS.fff` | UNVERIFIED (the parser also accepts `T`, `Z` and ` UTC`; anything else is refused) | — |
| Common Crawl's response records carry an identity-encoded body (the crawler's original `Content-Encoding`/`Transfer-Encoding` kept under other header names) and a `WARC-Payload-Digest` over that body | UNVERIFIED (a record that disagrees is refused, `archive_body_encoded` / `archive_digest_mismatch`: the first suspects if live records are refused) | — |
| `data.commoncrawl.org`'s terms, rate guidance and cost to the reader | UNVERIFIED (one request at a time, ≥ 1 s apart, until recorded) | — |
| Athena needs Glue Data Catalog permissions (`glue:GetDatabase`, `GetTable`, `GetPartitions`) for the `ccindex` table | UNVERIFIED | — |

## Human actions (nothing here is applied)

The develop Terraform root is EU-only by validation (`infra/develop/variables.tf:7`), and this
route places resources in `us-east-1`; that is a residency decision for the owner, not a chunk's,
so no Terraform is added. What an operator would create, once approved:

1. A results bucket in `us-east-1`, private, encrypted, with a short lifecycle expiry (results are
   Class C index rows; 7 days proposed).
2. An Athena workgroup in `us-east-1` with **enforced** configuration: that results location,
   encryption, and `BytesScannedCutoffPerQuery` equal to `AIA_DEEP_RESEARCH_COMMON_CRAWL_MAX_SCAN_BYTES`.
3. The `ccindex` database and table from the flat create-table statement, and `MSCK REPAIR TABLE`
   after each new crawl.
4. On the develop instance role, scoped to those: `athena:StartQueryExecution`,
   `GetQueryExecution`, `GetQueryResults`, `StopQueryExecution` on that workgroup; `glue:GetDatabase`,
   `GetTable`, `GetPartitions` on the `ccindex` catalog objects; `s3:GetObject` and `s3:ListBucket`
   on `arn:aws:s3:::commoncrawl` limited to `cc-index/table/cc-main/warc/*`; `s3:GetBucketLocation`,
   `GetObject`, `PutObject`, `ListBucket`, `AbortMultipartUpload` on the results bucket.
5. Record Athena's price and its date, and Common Crawl's terms of use for `data.commoncrawl.org`,
   in plan § 13 (chunk 1's sign-off).
