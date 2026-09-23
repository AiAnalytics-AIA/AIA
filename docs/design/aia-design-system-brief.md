# AIA — Brand & UI direction

**A brief for Claude Design.** Paste this whole file as the opening prompt, with
the AIA repository connected.

---

## 0. Your task

Design and build **the AIA design system**: brand direction, tokens, assets,
component library, page-level compositions, and a repo-ready implementation that
drops into `apps/web` (Next.js 16 / React 19 / Tailwind 4 / TypeScript strict).

Not a generic admin theme with our name on it. A system whose every decision
follows from what this product actually is and what it refuses to do.

**Read these before designing anything:**

| File | Why |
|---|---|
| `docs/product/README.md` | Authoritative product scope. The users, the lifecycles, the rules. |
| `README.md` | The core idea and what the system refuses to do. |
| `ARCHITECTURE.md` §4, §5, §6, §10 | Contracts, where code goes, anti-patterns, refusals. |
| `CLAUDE.md` §2 | The project map and the working rules you must follow. |
| `packages/aia_core/src/aia_core/domain/pipeline.py` | `ProjectType`, `StageStatus`, impact/invalidation. |
| `packages/aia_core/src/aia_core/domain/workflow.py` | Run/step/attempt states, `FailureClass`, `ReservationStatus`, `RecoveryAction`. |
| `packages/aia_core/src/aia_core/domain/scope.py` | `ScopeRole`, `Permission`, `StudyStatus`, `ClientStatus`, approval independence. |
| `packages/aia_core/src/aia_core/domain/providers.py` | `Provider`, `ProviderPolicy`, `ModelRole`. |
| `apps/web/src/app/globals.css`, `components/aia/*`, `i18n/cs.ts` | What exists today. |

**Warning about the existing client.** `apps/web` is a mock-backed demo. Its
vocabulary is stale: `lib/mock.ts` says "cases" with five numbered gates and a
nine-status flow. That contradicts the authoritative model — **Study → Project →
Revision → Stage**, thirteen stages, status enums as listed in the domain files.
Treat the existing UI as evidence of intent and nothing more. Take the
vocabulary from `docs/product/README.md` and the domain enums, never from the
mock.

---

## 1. What AIA is, in one paragraph

An **internal research operating system**. About five expert researchers use it
to produce paid client studies: a client asks a business question, AIA designs a
study, runs it against a calibrated synthetic population of the Czech Republic,
analyses the results, and produces a consulting-grade report. Clients never log
in — they receive a delivered document. There is no signup, no plan tier, no
marketplace. A single study represents days of work, real money in AI provider
calls, and a confidentiality obligation to a paying client.

Design for **five experts who live in this tool eight hours a day**, not for a
visitor who must be impressed in thirty seconds. Density, keyboard reach and
information honesty beat onboarding delight. Nothing here needs to sell itself.

---

## 2. The positioning: an instrument, not a dashboard

The one sentence that should govern every decision:

> **AIA is a precision instrument for producing defensible knowledge. Its
> interface must never make anything look more certain, more finished, or more
> measured than it is.**

The backend is built around refusals — no invented certainty, no fake progress,
no silent provider fallback, no spending past a budget, no visualisation
mutating research truth. Those refusals are enforced in code. **The design
system is where they become visible.** A backend that carefully tracks whether a
number was measured or modelled, wired to a UI that renders both as the same
grey digits, has thrown the whole investment away.

So the system's signature is not a colour or a corner radius. It is that
**epistemic status, provenance and cost are first-class visual citizens**, at
the same level as hierarchy and spacing.

### Two registers, one token set

Design the system in two registers that share one token foundation:

- **Studio** — the working surface. Dense, instrument-like, dark mode
  first-class, tabular, keyboard-driven. Where researchers spend the day.
- **Deliverable** — the report surface. Light, editorial, generous, print- and
  export-ready, consulting-grade. What a client eventually sees on paper.

The same evidence-role treatment must read correctly in both, including in
greyscale print. This is the hardest constraint in the brief and the most
important one to solve early.

---

## 3. Brand direction

No brand assets exist. `apps/web/public/` contains only Next.js defaults. You
are starting clean; propose the identity.

**Tone:** exact, calm, quietly confident. Scientific instrumentation and
serious consultancy — not startup SaaS, not "AI magic". Explicitly avoid:
purple-to-blue AI gradients, glows and light-leak effects, sparkle or wand
iconography, anything that implies the machine knows more than it does. AI is
present in this product as an assistant that chooses tools and writes prose; it
never computes the numbers, and the visual language must not suggest otherwise.

**Lead with this direction, and show one alternate pass on a single key screen:**

