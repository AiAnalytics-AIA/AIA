# Report fonts

The TrueType faces the DOCX report embeds, so a report looks the same on a machine
that has none of them installed. They are the **same families** the web client
serves as WOFF2 (`apps/web/public/skin/fonts/`); Word cannot embed WOFF2.

**The files are the upstream releases, byte for byte. Do not modify or rename
them.** Both licences reserve their font names ("Plex", "Source"): a modified or
renamed face would have to carry a different name. That is also why weight 600
is its own family here (`Source Serif 4 Semibold`, `IBM Plex Sans SmBld`) rather
than a renamed Bold. `SHA256SUMS` pins every file, and
`test_report_fonts.py::test_vendored_fonts_match_their_checksums` fails on any
change.

| Word font name | File | Upstream | Licence |
|---|---|---|---|
| Source Serif 4 | `SourceSerif4-Regular.ttf`, `-It`, `-Bold`, `-BoldIt` | npm `source-serif` 4.5.1, `TTF/` (sha256 `19a448df…d80746` of the tarball) | SIL OFL 1.1, `LICENSE-Source-Serif-4.md` |
| Source Serif 4 Semibold | `SourceSerif4-Semibold.ttf` | same | same |
| Source Serif 4 Display Semibold | `SourceSerif4Display-Semibold.ttf` | same | same |
| IBM Plex Sans | `IBMPlexSans-Regular.ttf`, `-Italic`, `-Bold`, `-BoldItalic` | GitHub release `@ibm/plex-sans@1.1.0`, `ibm-plex-sans.zip`, `fonts/complete/ttf/` (sha256 `fb365d91…c69200`) | SIL OFL 1.1, `LICENSE-IBM-Plex-Sans.txt` |
| IBM Plex Sans SmBld | `IBMPlexSans-SemiBold.ttf` | same | same |
| IBM Plex Mono | `IBMPlexMono-Regular.ttf` | GitHub release `@ibm/plex-mono@2.5.0`, `ibm-plex-mono.zip`, `fonts/complete/ttf/` (sha256 `6d23f012…bc481c`) | SIL OFL 1.1, `LICENSE-IBM-Plex-Mono.txt` |

Every face has `OS/2.fsType = 0` (installable embedding permitted), TrueType
outlines, and the full Czech range (Latin Extended-A). The versions match the web
client's WOFF2 files. **None has the evidence-mark shapes**, so evidence marks
are vector images in the report, never characters.

The set is exactly `domain/report/print_tokens.FONTS` — the faces the print
register can resolve to. Adding a face to `tokens.json`'s `print.faces` without
vendoring it here fails `test_every_print_font_is_vendored`.
