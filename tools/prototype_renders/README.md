# Prototype reference renders

The scripts that draw every prototype board and page as an image, so a canvas rebuilt in the other account can be
compared with what it was. The images live beside each prototype, in `prototypes/<name>/reference/`, with a
`renders.json` giving each image's title, size, text characters rendered, and any console errors or failed requests.
The `artifact-sync` skill (`.claude/skills/artifact-sync/`) says when to run them: after every export of a canvas.

| Script | Draws | Run |
|---|---|---|
| `render.js` | each board of every Design canvas under a folder (a folder holding `canvas.json`), at its own size, full page | `node tools/prototype_renders/render.js <folder holding the canvas folders> <out dir> [one canvas folder]` |
| `pages.js` | the Design System page (light, then dark through its own theme button) and the UX upgrade's before/after page, at 1440 px | `node tools/prototype_renders/pages.js <folder holding design-system and ux-upgrade> <out dir>` |

## How they draw

- **The canvas runtime:** each board loads `./support.js`, the Design type's own runtime (`artifact-type/dc-runtime.js`,
  read from a canvas with the Artifact tool). It is the type's file, so it is never committed. Copy the canvas folders
  to a scratch directory, save the runtime into each as `support.js`, and point `render.js` at the copy.
- **Rendering:** Chromium through Playwright, served over local HTTP. Light theme, the pointer moved off the page, so
  no hover state shows.
- **Format:** PNG out; convert each to WebP at quality 88 into the folder's `reference/` to keep the repo small.
- **What to check:** no script error on any image. A failed request must be explained. Today the research `Report`
  and `ReportEditor` boards request their `{{shot}}` image placeholders before the runtime fills them, and those 404s
  are harmless.

## The current images (27 Oct 2026)

| Folder | Version | Images |
|---|---|---|
| `prototypes/clients/reference/` | Klienti v20, core v4.3 | 8 boards |
| `prototypes/research-stages/reference/` | Výzkumné kroky v95, core v4.3 | 24 boards |
| `prototypes/settings/reference/` | Nastavení v117, core v4.3 | 11 boards |
| `prototypes/design-system/reference/` | Design System v3.2 (artifact v12), light and dark | 2 pages |
| `prototypes/ux-upgrade/reference/` | the before/after page | 1 page |
