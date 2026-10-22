---
status: in-progress
chunks:
  - "[x] 1. ONLYOFFICE Docs on the develop host: a Compose project of its own (deploy/develop/docs), the upstream image pinned by digest, bin/docs.sh, off unless aia_onlyoffice_enabled"
  - "[x] 2. docs.<hostname>: its own origin in the Caddyfile, every request through AIA's docs gate, the server-only paths refused; tools/caddy_routes.py holds it"
  - "[x] 3. The docs gate in the API: a docs-only session cookie on docs.<hostname> from a one-time ticket, refused without it"
  - "[x] 3b. A timed force-save every 5 minutes while a document is open (RPT8: every autosave a stored version), through one read-only configuration file"
  - "[ ] 4. Activation on develop (operations, the owner's word; precondition: F1 fixed, __Host-aia_session in deployed environments): the host resized, docs.<hostname> in Route 53, the JWT secret in SSM, the flag on, the editor's own checks"
---
# Report editor hosting: ONLYOFFICE Docs beside the develop stack

**Drafted:** 2026-10-22 · **Base:** `develop` @ `a9508fe3` · **Asked by:** the owner, Q77 (a) on
/pmstatus, through the coordinator. Self-host ONLYOFFICE Docs Community Edition on the develop host as
its own Compose project, the way GlitchTip runs (`plan error-tracking` chunk 5), so that Zpráva can make it
the report editor (`artifact-report#RPT8`, Q35).

This plan delivers **the server and the way to it**. It does not deliver the editor integration: the editor
config, the document download and the save callback in the API, and the pane in the web. Those are RPT8's,
built in the Zpráva session against chunks 1-3.

## What exists

- GlitchTip is the pattern:
  - a project of its own: `deploy/develop/errors/docker-compose.yml`, `name: aia-errors`;
  - on AIA's network as an external network (`aia-develop_internal`);
  - started by `deploy/develop/bin/errors.sh`;
  - started by `bin/deploy.sh` only when `AIA_ERRORS_ENABLED` is true (`deploy/develop/bin/deploy.sh:147 @ a9508fe3`);
  - shipped in the deploy bundle (`.github/workflows/deploy-develop.yml:166,170 @ a9508fe3`);
  - its Compose file validated in CI with its secrets required (`.github/workflows/ci.yml:901 @ a9508fe3`);
  - its own hostname, `errors.<hostname>` (`deploy/develop/Caddyfile:104 @ a9508fe3`), which
    `tools/caddy_routes.py` allows next to the product and holds to one upstream
    (`tools/caddy_routes.py:137,143 @ a9508fe3`).
- AIA's gate (`apps/api/src/aia_api/routers/session.py`):
  - it reads the `aia_session` cookie. The cookie is host-only, `Path=/`, SameSite=Lax, and holds the
    Cognito id token (`session.py:80-86 @ a9508fe3`);
  - it lets through GET and HEAD alone (`session.py:49 @ a9508fe3`);
  - the web client keeps the same id token in `sessionStorage`
    (`apps/web/src/lib/auth.ts:96 @ a9508fe3`).
- The host:
  - `t3a.medium`: 2 vCPU, 4 GiB, no swap (`infra/develop/main.tf:419 @ a9508fe3`);
  - root volume 80 GB;
  - IMDS reachable from containers: `http_put_response_hop_limit = 2`
    (`infra/develop/main.tf:434 @ a9508fe3`).
- Measured from CloudWatch (CWAgent, daily maxima), 2026-10-15 to 2026-10-21:
  - memory used peaked at 37.0 % of 4 GiB, about 1.5 GiB, with GlitchTip running;
  - disk peaked at 68.3 % of 80 GB, about 25 GB free, rising about 1 point a day between image-retention passes.

## The upstream image

- `onlyoffice/documentserver`, Community Edition, AGPL v3, unmodified.
- Pin: tag `9.4.0.1`, index digest `sha256:3ab6ebc7c605e5a32b7ae3ff19daed4925090245acc8100ce2230bd766c88212`.
  The amd64 manifest is `sha256:e231bc62…6db84b`, 1.40 GB compressed. Read from Docker Hub on 2026-10-22.
- Why not 10.0.0.1:
  - it is a major release published 2026-10-12;
  - 9.4.0.1 has been out since 2026-05 (re-pushed 2026-07-22);
  - moving to 10.x is a one-line digest change after the editor works on 9.4.
