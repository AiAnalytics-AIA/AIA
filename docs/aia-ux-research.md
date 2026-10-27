# AIA UX research: what AIA is, what the category expects, and the upgrade plan

27 Oct 2026 · branch `feature/ux-upgrade` from `develop` @ `dbaa7720` · desktop first (1280–1920 px;
the smallest screen in use is a Dell XPS 13, about 1280 × 720 usable CSS px at its default 150 % scaling).

Sources behind this document, all from this research pass:

- the repository (CLAUDE.md, ARCHITECTURE.md, `apps/web`, `.planning/`, `prototypes/LOOK.md`);
- an inventory of every route, native element and flow, anchored to `path:line @ dbaa7720`;
- two web studies: the research-software category (10 products, §2.1) and modern product UX (27 products and
  published design systems, §2.2). WebFetch was blocked in this environment (DNS), so page-level claims come
  from search-result summaries; published token packages were read directly from npm. Every claim below
  carries its source and an evidence grade (**A** primary artefact read, **B** vendor docs via search,
  **C** third-party, **D** inference);
- a hands-on walkthrough of the running app (§5.3) and 190 screenshots at 1280 / 1440 / 1920 in light and
  dark (`tmp/ux-shots/before/`, not committed);
- the audit tools: impeccable 4.8.0 `detect` (static and rendered, 11 signed-in screens) and taste-skill's
  `lint.mjs` and `inspect.mjs --app` (§5).

The product owner's brief for this work, in his words: *"our software looks and feels so clunky and
outdated, with little innovation and modern practices … look across many different relevant softwares and
combine the best from them all"*, and on 27 Oct: *"please upgrade the color pallets, i hate the current
color pallete"*. He chose the **Petrol** palette from three proposals.

---

## 1. What AIA is

**Category.** AIA is a **B2B research studio for market and social research agencies**, in the
sub-category of **AI-assisted survey research with synthetic (modelled) respondents**, combined with an
**agentic AI assistant** and a **client research repository**. Its nearest neighbours are survey/insights
platforms (Qualtrics, Conjointly, Toluna Start), synthetic-respondent tools (Qualtrics Edge Audiences,
Synthetic Users, Toluna HarmonAIze) and grounded research tools (Dovetail, Elicit). No studied product
combines all three. *(read: CLAUDE.md §2, ADR 0015/0016/0024/0026)*

**Users and roles.**

- **Researchers** at an agency, Czech-speaking, working in long desk sessions on laptops and monitors.
  Every member holds the research permissions (one role, ADR 0019).
- **Owners and administrators**: members, roles, client rules, budgets, deletion, system status.
- **The Metodik**: a member with the methodology mark who edits and activates methodology versions.
- **The client** never logs in; the client receives the approved report. *(inferred from the report flow
  and the absence of any client login)*

**Jobs they come to AIA to do.**

1. Turn a client's question into a defensible study design (brief → research questions → questionnaire →
   audience → dimensions → sample).
2. Run it on AI respondents drawn from a modelled Czech population, within a budget, with every spend
   confirmed.
3. Read what came back: tables with intervals and suppression, a sociomap (how objects such as brands
   relate), AI analysis modules, coverage of each research question.
4. Hand over an approvable report (DOCX/PDF), edited in place, approved as the exact version read.
5. Keep what they learn about a client: sources, documents, datasets, approved knowledge.
6. Work with Ada, the Research Lead, who proposes edits and paid jobs and never acts without a yes.

**Core objects.** Organization · Client (workspace, knowledge, sources, profile, rules, budget) · Study
(research or simulation; working copy, Design Revisions) · Stage (eleven, in six phases) · Run (steps,
events, spend, artifacts) · Result (measures, tables, sociomap, analysis modules) · Report (document,
versions, approvals) · Lead (turns, cards, edits, notes, mark) · Deep Research run (sealed bundle,
sources) · Methodology version · Member · Budget / wallet / threshold.

**Platform.** One **web application** (Next.js 16, React 19, Tailwind 4), desktop first, used in Czech.
Public pages are only the front door (`/login`, `/logout`, `/auth/callback`, `/classic`); everything else
is an app screen behind a session gate. An ONLYOFFICE editor is embedded for reports. There is no
marketing site, mobile app or widget in this repository. *(read: `apps/web/src/app`)*

---

## 2. Category research

### 2.1 The research-software category (10 products)

