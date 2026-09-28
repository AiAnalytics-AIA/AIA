# Accessibility report

Floor: WCAG 2.2 AA throughout. **AA-plus** on numeric and status text: every figure a conclusion rests on is set in `ink` at ≥ 7:1 on every surface and status wash, in both themes. Everything below was measured, not asserted. The checks were produced by the scripts that generated `tokens.json` (OKLCH → sRGB, WCAG 2 relative luminance) and by the data-viz palette validator (OKLab ΔE × 100, Machado–Oliveira–Fernandes 2009 CVD simulation at severity 1.0).

## 1. Contrast — both themes

Text pairs name their ground; non-text pairs (control borders, focus ring, client band, recovery hatch) are held to 3:1. The focus ring always sits on its 2px `surface` gap, so its ground is a surface, never the fill beneath.

| Foreground | Ground | Use | Floor | Light | Dark |
|---|---|---|---|---|---|
| `ink` | `surface` | numeric/body text | 7.0:1 | 16.24 ✓ | 15.52 ✓ |
| `ink` | `surface-raised` | numeric/body text | 7.0:1 | 17.08 ✓ | 14.42 ✓ |
| `ink` | `surface-sunken` | numeric/body text | 7.0:1 | 15.12 ✓ | 16.26 ✓ |
| `ink` | `surface-overlay` | numeric/body text | 7.0:1 | 17.21 ✓ | 13.38 ✓ |
| `ink` | `signal-wash` | numeric/body text | 7.0:1 | 14.49 ✓ | 11.20 ✓ |
| `ink` | `status-running-wash` | numeric/body text | 7.0:1 | 14.49 ✓ | 11.64 ✓ |
| `ink` | `status-world-wash` | numeric/body text | 7.0:1 | 14.20 ✓ | 12.45 ✓ |
| `ink` | `status-you-wash` | numeric/body text | 7.0:1 | 15.31 ✓ | 11.34 ✓ |
| `ink` | `status-fault-wash` | numeric/body text | 7.0:1 | 14.94 ✓ | 11.94 ✓ |
| `ink-muted` | `surface` | secondary text | 4.5:1 | 8.55 ✓ | 9.71 ✓ |
| `ink-muted` | `surface-raised` | secondary text | 4.5:1 | 9.00 ✓ | 9.02 ✓ |
| `ink-muted` | `surface-sunken` | secondary text | 4.5:1 | 7.96 ✓ | 10.18 ✓ |
| `ink-muted` | `surface-overlay` | secondary text | 4.5:1 | 9.07 ✓ | 8.37 ✓ |
| `ink-faint` | `surface` | secondary text | 4.5:1 | 5.80 ✓ | 6.78 ✓ |
| `ink-faint` | `surface-raised` | secondary text | 4.5:1 | 6.10 ✓ | 6.30 ✓ |
| `ink-faint` | `surface-sunken` | secondary text | 4.5:1 | 5.40 ✓ | 7.11 ✓ |
| `ink-faint` | `surface-overlay` | secondary text | 4.5:1 | 6.15 ✓ | 5.85 ✓ |
| `ink-muted` | `signal-wash` | secondary on selection | 4.5:1 | 7.63 ✓ | 7.01 ✓ |
| `signal` | `surface` | link / running label | 4.5:1 | 5.41 ✓ | 9.63 ✓ |
| `signal` | `surface-raised` | link / running label | 4.5:1 | 5.69 ✓ | 8.95 ✓ |
| `signal` | `surface-sunken` | link / running label | 4.5:1 | 5.04 ✓ | 10.09 ✓ |
| `signal` | `signal-wash` | link / running label | 4.5:1 | 4.83 ✓ | 6.95 ✓ |
| `on-signal` | `signal` | text on signal fill | 4.5:1 | 5.69 ✓ | 10.09 ✓ |
| `status-you-ink` | `surface` | waiting-on-you text | 4.5:1 | 5.29 ✓ | 11.01 ✓ |
| `status-you-ink` | `surface-raised` | waiting-on-you text | 4.5:1 | 5.56 ✓ | 10.23 ✓ |
| `status-you-ink` | `surface-sunken` | waiting-on-you text | 4.5:1 | 4.92 ✓ | 11.54 ✓ |
| `on-status-you` | `status-you` | label on parked-on-you fill | 7.0:1 | 9.16 ✓ | 10.57 ✓ |
| `status-world` | `surface` | waiting-on-world text | 4.5:1 | 5.54 ✓ | 7.63 ✓ |
| `status-world` | `surface-raised` | waiting-on-world text | 4.5:1 | 5.83 ✓ | 7.09 ✓ |
| `status-world` | `surface-sunken` | waiting-on-world text | 4.5:1 | 5.16 ✓ | 8.00 ✓ |
| `status-world` | `status-world-wash` | waiting-on-world text | 4.5:1 | 4.84 ✓ | 6.12 ✓ |
| `status-fault` | `surface` | failed text | 4.5:1 | 5.99 ✓ | 7.10 ✓ |
| `status-fault` | `surface-raised` | failed text | 4.5:1 | 6.30 ✓ | 6.59 ✓ |
| `status-fault` | `surface-sunken` | failed text | 4.5:1 | 5.58 ✓ | 7.44 ✓ |
| `status-fault` | `status-fault-wash` | failed text | 4.5:1 | 5.51 ✓ | 5.46 ✓ |
| `on-status-fault` | `status-fault` | label on failed fill | 4.5:1 | 6.30 ✓ | 7.44 ✓ |
| `on-status-recovery` | `status-recovery` | label on recovery fill | 7.0:1 | 16.24 ✓ | 15.52 ✓ |
| `ink-inverse` | `surface-inverse` | inverse text | 7.0:1 | 16.24 ✓ | 15.52 ✓ |
| `on-client` | `client-1` | monogram on client accent | 4.5:1 | 5.19 ✓ | 10.19 ✓ |
| `on-client` | `client-2` | monogram on client accent | 4.5:1 | 10.16 ✓ | 5.66 ✓ |
| `on-client` | `client-3` | monogram on client accent | 4.5:1 | 7.91 ✓ | 7.02 ✓ |
| `on-client` | `client-4` | monogram on client accent | 4.5:1 | 4.70 ✓ | 10.93 ✓ |
| `on-client` | `client-5` | monogram on client accent | 4.5:1 | 5.05 ✓ | 10.43 ✓ |
| `on-client` | `client-6` | monogram on client accent | 4.5:1 | 10.11 ✓ | 5.71 ✓ |
| `doc-ink` | `doc-paper` | report prose | 7.0:1 | 18.49 ✓ | 18.49 ✓ |
| `doc-muted` | `doc-paper` | captions | 4.5:1 | 9.06 ✓ | 9.06 ✓ |
| `doc-accent` | `doc-paper` | report headings accent | 4.5:1 | 8.27 ✓ | 8.27 ✓ |
| `border-strong` | `surface` | control border | 3.0:1 | 3.66 ✓ | 4.05 ✓ |
| `border-strong` | `surface-raised` | control border | 3.0:1 | 3.85 ✓ | 3.76 ✓ |
| `border-strong` | `surface-sunken` | control border | 3.0:1 | 3.40 ✓ | 4.24 ✓ |
| `focus-ring` | `surface` | focus ring | 3.0:1 | 5.41 ✓ | 9.63 ✓ |
| `focus-ring` | `surface-raised` | focus ring | 3.0:1 | 5.69 ✓ | 8.95 ✓ |
| `focus-ring` | `surface-sunken` | focus ring | 3.0:1 | 5.04 ✓ | 10.09 ✓ |
| `focus-ring` | `surface-overlay` | focus ring | 3.0:1 | 5.73 ✓ | 8.30 ✓ |
| `focus-ring` | `signal-wash` | focus ring | 3.0:1 | 4.83 ✓ | 6.95 ✓ |
| `focus-ring` | `status-you-wash` | focus ring | 3.0:1 | 5.10 ✓ | 7.04 ✓ |
| `focus-ring` | `status-fault-wash` | focus ring | 3.0:1 | 4.98 ✓ | 7.41 ✓ |
| `status-you` | `surface` | parked fill (shape carries it) | 1.0:1 | 1.77 ✓ | 10.57 ✓ |
| `status-recovery-hatch` | `status-recovery` | recovery hatch | 3.0:1 | 4.39 ✓ | 3.25 ✓ |
| `client-1` | `surface` | client band on surface | 3.0:1 | 4.94 ✓ | 9.72 ✓ |
| `client-1` | `surface-raised` | client band on surface | 3.0:1 | 5.19 ✓ | 9.03 ✓ |
| `client-2` | `surface` | client band on surface | 3.0:1 | 9.66 ✓ | 5.40 ✓ |
| `client-2` | `surface-raised` | client band on surface | 3.0:1 | 10.16 ✓ | 5.02 ✓ |
| `client-3` | `surface` | client band on surface | 3.0:1 | 7.52 ✓ | 6.70 ✓ |
| `client-3` | `surface-raised` | client band on surface | 3.0:1 | 7.91 ✓ | 6.22 ✓ |
| `client-4` | `surface` | client band on surface | 3.0:1 | 4.47 ✓ | 10.43 ✓ |
| `client-4` | `surface-raised` | client band on surface | 3.0:1 | 4.70 ✓ | 9.69 ✓ |
| `client-5` | `surface` | client band on surface | 3.0:1 | 4.80 ✓ | 9.95 ✓ |
| `client-5` | `surface-raised` | client band on surface | 3.0:1 | 5.05 ✓ | 9.24 ✓ |
| `client-6` | `surface` | client band on surface | 3.0:1 | 9.61 ✓ | 5.45 ✓ |
| `client-6` | `surface-raised` | client band on surface | 3.0:1 | 10.11 ✓ | 5.06 ✓ |
| `viz-axis` | `surface` | axis labels | 4.5:1 | 8.55 ✓ | 9.71 ✓ |
| `viz-axis` | `surface-raised` | axis labels | 4.5:1 | 9.00 ✓ | 9.02 ✓ |