- **A — "Instrument" (recommended).** Graphite and paper. A near-black,
  slightly cool ink; a true paper white with a faint warm cast so long reading
  sessions do not glare. One precise signal accent — a cold, calibrated blue
  with a cyan lean, the colour of a measurement line, used sparingly for
  selection, focus and the live edge of a running process. One warm counterpart
  — ochre or amber — reserved **exclusively** for *waiting on a human*. That
  reservation is deliberate: see §4.3.
- **B — "Editorial".** Warmer paper, a high-quality serif for headings on the
  Deliverable register, closer to a printed research quarterly. Stronger on the
  report surface, weaker in dense tables.
- **C — "Lattice".** The synthetic population as the whole identity — a field of
  individual points resolving into structure.

**The motif.** Whichever direction wins, AIA has one natural graphic idea worth
building the identity on: the population is **synthetic, individual and
calibrated** — thousands of modelled persons that aggregate into a society. A
field of discrete points that resolves into structure at distance, and
disaggregates into individuals close up. Use it for the wordmark, empty states,
loading surfaces, section dividers and the Sociomapa's visual grammar. It is
honest about what the product is, and it scales from a 16px favicon to a report
cover.

Avoid Czech national iconography — no flags, no lion, no Prague skyline. The
population being Czech is a data fact, not a brand theme. A restrained
cartographic or lattice reference is fine; a tourism poster is not.

**Deliver:** wordmark (AIA, plus "Agentic AI Analytics" lockup), app icon and
favicon at 16/32/180/512, a monochrome variant, the motif as reusable SVG, the
report cover treatment, and clear rules for clear-space and minimum size.

---

## 4. The signature systems — where this stops being generic

These are the components that only AIA needs. They are the point of the
engagement. Get these right and the rest follows.

### 4.1 Evidence roles — the epistemic grade

Every figure in this product carries a role that travels with the data:
`MEASURED_JOINT`, `CALIBRATED_CORE`, `MODELED_BEHAVIOR_PRIOR`,
`EXTERNAL_HOLDOUT_PENDING`, and others. A modelled figure must never be
presented as a measurement. Cross-block relationships are not same-person truth.

**Design a visual grade that applies to a number, a table cell, a chart series,
a map node and a paragraph of report prose** — the same grammar at every scale.

Hard requirements:
- It must survive **greyscale printing**, because reports are exported. Colour
  alone is disqualified. Use texture, stroke treatment, weight or a mark.
- It must survive being **shrunk into a dense table** without becoming noise.
- It must be **legible without a legend** after one exposure, and have a
  persistent legend available.
- It must degrade honestly: when the role is unknown, it says so — it does not
  default to the strongest grade.

Read `docs/product/README.md` → "No invented certainty" and
`ARCHITECTURE.md` §10 before designing this. Check the domain and architecture
docs for the full role list rather than assuming the four named above are all
of them.

### 4.2 Null is not zero, and unknown is not neutral

Two of this project's named anti-patterns: *never stamp a guess — prefer null*,
and *never score unknown as good*. The UI must hold up its end.

Design an explicit **"no data" treatment** — a glyph and a cell state — that is
unmistakably distinct from a zero, an empty string, a loading skeleton and a
suppressed value. Four distinct states, four distinct appearances:

| State | Means |
|---|---|
| Value | We measured or modelled this. |
| Zero | We looked and the answer is zero. |
| Not available | We never looked, or the answer did not arrive. |
| Suppressed | We have it, but it is withheld — sample too small, or permission. |

"Not available" must never look softer or more neutral than a bad value. It is
information, not absence.

### 4.3 Waiting is a first-class state, and it is not failure

This is the product's most distinctive interaction and its biggest UX risk.
Work does not fail when a provider is down or a budget is exhausted — **it parks
and asks**. The states from the domain:

- `WAITING_USER` · `WAITING_CREDITS` · `WAITING_CAPACITY` (stage level)
- `AWAITING_GATE` · `AWAITING_BUDGET` · `WAITING_PROVIDER` · `WAITING_CAPACITY`
  · `RECOVERY_REQUIRED` (run and step level)

Design the status system so a researcher can tell **at a glance and across a
room** the difference between:

1. **Running** — the machine is working, nothing is needed from you.
2. **Parked, waiting on you** — it will sit here forever until you act. This is
   the state that costs the business days, and it must be the loudest thing on
   any screen. This is what the warm accent is reserved for.
3. **Parked, waiting on the world** — provider capacity, quota. You may choose
   to act; you do not have to.
