# Plan: AIA design system → apps/web

**Status:** direction accepted; decisions DS-1, DS-2 and DS-3 resolved (below). Chunks 0–3 in review; the first vertical slice next. **Owner:** product-surface (A9).
**Brief:** [`docs/design/aia-design-system-brief.md`](../../docs/design/aia-design-system-brief.md).
**Design source:** the "AIA Design System" artifact, https://claude.ai/artifact/LB7SgQGTiynynHZNEXgqBy (private to its owner until shared).

Anchors below are against `main` @ 0d4c51d unless stated.

## Integration principle — the artifact is a design source, not a dependency

The Claude Design artifact is where the system was designed and reviewed. It is
**not** a production dependency. Everything the product needs becomes durable
repository material, under review like any other code:

- tokens (`apps/web/src/design/tokens.json`, the one source) and the generator that
  emits `tokens.css` and `tokens.ts` — the artifact page's own generated `tokens.css`
  is never used;
- identity assets (mark, wordmark, lockup, favicons) as files under `apps/web/public/`;
- component specs as code: components plus their tests, not screenshots;
- fonts as woff2 files with their licence texts (SIL OFL 1.1 for IBM Plex and
  Source Serif 4);
- state mappings (`enums.ts`, `status.ts`, `evidence.ts`) and their parity check;
- the accessibility checks (contrast, chart palette, +35 % Czech stress) as scripts
  that run in the repository.

**`apps/web` never requires the claude.ai artifact at runtime or in CI.** A build
that fetches from it is a defect. When the design changes, the change is ported
into the repository in a PR; the artifact may then be re-synced from the repository,
never the reverse without review.


These are chunks small enough to build and verify one at a time (`CLAUDE.md` §6). Each chunk lands with its docs in the same change set (`CLAUDE.md` §1) and passes `make verify` plus `tsc --noEmit` before the next one starts. The plan is mirrored in the repository at `.planning/plans/design-system.md`.

## Where things go

```
apps/web/src/
  design/
    tokens.json          ← copied from this system; the ONE source
    tokens.ts            ← GENERATED: typed values for charts/canvas
    enums.ts             ← domain vocabularies as `as const` arrays
    status.ts            ← Record<Enum, Tone> maps, `satisfies`-checked
    evidence.ts          ← role → grade; unknown → "?"
    format.ts            ← cs-CZ number, money, percent, duration
  app/
    tokens.css           ← GENERATED: :root / [data-theme] custom properties
    globals.css          ← @import tokens.css; @theme inline { … }; @font-face
    fonts/               ← the ten woff2 files (OFL)
  components/
    status/  evidence/  scope/  lifecycle/  money/  review/  results/  doc/  shell/
apps/web/scripts/build-tokens.mjs   ← tokens.json → tokens.css + tokens.ts
tools/enum_parity_check.py          ← domain StrEnums ⇄ design/enums.ts
```

Tailwind 4 stays CSS-first. There is no `tailwind.config.js`. `@theme inline` maps utilities onto the runtime variables, so `bg-surface`, `text-ink` and `border-border-strong` follow `data-theme` with no rebuild:

```css
@import "tailwindcss";
@import "./tokens.css";               /* :root,[data-theme="light"]{--surface:#f9f6f2;…} [data-theme="dark"]{…} */
@theme inline {
  --color-surface: var(--surface);  --color-ink: var(--ink);  --color-signal: var(--signal);
  --color-status-you: var(--status-you);  /* … every colour token, generated */
  --font-sans: var(--font-sans);  --font-mono: var(--font-mono);  --font-serif: var(--font-serif);
  --radius-sm: var(--radius-sm);  --spacing: 4px;
}
```

## The enum binding: a new domain status fails the build

