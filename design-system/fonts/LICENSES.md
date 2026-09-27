# Font licences

Every face here is licensed under the **SIL Open Font License 1.1**. The OFL
allows the fonts to be used, embedded (in PDF and DOCX too), self-hosted and
redistributed with software, provided that each copy carries its licence and
no copy is sold on its own. Modified versions may not use a Reserved Font Name
("Plex", "Source").

| Family | Files | Copyright | Version | Licence text |
|---|---|---|---|---|
| IBM Plex Sans | `IBMPlexSans-Regular.woff2`, `-Italic`, `-Medium`, `-SemiBold` | © 2017–2018 IBM Corp., Reserved Font Name "Plex" | 3.005 | [`LICENSE-IBM-Plex-Sans.txt`](LICENSE-IBM-Plex-Sans.txt) |
| IBM Plex Mono | `IBMPlexMono-Regular.woff2`, `-Medium` | © 2017 IBM Corp., Reserved Font Name "Plex" | 2.005 | [`LICENSE-IBM-Plex-Mono.txt`](LICENSE-IBM-Plex-Mono.txt) |
| Source Serif 4 | `SourceSerif4-Regular.woff2`, `-Italic`, `-Semibold` | © 2014–2023 Adobe, Reserved Font Name "Source" | 4.005 | [`LICENSE-Source-Serif-4.md`](LICENSE-Source-Serif-4.md) |
| Source Serif 4 Display | `SourceSerif4Display-Semibold.woff2` | © 2014–2023 Adobe, Reserved Font Name "Source" | 4.005 | [`LICENSE-Source-Serif-4.md`](LICENSE-Source-Serif-4.md) |

**Provenance.** These files are byte-identical to the ones in the AIA Design
System artifact and to `apps/web/public/skin/fonts/`. Their upstream sources
are npm `@ibm/plex-sans` 1.1.0, `@ibm/plex-mono` 2.5.0 and `source-serif`
4.5.1 (`apps/web/public/skin/fonts/README.md`). They are unmodified and not
subset.

## Czech coverage

Checked with fontTools 4.66 on every file here. Each face covers all Czech
letters (Á Č Ď É Ě Í Ň Ó Ř Š Ť Ú Ů Ý Ž and their lower case) and the Czech
quotation marks („ “ ‚ ‘), as well as – — and ….

| Family | Latin Extended-A (U+0100–U+017F) |
|---|---|
| IBM Plex Sans (all four) | 128 / 128 |
| IBM Plex Mono (both) | 128 / 128 |
| Source Serif 4, Source Serif 4 Display (all four) | 122 / 128. Missing: U+012C/U+012D Ĭ ĭ, U+0132/U+0133 Ĳ ĳ, U+0166/U+0167 Ŧ ŧ. None of these is used in Czech |

**No face has the evidence-mark shapes.** U+25A1 □, U+25A3 ▣ and U+2B1A ⬚
are missing from all of them, and U+25A0 ■ is missing from Plex Sans and Plex
Mono (only Source Serif 4 has it). This is
why evidence marks are always drawn as vector shapes, never as characters.