- Everything the database, broker and cache need is inside the one image: PostgreSQL, RabbitMQ, Redis,
  nginx, the doc and converter services.
- Upstream asks for:
  - 4 GB RAM or more;
  - 2 GB swap;
  - dual-core 2 GHz;
  - 2 GB free disk (Docker-DocumentServer README).
- Community Edition allows 20 simultaneous connections.

### AGPL, and what we owe

- The image is used as published: no file is changed, nothing is built on top, the config comes only
  from documented environment variables.
- A font mount (chunk 1, optional) adds files and changes no program.
- So §13's offer of modified source does not arise.
- We still keep:
  - a notice beside the Compose file (`deploy/develop/docs/NOTICE`): the program, its licence, the exact
    digest, and where its source is (`github.com/ONLYOFFICE/DocumentServer` at the matching tag);
  - ONLYOFFICE's §7 additional terms: their logo stays in the editor, so no white-labelling.
- If a later chunk patches the image, the notice must instead point at our patched source. That is a
  change to this decision, not a detail.

## Decisions

1. **Its own origin, `docs.<hostname>`, not a path on AIA's.** A path route (`/docs/*`) would serve
   ONLYOFFICE's JavaScript from AIA's origin. There it shares `sessionStorage`, which holds the person's id
   token, and the API that trusts it. A separate origin keeps an editor bug from being an AIA credential
   leak. The cost: AIA's `aia_session` cookie is host-only, so the gate needs a cookie of its own there
   (decision 2).
2. **AIA's gate, with a docs-only cookie.** Every request to `docs.<hostname>` goes through Caddy's
   `forward_auth` to a docs gate in the API (`/api/v1/session/docs-gate`). The gate admits a request
   carrying `aia_docs`:
   - an HMAC-signed cookie, good for a working day (8 h; 60 min at first, changed after review);
   - host-only on `docs.<hostname>`, HttpOnly, Secure, SameSite=Lax;
   - it names the person and their organization, and is never the id token.

   How a person gets one:
   - the API mints a one-time ticket (60 s, single use) when it builds an editor config;
   - the editor pane first loads `https://docs.<hostname>/__aia/session?ticket=…`, which Caddy sends to
     the API;
   - the API sets the cookie and redirects.

   The docs gate lets through:
   - GET, HEAD and POST, since the editor POSTs uploads, saves-as and long-polling;
   - the WebSocket upgrade, which is a GET.

   It never redirects to `/login`: a missing or expired cookie is 401, and the pane asks for a new ticket.

   Rejected: widening `aia_session` to `Domain=<hostname>`. That would send the id token to
   `docs.<hostname>` and `errors.<hostname>` on every request, on the strength of a header strip in Caddy
   staying right forever.
3. **JWT on every request between AIA and ONLYOFFICE.**
   - `JWT_ENABLED=true`, with `JWT_SECRET` from SSM `aia_onlyoffice_jwt_secret` (SecureString, required: the
     project refuses to start without it).
   - The default header (`Authorization`), with `JWT_IN_BODY=true` so a callback's body is also signed.
   - AIA signs every editor config and every command; ONLYOFFICE signs its document fetch and its save
     callback; AIA refuses an unsigned or wrongly signed one. The integration (RPT8) carries this out.
     This plan provides the secret, to the API and to ONLYOFFICE alone.
4. **ONLYOFFICE reaches AIA through the public hostname, with its request filter left on.**
   - The document URL and the callback URL are `https://<hostname>/api/v1/…`: they go out, back in through
     Caddy and its body bound, and are logged like any other API call.
   - `ALLOW_PRIVATE_IP_ADDRESS` and `ALLOW_META_IP_ADDRESS` stay `false`. This matters because containers
     on this host can reach IMDS and the instance role's credentials (hop limit 2), and ONLYOFFICE fetches
     URLs.
   - ONLYOFFICE is not on AIA's internal network, so it cannot reach `api:8000`, `postgres` or `glitchtip`.
   - It shares a network, `aia-docs`, with Caddy alone. The API joined it at first, for a call to the
     command and conversion services that RPT8 does not make yet. Review found that this let the Document
     Server reach `api:8000` directly, so the API left it; it joins only when AIA calls the Document
     Server, through `AIA_ONLYOFFICE_INTERNAL_URL`.