```ts
// design/enums.ts — checked against the Python StrEnums by tools/enum_parity_check.py
export const STAGE_STATUS = ["NOT_STARTED", "READY", "RUNNING", "WAITING_USER", "WAITING_CREDITS",
  "WAITING_CAPACITY", "DONE", "DONE_WITH_WARNINGS", "INVALIDATED", "FAILED"] as const;
export type StageStatus = (typeof STAGE_STATUS)[number];

// design/status.ts
export type Tone = "running" | "you" | "world" | "fault" | "recovery" | "done" | "done-warn"
  | "ready" | "inert" | "blocked" | "invalid" | "cancelled" | "skipped";
export const STAGE_TONE = {
  NOT_STARTED: "inert", READY: "ready", RUNNING: "running", WAITING_USER: "you", WAITING_CREDITS: "you",
  WAITING_CAPACITY: "world", DONE: "done", DONE_WITH_WARNINGS: "done-warn", INVALIDATED: "invalid", FAILED: "fault",
} as const satisfies Record<StageStatus, Tone>;   // a missing or extra key is a tsc error
```

This gives two independent tripwires:

1. `satisfies Record<…>` makes a map that is missing a value in `enums.ts` fail `tsc --noEmit`.
2. `tools/enum_parity_check.py` imports `aia_core.domain` and compares every bound enum with its TypeScript array. It runs in `make verify` and CI, so adding a value in Python without adding it in TypeScript fails CI *before* anyone touches a map. Neither tripwire alone is enough: (1) cannot see Python, and (2) cannot see the maps.

When the API publishes these enums in its OpenAPI document, `enums.ts` can be generated from it instead, and the parity check becomes a drift check on the generated file.

## Chunks — order revised

Chunks 0–3 are the foundation, each its own PR. **After chunk 3 the plan stops going
screen by screen over fixtures** and builds one real vertical slice first (chunk V).
Chunks 4–11 resume only after that slice is working and reviewed.

| # | Chunk | Lands | Verify |
|---|---|---|---|
| 0 | **Vocabulary alignment.** Remove the "case / five gates / nine statuses" product language. Canonical: Organization → Client → Study → Project Revision → Stage, with the real 13-stage Research and Simulation lifecycles from `pipeline.py`. No frontend-invented statuses. **API routes are authoritative**; browser routes are not renamed merely for tidiness if that breaks links or duplicates router state. Remaining fixtures are explicit development fixtures, labelled as such. | fixtures, `i18n/cs.ts` keys, pages | `tsc`, lint, build; no "case"/"gate N" product vocabulary left |
| 1 | **Tokens, themes, identity.** `design/tokens.json` as the one source; a repository generator emits `tokens.css` and `tokens.ts` (CI fails on drift); `@theme inline`; light/dark/system; self-hosted fonts with licences; identity and favicon assets; the contrast, chart-palette and +35 % Czech checks re-run from the repository. | tokens, generator, fonts, assets, checks | generator drift check; 146 contrast checks; palette validation; stress test |
| 2 | **Domain enum binding** (high priority). Total `Record<>` mappings for the bound enums; an independent Python ↔ TypeScript parity check in CI. The UI maps state → visual treatment only. Evidence roles: until analysis-governance publishes the contract, an unknown role renders `?` — never measured, never the strongest grade. | `design/enums.ts`, `status.ts`, `evidence.ts`, `tools/enum_parity_check.py` | a fake domain value fails both tripwires |
| 3 | **Primitives + Vitest** (DS-1). `StatusGlyph`, `StatusChip`, `EvidenceMark`, `Value`, `Money`, `Icon`, `Button`, `Kbd`, `Panel`, with tests: zero ≠ null, null ≠ suppressed, unknown evidence ≠ measured, every status has text and shape besides colour, both themes, keyboard/focus where interactive, Czech labels. Evidence marks stay SVG. | components + tests | `npm test` in CI |
| V | **First vertical slice.** Portfolio → Client → Study → Study overview → workflow state → human action / approval, on **real APIs** wherever the capability exists: authenticated user, active Client and Study, accent + monogram, study status, real runs and stages, real waiting reasons, what needs *this viewer* (only as the API states it), permitted approvals, budget where data exists, error and recovery states. No fake percentages or synthetic progress. Fixtures only for capabilities that genuinely do not exist, labelled in code, never presented as production-complete, and counted in a machine-readable registry. | pages + API client | a real run through the dev API; fixture count reported |
| 4 | **Scope chrome.** `ScopeBar`, `ClientMonogram`. API: `clients.accent_slot` (DS-2) — **integration-architecture is notified before the migration lands** (OI-12). | layout + migration | migration reversible; slot-assignment test |
| 5 | **Lifecycle.** `StageRail` (`"use client"`: roving focus and `[` `]` keys), `RunTimeline`, `RevisionBanner`, `RevisionHistory`. | `components/lifecycle` | keyboard test; narrow layout at 1024 px |
| 6 | **Impact preview.** Renders the domain `ImpactPreview` only: stages preserved, stages invalidated, the presentation-only flag, and cost and duration **explicitly unavailable**. React computes no estimate. The estimator is a cross-context dependency (`ImpactPreviewEstimate`, OI-10). | component + endpoint wiring | cost/duration render as unavailable while the contract is absent |
| 7 | **Money.** `BudgetMeter`, `UsageLedger` (server), `ParkAndAsk` (`"use client"`: dialog focus trap), `ProviderChoice`, `RecoveryDecision`. | `components/money` | focus opens on the heading; no default action |
| 8 | **Review.** `ApprovalPanel` including the separation-of-duties state, driven by the server's `ApprovalIndependence` / denial reason. | `components/review` | a SoD state test |
| 9 | **Results.** `HeadlineAnswer`, `GradedBars`, the respondent explorer, `Sociomap` (`"use client"`: drag saves a view override through the API; it never mutates results). | `components/results` | a view-override test: the original is unchanged |
| 10 | **Deliverable.** The `.aia-doc` register, the cover, the evidence margin, the holdout statement, and the export spec handed to the report service. | `components/doc` | greyscale-print snapshot |
| 11 | **Remaining screens.** Recompose the other screens on real endpoints where they exist. | pages | +35 % string test at 1280 / 1024 |

