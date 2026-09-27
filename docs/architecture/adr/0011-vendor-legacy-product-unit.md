# ADR 0011 — Vendor the NPC Panel 18.6.6 product as a frozen unit, and run it as the baseline

**Status:** Accepted for the `develop` environment. The unit is a baseline and an
oracle, not a product surface; nothing in it is edited, and nothing in AIA
imports it.
**Amended by [ADR 0018](0018-aia-runs-without-18-6-6.md)** (2026-09-27, decision 5): the
unit is no longer a service of the develop deployment. It stays frozen here and runs, when a
comparison needs it, from `deploy/reference/` beside the product, behind a basic-auth gate on
the host's loopback; the oracle hostname is not served. Everything else stands.
**Date:** 2026-09-23

## Context

AIA is rebuilding NPC Panel 18.6.6 from a reference specification
(`AiAnalytics-AIA/AIA-reference`: contracts, ledgers, 11 golden fixtures) rather
than from the product itself. That was deliberate: the archive is licence-bound
(the population derives from PIAAC 2023 CZ and ISSP 2022 CZ microdata) and carries
real-subject client material, so this repository was kept clean of it and the
guards (`tools/exposure_check.sh`, `.gitignore`) enforce that.

Two things changed the picture. First, the deployed rebuild does not look like
the product: 19 of 136 HTTP paths are ported and the frontend is still
mock-backed, so nobody can point at the running system and say what 18.6.6 does.
Second, the reference repository now runs the audited snapshot unmodified as a
hash-verified container (its `container/`), which proved that the product's *code*
is under 5 MB of Python, one HTML file and configuration, and that its licence and
client-material problems live entirely in the *data* and the *demo library*, which
are separable.

The data owner decided to change strategy: take the working 18.6.6 product as is,
make it the day-one baseline, and restructure it behind a running oracle rather
than rebuild it from prose.

## Decision

1. **The product is vendored as one frozen unit at `legacy/npc-panel-18.6.6/`**,
   produced only by `AIA-reference/tools/extract_legacy.py` from the archive whose
   SHA256 is `86b70bfb5c1b4a7984b392cc6187c0842edc5cd28d37d2dd72dcf15d58d53216`.
   Every file under `app/` is byte-identical to the archive and listed with its
   hash in `app-manifest.json`. The unit is regenerated, never edited. A change to
   what it contains is a change to the extraction policy in the reference
   repository, reviewed there.

2. **The partition is by policy, not by hand.** Of the archive's 1,565 files:
   924 are code and configuration (Git, baked into the image); 245 are runtime
   data (`data-manifest.json`: population panels, CSV assets, demo payloads,
   shipped SQLite state) kept in the EU ops bucket, synced to the host by
   `bin/deploy.sh` and hydrated into the working tree at start with hash
   verification; 69 are real-subject client material and are excluded; 327 are
   release debris and stay in the archive.

3. **It runs as the `legacy-panel` service on the develop host**, on its own
   hostname behind HTTP basic authentication in Caddy. Its own hostname because
   the reference UI calls absolute `/api/*` paths that collide with AIA's; a gate
   because the reference has no identity model (reference R14).

4. **It is outside every code-quality gate by construction** (`ruff`, `mypy`,
   `layer_check`, `pytest` scan `packages/`, `apps/`, `migrations/`) and outside
   the API and worker build contexts (`.dockerignore`). `exposure_check.sh` skips
   it by path for the rules it would trivially fail (reference bytes, reference
   names, dataset nouns, the invented demo brands) and keeps enforcing real-client
   tokens in file names inside it.

5. **Decision D-L1 (data owner): real-client identifiers inside code files are
   accepted in this private repository.** The reference code names its own
   canonical demos by identifier in a handful of files (`demo_showcase.py`, a
   browser smoke test, a shipped checksum list); the unit's
   `exposure-report.json` lists each with a hit count. They are identifiers, not
   briefs or findings. The alternative, dropping those files from the extraction,
   removes working code from the baseline. If a listed file turns out to quote
   client text, the fix is a policy exclusion in the reference repository, and
   this decision is revisited.

## Consequences

- The reference posture changes: **the snapshot's observable behaviour and UI are
  canonical; its architecture is not.** `docs/migration/reference-source.md` and
  `legacy-system-map.md` are updated accordingly. Parity is now measurable
  against a running system, not only against fixtures.
- The restructuring plan follows the reference's UI ledger: the 88 frontend
  functions carrying methodology or computation move server-side first, the
  remaining routes are ported, `ui_app.html` is split along capability families,
  each step checked against the unit over HTTP.
- The unit is single-tenant and unauthenticated by design. It never becomes a
  user-facing surface; the gate in front of it is part of the decision.
- Live AI runs on the unit need a provider credential and are a separate,
  recorded decision. The baseline runs everything deterministic without one.
- The deploy builds a fourth image, `aia-legacy-panel`, and `compose up --wait`
  now includes it: a unit that fails hydration or verification fails the deploy.

## Alternatives considered

- **Keep rebuilding from the specification alone.** Rejected: after five phases
  the deployed system still does not resemble the product, and the risk of
  reconstructing behaviour from prose was the problem this repository was
  created to avoid.
- **A separate repository for the unit.** Rejected: the deploy pipeline, the
  parity suites and the restructuring work all live here; a second repository
  would re-create the hand-off this ADR removes.
- **Vendor the whole archive.** Rejected on licence and exposure grounds; the
  extraction exists precisely to separate what may enter Git from what may not.

## Revisit when

- The licence decision on the population (reference D3) resolves either way.
- The unit is no longer the best oracle because production reproduces the full
  route and UI surface; then the unit is retired, not edited.
