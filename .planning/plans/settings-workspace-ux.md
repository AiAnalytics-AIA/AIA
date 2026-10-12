---
status: in-progress
chunks:
  - "[x] 1. Audit every live tab and introduce clear task-based navigation and setting explanations"
  - "[x] 2. Rebuild Methodology browsing/editing with focused sections, plain-language guidance and protected drafts"
  - "[x] 3. Upgrade AI, research policy, access, budgets, audit and reference usability"
  - "[ ] 4. Verify all tabs and editing journeys across desktop/tablet/phone, integrate and deploy"
---
# Pleasant settings workspace

User request: upgrade every settings tab, clarify what settings do and how they can be edited, especially methodology.

Baseline ca56fd00: live Methodology is a 13,367px stream of formulas, provenance, version management and raw editing fields. Deep Research mixes code reference rows with policy controls. Study costs display unrounded floating-point values. Shared setting rows show source paths prominently but provide no purpose. Access and audit use wide dense tables. Inspect every current API-backed tab; preserve organization/study scope, immutable methodology/prompt versions, server validation and approval rules.

Design: descriptive grouped settings navigation, useful per-tab introductions, clear editable/managed-in-deployment/fixed distinctions, search where catalogues are large. Methodology gets searchable module navigation and focused grouped steps, readable values, optional technical details, clear preview versus in-force state, and an editor with check/compare/save/activate workflow and draft guards. Apply source metadata rather than inventing switches for uneditable code settings. No live policy or methodology changes during UX testing.

Verification: existing contracts/unit tests plus real local browser → API → stored settings journeys using fictional identities. Test editable roles, invalid fields, version save vs activation, replacement guards, search/filter, hash navigation, responsive overflow and preserved edits when moving between settings. Read-only live acceptance after all required CI and deployment checks.

Doc follow-up: new settings navigation/explanation map and the browser acceptance command, with any reproducible defects anchored to tests. Shared docs stay out of this feature PR.

Chunk 1: live audit of all eight tabs completed. Descriptive responsive navigation, per-tab action guidance, purpose text for catalogued settings, optional technical sources, readable control ownership and rounded display-only USD amounts implemented. ControlPanel: 28 tests pass; frontend types/lint pass. Unknown future setting names now remain readable instead of exposing translation keys.

Chunk 2: Methodology module/step search, grouped disclosure browsing, clearly labelled code documentation versus active versions, section-focused parameter editing, original-value/change summaries, optional expert formula controls, stale-check invalidation, locked inputs during requests, preset/cancel/module/navigation draft guards. Methodology: 21 tests pass; frontend types/lint pass. Existing immutable version, compare, validation and activation contracts are preserved.

Chunk 3: research policy purpose search/filter, group descriptions, scoped approvals/readiness, protected/pinned drafts and locked approval during editing; member name/role editing through the existing audited upsert API (scope_repository.py add_member), new members default MEMBER; study search retains budget inputs; readable/searchable audit; expandable/searchable reference, optional runtime metadata and all existing immutable controls preserved. 60 affected tests pass. Full frontend: 53 files / 1125 tests pass; TypeScript, lint, production build, Python lint/format and structural/design checks pass.

Local production browser acceptance: eight tabs and seven complete API journeys passed, including 48 desktop/tablet/phone layout assertions, member update persistence, exact-study budget saving, draft retention, policy propose/approve/withdraw, methodology domain rejection/compare, protected replacements, refused-save retry, separate activation, reload and reset. Zero page errors and zero paid jobs. Default methodology panel height decreased from the observed live 13,367px to 2,678px locally. Verify technical disclosures as well before release.

Local backend gates remain unchanged: core 5758 pass / 104 environment skips / existing macOS exact-float fixture failure; API 395 pass; worker 54 pass / 8 PostgreSQL skips; executors 427 pass / 2 skips / three macOS GNU mv -T failures. make verify stops at three unchanged ai_respondent.create_model typing errors with installed mypy/Pydantic. Domain/backend files have no feature diff; preserve the signal and require all Linux/PostgreSQL CI gates before integration/deployment.

Review map: settings presentation/navigation/explanation catalogue; existing audited member/status/budget/policy APIs; methodology read/immutable propose/check/compare/activate flows. No domain math, backend policy, database schema, provider credentials or frozen results change. Tests cover UI contracts and local browser acceptance records the real API path.

Final local production browser journey: 52 layout assertions including expanded formula/provenance details pass; seven complete settings journeys, zero page errors and zero paid jobs. Technical text wraps and comparison tables scroll inside their panels. Full frontend remains 1125 passing; current production build and lint pass. Screenshot captures reviewed for reader/editor, policy and access pages.