## Chunk log

- **Chunk 0 — vocabulary alignment** (branch `feature/web-vocabulary`). The
  "cases" routes, the five-gate and nine-status flow, and the "agents"/"templates"
  pages are gone. Old paths redirect (307) to Portfolio instead of 404ing. Browser
  routes follow the API's study scoping: `/org/[orgSlug]/studies/[studyId]/projects/[projectId]/stages/[stageId]`.
  The org segment is kept, because renaming it would break existing links for no
  gain. Screens render API-shaped fixtures (`src/fixtures/`), each marked on screen,
  with 5 fixture-backed capabilities in `src/fixtures/registry.ts`. Copy keys are
  now typed: a missing key is a `tsc` error. Unknown ids return 404 with the same
  copy for "missing" and "not granted", as the API does.

- **Chunk 1 — tokens, themes, identity** (branch `feature/design-tokens`).
  `src/design/tokens.json` is the one source. `scripts/build-tokens.mjs` generates
  `src/app/tokens.css`, `src/app/tokens-theme.css` (the Tailwind `@theme inline`
  mapping) and `src/design/tokens.ts`, and `tokens:check` fails CI on drift. The
  artifact page's generated CSS is not used. Themes are light, dark and system;
  the system theme sets no attribute and follows the OS. The preference is stored
  per viewer and applied before first paint. The four faces are self-hosted with
  `next/font/local`, with their OFL licences beside them. The mark, wordmark,
  lockup, motif and favicon set are repository files. Evidence re-measured from
  the repository:
  - `check:design`: 146 contrast checks, 0 failures.
  - Chart palette: colour-blind ΔE 9.2 light / 9.3 dark, normal-vision ΔE
    27.6 / 24.6, and the first three slots pass all-pairs.
  - Accent separation: ΔE ≥ 7.6 from status/UI/chart colours and ≥ 12.9 between
    accents.
  - `check:layout`: +35 % Czech at 1280 and 1024 px, 0 overflows, after fixing
    the Report stage, which overflowed on first run.
  `check:layout` needs a browser, so it is manual for now. Existing screens moved
  from zinc/blue/amber classes to token utilities. Amber now appears only on the
  waiting-on-a-person tone: the report editor's "proposal ready" is neutral.

