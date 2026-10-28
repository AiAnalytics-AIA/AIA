# Ikona (Icon)

Phosphor Regular (`@phosphor-icons/core` 2.1.1, MIT) everywhere (UI-2): 16 px in text and controls, 14 px in small buttons, 20 px in tiles; colour `currentColor`. The rail keeps its own navigation icons. No emoji, no unicode symbol as an icon (✓ ⚠ ▸ ⓘ →). An icon never stands for a status: status is StatusGlyph.

**The set** the 93 glyphs core v3 carries are in Assets → Icons. The product registers 58 today (`components/icons/phosphor.ts`); 40 the boards use are missing from it (eye, pause, play, file-text, exclamation-mark …), 22 it has are on no board.

**Replaces** the two name maps (`rehome/icons.tsx`, `workbench/Icons.tsx:34`, where "next" is arrow-right in one and caret-right in the other) → one `Icon`; 41 unicode marks and the one emoji (`ResearcherSpendCard.tsx:118`); ~100 icons at 12 or 14 px outside small buttons.
