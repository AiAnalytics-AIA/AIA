# The Lead pane: conversation, composer and Lead cards

Scope: the right-hand (or drawer/sheet) Lead pane every research stage shares, as drawn in
`CardsF.dc.html`, `ChatF.dc.html` and the eleven stage boards' `<aside class="lead cfz">` + `chatF()`
(Brief.dc.html:45-108, 185-222 is the reference instance). Decisions R12-R15 (Main.dc.html) apply.
Code anchors are `file:line @ bd0d1ad6` (the develop worktree). The board itself cites `d5d36b25`;
those anchors were re-checked here and the lines below are bd0d1ad6's. Anything not anchored is
marked **hypothesis**. Visual values (colour, radius, size) are left to the coming look contract;
this section names states and content only.

---

## 1. Anatomy: prototype vs `LeadPane.tsx` today

| Part | Prototype (Brief.dc.html, ChatF.dc.html) | Today | Delta |
|---|---|---|---|
| Header | Avatar: the Lead's mark when idle, the activity orb while busy; the Lead's own name ("Ada"); a status line: `Připravena` / `Přemýšlí…` / `Pracuje na <job>`; one settings icon to Můj Vedoucí (Brief.dc.html:46, chatF 192-193) | Static mark, name from `me.lead.name` (LeadPane.tsx:292, 298-300); the **Vidí chip sits in the header** (301-307); Můj Vedoucí link (309); focus toggle or Zavřít (310-318) | Status line is new: `Přemýšlí…` = `session.busy` (LeadPane.tsx:323), `Pracuje na …` = the newest job/run whose step is RUNNING (derivable from `jobs`/`runs` already passed in, LeadPane.tsx:68-100; **hypothesis** that no new field is needed). Orb-in-avatar reuses ActivityOrb. Keep Zavřít/focus toggle (not drawn, but required by the layouts, D21). |
| Timeline | "ChatF": bubbles on a time axis; a day divider `Dnes`; each card has a **node on the axis** that repeats its state (pause = awaits you, orb = running, check = done, amber = waits for budget, cross = failed) (CardsF rules block; ChatF title) | Day dividers exist (`withDayBreaks`, LeadPane.tsx:393; LC19 done); no axis, no node | New: axis + per-item node; the node's state is the same `CardTone` the pill already uses (lead-cards.ts:17). |
| Lead message | "who" row: name, time, `četl revizi N`; prose; view chips `Ukázat: <target>`; follow-up buttons (Brief.dc.html:50-58) | Same content: time + `četl revizi` (LeadPane.tsx:506), Prose (507), view chips (511), follow (521-523), edits link (508-510), self-update (512) | Content matches; restyle only. |
| Person message | Right-aligned bubble; a pointing token prefix (Brief.dc.html:61, chatF `cfSend`) | Bubble with `bubble__ref` focus label (LeadPane.tsx:447-450) | Matches. |
| Thinking | Orb + shimmer row while the Lead thinks (Brief.dc.html:84) | Three-dot `typing` row for a QUEUED/RUNNING turn (LeadPane.tsx:485-490) | Restyle. |
| Cards | Section 2 below | Request card (581-631), self-update (535-579), worker/run cards (LeadCards.tsx) | Section 2. |
| Composer | `+` button (opens menu with tabs **Akce / Přidat / Kontext**), textarea `Zeptejte se Ady…`, send; a removable **token chip** above the row (the chosen action or pointed element); under it the **`Vidí:` line** listing what the next turn will see (Brief.dc.html:86-104) | `@` button (663), quick buttons `Kde jsme?` / `Navrhni úpravy` (664-665), send (666), hint line (669), refchip for focus (653), queue list (644-652) | `+` menu, token chip and Vidí-under-composer are new. The two quick buttons are not in the prototype: drop them (their texts can become Akce items only if they map to a start; they don't, they are plain messages). Keep the queue list (LC5a, not drawn but load-bearing). Keep Enter/Shift+Enter. |
| Vidí | Under the composer, a forward-looking line: `Vidí: <stage> · revize N, znalosti klienta[, moje poznámky]` (chatF `cfCtxLine`) | In the header, backward-looking: the last turn's manifest opens from the chip (LeadPane.tsx:293-307, 320; LeadSees.tsx) | Two different things. Keep LC2's manifest panel (what the *last* turn saw) reachable from the Vidí line; the line itself says what the *next* turn will get. See §3.3. |
| Hatch / unavailable / errors | not drawn (Hatch board optional) | HatchCard (333, 344-357), unavailable notice (334), held/drain retry (325-332) | Keep; restyle. |

Build chunks for §1:

- **LP-1 (new): header status and avatar orb.** Status from `session.busy` and the running job/run. Test: `LeadPane.test.tsx` renders `Přemýšlí…` while `busy`, `Pracuje na Analýza zadání` with a RUNNING `analyze_brief` job, `Připravena` otherwise.
- **LP-2 (new): timeline axis and nodes.** Pure `cardNode(tone)` in lib/lead-cards.ts; test that each `CardTone` maps to exactly one node and the folded row keeps it.
- **LP-3 (new): composer shell.** `+` button, token chip, Vidí line under the composer, quick buttons removed. Test: journey `lead_journey.mjs` at 1440/1100/768/390 finds the menu, the token chip, and no `Kde jsme?` button.

---

## 2. The cards

### 2.0 Shared card contract (CardsF §1 "Anatomie", §2 "Život jedné karty")

Seven parts: (1) kind + icon; (2) the action's title exactly as the registry names it, or `Váš příkaz` for
a typed start; (3) **one** state label; (4) one sentence of what happens and what does not ("nic
nepřepíše"); (5) facts, the first one the stake and the largest (a paid action's `Cena nejvýše`, "horní mez,
ne odhad"); (6) actions: quiet `Teď ne` left, one primary right whose label is verb + **bold amount**; for a
budget lift the amount leads: `+10 USD a pokračovat` (R13); (7) the axis node.

Life (CardsF LIFE): **Čeká na vás** (only state expanded and marked as awaiting) → **Běží** (event log with
times, `Drženo <x> USD`, `Zastavit`) → **Hotovo**, folded to one row: title · `hotovo · <actual> USD` · one link
(`Posoudit` / `Otevřít`) → re-expandable. Side states: **Čeká na rozpočet** (`Potřebuje`, `Zbývá ve studii`,
`+N USD a pokračovat`), **Selhalo** (why in words, `Znovu nejvýše`, `Dosud stálo`, `Zahodit` / `Zkusit znovu`),
**Ponecháno** folded (`ponecháno · nic nespuštěno`, `Rozbalit`), **Zastaveno** folded (`zastaveno · zaplaceno
<x> USD`, `Znovu`). R15: no percentages, only what the backend reports; when step events are off the card says
so and shows only elapsed time.

Today's card frame: `Pill`, `Facts` (LeadCards.tsx:30-47); request card (LeadPane.tsx:593-631); worker card
(LeadCards.tsx:50-91); run card (95-124); run request card (137-226). Pure words in lib/lead-cards.ts.

Cross-card gaps (apply to several cards below):

- **G-keep.** `Teď ne` is page state only (`useState(... "kept")`, LeadPane.tsx:595, 624; LeadCards.tsx:148, 216): a reload shows the card awaiting again. The server has no "dismiss request" for a Lead turn's request (routes LeadPane relies on: lead.py `/lead/turns/{id}/edits`, `/self-update`, `/request`, `/withdraw`, lines 680-760). Need a ledger-recorded `dismiss` on `/lead/turns/{id}/request`.
- **G-ceiling.** A design job's ceiling before start is not served: `AgentJobResponse` has `actual_cost_usd` only (research.py:3740-3761); the ceiling exists only inside the 409 `cost_confirmation_required` details (lead.py:466-473) and as the setting `ai_research_reservation_usd` (lead.py:757). Same for the analysis retry: `/analysis/retryable` returns modules, no ceiling (research.py:2023-2050).
- **G-held.** `Drženo` (open hold) for a job is not served (no `reserved_usd` on `AgentJobResponse`, research.py:3740-3761). A run's `spend.reserved_usd` is served only on `GET …/research/runs/{id}`, null on a listed run (CLAUDE.md §2), and the card reads the listing (Workbench.tsx:789-790).
- **G-lift.** The lift routes take the **absolute** new budget (`BudgetLiftRequest.budget_usd`, research.py:1821-1827; job 3956-3977; run 1830-1858). `+10 USD` must be computed as current budget + 10 on the client, and `Potřebuje 0,90 USD` (what the waiting step needs) is not served: `ResearchStepResponse` has no reservation field (research.py:352-388).
- **G-spend-modal.** `SpendDialog` (components/ui/SpendDialog.tsx:1-60) has no consumer; the Lead's confirmation uses a text `confirm(...)` (Workbench.tsx:536-540). R13's "amount in the button" belongs in the card; the threshold confirmation should be SpendDialog.
- **G-stop.** No `Zastavit` on any card today; cancel routes exist for jobs (research.py:3936), runs (1802) and Deep Research (deep_research.py:701).
- **G-fold.** No folded row; every decided card stays full size (`is-decided` class only, LeadPane.tsx:606).

### 2.1 Návrhová úloha (design job) — `analyze_brief`, `build_questionnaire`, `optimize_questionnaire`, `propose_audience`, `suggest_dimensions`

States drawn: all seven of §2.0 (CardsF LIFE uses this card for Čeká na vás, Běží, Hotovo, Selhalo).

| Field / event | Provided? |
|---|---|
| Title from action | yes: `ACTION_LABELS` (lead-cards.ts:91), same labels as the command registry (lead_commands.py:73-86) |
| One-sentence lead ("nic nepřepíše") | static copy per action: **new** copy |
| `Cena nejvýše` before start | **no** (G-ceiling) |
| `zbývá v rozpočtu` | yes: `readBudget` (budget-line.ts:41), already used by the run request card (LeadCards.tsx:155) |
| `Výsledek: návrh na kroku X` | yes: `JOB_STAGE` (lead-cards.ts:26-35) |
| Approve | yes: `POST /lead/turns/{id}/request` with `confirm_cost_usd`, `workspace_revision` (lead.py:125-137, 718-760); 409 stale_card, cost_confirmation_required, cost_ceiling_unknown; 422 agent_context_too_large (lead.py:455-515) |
| Running log: `Worker krok převzal` | yes: ATTEMPT_CLAIMED (step-activity.ts:90-91) |
| `Dotaz odeslán modelu` / `Model odpověděl · tokens · USD · s` | only with `AIA_AI_STEP_EVENTS` (ai_step.py:229-232, 263-273; flag ai_runtime.py:498-502, 682; develop default false, deploy/develop/docker-compose.yml:294) |
| `Krok dokončen` | yes: STEP_SUCCEEDED (step-activity.ts:92-93) |
| Feed route | yes: `GET …/agent-jobs/{id}/events` (research.py:3922); live reader `useStepActivity` (LeadCards.tsx:61) |
| `Drženo` while running | **no** (G-held) |
| Actual cost after | yes: `actual_cost_usd` (research.py:3756; lead-cards.ts:95) |
| Proposal state pending/accepted/dismissed/superseded | yes (research.py:3757-3759; lead-cards.ts:49-54) |
| `Posoudit` | yes: `onOpen` → review (LeadCards.tsx:85) |
| Waits for budget + lift | state yes (lead-cards.ts:41); lift route yes (research.py:3956); card today says "raise it in the inspector" (LeadCards.tsx:68): **G-lift** |
| Failed: why + `Znovu nejvýše` + `Dosud stálo` | why: `error_message` (lead-cards.ts:105) / `error_reason` (research.py:373); retry = `/rebuild` (research.py:4008) on newest revision; ceiling **no** (G-ceiling); cost so far yes |
| `Zastavit` | route yes (research.py:3936); **no button** (G-stop) |
| `Teď ne` persisted | **no** (G-keep) |

Chunks:
- **research-lead-workbench#23 (finish the job half) / LO21c:** restructure `WorkerCardView` + `RequestCard` into one card with the §2.0 slots; fold on done/kept/stopped. Test: `LeadCards.test.tsx` (new) renders each lifecycle state from fixture jobs; a COMPLETED job renders the folded row with `hotovo · 0,52 USD` and one `Posoudit`.
- **LP-4 (new, API): `ceiling_usd` on a prepared request.** `GET /lead` turns carry, for an `agent_job` request or typed command, `ceiling_usd` (= reservation; null when unknown, never 0). Test: `test_lead_router.py` — a turn with an agent_job request answers `ceiling_usd == AIA_AI_RESEARCH_RESERVATION_USD`; unset reservation answers null.
- **LP-5 (new, API): `reserved_usd` on `AgentJobResponse`.** Test: a running job's open hold shows; a settled one 0; unknown null.
- **LP-6 (new): Zastavit on job cards** via `/agent-jobs/{id}/cancel`, folded as `zastaveno · zaplaceno <actual>`. Test: component test posts cancel and renders the folded row.
- **LP-7 (new, API+web): dismiss a Lead turn's request** (ledger row, `request_decision.status = dismissed`), card folds as Ponecháno after reload. Test: router test (dismiss then GET shows it; approve after dismiss is 409) + component test.
- **LP-8 (new): budget lift in the card** (`+N USD a pokračovat`, amount first) through SpendDialog kind "Zvýšení rozpočtu studie", posting absolute `budget_usd`. Test: SpendDialog consumer test computes `budget_usd = budget + N` and never sends a lower one.
- **LP-9 (new): step-events-off note.** When a running job's feed has only ATTEMPT_CLAIMED, the card says events are not reported and shows elapsed time. Test: `step-activity.test.ts` / card test with a feed of one ATTEMPT_CLAIMED.

### 2.2 Rada (advice) — `critique_design`, `design_copilot`, `answer_memory`

Drawn only in the requirements matrix (CardsF §6): stages per contract; `Cena nejvýše`; "nic nemění"; stream
as a job; after: an answer to read (knowledge only approved, with sources).

| Field | Provided? |
|---|---|
| Advice classification | yes: `ADVICE_ACTIONS` (lead-cards.ts:20), stage null (32-34) |
| `Otevřít odpověď` | yes (LeadCards.tsx:85); result route `GET …/agent-jobs/{id}/result` (research.py:3980) |
| Answer inline in chat | **no**: opens elsewhere (`onOpenJob`); **hypothesis** that the matrix wants it in the card |
| Ceiling | **no** (G-ceiling) |

Chunks: shares 2.1's. **LP-10 (new, optional):** show the advice answer's first paragraph in the folded card, full in the review. Test: component test with a recorded `answer_memory` result (recorded_models.py DESIGN_ANSWERS).

### 2.3 Výzkumný běh (research run) — launch card and streaming card

Launch card drawn (CardsF KINDS "Běh výzkumu · revize 8"): `Cena nejvýše 14,60 USD · horní mez, ne odhad`;
`Rozpočet studie: zbývá 38,80 USD z 50,00`; `Spustit výzkum 14,60 USD`. Typed variant ("Spusť výzkum", Váš příkaz)
same facts. Streaming card (CardsF §5): 16-step strip, phase labels (sestavení, sběr, agregace · mapa,
analýza, zpráva), `Krok x z 16 · <name>`, tag `AI model` / `kód`, current line (`Odpovědělo N z 400
respondentů` or `AI analyzuje modul X, kolo n`), eight module chips during analysis, `Utraceno` with `strop
běhu … horní mez, ne odhad`, link `Průběh`. Special: waits for budget (one lift per run), `Potřebuje opravu`
(module BLOCKED), cancelled.

| Field / event | Provided? |
|---|---|
| Model-prepared launch: readiness, ceiling, threshold, source, existing run | yes: `RunRequestCard` (LeadCards.tsx:137-226), `runRequestPlan` (lead-cards.ts:185-204), `budgetFacts` (247-255) |
| Typed launch ceiling | **not shown**: typed run card says "Spustí se výzkum s výchozím nastavením" with no ceiling (LeadPane.tsx:618-619); the data is there through `prepareRun` — reuse RunRequestCard |
| Step list, done/total | yes from listing with steps (lead-cards.ts:136, 145) |
| Running step name, AI/code | yes: `stepLabel` (lead-cards.ts:144), `researchStepWork` (activity-orb.ts:76-79) |
| Respondents per 10 | yes: `fieldwork_progress` every `progress_every = 10` (ai_fieldwork.py:159, 505-506; fieldwork_events.py:85-92), heartbeat 30 s (fieldwork_events.py:51); folded `progress` (step-activity.ts:118-124, 187-192) |
| Module + round | yes: `progress("AI analyzuje modul", module, turn)` (analysis.py:355; step-activity.ts:141-143) |
| Per-module state for 8 chips | yes: the eight `analysis_*` steps' status and `analysis_outcome` (research.py:377-380) |
| `Utraceno` + `strop běhu` | served only on single-run GET (`spend`, `cost_ceiling`; CLAUDE.md §2); card uses listing → **G-held** |
| Budget lift (one per run) | route yes (research.py:1830-1858); `Potřebuje` **no** (G-lift) |
| BLOCKED module → `Potřebuje opravu` | yes: `needsRepair` (CLAUDE.md §2 research-execution.ts) |
| Cancel | route yes (research.py:1802); no button (G-stop) |

Chunks:
- **research-lead-workbench#23 (run half):** RunCardView becomes the streaming card: step strip, `Krok x z N`, AI/kód tag, the line, module chips. Test: `lead-cards.test.ts` `runCard` on a fixture run in fieldwork (40/400) and in analysis (module Hypotézy, kolo 2); no `%` anywhere in the output.
- **LP-11 (new): run spend on the card** by reading `GET …/research/runs/{id}` for runs whose card is expanded (not the list). Test: card test shows `Utraceno` from `spend.spent_usd` and `?` for uncertain calls, never 0.
- **LP-12 (new): typed `Spusť výzkum` renders RunRequestCard's facts** (ceiling, budget, source) before approval. Test: typed turn with `command: "research_run"` renders `Cena nejvýše` from readiness.
- **LP-8 / LP-6** apply (run lift, run cancel).

### 2.4 Opakování analýzy (analysis retry) — typed `Zopakuj analýzu`

Drawn: request (`Zopakovat Hypotézy`, `Cena nejvýše 0,90 USD`, `Hotové části zůstanou, neplatí se znovu`) and
streaming (module chips, the reused ones light, the retried one marked; log `7 modulů převzato z původního
běhu, bez platby` / `AI analyzuje modul Hypotézy, kolo 2`; `Data: původní sběr, ověřený SHA-256`).

| Field | Provided? |
|---|---|
| Typed start | yes: ANALYSIS_RETRY (lead_commands.py:85); `analysis_retry_run` in GET /lead (lead.py:285-287); 409 analysis_retry_target_moved (lead.py:488-494) |
| Which modules | yes: `/analysis/retryable` (research.py:2023-2050) — **not read by the card** today (LeadPane.tsx:613-617 states it in prose) |
| Ceiling | **no** (G-ceiling) |
| Modules reused, no payment | reuse is real (retry_failed_modules, CLAUDE.md §2 analysis_results.py); event "převzato" **no** such event (**hypothesis**: the retry run's skipped/SUCCEEDED steps can be read as reused) |
| Dataset by SHA-256 | yes: FrozenDataset (CLAUDE.md §2 application/research.py) — not on the run response (**hypothesis**) |
| From the Lead model (not typed) | **no**: `LeadOutput.request` has no `analysis_retry` kind (domain/research_lead.py:328-331); approve of any non-agent_job model request is `NotAPaidRequest` (application/research_lead.py:1137-1140) |

Chunks: **LP-13 (new):** the card reads `/analysis/retryable` for the named run and lists the modules. Test: card test with `modules: ["hypotheses"]` titles it `Zopakovat Hypotézy`. Ceiling: LP-4 extended to analysis retry. Streaming reuses 2.3.

### 2.5 Hloubkový výzkum (Deep Research) — design and interpretation

Drawn: request (`Rešerše k návrhu`: `Cena nejvýše 1,20 USD` from the quote; `Zdroje: Wikipedie CZ/EN zdarma ·
Brave placeně`; `Data: jen třída C`) and (`Rešerše k výkladu`, target `dvojice na mapě běhu 21. 10.`, frozen by
SHA-256); streaming (six-step strip plán, stopy, sloučení, ověření, shrnutí, zveřejnění; current step words;
last 4 tool calls in AIA's words; `Zatím N volání webu · M dotazů modelu`; `Cena nejvýše … utraceno …`;
`Zastavit`). Special: `live_settings_unapproved`, parked until the design is classified. After: sealed bundle,
"Ověřeno, přidat zdroj", "Použít ve zprávě". **Today: no card at all** (R12, R15; CardsF §5 "V chatu se tento
běh dnes neukazuje vůbec").

| Field / event | Provided? |
|---|---|
| Lead model prepares it | yes, `DesignResearchRequest` / `InterpretationResearchRequest` (domain/research_lead.py:317-326) |
| Approve starts it | **no**: `NotAPaidRequest` (application/research_lead.py:1137-1140); web just opens a stage (Workbench.tsx:516-521; LeadPane.tsx:585-586) → LO5a.2 |
| Typed start | **no** command (lead_commands.py:75-86) → LO5a.3 |
| Quote: ceiling by kind, routes, missing live settings, threshold, start_verdict, would park | yes, read-only `POST …/deep-research/quote` (deep_research.py:550; ceiling 522, 561) |
| Interpretation target candidates | start route exists (deep_research.py:644); a code-built candidate list for the card **no** → LO5a.1 |
| Runs in the conversation | **no**: timeline places turns, jobs, research runs only (lead-cards.ts:150-176; Workbench.tsx:789-790) |
| Step events | yes: `deep_research_plan/replan/turn/track/investigated/merged/verified/synthesized/published` (plan.py:381; lead.py:567; investigate.py:183, 269; review.py:165, 384; publish.py:400, 574), worded in cs.ts:3286-3296 |
| Tool calls | yes: `deep_research_tool_<outcome>` per journaled call (tooling.py:96; runtime.py:385), outcomes dispatched/succeeded/failed/uncertain/refused/cached worded (cs.ts:3305-3312); count folded as `toolCalls` (step-activity.ts:220) |
| Which URL / why refused | **no** in words: payload has `tool`, `outcome`, `route_id`, `track_id`, `request_fingerprint`, `note`, costs (tooling.py:157-182), no URL; CardsF calls this "mezera pro vývoj" |
| Model request count | only with `AIA_AI_STEP_EVENTS` (**hypothesis** that DR agents announce: `announce=` is wired for research_agents, analysis, lead, client_source_proposals only, research_agents.py:237, analysis.py:594, research_lead.py:188, client_source_proposals.py:198); `deep_research_track` carries `model_requests` (cs.ts:3290) |
| Feed route | yes `GET …/deep-research/runs/{id}/events` (deep_research.py:772); web `deepResearch.events` (api.ts:1588), `deepResearch.runs` (api.ts:1586) |
| Spend, cancel, budget lift | cancel (deep_research.py:701), budget (730); `utraceno` per run: **hypothesis** that `DeepResearchRun` carries it |

Chunks (all existing): **LO5a.1** (requests and context), **LO5a.2** (approve starts DR; ceiling from quote),
**LO5a.3** (typed DR starts), **research-lead-workbench#23b** (request + running card: quote, orb, six steps,
tracks, waits, resume, lift, Zrušit), **#23c** (finished card: coverage, findings with "Ověřeno, přidat zdroj",
"Zkontrolovat návrh", "Použít ve zprávě", failure + "Zkusit znovu"), **#26f.1** (stage DR starts removed, R12).
Tests: 23b — `deep_research_journey.mjs` extended: the run appears as a card in the Lead pane with its six steps
and a tool line, zero paid calls; `lead-cards.test.ts` `deepResearchCard` on a recorded feed. LO5a.2 —
router test: approving a `design_research` turn starts a run and writes the ledger row, 409
`live_settings_unapproved` with missing settings. **LP-14 (new, executor):** add the fetched host (not the
full URL; class C only) and a refusal reason code to the tool event payload. Test: `test_deep_research_journey.py`
asserts each `deep_research_tool_refused` event carries `reason`.

### 2.6 Váš příkaz (typed start)

Drawn: eyebrow `Váš příkaz`, "Rozpoznáno přesně podle textu, model se na nic neptal. Stejné kontroly jako na
<stage>", the target card's facts and button.

Provided: matcher (lead_commands.py:91-137), 10 commands (75-86), served in `GET /lead` `commands`
(lead.py:282-283, 536-544) but **not consumed by the web** (no reader of `.commands` in apps/web/src); card via
`commandRequest` (lib/lead.ts:75-81) + `RequestCard typed` (LeadPane.tsx:589-631); approval path
`approve_chat_start` (application/research_lead.py:1110-1130), ledger `chat_start` (approval_ledger.py:56),
wallet when on (`wallet_enabled`, lead.py:284-285).

Chunks: covered by 2.1/2.3/2.4 (a typed card is the target card with the `Váš příkaz` eyebrow). **LP-15
(new):** the composer builds its Akce list and token phrases from `GET /lead` `commands` instead of literals.
Test: `LeadPane.test.tsx` with a two-command `commands` array shows exactly those two items.

### 2.7 Zapamatovat si (remember / self_update)

Drawn: `Pro všechnu vaši práci`, the note quoted, `Kam: USER.md · Můj Vedoucí`, `Cena: zdarma`, `Zahodit` /
`Pamatovat si`. Matrix: which file, all clients or this one; stale when the file changed meanwhile.

Provided: all of it — `SelfUpdate` (LeadPane.tsx:535-579), client notes applied with the turn (540-545), waiting
personal/file changes (546-547), decide route (lead.py `/self-update`, 701-716), stale files (553, 567-569).
Gap: the drawn `Kam` fact (file name) is present per item (565) but not as a card fact. Chunk: restyle under
LO21c. Test: existing self-update tests + snapshot of the facts row.

### 2.8 Návrhy změn (edits)

Drawn: `3 změny v Návrhu`, "Hypotéza H2, otázka VO3, znění Q7. Rozhodujete po jedné v liště nad krokem",
`Kde: lišta na kroku Návrh`, `Cena: zdarma, už zaplaceno`, `Zahodit vše` / `Otevřít lištu`. Matrix: accepted /
dismissed; auto-accepted with `Vrátit`; `stale_turn`; locked Sociomap input.

Provided: the edit count link only (LeadPane.tsx:508-510); the bar is in the artifact (`EditsBar`,
Workbench.tsx:846, 879-920; auto-accepted bar 921); decide route with `indices`, `decision: dismiss`
(lead.py:111-122) so `Zahodit vše` is one call; item names via `targetLabel` (lib/lead.ts, used
LeadPane.tsx:476). Chunk: **LP-16 (new):** an edits card listing targets, `Zahodit vše` posting every index,
`Otevřít lištu` opening the stage. Test: component test dismisses all indices in one POST and folds.

### 2.9 Plán (LO4) — backend does not exist

Drawn: `Plán · 4 kroky, jedno schválení`, `Od návrhu ke sběru dat`, steps with prices and a gate step
(`Přijetí dotazníku · rozhodujete vy · zdarma`), `Plán nejvýše 15,60 USD · nad prahem potvrzení 10,00 USD`,
`Schválit plán`. The board marks it a proposal, not today's AIA.

Provided: only the reserved ledger subjects `lead_plan`, `plan_step` (approval_ledger.py:54-55); no
`lead_plans` table (tables.py:1912 says it arrives with LO3). Chunks: **LO3** (tables, authority, workflow type,
`AIA_LEAD_PLANS_ENABLED`), **LO4** (the card), **LO21e** (plan as a registry action), **LO2** (typed
`start_run` without `confirm_cost_usd`), **LO17** (withdraw a plan). Test: LO4's own; out of the first build.

---

## 3. The composer's "+" menu

### 3.1 Akce, per stage, vs `lead_artifacts.py` starts

Prototype lists (each board's `chatF` `const A`) against `ARTIFACTS[stage].starts` (lead_artifacts.py:237-411;
web mirror workbench-artifacts.ts:55-…):

| Stage | Prototype Akce | Contract starts (lead_artifacts.py) | Match |
|---|---|---|---|
| Zadání | Analyzuj zadání; Zeptej se na klientské znalosti | analyze_brief, answer_memory (246) | yes |
| Návrh | Analyzuj zadání; Zkontroluj návrh; Pomoz s návrhem; Zeptej se…; Rešerše k návrhu | analyze_brief, critique_design, design_copilot, answer_memory, design_research (258-264) | yes |
| Dotazník | Navrhni dotazník; Uprav dotazník; Zeptej se…; Rešerše k návrhu | build, optimize, answer_memory, design_research (282-287) | yes |
| Cílová skupina | Navrhni audienci; Zeptej se… | propose_audience, answer_memory (304) | yes |
| Dimenze | Navrhni dimenze; Zeptej se… | suggest_dimensions, answer_memory (316) | yes |
| Vzorek | Zeptej se… | answer_memory (328) | yes |
| Sběr dat | Spusť výzkum | research_run (340) | yes |
| Výsledky | Zeptej se… | answer_memory (356) | yes |
| Sociomapa | Rešerše k výkladu | interpretation_research (368) | yes |
| Analýza | Zopakuj analýzu; Rešerše k výkladu | analysis_retry, interpretation_research (380) | yes |
| Zpráva | Rešerše k výkladu | interpretation_research (402) | yes |

All eleven match (R15's fix is already in the boards). How each item starts:

- Every **agent_job** and `research_run` / `analysis_retry` item maps 1:1 to a typed command phrase
  (lead_commands.py:76-85). Picking it sets the token; send posts the phrase, plus `: <text>` when the person
  typed something after it — exactly LO5's grammar (`takes_instruction` true for jobs, false for run and retry,
  lead_commands.py:69-70, 84-85, 130-133). So the composer must **disallow extra text** after `Spusť výzkum` /
  `Zopakuj analýzu` tokens (the server would treat it as a plain message).
- `Rešerše k návrhu` / `Rešerše k výkladu` have **no command** (lead_commands.py:75-86): blocked on LO5a.3; until
  then the item is shown disabled with its reason, or omitted (decision for the owner; R9's pattern is
  "vypnuté s důvodem").
- Item subtitles carry the ceiling (`do 0,40 USD`): G-ceiling (LP-4) or omit the amount.
- Gating: show `Zopakuj analýzu` only when `analysis_retry_run` is non-null (lead.py:286-287); hide AI items when
  the Lead/worker is off (availability, lead-availability.ts:46) — typed commands still work with the Lead off
  (lead.py:282 "with the Lead on or off").

Chunk **LP-17 (new): the Akce tab** from `ARTIFACTS[stage].starts` ∩ `GET /lead commands`, token → phrase.
Test: a table test over all eleven stages asserting the menu equals the contract's starts (DR items disabled
until LO5a.3), and that `Spusť výzkum` + extra text is not sendable.

### 3.2 Přidat

| Item | Prototype | Today | Chunk |
|---|---|---|---|
| Ukázat na prvek | "klikněte na prvek v kroku vpravo"; sets a token | `@` button arms picking (LeadPane.tsx:663; `picking`/`onPick`, 74-76); focus sent with the message (191); 23 target kinds (lead_artifacts.py:87-115) | move into the menu; keep `@` keyboard shortcut. research-lead-workbench#16 (open). Test: lead_journey "@ on an objective" still passes from the menu. |
| Přidat podklad | "soubor nebo odkaz ke klientovi" | IntakeSheet via `openIntake` (components/aia/clients/ClientContext.tsx:30, 48-56), provided on every client page by the client layout (app/app/clients/[clientId]/layout.tsx:9), so reachable from the study | **LP-18 (new):** menu item calls `openIntake()`. "odkaz" (link) is "V AIA zatím není" in the intake (CLAUDE.md §2 IntakeSheet). A file *to the Lead's turn* is a different thing: LO18 / #30. Test: component test that the item opens the intake sheet. |
| Hledat na webu | disabled, "připravujeme" | not built: LO20, ADR 0040 Accepted 2026-10-20 (docs/architecture/adr/0040-the-leads-web-lookup.md:3); UI is research-lead-workbench#32 | ship disabled with that subtitle; LO20 + #32 enable it. Test: menu renders it disabled with `aria-disabled`. |

### 3.3 Kontext toggles vs LC2 and the manifest

Prototype: three toggles — `Aktuální krok` (stage · revize N, on), `Znalosti klienta` (approved items, on),
`Moje poznámky` (what Ada remembers about you, **off** by default); the `Vidí:` line lists those on.

Today:
- The context is a fixed pipeline of layers: prompt, lead (name, SOUL, USER, notes), knowledge, study, design,
  runs, external, view, memory, conversation (lead_context.py:74-113). No per-turn switch exists: `TurnPost` is
  `kind, text, stage, focus` with `extra="forbid"` (lead.py:101-108).
- Notes are **always in** (layer `lead`), so the prototype's default "notes off" differs from today.
- LC2 (done) shows, after the fact, what a turn saw, layer by layer with omissions (LeadSees.tsx;
  `/lead/turns/{id}/manifest`, lead.py:601-636).

Gap and chunk: **LP-19 (new, core+API+web): per-turn context choices.** `TurnPost.context: {knowledge: bool,
notes: bool}`; `freeze_context` leaves a switched-off layer empty and the manifest records it as omitted with
reason `person_off`, so LC2 reads it back. `Aktuální krok` cannot be switched off without breaking edits and
focus (the `design` and `view` layers are "never shortened", lead_context.py:91, 101): show it as fixed, not a
toggle — **owner decision**. Default for notes needs an owner decision (prototype off vs today on). Tests:
`test_lead_context.py` — knowledge off yields an empty knowledge layer and a `person_off` omission; router test
rejects unknown keys; LeadSees shows the omission.

The `Vidí:` line under the composer states the next turn's inputs from those choices; clicking it opens the
LC2 panel of the last turn (keep `LeadSees`).

---

## 4. Streaming

### 4.1 Events that exist (the run event feed, folded by step-activity.ts:81-145, 173-227)

| Source | Event (`event_type` / `message`) | Switch |
|---|---|---|
| Engine, every step | ATTEMPT_CLAIMED, STEP_SUCCEEDED, STEP_DEFERRED, STEP_RECOVERY, ATTEMPT_ABANDONED (step-activity.ts:90-99) | always |
| AI fieldwork | `fieldwork_sample` (cells), `fieldwork_progress` (respondents, of, sent, replayed, cells) every 10 and at most every 30 s idle (ai_fieldwork.py:388-413, 505-506; fieldwork_events.py:51, 85-92) | heartbeat part behind `AIA_AI_FIELDWORK_HEARTBEAT` (CLAUDE.md §2) |
| Analysis module | `AI analyzuje modul` with module, turn (analysis.py:355) | always |
| Model request | `ai_request_sent`, `ai_request_answered` (input/output tokens, cost, latency) (ai_step.py:85-86, 229-273) | **`AIA_AI_STEP_EVENTS`** |
| Deep Research steps | `deep_research_*` summaries (§2.5) | always |
| Deep Research tool calls | `deep_research_tool_<outcome>` per journaled call (tooling.py:96; runtime.py:385) | always |
| Lead turn | none streamed; the pane polls `GET /lead` every 1.5 s while busy (LeadPane.tsx:27, 156-161) | LO18 (streamed text) open |

Feeds: runs `GET …/research/runs/{id}/events` (research.py:1770), jobs `…/agent-jobs/{id}/events`
(research.py:3922), Deep Research `…/deep-research/runs/{id}/events` (deep_research.py:772); reader
`useStepActivity` polls 1.5 s while a step runs (CLAUDE.md §2).

### 4.2 Behind `AIA_AI_STEP_EVENTS` (off by default)

Flag: `step_events: bool = False` (ai_runtime.py:498-502), read at 682; develop Compose default `false`
(deploy/develop/docker-compose.yml:294). It turns on `announce=` for research agents (research_agents.py:237),
analysis modules (analysis.py:594), the study Lead (research_lead.py:188) and client-source proposals
(client_source_proposals.py:198). Cost: two lease-fenced writes per request (ai_runtime.py:500-501; CLAUDE.md
quotes ~1.3 ms). **Consequence for the cards:** with it off, a design job's card shows `Worker krok převzal`
and then nothing until `Krok dokončen` (CardsF §"Největší výtka"); the card must say events are not reported
and show elapsed time (LP-9). Decision for the owner: switch it on for develop (it is a kill switch, measured).

### 4.3 What an in-chat Deep Research card needs (none exists today)

1. Placement: `conversationTimeline` takes Deep Research runs as a fourth kind (lead-cards.ts:150-176) and
   Workbench passes `deepResearch.runs(studyId)` (api.ts:1586) into `LeadCardsContext` (LeadPane.tsx:34-45;
   Workbench.tsx:789-790). A card started from a turn binds to it, as `runOfTurn` does for research runs.
2. Live feed: `useStepActivity` over `deepResearch.events` (api.ts:1588) while a step RUNNING; fold already
   handles DR summaries and tool outcomes (step-activity.ts:129-136, 220).
3. Six-step strip from the run's steps (plan → publish; workflow.py, CLAUDE.md §2); fan-out tracks as
   `deep_research_track` lines.
4. Counts: web calls from `toolCalls`; model requests from `deep_research_track.model_requests` (cs.ts:3290) —
   `ai_request_*` is not wired for DR agents (**hypothesis**, §2.5).
5. Money: ceiling from `/quote` (deep_research.py:550) at request time, spent from the run response
   (**hypothesis** on the field), lift through `…/runs/{id}/budget` (730), stop through `…/cancel` (701).
6. Start from the card: LO5a.2 (approve_request starts it; today `NotAPaidRequest`).
7. What a refused or failed fetch was: LP-14 (payload has no URL or reason today, tooling.py:157-182).

Chunks: research-lead-workbench#23b, #23c; LO5a.1-3; LP-14.

---

## 5. Backend gaps (anchored)

| # | Gap | Anchor | Chunk |
|---|---|---|---|
| B1 | No ceiling for a design job or analysis retry before start; only inside a 409 | research.py:3740-3761; lead.py:466-473; research.py:2023-2050 | LP-4 (new) |
| B2 | No open hold (`reserved_usd`) on agent jobs; run spend only on the single-run read | research.py:3740-3761; Workbench.tsx:789-790 | LP-5, LP-11 (new) |
| B3 | No dismiss for a Lead turn's request; `Teď ne` is page state | LeadPane.tsx:595, 624; lead.py routes 680-760 | LP-7 (new) |
| B4 | Lift takes an absolute budget; no "needs X" on a waiting step | research.py:1821-1827, 352-388 | LP-8 (new) |
| B5 | Deep Research cannot be started from a Lead card or typed | application/research_lead.py:1137-1140; lead_commands.py:75-86 | LO5a.2, LO5a.3 |
| B6 | Lead model cannot prepare an analysis retry | domain/research_lead.py:328-331 | LO21a/LO21d (registry) |
| B7 | One request per Lead turn | domain/research_lead.py:371 | LO21 (several actions per turn) |
| B8 | No per-turn context choices | lead.py:101-108; lead_context.py:74-113 | LP-19 (new) |
| B9 | DR tool events carry no host or refusal reason | tooling.py:157-182 | LP-14 (new) |
| B10 | Model-request events off by default; DR agents not announced (**hypothesis**) | ai_runtime.py:498-502, 682; docker-compose.yml:294 | owner decision; LP-9 |
| B11 | No plan backend | approval_ledger.py:54-55; tables.py:1912 | LO2, LO3, LO4, LO21e |
| B12 | No cost per Lead turn | LeadTurn has status, reason, request_decision, command; no cost (lead.py:202-234) | LC6 |
| B13 | No stop of a running Lead turn | — (no cancel route among lead.py:560-805) | LO17 |
| B14 | Lead turn text not streamed | LeadPane.tsx:156-161 (polling) | LO18, research-lead-workbench#30 |
| B15 | `GET /lead commands` served but unread by the web | lead.py:536-544; no reader in apps/web/src | LP-15 (new) |
| B16 | SpendDialog has no consumer; money confirmations are plain `confirm` text | SpendDialog.tsx:60; Workbench.tsx:536-540 | LP-8 |

Suggested order: LP-3 + LP-17 (composer and Akce, no backend) → #23 job/run card restructure + LP-1/LP-2/LP-9
→ LP-4/LP-5/LP-7 (API) → LP-6/LP-8/LP-11/LP-12/LP-13/LP-16 → LP-19 (context) → LO5a.1-3 + #23b/#23c (Deep
Research) → LO3/LO4 (plan). Every journey keeps "zero paid jobs" (CLAUDE.md §3 workbench journeys).