- **Chunk 2 — domain enum binding** (branch `feature/enum-binding`). There are 17
  bound enums plus both lifecycles (ids and Czech labels). Two independent
  tripwires, both demonstrated by adding a fake `PAUSED_BY_ADMIN` stage status:
  1. `satisfies Record<Enum, Tone>` / `Record<Enum, string>` in
     `src/design/status.ts`. A value without a treatment or label fails `tsc`.
  2. `tools/enum_parity_check.py` (`make enum_check`, backend CI job, blocking)
     compares values and order in both directions. It also forces a decision on
     any *new* domain enum: `InteractionMode`, `RecoveryAction`, `DataClass` and
     `ResidencyZone` are listed as deliberately unbound, each with a reason.
     `packages/aia_core/tests/test_enum_parity_check.py` covers it with 6 tests.
  DS-3 is encoded: the base maps can never produce the personal `you` tone.
  `appearance()` upgrades `person` → `you` only when the caller passes the API's
  `viewerCanResolve: true` (OI-11); anything else renders "čeká na tým / správce".
  Evidence roles: 4 known. Any other value, including null, is `unknown` (OI-9).
  There is no Python evidence enum yet, so evidence is not in the parity check;
  it joins when analysis-governance publishes one.

- **Chunk 3 — primitives + Vitest** (branch `feature/web-primitives`). DS-1:
  Vitest 3 + Testing Library + jsdom. `npm test` runs in CI and is blocking.
  `src/components/ui/` holds `StatusGlyph`, `StatusChip`, `EvidenceMark`,
  `Value`, `Money`, `Icon`, `Button`, `Kbd` and `Panel`. All are server
  components; `ThemeSwitch` is the one client component. 117 tests, including
  the required ones:
  - zero ≠ null, null ≠ suppressed, and suppression always carries its reason;
  - an unknown evidence role is never measured;
  - every status of the 9 bound status enums renders a Czech label and a
    shaped glyph;
  - the five room-scale tones have five distinct shapes;
  - DS-3: team vs "you" is decided only by `viewerCanResolve`;
  - chip classes use token utilities only, and the solid amber fill is
    reserved for `you`;
  - `ThemeSwitch` works with light, dark and system, including from the
    keyboard;
  - `Button` activates on Enter and Space and has no `disabled` prop at all;
  - tokens resolve in both themes.
  Evidence marks are SVG, with the "?" drawn as a path rather than typed. The
  demo's `components/aia/ui.tsx` (`Card`, `Pill`) is gone; screens use `Panel`
  and `StatusChip`. `/dev/states` is a dev-only state gallery for review
  screenshots, and 404s unless `AIA_ENABLE_DEV_PAGES=1`.

## What product-surface does not own

The UI renders the results of these contracts and never re-implements them:
research computation, population policy, evidence policy, budget calculation,
provider fallback logic, approval authorization, and Sociomapping mathematics.

## Cross-context contracts this plan depends on

| Contract | Owner | Needed by | Register |
|---|---|---|---|
| Complete evidence-role enum | analysis-governance (A6) | chunk 2 (until then: unknown → `?`) | OI-9 |
| `ImpactPreviewEstimate` — cost and duration of re-running invalidated stages | integration-architecture, with research execution and the cost ledger | chunk 6 (until then: unavailable) | OI-10 |
| Viewer actionability ("what needs me") — e.g. `action_required`, `action_kind`, `viewer_can_resolve`, `required_permission`, `waiting_reason`; exact shape is theirs | integration-architecture / platform-runtime | chunk V Portfolio (until then: raw system state, never assigned to the viewer) | OI-11 |
| `clients.accent_slot` persistence change | integration-architecture (notified before the migration) | chunk 4 | OI-12 |

## What happens to the existing client

| Today | Becomes |
|---|---|
| `components/aia/ui.tsx` — `Card`, `Pill`, `AiaLink` | `Panel` (`components/shell`), `StatusChip` (`components/status`) — a `Pill` with a free `tone` prop is exactly the drift this system removes — and plain `next/link` styled `text-signal` |
| `AppShell.tsx` | `components/shell/AppShell` with `ScopeBar` above the navigation |
| `CaseWorkspaceLayout.tsx`, `Ribbon.tsx`, `StepPage.tsx` | `StudyLayout` + `StageRail` + `StagePage` |
| `ArtifactsPanel.tsx` | restyled onto `Panel`, artifacts listed with revision and `StatusChip` |
| `DocEditor.tsx` (TipTap) | kept; toolbar restyled; editing a material field routes through `ImpactPreview` |
| `lib/mock.ts`, `mockArtifacts.ts` | API-shaped fixtures (chunk 0), deleted once the endpoints exist |
| `app/org/[orgSlug]/cases/…` | decided in chunk 0 against the API's study-scoped paths (`/api/v1/studies/{study_id}/…`), which are authoritative; no rename that breaks links or duplicates router state |
| `app/favicon.ico`, `public/*.svg` (Next.js defaults) | the AIA favicon set; defaults deleted |