Products: Qualtrics XM (incl. ExpertReview, Quotas, Stats iQ, Edge Audiences), Displayr/Q, Conjointly,
Dovetail, Remesh, Synthetic Users, Toluna Start + HarmonAIze, Elicit, SurveyMonkey Genius and Typeform
Logic Map, and the agentic side-pane tools (Cursor, VS Code Copilot agent mode, Notion AI). Aaru and
Evidenza were considered and dropped: almost no public product documentation.

What users of this category expect (strong = ≥ 3 products or a design-system/NNg/HAX/WCAG source):

| Expectation | Products | Strength | Source |
|---|---|---|---|
| Structured questionnaire editor: blocks, typed questions, reorder, copy | Qualtrics, SurveyMonkey, Typeform | strong | qualtrics.com/support/survey-platform/survey-module/survey-builder/survey-builder-basic-overview/ |
| A live cost or credit figure **before** launch | Conjointly, Qualtrics Edge, Elicit, Copilot | strong | conjointly.com/guides/predefined-panel/ |
| Review/confirm before launch (check answers, a design score, the cost) | Qualtrics ExpertReview, SurveyMonkey Genius, Conjointly; GOV.UK "check answers" | strong | design-system.service.gov.uk/patterns/check-answers |
| Citation chip that opens the exact supporting quote | Elicit, Dovetail, Remesh | strong | docs.dovetail.com/help/chat/index |
| A visible AI marker on generated content | Dovetail, Atlassian, Carbon | strong | carbondesignsystem.com/components/ai-label/usage/ |
| AI proposals reviewed per item and all at once, editable before accepting | Cursor, VS Code, Notion, Remesh | strong | code.visualstudio.com/docs/agents/run/review-code-edits |
| Roles with inherited access; "ask this person for access" | Qualtrics, Dovetail | strong | dovetail.com/help/workspace-roles |
| Empty state: what goes here and one action | Carbon, Polaris, NN/g | strong | carbondesignsystem.com/patterns/empty-states-pattern/ |
| Skeletons for containers only; a progress bar with an estimate after 10 s | Carbon, NN/g | strong | carbondesignsystem.com/patterns/loading-pattern |
| Errors that say what went wrong and how to fix it | GOV.UK, Carbon | strong | design-system.service.gov.uk/components/error-message |
| Bulk action bar, inline edit, a non-drag alternative to every drag | Carbon, Atlassian, WCAG 2.5.7 | strong | w3.org/WAI/standards-guidelines/wcag/new-in-22/ |
| Low base suppressed with an explanation, never a blank or a zero | Displayr/Q | moderate | wiki.q-researchsoftware.com (small sample sizes) |
| Design checker with predicted duration and completion | Qualtrics, SurveyMonkey | moderate | help.surveymonkey.com/…/survey-score/ |
| Quota table, feasibility and sample-size estimate | Qualtrics, Conjointly | moderate | conjointly.com/faq/guidance-on-sample-size/ |
| Plan approved before an agent acts | Notion, Displayr agent | moderate | notion.com/en-gb/help/review-and-approve-plans-before-notion-ai-runs |
| Synthetic first, validated with people for decisions | Qualtrics Edge, NN/g | strong (NN/g) | nngroup.com/articles/synthetic-users/ |

Where AIA has **no precedent** (and leads): a per-job **cost ceiling** on an approval card (others show
unit prices or allowances), and labelling **every modelled number** as modelled. NN/g finds synthetic
users shallow and sycophantic, which supports AIA's evidence labelling (nngroup.com/articles/synthetic-users/).

### 2.2 Modern product UX (27 products and design systems)

Studied: Linear, Superhuman, Raycast, Things 3, Notion (and Notion Agent), Coda, Airtable Interfaces,
Attio, Hex, Observable, Vercel and Geist, Stripe Dashboard and Workbench, Supabase Studio, PostHog, Sentry,
GitHub (Primer, command palette, Copilot agent), Claude, ChatGPT canvas, Cursor, v0, Perplexity, Elicit,
Linear's agent guidelines, Figma UI3, and the published systems Atlassian, Carbon, Polaris, Radix/shadcn
and Apple HIG.

**The numbers the published systems agree on** (grade A, read from `@primer/primitives@11.10.0`,
`@atlaskit/tokens@20.8.0`, `@carbon/motion`, `@radix-ui/themes@3.3.0`, `sonner@2.0.8`):