4. **Failed** — it is over and it needs diagnosis.
5. **Recovery required** — a metered call may have been billed and its outcome
   is unknown. Rarest, most serious, needs its own treatment: this is not a
   retry button, it is a decision.

A parked stage that looks like a failed stage will produce panic; a parked stage
that looks like a running stage will produce a week of silent nothing. Both are
real failure modes of the naive design. Show the full state matrix explicitly in
your deliverable, with the reasoning.

**No fake progress.** Real elapsed time, real stage transitions, real counts
only. No synthesised percentage bar, no indeterminate shimmer that implies
imminence the backend cannot promise. Design the honest alternative: elapsed
time, the current step, what it is waiting on, and what it has completed. Make
that genuinely satisfying to watch — it is the product's most-watched surface.

### 4.4 Client confidentiality made physical

Client and Study are **hard isolation boundaries**, enforced in code. The
interface must make them felt, because the residual risk is human: a researcher
with two clients open pasting the wrong thing into the wrong study.

Design **persistent scope chrome** that is impossible to lose track of:
- The active Client and Study visible at every moment, in every register.
- A **deterministic per-client accent** derived from the client identifier,
  drawn from a constrained set that provably never collides with the status
  palette or the data-viz palette. Switching clients should feel like walking
  into a different room.
- A distinct treatment for cross-client surfaces (Portfolio, admin) so it is
  obvious you are *above* the boundary rather than inside one.
- An unmistakable state for delivered and archived studies — read-only past work
  must not look like live work.

Also design for the authorization model: `VIEWER`, `REVIEWER`, `RESEARCHER`,
`LEAD`, and organization roles above them. A viewer's screen should not be a
researcher's screen with dead buttons. Absent permissions are absent, not
disabled — except where the presence of an action is itself the information the
user needs.

### 4.5 The lifecycle rail and the impact preview

Both lifecycles are thirteen stages:

```
Research     Brief → Deep Research → Research Design → Questionnaire → Audience
             → Dimensions → Sample Plan → Fieldwork → Aggregation → Validation
             → Analysis → Report → Delivery

Simulation   Brief → Deep Research → Baseline → Scenario Contract → Audience
             → Dimensions → Variants → Worlds → Frozen Results → Comparison
             → Interpretation → Report → Delivery
```

Design the **stage rail**: thirteen stages, ten possible statuses each, legible
at a glance, usable as the primary navigation of a project, and still workable
on a laptop screen. It must carry both lifecycles without feeling like one was
retrofitted.

Then design the system's most interesting single component: the **impact
preview**. Each stage's material inputs are fingerprinted, so editing something
reopens only the affected stage and its dependants. Before a researcher commits
an edit, the UI must answer: *what does this cost me?* — which stages reopen,
which artifacts survive, what must be re-run and what that will cost in money
and time. Make the consequences of an edit visible **before** the edit, not
after. See `pipeline.py` → `ImpactPreview`.

Related: revisions are immutable and content changes create new ones. Design the
revision history, the comparison between revisions, and a clear indicator of
"you are looking at a superseded revision".

### 4.6 Money as a first-class object

Paid calls are checked before they are made; over budget means park and ask.
Reservations settle as `RESERVED`, `SETTLED`, `RELEASED` or `SETTLED_UNCERTAIN`.
There is an immutable AI usage ledger.

Design:
- A **budget meter** that distinguishes *spent*, *reserved but not yet settled*,
  *remaining* and *uncertain*. Three of those four are not a simple progress
  bar, and `SETTLED_UNCERTAIN` must be visible rather than rounded away.
- The **park-and-ask dialog** — the moment a researcher is asked to authorise
  spending. It must state what will be spent, on what, against which study's
  budget, and what happens if they decline. It must not have a cheerful default.
- The **usage ledger**: dense, sortable, exportable, immutable, attributable to a
  model role and a step.
- **Provider and model provenance** — `Provider`, `ProviderPolicy`, `ModelRole`.
  When work parks because a provider cannot serve it, the UI offers an explicit
  choice; it never presents a cheaper substitution as a convenience.

Money should be legible instantly: tabular figures, a consistent currency
treatment, and never a bare number whose unit you must infer.

### 4.7 Gates, review and sign-off

Automated reports pass an evidence and QA gate and **still require a person** to
approve them before a client sees them. Independent review is the default;
self-approval exists only where an administrator enabled it in persisted policy.

Design the approval object: what is being approved, by whom, on what evidence,
what the reviewer is attesting to, and the audit trail afterwards. Include the
**separation-of-duties refusal** — the state where you cannot approve this
because you produced it — as a designed state, not an error toast. See
`scope.py` → `ApprovalIndependence`, `SelfApprovalPolicy`,
`SeparationOfDutiesViolation`.

