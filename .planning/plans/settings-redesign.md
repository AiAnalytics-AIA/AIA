---
status: in-progress
chunks:
  - "[x] 1. Tab frame: ten tabs in three groups (Tým a peníze), a line under each name, Lucide icons; Stav systému and Správa dat as their own tabs"
  - "[x] 2. Shared inputs: one Switch (ui/Switch); Segmented = ChoiceChips, Stepper, InlineCreateRow, InlineText and UndoToast already in ui/ (input-interactions)"
  - "[x] 3. Přístup a schvalování: role, status and self-approval chosen in their rows, name edited in place, inline add member, role change with Vrátit, roles boxes, samoschválení above Klienti"
  - "[x] 3b. Přístup over its backends: Metodik switch (owner only), deactivate with Vrátit and the sealed Lead"
  - "[x] 3c. A client's data posture and wallet ceiling read in Přístup (#853), set on Profil → Pravidla (D-17)"
  - "[x] 4. Studie a rozpočty: the four money names, steppers with bounds, % and near-limit (90 %), spend tiles and per-researcher spend"
  - "[x] 5. Systémové prompty: grouped list, editor layout, in-force version in green, Verze table"
  - "[x] 6. Deep Research: Dosah, proposals in the Návrh cell, I7 modals, Pevné ochrany v kódu"
  - "[x] 7. AI běh: route tiles, activities grouped with descriptions, the missing activities"
  - "[x] 8. Audit: categories with counts, period, search, Czech names for every action code"
  - "[x] 9. Reference: categories, Kdo mění filter, Co znamená column"
  - "[x] 10a. Metodika catalogue: a card per module with its drawing, accent and facts, no categories, the map first; -5 only, the reference map and H-Model not listed (D-13)"
  - "[x] 10b. Metodika module view: sub-tabs Výpočet / Verze a aktivace / Porovnání / Upravit, activation modal with reason chips, editor from the version in force, Metodik-only editing (D-14)"
  - "[x] 11. Stav systému and Správa dat: content over their backends"
  - "[x] 12. Profil → Pravidla: a client's data posture and wallet ceiling set where they are read (D-17, #853); opening to public research asks first"
  - "[x] Q82-Q85. The product owner's answers of 2026-10-23: the Metodik editor's way in named, done as an ink ✓, dark needs-you #ffaa77 held apart by check:design, a budget-parked Lead turn coral for who can raise it"
  - "[x] F1. Fidelity gap 2: the Metodika art and accents drawn (runtime colour properties, never Tailwind's --color-*)"
  - "[x] F2. Page frame and tab heads as the prototype draws them (breadcrumb, plain tab column, serif h1, one paragraph, status chips right)"
  - "[x] F3. One segmented control for role, status, self-approval, Audit period and Reference owner; Správa dat's client picker"
  - "[x] F4. Metodika opens on the module catalogue (one-line cards, 'Pro klienty' fact, the MVP note), back link and module header"
  - "[x] F5. Metodika → Výpočet: stage tiles, 'S parametry' filter, step rows with the formula on opening"
  - "[x] F6a. Metodika → Upravit as one parameter list (original, stepper; no bound the domain does not declare, AUD-10) over the existing guards, every editable field in stage order with the formulas in a closed expert disclosure (AUD-9), check/compare and activation with a reason; the module's tabs unboxed; Výpočet marks a parameter the version in force changes; the Metodik rule kept"
  - "[x] F6b. Metodika → Verze and Porovnání as full tables even when empty (the code's preset a row of Uložené verze, Druh / Co mění / Uložil / Stav pro klienty, each version's register status from the API; Porovnání shows what is in force beside itself when asked)"
  - "[x] F7. Studie a rozpočty: the 6-column table without the per-study status picker, the KPI tiles, per-researcher stacked bars; near-limit grey with ⚠ (gaps 4, 16, 17)"
  - "[x] F8. Deep Research: one flat rules table with Schválit/Stáhnout per row, readiness in the card head, Dosah always listing routes, the code's protections inside, unknown in ink (gaps 5, 6, 20, 21)"
  - "[ ] F8b. Deep Research compacted (prototype v55): a one-line intro, ⓘ tooltips in place of captions, symbols; every ⓘ a real button, no amber"
  - "[x] F9. Přístup: three flat cards, the Naposledy column (gaps 7, 8)"
  - "[x] F10. Audit: category tiles and the Důvod / změna column in words (gap 10)"
  - "[ ] F11. AI běh tiles and activity columns, Reference categories and tiles (gaps 13, 19)"
  - "[ ] F12. Colour rules and copy: Stav systému's shared deployment not red, Správa dat's danger button, retention rows and inline Smaže se / Zůstane, Systémové prompty head chips and buttons (gaps 14, 15, 18)"
  - "[x] F12a. Moved to client-knowledge-lifecycle#K12 (AUD-6 (a), the product owner 2026-10-25: the Simulace tab and the new-simulation entry hidden for the MVP), built and ticked there (#898); nothing of it is left in this plan"
  - "[x] F12b. ⌘K navigation (prototype v54): the left settings column replaced by \"Nastavení > <sekce> ⌄\" and a section menu (click, ⌘K / Ctrl+K anywhere; search by keyword; three columns with icon and line; Enter opens the first match, Esc closes); content full width; the coral count on Deep Research and Systémové prompty from real API state, admins only, never invented; #hash deep links and keyboard access kept; the tab-column journey checks rewritten to the menu (⌘K, Esc, Enter on the first match, #hash), not deleted"
  - "[x] F13. Metodika → Upravit bounds (AUD-10 (b), the product owner 2026-10-25; before F9-F12): each editable field declares its bound in the domain, tested against the check that guards it (no bound without one), the API returns it, Upravit says \"mez …\" beside the field; its own PR"
  - "[x] F14. AI běh: each activity's last answered call, an organization-level aggregate from the usage ledger (OI-75 (a), the product owner 2026-10-25; before F9-F12); unknown never reads as working"
  - "[ ] F15. Metodika copy (prototype v54): the module cards renamed (Sociomapa, Práh zobrazení, Odhady a intervaly, Vážení vzorku, Losování odpovědí, Kontrola před spuštěním), the intro and the sociomap-5 note one line each"
  - "[ ] F16. Studie a rozpočty compacted (prototype v52): symbols and ⓘ in place of explanatory text, keeping #892's accessibility (visible activity labels, ⓘ as buttons, 44 px targets)"
  - "[ ] F17. Reference's content folded into Stav systému, so Settings has nine sections; the flyout that lists them is prototype-build PBA3 (Nigel, 25 Oct 2026 23:13-23:15 UTC; W1)"
  - "[ ] F18. Each Settings page's hero figures, read from the routes it already reads (gap map §0; W1, on prototype-build PBA4's hero)"
  - "[x] F19. The Naposledy column served: last_seen_at on GET /members, which F9 shows (W1)"
  - "[ ] F20. Studie a rozpočty's 'Čeká na rozpočet' tile beside per-researcher spend by kind: an organization-scoped count of steps waiting for budget (W1, its read needs an architecture decision)"
  - "[ ] F21. Stav systému: Připravenost first, then Prostředí a verze (environment, build, API, database, sign-in, LIVE and STATIC population, field rules) and 'Kopírovat diagnostiku' (W1)"
  - "[ ] F22. Správa dat: the running-study block ('Klientovi právě běží …', from a running flag in the deletion preview) and the typed-name confirmation before 'Smazat natrvalo' (W1)"
