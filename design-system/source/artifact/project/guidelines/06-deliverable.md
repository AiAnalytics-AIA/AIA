# The Deliverable register

The report is the product. It is set as premium consultancy output: Source Serif 4 prose, Plex Sans for figures, tables and captions, and one accent (`doc-accent`), which prints as dark grey.

## Page system

| Element | Style | Rule |
|---|---|---|
| Cover | `doc-title` (Source Serif 4 Display 44/48), client · "Důvěrné", subtitle, date · revision · pages, the population field bottom-right | The cover names who signed it off, or "čeká na podpis" in a draft |
| Running head | `doc-caption`, rule below | Report title left, page right |
| Chapter | `doc-h1` with a sans number in `doc-accent` | Numbered, 32px above |
| Headline paragraph | `doc-lede` (18/28) | The answer to the client's question, with its grade in the margin |
| Body | `doc-body` (15/24 on screen, 10.5/16.8pt in print) | Hyphenated, max 72ch |
| Evidence margin | the grade mark 28px left of the paragraph | Every paragraph that states a figure carries one |
| Holdout statement | a boxed sans statement in body size | In the chapter it qualifies, before the figures — never in a footnote |
| Figure | vector, direct labels, `doc-caption` below | The caption names n and every grade used |
| Table | sans 12/16, a 1px ink rule under the header, `doc-rule` between rows | The column declares its grade; cells mark only exceptions |
| Footnote | `doc-footnote` above a rule | Explains modelled figures and suppression |
| Evidence appendix | a table of every figure → role → source artifact | Generated from provenance, never hand-written |

## Export: what degrades and what must not

| Content | PDF | DOCX | Must not degrade |
|---|---|---|---|
| Text, headings | Live text, fonts embedded (OFL permits it) | Live text; fonts embedded or substituted by name | Czech diacritics — test every weight |
| Evidence marks ■ ▣ □ ⬚ ? | Vector | Inline vector images (SVG with an EMF/PNG fallback), sized to the cap height. **Never characters**: neither IBM Plex Sans nor Source Serif 4 has U+25A1, U+25A3 or U+2B1A, so a character mark would fall back to an arbitrary system font — verified with fontTools on the shipped files | The distinction itself: hollow vs filled must survive a 1-bit printer |
| Dotted/dashed underlines on modelled values | Vector | Word dotted/dashed underline | Present on every modelled number |
| Charts | Vector (SVG → PDF) | SVG plus a 300 dpi PNG fallback | Hatches, dash patterns, direct labels |
| *Chybí* / *potlačeno* cells | Vector hatch / bar | Cell shading pattern + text | The word itself — it is text, so it survives any pattern loss |
| Holdout statement | A boxed paragraph | A bordered paragraph | Its position: in the chapter, before the figures |
| Cover field | Vector | Embedded SVG with a PNG fallback | — (decorative; may rasterise) |
| Colour | CMYK-safe; `doc-accent` only | The same | Nothing depends on colour: see the greyscale proof |

A draft exported before sign-off carries a "NESCHVÁLENO" watermark on every page. It goes to a client only after the human sign-off (`SIGN_OFF_DELIVERABLE`).