| Aspect | Consensus | AIA today |
|---|---|---|
| Body text | 14/20 (Primer, Atlassian, Radix, Geist); 12/16 small; dense tools set labels and rows in 13 | 14/20 body; 223 arbitrary `text-[Npx]` |
| Control height | 32 default, 28 small, 24 inline; rows 32–40 | buttons 36, small 28 |
| Radius | 6 controls, 8–12 containers; pills only for status | 6 / 8 / 10 tokens; 118 pill uses |
| Motion | hover 70–100 ms, state 150–200, enter 200–300, exit shorter, ease-out on entry | 120 / 180 ms tokens; reduced motion only inside the workbench |
| Elevation | borders at rest, shadows only on what floats | 56 resting shadow uses, 27 nested cards |
| Toast | ~4 s, max 3, an Undo action | UndoToast 8 s (good), one other Toast |

**The 2026 direction** (B/C): calm but dense. Linear's March 2026 refresh dims the sidebar so content
leads and uses one header grammar everywhere (linear.app/changelog/2026-03-12-ui-refresh); Vercel moved to
a resizable, hideable sidebar (vercel.com/changelog/dashboard-navigation-redesign-rollout); PostHog chose
"data density, smaller text, fixed panes" over the SaaS look (posthog.com/blog/posthog-as-a-dev-tool.md);
Figma reversed floating panels after UI3 (figma.com/blog/our-approach-to-designing-ui3/).

**Patterns worth adopting for AIA**, from the 36 the study lists (each with its products and grade):

1. **A global command palette (Ctrl/⌘ K)** that navigates *and* runs actions, ranked by context and
   recency, with shortcut hints and accent-folded matching. Linear, Superhuman, Raycast, GitHub (A/B).
2. **`?` shortcut sheet and G-chords**: `G K` Klienti, `G N` Nastavení, stage keys inside a study. Linear (C).
3. **A dimmed, collapsible rail**: the work leads, the chrome steps back; Ctrl+B toggles. Linear, Vercel (B).
4. **One header grammar** on every surface: title, saved state, view controls, one primary action. Linear,
   Supabase (B).
5. **Peek**: a side sheet for an item from any list (knowledge items, runs, audit rows). Linear, Notion,
   Airtable (B). AIA's ItemInspector already does this for artifacts.
6. **Data tables built for work**: sticky header, right-aligned tabular numbers, hover row actions, a bulk
   bar. Stripe, Airtable, Carbon (B/C).
7. **Filters as tokens** in one bar instead of rows of pill buttons. Vercel, Sentry, Linear (B/C).
8. **Undo over "Are you sure?"** for reversible actions; a typed confirmation for irreversible ones.
   Sonner, Linear; GOV.UK (A/B).
9. **Skeletons for page loads**, inline progress for one module, counts with an estimate after 10 s.
   NN/g (B).
10. **Tooltips with shortcut hints**, delay on first, instant on the next. Emil Kowalski's motion notes (C).
11. **Agent status always readable, with Stop**, a collapsible step log, "thought for N s". Linear AIG,
    GitHub Copilot, Perplexity (B/C).
12. **Per-change Keep/Undo** on every AI proposal; never remove granular review. Hex, Cursor history (B/C).
13. **Graded agent autonomy** (always ask · ask for money or structure · auto-accept text). Notion Agent (B).
14. **Cost visible before, during and after** a paid job; unknown reads unknown. Cursor's backlash when USD
    vanished (C).
15. **Claim-level citations with hover previews.** Elicit, Perplexity (B/C); keep AIA's grounding rule.
16. **Restore as a new version**, never rewriting history. v0, Claude artifacts (B/C).

**What to avoid** (B/C): glass and backdrop blur, gradient and purple buttons, heavy resting shadows,
radius above 16 on app cards, pill-shaped everything, a thick accent border on one side of a card,
icon-in-tinted-square grids, floating panels, marketing-size titles in an app, motion over 300 ms, and
removing review or cost visibility to "simplify".

### 2.3 Art direction (design-taste-frontend)

`draw.mjs --app --kind analytics` dealt three app styles (framed-sheet, accent-ladder, achromatic-ledger);
**accent-ladder** fits AIA: *one hue at full strength only on small marks (the primary button, the data
series, the active icon), its pale tints doing the area work (the selected row and stage, badges, tracks)*.
Seed 722374711, sheet in `.taste-skill/direction.json`. The taste library's own hue (raspberry) is
replaced by the owner's chosen Petrol; the skill's ban on indigo and violet accents is honoured: Petrol's
accent is teal, and violet survives only as the AI mark.