73 pairs × 2 themes = 146 checks, 0 failures.

Client accents, light: nearest status/UI/categorical token ΔE 7.6 (`client-5` vs `focus-ring`); nearest other accent ΔE 13.3 (`client-3` vs `client-4`).

Client accents, dark: nearest status/UI/categorical token ΔE 7.7 (`client-6` vs `viz-cat-4`); nearest other accent ΔE 12.9 (`client-4` vs `client-5`).

Status vs categorical, light: nearest pair ΔE 9.3 (`status-running` vs `viz-cat-1`).

Status vs categorical, dark: nearest pair ΔE 10.9 (`status-fault` vs `viz-cat-2`).

`status-you` (amber) as a fill is deliberately not a text colour: on paper it is 1.9:1 as a *mark*, so the parked state is carried by its label in `on-status-you` (≥ 7:1 on the fill) and by the solid-square shape. On a surface, amber text uses `status-you-ink` (≥ 4.5:1).

## 2. Data-viz palette — colour-blind validation

Six categorical slots in fixed order: blue, orange, aqua, violet, green, magenta. The two hues the status family reserves — amber (waiting on you) and red (failed) — are left out of the categorical palette entirely. The order was chosen by enumerating all 120 orderings with blue first and keeping only those that pass every hard gate in both themes. Validator output, verbatim:

```
== light, adjacent

Palette (light, surface #f9f6f2, categorical): 6 slots
  [PASS] Lightness band         all 6 inside L 0.43–0.77
  [PASS] Chroma floor           all 6 >= 0.1
  [PASS] CVD separation         worst adjacent #1baf7a↔#eb6834 ΔE 9.2 (deutan) · tritan 13.1
  [PASS] Normal-vision floor    worst adjacent #1baf7a↔#eb6834 ΔE 27.6 (normal)
  [WARN] Contrast vs surface    below 3:1 — relief required (visible labels or table view): [["#eb6834",2.97],["#1baf7a",2.61],["#e87ba4",2.5]]

  → ALL CHECKS PASS  (CVD in the 6–8 floor band is legal ONLY with secondary encoding: direct labels, gaps, or texture)
  scope: categorical palettes only. For a lone status/text color check WCAG text contrast; for a sequential ramp, lightness monotonicity.

== dark, adjacent

Palette (dark, surface #0f1215, categorical): 6 slots
  [PASS] Lightness band         all 6 inside L 0.48–0.67
  [PASS] Chroma floor           all 6 >= 0.1
  [PASS] CVD separation         worst adjacent #199e70↔#d95926 ΔE 9.4 (deutan) · tritan 9.4
  [PASS] Normal-vision floor    worst adjacent #9085e9↔#199e70 ΔE 24.6 (normal)
  [PASS] Contrast vs surface    all 6 >= 3:1

  → ALL CHECKS PASS  (CVD in the 6–8 floor band is legal ONLY with secondary encoding: direct labels, gaps, or texture)
  scope: categorical palettes only. For a lone status/text color check WCAG text contrast; for a sequential ramp, lightness monotonicity.

== light, all pairs, first 3

Palette (light, surface #f9f6f2, categorical): 3 slots
  [PASS] Lightness band         all 3 inside L 0.43–0.77
  [PASS] Chroma floor           all 3 >= 0.1
  [PASS] CVD separation         worst all-pairs #1baf7a↔#eb6834 ΔE 9.2 (deutan) · tritan 9.6
  [PASS] Normal-vision floor    worst all-pairs #1baf7a↔#2a78d6 ΔE 24.0 (normal)
  [WARN] Contrast vs surface    below 3:1 — relief required (visible labels or table view): [["#eb6834",2.97],["#1baf7a",2.61]]

  → ALL CHECKS PASS  (CVD in the 6–8 floor band is legal ONLY with secondary encoding: direct labels, gaps, or texture)
  scope: categorical palettes only. For a lone status/text color check WCAG text contrast; for a sequential ramp, lightness monotonicity.

== dark, all pairs, first 3

Palette (dark, surface #0f1215, categorical): 3 slots
  [PASS] Lightness band         all 3 inside L 0.48–0.67
  [PASS] Chroma floor           all 3 >= 0.1
  [PASS] CVD separation         worst all-pairs #199e70↔#d95926 ΔE 9.4 (deutan) · tritan 4.0
  [PASS] Normal-vision floor    worst all-pairs #199e70↔#3987e5 ΔE 20.9 (normal)
  [PASS] Contrast vs surface    all 3 >= 3:1

  → ALL CHECKS PASS  (CVD in the 6–8 floor band is legal ONLY with secondary encoding: direct labels, gaps, or texture)
  scope: categorical palettes only. For a lone status/text color check WCAG text contrast; for a sequential ramp, lightness monotonicity.
```

