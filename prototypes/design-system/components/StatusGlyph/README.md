# Stav (StatusGlyph and status pill)

One vocabulary for every state, a glyph always beside its word. Circles only: research's glyph circles at 14 / 16 / 20 px; Settings' 8 px dot only in dense tables.

| Stav | Glyph | Token |
|---|---|---|
| Hotovo | filled ink circle | `status-done` |
| Čeká na vás | filled coral | `status-you`, text `status-you-ink`; shown only to people who can act |
| Běží | 2 px signal ring | `status-running` |
| Čeká na rozpočet (for others) | filled slate | `status-world` |
| Chyba | filled fault | `status-fault` |
| Nezačato | 1.5 px strong ring | `border-strong` |
| V platnosti | filled green | `in-force` |

**Rules** done is quiet ink, never green; no amber anywhere; a person who cannot act on a wait sees slate, not coral; colour is never the only signal (word, and glyph shape for running and not started). Under reduced motion the running ring stops.

**Pills** (`.pill`, 24 h, radius 6) carry a glyph and a word: the stage navigator, Lead cards, tables.

**Replaces** `workbench/Glyph.tsx:14` (squares for you/world, a diamond for recovery, 12 px default), Phosphor icons used as status in `rehome/ui.tsx:85` Chip, `PlanStep.tsx:305` and `BriefStep.tsx:315`, `live/ui.tsx:67` Status (amber), workbench `.statepill` (r2), `StudiesPanel.tsx:39` unicode marks ✎ ▶ ◐ ✓ ▪ ✕. *Open question D5: research draws "Čeká na vás" as a 6-radius square with a pause (`.stg.youq`); LOOK.md says a filled circle. Recommended: the circle, with the pause glyph inside.*
