# Implementation plan for apps/web

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

## Chunks

| # | Chunk | Lands | Verify |
|---|---|---|---|
| 0 | **Vocabulary purge.** Rewrite `lib/mock.ts` as API-shaped fixtures (Study → Project → Revision → Stage, 13 stages, domain enums). Drop "cases", five numbered gates and the nine-status flow. Routes move to `/studies/[studyId]/…`, matching the API's study-scoped paths. | fixtures, route rename, `i18n/cs.ts` keys | `tsc`; no string "case" left in `src/` |
| 1 | **Tokens.** `design/tokens.json`, `build-tokens.mjs`, generated `tokens.css` and `tokens.ts`, `globals.css` `@theme inline`, `next/font/local` over `app/fonts/`, and `data-theme` on `<html>` with a light/dark/system switch. | tokens, fonts, theme switch | a CI check re-runs the generator and fails on diff; the contrast script's 146 checks re-run |
| 2 | **Enum binding.** `design/enums.ts`, `status.ts`, `evidence.ts`, `tools/enum_parity_check.py`, and a `make enum_check` target wired into `verify` and CI. | the two tripwires | add a fake value to `StageStatus` locally → both fail |
| 3 | **Primitives.** `StatusGlyph`, `StatusChip`, `EvidenceMark`, `Value`, `Money`, `Icon`, `Button`, `Kbd`, `Panel`. All are server components. | `components/status`, `evidence`, `shell` | a unit test per component (see decision DS-1) |
| 4 | **Scope chrome.** `ScopeBar` and `ClientMonogram` in the study layout; `Portfolio` / `Admin` get the above-boundary band. API: `clients.accent_slot` smallint, assigned least-used at creation, immutable (Alembic migration + repository + test). | one migration, one layout | migration reversible; a slot-assignment test |
| 5 | **Lifecycle.** `StageRail` (`"use client"`: roving focus and `[` `]` keys), `RunTimeline`, `RevisionBanner`, `RevisionHistory`. | `components/lifecycle` | keyboard test; narrow layout at 1024 px |
| 6 | **Impact preview.** An API endpoint that returns the domain `impact_preview` for a pending edit; the `ImpactPreview` component; the edit flow always passes through it. | endpoint + component | an API test per `IMPACT_ROOTS` entry |
| 7 | **Money.** `BudgetMeter`, `UsageLedger` (server), `ParkAndAsk` (`"use client"`: dialog focus trap), `ProviderChoice`, `RecoveryDecision`. | `components/money` | focus opens on the heading; no default action |
| 8 | **Review.** `ApprovalPanel` including the separation-of-duties state, driven by the server's `ApprovalIndependence` / denial reason. | `components/review` | a SoD state test |
| 9 | **Results.** `HeadlineAnswer`, `GradedBars`, the respondent explorer, `Sociomap` (`"use client"`: drag saves a view override through the API; it never mutates results). | `components/results` | a view-override test: the original is unchanged |
| 10 | **Deliverable.** The `.aia-doc` register, the cover, the evidence margin, the holdout statement, and the export spec handed to the report service. | `components/doc` | greyscale-print snapshot |
| 11 | **Screens and brand.** Recompose the eleven screens on real endpoints where they exist and fixtures where they do not; favicons into `public/`; `layout.tsx` metadata. | pages | +35 % string test at 1280 / 1024 |

## What happens to the existing client

| Today | Becomes |
|---|---|
| `components/aia/ui.tsx` — `Card`, `Pill`, `AiaLink` | `Panel` (`components/shell`), `StatusChip` (`components/status`) — a `Pill` with a free `tone` prop is exactly the drift this system removes — and plain `next/link` styled `text-signal` |
| `AppShell.tsx` | `components/shell/AppShell` with `ScopeBar` above the navigation |
| `CaseWorkspaceLayout.tsx`, `Ribbon.tsx`, `StepPage.tsx` | `StudyLayout` + `StageRail` + `StagePage` |
| `ArtifactsPanel.tsx` | restyled onto `Panel`, artifacts listed with revision and `StatusChip` |
| `DocEditor.tsx` (TipTap) | kept; toolbar restyled; editing a material field routes through `ImpactPreview` |
| `lib/mock.ts`, `mockArtifacts.ts` | API-shaped fixtures (chunk 0), deleted once the endpoints exist |
| `app/org/[orgSlug]/cases/…` | `app/studies/[studyId]/…` |
| `app/favicon.ico`, `public/*.svg` (Next.js defaults) | the AIA favicon set; defaults deleted |

## Decisions this plan needs from a person

- **DS-1 — a web test runner.** `apps/web` has none (`make test-web` runs `npm test --if-present`). Vitest with Testing Library is the smallest option that fits Next 16 / React 19. Chunk 3 needs a yes or no.
- **DS-2 — `accent_slot` in the schema** (chunk 4). The alternative, a hash only, is proven to collide at five clients.
- **DS-3 — who owns `WAITING_CREDITS`.** This system treats it as parked-on-you (someone must add credits). If credits are provider-side quota, it moves to `world`: a one-line change in `status.ts`.
