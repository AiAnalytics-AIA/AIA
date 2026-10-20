# settings-prototype (AIA design: Settings prototype)

Updated 2026-10-20. Design prototype only: no product code, no product PR (scope freeze, MP16).

## Done (published, verified only as noted)
- Design artifact "AIA Nastavení – prototyp": https://claude.ai/artifact/8W9LR8Ju9BWnR5JACmiWv7 (private to Nigel until he shares it).
  10 interactive artboards, one per tab: Metodika, Systémové prompty, Deep Research, AI běh, Přístup a schvalování,
  Studie a rozpočty, Audit, Stav systému, Reference, Správa dat (proposal, N12).
- Bound decisions applied: D-13 (only aia-sociomap-5), D-14 (Metodik mark, OWNER grants; admins read-only), Q8 a
  (compare shows positions, credibility, respondents, segments), D-17 (posture and wallet ceiling set on Profil → Pravidla;
  Settings lists them read-only, I15 @ efc6dbc), X10 (no draft-prompt test), operator switches read-only, Q7 a (GlitchTip → Nigel).
- The earlier single-file HTML version was checked in headless Chromium (4 roles × 10 tabs, no JS errors, no overflow at 390 px).
  The Design-format artboards were not rendered by me.

## Owner decisions that change a plan
- 2026-10-20 21:10 (Nigel, via coordinator 3): no input boxes overlaid on the screen. Edit in place (Enter/blur saves, Esc cancels),
  steppers for numbers, segmented controls / chips for predetermined answers, an inline "new" row for creating, a modal only
  for a consequential action. Applied to every Settings artboard (round 2): role, client status and self-approval as segmented
  controls; Metodik as a switch; budgets, thresholds and methodology parameters as steppers with in-place typing; Deep Research
  proposals made in the Návrh cell; add member as an inline row; Lead read/handover as an expanding row; modals kept only for
  methodology activation (reason chips + in-place note), deactivating a member and deleting a client (acknowledge switch, no typed name).
  Affects every Settings plan's UI chunks (settings-workspace-ux, methodology-tab, system-prompts-settings, client-budget).

## Open, with Nigel
1. Hide Sociomapping (H-Model) and the 18.6.6 reference map in Metodika (recommended).
2. A Správa dat tab for client delete and kept records (N12; recommended) vs Přístup → Klienti.
3. Lead read/handover from Přístup (recommended) vs Můj Vedoucí (LO11).
4. Stav systému as its own tab (recommended) vs inside Reference.
5. Prompts edited by OWNER/ADMIN (recommended) vs a new mark.