### 4.8 Results workspace and Sociomapa

The results surface carries: headline answer, findings, segments, filters,
respondent explorer, charts, evidence and exports. Design the **headline answer**
as a deliberate component — the single sentence a client pays for — with its
evidence grade attached and its supporting findings one level down.

**Sociomapa** is respondent and object maps over a shared data contract, with
matrix, comparison and what-if modes. Design its visual grammar: nodes, edges,
clusters, density, selection, the three modes, and the legend. Two rules bind
it:
- **Visualisation never mutates research truth.** Dragging a node saves a *view
  override*. The UI must show that a view is a view — layered over immutable
  originals, attributable, resettable, and never confusable with a finding.
- **What-if is a layer**, visibly provisional, never printed as a result without
  saying so.

The data-visualisation palette is a **separate token family** from the status
palette and from client accents. Colourblind-safe, ordered for categorical,
sequential and diverging use, and verified in both light and dark. Series must
remain distinguishable in greyscale print. Show the validation, not just the
swatches.

### 4.9 The Deliverable register

The report is the product. Design a document system that reads as premium
consultancy output: a typographic scale for long-form prose, figure and table
treatments, captioning, footnoting, an evidence appendix, and a cover. It must
survive export to DOCX and PDF — so specify what degrades gracefully and what
must be raster or vector embedded. Carry the evidence grades into print.
`EXTERNAL_HOLDOUT_PENDING` must appear on the page, plainly, not in a footnote
nobody reads.

---

## 5. Tokens and foundations

Produce a complete, named, documented token set. Every token needs a stated
purpose; a token nobody can explain is a token that will be misused.

- **Colour.** Semantic layering (surface, raised, sunken, border, muted, strong),
  light and dark as equal first-class themes — not dark as an inverted
  afterthought. Four strictly separated families: *semantic UI*, *status*,
  *data-viz*, *client accent*. Document why they cannot collide.
- **Typography.** Must cover **Czech**: full Latin Extended-A with ě š č ř ž ý á
  í é ů ú ň ť ď rendering correctly at every weight. Czech UI strings run
  noticeably longer than English — design and test at +35% string length.
  **Tabular figures are mandatory** anywhere numbers are compared. Specify a UI
  face, a numeric treatment, a mono face for identifiers, fingerprints and
  ledger rows, and a Deliverable face for long-form report prose. Prefer
  self-hostable faces; state licensing.
- **Spacing, radii, borders, elevation.** A restrained scale. This product needs
  precision, not softness.
- **Density modes.** Comfortable and compact, as a real token dimension — the
  respondent explorer and the usage ledger need compact; the brief and report
  need comfortable.
- **Motion.** Sparing and purposeful. Motion may confirm a transition; it must
  never imply progress the backend cannot verify. Respect
  `prefers-reduced-motion` throughout.
- **Focus and keyboard.** A visible, high-contrast focus ring on every
  interactive element, on both themes. Expert users keyboard-drive; specify the
  shortcut model, the focus order, and the skip targets.
- **Iconography.** One coherent set, geometrically consistent, with explicit
  icons for the AIA-specific concepts: stage, revision, fingerprint, artifact,
  gate, reservation, evidence role, parked, recovery. No emoji anywhere.

**Accessibility floor:** WCAG 2.2 AA throughout, and AA-plus on numeric and
status text — these are the pixels a research conclusion rests on. Status is
never conveyed by colour alone; every status has a shape, a label or a mark.
Ship contrast verification, not assertions.

---

## 6. Implementation constraints — non-negotiable

The output must drop into this repository and pass its gates.

- **Tailwind 4, CSS-first.** Tokens go in `@theme` in
  `apps/web/src/app/globals.css`. There is no `tailwind.config.js` and one must
  not be introduced.
- **Next.js 16 App Router, React 19.** Server components by default; `"use
  client"` only where interaction genuinely requires it, and say why.
- **TypeScript strict.** `tsc --noEmit` is a blocking CI gate. No `any`, no
  unchecked casts.
- **Components render state the server computed. No business logic in
  components** — `ARCHITECTURE.md` §5. A status chip maps a value to an
  appearance; it does not decide what the status is.
- **One source of truth for tokens.** CSS custom properties consumed by
  Tailwind, plus a typed TypeScript export for anything JavaScript needs (chart
  colours, canvas rendering). Not two hand-synced lists.
- **Status vocabulary is bound to the backend enums.** Every status map —
  `StageStatus`, `WorkflowRunStatus`, `StepRunStatus`, `ReservationStatus`,
  `StudyStatus`, `ClientStatus`, `FailureClass`, roles, permissions — must be a
  total mapping over the enum's values, typed so that **adding a status in the
  domain and not in the design system fails the build**. This is the single most
  valuable integration you can give us: it stops the UI drifting from the
  backend, which is how "no invented certainty" quietly dies.
