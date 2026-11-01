# AIA UX Upgrade, before and after: export of 27 Oct 2026

The "AIA UX Upgrade" page, exported so another account can read it without the live artifact. It is a record,
not product code. Every client, study and number in its screenshots is fictional (the UI workbench's fixtures).

| | |
|---|---|
| Live artifact (private to the owner's account) | <https://claude.ai/artifact/6duL5pNSVfiqqBz6V16Tfo> |
| Exported version | artifact version id `1793072278-450e`, 27 Oct 2026 |
| Before | `develop` @ dbaa7720 |
| After | `feature/ux-upgrade` (draft PR #1022) as it stood then |
| Design System | [`../design-system/`](../design-system/) |

## How to open it

Open [`index.html`](index.html) in a browser. Its one script only filters the screenshots by theme. The fonts come
from Google Fonts; offline, the system fonts stand in.

The artifact keeps its 24 screenshots inline as base64 JPEGs. Here each one is its own file in `images/`, byte for
byte, and `index.html` names it by path; nothing else in the page changed. The reason: a 4-character run in one
image's base64 matched a client token in `tools/exposure_check.sh`. That match was chance, not content, but the check
rightly allows no file exceptions.

## What it shows

- **Audits, before → after:**
  - taste lint FAILs 38 → 26;
  - impeccable's rendered findings 57 → 35;
  - cards inside cards 27 → 15;
  - contrast failures 4 → 0.
- **What changed:** palette, contrast, keyboard (Ctrl/⌘ K), money (SpendDialog), errors, saving, undo, dead ends,
  chrome, icons and density. The page also lists what is only designed so far: Přehled studie, the activity tray,
  peek, filter tokens and bulk undo.
- **12 screens at 1280 × 900, before and after:**
  - in the light theme: Klienti, Přehled klienta, Znalosti, Zadání, Cílová skupina, Dotazník, Spuštění, Můj Vedoucí and
    Nastavení · Metodika;
  - in the dark theme: Klienti, Přehled klienta and Zadání.

## Out of date

The page was made before two later decisions, and it was exported unchanged:
- **AI colour:** its change table still says "iris only for AI". Since then AI has no colour of its own and is marked by
  the spark edge; the owner disliked the lilac. See the Design System README, § Decided.
- **Redundancy pass:** its "after" screenshots predate the redundancy pass on #1022 (e783f692, 5325fa97, 50107977).
