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
  - "[ ] F8. Deep Research: one flat rules table with Schválit/Stáhnout per row, readiness in the card head, Dosah always listing routes, the code's protections inside, unknown in ink (gaps 5, 6, 20, 21)"
  - "[ ] F9. Přístup: three flat cards, the Naposledy column (gaps 7, 8)"
  - "[ ] F10. Audit: category tiles and the Důvod / změna column in words (gap 10)"
  - "[ ] F11. AI běh tiles and activity columns, Reference categories and tiles (gaps 13, 19)"
  - "[ ] F12. Colour rules and copy: Stav systému's shared deployment not red, Správa dat's danger button, retention rows and inline Smaže se / Zůstane, Systémové prompty head chips and buttons (gaps 14, 15, 18)"
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

## Fidelity to the prototype v51 (the product owner, 2026-10-23)
"Implement the settings pages just as we designed them; the current deploy is far from it."
The tab-by-tab report (22 ranked gaps, side-by-side shots at 1440 and 390) is the fidelity
agent's; chunks F1-F12 follow its order. His decisions on it: Metodika follows the prototype
(catalogue first, Výpočet as stage tiles and step rows, Upravit as one parameter list over the
existing guards, check/compare and activation with a reason; the Metodik rule kept); Studie a
rozpočty drops the per-study status picker for the design's 6-column table; the global shell
(gap 22) is not now. Each chunk is its own PR from a fresh develop, with side-by-side screenshots.