---

## 3. Component gap matrix

States: **custom** (designed for AIA) · **native** (bare browser element) · **missing** · **drift**
(custom but off the system: duplicated, off-token or in conflict with the look). AIA uses no component
library, so there is no "library default" column. Priority: **P1** this upgrade must close, **P2** this
upgrade should close, **P3** later.

| Component | Needed by (flows, §4) | Current state (anchor @ dbaa7720) | Target | P |
|---|---|---|---|---|
| Colour tokens (light, dark) | all | custom, rejected by the owner (`design/tokens.json`) | Petrol palette, one source, both themes, contrast-checked | P1 |
| Type, spacing, z-index, motion tokens in Tailwind | all | drift: only colour, font family and radius reach Tailwind; 223 `text-[Npx]`, 446 off-grid spacings | role-named type utilities; spacing and z-index scales | P2 |
| Button (primary, secondary, quiet, danger, AI with amount) | all | drift: 36 px/14 px, no danger, AI with a glow ring (`rehome/ui.tsx:34,57`); 171 hand-rolled buttons | 32 px/13 px, five variants, amount slot, loading state | P1 |
| Checkbox | knowledge bulk select, intake, profile, Lead, design review, answerability | **native** ×7 (`KnowledgeLibrary.tsx:170`, `AnswerabilityGate.tsx:94` bare) | custom, keyboard, indeterminate | P1 |
| Radio group / choice cards | run population and persona source, memory reuse | **native** ×5 bare (`ExecutionSteps.tsx:959-997`, `MemoryStudy.tsx:212`) | custom radio cards | P1 |
| Select | settings, sociomapping, results | **native** ×5 + shared native `Select` (`rehome/ui.tsx:134`) | button + listbox, type-ahead | P1 |
| Disclosure (details/summary) | results, methodology, interpretation, map | **native** marker on 43 of 47 | one Disclosure with a caret | P2 |
| Range slider | map relief | **native** bare (`ObjectMapView.tsx:333`) | accent-coloured, labelled | P3 |
| Tooltip | rail, Lead, map, spend | **native** `title=` ×96 | one Tooltip with shortcut hint, delay-then-instant | P2 |
| Focus ring | all | **native** on 201 of 315 interactive tags | one global `:focus-visible` ring | P1 |
| Scrollbars | panes, tables | **native** everywhere but one class | thin, token-coloured | P3 |
| Command palette (Ctrl/⌘ K) | navigate, create, jump to stage | **missing** (a section search exists only in Settings, `SectionMenu.tsx:189`) | global palette: clients, studies, stages, settings, actions | P1 |
| Shortcut sheet (`?`) and `Kbd` | expert use | **missing** | `?` dialog; `Kbd` in menus and tooltips | P2 |
| Status glyph and pill | navigator, cards, tables, runs | drift: 8 drawings, icons as status, squares, a diamond (`workbench/Glyph.tsx:14`, `rehome/ui.tsx:85`) | one StatusGlyph (circles), one status pill | P1 |
| Chip / tag | knowledge labels, register, filters | drift: ten forms, radii 2–999 | one Chip (24 px, radius 6) | P2 |
| Note / callout | errors, waits, context | drift: 244 hand-rolled boxes; no component | one Note: info, you, fault, signal, ai | P1 |
| Card / section | all | drift: `CARD` + 5 copies; 27 nested cards rendered | one Card, one Section; no nesting | P2 |
| Table | results, settings, audit, knowledge | drift: 36 ad-hoc tables, no sticky header | one Table: sticky header, tabular numbers, row hover | P1 |
| Segmented control | filters, views, options | drift: 9 pill-row menus, an iOS-style segmented (`step.tsx:217`) | one Segmented (square cells) | P1 |
| Tabs | methodology, results views | drift: three looks | one Tabs | P2 |
| Switch | settings, Lead auto-accept | drift: three implementations | one Switch | P2 |
| Dialog / confirm | consequential actions | custom (ConfirmDialog, AskDialog) | keep; AskDialog's money use moves to SpendDialog | — |
| SpendDialog (money) | every paid start, retry, Deep Research | custom but **0 call sites** (`ui/SpendDialog.tsx:60`) | used for every paid confirmation | P1 |
| Toast | saves, undo | custom (UndoToast), plus a second Toast (`rehome/ui.tsx:286`) | one Toaster with Vrátit | P2 |
| Skeleton | page and panel loads | **missing** (`Loaded` shows text) | skeleton rows and blocks; no shimmer under reduced motion | P1 |
| Empty state | lists, areas | custom `Empty` + 24 hand-rolled | one EmptyState: sentence + one action | P2 |
| 404 / not found | unknown URL, unknown stage | **native**: Next's English 404 (no `not-found.tsx`) | AIA's own page in Czech | P1 |
| Loading route | route changes | **missing** (no `loading.tsx`) | skeleton of the shell | P2 |
| Thinking / agent status | Lead, runs | drift: CSS dots in the Lead (`LeadPane.tsx:505`); ActivityOrb elsewhere | ActivityOrb everywhere; Stop and step log | P2 |
| Design-system page | builders | **missing** | internal `/app/design-system` | P1 |
| Notifications | finished runs, approvals | **missing** (counts only) | a bell / activity tray | P3 (needs a backend event feed) |