- **Relief rule.** In the light theme orange, aqua and magenta sit below 3:1 on paper. Every chart therefore carries direct labels on its marks and a table view ("Zobrazit jako tabulku"). `GradedBars` does both.
- **All-pairs forms** (scatter, Sociomapa clusters, small multiples) validate for the first three slots. Past three, fold into "Ostatní" or facet.
- **Greyscale.** Categorical series are not expected to survive greyscale by hue. Series therefore also carry marker shape and dash pattern, and the evidence grade (solid / framed / hatched / dashed) is independent of hue.
- **Sequential** `viz-seq-1…7`: one hue, monotone lightness; the dark theme flips the anchor. **Diverging** `viz-div-1…7`: blue ↔ orange with a grey midpoint (`viz-div-4`), never a hue at the midpoint.

## 3. Greyscale print — evidence grades and states

Rendered from the live state gallery with `filter: grayscale(1)` (assets group *Accessibility*):

- `greyscale-evidence-grades.png`: ■ ▣ □ ⬚ ? remain distinct at number, cell, series, node and sentence scale.
- `greyscale-five-states.png`: running, parked-on-you, parked-on-world, failed and recovery are told apart by shape alone (circle-with-core / solid square / hollow dashed square / circle-with-× / inverse diamond).
- `greyscale-null-states.png`: value, zero, *chybí*, *potlačeno* and loading are distinct.
- `greyscale-ReportPage.png`: the Deliverable page printed in greyscale.