- **Internationalisation.** Strings come from `src/i18n/`. Czech is the primary
  UI language today. No hardcoded copy in components, and no layout that breaks
  when a label grows.
- **No heavyweight UI kit** that fights Tailwind 4 or ships its own theming
  runtime. Headless primitives for accessibility behaviour are welcome; a
  pre-themed component library is not.
- **Documentation is part of the deliverable**, per `CLAUDE.md` §1 — the code and
  the document that describes it change together, or the docs are worse than
  nothing because they are believed.

---

## 7. Screens to compose

Design these at real fidelity with real-shaped content — realistic Czech strings,
realistic numbers, realistic edge cases. Each screen must show at least one
degraded state, not only the happy path.

1. **Portfolio** — studies across clients, state, pending steps, quick resume.
   The screen that answers "what needs me today?" The parked-on-you items are
   the whole point of this page.
2. **Study overview** — the stage rail, budget, gates, team, recent activity.
3. **Research Studio, a stage page** — brief-first, AI-assisted, with the
   artifact panel, the run log and the impact preview on edit.
4. **Simulation Studio** — scenario contract, variants, worlds, frozen results,
   comparison. Show how it differs from Research without being a second system.
5. **Results workspace** — headline answer, findings, segments, filters,
   respondent explorer, charts with evidence grades, exports.
6. **Sociomapa** — all three modes, with the view-override and what-if layers
   visibly provisional.
7. **Data Library / Society Intelligence** — ingestion → evidence proposal →
   human approval → dimension materialisation → population revision. An approval
   queue with real evidence attached.
8. **Cost and budget** — the meter, the reservations, the immutable ledger, the
   park-and-ask dialog.
9. **Report and Delivery** — the Deliverable register, the QA gate, the human
   sign-off, the export.
10. **Admin** — clients, studies, access grants, budgets, self-approval policy.
11. **The state gallery** — every status, every evidence grade, every empty,
    loading, parked, denied and recovery state, side by side on one page. Treat
    this as a primary deliverable, not an appendix. It is the page the
    implementing engineer will actually work from.

---

## 8. What to deliver

1. **Brand direction** — the recommended direction argued in a short rationale,
   one alternate pass on a key screen, and the reasoning for the choice.
2. **Identity assets** — wordmark, lockup, app icon and favicon set, monochrome
   variant, the motif as SVG, usage rules.
3. **The token set** — as CSS custom properties in Tailwind 4 `@theme` form, as a
   typed TS export, and as a human-readable reference with each token's purpose.
4. **The component library** — every component in every state, with props,
   accessibility behaviour, keyboard model and usage guidance. Signature
   components from §4 documented in depth, including the reasoning.
5. **The screens** from §7, at fidelity, with degraded states.
6. **The state gallery.**
7. **Accessibility report** — contrast verification across both themes, the
   colour-blind check on the data-viz palette, the greyscale-print check on
   evidence grades, and the keyboard model.
8. **The implementation plan** — what lands in the repo, in what order, in
   chunks small enough to build and verify one at a time, respecting
   `CLAUDE.md` §6. Name what replaces `components/aia/ui.tsx` and what happens
   to the stale mock vocabulary.

---

## 9. How to judge your own output

Before you call this done, answer these. If any answer is weak, the system is
not finished.

1. Can a researcher tell a **modelled** number from a **measured** one, in a
   dense table, in dark mode, and on a printed page — without a legend?
2. Can they tell **parked-waiting-on-me** from **running** from **failed**, from
   across a room?
3. Can they tell **zero** from **we never looked**?
4. With two clients' work open, is it possible to lose track of which client's
   study is on screen?
5. Does an edit show its consequences **before** it is committed?
6. Does any surface imply progress or certainty the backend cannot prove?
7. Does the report look like something a client paid a consultancy for?
8. If an engineer adds a status to the domain enums and forgets the UI, does the
   build fail?
9. Is any status distinguishable **only** by colour?
10. Does the Czech UI break any layout at +35% string length?

---

## 10. The trade-off to state plainly

This system optimises for **five experts over eight-hour days** and for
**epistemic honesty over visual reassurance**. It will look denser and more
sober than a product designed to impress a first-time visitor, and some states
will be deliberately loud in a way a consumer product would soften. That is the
accepted cost. Say so in your rationale, and say what you would change if AIA
ever gained a client-facing surface — so that the decision is recorded rather
than rediscovered.