---

## 4. Flow gap matrix

Columns: what the flow has today (anchored in the inventory) · what the category expects (§2) · what is
missing. ✓ present · ~ partial · ✗ missing.

| Flow | Has today | Category expects | Missing steps and states |
|---|---|---|---|
| F1 Sign in / out | sign-in with retry and loop handling, denied view, the launch film | session expiry handled everywhere | ✗ a write after the session expired shows a raw error instead of going to login (all but 3 files) |
| F2 Create a client | AskDialog name prompt → navigate | progress, success, recovery in words | ✗ no busy state · ✗ no success message · ~ raw `e.message` |
| F3 Intake (Přidat podklady) | sheet, per-file reading, retry, filing | review before save | ~ no summary step before saving |
| F4 Knowledge | add, file, label, approve, history, undo for organizers | bulk actions, peek, remove/retire | ✗ no retire or delete of an item (no API) · ~ bulk only for placement |
| F5 Create a study | AskDialog → navigate | as F2, plus a template or sample study | ✗ busy · ✗ success · ✗ sample study for a first run |
| F6 Pipeline | eleven stages, autosave, readiness, run, progress, results, map, analysis, report | review before launch, cost before launch, progress with steps, citations, approval | ✗ paid confirmations as plain text instead of SpendDialog · ✗ map snapshot and approval UI (RD4) · ✗ per-question CSV/XLSX tables UI (RD12) · ✗ Next 404 for an unknown stage · ~ nothing in route transitions |
| F7 Research Lead | hatch, greeting, messages, queue, edits accept/dismiss, auto text edits with Vrátit, cards, Pamatovat si | status with Stop, step log, per-change review, cost on the card | ✗ a turn parked on the budget has no way out from the pane (points to "the inspector") · ✗ thinking shown as CSS dots |
| F8 Deep Research | start with cost, events, retry, lift, bundle, verified source | plan before run, citations | ~ text confirmation instead of SpendDialog |
| F9 Project memory | search, read-only past study, reuse | — | ~ bare radios for "reuse into" |
| F10 Settings | members, roles, budgets, methodology, prompts, Deep Research rules, deletion | — | ~ native selects; ~ tables without sticky headers |
| F11 Simulations | read-only frame saying not in AIA | — | ✗ no way to create one (product decision, not this upgrade) |
| Global | — | Ctrl/⌘ K, `?`, notifications, first-run guidance | ✗ command palette · ✗ shortcut sheet · ✗ notifications · ✗ guided first study |

---

## 5. Audit and critique findings

### 5.1 Tool results (before)

