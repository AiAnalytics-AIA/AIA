# ADR 0001 — Keep the validated Python domain engine; FastAPI for the API

**Status:** Accepted. Implemented.
**Date:** 2026-09-21

## Context

Two codebases existed at the start of the migration. The AIA repository had a
44-line Fastify stub (`src/server.js`: a login route and a health check, no domain
logic, with `better-sqlite3`, `exceljs`, `papaparse` and `zod` declared but never
imported). The NPC Panel prototype had 44,395 lines of Python behind 394 passing
hermetic tests, containing the research methodology, the population model, the
simulation engine and the validation gates.

## Decision

Preserve the Python domain engine. Build the API with FastAPI and Pydantic.
Remove the Fastify stub once authentication is complete.

## Why not a rewrite

Those 394 tests are the only evidence that the methodology works. A rewrite in
TypeScript would discard that evidence and re-derive numerical behaviour —
donor fusion, weighting contracts, unfolding mathematics, significance testing —
from prose documentation. The parity suite exists precisely because "it looks
right" is not acceptance for research output.

The relevant asymmetry: the repository's "existing backend convention" was a stub
with nothing to preserve, while the prototype's Python carried everything of value.
So the brief's default (FastAPI) won on the merits rather than by fiat.

## Frontend

Next.js is kept, because `apps/web` already established it along with the
`/org/[orgSlug]/…` routing shape that anticipates tenancy. That was a genuine
existing convention worth following.

## Consequences

- Two languages in the repository. Accepted: the boundary is an OpenAPI contract.
- Python 3.12+ required; the prototype targeted 3.11+.
- `src/server.js` is retained until the auth seam is filled, because it holds the
  only working login path. Removing it earlier would leave no authentication at
  all.
