---
status: done
chunks:
  - "[x] 1. One redaction in aia_core (closes OI-23) and the error reporter: scrubbed events, off without a DSN"
  - "[x] 2. The API reports what a person hit: unhandled exceptions and 5xx, tagged with the request id"
  - "[x] 3. The worker reports what broke a run: a step ending FAILED, an unclassified exception, a lost outcome"
  - "[x] 4. The browser reports what broke a page: uncaught errors and render crashes, DSN from /config"
  - "[x] 5. GlitchTip on the develop host: a Compose project of its own, its own database, errors.<hostname>"
---
# Error tracking: every important failure as one grouped, scrubbed issue

**Drafted:** 2026-10-15 · **Base:** `develop` @ `f6f88cb9` · **Owner:** the product owner: "can we
implement a log system like sentry, something we can monitor the software and identify where exactly
the issue is" … "self host on aws, i want it to be structured in the most relevant way in order to
catch important glitches and bugs".

## What exists, and what is missing

The logs are good and stay the record: one JSON line per event with `request_id` (API) or
`worker_id`/`run_id`/`step_id`/`attempt_id` (worker), shipped to CloudWatch `/aia/develop`
(`deploy/develop/README.md` § Logs). Missing: grouping (the hundredth time is one issue, not a hundred
lines), a stack trace you can click, a "first seen in build X" per issue, an alert, and anything from the
browser at all.

## Decisions

1. **GlitchTip, self-hosted on the develop host** (owner, 2026-10-15). It speaks Sentry's protocol, so
   AIA uses the Sentry SDKs (`sentry-sdk` in Python, `@sentry/browser` in the web); moving to Sentry or
   to GlitchTip's hosted plan later is a DSN change, not a code change. Data stays in our AWS account
   in the EU.
2. **Off without a DSN.** `AIA_ERROR_TRACKING_DSN` unset (every test, every local run) installs
   nothing: no SDK client, no transport, no thread. The DSN is the kill switch.
3. **Important, not everything.** An issue is something a person should act on:
   - API: an unhandled exception (the 500 a person saw) and a 5xx a handler raised. Never a 4xx: a
     refusal is AIA working.
   - Worker: a step whose attempt left it `FAILED` (the run is broken for its owner), any unclassified
     exception (a bug even when the retry succeeds), an outcome that could not be recorded, and a loop
     or sweep that raised. Never a park, a gate, a budget stop, a quota wait or a cancellation: each is
     a state the interface already explains.
   - Browser: an uncaught error, an unhandled rejection, and a React render crash (the error boundary).
