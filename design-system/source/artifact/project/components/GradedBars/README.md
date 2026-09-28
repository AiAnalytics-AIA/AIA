# GradedBars

A bar chart whose bars carry their evidence grade, with direct labels.

**The consumer provides:** `rows` [`{label, value | null, state?, role, lo?, hi?}`], `label`, `color` (a categorical slot, default `viz-cat-1`), `max`, `width`.

**Use:** Use it for magnitudes by segment. A table view must be available alongside.

**Don't:** Text stays in text tokens. Intervals only where they exist. Chybí and potlačeno get their own marks, never a zero bar.
