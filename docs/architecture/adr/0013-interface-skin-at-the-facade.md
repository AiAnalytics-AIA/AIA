# ADR 0013 — Restyle the 18.6.6 interface with an AIA skin applied at the facade

**Status:** Accepted — develop only (data owner's direction, 2026-09-23; seen
working on develop by the data owner, 2026-09-24; see
*Decision record* below). Builds on [ADR 0012](0012-legacy-interface-as-product-facade.md);
leaves [ADR 0011](0011-vendor-legacy-product-unit.md) intact.
**Date:** 2026-09-23

## Context

ADR 0012 made the 18.6.6 interface the product surface: the develop site serves
`legacy/npc-panel-18.6.6/app/ui_app.html` at `/`, behind AIA sign-in, and each
feature is rebuilt behind the same screens. The screens carry every feature,
button and label the product needs. What they do not carry is the design the
product is meant to have: the AIA design system (tokens, IBM Plex and
Source Serif 4, the status and evidence semantics, the identity) was designed
against the brief in [`docs/design/aia-design-system-brief.md`](../../design/aia-design-system-brief.md)
and ported as far as `feature/web-primitives`, but its screen compositions
targeted AIA's own Next.js pages, which ADR 0012 replaced.

The data owner decided on 2026-09-23 that the develop deployment is the
canonical baseline for every screen, that the screens need a major design
upgrade in the direction they were already going, and that the existing design
system is the base for it. Two recorded decisions constrain how:

- ADR 0011 — the unit is regenerated, never edited. `ui_app.html` is
  byte-identical to the archive and its SHA256 is pinned in
  `legacy/npc-panel-18.6.6/app-manifest.json`.
- ADR 0012 — copying `ui_app.html` into the web client is rejected until screens
  are re-homed area by area, because the file names real clients' demos (D-L1).

The interface allows a restyle without either. It is one document served only
at `/` (`ui_server.py` `do_GET`, `path=="/"`), styled by inline `<style>` blocks
built on custom properties (`--bg`, `--card`, `--ink`, `--brand`, `--ok`,
`--warn`, `--bad`, `--r`, `--font-sans`, … — 659 `var()` uses), and its later
blocks already move it toward a flat, single-accent look (teal `#2180A5`, Inter,
4 px radii, no shadows). A stylesheet loaded after those blocks can re-point
every variable and restyle every shared component, without touching markup,
text or behaviour.

## Decision

1. **The product hostname serves the 18.6.6 document with one AIA stylesheet
   added.** Caddy sends `GET /` — and only `/` — through the existing
   `forward_auth` gate to the web client, by an internal rewrite to
   `/interface-document`. The web client fetches the document from
   `legacy-panel:8765/` on the internal network and inserts two tags: a
   `<link rel="preload" as="style">` for the skin before `</head>`, so it is
   fetched as early as the page's own styles, and the
   `<link rel="stylesheet">` itself immediately before the last `</body>`.
   The stylesheet goes last because the interface's own styles do not all live
   in `<head>`: three `<style>` blocks sit inside `<body>` and nine more are
   appended to `<head>` at runtime (`document.head.appendChild`), so a
   stylesheet placed in `<head>` would lose the cascade to every one of them at
   equal specificity. Nothing else in the document changes. Every other unit
   path is routed exactly as ADR 0012 records.
2. **The skin applies only to the document it was written for.** The injector
   computes the SHA256 of the fetched document and inserts the link only when it
   equals the pinned hash of the vendored `ui_app.html`. Any other document is
   passed through unchanged, with `X-AIA-Skin: bypassed` and a structured warning
   in the log. A regenerated unit therefore shows the original design, never a
   skin written against different markup. A test keeps the pin equal to the
   manifest's hash, so the pin going stale is a failing test, not a silent
   bypass.
3. **Behind a kill switch, off by default.** `AIA_INTERFACE_SKIN_ENABLED`
   (web client) defaults to off; off means the injector passes the document
   through unchanged. The develop environment turns it on. Production is not
   decided here.
4. **The parity oracle is never skinned.** The legacy hostname (basic auth)
   keeps proxying straight to the unit, so parity and browser-comparison tests
   see the exact 18.6.6 document.
5. **The skin is generated from the design system's one token source.**
   `apps/web/src/design/tokens.json` is the only place a colour, font, radius or
   spacing value is decided. The generator emits the skin's variable layer from
   it; hand-written skin rules may reference tokens but not introduce raw
   values. Fonts are self-hosted with their OFL licences. The skin is served as
   static files under `/skin/`, public like `/_next/*`: it contains no data.
6. **The direct path is not an entry point.** A request for
   `/interface-document` from outside is answered 404 by Caddy; the document is
   reachable only through the gated rewrite of `/`.

## Consequences

- Every 18.6.6 screen moves to the design system in the same release, with no
  change to markup, labels, flows or the unit's bytes.
- A skin cannot change structure. Reordering, regrouping, new components and
  renamed labels wait for the area's re-homing (legacy strangler, slice 16+),
  which reuses the same tokens — nothing written for the skin is thrown away.
- `/` now depends on the web container as well as the unit. Sign-in already
  depends on it (`/login`), so no new single point of failure is introduced for
  a working session.
- One extra internal hop for the document only (≈ 0.9 MB, one fetch per
  navigation, `no-store` as the unit sends it). Assets and API calls are
  unaffected. Measured before production.
- The skin overrides inline `style=` attributes (356 in the document) only where
  a shared component needs it, with `!important` scoped to that component. Each
  such override is listed in the plan, because it is the part most likely to
  surprise a reader.
- Status colours in 18.6.6 (`--ok`, `--warn`, `--bad`) are re-pointed to the
  design system's status tokens. The skin does **not** reinterpret what 18.6.6
  says a state is; it changes how a state the interface already names looks.

## Alternatives considered

- **Re-home the screens into `apps/web` now.** The end state, with full design
  freedom, but months of work across 737 functions, and it reverses ADR 0012's
  order and needs D-L1. Rejected for now; it remains the plan's slice 16+.
- **A Caddy response-body rewrite.** Needs a third-party Caddy module and a
  custom Caddy image, and puts presentation logic in the edge configuration.
  The web client is where presentation already lives.
- **Serve the injector from the API.** The API validates, delegates and
  serialises (`CLAUDE.md` §2); a transformed HTML document is presentation.
- **Edit `ui_app.html` or add a `<link>` to it.** Violates ADR 0011.
- **A browser extension or user stylesheet.** Not deployable, not reviewable.

## Revisit when

- An area is re-homed: its skin rules are deleted as its screens move.
- The unit is regenerated: the pin fails, the skin bypasses, and the skin is
  re-verified against the new document before the pin is moved.
- Production is planned.

## Decision record

Asked and answered on 2026-09-23 in the session that wrote this ADR: *skin now,
re-home later*; *implement the existing design system*; *verify against the
live oracle*. Status stays **Proposed** until the first skinned deploy is seen
working on develop.

Accepted on 2026-09-24: the data owner saw the skin on develop (deploy run 15,
`230ee7e`) — "the skin was applied, and all seems to look fine". The same day
they asked for full UI control; [ADR 0014](0014-rebuild-the-interface-in-react.md)
rebuilds the screens in React, and this skin covers the classic screens until
each area moves.
