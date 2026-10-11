---
status: done
chunks:
  - "[x] 1. Add audited expiring approvals limited to one fictional study"
  - "[x] 2. Verify scope expiry withdrawal and independent review"
  - "[x] 3. Publish and test broader retrieval within the USD 20 sandbox"
---
# Study scoped Deep Research testing

The user declined organization-wide approvals and explicitly restricted the proposed test configuration to the existing fictional sandbox. They report email permission from the search provider to test while the general agreement remains pending. Organization settings must remain unchanged. Implement a separate immutable test-policy proposal and append-only approval log, resolved only through the exact study and client in local/test/develop, with the existing fictional-client allowlist, an explicit provider-permission note, an expiry of at most seven days, and a study budget no greater than USD 20. The operator will select a one-day authorization. Preserve the existing organization independent-review policy, setting catalogue validation, per-call spend reservations, query classification, robots rules and source admission. Later settings changes, expiry, revocation or a larger budget refuse new test jobs; already enqueued runs retain their frozen settings as existing policy approvals do.

No API request can supply an approval or provider prices. Organization admins propose and approve through the existing repository operator seam; both operations create access audit records. Run metadata carries the exact policy and approval receipt alongside its settings pin. A new nullable-free table pair requires a reversible additive migration. Organization readers and all other studies retain their existing settings. The test grant must not imply a permanent provider agreement or silently approve client materials.

## Verification

Twenty-three focused policy tests pass, including paid enqueue refusal before approval and after withdrawal; other-study isolation, immutable run pins, exact authority receipts, independent-review enforcement, expiry, environment and budget guards, malformed proposals and tamper refusal. Existing settings tests pass (31 tests). Full core type checking passes (248 files), layering and exposure checks pass. The additive migration upgrades, reports no metadata drift, downgrades to the prior head, and upgrades again on a temporary SQLite copy of the previous schema. The pre-existing entire SQLite migration chain cannot bootstrap access_audit cleanly; this verification isolates the new migration rather than altering an unrelated historical migration. PostgreSQL migration verification remains required in CI.

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
