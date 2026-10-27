# Reference renders of the prototypes, 27 Oct 2026

Every prototype board and page as it looked when design moved to Nigel's other account, after the design system's
v4.3 upgrade pass. After rebuilding a canvas there, compare each board with its image here, side by side, to catch
anything lost in the move.

| Folder | What | Exported in | Images |
|---|---|---|---|
| `clients-2026-10-27/` | AIA Klienti – prototyp, v20, core v4.3 | #1026 | 8 boards |
| `research-stages-2026-10-27/` | AIA Výzkumné kroky – prototyp, v95, core v4.3 | #1027 | 24 boards |
| `settings-2026-10-27/` | AIA Nastavení – prototyp, v117 (`1793098752-b063`), core v4.3 | #1028 | 11 boards |
| `design-system-2026-10-27/` | AIA Design System v3.2 (artifact v12, `1793100361-1081`), its `index.html` in light and dark | #1031 | 2 pages |
| `ux-upgrade-2026-10-27/` | The before/after page of the UX upgrade (`1793072278-450e`) | #1031 | 1 page |

Each board image is named `NN-<board>.webp`, in the order of the board list in the canvas's `canvas.json`.

## How they were made

- **Canvases:** rendered by `render.js` with the Design type's own runtime, the file a canvas loads as `support.js`:
  `artifact-type/dc-runtime.js`, SHA-256 `b795ee21…191844`, read from the live Klienti canvas on 27 Oct. It is the
  type's file, so it is not committed here. Each board at its own width and height from `canvas.json` (1440 px wide),
  full page.
- **Pages:** rendered by `pages.js` at 1440 px wide, full page. The Design System page is shot in light, then in dark
  through its own theme button.
- **Settings:** Chromium (Playwright) over local HTTP; boards in their default light theme; the pointer moved off the
  page, so no hover state shows.
- **Format:** WebP at quality 88, converted from PNG to keep the folder small (9 MB).
- **`renders.json`:** per image, its title, size, the number of text characters rendered, and any console errors or
  failed requests.
  - All 46 images rendered with no script error.
  - Two research boards (`Report`, `ReportEditor`) log one or two 404s for `{{shot}}`-style image placeholders. The
    browser requests these before the runtime fills them in; the real images load after.

## What v4.3 changed, and what these images show

- The left rail's hover no longer turns its text white on the light rail. Hover is not shown in these images.
- `.ph-dots-three` (the ⋯ icon) is in core.
- Projektová paměť is gone from Nastavení's rail and ⌘K palette. Its one remaining mention is content: the "where" of
  the `answer_memory` prompt on Prompts.
- The before/after page predates the AI spark edge and the redundancy pass; its own README says so.

## Re-rendering

- Canvases: save the Design type's runtime into each canvas folder as `support.js`, then run
  `node render.js <folder holding the canvas folders> <out dir> [one canvas folder]`.
- Pages: `node pages.js <folder holding design-system-2026-10-27 and ux-upgrade-2026-10-27> <out dir>`.
