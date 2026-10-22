---
status: in-progress
chunks:
  - "[x] 1. The methodology journey has an edit for the readiness limits, and the research journey waits for the steps"
  - "[ ] 2. Nový klient: an empty name is said, not silently dropped"
  - "[ ] 3. Znalosti at 390 px: the library table's clipped columns"
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

### F1. `make ui-methodology` fails on develop (fixed by chunk 1)

1. Claim: the methodology journey refuses the readiness module, which is now editable, because it
   has no edit for it. Once that is added, its research run fails on a timing bug.
2. Anchor: `tools/ui_workbench/methodology_journey.mjs:42-47 @ bfe6d15` (EDITS has no readiness);
   `tools/ui_workbench/research_journey.mjs:107-112 @ bfe6d15`.
3. Repro: `make ui-workbench && make ui-fixtures && make ui-methodology` gives
   `FAIL readiness: editable, but the journey has no edit for it`.
4. Consequence: the Metodika acceptance journey is red, so a regression in Metodika goes unseen.
5. Fix: give the journey an edit for readiness (`sample_size.min` = 40), checked through
   `GET …/research/limits`. Readiness is not in a run's methodology because it decides whether a
   run may start, not what it computes. Also make the research journey wait for the steps' own
   `data-status`. With the research workbench on, the Lead pane's card for an earlier run says
   "Zpráva je hotová" while the new run is still running.
6. Test: the journey itself; it passes with the fix (9 checks).

### F2. Nový klient: an empty name is dropped without a word

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

### F3. Znalosti at 390 px: the library table hides its last columns

1. Claim: at 390 px the knowledge table scrolls sideways inside its own frame. The revision column
   is cut at the edge and nothing shows that more is to the right.
2. Anchor: `apps/web/src/components/aia/clients/KnowledgeLibrary.tsx:163-164 @ bfe6d15`.
3. Repro: open /app/clients/<client>/knowledge at 390 px (`tmp/audit/sweep/390_…_knowledge.png`).
4. Consequence: on a phone the revision and date of an item are out of view, and the reader does
   not know they exist.
5. Smallest fix: below `sm`, show each row as a card (name, kind, folder, revision), or hide the
   minor columns and show them in the opened item.
6. Test: a journey assertion at 390 px that every column header's right edge is within the frame.

### Notes (not defects)

- The workbench keeps every methodology version the journeys stored (`aia-sociomap-4+e1…e6`), so
  Metodika at 390 px is a very long page of versions. That comes from running the journeys again
  and again, not from the product; `workbench.py up --fresh` resets it.
