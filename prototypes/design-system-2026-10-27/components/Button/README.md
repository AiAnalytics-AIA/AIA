# Tlačítko (Button)

One button, five kinds: primary, secondary, quiet, danger and AI; 32 px high (small 28), radius 6, 13/500.

**Use**
- `primary` (`signal`): the one forward action of a view: "Návrh", "Uložit jako v3". At most one per view.
- secondary (default, raised with `border-strong`): every other action.
- `quiet`: a cancel or a low action beside another ("Zrušit", "Teď ne", "Přehled").
- `danger` (fault outline, transparent): only what cannot be undone ("Smazat natrvalo", "Deaktivovat"). Never fault-filled.
- `ai` (`ai` fill, `on-ai` text): only a start that pays a model from a budget. It leads with its amount: `<b class="amt">0,40 USD</b>` ("should focus on the 10 USD").
- `sm` (28 px) inside cards, tables and the Lead pane.

**The consumer provides** a label in Czech, sentence case, saying what happens; an optional Phosphor icon (16 px, `.ph.s` 14 px in `sm`); an amount for a paid start, formatted `1 250,00 USD`.

**Rules**
- No green "ok" button, ever. No pill-shaped buttons.
- Disabled is 45 % opacity with `cursor: not-allowed` and a reason nearby (a caption or `title`), never a silent grey.
- Focus: the 2 px `focus-ring` outline with 2 px offset.

**Replaces** `rehome/ui.tsx:34` Button (36/14 → 32/13), `rehome/ui.tsx:57` AiButton (600 weight and glow ring dropped, amount slot added), `live/ui.tsx:21` Button (zinc), workbench.css `.btn--*` (BEM copy, `--sm` 26 → 28), the hand-made danger buttons (`DataPanel` DangerButton, `step.tsx:342` InlineConfirm's filled yes, workbench `.btn--danger`). 171 hand-rolled `<button>`s in 45 files move to it.


**AI (v3.1)**: graphite with the spark edge, not a colour. The edge turns on hover and focus and while the job runs; see AiSpark.