## Decisions — resolved

- **DS-1 — web test runner: YES.** Vitest + Testing Library in `apps/web` (chunk 3).
- **DS-2 — `clients.accent_slot`: YES, with a contract qualification.** It is a stable
  *presentation and scope cue*. It is **not** a security boundary, **not** a client
  identifier, and **not** required to be globally unique for ever. Client name,
  monogram and the explicit Client / Study scope chrome remain authoritative, and
  colour is never the only cue. A constrained smallint slot range (1–6), assigned
  deterministically server-side at client creation by the least-used strategy.
  Browser input never chooses it. Because it changes the Client persistence
  contract, integration-architecture is notified before the migration lands (OI-12).
- **DS-3 — `WAITING_CREDITS`: RESOLVED.** `WAITING_CREDITS` means work needs *human
  intervention* to become runnable again; `WAITING_CAPACITY` means the system,
  provider or world must recover. `WAITING_CREDITS` is **not** automatically
  "waiting on the current viewer". The application layer exposes whether the
  authenticated viewer is authorized and able to resolve the parked condition, and
  the UI rule is:

  | Status | Viewer can resolve | Treatment |
  |---|---|---|
  | `WAITING_CREDITS` (and every `AWAITING_*`) | yes | "čeká na vás" — personal amber |
  | `WAITING_CREDITS` (and every `AWAITING_*`) | no, or not stated | "čeká na tým / správce" — waiting on a person, not amber-personal |
  | `WAITING_CAPACITY`, `WAITING_PROVIDER` | — | "čeká na externí kapacitu" |

  Viewer actionability is never inferred from the status enum. Until the API
  states it (OI-11), the second row applies.

## Findings carried from the design work

1. **The evidence role list is incomplete in this repository** — *finding*, filed as OI-9. Only `MEASURED_JOINT`, `CALIBRATED_CORE` and `MODELED_BEHAVIOR_PRIOR` are named, followed by "…" (`docs/product/README.md:103` @ 17c0a6b), plus `EXTERNAL_HOLDOUT_PENDING`. Reproduce: `grep -rn "MEASURED_JOINT" --include=*.py .` returns nothing. The Validation & Evidence context is not started (`docs/architecture/domain-map.md` @ 17c0a6b). Consequence: the grade grammar is built for an open set, and unknown roles render "?". Fix: publish the role enum in `aia_core.domain` and add it to `enums.ts` and the parity check.
2. **A hash-derived client accent collides at five clients** — *finding*. `clientAccentIndex("cl_salvia") === clientAccentIndex("cl_tecka") === 4` (FNV-1a mod 6; run it in the bundle). Fix: a persisted `accent_slot` (DS-2, resolved).
3. **Neither shipped face has the geometric-shape glyphs** — *finding*. U+25A1, U+25A3 and U+2B1A are missing from IBM Plex Sans and Source Serif 4, and U+25A0 is missing from Plex Sans (fontTools cmap check on `fonts/*.woff2`). Consequence: evidence marks are always vector, never characters, including in DOCX export.
4. **`ImpactPreview` carries no cost or time estimate** — *finding*, filed as OI-10. The domain object has only `root_stage`, `invalidate`, `preserve` and `presentation_only` (`packages/aia_core/src/aia_core/domain/pipeline.py:423` @ 17c0a6b). The component shows *chybí* until an estimate exists. Deriving one from past runs is backend work, not UI.
5. **`WAITING_CREDITS` ownership** — *resolved by DS-3*: a person must act; whether that person is the viewer comes from the API (OI-11).
6. **Portfolio amber is personal** — *design requirement on the API*, filed as OI-11. The server must say whether a pending decision is assignable to the viewer, for example through a permission check against `APPROVE_BUDGET` / `APPROVE_GATE`. The UI must not infer it.
7. **Plex Sans ships no `tnum` feature** — *finding, benign*. Its default figures are already tabular (all digits 600 units in Regular and SemiBold). `tabular-nums` is kept in CSS for fallback faces.