5. **Locked down to the editor.**
   - Variables: `PLUGINS_ENABLED=false` (no plugin marketplace, and above all no AI plugin sending text to
     a third party); `EXAMPLE_ENABLED=false`; `WOPI_ENABLED=false`;
     `USE_UNAUTHORIZED_STORAGE=false`; `METRICS_ENABLED=false`. 9.4.0.1's start script has no
     `WELCOME_PAGE_ENABLED` (upstream's README describes a later release), so the welcome page is
     refused at Caddy instead.
   - Caddy refuses from outside the server-to-server and admin paths:
     - `/coauthoring/CommandService.ashx`, `/command`;
     - `/ConvertService.ashx`, `/converter`;
     - `/info`, `/internal`, `/example`, `/welcome`;
     - `/healthcheck` (Compose's own check reads it inside).
6. **Framed by AIA alone.** The docs site sends `Content-Security-Policy: frame-ancestors
   https://<hostname>` instead of `X-Frame-Options: DENY`. AIA's own site keeps `DENY`; the product embeds,
   it is never embedded.
7. **Sized, not squeezed.**
   - `mem_limit: 2g` and `memswap_limit: 2g` on the container.
   - With today's peak of about 1.5 GiB and GlitchTip's caps (900m + 384m), a 4 GiB host would run at its
     ceiling with no swap.
   - So activation (chunk 4) resizes to `t3a.large` (2 vCPU, 8 GiB): the README's § Resize, about
     2 minutes of downtime, the volume untouched.
   - Cost: about USD 32 a month more at list price (an estimate; not verified from this session, where the
     pricing API is not granted). The develop total goes from about 55 to about 87, inside the
     USD 100 budget, with less headroom for Bedrock.
   - Disk: the image is about 4 GB unpacked against about 25 GB free. The file cache (`/var/lib/onlyoffice`)
     is bounded by the documents open. No volume growth is needed now. If disk passes 80 %, the README's
     § Resize applies.
8. **Off by default.** SSM `aia_onlyoffice_enabled` (absent means false):
   - `bin/deploy.sh` starts the project only when it is `true`, after AIA is healthy, never failing the
     deploy — as with GlitchTip;
   - the product stack never depends on it: with it down, `docs.<hostname>` answers 502 and AIA is
     unaffected, the pane falling back to RPT2's read-only view.
9. **What is kept.**
   - The documents' truth stays in AIA's artifact store: a save is a new draft through the callback (RPT5).
   - ONLYOFFICE's cache volume and its internal database hold only the editing sessions in flight. Neither is
     in `bin/backup.sh`; losing them loses unsaved edits, not reports.
   - Logs go to the container's json-file log with GlitchTip's rotation.

## Chunks

### 1. The Compose project (`deploy/develop/docs`)

- `deploy/develop/docs/docker-compose.yml`, `name: aia-docs`, with one service, `onlyoffice`:
  - the image by digest (`onlyoffice/documentserver@sha256:3ab6…2c88212`);
  - `JWT_SECRET: ${AIA_ONLYOFFICE_JWT_SECRET:?SSM aia_onlyoffice_jwt_secret}`, plus the variables in decisions 3-5;
  - `expose: ["80"]`, no `ports:`;
  - networks: `docs` (named `aia-docs`, created here), plus an `egress` default network for the outbound
    document fetch;
  - `mem_limit: 2g`, `memswap_limit: 2g`;
  - `security_opt: [no-new-privileges:true]`;
  - volume `docs_cache:/var/lib/onlyoffice`;
  - healthcheck `curl -fsS http://localhost/healthcheck | grep -q true`, `start_period: 180s` (the first
    start builds its font cache);
  - GlitchTip's log rotation.
- Optional: AIA's vendored report fonts (OFL, `packages/aia_core/.../report_docx/fonts/`) mounted
  read-only at `/usr/share/fonts/truetype/aia`, so the editor renders the report in its own type. Only
  if RPT8's fidelity check needs it.
- `deploy/develop/docs/NOTICE`: the AGPL notice above.
- `deploy/develop/bin/docs.sh up | down | status | logs`:
  - `up` refuses unless AIA's network exists;
  - `up -d --wait --wait-timeout 420`;
  - `down` keeps the cache volume.
- `bin/deploy.sh`: start it when `AIA_ONLYOFFICE_ENABLED=true`, under `timeout`, a warning on failure, never
  failing the deploy.
- `.github/workflows/deploy-develop.yml`: `deploy/develop/docs` into the bundle.
- `deploy/develop/bin/image_retention.py`: confirm it never removes a running or pinned third-party image
  (GlitchTip's precedent); a test if it does not already hold.
- CI (`develop-host-config`):
  - the project does not validate without `AIA_ONLYOFFICE_JWT_SECRET`, and does with it;
  - the image is pinned by `@sha256:`;
  - no `ports:`;
  - `ALLOW_PRIVATE_IP_ADDRESS` / `ALLOW_META_IP_ADDRESS` are not `true`;
  - `PLUGINS_ENABLED` is `false`.
- Product stack:
  - the product stack creates `aia-docs` (`name: aia-docs`), so it exists before the editor's project
    joins it as an external network; Caddy alone of AIA's services is on it;
  - the API gets `AIA_ONLYOFFICE_URL` and `AIA_ONLYOFFICE_JWT_SECRET`, both unset unless SSM has them;
  - CI asserts the web service never receives the secret.

### 2. `docs.<hostname>` in the Caddyfile

- A third site, `docs.{$AIA_PUBLIC_HOSTNAME}`:
  - headers: HSTS, nosniff, the `frame-ancestors` CSP, `-Server`;
  - `/__aia/session` → `api:8000` (rewritten to `/api/v1/session/docs`);
  - the paths of decision 5 → `respond 404`;
  - everything else: `forward_auth api:8000 { uri /api/v1/session/docs-gate }`, then
    `reverse_proxy onlyoffice:80 { header_up -Cookie … }`;
  - WebSockets pass through Caddy unchanged;
  - a `request_body` bound for uploads (images into a document): 40 MiB, like the API's.
- `tools/caddy_routes.py` and `packages/aia_core/tests/test_caddy_routes.py`:
  - the only sites are the product, `errors.` and `docs.`;
  - `docs.` reaches `onlyoffice:80` only behind the docs gate, and the API only at `/__aia/session`;
  - the server-only paths are refused;
  - the cookie is dropped before ONLYOFFICE;
  - nothing on the product site reaches `onlyoffice:80`.
- `tools/develop_routing_proof.py`: a stand-in for `onlyoffice:80`, and the gate checked in the browser
  journey.

### 3. The docs gate (API)

- `POST /api/v1/session/docs-ticket`: an active member's one-time ticket, 60 s. The RPT8 editor-config
  route may mint it in the same response instead.
- `GET /api/v1/session/docs?ticket=…`:
  - spends the ticket (single use, stored hashed, refused twice);
  - sets `aia_docs` (HMAC with a key from `AIA_ONLYOFFICE_JWT_SECRET`'s derivation, 8 h, host-only,
    HttpOnly, Secure, Lax);
  - redirects to the path the ticket names on `docs.<hostname>`.
- `GET /api/v1/session/docs-gate`:
  - 204 for a valid, unexpired `aia_docs` whose person is still an active member (`authorize_session`);
  - 401 otherwise, never a redirect;
  - methods GET, HEAD and POST.
- Off when `AIA_ONLYOFFICE_JWT_SECRET` is unset: 404 on all three, and the product is unchanged.
- Tests:
  - ticket single use and expiry;
  - a cookie from another organization's member;
  - a removed member refused at the gate;
  - a forged and an expired cookie;
  - the method rule;
  - unset secret → 404;
  - the cookie is never the id token.
- Whether this chunk is built here or in the Zpráva session: here by default, since chunk 2's route is
  its contract. The Zpráva session builds the editor config, the document fetch and the save callback on
  top (RPT8).

### 4. Activation on develop (operations)

**Precondition: finding F1 is fixed.** AIA's session cookie must be `__Host-aia_session` in deployed
environments before `aia_onlyoffice_enabled` or `aia_onlyoffice_url` is set. Until then, one script defect
in the Document Server could plant `aia_session; Domain=<hostname>; Path=/app`, which AIA's gate would read
ahead of the host-only cookie. That is a login CSRF, and a lockout `DELETE /session` cannot clear, since it
deletes only the host-only cookie (review of #785, 2026-10-22). Nothing is served while the editor is off,
so this PR does not wait on it; activation does.

Each step needs the owner's word and the coordinator's approval:

1. Resize to `t3a.large`: `instance_type` in the SSM tfvars, `terraform apply`, about 2 minutes down.
   Done 2026-10-22, 14:05-14:06 UTC: one in-place change, status checks ok at 14:08; the SSM tfvars
   change is Nigel's.
2. `aws_route53_record.docs` in `infra/develop/main.tf` (like `errors`), then apply. This is the only
   Terraform code change, in this plan's PR.
3. SSM `aia_onlyoffice_jwt_secret`: `openssl rand -hex 32`, SecureString, by hand, like the GlitchTip secrets.
4. SSM `aia_onlyoffice_enabled=true`.
5. Deploy. `bin/docs.sh status` healthy.
6. Checks from outside:
   - `https://docs.<hostname>/` without the cookie → 401;
   - `/coauthoring/CommandService.ashx` → 404;
   - `/healthcheck` → 404;
   - a ticket opens the cookie;
   - the editor's own `api.js` loads framed by AIA and not from another origin.
7. Rollback: `aia_onlyoffice_enabled=false`, `bin/docs.sh down`. The resize can stay or be reversed.

## The contract with RPT8 (agreed with the Zpráva session, 2026-10-22)

- **Settings.**
  - `AIA_ONLYOFFICE_URL`: the public origin, `https://docs.<hostname>`, from SSM `aia_onlyoffice_url`.
    Unset by default; while it is unset, Zpráva keeps RPT2's read-only pane.
  - `AIA_ONLYOFFICE_INTERNAL_URL`: not yet. RPT8 makes no API-to-Document-Server call at first; when it
    does, the API joins `aia-docs` in that PR, and `http://onlyoffice` is its way in.
  - `AIA_ONLYOFFICE_JWT_SECRET`: from SSM `aia_onlyoffice_jwt_secret`; the API and the Document Server
    only, never the web service.
  - `aia_onlyoffice_enabled`: whether the host runs the project at all.
- **CSP on AIA's pages.** `frame-src` and `script-src` include `https://docs.<hostname>`, and only it.
- **The script load is the way in.** The pane asks the API for a ticket, then loads
  `https://docs.<hostname>/__aia/session?ticket=…&next=/web-apps/apps/api/documents/api.js` as its
  script. The API spends the ticket, sets `aia_docs` and redirects to `next`, which must be a path on
  `docs.<hostname>` (refused otherwise). `api.js` and everything the editor loads after it then carry
  the cookie. Same-site, so SameSite=Lax holds.
- **The document fetch and the save callback go through the public hostname, not the internal
  network** (decision 4):
  - the URLs are `https://<hostname>/api/v1/…/report/editor/document?token=…` and
    `…/report/editor/callback`;
  - the Document Server's request filter refuses private addresses, and this host's containers can
    reach IMDS;
  - each route is authorized by its own short-lived token and the Document Server's JWT, so the
    session gate is not involved;
  - the API's service name is therefore not part of the contract.
- **Document key.** The stored version's artifact id and its SHA-256, as RPT8 proposed. ONLYOFFICE takes
  at most 128 characters of `0-9 a-z A-Z . = _ -`; the artifact id plus 64 hex characters fits.
- **Outbound calls.** The Document Server makes exactly two kinds:
  - to `https://<hostname>`, for the document fetch and the save callback;
  - with plugins off, no third-party calls.

  Egress is not firewalled at the container (no egress filter on this host); the variables and the URLs
  AIA signs are what keep it to these.

## Doc follow-up (for the docs PR)

- CLAUDE.md § 2 map:
  - `deploy/develop/docs` (ONLYOFFICE Docs, its own Compose project, `docs.<hostname>`, AGPL notice);
  - `bin/docs.sh`;
  - the docs gate in `routers/session`.
- CLAUDE.md § 3: `bin/docs.sh up | down | status | logs`.
- ARCHITECTURE.md: the third origin, and why it is not a path.
- `deploy/develop/README.md` § Report editor is in this PR: it is the runbook beside the code, like
  § Error tracking.

## Measured (chunk 1, 2026-10-22)

`onlyoffice/documentserver:9.4.0.1@sha256:3ab6…2c88212`, started locally with exactly the
environment in `deploy/develop/docs/docker-compose.yml`, `--memory 2g --memory-swap 2g`, and
`no-new-privileges`:

- `/healthcheck` answered `true` about 10 s after start.
- About 530 MiB once its first-start font and theme generation finished: docservice about 214 MiB,
  converter about 164 MiB.
- No PostgreSQL, RabbitMQ or Redis process runs in this release's Community image. Its editing state is
  in memory and `/var/lib/onlyoffice`.
- 4.86 GB unpacked.
- Inside the container, `/welcome/` and `/info/info.json` answer 200, which is why decision 5 refuses
  them at Caddy.
- An unsigned `CommandService.ashx` request answered `{"error":6}` (invalid token): JWT is enforced.
- `deploy/develop/bin/image_retention.py:108 @ 9eb78f6c` only ever removes this registry's
  `aia-(api|worker|web)` images, so the Document Server's image is never a candidate.

So the 4 GiB host would carry it idle: about 2.0 of 3.8 GiB at today's peak. Editing sessions and a
LibreOffice PDF render on the worker would leave little room, and the host has no swap. The resize stays
(the owner approved it, 2026-10-22).

## Proved (chunk 2, 2026-10-22)

Caddy 2.10.2 ran the real Caddyfile, with only its three site names given an `http://` scheme, in front of
the real Document Server (9.4.0.1, the chunk 1 settings) and a stand-in for the API's two docs routes, all on
one Docker network:

| Request to docs.<host> | Answer |
|---|---|
| `api.js`, no cookie | 401 from the docs gate |
| `/__aia/session?ticket=T1&next=…api.js` | 302 to `next`, `Set-Cookie: aia_docs=…`; the API saw the query and `Host: docs.<host>` |
| `api.js`, with the cookie | 200 |
| `POST /coauthoring/CommandService.ashx`, `POST /9.4.0-1/coauthoring/CommandService.ashx`, `//info/info.json`, `/AI-PROXY/x`, `/healthcheck`, `/welcome/` | 404 each, before the gate is asked |
| `POST /downloadas/abc`, with the cookie | passed the gate (`X-Forwarded-Method: POST`), then the Document Server's own 400 for an empty body |
| WebSocket upgrade, no cookie | 401 |
| WebSocket upgrade, with the cookie | 101 Switching Protocols; the gate received no `Upgrade` header |

Every answer carried `Content-Security-Policy: frame-ancestors https://<host>`.

The Document Server's nginx (`/etc/nginx/includes/ds-docservice.conf` in the image) has a versioned location,
`location ~ ^/([\d]+\.[\d]+\.[\d]+[\.|-][\w]+)/(?<path>.*)$`, which passes any path to the document
service. A plain path match on `/coauthoring/CommandService.ashx` would therefore leave
`/9.4.0-1/coauthoring/CommandService.ashx` open. The refusal is one case-insensitive `path_regexp` that takes
the prefix and repeated slashes, and `tools/caddy_routes.py` checks it against sample paths both ways: refused
ones, and the editor's own paths, which must stay open. The same config also showed an `/ai-proxy` location;
it is refused.

## Built (chunk 3, 2026-10-22)

- `apps/api/src/aia_api/docs_pass.py`: the ticket and the cookie, `<payload>.<mac>`, HMAC-SHA256 under
  a key derived from `AIA_ONLYOFFICE_JWT_SECRET` (never the secret itself), read back only as their own
  kind, unexpired, under the same secret.
- `routers/session.py`:
  - `POST /session/docs-ticket` takes the person's own token;
  - `GET /session/docs` answers only when the request's Host is the editor's origin (any other host is
    404 and spends nothing), admits and audits (`AIA_SESSION`, or `AIA_SESSION_DENIED`), then sets
    `aia_docs` and redirects to `next` through `_local_path`;
  - `GET /session/docs-gate` checks the method first (GET, HEAD, POST), then the cookie, then the person,
    who must still be an active member of the organization the cookie names; it answers 401, never a
    redirect.
  - All three answer 404 until both `AIA_ONLYOFFICE_URL` (an https origin, checked at start) and
    `AIA_ONLYOFFICE_JWT_SECRET` (at least 32 characters) are set.
- `docs_ticket_spends`, migration `f4b6d8a0c2e3`: single use by primary key. It was run up, down and up
  on PostgreSQL 16, and `alembic check` finds nothing to add. `DocsTicketRepository` writes it only
  under the `OrganizationContext` that `ScopeResolver` issued, and deletes that person's rows a day past
  expiry. `application/docs_session.open_docs_session` is the router's way to it (the ratchet contract).
- Tests: `apps/api/tests/test_docs_pass.py` (19) and `test_docs_session_api.py` (35), on SQLite and on
  PostgreSQL; the existing session tests pass unchanged.
- `infra/develop/main.tf`: `aws_route53_record.docs`, like `errors`. A read-only plan on 2026-10-22
  (`-lock=false`, the SSM tfvars) showed 2 to add: `docs[0]`, and `errors[0]`, the drift known since
  2026-10-20 (the record is in the zone but not in state). An apply would fail on `errors[0]`, so
  activation imports it first:
  `terraform import 'aws_route53_record.errors[0]' Z0491946PNRJDOXB1EWV_errors.aia-develop.art-chain.io_A`.

Accepted, said here: the ticket travels in the query of `/__aia/session`, so Caddy's access log on
`docs.<hostname>` records it. It is good once and for 60 seconds, and spent on that very request, so the
logged value opens nothing.

## Timed force-save (chunk 3b, 2026-10-22, evening)

Asked by the Zpráva session (PR #824, artifact-report "Revision of 2026-10-22, evening"): the owner
decided that every autosave becomes a stored report version, so the Document Server must force-save
every 5 minutes while a document is open; AIA's callback then gets status 6 with forcesavetype 2.

- The setting is `services.CoAuthoring.autoAssembly` (`default.json` of 9.4.0.1: `enable: false,
  interval: "5m", step: "1m"`). No environment variable reaches it.
- **Not `local.json`.** The image's start script (`/app/ds/run-document-server.sh`, `ONLYOFFICE_DEFAULT_CONFIG`)
  writes `local.json` at every start, the JWT secrets among it, and the image ships one with a fixed
  secret. A read-only `local.json` would stop that write: at best the start fails, at worst the server
  runs on the image's published secret.
- **`local-production-linux.json` instead**: the services run with `NODE_ENV=production-linux` and
  `NODE_CONFIG_DIR=/etc/onlyoffice/documentserver` (`/etc/supervisor/conf.d/ds-docservice.conf`), and
  their configuration loader reads `local-<NODE_ENV>.json` after `local.json`. Proved on the pinned image,
  2026-10-22 23:40 UTC: the same mount carrying `server.port: 8001` moved the document service to 8001,
  and `local.json` still held the JWT secret given in the environment. With the real file
  (`autoAssembly: {enable: true, interval: "5m"}`) `/healthcheck` answered `true`.
- `deploy/develop/docs/local-production-linux.json`, mounted read-only; nothing else in it.
- CI's "Validate the report editor's Compose project" now holds the one bind mount (that path, read-only)
  and the file's exact content. Run on the previous Compose file, it fails (`AssertionError: []`).
- `NOTICE`: the program is still unmodified. A configuration file its own loader reads is configuration,
  not a change to the program's code, so AGPL section 13's offer of modified source does not arise; the
  notice now names the file.
- Not measured here (a hypothesis, from upstream's documentation of forcesavetype 2): the timer saves
  only a document that changed since its last save, so an open document nobody edits sends no callback.
  RPT8's end-to-end test (an edit, then a callback within the interval plus `step`) is what proves it.

## Review (2026-10-22, before the push)

`/security-review` reported nothing it was at least 80 % sure was exploitable. It noted cookie tossing from
`docs.<hostname>` as hardening. `/code-review` (medium) reported nine findings:

| # | Finding | Outcome |
|---|---|---|
| 1 | The 60-minute docs cookie cannot be renewed (forward_auth's answer never reaches the browser), so a session longer than an hour breaks mid-edit | **Fixed**: 8 h, a working day. The gate still re-checks active membership on every request, so the age only bounds a stolen cookie |
| 2 | A configured port (`https://docs.x:443`) never equals the Host a browser sends | **Fixed**: a port is refused at start |
| 3 | A fragment or a password-only userinfo passed the origin check | **Fixed**: the origin must be exactly `https://<host>` (`netloc == hostname`, no path, params, query or fragment); tests for each |
| 4 | Caddy's access log on the docs site would write the ticket in the URI | **Fixed**: the docs site's log filter deletes `ticket` from `request>uri`. Proved on the real Caddy: the API received `SECRET-TICKET-123`, and the log line reads `"/__aia/session?next=%2Fx"`. `tools/caddy_routes.py` requires the filter |
| 5 | Login CSRF: a member's ticket link opened by another person gives that browser a docs cookie in the member's name | **Not changed**: the cookie names no document. What a browser may open is the editor config AIA signs for that browser's own AIA session (ONLYOFFICE's JWT), so the cookie's name decides nothing; the gate only stands in front of the Document Server |
| 6 | The Document Server shared `aia-docs` with the API, so it could call `api:8000` directly | **Fixed**: the API left `aia-docs` (decision 4); CI asserts Caddy alone is on it |
| 7 | Cookie tossing: a script on `docs.<hostname>` can set a cookie for the parent domain, `aia_session` included | **Finding F1 below** |
| 8 | The docs gate checks membership in the database for every asset | **Kept, said**: the same check AIA's own gate makes per page request; it is what shuts a removed member out at once, and it runs only while the editor is on |
| 9 | `claims.ticket_id is None` duplicates what `read(kind="ticket")` guarantees | **Kept**: it narrows the type for `open_docs_session(ticket_id: str)` under mypy --strict |

The coordinator's stand-in review of #785 (2026-10-22) found two P2s, both fixed in `e0f767a8`: the runbook's
stale cookie lifetime, and F1 named as chunk 4's precondition. Its optional note was checked on the real
Caddy with the API down. Caddy's error logger (`http.log.error.log2`, written by the default logger) did
record the URI with the unspent ticket. The default logger now deletes `ticket` from `request>uri` too:
the same request then logged `"/__aia/session?next=%2Fx"` in both its access and error lines, and
`tools/caddy_routes.py` requires both filters.

## Findings

- **F1. A script on `docs.<hostname>` can plant a cookie AIA's pages read.**
  - **Claim:** `docs.<hostname>` is a subdomain of the product hostname, so script running there can set
    `aia_session` with `Domain=<product hostname>`, and the browser sends it to AIA's pages. AIA's own
    cookie is host-only but has no `__Host-` prefix to refuse such a planted twin.
  - **Anchor:** `apps/api/src/aia_api/routers/session.py:68` @ 8b51875b (`SESSION_COOKIE = "aia_session"`).
  - **Reproduction:** a hypothesis until shown. It needs script execution on `docs.<hostname>`, that is,
    a defect in ONLYOFFICE.
  - **Consequence:** a person could be working in AIA as somebody else (login CSRF), never reading
    another organization's data unseen.
  - **Smallest fix:** the session cookie as `__Host-aia_session` in deployed environments (Secure,
    Path=/, no Domain), read by the gate and the session routes.
  - **Test that would catch it:** the gate refusing a request whose only session cookie is the
    unprefixed name, in production settings.

  A follow-up of its own: it changes AIA's sign-in, not this host.

- **F2. A deploy of a SHA older than #785 fails before reaching the host.** Fixed in this plan's follow-up
  PR.
  - **Claim:** `deploy-develop.yml` runs from develop's head but checks out the SHA it deploys, and its
    bundle step named `deploy/develop/docs` unconditionally. A SHA from before #785 has no `docs/`, so
    `cp` failed.
  - **Anchor:** `.github/workflows/deploy-develop.yml:165-170 @ 07b2fa31`.
  - **Reproduction:** deploy run 39811181434 (inputs.sha `013f2e11`) failed with
    `cp: cannot stat 'deploy/develop/docs'`. CI's "The deploy bundle of an older SHA" step, run on the
    previous workflow, fails the same way.
  - **Consequence:** a rollback or re-dispatch of an older SHA cannot deploy. Nothing reached the host;
    the site stayed on the SHA it ran.
  - **Smallest fix:** the bundle carries what the deployed SHA has: `errors/` and `docs/` only where
    they exist.
  - **Test that would have caught it:** that CI step. It runs the real bundle step, in Actions' shell
    and with S3 stubbed, on `013f2e11` and on the current tree.
