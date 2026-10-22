---
status: in-progress
chunks:
  - "[x] 1. ONLYOFFICE Docs on the develop host: a Compose project of its own (deploy/develop/docs), the upstream image pinned by digest, bin/docs.sh, off unless aia_onlyoffice_enabled"
  - "[ ] 2. docs.<hostname>: its own origin in the Caddyfile, every request through AIA's docs gate, the server-only paths refused; tools/caddy_routes.py holds it"
  - "[ ] 3. The docs gate in the API: a docs-only session cookie on docs.<hostname> from a one-time ticket, refused without it"
  - "[ ] 4. Activation on develop (operations, the owner's word): the host resized, docs.<hostname> in Route 53, the JWT secret in SSM, the flag on, the editor's own checks"
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
   - an HMAC-signed, short-lived (60 min) cookie;
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
   - AIA's API reaches ONLYOFFICE's command and conversion services at `http://onlyoffice` on a network
     the two share: a dedicated `docs` network, which only the API and Caddy join.
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
  - `api` and `caddy` join the external network `aia-docs`, declared `external: true` with
    `name: aia-docs`. Compose refuses to start a service on a missing external network, so `bin/deploy.sh`
    creates the network idempotently before `up`, whether docs is on or not;
  - the API gets `AIA_ONLYOFFICE_JWT_SECRET` and `AIA_ONLYOFFICE_INTERNAL_URL=http://onlyoffice`, both unset unless
    SSM has them;
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
  - sets `aia_docs` (HMAC with a key from `AIA_ONLYOFFICE_JWT_SECRET`'s derivation, 60 min, host-only,
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

Each step needs the owner's word and the coordinator's approval:

1. Resize to `t3a.large`: `instance_type` in the SSM tfvars, `terraform apply`, about 2 minutes down.
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
  - `AIA_ONLYOFFICE_INTERNAL_URL`: `http://onlyoffice`, the API's way to the command and conversion
    services on `aia-docs`.
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

## Findings

None yet.
