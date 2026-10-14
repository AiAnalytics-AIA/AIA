# AIA Settings · contextual UX (S1)

Variant: `ui_kits/aia-develop/contextual-ux/Settings Context.dc.html`
Baseline: `ui_kits/aia-develop/AIA Develop Settings.dc.html` (unchanged).

Fictional examples only. The methodology structure comes from the repo fixture `apps/web/src/lib/fixtures/methodology.json`, extracted into `contextual-ux/methodology-data.js`; versions, people, studies and audit events are fictional. The prototype simulates the server. Use the Tweaks to see each state:
- `serverScenario`: ok / saveFails / refused
- `role`: admin / member
- `dataState`: ready / loading / empty / error
- `theme`: light / dark

## Foundation preserved
- Tokens (light and dark) copied verbatim from the baseline. Settings controls use `--signal`; the AI accent (`--ai #a3319a`) is left untouched.
- IBM Plex fonts, AIA logo, `support.js` runtime.
- The tab IDs and hash links `ai`, `prompts`, `deep_research`, `methodology`, `access`, `studies`, `audit` and `reference` are kept. Navigation updates the hash, and the browser back/forward buttons work.

## Change manifest

**1. Grouped navigation**
- Three groups: Nastavení výzkumu / Tým a útrata / Provoz.
- Each tab header shows its purpose plus scope and ownership facts.
- There are at most two side columns; the choosers inside tabs are inline.

**2. Metodika**
- **Module chooser:** grouped by purpose, with an editable / read-only tag, the version in force and a draft marker.
  - Editable: sociomap, support, aggregation, response.
  - Read-only: sociomap_reference, sociomapping, weighting (no edit controls at all).
- **Hierarchy:** module.groups → step_ids → values, with formulas as expert slots. A select groups blocks per group, with prev/next buttons and change/problem counts in the options.
- **Selected block:** readable formula and note above the fields; original value and changed marker under each field. Expert expressions, variables, provenance and tests sit in a collapsible section.
- **Drafts:** one per module, persisted. Changed count is shown. Replacing a dirty draft needs confirmation.
- **Check and compare:** local parse errors appear first, then the server check. A summary links to the affected blocks. Any edit invalidates check and compare. The comparison appears only after the server returns, with no causal claims.
- **Save and activate:** saving creates an immutable version. Activation is separate, needs a reason, and applies only to future runs; existing runs keep their pins.

**3. Systémové prompty**
- Searchable agent chooser.
- Active / working / stored cards.
- Full text kept per version.
- Save is separate from activation (with confirmation).
- Declaration and data-class approval explained.

**4. Deep Research**
- Readiness check linking to missing approvals.
- Categorised rules showing the effective value with its origin, and any proposals.
- Propose with validation (lower-only caps, https source), approve with reason, history.
- Nothing becomes effective until the server acknowledges.

**5. AI běh**
- Deployment values are read-only.
- The tab states that a switch is not a verified connection or grant.

**6. Přístup a schvalování**
- Members with server-evaluated approval eligibility.
- Client state.
- Scoped approvals.

**7. Studie a rozpočty**
- Client/study search.
- Budget, spent, reserved and remaining for each study.
- Unknown cost is shown as unknown, never as 0.
- The budget cannot be set below the amount already spent.
- Save outcome, with failure and retry.

**8. Audit**
- Filters for person, event and reason.
- Readable sentences, with technical JSON optional.
- Read-only.

**9. Reference**
- Purpose search.
- Ownership (code invariant / deployment / organisation) and where each item changes.
- No switches.

**10. States**
- Loading, empty and error.
- Busy buttons disabled (no duplicate submits).
- Save failure with explicit retry.
- Server refusal (403) changes nothing.
- Read-only member role.

## Files
- `contextual-ux/Settings Context.dc.html` (new)
- `contextual-ux/methodology-data.js` (new, generated from the repo fixture)
- `exports/contextual-settings/design-contract.json`
- `exports/contextual-settings/component-layouts.html` (loads `/styles.css`, with a light/dark toggle)
- `exports/contextual-settings/README.md`

## Simulated server rules (prototype only)
- The check refuses negative numbers.
- Deep Research rejects values above lower-only caps.
- Budgets below spend are rejected.

The real rules come from the API's check responses.
