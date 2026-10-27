# Otázky k rozhodnutí

Where `tokens.json` (what ships), core v3 and the boards (what was approved), and LOOK.md (the contract) disagree. Only the product owner decides; each has a recommendation, following LOOK.md's own order: his words, then what ships, then the richer prototype.

| Id | Question | Where they disagree | Recommendation |
|---|---|---|---|
| D1 | What happens to the old `design-system/` package? | It claims parity with `tokens.json`; 17 colours, the radii and the status map are out of date. | **Regenerate it from this system**, so design tools keep a correct copy; or delete it and point here. |
| D2 | Input height | LOOK.md: 32 px, 13 px text. The v73 boards: about 36 px, 14 px (`.inp`, `.ta`). The product: 36/14. | **32/13, as LOOK.md says**; the boards follow. |
| D3 | The old `/studies` pages and `components/live/` | Raw Tailwind colours and amber; 3 pages. | **Retire the pages**, once a check shows every function they offer has a home under `/app`; else rebuild them on the shared parts. |
| D4 | Green on the Data tab and the Společenská inteligence rail tile | LOOK.md: green only for "in force", but wayfinding tints are allowed at ≤ 9 %. | **Keep as wayfinding**, at the contract's tint, never as a status. |
| D5 | "Čeká na vás" glyph | LOOK.md and core v3 `.st .g.you`: a filled coral circle. Research `aia-study.css` `.stg.youq`: a 6-radius coral square with a pause. | **The circle, with the pause glyph inside**, so all statuses are circles. |
| D6 | "Na rozpočtu" on the respondent disc | The board uses amber `#f0b429` (`--pfill` default) for a parked step. LOOK.md: no amber; parked on a person is coral, waiting on others slate. | **Coral for those who can lift the budget, slate for others.** |
| D7 | Weight 700 in the boards | The boards' Google Fonts link loads Plex at 700; LOOK.md allows 400/500/600. Only the research canvas's retired Hatch and LeadSettings copies set 700; core v3 and aia-study set none. | **Drop 700 from the boards' font link**, and remove the two retired copies from the research canvas. |
| D8 | z-index | core v3: scrim 50, toast 60. `tokens.json`: overlay 40, toast 50. | **The tokens win**; core's next version follows. |
| D9 | `num-hero` weight | `tokens.json` 28/32 at 500. LOOK.md: figures at 600. | **600**, and add `figure` / `figure-xl`. |
| D10 | Type tokens LOOK.md names but `tokens.json` lacks | hero 40/46, lede 16/24, eyebrow, figures; `Hero.tsx` hard-codes them. | **Add them to `tokens.json`** (drafted here as "Hlavičky v2"). |
| D11 | Diff colours | `diff-*` exist only in core v3. | **Add them to `tokens.json`** (drafted here). |
| D12 | Dialog width | LOOK.md and core: 560, padding 24. Research `.sdlg`: 520, padding 20. | **560/24**. |
| D13 | Running glyph | LOOK.md: a 2 px signal ring. Research `.stg.run`: a spinning arc (2.5 px, signal top on wash). | **The still ring** (core `.st .g.run`); motion only in the Thinking orb. |
| D14 | The Lead's mark in the product | The product draws the AIA lattice (`workbench/Icons.tsx:39` Mark) for the Lead. Settings defines five Lead marks per researcher. | **The AIA mark stays the product's identity; the Lead takes the researcher's chosen mark** (built with Můj Vedoucí). |
| D15 | Remaining old usage notes in `tokens.json` | Some notes still describe the scope bar, "Studio v3" and the warm paper ground. | **Rewrite the notes in the token PR** (several are rewritten here). |