---
# Settings redesign (Nastavení)

The product owner's redesign of Settings, built from the design artifact
https://claude.ai/artifact/8W9LR8Ju9BWnR5JACmiWv7 (ten boards, one per tab) and its decision log
`.agent-status/settings-prototype.md` on `coordination/agent-status`. Stay true to the design.

## Decisions (the product owner, 2026-10-22 night)
- Build every tab, backends included (the backends are their own plan, `settings-backends.md`,
  built beside this one; a tab whose route has not landed says "V AIA zatím není", never fake data).
- Green marks only what is in force (a prompt's active version, a switched-on item); done stays ink.
  "Needs you" rows use the status-you tokens (coral after the Indigo palette).
- ~~Lucide icons in Settings now (lucide-react, pinned): tab icons and icon buttons with a label and
  tooltip; consequential actions keep their text.~~ Superseded 2026-10-23 by the decision to follow
  prototype v51 (fidelity F2): its plain tab column draws no icons, so #868 removed them and lucide-react.
- As many chunks as fit, one PR each.
- Metodika keeps the module accent colours and drawings and drops the per-stage filter (S1–S7, "Jen kroky").
- "Téměř vyčerpáno" at 90 % of a study's budget.
- Client delete removes the client's content and keeps the money ledger, the approval ledger and the
  audit with the client's name replaced by its id. A deactivated member's Lead is sealed and erased
  after 30 days. GlitchTip's issues come through a read-only route over an API token the owner adds to
  SSM. The Metodik mark ships to the product owner alone. Spend from before attribution reads "Neznámý".

## Rules carried from the design rounds
- Edit in place; steppers with bounds and Shift ×10; refusal at the field in words; reversible actions
  immediate with Vrátit (8 s); a modal only for a consequential action (I1–I11).
- Keep all information visible: sections, summary chips, "needs you" first, muted switched-off rows.
  Never hide information behind toggles.

## Findings
- Metodika → Upravit's "Porovnat s metodikou v platnosti" sat on "Porovnávám metodiky…" past the
  settings journey's 30 s on the first comparison in a process with an empty numba kernel cache --
  every container start, since NUMBA_CACHE_DIR is /tmp in a read-only image (python.Dockerfile).
  Measured on a 4-vCPU Xeon 2.8 GHz (fresh process, empty cache): first compare 47.6 s, then 8.0 s;
  warm 8.7 s and 7.9 s; five settings journeys on a warm workbench, compare 8.1-9.2 s, all passed.
  The web clears its busy state in a finally (MethodologyVersions.tsx compare), so it was a slow
  first compute, not a stuck state. Fix: AIA_SOCIOMAP_WARMUP_ENABLED (apps/api warmup.py) compiles
  the kernels in a separate low-priority process after start (56 s alone; the API's health p95 8 ->
  9 ms meanwhile, against 60 ms in a thread), and the editor counts a comparison's seconds after 3 s
  and says why after 10 s. apps/api/tests/test_warmup.py, test_methodology_sociomap_check.py
  "the warm-up computes the preset's map on every check panel", MethodologyVersions.test.tsx "counts
  a long comparison's seconds". Not measured on develop's t3a.medium.
- Hypothesis: a warm comparison takes 8-9 s (six aia-sociomap-5 maps, about 1.4 s each, with the
  noise rule's 100 permutations and the layout's restarts). Unprofiled; it may be what -5 costs, or a
  second finding. Not a person-blocking wait now that the editor says what it is doing.
- The membership call (POST /api/v1/members) writes a member's name and role together, so a role chosen
  while the list was still re-reading a new name would have written the old name back. Caught by the
  settings journey on chunk 3; the row now sends the newest name (AccessPanel.tsx MemberRow), and
  ControlPanel.test.tsx "never writes an old name back when a role is chosen while the new name is
  still being read" fails without it.
- A stepped study budget fell back to its old value between the PUT's answer and the re-read, so
  the field showed 0,00 after a save that had landed (caught by the settings journey on chunk 4). The
  row now holds the answered value until the re-read reaches it (StudiesPanel.tsx useAnswered);
  ControlPanel.test.tsx "keeps a saved budget in its field while the re-read has not caught up" fails
  without it.
- Hypothesis (no fix here): the settings journey's "Methodology default height < 4500" grows with
  each run on the same workbench (4178 on a fresh one; 4502 after several runs), because each run
  stores and activates a methodology version and the tab lists every version. It passes on
  `workbench.py up --fresh`; chunk 10 (Metodika) redraws that tab and should settle it.
- The prompts' Verze table, with its actions in a fifth column, pushed the page wider than 1024 px
  once a version was saved (caught by proposal_prompt_journey on chunk 5): the actions now stand on a
  row of their own under each version's facts (SystemPromptsPanel.tsx Versions).
- Chunk 5 removes Settings' draft test (X10): the web half of system-prompts-settings #14. The web no
  longer sends `prompt_version` or reads `draft_test_client_ids`, but the server half stays open: the
  agent-job route still accepts `prompt_version` (AgentJobStart.prompt_version) and the prompt detail
  still answers `draft_test_client_ids` (SlotDetail). The backend builder removes them under #14 (D-15);
  until then #14 is not done.
- A stored version "waits" only when saved after the last switch-on (or with none made): a number above
  the one in force read a rollback or a reset to the code's wording as waiting (review of #838). The
  list's summary carries no version date, so the list says a version waits only when nothing was ever
  switched on (SystemPromptsPanel.tsx waitsForActivation, standing).
- Deep Research's rules: a proposal "waits" only when saved after the rule's last approval (or with
  none made). A version approved and then withdrawn to the default read as waiting by number alone
  (caught by the settings journey on chunk 6); the overview carries no version date, so a rule with a
  newer number is read once to decide (DeepResearchSettingsPanel.tsx usePending), and until then
  nothing waits.
- Chunk 6's "Dosah" reads #844's GET /settings/deep-research/reach: the newest worker's record,
  waiting first (coral for an administrator only), each reason code in Czech (the server's English
  detail is technical only); "no worker has recorded" says so and claims nothing reachable; a 404 (the
  route not deployed yet) still says "V AIA zatím není". "Stáhnout návrh" is wired to
  #841's POST …/versions/{n}/withdrawal (reason required) and reads each version's `state` when the
  server sends it; until #841 merges, the route answers 404 and the refusal is said in the modal.
- Chunk 6 keeps the group list beside the rules (the catalogue has ~40 rules; the design's flat table
  had 8) and puts the design's columns in each group: Pravidlo, V platnosti, Návrh, Schválení.
- Chunk 7 lists five activities the settings document does not carry (Lead plans and the run's
  quality check, not built; population personas, the report PDF and client-source proposals, built).
  /config does not read their switches, so the built ones read "Stav nevidíme", never on or off. Their
  state belongs in the settings document's `ai_runtime` (backend follow-up), with their data classes;
  until then the board has no data-class column, rather than one written by hand.
- Chunk 8 reads the last 500 audit records (the API's limit is 1000; it was 50) and files every action
  the server writes under a category by rule (lib/audit.ts); a code it does not know reads as words
  under "Ostatní", and a record without a time is in every period. The design's "Postoj dat",
  "Strop peněženky", "Štítek Metodik" and "Vedoucí zapečetěn" names are there for the codes that exist;
  the posture, ceiling and Metodik codes get names when their backends write them.
- Chunk 10a keeps the module cards behind "Změnit oblast": the product owner's rule of 2026-10-13
  (a methodologist opens on the editor, its sequence on the first screen; the settings journey holds it
  at 1440x900) would break with the cards above the editor. The design's always-visible card grid is a
  decision for the product owner, recorded for 10b.
- 10a's accents are wayfinding tints only; readiness takes hue-slate, not the design's green, which is
  "in force" alone. The support drawing's n = 30 line is ink, not fault red.
- F7 (#892): the "Téměř vyčerpané" tile and each row's ⚠ read spent alone against the budget
  (`lib/researcher-spend.ts` nearLimit, >= 0.9; closed studies left out of the tile). The server's
  own rule, `GET /settings/organization-spend` `near_limit` (`domain/spend_attribution.py`
  NEAR_LIMIT_SHARE), counts open studies by spent plus held; the Study response carries no held
  amount, so a study whose budget is taken by open holds is near to the server and not here.
  Follow-up: read `near_limit` from that route for an OWNER or ADMIN (it refuses a member 403), and
  keep the client rule for a member's own rows. Test: a held-heavy study near on the tile.
- F7 (#892): a study's status moved from the Settings table to the study (StudyStatusMenu in the
  stage header and the workbench's study header; "Znovu otevřít" on a closed study's notice reopens
  it in place), so the capability the picker held is not lost.

- F8: the catalogue holds 52 rules where the design's flat table drew 8. The table is the design's --
  one flat table, the group a column -- with the search and "only what live needs" kept above it; a
  rule's purpose moved from its row to the name's ⓘ (and a screen reader's text) and to the top of
  its opened row, so 52 rows read at a glance. Dosah's "Schválení organizace" is read from the
  worker's record alone: a route it did not compose recorded no price, so its approval reads "—",
  never "nepotřebuje". With no record the table is drawn with one row saying why; no route is named
  by hand ("No screen or document names a route set by hand", domain/deep_research_reach.py).
- F13: none of the editable modules' specification models declares a range in its type (no pydantic
  constraint), so the bounds come from the checks themselves: `require_supported` and its helpers,
  `readiness_problems`, the support, aggregation and response validators. 77 fields carry one
  (`MethodModule.bounds`), each naming its guard and proved by `test_methodology_bounds.py` under every
  preset that gives it a number. Left without one: fields held only to be finite (the response
  coefficients), fields whose range depends on the preset (`relation.confidence` and SMACOF's
  iterations and tolerance, held to one value under the signed-off layout; `layout.min_objects`, two
  or three by layout), and pairs checked as one (quantiles, stress bands). A null line in a preset
  (support's results.min_cell) has no bound shown: no preset lets the test prove it.
- F14: the activity of a ledger row is read from the agent id its code sends (`domain/ai_activity.py`;
  Deep Research's lead researcher by its capability); a call no listed activity makes (AI proposals
  from a client's document, an operator's calibration) is left out. The read asks each known agent's
  newest `SUCCEEDED` row, one lookup each on the partial index `ix_usage_org_answered`: a grouped
  maximum read the organization's whole ledger (a parallel scan, 42 ms at 600,000 rows and growing),
  the lookups 0.03 ms each, 11 ms for all 22 agents whatever the ledger's size. "Last answered" is the
  past: a newer failure is not hidden by it and the page never says an activity works.

The order of the remaining chunks (the coordinator, 2026-10-25, after the product owner's answers of
that day): F8, F12a (AUD-6), F12b (⌘K navigation: every later tab sits in the new frame), F13 and F14
(decided that day), F15, F16, F8b, then F9-F12 built against prototype v56-v58 (Systémové prompty, AI běh, Přístup compacted). The list above is the chunks' ids, not their order.

## Fidelity to the prototype v51 (the product owner, 2026-10-23)
"Implement the settings pages just as we designed them; the current deploy is far from it."
The tab-by-tab report (22 ranked gaps, side-by-side shots at 1440 and 390) is the fidelity
agent's; chunks F1-F12 follow its order. His decisions on it: Metodika follows the prototype
(catalogue first, Výpočet as stage tiles and step rows, Upravit as one parameter list over the
existing guards, check/compare and activation with a reason; the Metodik rule kept); Studie a
rozpočty drops the per-study status picker for the design's 6-column table; the global shell
(gap 22) is not now. Each chunk is its own PR from a fresh develop, with side-by-side screenshots.

## From the research build spec (2026-10-26)

Source: the research build spec (https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy), checked chunk by chunk against this plan's front-matter at
develop `bd0d1ad6` in the research chunk register (26 Oct 2026); waves recorded in
`.planning/mvp-execution-contracts.md`. Lane and order: [`prototype-build.md`](prototype-build.md).
A spec id carries its section prefix (`navrh/`, `vzorek/`, `sber/`, `szz/`, `lead/`), because the
ids repeat across sections. A ticked chunk the spec reopens is never unticked: its rework is a
follow-up chunk below.

**F10. Audit's Důvod / změna** (built). The table as prototype v99 draws it: Kdy, Kdo, Událost (the
category's dot with its name for a reader, the event, what it concerns) and Důvod / změna: the change in
words from what its writer stored (`apps/web/src/lib/audit-change.ts`): the scope repository's
"a -> b" reasons as money ("100 → 120 USD", "bez prahu"), status codes and roles in Czech, the
self-approval rule, a client's posture and wallet ceiling, methodology, prompt and Deep Research
versions; the person's reason (payload `why`, or the reason where the code writes none) under it. A
shape it does not know keeps its reason as written and invents no change; nothing at all is "—". The
category chips with their counts stay as chunk 8 built them; the search reads the change as shown.

**F17. Reference into Stav systému** (W1, lane B). Nigel, 25 Oct 2026 23:13/23:15 UTC: merge Reference into Stav systému, drop what is irrelevant. The rail flyout is lane A's (`prototype-build#PBA3`, after #900); this chunk moves the page content.

**F18. Hero figures** (W1, lane B). The hero component is lane A's (`prototype-build#PBA4`); this chunk fills each page's figures from its existing reads (Metodika, Systémové prompty, Deep Research, AI běh, Přístup, Studie, Audit, Stav systému, Správa dat). Unknown never zero.

**F19. Naposledy, served** (W1, lane B). `users.last_seen_at` is stored (`packages/aia_core/src/aia_core/infrastructure/tables.py:458 @ 40b16d58`) and `MemberResponse` does not carry it (`apps/api/src/aia_api/routers/scope.py:194-210 @ 40b16d58`). F9 draws the column. Null reads as never, not as a date.
  Built: `last_seen_at` on `MemberResponse`, for an OWNER or ADMIN (null otherwise, as the Lead's seal
  is), in UTC whichever database stored it. **Finding (fixed here):** `ScopeRepository.upsert_user`
  stamped `last_seen_at` on every upsert of an existing user, and `add_member` upserts the member, so
  an administrator's role change or re-add wrote their own moment as the member's last activity
  (`packages/aia_core/src/aia_core/infrastructure/scope_repository.py:214 @ 25ce6493`); it now
  stamps only with `seen=True`, which the API's identity path alone passes, and a first sign-in
  stamps the row it creates. Test: `apps/api/tests/test_member_last_seen_api.py`.
- F9: Přístup as prototype v58 draws it: Členové, Samoschválení and Klienti as three flat cards under
  the tab's head (no group card around them; each card's title the h2), their explanations behind an ⓘ
  that a keyboard or touch opens (`settings/InfoButton.tsx`, shared with later compaction chunks), the
  role boxes behind the Role column's ⓘ. Naposledy for an administrator: a time with the exact moment on
  hover, "nikdy" for null, "nezjištěno" for an API that does not serve it; a member sees no column. The
  organization's self-approval in the card's one row beside the precedence; "Výchozí" kept (the code's
  third option) and the study rules kept in the card, against v58's two options and "ve studii".

**F20. Čeká na rozpočet** (W1, lane B). Per-researcher spend by kind is built (F7); the tile needs an organization-scoped read of steps AWAITING_BUDGET, which ARCHITECTURE §3 allows only through `WorkQueue`: the read's shape is decided in the PR, or the tile waits. The same read serves `fronta-prace` later.

**F21. Prostředí a verze** (W1, lane B). From the build identity and `GET /population`; no secret in the copied text. Fronta práce is post-MVP (`fronta-prace.md`).

**F22. Running work and typed name** (W1, lane B). Deletion is already refused with 409 `client_has_active_work`; the preview gains the flag. The kept records' lhůta reads 365 days (MVPQ-07 closed, 26 Oct 2026).

**Notes.**
- Audit's eight categories, Dnes / 7 / 30 dní and search are chunk 8 (done); F10 finishes the Důvod / změna column.
- The global shell (gap 22, "not now" above) is now lane A's, built by "the second account": the Dock rail, Můj Vedoucí on the rail, the flyout from the rail item and the hero component (`prototype-build#PBA1` to `#PBA4`). F12b (#900) lands first; PBA3 then opens its menu from the rail item.
- **Proposed (26 Oct 2026): this plan becomes core with waves** (master §3.1), every open chunk W1: the frame work with lane A in step 2 and the remaining pages in step 3 (`prototype-build.md`). Nigel may change it.
- Nigel, 26 Oct 2026 ~00:35 UTC: "no narrower screens right now": the Settings pages are drawn at 1440 only; the product keeps the workbench's existing narrower layouts.
- Decided by default (planning, open to Nigel's override): a study budget may go to 1,000,000 USD (the prototype's 10 000 is not adopted).
