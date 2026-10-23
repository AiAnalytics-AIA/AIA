---
status: in-progress
chunks:
  - "[x] 1. Tab frame: ten tabs in three groups (Tým a peníze), a line under each name, Lucide icons; Stav systému and Správa dat as their own tabs"
  - "[x] 2. Shared inputs: one Switch (ui/Switch); Segmented = ChoiceChips, Stepper, InlineCreateRow, InlineText and UndoToast already in ui/ (input-interactions)"
  - "[x] 3. Přístup a schvalování: role, status and self-approval chosen in their rows, name edited in place, inline add member, role change with Vrátit, roles boxes, samoschválení above Klienti"
  - "[ ] 3b. Přístup over its backends: Metodik switch (owner only), deactivate with Vrátit and the sealed Lead, a client's posture and wallet ceiling"
  - "[x] 4. Studie a rozpočty: the four money names, steppers with bounds, % and near-limit (90 %), spend tiles and per-researcher spend"
  - "[ ] 5. Systémové prompty: grouped list, editor layout, in-force version in green, Verze table"
  - "[ ] 6. Deep Research: Dosah, proposals in the Návrh cell, I7 modals, Pevné ochrany v kódu"
  - "[ ] 7. AI běh: route tiles, activities grouped with descriptions, the missing activities"
  - "[ ] 8. Audit: categories with counts, period, search, Czech names for every action code"
  - "[ ] 9. Reference: categories, Kdo mění filter, Co znamená column"
  - "[ ] 10. Metodika: module cards with drawings and accent colours (no stage filter), -5 only, editor from the version in force, activation modal with reason chips"
  - "[ ] 11. Stav systému and Správa dat: content over their backends"
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
- Lucide icons in Settings now (lucide-react, pinned): tab icons and icon buttons with a label and
  tooltip; consequential actions keep their text.
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
