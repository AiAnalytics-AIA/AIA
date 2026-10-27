# Reference renders of the three prototype canvases, 27 Oct 2026

What every board looked like when the canvases were frozen and design moved to Nigel's other account. After
rebuilding a canvas there, compare each board with its image here, side by side, to catch anything lost in the move.

| Folder | Canvas | Exported in | Boards |
|---|---|---|---|
| `clients-2026-10-27/` | AIA Klienti – prototyp, v18 (artifact version `1793095242-1377`) | #1026 | 8 |
| `research-stages-2026-10-27/` | AIA Výzkumné kroky – prototyp, v93 (`1793095498-cbb2`) | #1027 | 24 |
| `settings-2026-10-27/` | AIA Nastavení – prototyp, after v112 (`1793094882-5e7e`) | #1028 | 11 |

Each image is named `NN-<board>.webp`, in the order of the board list in the canvas's `canvas.json`.

## How they were made

- Each exported folder was rendered with the Design type's own runtime, the file the canvas loads as `support.js`.
  It was read from the live Klienti canvas on 27 Oct, `artifact-type/dc-runtime.js`, SHA-256 `b795ee21…191844`, and is
  not committed here. Rendering used Chromium (Playwright), served over local HTTP.
- **Board size:** each board at its own width and height from `canvas.json` (1440 px wide), full page.
- **Settings:** the light theme (each board's default); the pointer off the board, so no hover state shows.
- **Format:** WebP at quality 88, converted from PNG to keep the folder small (8 MB).
- **`renders.json`:** per board, its title, size, the number of text characters rendered, and any console errors or
  failed requests.
  - All 43 boards rendered with no script error.
  - Two boards (`Report`, `ReportEditor`) log one or two 404s for `{{shot}}`-style image placeholders. The browser
    requests these before the runtime fills them in; the real images load after.

## Known in these images, to be fixed in the design system's final export

- The left rail's hover makes its text white on a light rail; only a hover shows it, so these images don't.
- The rail may still show Projektová paměť on boards drawn before its removal.
- The ⋯ icon is drawn locally on some boards.

## Re-rendering

Run `node render.js <folder holding the canvas folders> <out dir> [one canvas folder]` after saving the Design
type's runtime into each canvas folder as `support.js`. The runtime is the type's own file, so it is never committed.
