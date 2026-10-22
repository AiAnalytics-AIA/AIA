---
status: done
chunks:
  - "[x] 1. The methodology journey has an edit for the readiness limits, and the research journey waits for the steps (#718)"
  - "[x] 2. Nový klient: an empty name is said, not silently dropped (#720)"
  - "[x] 3. Znalosti at 390 px: the library table's clipped columns (#722)"
  - "[x] 4. The API refuses a client or study name of spaces (#783)"
  - "[x] 5. A run's methodology receipt reports its readiness pin (#789)"
  - "[x] 6. A slow rename's answer leaves focus where the person went (#735)"
  - "[x] 7. InlineText's refocus after Enter waits for nothing the person moved (#746)"
---
# UX audit, 2026-10: the areas outside the study stages

Clients home, the client workspace (Přehled, Výzkumy, Simulace, Znalosti, Data, Profil, the intake
sheet), Projektová paměť, Společenská inteligence, Nastavení (eight tabs, Metodika), Můj Vedoucí,
/login and /logout. Audited on the UI workbench at bfe6d15 (origin/develop, 2026-10-21).

## What passed

- `client_journey.mjs`, `settings_journey.mjs` (eight tabs, four widths, zero paid jobs),
  `make ui-intake` (17 checks, the sheet open in 59 ms).
- A sweep of 16 routes at 1440, 1024, 768 and 390 px: no document overflow, no control without an
  accessible name, no console error or page error. The one 4xx is a malformed client id
  (`/app/clients/CLI-nope`: two 422s), which the page answers correctly with "Tady nic není".
- Keyboard: a skip link first, then every shell link and button with a 2 px focus outline.
- Empty states: client search with no match, project memory before a client is chosen, with fewer
  than two characters and with no hit, Můj Vedoucí before hatching, Společenská inteligence with no
  population imported. Each one says what is happening and what to do.

## Findings

### F1. `make ui-methodology` failed on develop (fixed by #718, chunk 1)

1. Claim: the methodology journey refuses the readiness module, which is now editable, because it
   has no edit for it. Once that is added, its research run fails on a timing bug.
2. Anchor: `tools/ui_workbench/methodology_journey.mjs:42-47 @ bfe6d15` (EDITS has no readiness);
   `tools/ui_workbench/research_journey.mjs:107-112 @ bfe6d15`.
3. Repro: `make ui-workbench && make ui-fixtures && make ui-methodology` gives
   `FAIL readiness: editable, but the journey has no edit for it`.
4. Consequence: the Metodika acceptance journey is red, so a regression in Metodika goes unseen.
5. Fix: give the journey an edit for readiness (`sample_size.min` = 40), stored, compared and put
   in force like the other modules. A start pins it (`readiness_methodology` in the run's
   metadata, `application/research.py:883 @ 4568badd`), but the run's methodology receipt does not
   report it (F5), so the journey cannot check the run's readiness pin and says so. Also make the
   research journey wait for the steps' own `data-status`, ending on a failed step and saying a
   timeout. With the research workbench on, the Lead pane's card for an earlier run says "Zpráva je
   hotová" while the new run is still running, so the run's own completed state is read outside
   the pane (`.conv`).
6. Test: the journey itself; it passes with the fix (9 checks).

### F2. Nový klient: an empty name is dropped without a word (fixed by #720)

1. Claim: OK on an empty or blank name closes the prompt, creates nothing and says nothing.
2. Anchor: `apps/web/src/components/aia/clients/ClientDirectory.tsx:70-71 @ bfe6d15`
   (`if (!name?.trim()) return;`).
3. Repro: on /app/clients click Nový klient, then OK with the field empty.
4. Consequence: the person cannot tell whether a client was made. The dialog also has no title,
   only the field label "Název klienta", and its button says "OK" rather than what it does.
5. Smallest fix: keep the prompt open with the reason under the field, or disable OK while the
   name is blank. Title the dialog "Nový klient" and name the button "Založit klienta".
6. Test: a ClientDirectory Vitest that clicks OK on an empty name and expects the prompt to stay
   open with the reason.

### F3. Znalosti at 390 px: the library table hides its last columns (fixed by #722, with Výzkumy and Simulace)

1. Claim: at 390 px the knowledge table scrolls sideways inside its own frame. The revision column
   is cut at the edge and nothing shows that more is to the right.
2. Anchor: `apps/web/src/components/aia/clients/KnowledgeLibrary.tsx:163-164 @ bfe6d15`.
3. Repro: open /app/clients/<client>/knowledge at 390 px (`tmp/audit/sweep/390_…_knowledge.png`).
4. Consequence: on a phone the revision and date of an item are out of view, and the reader does
   not know they exist.
5. Smallest fix: below `sm`, show each row as a card (name, kind, folder, revision), or hide the
   minor columns and show them in the opened item.
6. Test: a journey assertion at 390 px that every column header's right edge is within the frame.

### F4. The API accepted a client or study name made of spaces (fixed by #783)

1. Claim: `name: str = Field(min_length=1, …)` does not strip, so a name of spaces is accepted.
2. Anchor: `apps/api/src/aia_api/routers/workspace.py:290 @ 4568badd` (a client),
   `apps/api/src/aia_api/routers/workspace.py:470 @ 4568badd` (a study).
3. Repro: `POST /api/v1/workspace/clients` with `{"name": "   "}` answers 201.
4. Consequence: a client or study named by blanks, listed with no readable name. The dialogs refuse
   it since #720, so only a caller other than the web can do this. Reuse's `new_study_name` of
   blanks was worse: the route stripped it to nothing and `reuse_design` raised, a 500
   (`apps/api/src/aia_api/routers/workspace.py:1069 @ ba596c71`).
