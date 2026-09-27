# Value

The one way a figure is rendered: value, zero, chybí, potlačeno or loading, with an optional evidence grade.

**The consumer provides:** `value` (number or null), or `state` (`value` · `zero` · `na` · `suppressed` · `loading`), plus `format`, `digits`, `role`, `inheritRole` (the column's declared grade: the mark is omitted when it matches), `reason` and `showReason` for suppression.

**Use:** Use it in every table cell and inline figure.

**Don't:** Never coalesce null to 0 or to “—”. A null value renders “chybí”. Suppression always carries its reason.
