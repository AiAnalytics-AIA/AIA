# Legacy route and UI function ledgers

The strangling of the NPC Panel 18.6.6 unit behind the running oracle
([ADR 0011](../architecture/adr/0011-vendor-legacy-product-unit.md), plan
[`.planning/plans/legacy-strangler.md`](../../.planning/plans/legacy-strangler.md))
is tracked in two machine-readable ledgers. Both are hand-maintained; tests keep
them honest.

| Ledger | Rows | Source of truth for the rows | Kept honest by |
| --- | --- | --- | --- |
| [`legacy-route-ledger.json`](legacy-route-ledger.json) | 153 unique verb + path routes (162 dispatch arms) | `AIA-reference/api-ledger.json` and `capability-map.json` @ `678e298`, pinned by SHA256 | `packages/aia_core/tests/test_legacy_route_ledger.py`, `apps/api/tests/test_legacy_route_claims.py` |
| [`legacy-ui-functions.json`](legacy-ui-functions.json) | the 88 `METHODOLOGY_SEMANTICS` / `DETERMINISTIC_COMPUTATION` functions of `ui_app.html` | `AIA-reference/ui-capability-ledger.json` @ `678e298`, pinned by SHA256; each row carries the SHA256 of the function's source in the vendored unit | `tools/ui_functions.py check`, `packages/aia_core/tests/test_legacy_ui_functions.py` |

## Route statuses

| Status | Meaning | Moves when |
| --- | --- | --- |
| `LEGACY` | Served by the oracle only; no AIA route | An AIA route lands that serves the capability → `PORTING` |
| `PORTING` | An AIA route serves the capability; parity against the oracle is not yet `PASS` | The capability's oracle gate reports `PASS` from an executed run → `PORTED` |
| `PORTED` | Parity `PASS`; the legacy path for this route is retired (the oracle is no longer the only server of it) | Never backwards without a recorded decision |
| `RETIRED` | No production equivalent, by the decision named in `decision` | — |

Rules:

- **A row's `aia_route` exists.** The API test proves every `PORTING` / `PORTED`
  row's route is in the OpenAPI document. A ledger claim with nothing behind it
  is the failure this prevents.
- **Scope is decided, never inferred** (reference R14, open decision D8). A
  `LEGACY` row's scope is `undecided (D8)`; a ported row's scope is one of
  `public`, `organization`, `study`, and a `study` route carries the study id in
  its path (ARCHITECTURE.md §2).
- **Retirement needs a decision id.** The second HTTP server's four routes
  (`prototype_server.py`) are reference decision D9 and stay `LEGACY` until it
  is taken.
- **The reference's capability assignment is family-level.** `capability-map.json`
  lists every route under every capability of its family, so the ledger records
  the family and the full list as `reference_capabilities`, and the reference's
  own `api.*` id as `api_ledger_capability`. The precise capability a route
  proves parity for is recorded in `docs/migration/parity-matrix.json` when its
  oracle gate is declared, not guessed here.
- **`slice`** is the row's slice in the strangler plan. The plan is the order;
  the ledger is the state.
- **Suffix arms.** The reference's AST scan recovered the `endswith` halves of
  prefix dispatches (`POST /api/workflows/<id>/pause` appears as both
  `POST /api/workflows/` and `POST /pause`). Both rows are kept so coverage is
  exactly the reference's 162 arms; the suffix rows say so in `notes`.

## UI function statuses

| Status | Meaning |
| --- | --- |
| `LEGACY` | Runs only in the oracle's browser |
| `PORTING` | An `aia_core.domain` implementation exists (`implementation`); parity is not yet `PASS` for the whole function |
| `PORTED` | Parity `PASS` from executed gates against fixtures captured from the function's own JavaScript (`fixtures`) |

Every row carries `source_sha256`, the SHA256 of the function's source as
extracted by `tools/ui_functions.py` from the vendored `ui_app.html`. A fixture
captured from that source records the same hash; when the unit is regenerated
and a function changes, `tools/ui_functions.py check` fails and names it, so a
stale fixture is *known* rather than quietly wrong.

## Regenerating

The rows come from the reference; the statuses are ours. To regenerate after a
reference re-pin, rebuild the rows from the new `api-ledger.json` /
`ui-capability-ledger.json`, carry the statuses, decisions, `aia_route` and
notes across by verb + path (or function name), update the pinned SHA256s in
the same commit, and say in the commit body which rows moved and why.
