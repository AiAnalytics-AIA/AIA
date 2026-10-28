# Settings prototype, 27 Oct 2026

A snapshot of the Design canvas "AIA Nastavení – prototyp"
(<https://claude.ai/artifact/8W9LR8Ju9BWnR5JACmiWv7>, private to the owner's account), exported on
27 Oct 2026 at about 11:15 UTC. It replaces the 26 Oct snapshot, `prototypes/settings-v99/` (v99), which is in git history. Design reference only, no product code; every client, person and number is fictional.

- **Owner:** the second account's canvas, <https://claude.ai/artifact/8bHnTkAJNiPNgGcYTzQqLS>, since 28 Oct
  2026 (the owner: "This account now owns the Settings prototype"). It was rebuilt from these files on 27 Oct
  (artifact version `1793114802-6ae6`): every file byte-identical, and every board's render matching
  `reference/`. Change the design there, and export it here. Don't edit the first account's canvas any more.

- **Version:** v117, artifact version `1793098752-b063`, on core v4.3. It includes the owner's own canvas
  edit renaming the hatch start button to "Vypěstovat" and the design-system session's v4.3 pass (the owner,
  27 Oct 11:10 UTC: "i need these to be included").
- **How to read it:** as in [`../README.md`](../README.md) § How to read a `.dc.html` file. Each
  `.dc.html` is one canvas artboard that loads `./support.js`, the canvas runtime, which is not exported.
  `canvas.json` gives each board's size, position and order.
- **Assets:** the canvas's uploaded files are under `assets/`, and the pages reference them relatively:

| File | What | Canvas asset |
|---|---|---|
| `assets/aia-core.css` | Core v4.3, the shared stylesheet: the Petrol palette, the shell (Dock rail, top bar with ⌘K palette and activity tray), the components and the Phosphor icons. Written by the design-system session from Settings' core v3 | `be52e47160b1f8335f5ed91f934ae252` |
| `assets/aia-settings.css` | Settings-only: Metodika steps and maps, KPI tiles, the compact hero. Loaded second on the nine Settings boards | `88037ffee3c58d5ab72ffad1caf4bfc2` |
| `assets/thinking-orb.js` | thinking-orbs 0.3.2 (MIT, Jakub Antalik) as a `<thinking-orb>` element; licence in its header | `6659cc2592302e4ff9bbdaaa4c953b68` |
| `assets/889c3d28bc209704c3ef7887107cb48d.webp` | The Metodika Sociomapa card's placeholder image | `889c3d28bc209704c3ef7887107cb48d` |
| `assets/PHOSPHOR-LICENSE` | MIT licence of the Phosphor icons inlined in core | (copy of `../shared/PHOSPHOR-LICENSE`) |

Links to `https://claude.ai/artifact/…` point at the live sibling canvases (research stages, Klienti).

## Boards

| Board | File | Size |
|---|---|---|
| Metodika | `Main.dc.html` | 1440 × 1060 |
| Systémové prompty | `Prompts.dc.html` | 1440 × 1090 |
| Deep Research | `DeepResearch.dc.html` | 1440 × 1450 |
| AI běh | `AI.dc.html` | 1440 × 1310 |
| Přístup a schvalování | `Access.dc.html` | 1440 × 1200 |
| Studie a rozpočty | `Studies.dc.html` | 1440 × 1110 |
| Audit | `Audit.dc.html` | 1440 × 930 |
| Stav systému | `System.dc.html` | 1440 × 1560 |
| Správa dat | `Data.dc.html` | 1440 × 930 |
| Vypěstovat Vedoucího | `Hatch.dc.html` | 1440 × 1050 |
| Můj Vedoucí | `LeadSettings.dc.html` | 1440 × 2110 |

## What changed since v99

- **The Petrol design system,** written by the design-system session (session_01WhkCbrxP4R2kgtfDvr4VRt)
  on the owner's word of 27 Oct ("Not just color, the whole design system and UX of all the open
  prototypes"):
  - core v4.3 in place of core v3;
  - a petrol accent, AI drawn graphite with a blue "spark" edge, orange for "čeká na vás";
  - a rail that follows the theme;
  - the global ⌘K palette and the activity tray in the top bar;
  - the rail's hover and current item drawn in the rail's own ink (core v4.3), so text no longer turns white
    on the light rail;
  - Projektová paměť removed from the rail and the ⌘K palette.
  
  Its rules are in Design System v3.1 (<https://claude.ai/artifact/SEEkz1TrFgEZ1yK53Qmas4>).
- **Compact heroes** (the owner, 27 Oct: "all the heros in each page have no visual hierrchy and take
  up so much space"):
  - one band: title (serif 30) and a short lede on the left, the figures on the right as one stat strip
    (value over label);
  - the figure that needs you in its own tinted cell;
  - 189 px → 129 px;
  - in `aia-settings.css`, with core left untouched.
- **The hatch test tube's liquid is green slime** (the owner, 27 Oct).

## Decided (the owner's words, 20–27 Oct 2026)

- **Look:**
  - no emoji, Phosphor icons only;
  - no menu as a row of pill buttons;
  - the AppShell rail as a Dock (64 px icons, opening to 240 on hover or focus);
  - Nastavení opens a flyout of nine sections;
  - Můj Vedoucí is its own rail item;
  - 1440 px only for now ("no narrower screens right now").
- **Systémové prompty:**
  - the Metodik mark edits and switches on prompts ("metodik edits the prompts"); owners and admins
    without it read;
  - versions are compared as a +/− line diff ("like code").
- **Přístup:** a departing member's Lead is sealed, never handed over, and erased after 365 days ("lets
  seal it, a new user gets a new vedouci"; "365", 27 Oct).
- **Správa dat:** AI spend and audit are kept 365 days ("lets do 365 days"); deleting a client asks for
  its name to be typed.
- **Stav systému:**
  - Reference is merged into it;
  - Fronta práce is post-MVP ("lets table this idea as a plan in the future"), drawn as a dashed "Plán po
    MVP" card;
  - GlitchTip is linked from Hlášení chyb.
- **Vedoucí:**
  - it grows from a test tube in four questions;
  - SOUL and USER are shown in full to accept ("Přijmout") or redo ("Zadat znovu") before anything is
    kept;
  - Můj Vedoucí shows its files read only, with the chat preview behind a button.

## Still open

- **The flyout's Můj Vedoucí card** (no Lead yet) still draws the test tube in the old colour. It is
  drawn by core.
- **The Metodika Sociomapa card** keeps a placeholder image until aia-sociomap-5 renders live ("lets
  wait until we have sociomap 5 live").
- **The 365-day erasure is decided but not built:** the sealed Lead's horizon (30 → 365 days, an ADR
  0030 amendment) and the erase job for AI spend and audit (settings-redesign F22's finding). The
  coordinator queued both on 27 Oct.
- **Partly covered by plan chunks**, from the inventory sent to the coordinator on 27 Oct:
  - the prompts' Text / Změny switch and its +/− count;
  - the coral "waiting to switch on" count going to the Metodik, not all admins;
  - Audit categories as a dropdown;
  - the Můj Vedoucí chat preview's three states;
  - the flyout's Můj Vedoucí card;
  - the collapsed rail's dot and ring;
  - the hero on the hatch page.
- **The compact hero lives in `aia-settings.css`;** core v4.3 still carries the old 189 px hero, so
  other canvases (Klienti) keep it until the design-system session folds this in.