5. Fix: `aia_api/schemas/names.py` `EntityName`, `StringConstraints(strip_whitespace=True,
   min_length=1, max_length=255)`, on every field that names a client or a study (the two
   workspace routes, the two administration routes, reuse); the domain models are unchanged, so a
   stored name still reads as stored.
6. Test: `test_client_api.py` › "a client or study named by blanks is refused and a name is kept
   without them" (201, 201, 201, 201 and a 500 before; 422 for each now).

### F5. A run's methodology receipt did not report its readiness pin (fixed by #789)

1. Claim: a start pins the readiness limits in force as `readiness` / `readiness_methodology`, but
   `run_methods` reports only the Sociomap, support, aggregation and response modules.
2. Anchor: `packages/aia_core/src/aia_core/domain/methodology/pins.py:227 @ 4568badd`.
3. Repro: start a run with a stored readiness version in force; `GET …/research/runs/{id}` has no
   `methodology.readiness`.
4. Consequence: neither the web nor an audit can tell which readiness limits a run started under;
   the methodology journey checks it only as in force (F1).
5. Smallest fix: add `readiness` to `run_methods`' pinned and stored keys, and to
   `ResearchRunMethodology`.
6. Test: `test_run_methods.py` (four tests fail on develop's `pins.py`), `test_research_api.py` ›
   "a run names the methods it computed under", `test_methodology_run_pins.py` › "a retry keeps the
   stored versions its pins came from" (readiness among them), and `methodology_journey.mjs` reading
   `latest.methodology.readiness` (its skip removed; `make ui-methodology` reports
   `aia-readiness-1+e1`). The report's method table and Results are
   unchanged: they list what computed the numbers, and readiness decides only whether a run may
   start.

### F6. A slow rename's answer took focus from where the person went (fixed by #735)

The CI flake in `KnowledgeLibrary.test.tsx` › "renames a label on F2 and recolours it by its
swatch": `useRenaming`'s refocus ran when the save answered and took focus from the colour list the
person had opened meanwhile. #735 refocuses only when focus is on the page.

### F7. InlineText refocused its shown value a frame after Enter (fixed by #746)

1. Claim: on Enter, `commit(true)` schedules `requestAnimationFrame(() => shown.current?.focus())`
   while the save is in flight, so a person who moves within that frame can lose focus.
2. Anchor: `apps/web/src/components/ui/InlineText.tsx:96 @ 4568badd`.
3. Repro: `InlineText.test.tsx` › "gives focus back to the value only if the person has not moved it before the next frame" (fails on develop before #746).
4. Consequence: focus jumps back into the field's row after Enter on a loaded machine.
5. Smallest fix: focus only when `document.activeElement` is still in the field or on the page.
6. Test: an InlineText test that moves focus before the frame runs.

### F8. A research stage's cold first open lands at about 480 ms (decided: no product change; budget in #768)

1. Claim: a cold load of a research stage fetches the client, the study and its working content
   one after another, so first content lands at about 480 ms on a production build.
2. Anchor: `apps/web/src/components/aia/clients/ClientContext.tsx` (ClientProvider renders nothing
   until the client has loaded) and `apps/web/src/components/aia/ResearchStudy.tsx:78-85 @ fec6d8c5`.
3. Repro: `workbench.py up --production`, `make ui-fixtures`,
   `node tools/ui_workbench/contextual_research_journey.mjs`: 456-751 ms over 5 runs (median 484);
   the web client as of the journey's first day (aa4ef55e) measured 396-610 ms (median 432).
4. Consequence: about half a second from navigation start before Návrh is usable.
5. Decision: Q78 (c), the product owner, 2026-10-22: the cold first open of a research stage is held
   to 800 ms from navigation start, on a production build; every interaction keeps 400 ms
   (`tools/ui_workbench/production.mjs` `COLD_OPEN_BUDGET_MS`, `INTERACTION_BUDGET_MS`). A study
   prefetch started beside the client fetch was tried and measured no gain (hydration takes about
   250 ms before the first fetch), so it was dropped.
6. Test: `contextual_research_journey.mjs`'s cold assertion, on `--production`.

### Notes (not defects)

- A name the API refuses (longer than its 200 or 255 characters) still closes the dialog first,
  losing what was typed, as it did before #720 (/code-review on #720). The field has no `maxLength`.

- The workbench keeps every methodology version the journeys stored (`aia-sociomap-4+e1…e6`), so
  Metodika at 390 px is a very long page of versions. That comes from running the journeys again
  and again, not from the product; `workbench.py up --fresh` resets it.

### F9. At 390 px a study's Upravit sat out of view on Studie a rozpočty (fixed by #767)

1. Claim: the studies table kept all seven columns on a phone, so the row's one action needed a
   sideways scroll inside the table to be found.
2. Anchor: `apps/web/src/components/aia/settings/ControlPanel.tsx:371 @ c7fbd15a`.
3. Repro: `settings_journey.mjs` (every visible study's Upravit inside 390 px) failed with all 13
   fixture studies out of view; `ControlPanel.test.tsx` › "keeps a study's Upravit in view on a
   phone" failed with 7 cells where 3 are shown.
4. Consequence: Upravit, Utraceno and Zbývá past the right edge at 390 px (table 367 px in 316).
5. Fix: below `sm` the client and status show under the study's name; client, status, spent and
   remaining are columns from `sm`, as #722 did for Výzkumy; a row whose costs are hidden spans
   no hidden column.
6. Test: the two above.
