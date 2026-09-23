# Brand assets

Ported from the AIA Design System artifact; these files are now the source.
Single-ink SVGs name their ink because `<img>` cannot inherit colour:
`#151a20` (`ink`, light), `#ece9e4` (`ink`, dark) on graphite `#0f1215`, apex
`#006b9f` / `#6ac5e8` (`signal`). In the app, prefer `components/brand/Wordmark`,
which follows the theme.

- `aia-mark*.svg` — the population lattice resolving into A. ≥ 20px; below that use the favicon.
- `aia-wordmark*.svg`, `aia-lockup*.svg` — minimum height 16px / 24px. The lockup's text is outlined (IBM Plex Sans Medium).
- `lattice-field*.svg`, `section-divider.svg`, `report-cover-field.svg` — the motif. Never behind data.
- `icon-512.png` — the app icon. Favicons live in `src/app/` (`favicon.ico`, `icon.svg`, `apple-icon.png`) per the App Router convention.

Clear space: one lattice pitch (⅙ of the mark's width). Never recolour the apex
except to the mono ink.
