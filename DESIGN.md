---
name: AIA
description: A Czech research studio with an AI Research Lead beside every step. Captured as shipped on develop dbaa7720 (27 Oct 2026), before the UX upgrade.
colors:
  surface: "#eef0f4"
  surface-raised: "#ffffff"
  surface-sunken: "#e5e8ee"
  border: "#dde1e8"
  border-strong: "#7d8490"
  ink: "#151a20"
  ink-muted: "#43484f"
  ink-faint: "#5c6167"
  signal: "#4b48ce"
  signal-hover: "#3f3cad"
  signal-wash: "#ededfa"
  signal-tint: "#f6f6fd"
  on-signal: "#ffffff"
  ai: "#9b8bfb"
  ai-ink: "#5c28a0"
  ai-wash: "#f1f0fd"
  status-you: "#ff8270"
  status-you-ink: "#971c11"
  status-you-wash: "#fbe7e6"
  status-world: "#576574"
  status-fault: "#c92516"
  status-fault-wash: "#f7e3e3"
  in-force: "#1d9a6c"
  shell: "#11151b"
  shell-ink: "#e8e6e1"
typography:
  hero:
    fontFamily: "Source Serif 4, Georgia, serif"
    fontSize: "40px"
    fontWeight: 600
    lineHeight: "46px"
  title:
    fontFamily: "IBM Plex Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "20px"
    fontWeight: 600
    lineHeight: "26px"
  heading:
    fontFamily: "IBM Plex Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    lineHeight: "20px"
  body:
    fontFamily: "IBM Plex Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "20px"
  label:
    fontFamily: "IBM Plex Sans, Segoe UI, system-ui, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: "16px"
  mono:
    fontFamily: "IBM Plex Mono, ui-monospace, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: "16px"
rounded:
  control: "6px"
  card: "8px"
  panel: "10px"
  composer: "12px"
spacing:
  "1": "4px"
  "2": "8px"
  "3": "12px"
  "4": "16px"
  "6": "24px"
  "8": "32px"
  "12": "48px"
components:
  button-primary:
    backgroundColor: "{colors.signal}"
    textColor: "{colors.on-signal}"
    rounded: "{rounded.control}"
    height: "36px"
  button-secondary:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "36px"
  input:
    backgroundColor: "{colors.surface-raised}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "36px"
  card:
    backgroundColor: "{colors.surface-raised}"
    rounded: "{rounded.card}"
    padding: "20px"
---

# Design System: AIA (before the UX upgrade)

This file records the system **as it ships on `develop` at `dbaa7720`**, so the upgrade has a
"before". The target is the look approved on 26 Oct 2026 (`prototypes/LOOK.md`, core v3) and the
AIA Design System v2 artifact; `docs/aia-ux-research.md` holds the gap analysis.

## Overview

**Creative North Star: "The Research Ledger"** *(proposed; not yet confirmed by the product owner)*

AIA is a dense, professional research studio in Czech. Flat, bordered surfaces in cool greys carry
the work; one indigo signal marks selection, links and the primary action; coral is reserved for
what needs this person; slate for waiting on the world; green only for the version in force. A
graphite rail holds the navigation, and an AI Research Lead sits in a pane beside each study's
artifact.

As shipped, the system is two systems: the newer one (the Dock rail, the hero, Phosphor icons, the
input standard in `components/ui/`) follows the look contract; the older one (`components/live/`,
`workbench.css`'s leftovers, hand-rolled boxes and pills across the screens) predates it.

**Key Characteristics:**
- One token source (`apps/web/src/design/tokens.json`), light and dark.
- Flat; one overlay shadow.
- Indigo signal, coral needs-you, slate waiting, fault red, green only in force.
- IBM Plex Sans / Mono; Source Serif 4 on top-level heroes.
- Many hand-rolled elements: 171 buttons, 244 note boxes, 36 tables, 9 pill-row menus.

## Colors

Cool neutral greys with one indigo accent and reserved status hues.

### Primary
- **Indigo Signal** (#4b48ce, dark #828bea): primary action, selection, links, focus, a running process.

### Secondary
- **Lead Violet** (#9b8bfb, ink #5c28a0): the Lead's mark, the thinking orb, paid AI starts only.

### Neutral
- **Cool Ground** (#eef0f4), **Raised White** (#ffffff), **Sunken Grey** (#e5e8ee): page, cards, wells.
- **Graphite Ink** (#151a20), **Muted** (#43484f), **Faint** (#5c6167): text levels.
- **Hairline** (#dde1e8) and **Control Edge** (#7d8490).
- **Graphite Shell** (#11151b): the rail.

### Named Rules
**The Reserved Status Rule.** Coral only for what this person must do; slate for waiting on others;
green only for "in force"; no amber. *(As shipped, amber survives on `/studies` and the Sociomapa
warning; budget waits read coral for everyone.)*

## Typography

**Body Font:** IBM Plex Sans (Segoe UI, system-ui) · **Mono:** IBM Plex Mono · **Display:** Source Serif 4.

### Hierarchy
- **Hero** (600, 40/46, serif): top-level pages only. Hard-coded in `Hero.tsx`, not a token.
- **Title** (600, 20/26): a stage title. As shipped it renders 16/20 in the workbench and 22/28 in the classic layout.
- **Heading** (600, 15/20): sections.
- **Body** (400, 14/20); tables 13/18.
- **Label** (500, 12/16) and caption (400, 12/16). 223 arbitrary `text-[Npx]` values bypass the scale.

## Layout

Graphite rail 64 px (240 px open), breadcrumb top bar, a 420 px Lead pane beside the artifact at
≥ 1100 px, a drawer from 768 px, a sheet below. Spacing tokens exist (4-48) but are not exposed to
Tailwind, so screens use Tailwind's default scale (446 off-grid spacings).

## Elevation & Depth

Flat and bordered. One shadow, `shadow-overlay`, for dialogs and menus. As shipped, 56 other shadow
uses remain (lint `shadow`), and the Sociomapa panels use backdrop blur.

## Shapes

Radius 6 for controls, 8 for cards, 10 for dialogs and menus, 12 for the Lead's composer. As
shipped, 69 `rounded-full` and 49 `rounded-pill` uses keep pill shapes in chips and menus; the
workbench's status pill has radius 2.

## Components

- **Button** (`rehome/ui.tsx`): 36 px, 14 px text, primary/secondary/quiet; no danger variant.
- **AiButton**: AI fill with a glow ring, weight 600.
- **Inputs** (`rehome/ui.tsx`, `components/ui/`): 36 px; Select is a native `<select>`.
- **Chips**: ten forms, radii 2 to 999.
- **Status**: at least eight drawings (squares, a diamond, icons as status).
- **Dialogs**: AskDialog text confirmations; `SpendDialog` exists but no screen uses it.
- **Tables**: no shared table; 36 hand-made.

## Do's and Don'ts

- Do take every colour from `tokens.json`; don't write hex in components.
- Do keep money in the Czech locale with its four names; don't show an unknown amount as 0.
- Don't use emoji (41 unicode marks and one emoji ship today).
- Don't build an option menu as a row of pills (9 ship today).
