# Prototypes

Design references for AIA's interface. None of this is product code: nothing here is imported by
`apps/web`, calls an AIA endpoint, a model or a paid service, and every client, study, person and
number in it is fictional.

**These are shared artifacts** (CLAUDE.md §1, "Shared artifacts live in the repo"). The owner works from two
claude.ai accounts, and neither can open the other's artifacts, so the repo is where they meet: each artifact has
one folder here, named without a date, updated in place by the `artifact-sync` skill. A folder's README names the
version it holds; git history keeps every earlier one. This index lists the folders and each artifact's link in each
account, and changes only when a folder is added or retired.

## The shared artifacts

| Folder | What | Kind | First account (nigelblount@art-chain.io) | Second account |
|---|---|---|---|---|
| [`clients/`](clients/) | "AIA Klienti – prototyp": the client pages (Klienti, Přehled, Výzkumy, Znalosti and item, Přidat podklady, Profil) | Design canvas, 8 boards | <https://claude.ai/artifact/4dP7Y43dtHcJFkJLD31hFo> | <https://claude.ai/artifact/76oZLbQk8Gt28qYahSHAs4> |
| [`research-stages/`](research-stages/) | "AIA Výzkumné kroky – prototyp": the eleven stages, the respondent disc, the Lead's cards and chat | Design canvas, 24 boards | <https://claude.ai/artifact/3dkKPTDoa1yvK4GCV7PLtJ> | <https://claude.ai/artifact/U4b83GH2X5coxx51ATL1T5> |
| [`research-stages/spec/`](research-stages/spec/) | The research stages build spec: the prototype mapped onto develop, stage by stage | page + Markdown | <https://claude.ai/artifact/8HJhn5tAsqt3Ugf6nzfQNy> | not rebuilt yet |
| [`settings/`](settings/) | "AIA Nastavení – prototyp": the eleven Settings pages | Design canvas, 11 boards | <https://claude.ai/artifact/8W9LR8Ju9BWnR5JACmiWv7> | <https://claude.ai/artifact/8bHnTkAJNiPNgGcYTzQqLS> |
| [`design-system/`](design-system/) | The AIA Design System: every component's preview and rules, tokens, the shared core stylesheet | page and components | <https://claude.ai/artifact/SEEkz1TrFgEZ1yK53Qmas4> | not rebuilt yet |
| [`ux-upgrade/`](ux-upgrade/) | The UX upgrade's before/after page and audits | page | <https://claude.ai/artifact/6duL5pNSVfiqqBz6V16Tfo> | not rebuilt yet |
| [`palettes/`](palettes/) | The palette study behind Petrol | page | <https://claude.ai/artifact/CcT6HoxR4EHpao5rXYrda7> | not rebuilt yet |
| [`../tools/build_map/`](../tools/build_map/) | The AIA Build Map, built from the repo by `build.py` | generated page | <https://claude.ai/artifact/XdjCNHdYnvcjYiijJpwrL3> | <https://claude.ai/artifact/SHi9i7hDJMFTEbArivLS95> |

Each canvas and page folder has a `reference/` folder of images of every board as it stood at that version; the
scripts that draw them are in [`../tools/prototype_renders/`](../tools/prototype_renders/). Rebuilding a canvas in
the second account: the `artifact-sync` skill, "Publishing an artifact from the repo". Put the new link in the last
column when it exists.

## History, kept as it was

- [`research-lead-v2/`](research-lead-v2/): the workbench prototype, the canonical design reference from 2026-10-20 to
  2026-10-26, and [`research-lead-v3/`](research-lead-v3/): its artifact boards as text. Where they disagree with the
  folders above, the folders above win.
- [`LOOK.md`](LOOK.md): the look contract of 26 Oct that the canvases followed before the Petrol design system.
- [`shared/aia-core.css`](shared/aia-core.css): core v3, the stylesheet of 26 Oct; each canvas now carries its own copy
  of the current core under `assets/`.
- The dated snapshots `settings-v99/` and `research-stages-v73/` (26 Oct) and the `*-2026-10-27/` export folders were
  replaced by the folders above on 27 Oct; they are in git history.

## How to read a `.dc.html` file

Each `.dc.html` is one **Design-canvas artboard**, not a web page. It loads `./support.js` (the canvas
runtime) and its scripts, and uses the canvas's own markup (`<x-dc>`, `<helmet>`, `<sc-if>`,
`<sc-for>`, `{{…}}` bindings and a `DCLogic` component class in a `text/x-dc` script). That runtime
exists only inside the canvas, so opened in a browser the file does not render as designed. Read it
as source: the markup, the copy, the class names and the component logic are the design.
`canvas.json` in each folder lists the boards, their titles, sizes and positions, and their order.

Links between boards (`href="Design.dc.html"`) are relative and resolve inside the folder. Links to
`https://claude.ai/artifact/…` point at the live canvases: the research boards' "Můj Vedoucí" button
opens the Settings canvas, and Sociomapa's "Otevřít živou dílnu" opens the Sociomap workshop
(`QWDidu8ztrcuiBNL5Sa4Vy`, not exported).

Icons are Phosphor Regular (`@phosphor-icons/core` 2.1.1, MIT licence, Copyright (c) 2023 Phosphor
Icons; the licence text is in [`shared/PHOSPHOR-LICENSE`](shared/PHOSPHOR-LICENSE), copied from the 2.1.1 package), written as `<i class="ph ph-<name>">`. Their 93 glyphs are inline SVG masks inside
`shared/aia-core.css`, so no icon font or CDN is involved. Fonts load from Google Fonts in the boards
themselves (IBM Plex Sans, IBM Plex Mono, Source Serif 4).
