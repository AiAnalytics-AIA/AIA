---
status: in-progress
chunks:
  - "[x] 1. Add audited expiring approvals limited to one fictional study"
  - "[x] 2. Verify scope expiry withdrawal and independent review"
  - "[ ] 3. Publish and test broader retrieval within the USD 20 sandbox"
---
# Study scoped Deep Research testing

The user declined organization-wide approvals and explicitly restricted the proposed test configuration to the existing fictional sandbox. They report email permission from the search provider to test while the general agreement remains pending. Organization settings must remain unchanged. Implement a separate immutable test-policy proposal and append-only approval log, resolved only through the exact study and client in local/test/develop, with the existing fictional-client allowlist, an explicit provider-permission note, an expiry of at most seven days, and a study budget no greater than USD 20. The operator will select a one-day authorization. Preserve the existing organization independent-review policy, setting catalogue validation, per-call spend reservations, query classification, robots rules and source admission. Later settings changes, expiry, revocation or a larger budget refuse new test jobs; already enqueued runs retain their frozen settings as existing policy approvals do.

No API request can supply an approval or provider prices. Organization admins propose and approve through the existing repository operator seam; both operations create access audit records. Run metadata carries the exact policy and approval receipt alongside its settings pin. A new nullable-free table pair requires a reversible additive migration. Organization readers and all other studies retain their existing settings. The test grant must not imply a permanent provider agreement or silently approve client materials.

## Verification

Twenty-three focused policy tests pass, including paid enqueue refusal before approval and after withdrawal; other-study isolation, immutable run pins, exact authority receipts, independent-review enforcement, expiry, environment and budget guards, malformed proposals and tamper refusal. Existing settings tests pass (31 tests). Full core type checking passes (248 files), layering and exposure checks pass. The additive migration upgrades, reports no metadata drift, downgrades to the prior head, and upgrades again on a temporary SQLite copy of the previous schema. The pre-existing entire SQLite migration chain cannot bootstrap access_audit cleanly; this verification isolates the new migration rather than altering an unrelated historical migration. PostgreSQL migration verification remains required in CI.
