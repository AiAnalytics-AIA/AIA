# Fonts

Self-hosted, served at `/skin/fonts/` and declared by the generated
`src/app/fonts.css` (`scripts/build-tokens.mjs`, `FACES`). AIA's own pages and
the 18.6.6 interface skin (ADR 0013) use the same files. Nothing is fetched from
a font CDN at build or run time.

| Family | Files | Source | Licence |
|---|---|---|---|
| IBM Plex Sans | Regular, Italic, Medium, SemiBold | npm `@ibm/plex-sans` 1.1.0, `fonts/complete/woff2` | SIL OFL 1.1 — `LICENSE-IBM-Plex-Sans.txt` |
| IBM Plex Mono | Regular, Medium | npm `@ibm/plex-mono` 2.5.0, `fonts/complete/woff2` | SIL OFL 1.1 — `LICENSE-IBM-Plex-Mono.txt` |
| Source Serif 4 (+ Display) | Regular, Italic, Semibold, Display Semibold | npm `source-serif` 4.5.1, `WOFF2/TTF` | SIL OFL 1.1 — `LICENSE-Source-Serif-4.md` |

All files carry the full Latin Extended-A range (ě š č ř ž ý á í é ů ú ň ť ď),
checked with fontTools. **None contains the evidence-mark shapes** (U+25A0,
U+25A1, U+25A3, U+2B1A), so evidence marks are always SVG, never characters.
