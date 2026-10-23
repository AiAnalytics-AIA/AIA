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
  proposals made in the Návrh cell; add member as an inline row; modals kept only for
  methodology activation (reason chips + in-place note), approving/withdrawing a DR policy, and deleting a client (acknowledge switch, no typed name).
- Round 3 (21:20): aligned with the input standard I1-I11 (input-interactions audit): steppers state bounds, Shift x10, out-of-range refused at the field; deactivate member is immediate with Vrátit (8 s), as are role and Metodik changes; Uloženo beside the value. Not built: leave-guard for the unsaved methodology draft (I10).
- Round 3b (21:23, coordinator relaying the owner's D-32/33/34, Q5 c, Q14 a, ADR 0030): no admin read or handover of a Lead. Removed from Přístup; a deactivated member's row and toast say the Lead is sealed, unreadable by anyone, deleted at the end of retention. Audit shows "Vedoucí zapečetěn".
  Affects every Settings plan's UI chunks (settings-workspace-ux, methodology-tab, system-prompts-settings, client-budget).

- 2026-10-21 (Nigel, in this session): accept all four recommendations. (1) Metodika hides the experimental Sociomapping (H-Model)
  and the 18.6.6 reference map, beside -1..-4; (2) a Settings tab "Správa dat" holds client delete (owner/admin, irreversible-action
  modal) and the kept records (N6, N12); (3) "Stav systému" is its own tab under Provoz (smoke rows + GlitchTip); (4) system prompts
  stay edited by OWNER/ADMIN, no new mark. Plans to carry it: study-data-lifecycle#SDL3 (delete entry point), mvp-acceptance-harness/MP6
  (Stav systému as the smoke's reader), system-prompts-settings, methodology-tab.
- Fix (2026-10-21): Přístup and other screens rendered broken because sc-for/sc-if inside <table> are foster-parented out by the HTML
  parser. Every dynamic table is now an ARIA grid of divs (role=table/row/cell).
- 2026-10-21 (Nigel): track each researcher's individual spend on Studie a rozpočty. Prototype: per-person total, share,
  split by activity, per-study breakdown, period selector. Decided (Nigel, Q40 a, 2026-10-21 11:42 UTC): attributed to whoever started or approved the paid
  work; OWNER/ADMIN see all, a researcher sees only their own. Needs an actor on every ledger and reservation row
  (develop-spend-attribution, I20). Carried as develop-spend-attribution chunk 7 (plan PR in progress); the prototype label is removed.
- Readability pass (2026-10-21, Nigel): Stav systému, Deep Research, Správa dat, Metodika: all information kept, sections separated.

## Design system update (2026-10-23, Version 51)

All ten artboards now use develop's Indigo tokens (1d7eae81) and the in-force green (be220ebc), light and dark, with no layout or content changes. Colour rules:
- green only on what is in force (the Metodika version, the switched-on prompt);
- coral only for "needs you", shown only to someone who can act; a non-admin sees slate;
- slate for waiting on the world;
- AI elements are purple;
- the spend split uses viz-cat v1–v4.

develop has no separate "parked" token, so each old amber was mapped by meaning to coral, slate or neutral. Contrast was checked on every changed pairing; the lowest text ratio is 4.69 (AI ink, dark). The coral dot gets a youink ring, because coral alone is 2.42:1.

## Open, with Nigel
None.
