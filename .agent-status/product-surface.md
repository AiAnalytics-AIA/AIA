# product-surface (A9)

**STATUS: ACTIVE. Chunks 0–3 are stacked PRs; slice V (#24) is merged into #21's branch.
The slice is waiting for review; chunks 4–11 will not start until it has been reviewed.**
Cloud session. PostgreSQL 16 and Python 3.12 were provisioned in-session, with
Node 22.22.2 for the web client. Every number below was measured here.

## Mission

Turn the accepted AIA design direction into repository material. Then put a real
slice of the product in front of reviewers: Portfolio → Client → Study → Project
workflow state → human action, on the real API. Where the API cannot serve a
capability, say so on screen.

## PR stack (base ← head)

| PR | Branch | What | CI observed |
|---|---|---|---|
| #15 | `claude/determined-clarke-q6002c` → main | Planning: DS-1/2/3, the integration principle, and the chunk order | no checks reported |
| #16 | `feature/web-vocabulary` | Chunk 0: domain vocabulary, 13-stage lifecycles | green at last check |
| #17 | `feature/design-tokens` | Chunk 1: `tokens.json` → css/ts, themes, fonts, identity, contrast checks | green at last check |
| #18 | `feature/enum-binding` | Chunk 2: exhaustive `Record<>` maps + `make enum_check` in CI | green at last check |
| #21 | `feature/web-primitives` | Chunk 3: Vitest and the primitives, plus slice V since #24 merged in | green on 8f51488 (all 6 checks), after the CI Node 20 → 22 fix. The #24 merge moved the head; CI on the new head not re-checked yet |
| #24 | `feature/web-first-slice` → `feature/web-primitives` | Chunk V: the slice on the real API | **merged** into `feature/web-primitives`; all 6 checks green on bc94266 |

## Slice V: observed state

- Pages read the API server-side through `apps/web/src/lib/api/`. Responses are
  shape-checked. Failures render as error panels. Nothing falls back to fixture data.
- Local evidence:
  - 170 Vitest tests pass;
  - `make verify` passes (769 passed, 136 skipped because they need PostgreSQL);
  - `check:layout` at +35 % Czech: 6 real routes × 2 widths, 0 overflows;
  - screenshots checked in light, dark and greyscale, and in the unauthenticated and API-unreachable states.
- Fixture-backed capabilities: **2** (stage artifacts, report draft), down from 5.
- Unavailable capabilities: **7**, each with an owner and a register entry. The list is
  `UNAVAILABLE_CAPABILITIES` in `src/fixtures/registry.ts`.
- `make dev-seed` provisions a local world through the real authorisation path.

## Requests to other agents (each is an entry in `.planning/open-items.md`)

**integration-architecture**
- **OI-12: `clients.accent_slot`. This is the notice required before the migration lands.**
  - The contract: a smallint 1–6, assigned server-side by least-used at client creation, immutable.
  - It is never chosen by browser input. It is a presentation cue only: not a
    security boundary, not an identifier, not globally unique.
  - The migration is **held** until you acknowledge. The web client uses a labelled
    hash fallback until then.
- **OI-10: `ImpactPreviewEstimate`.** The cost and duration of re-running the invalidated
  stages. The UI shows both as missing and will not compute them.
- **OI-11: viewer actionability ("what needs me").** Suggested per-item fields:
  `action_required`, `action_kind`, `viewer_can_resolve`, `required_permission`,
  `waiting_reason`. The exact shape is your decision. The UI shows raw state and never assigns an
  item to the viewer.
- **OI-13: finding.** `GET …/impact?field=<unknown>` answers 200 with "nothing
  invalidated". The smallest fix is a 422 `unknown_field` in the route.
- **OI-14: the token contract for web sign-in.** The web client has a development identity only.

**platform-runtime**
- **OI-15: read routes are needed, in this order:**
  1. runs, steps and attempts (status, failure class, retry-at);
  2. pending gates, with the permission that resolves each one (this also feeds OI-11);
  3. a study's reservations and spend;
  4. then the approval write.

  Also: the study *list* route returns `your_role: null` and no costs, so the portfolio makes one
  call per study.

**analysis-governance (A6)**
- **OI-9: publish the evidence-role enum in `aia_core.domain`.** It then joins
  `make enum_check`. Until it exists, an unknown role renders "?" and is never
  treated as measured.

## Not owned here

Research computation, population policy, evidence policy, budget calculation,
provider fallback, approval authorization, Sociomapping math.

## Next

1. The slice now reaches main through #21 → #18 → #17 → #16 → #15; review the stack.
2. Drive #21 and #24 to green CI.
3. Once OI-12 is acknowledged, run chunk 4 (scope chrome + the `accent_slot` migration).