4. **Grouped by cause.** A step failure's fingerprint is `step-failed / <kind> / <failure class> /
   <error code or type>`, so "executive analysis is incomplete" is one issue however many runs hit it,
   and a different step or cause is another.
5. **Where exactly.** Every event carries `environment` (`AIA_ENV`), `release` (`AIA_BUILD_SHA`) and
   `service` (api, worker, web); the API's `request_id` and the worker's `run_id`, `step_id`,
   `attempt_id`, `step_kind` and `failure_class` as tags, so an issue opens the matching CloudWatch lines
   with one Logs Insights filter.
6. **Scrubbed before it leaves.** One `before_send` and one `before_breadcrumb` apply AIA's redaction
   (by key and by value shape) to the whole event; request bodies, cookies and headers other than
   `user-agent` and `x-request-id` are dropped; local variables are never collected (they hold
   respondent answers and prompts); `send_default_pii` is off. No performance tracing.
7. **One redaction.** The patterns move into `aia_core.infrastructure.redaction`; the API and the worker
   import them, and so does the reporter (closes OI-23).
8. **The SDK stays behind one module.** `sentry_sdk` is imported only in
   `aia_core/infrastructure/error_tracking.py` (layer_check), lazily, from the optional `errors` extra.

## Chunks

1. `aia_core.infrastructure.redaction` (the API's `redact` + the worker's `redact_text`, one pattern
   set); `aia_core.infrastructure.error_tracking`: `ErrorTrackingSettings.from_env`, `init`,
   `scrub_event`, `report_step_failure`, `report_exception`; the `errors` extra; a layer rule. Tests:
   settings, a real SDK client over a capturing transport proves a key, a bearer token, a cookie, a body
   and a local never leave.
2. API: init in `create_app`; `_unhandled` reports with `request_id`. Tests: a raising route produces
   one event with the request id and no secret; a 404/409 produces none.
3. Worker: init in `main`; `_record` reports a terminal `FAILED`, `_run_executor` an unclassified
   exception, `_record` an unrecorded outcome; the loop's `log.exception` reaches it through the logging
   integration. Tests over the scripted executor: failed → one event with the fingerprint; retried,
   gated, parked, budget → none.
4. Web: `@sentry/browser` 10.75.3, started once from `/config`'s `errorTracking` (DSN, environment,
   release); `app/global-error.tsx` and `app/app/error.tsx` report a render crash and say so in Czech.
   Tests: the config route, init only with a DSN, the scrubber.
5. Deploy: `glitchtip` (6.2.6, all-in-one, Postgres-only: no Valkey) and `glitchtip-db` (PostgreSQL 16,
   its own volume and network) as a Compose project of their own (`deploy/develop/errors`,
   `aia-errors`) on AIA's internal network, so a GlitchTip that will not start can never fail an AIA
   deploy (`--wait` would have waited on it in one project); `bin/errors.sh` up / down / status /
   admin, and `bin/deploy.sh` starts it after AIA is healthy when `aia_errors_enabled` is true,
   non-fatally. Caddy serves `errors.<public hostname>` to it alone; `tools/caddy_routes.py` allows
   exactly that; the DNS record in Terraform; SSM keys; the runbook in `deploy/develop/README.md`
   § Error tracking. Two GlitchTip projects: `aia-backend` (API and worker, told apart by the
   `service` tag; internal DSN) and `aia-web` (public DSN).

## Trade-off

A second PostgreSQL and a ~600 MB service on a 4 GB host, in exchange for not putting GlitchTip's
partition locks (`max_locks_per_transaction`) and its ingest load on AIA's database. Events are kept 30
days.

## Not done

- No email alerts until the host has an SMTP route (SES); GlitchTip's webhook alerts work without it.
- No performance tracing, no session replay, no source maps upload (the browser's stack is minified
  until a later chunk uploads them at build).

## Findings

- The API's error body loses its request id on a 500: `RequestContextMiddleware` resets
  `request_id_var` in its `finally` before Starlette's `ServerErrorMiddleware` runs the
  `Exception` handler, so `_error` reads an empty id (`apps/api/src/aia_api/observability.py`,
  `dispatch` and `_unhandled` @ f6f88cb9). **Hypothesis**: reasoned from the middleware order, not
  reproduced by a test here. The reporter is not affected: it tags the request id when the request
  starts (`error_tracking.set_tags`), and `apps/api/tests/test_api_error_reporting.py` asserts it.

## Doc follow-up

- `CLAUDE.md` § map: `aia_core/infrastructure/redaction.py` (every process's redaction, OI-23) and
  `error_tracking.py` (the reporter, off without `AIA_ERROR_TRACKING_DSN`); the `errors` extra;
  `apps/web/src/lib/error-tracking.ts`, `error-tracking-sdk.ts` and `components/errors/`; `deploy/develop/errors/` and
  `bin/errors.sh`; `errors.<hostname>` in the develop-site paragraph ("the product hostname serves
  nothing of the unit" stays true; GlitchTip is a second name).
- `CLAUDE.md` § commands: "Error tracking on develop: `bin/errors.sh up | down | status | admin`".
- `ARCHITECTURE.md`: the layer rule "sentry_sdk only in infrastructure/error_tracking.py".
- `open-items.md`: OI-23 closed by chunk 1.
