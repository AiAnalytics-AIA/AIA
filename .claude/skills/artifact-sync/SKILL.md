---
name: artifact-sync
description: Export a shared claude.ai artifact (a Design canvas, the Design System, the Build Map, a build spec or decision page) into its folder in the repo, or publish one from the repo, so the product owner's two accounts work from the same files. Use after publishing a new version of a shared artifact, when asked to "export", "sync" or "put on GitHub" an artifact, or when rebuilding an artifact from the repo in the other account.
---

# /artifact-sync

The rule is CLAUDE.md §1, "Shared artifacts live in the repo". The permission is §5, "Artifact exports": a
change limited to `prototypes/` and `tools/build_map/` is committed, pushed and merged without asking,
once CI is green and Codex (or its stand-in) is clean on the head.

## Where each artifact lives

| Artifact | Folder | Kind |
|---|---|---|
| AIA Klienti – prototyp | `prototypes/clients/` | Design canvas |
| AIA Výzkumné kroky – prototyp | `prototypes/research-stages/` | Design canvas |
| AIA Nastavení – prototyp | `prototypes/settings/` | Design canvas |
| AIA Design System | `prototypes/design-system/` | Design System page and components |
| The shared core stylesheet (`aia-core-v<N>.css`) | `prototypes/shared/` | asset of the canvases |
| Research Stages Build Spec | `prototypes/research-stages/spec/` | page + Markdown |
| AIA Build Map | `tools/build_map/` (the page is built, never copied) | generator |
| Anything new | `prototypes/<short-name>/`, added to `prototypes/README.md` | |

`prototypes/README.md` is the index: each folder with the artifact's URL in each account. A folder's own
README names its current version.

## Exporting an artifact into the repo

1. **Read it, byte for byte.** `Artifact` `action: "list"`, `scope: "files"` on its URL, then `action:
   "read"` with `paths` (every file but the Design type's own `artifact-type/…` and `SKILL.md`) and `out_dir`
   in the scratchpad. A single-page artifact: `read` with `path: "index.html"`. Never retype a file.
2. **Branch from a fresh develop.** `git fetch origin develop`, then a worktree on
   `chore/export-<name>-<yyyy-mm-dd>` from `origin/develop`. Never the main checkout's working tree.
3. **Replace the folder's files.** The canvas's `project/` files go to the folder's root (`canvas.json`,
   `*.dc.html`, its stylesheets), uploaded assets to `assets/`. Rewrite each `/_blob/<id>` the boards
   load to its relative path. Delete what the new version dropped. Keep the README.
4. **README.** The version line: the artifact's title, version number, version id and date. Then one
   paragraph on what changed since the last export, and what is known to be wrong in it.
5. **Reference renders, for a canvas.** Save the Design type's runtime (`artifact-type/dc-runtime.js`,
   read from the canvas) into the folder as `support.js` in a scratch copy, never in the repo. Run
   `node tools/prototype_renders/render.js <scratch root> <out> <folder>` and convert each PNG to WebP at
   quality 88 into the folder's `reference/`, with `renders.json`. A page:
   `tools/prototype_renders/pages.js`. Check every render: no script error, and each failed request
   explained.
6. **Index.** Only when a folder is new or retired: add or remove its row in `prototypes/README.md`, in this
   same change, so the export and its entry land together.
7. **Stage, then check.** `git add -A` the folder (and the index, if it changed) first: `make
   exposure_check` reads the files git tracks, so an unstaged new file goes unchecked. It must pass before
   anything is committed: no client-identifying name, even by chance inside a base64 run (move such an
   image out to a file). Nothing secret, no real client data.
8. **Commit and merge.** Author `nigelblount <nigelblount@art-chain.io>` with the session's trailers. The
   subject says what changed in the artifact, not "export". Open the PR into `develop`, ready (not a
   draft), titled the same; then merge it with a merge commit once CI is green and Codex is clean on the
   head. A failure in code the export doesn't touch is not the export's; say so on the PR and re-run once.

## Publishing an artifact from the repo

- **A page** (spec, decision page): publish the folder's `index.html` with the `Artifact` tool. Give
  it a footer naming its source, `Source: <folder> @ <short sha>`.
- **The Build Map:** `python3 tools/build_map/build.py <a checkout of origin/develop> <out.html>`, then
  publish `<out.html>`. Change its data in `tools/build_map/*.json` through a PR.
- **A Design canvas in the other account:** create a Design artifact and add the folder's files as its
  project, with the stylesheet and assets uploaded and linked. Then compare each board with
  `reference/` and fix what differs. The first rebuild makes the new URL; add it to the index.

## Don'ts

- **No dated copies.** Never add `prototypes/<name>-<date>/` or `-v<N>/` beside the folder: git history
  is the version record.
- **No second artifact for the same thing.** Update the existing URL, or the index's URL for that account.
- **Nothing outside these paths under the standing permission.** If the export needs a code or docs
  change too, that part needs the product owner's words.
