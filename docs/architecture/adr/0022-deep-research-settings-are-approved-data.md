# ADR 0022 — Deep Research's policy values are data an Admin approves; switches, secrets and routes stay in the deployment

**Status:** Proposed — develop (2026-10-07). To be implemented as
[`deep-research-web-search.md`](../../../.planning/plans/deep-research-web-search.md) chunks 40–44.
**Takes up** what [ADR 0020](0020-runtime-editable-system-prompts.md) left undecided ("a database
row overriding that guard is a different decision"), for Deep Research's policy values only.
**Builds on** ADR 0020 (immutable versions, append-only activations, a pin at enqueue, audit),
[ADR 0019](0019-two-roles-and-human-ai-gates.md) (system settings are the Admin's; no approval
between people), [ADR 0021](0021-deep-research-purpose-target-lineage.md) (the frozen engine; a
method change moves the reuse identity) and [ADR 0010](0010-bedrock-eu-inference-route.md) (the
model route).
**Date:** 2026-10-07

## Context

Deep Research cannot go live until the data owner signs off a list of decisions (plan chunk 1):

- the search provider's terms and price;
- budgets and caps per preset;
- the lead's and the light model's policy entries;
- quotas;
- snapshot and dataset retention;
- the source tiers, the reputation register and the confidence weights;
- for extraction (chunks 33–39): the host denylist, the personal-data rules, the inventory caps
  and the record presets.

Today the sign-off is "recorded in § 13 with a date", and none has been.

Where those values live today:
- **Code constants, marked proposed:** the presets (`planning.PRESETS`, `PRESET_STATUS =
  "PROPOSED_DR5"`), the route allowances (`budgets.ROUTE_ALLOWANCES`), the request limits
  (`request_limits.REQUEST_LIMITS`), the register (`reputation.REPUTATION_REGISTER_V1`, PROPOSED)
  and the confidence weights (PROPOSED).
- **Nowhere:** the denylist, the retention periods, the search price and the light model's entry.

Changing any of them means a branch, CI and a deploy, and nothing records who approved a value
or when.

The owner asked for these decisions on a Deep Research settings page, so that building can go on
and the values can be filled in later. Approved values are what runs. The worker reads only its
environment when it starts, and the database only for fan-out coordination.

## Decision

1. **Three homes, by kind of value.**

   | Kind | Examples | Home |
   |---|---|---|
   | Switches, secrets, routes | `AIA_DEEP_RESEARCH_*` switches, the Brave key (a credential reference, D8), the Bedrock route, its prices and approvals (ADR 0010) | the deployment (environment / SSM), read at start, unchanged |
   | Rails | `robots.txt` obeyed, no logins or barriers, the personal-data screen on, Class C only, grounding, the gate | code; never a setting |
   | Policy values | provider terms and price, presets and caps, request limits, retention, register and weights status, denylist, personal-data patterns, record presets | **settings an Admin approves**, this ADR |

   A setting can never switch a rail off. The personal-data screen, for example, takes
   additional patterns and cannot be disabled. A secret is never stored: the page shows whether
   its credential reference is configured, and nothing more.

2. **A code-owned catalogue.** `aia_core.domain.deep_research.settings` (pure) lists every
   setting:
   - its key, group and type: integer, money with currency, days, URL, date, text, host list, a
     per-preset table, or a status;
   - its unit and bounds;
   - its **proposed default**: today's constant, so storing nothing changes nothing;
   - whether it is **required for live**.

   Only catalogued keys can be stored. Every value is validated by code against the type and
   bounds. A cap, for instance, can be lowered below the code's ceiling and never raised above it.

3. **A value is an immutable version; what is in force is an append-only approval.** This is
   ADR 0020's shape:
   - `deep_research_setting_versions` holds versions, numbered per organization and key, never
     updated. Each records the value, the source (a terms URL, a document), a note, and who
     proposed it and when.
   - `deep_research_setting_approvals` holds approvals: newest row wins; `NULL` means the
     proposed default.
   - Approving and withdrawing are an Admin's acts (`require_administer`). The organization's
     self-approval setting decides whether the proposer may approve their own version, as for
     prompts.
   - Every change writes an `access_audit` row in its own transaction.

4. **A run pins its settings at enqueue.**
   - `DeepResearchRuns` resolves the effective settings once, at enqueue: each approved value,
     else its proposed default, each labelled with its origin.
   - It stores them on the run with their digest, beside the run spec (ADR 0021).
   - The steps read the pin and never ask what is in force now, so an approval changes only runs
     enqueued afterwards.
   - A pin that does not hash to its own content fails the run closed.
   - The worker still reads no settings from the database.

5. **Settings that shape the method are part of reuse identity.**
   - The digest of the method-shaping settings enters every reuse key that crosses runs: track,
     verification, synthesis, brief and, later, the dataset. Those settings are the presets, the
     caps, the request limits, the register and the weights.
   - So a changed cap or limit never reuses work made under the old one. Wiring this moves the
     harness once, to 3, as ADR 0021 decision 7 requires for a method change.
   - Settings that do not shape a result do not move any key: the provider's price, retention,
     a terms URL.

6. **Live needs approval; offline does not.**
   - A composition with a live route (chunk 27), and the start of a run that would use one,
     refuse unless every setting required for live is APPROVED. The refusal names each missing
     setting.
   - Recorded and offline runs use the effective values and label proposed ones as proposed.
     That is how development continues before the sign-off.
   - Chunk 1 becomes "every required setting approved on the page", with the record kept in the
     settings' history rather than in a plan's prose.

7. **The route is organization-level, and the page is a Settings tab.**
   - `/api/v1/deep-research/settings` covers the catalogue with effective values and origins, a
     setting's history, proposing a version, approving and withdrawing. It takes an
     `OrganizationContext`, which carries no client or study and reads no research data.
   - The Settings document gains a Deep Research group, and an `ai_runtime` activity whose
     switches read as configured or off, never "connected".
   - The page shows a live-readiness list: what live still needs approved.

8. **The API's cost ceiling reads the same effective values.** Prices that are settings, caps and
   presets come from the same resolution the run pins. The Bedrock route's prices stay in the
   deployment (decision 1).

## Not decided here

- Editing the model route, its prices or its approvals from the page (ADR 0010; still the
  deployment).
- Per-client or per-study settings: these are organization policy.
- Storing a secret in the database.
- Which values to approve. That is the sign-off itself (chunk 1), made on the page.

## Consequences

- The sign-off becomes something done in the product, attributable and dated, and development
  continues on the proposed defaults in the meantime.
- **The cost:** a policy value now has two homes, the code's proposed default and the approved
  database row. The page always shows which one is in force for every setting.
- The engine reads pinned settings where it read constants. That is a method-identity change made
  once (harness 3) and verified by an old-pin / new-pin reuse test, like harness 2's.
- `CLAUDE.md` and `deep-research.md` gain the settings module, the tables, the route and the tab
  when chunks 40–44 land (their Doc follow-up).

## Revisit when

A production deployment needs these values per environment rather than per organization, a
second engine needs policy settings, or the model route itself must be editable live.
