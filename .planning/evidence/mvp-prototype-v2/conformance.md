# The V2 prototype against AIA: what is built, what is planned, what conflicts

Written 2026-10-19 for `mvp-master-plan.md` chunk 12. The owner calls the prototype "the desired state,
with our real code and engines powering it". This file compares it, row by row, with what AIA has and what
the plans build. Statuses: **BUILT** (AIA has it), **PARTIAL**, **PLANNED** (a chunk builds it),
**UNPLANNED** (no plan does), **CONFLICT** (it differs from a decision already recorded). Anchors for AIA's
side are in `.planning/evidence/mvp-master-traces/` (T1-T5); a `G`/`I` number is a row of
`mvp-master-plan.md` §6 and §5.

## 1. What was walked

The file the owner sent is the single-file build of `prototypes/research-lead-v2` @ `9b50963f`; its
source, `docs/` (capability inventory, boundary matrix, decision log) and a 112-check verify script are
already in the repository. It was opened in the preinstalled Chromium through Playwright at 1440 x 900
(no console error, no network request): all eleven stage tabs; the twenty scenarios the prototype ships
(A to M and X1 to X7), each landing state read; and the panels (Co Vedoucí čte, Kontrakt AI, Oprávnění
hloubkového výzkumu, Rozpis rozpočtu, Přehled fází, Kde jsme?, Podrobnosti, Historie revizí, the study
menu, and the prototype's own documentation page). Click-through flows past a scenario's landing state
(accepting a proposal, raising a budget, a retry round) were **not** walked here: the repository's
`scripts/verify.mjs` covers them, and the master plan's chunk 12 turns each scenario into an acceptance
journey.

## 2. Capability by capability

| # | The prototype shows | Status | AIA today and the plan |
|---|---|---|---|
| 1 | **One persistent Lead conversation per Study**, with history and a return summary | **CONFLICT** | AIA's turns are per researcher and private (`study_lead_repository.py:1-6`); the owner decided each researcher has their own Lead (Q18, Q19, Q26). Master-plan question 3 |
| 2 | "Vidí: Dotazník · revize 14", and **Co Vedoucí čte**: the context hierarchy, what it reads (the artifact, the working copy, pending proposals, step states, the last 20 messages and a summary) and does not read (the whole database, all client documents) | PARTIAL | `freeze_context` exists (96 KB) with no screen that lists it; ADR 0026 decision 2's layers (readiness, outlook, "changed since last turn") are missing (G20); workbench 15-16 |
| 3 | A status message: **Hotovo / Mezery / Rozpočet**, and **Kde jsme?** | UNPLANNED | needs readiness, outlook and trace in the Lead's context (G20) and a command |
| 4 | Message actions (copy, **why this answer: origin**, edit), load older (40 at a time), queued messages, Esc stops, ArrowUp edits the last | PARTIAL | the Lead pane queues and holds messages (CLAUDE.md map); "why" and the origin view are new |
| 5 | **Activity cards typed by actor** (worker, research, compute, lookup, decision), one card updated in place, completed ones folded to "N dokončené činnosti" | PLANNED (workbench 23) | needs step events returned to the Lead: no continuation turn exists (G13) |
| 6 | A **decision card to start a run**: "Spustit sběr dat nad revizí 16", with alternatives ("Spustit s omezeními", "Nejdřív zvýšit n na 430") and the cost line | **CONFLICT** | `approve_request` exists for design jobs only; the owner decided a plan is approved once and the Lead runs its steps (Q14, Q25). Question 2 |
| 7 | **Pokračuj sám / Pokračuj, dokud mě nebudeš potřebovat**: works inside permissions, stops at the first decision that is the person's, a Stop button | **CONFLICT** | workbench D16 and chunk 24 put it after the MVP; the MVP plan puts a plan card in W1. The prototype's version is smaller: no standing budget, it stops at every human decision. Question 2 |
| 8 | Eleven stages in six phases, a glyph and state per stage (accepted, waits for you, running, waits for the provider, **reopened**, needs repair, waits for the previous step); **Přehled fází** with dependency notes; Deep Research outside the order | PARTIAL | `workbench-stages.ts`, `lane.ts` are built; "reopened" needs the impact of a design change after a run, which a study has no surface for (G22) |
| 9 | Header: synthetic-data chip, "Čeká na vás: N" only when pending, **one budget meter** with a breakdown: study limit, spent, remaining, **confirmation threshold "when the run's cap is 25 USD or more"**, research per run (at most 5 USD) | **CONFLICT** | the owner decided two meters and an envelope as a slice (Q20). The prototype is **right about the spend semantics**: ADR 0019's limit is a confirmation threshold and `budget_usd` is the cap; the plan documents are wrong (G11). Question 5 |
| 10 | A version line on every artifact: **"Obsah z revize 12 · studie je na revizi 14"**; older Lead answers marked "Platilo pro revizi 13 · aktuálně 14" | PARTIAL | AIA has a working revision and Design Revisions, not a per-stage content revision; the stale marker needs a definition (G22). Master-plan question 17 |
| 11 | A **proposal shown in the artifact**: "Dopad a pokrytí" (coverage gained, lost, kept), "Ponechat současný stav" / "Použít jako revizi 15", each change with its reason (merge, reword, branching) | PARTIAL | `ProposalReview` is whole-proposal; per-change accept is planned and unchunked (G18); workbench 7 and 17 |
| 12 | **A hand edit autosaved as the working copy**; the Lead notices an overlapping edit and warns "accepting yours makes the proposal stale"; "Přijmout jako revizi 15" / "Zahodit úpravy" | **CONFLICT** | AIA has no path where accepting a working copy creates a revision (hand edits create none, T1 #6), and `proposal_accept.py:117-118` stales every proposal when the head moves (G14, G22). Needs an ADR |
| 13 | **A stale proposal**: the revision advances, rejection, rebuild | BUILT, PARTIAL | dismiss and rebuild through the ledger exist; the stale rule is stricter than shown (G14) |
| 14 | **Protected items**: Set 1 and Q19 locked with the reason; the Lead refuses to propose changes | UNPLANNED | no editor for `sociomap_rating` / `context_objects`; the lock is only in the architecture (G21) |
| 15 | **Research question to decision to measure to analysis to report**, "Celý řetěz", with honest gaps ("Kódování otevřených odpovědí v AIA zatím není") | PARTIAL | `research_trace` links questions to items; the chain beyond that is `deep-research-web-search` 32 (the report evidence graph), unbuilt |
| 16 | **Assumptions A1-A3** with a status; Deep Research evidence attached as a proposal; "Stav předpokladu se mění jen přijetím návrhu" | UNPLANNED | AIA has no assumptions object (the prototype's own documentation says so); a new design-item kind affects `design_items`, the Lead's ops and `research_trace` |
| 17 | Audience filters with counts from LIVE, "náhled jen počty", "Vlastní a speciální panely: V AIA zatím není" | BUILT | `/population/audience-preview` |
| 18 | Dimensions with their persona topic and research-question links; "bez tématu persony" is named | BUILT | `dimensions_unmatched`; the own-dimension chip and its build are not in V2 and are unwired in AIA (G28) |
| 19 | **Sample**: n and quotas by sex x age x region, "Vzdělání se do kvót přidává až od n 700", a Kish n support estimate per object, the smallest sufficient n (about 430), readiness | PARTIAL | `support_forecast` exists for the roster path and is unknown for a panel run; quotas before a run do not exist (G29) |
| 20 | **Fieldwork**: steps labelled deterministic or AI, spent / reserved / run cap / remaining, quality, "Kdo odpovídal" (persona source, population recorded, what was read) | PARTIAL | Progress and the receipt are built; heartbeat, quota-cell fill and the respondent grid are unspecified (G29, I7) |
| 21 | **Straight-liners flagged, not replaced**; replacement shown as "navrženo, v AIA zatím není" | UNPLANNED (wiring) | agrees with the owner's F18; QC is not wired and has three definitions (G27, I6) |
| 22 | **Results**: means on a 1-10 scale with 95 % intervals and Kish n, a suppressed object named, "order only where intervals part"; open answers listed as data, not admitted evidence | PARTIAL | `result-reading.ts` is built; Results reads raw aggregates, not admitted claims, and suppression is decided in the browser (G31) |
| 23 | **Sociomap**: display filters that change only the picture, a pair inspector (r, interval, n, threshold, heights, "line on the map", what it means), objects by height, unmapped with the reason, method status ("approved for clients, this run fictional so internal only") | BUILT | `ObjectMapView`, `object-map-view.ts`, the register; "11 unmapped (no relative preferences)" is what the straight-liner exclusion does |
| 24 | **A labelled interpretation** of a pair and **"Dohledej kontext k této dvojici"**; the evidence explains and never changes the map | PARTIAL | Interpretation Research accepts a pair as a target; the Lead has no card or provider for it (G33, I1); the `interpret_map` worker is new (G16) |
| 25 | A legend with **four things kept apart**: deterministic result, display, interpretation, external context | UNPLANNED (UI) | consistent with the evidence rules; no chunk draws it |
| 26 | **Analysis**: a coverage table per research question, findings F with claims C and sources S, **blocked claims with the reason**, "7 z 8 modulů, Segmenty blokovány", a new round after a failed check (X4) | PARTIAL | the modules, the retry round and `needsRepair` are built; the finding to claim to source chain is shown on the report path only (G31); segments are blocked because `compare_segments` does not exist |
| 27 | **Open-answer coding**: themes with examples, counts from a stored classification | UNPLANNED | "navrženo" in the prototype's own documentation; needs a methodology decision. Question 8 |
| 28 | **Report**: claim chips on every sentence, tracked changes per paragraph, semantic edits (less technical, emphasis, an "overstate" check), "Schválit interně", a client report refused for a fictional run (X7), and **a sentence that claims a comparison with no admitted claim is flagged** | PARTIAL | composition, approval and the refusal are built; `polish_report` is new (G16); a check on a sentence's claim, beyond numbers, is a new rule |
| 29 | **Return after days (M)**: what changed, what finished, what needs attention, the next step, "Na poslední přečtené místo" | UNPLANNED | needs signals, a summary and a last-read marker; depends on question 3 |
| 30 | **Deep Research permission**: approved by the organization on a date; the purposes; approved routes with their class; "only class C queries to public search; a query derived from confidential material inherits its class"; **not allowed: client confidential material in a search, even paraphrased**; limits "5 USD per run, study budget 60 USD, no further confirmation inside these" | **CONFLICT** | ADR 0022 settings and approvals are built. The strict class text is what the owner **deferred on 2026-10-19** (open posture; derived queries are fine). Question 4 |
| 31 | **Deep Research started from the Lead**: a card ("krok 3 ze 6", "DESIGN_RESEARCH / INTERPRETATION_RESEARCH, v rámci schváleného oprávnění, 0,38 USD") | PARTIAL, **CONFLICT** | workbench chunk 25 ("reachable from every stage") is after the MVP (D16) while chunk 23 (the cards) is inside it, and the prototype treats it as core |
| 32 | **Exceptions**: X1 the budget limit and a raise decision; X2 missing evidence; X3 a provider failure parked, the retry the person's; X4 a failed analysis check, a new round; **X5 reopened work: a questionnaire edit after a run**; X6 a methodological restriction refused in place and routed to Metodika; X7 a client report for a fictional run refused | PARTIAL | budget lift, parks, the retry round, Metodika and the refusal are built; X5 needs the impact of a design change on a run (G22); X2's handling is a Deep Research gap record |
| 33 | **AI Interaction Contract** per artifact (readable state, visual actions, domain commands, rejections) and stable ids `data-aia="questionnaire.<section>.<element>"` | PLANNED (workbench 14, 16) | items are keyed by normalised text, so a reword breaks a link (G19) |
| 34 | **Brief**: objectives O, decisions D, context C, materials with a data class | PARTIAL | the Brief stage exists; its items are keyed by text (G19) |

## 3. What the prototype's own documentation lists as gaps to production

The prototype names seven; the plan's answer to each:

| Gap in the prototype's documentation | Where it lands |
|---|---|
| A persistent per-Study conversation needs storage, retention and summarisation | master-plan question 3, then `lead-orchestration` |
| The AI Interaction Contract needs stable semantic ids in `apps/web` and a server-side command registry | workbench 11, 14, 16; G19 |
| Assumption objects, qualitative coding, semantic report edits and respondent replacement are not in the product; each needs a design and a methodology decision | master-plan question 8 |
| `compare_segments` is unavailable; research question 3 and the Segments module stay blocked | `segment-maps-and-drilldown`, the method owner |
| Report proposal kinds and draft numbering need a decision against ADR 0016's revision semantics | master-plan question 10 |
| The Lead's cost per turn is unmeasured; a kill switch and a budget line are needed | `develop-spend-attribution`, an `AIA_LEAD_*` switch in the activation matrix |
| The four supplied exports were not available to the prototype's author | the V3 text in `prototypes/research-lead-v3/` is separate: master-plan question 1 |

## 4. The count

Of 34 rows: 4 BUILT, 16 PARTIAL, 2 PLANNED, 7 UNPLANNED and 7 CONFLICT (rows 13 and 31 carry two labels).
The owner's description, "with our real code and engines powering it", is true for the audience, dimensions,
sample, results, sociomap and run-control halves, and not yet for the conversation, the orchestration and the
working-copy halves, which is where the new plan files of `mvp-master-plan.md` §6.3 go.
