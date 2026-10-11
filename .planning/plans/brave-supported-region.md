---
status: done
chunks:
  - "[x] 1. Correct unsupported country and version the Brave adapter"
  - "[x] 2. Verify and deploy the correction, then complete the live sandbox report"
---
# Brave supported search region

The first authorized broader-search sandbox test rejected every web-search request as bad_request. The deployed adapter hardcodes country=CZ, absent from Brave's official GET search country enum verified 2026-10-10 at https://api-dashboard.search.brave.com/api-reference/web/search/get. Use the documented ALL region, keeping cs/en language selection, strict safe search, checked address/TLS transport, cost reservations and admission rules. Version the adapter to brave-web-search-2 so the runtime track identity cannot reuse the failed source route. Run start is still idempotent for the same frozen specification: it returns the cancelled predecessor. DeepResearchRuns.retry re-freezes current approvals and the same target into a new run; use that retry for this test. Adapter versioning changes track reuse independently of run specification identity. Anchor: DeepResearchRuns.retry and the actual live completion receipt below.

Stop faulty paid work before fixing. RUN-e14bcf6920f44a0a was cancelled from the actual AIA results UI; no fieldwork rerun. Keep the existing expiring study-only approval, organization settings, provider permission attestation and hard USD 20 total guard. Full required CI must verify the merged SHA before release. Then retry the cancelled QUICK interpretation review via the results UI, inspect its sealed accepted evidence and actual search ledger, download the contextual AIA report, verify retained prose/canonical sociomap provenance, and render/visually inspect every page before delivery.

Regression verification uses a transport that rejects unsupported regions with the provider's 422 response and admits both Czech and English search in ALL. No real network or provider credentials in tests.

Focused adapter and live-composition route tests: 113 passed, including both supported-language regression cases. Ruff, planning validation and whitespace checks passed.

## Live completion receipt — 11 October 2026

The real results UI completed interpretation review RUN-64e83e1e07f54d29 over
frozen study results RUN-1725024c5b8b480a: seven successful Brave searches, seven
successful reads of eleven attempted sources, six accepted findings, three
quarantined findings and seven captured source snapshots. Origins are exclusively
LIVE_RETRIEVAL; the sealed bundle is
`afeff197b5c0abeecd687819c965d9409084af506575f41817328580e8d18d1d`.
Academic library-service-quality and library-trust research was admitted; no
comparable attractiveness benchmark was established. The review cost USD
0.7703786. Settled study spend is USD 12.7145247, leaving USD 7.2854753 of the
unchanged USD 20 total cap. No fieldwork, analysis or map was rerun.

The source-publication release merged as `5e0fe65d039bf3aa1e6160eea01c784b2665bb3c`, passed exact merged CI
`38127433049` and deployment `38128554168`. API and worker build identity and the actual
results UI download were verified. The 25-page AIA-branded Word export preserves
all 37 original analysis passages, all six accepted source claims, references and
both canonical top-down/3D sociomap snapshots; every page was rendered and checked.
Word SHA-256: `ad72e94906264f73bcdbd23fa0b2f181283854714e02fa07d8ae624de35fb72a`. Unsupported generated inapplicability prose and the
withheld technical title marker are absent; the raw sealed interpretation remains
an explicitly unapproved draft in AIA.

The one-day test approval remains limited to the fictional client and study and
expires at 2026-10-11T21:31:07.527531+00:00. All 26 organization-wide requirements
remain missing. Provider email permission is owner-attested for testing, not a
verified permanent agreement. No broader organization approval or new subscription
was applied.