| Tool | Result | Notes |
|---|---|---|
| taste `lint.mjs --app apps/web/src` | **38 FAIL, 263 WARN** (557 files) | FAIL: micro-labels ×10 (uppercase tracked labels, mostly legacy `/studies`), gradients ×9 (the front door's dot field, map overlays, workbench), emoji/unicode as UI ×19. WARN: mono ×167 (ids and money: defended where they are ids), shadows ×56, glass ×11 (map panels), decorative numbering ×13 (tests and the numbered sections, which encode real order) |
| taste `inspect.mjs --app` Klienti | 0 FAIL, 2 WARN | a 40 % empty first screen; the 40 px hero title on an app screen |
| taste `inspect.mjs --app` /login | 1 FAIL, 1 WARN | the front door's dot field (a gradient, brand identity: defended) |
| impeccable `detect` (static) | 4 | bounce easing in the rail, a 4 px top border on rounded methodology cards, a side-tab accent in the workbench |
| impeccable `detect --cdp` (rendered, 11 screens, 1440) | **57** | nested cards ×27, stragglers ×8, 11 px text ×6, bounce easing ×5, flat hierarchy ×4, undersized UI text ×3, first-viewport column overflow ×2, accent border ×1, skipped heading ×1; **no contrast failure** |

### 5.2 Audit health score (impeccable rubric, before)

| # | Dimension | Score | Key finding |
|---|---|---|---|
| 1 | Accessibility | 2 | browser focus ring on 201 controls; 96 title-only tooltips; bare radios and checkboxes; reduced motion only in the workbench |
| 2 | Performance | 3 | no evidence of thrash; numba warm-up is server-side; map canvases are bounded |
| 3 | Theming | 2 | one token source, but 223 arbitrary sizes, 86 raw hex in map code, a second zinc/amber system on `/studies`; owner rejects the palette |
| 4 | Responsive (desktop band) | 3 | no overflow at 1280–1920; at 1280 the Lead pane leaves ~800 px for the artifact |
| 5 | Implementation integrity | 1 | systemic drift: ten chip forms, eight status drawings, 244 hand-made notes, 36 tables, 171 buttons |
| | **Total** | **11/20** | **Acceptable: significant work needed** |

### 5.3 Ranked findings (user impact first)

The hands-on walkthrough (`scratchpad/walkthrough.md`, summarised here) and the audits agree on these:

1. **P1 · The palette reads dated and is disliked by the owner.** Cool grey ground, indigo, violet AI,
   coral, a rainbow of nav tints. → Petrol tokens (§6), wayfinding tints dropped from the chrome.
2. **P1 · No keyboard way around.** No command palette, no shortcuts outside a few fields; moving between
   a client, a study and a stage is all mouse. → Ctrl/⌘ K palette, `?` sheet.
3. **P1 · Paid starts confirm as plain text.** The money dialog built for this has no caller; the amount,
   the budget left and the threshold are a sentence. → SpendDialog on every paid start.
4. **P1 · Inconsistent controls everywhere.** Pill rows as menus, three switch and tab looks, native
   selects, radios and checkboxes on decision points. → one control set.
5. **P1 · Dead ends.** Unknown URLs and stage slugs show Next's English 404; a Lead turn parked on the
   budget has nowhere to go; an expired session on a write shows a raw error. → own 404, a budget link,
   one session handler.
6. **P2 · Cards on cards.** 27 nested cards on 11 screens; resting shadows; heavy chrome around little
   content. → flat sections, borders at rest.
7. **P2 · No feedback on create.** New client, new study: nothing while it runs, no success. → busy state and toast.
8. **P2 · Loading says "Načítám…" in text.** → skeletons.
9. **P2 · 96 hover-only tooltips**, invisible to keyboard users. → Tooltip component.
10. **P3 · Scrollbars, disclosure triangles and the range slider are the browser's.**
11. **P1 · Audience filters do not reach the run.** The walkthrough set filters on Cílová skupina and the run
    recorded none applied; the screen says nothing about it. → say it where it is set (the selection
    receipt already exists, `respondentReceipt`), and keep the backend fix with its owner.
12. **P1 · The stage navigator says "nezačato" for stages that have results.** Sociomapa, Analýza and Zpráva
    read as not started after a finished run. → the stage state reads the run, and the study bar names
    the run the stage stands on.
13. **P1 · "Spustit výzkum" is ~2 800 px down at 1280×720.** → the study bar's gate and Přehled studie put
    the run one click from every stage.
14. **P1 · Accepting a Lead edit gives no sign of where it went**, and red dots on the conversation have no
    legend. → ChangeReview flashes its target; the dots become the status vocabulary.
15. **P1 · Questions cannot be reordered.** → drag handle plus Alt+↑/↓ on every ordered list.
16. **P1 · Settings has no visible section list at 1280.** The ⌘K section menu is the only way. → the menu
    stays, and the global palette reaches every section too.
17. **P2 · The artifact pane is ~770×555 px at 1280×720** beside the Lead. → the Lead pane at 360 px from
    1280, a focus mode that hides it.
18. **P2 · Raw codes and English reach the screen** (e.message, HTTP codes, user and run ids, OPEN /
    CLASSIFIED, `e3`). → Stavy obsahu rule, below.
19. **P2 · Opening the Run stage saves a design revision.** → opening never writes.
20. **P2 · Money formatting mixes "11.20" and "11,20"; the avatar shows "K(".** → one formatter; initials
    from letters only.

### 5.4 Interaction inventory (27 Oct 2026)

Two code reads of every interaction in `apps/web`: the client workspace with Settings and the shared controls,
and the workbench with its eleven stages. Each recorded trigger, states and words, feedback, confirm or undo,
keyboard and file:line. The page-owning design sessions were asked the same questions; the per-screen
sessions were inactive, so the code is the source. What repeats, and what differs:

| Behaviour | Today | One rule (Design System v3, Interakce) |
|---|---|---|
| Saved state | 3 s in InlineText; never in Stepper; never cleared in Access; until the next edit in Profile; none on four toggles | Ukládám… → Uloženo 3 s → Neuloženo – Zkusit znovu, everywhere |
| Undo | 8 s for folders, labels and member changes; none for contacts, approvals, bulk filing, client status, intake rows | reversible acts at once with Vrátit 8 s |
| Confirm | ConfirmDialog in four places, inline panels in prompts, AskDialog for money in the workbench | ConfirmDialog for the irreversible, SpendDialog for money, InlineConfirm (Esc keeps) for drafts |
| Money | SpendDialog used nowhere; budgets typed into number and free-text fields, a bad value silently ignored; AI proposals start unconfirmed | SpendDialog on every spend; amount on the button |
| Keyboard | arrows save at once in five chip groups and every Stepper press saves; no arrows in three lists; no Esc in four surfaces | arrows move, Enter chooses what saves or spends; Esc inside out |
| Search | 300 ms debounce in two searches, instant in eight | 300 ms everywhere |
| Errors | raw `e.message`, "HTTP 409 · code", ids | one Czech sentence + Zkusit znovu; detail under Technické údaje |
| Selects | three that act on change | a select chooses, a button acts |


---

## 6. Design direction

**Petrol, calm and dense** (accent-ladder, dealt seed 722374711, mapped onto the owner's choice).

- **Colour.** True neutral greys (light ground `#f6f7f8`, cards `#ffffff`, wells `#eef0f2`; dark ground
  `#0e1113`, cards `#15191c`). One accent, **petrol** `#0f6577` (dark `#4fb2c3`), at full strength only on
  small marks: the primary button, the selected stage's underline, links, focus, a running process, the main
  data series. Its pale tints (`#e1eff2`, `#f1f7f8`) carry selected rows and stages. **Iris** `#6650d8`
  only for the Lead and paid AI starts. **Orange** `#ff9050` (dark `#ffa45c`) only for what needs this person; **slate** for
  waiting on others; **crimson** `#c22b2f` for faults; **green** `#1d7a4e` only for the version in force.
  No amber, no gradients, no glass. Every text pair ≥ 4.5:1 in both themes (checked).
- **The rail goes quiet.** It follows the theme instead of staying graphite: the page ground, grey icons, the
  active item a raised tile. The colourful nav tiles go.
- **Type.** IBM Plex Sans stays (the owner's brand): 14/20 for prose and fields, 13/18 for labels, rows and
  chrome, 12/16 for single-line metadata only. Titles 20/26 in a study, 24/30 on top-level pages; the 40 px
  serif hero shrinks to 28/34 (taste: no landing-page titles in an app). Weights 400/500/600. Tabular
  figures everywhere.
- **Shape and depth.** Radius 6 controls, 8 cards, 10 overlays. Borders at rest; the one shadow only on what
  floats. No card inside a card.
- **Density.** Controls 32 px (small 28), rows 36 (compact 28).
- **Motion.** 100 ms hover, 150 ms state, 200 ms enter, ease-out; everything off under reduced motion.
- **Interaction.** Ctrl/⌘ K palette, `?` shortcuts, tooltips with shortcut hints, undo toasts for
  reversible actions, SpendDialog for money, skeletons for loads.

Why it fits AIA's users: researchers read dense tables and long Czech text for hours; a neutral, low-chroma
ground with one calm accent keeps attention on numbers, and teal reads as "instrument" rather than
"marketing". Orange-for-you is the one warm signal, so what needs action stands out. The Lead keeps a
distinct iris so AI output is never mistaken for evidence.

---

## 7. Execution plan

In order; each item says what done looks like. This PR closes the P1 and P2 items it lists; the rest is
the backlog at the end.

**Tokens**

1. **Petrol palette.** `tokens.json` light and dark replaced; `make web_design` (contrast, palette
   evidence) passes; `check-design.mjs`'s evidence updated for the new pairs; the report's print tokens
   untouched. *Done when every screen renders Petrol in both themes with no raw hex outside the map's
   plot palette.*
2. **Shell and foundations.** The rail follows the theme; the 3 px accent strip goes; one global
   `:focus-visible` ring; reduced motion global; native checkbox/radio/range take the accent
   (`accent-color`) as a floor; thin token scrollbars; `::selection`; summary markers replaced. *Done when
   no screen shows a browser focus ring or the disclosure triangle.*
3. **Type and spacing utilities.** Role-named type utilities (`text-label`, `text-body`, …); hero 28/34;
   stage title 20/26. *Done when the hero and stage titles match §6.*

**Base components** (each: all states, keyboard, ARIA, light and dark, tested where the repo tests UI)

4. **Button**: 32/13, danger, amount slot, loading. 5. **Checkbox, Radio group (with choice cards)**,
replacing the 12 native uses. 6. **Select** as a listbox, replacing the native ones. 7. **Tooltip** and
**Kbd**. 8. **Note**. 9. **StatusGlyph** and status pill unified. 10. **Table** (sticky header). 11.
**Skeleton**. 12. **Segmented** replacing the pill-row menus. *Done when `make test-web`, `make typecheck`
and `make web_unused` pass and the design-system page shows each component in every state.*

**Missing custom components**

13. **Command palette** (Ctrl/⌘ K): clients, studies (from the API the screens already call), stages of
the open study, Settings sections, actions (Nový klient, Nový výzkum, Přepnout motiv); accent-folded
matching; `?` shortcut sheet. *Done when every top-level destination is reachable from the keyboard.*
14. **Design-system page** at `/app/design-system`. *Done when every component in this plan renders there.*

**Missing flow steps and states**

15. **Own 404** for unknown URLs and stages (`not-found.tsx`, Czech, a way back). 16. **Route loading**
skeleton (`app/app/loading.tsx`). 17. **Create client / study**: busy state and success toast. 18.
**SpendDialog on paid confirmations** where the call sites pass the same facts they pass today. 19. **Lead
parked on budget**: a link to where the budget is lifted. 20. **Session expired on write**: one handler that
sends the person to login. *Done when each flow's journey or unit test covers the new step.*

**Screens**

21. Klienti, the client workspace, the study frame and stages, Settings, Můj Vedoucí: Petrol, the quiet
rail, flat sections (no nested cards), segmented filters, the new controls. *Done when the after
screenshots at 1280/1440/1920 in light and dark are clean and the re-run audits improve on §5.1.*

**Backlog (not in this PR)**

- Knowledge item retire/delete (needs an API; none exists).
- Notifications / activity tray (needs an event feed).
- Map snapshot and approval UI (RD4) and per-question CSV/XLSX tables (RD12): the API exists, the client
  functions do not; a feature of its own.
- Peek for every list, filter tokens, bulk bars beyond the knowledge library.
- Graded agent autonomy, Stop and step log in the Lead pane, per-change review on every proposal.
- Simulations creation (a product decision).
- Phone and tablet layouts beyond keeping today's behaviour (out of scope by the owner's word).

---

## 8. What landed outside the code (27 Oct 2026)

- **Design System v3 (Petrol)**: https://claude.ai/artifact/SEEkz1TrFgEZ1yK53Qmas4. It holds:
  - the Petrol tokens, re-measured;
  - core v4.1;
  - new components: CommandPalette, ActivityTray, StudyBar, StudyOverview, AgentStatus, ChangeReview, FilterBar;
  - the **Interakce** group, nine rules with today's breaks at file:line.
- **The three prototype canvases** load core v4.1:
  - Klienti: https://claude.ai/artifact/4dP7Y43dtHcJFkJLD31hFo
  - Výzkumné kroky: https://claude.ai/artifact/3dkKPTDoa1yvK4GCV7PLtJ
  - Nastavení: https://claude.ai/artifact/8W9LR8Ju9BWnR5JACmiWv7

  Every top bar has the ⌘K palette and the activity tray. Every research stage has the study bar. The research canvas has a new **Přehled studie** board: the study's home, with every stage, what waits, the run gate, the money and the last events.
