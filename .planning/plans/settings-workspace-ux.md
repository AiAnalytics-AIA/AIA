---
status: in-progress
chunks:
  - "[x] 1. Audit every live tab and introduce clear task-based navigation and setting explanations"
  - "[ ] 2. Rebuild Methodology browsing/editing with focused sections, plain-language guidance and protected drafts"
  - "[ ] 3. Upgrade AI, research policy, access, budgets, audit and reference usability"
  - "[ ] 4. Verify all tabs and editing journeys across desktop/tablet/phone, integrate and deploy"
---
# Pleasant settings workspace

User request: upgrade every settings tab, clarify what settings do and how they can be edited, especially methodology.

Baseline ca56fd00: live Methodology is a 13,367px stream of formulas, provenance, version management and raw editing fields. Deep Research mixes code reference rows with policy controls. Study costs display unrounded floating-point values. Shared setting rows show source paths prominently but provide no purpose. Access and audit use wide dense tables. Inspect every current API-backed tab; preserve organization/study scope, immutable methodology/prompt versions, server validation and approval rules.

Design: descriptive grouped settings navigation, useful per-tab introductions, clear editable/managed-in-deployment/fixed distinctions, search where catalogues are large. Methodology gets searchable module navigation and focused grouped steps, readable values, optional technical details, clear preview versus in-force state, and an editor with check/compare/save/activate workflow and draft guards. Apply source metadata rather than inventing switches for uneditable code settings. No live policy or methodology changes during UX testing.

Verification: existing contracts/unit tests plus real local browser → API → stored settings journeys using fictional identities. Test editable roles, invalid fields, version save vs activation, replacement guards, search/filter, hash navigation, responsive overflow and preserved edits when moving between settings. Read-only live acceptance after all required CI and deployment checks.

Doc follow-up: new settings navigation/explanation map and the browser acceptance command, with any reproducible defects anchored to tests. Shared docs stay out of this feature PR.

Chunk 1: live audit of all eight tabs completed. Descriptive responsive navigation, per-tab action guidance, purpose text for catalogued settings, optional technical sources, readable control ownership and rounded display-only USD amounts implemented. ControlPanel: 28 tests pass; frontend types/lint pass. Unknown future setting names now remain readable instead of exposing translation keys.