**Is any status distinguishable only by colour?** No. Every tone has a distinct glyph and a text label, and every row wash has a shape counterpart (the 4px amber rule on parked rows, the dashed border on world waits, the inverse block for recovery).

## 4. Czech at +35 % string length

Every text node on all 11 screens and 8 dense components was extended by 35 % with Czech diacritics (ěščřžýáíéůú). Overflow was then measured in a headless browser at 1280 px and at 1024 px (laptop):

- **Before fixes:** DataLibrary overflowed by 111 px, CostBudget by 34 px, ReportDelivery and Admin by up to 36 px, and the gallery cells by 25 px.
- **Fixes, now in `bundle.css`:** layout children may shrink (`min-width: 0`), table text may wrap (`overflow-wrap: anywhere`), dense tables scroll inside their panel (`.aia-scroll-x`), and status chips wrap before they would clip. A status label is never truncated.
- **After:** 0 unintended overflows at either width. The only elements still flagged are the intentionally clipped screen-reader labels.
- The test appends the extra length to the *last word*, which is harsher than real Czech (longer sentences, not longer words).

## 5. Keyboard model

| Keys | Action | Notes |
|---|---|---|
| `Tab` / `Shift+Tab` | Focus order: skip link → scope bar → stage rail → main → side panel | Every interactive element has the 2px ring |
| `⌘K` | Command palette | Go-to study is scoped: it lists only studies you hold a grant on |
| `?` | Shortcut overlay | — |
| `g p` · `g s` · `g c` | Portfolio · current study · costs | Two-key sequences, no modifier |
| `[` · `]` | Previous / next stage on the rail | The rail is an `ol` of buttons; `aria-current="step"` marks the current stage |
| `j` · `k` · `Enter` | Move through / open rows | Tables keep row focus, not cell focus, in compact density |
| `e` | Edit the focused field | Always opens `ImpactPreview` first; `⌘↵` commits a new revision, `Esc` discards |
| `a` | Approve the focused gate | Bound only when the viewer holds the permission; otherwise the key does nothing and the overlay omits it |
| `Esc` | Close dialog / popover | `ParkAndAsk` is an `alertdialog`; focus opens on its heading, never on "Schválit" |

Skip targets are "Přeskočit na obsah" and "Přeskočit na fáze". Status changes announce through the chip's text (never colour); a `RecoveryDecision` is `role="alert"`.

## 6. Self-assessment against the brief's ten questions

1. **Modelled vs measured, in a dense dark table and on paper, without a legend?** Yes. □ plus a dotted underline against ■; see the greyscale proof and the dark state gallery.
2. **Parked-on-me vs running vs failed across a room?** Yes. A solid amber square block, a blue ring and a red circle-×; shape alone carries them in greyscale.
3. **Zero vs never looked?** Yes. `0` is a plain figure; *chybí* is a boxed, hatched word in full ink.
4. **Two clients open — can you lose track?** The accent band, the monogram and the full client name are on every screen and every spending dialog. Residual risk: with more than six clients, accents repeat, so the name is primary by design.
5. **Consequences before commit?** Yes: `ImpactPreview`, bound to the domain `ImpactPreview`.
6. **Implied progress or certainty?** None. No percentage bars, spinners, shimmers or skeletons; missing estimates read *chybí*.
7. **Does the report look paid-for?** It is Source Serif 4 on a disciplined grid, numbered chapters, vector figures and an evidence margin. It is judged against the Deliverable screen and cover.
8. **Does a new domain status fail the build?** In the bundle, `checkTotality()` reports it and an unmapped value renders as "Neznámý stav". In `apps/web`, chunk 2 of the implementation plan makes it a `tsc` error *and* adds a CI check that diffs the Python enums against the TypeScript ones. Not built yet.
9. **Any status by colour only?** No.
10. **Does +35 % Czech break a layout?** No, after the fixes in §4, at both 1280 and 1024 px.
