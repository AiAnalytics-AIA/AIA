---
status: in-progress
chunks:
  - "[x] 1. Correct unsupported country and version the Brave adapter"
  - "[ ] 2. Verify and deploy the correction, then complete the live sandbox report"
---
# Brave supported search region

The first authorized broader-search sandbox test rejected every web-search request as bad_request. The deployed adapter hardcodes country=CZ, absent from Brave's official GET search country enum verified 2026-10-10 at https://api-dashboard.search.brave.com/api-reference/web/search/get. Use the documented ALL region, keeping cs/en language selection, strict safe search, checked address/TLS transport, cost reservations and admission rules. Version the adapter to brave-web-search-2 so a changed source method cannot reuse the failed run. Never retry the cancelled run with its frozen method pin.

Stop faulty paid work before fixing. RUN-e14bcf6920f44a0a was cancelled from the actual AIA results UI; no fieldwork rerun. Keep the existing expiring study-only approval, organization settings, provider permission attestation and hard USD 20 total guard. Full required CI must verify the merged SHA before release. Then start a fresh QUICK interpretation review via the results UI, inspect its sealed accepted evidence and actual search ledger, download the contextual AIA report, verify retained prose/canonical sociomap provenance, and render/visually inspect every page before delivery.

Regression verification uses a transport that rejects unsupported regions with the provider's 422 response and admits both Czech and English search in ALL. No real network or provider credentials in tests.

Focused adapter and live-composition route tests: 113 passed, including both supported-language regression cases. Ruff, planning validation and whitespace checks passed.
