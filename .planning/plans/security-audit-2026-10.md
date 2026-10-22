---
status: in-progress
chunks:
  - "[x] 1. The sign-in's `next` cannot leave the origin through a tab, CR or LF (S1; #705, merged 2026-10-22)"
  - "[x] 2. A sign-in never takes over an account bound to another identity-provider subject (S2; #704, merged 2026-10-22)"
  - "[x] 3. Every step failure the worker records is redacted, at any depth (S3; #710, merged 2026-10-22)"
  - "[x] 4. An ODT or ODS run of spaces cannot expand past the part's own bound (S4; #707, merged 2026-10-22)"
  - "[x] 5. The questionnaire XLSX reader refuses cells past XFD and past a million cells (S5; #708, merged 2026-10-22)"
  - "[x] 6. An XML part declaring a DTD is refused in any encoding, and the questionnaire reader refuses one too (S6; #709, merged 2026-10-22)"
  - "[x] 7. Caddy bounds an API request body at 40 MiB, checked by tools/caddy_routes.py (S7; #706, merged 2026-10-22)"
  - "[x] 8. CI's pip-audit installs the errors extra the images ship (S8; #711, merged 2026-10-22)"
  - "[ ] 9. PDF table extraction inflates within a bound and a wall clock that holds inside one page (S9)"
  - "[ ] 10. DOCX table rows read one cell per w:tc, never repeated by gridSpan or vMerge past a bound (S10)"
  - "[x] 11. No entity expands in an XLSX source or attachment (S11; #709: refuse_dtd over every workbook member before openpyxl, not defusedxml)"
  - "[ ] 12. AIA_MAX_REQUEST_BYTES is enforced by the API, per route, or removed from Settings (S12)"
  - "[ ] 13. A web fetch has an overall deadline, not only a per-read timeout (S13)"
  - "[x] 14. Only an OWNER grants or removes OWNER, and the last OWNER is never demoted (S14; the product owner chose option (b) on 2026-10-22; #782, merged 2026-10-22)"
  - "[ ] 15. ScopeRepository.deactivate_user acts only on a member of the admin's organization (S15)"
  - "[ ] 16. Hardening: email_verified, a CSP, worker log fields redacted, URL userinfo and AWS key shapes redacted, workflow inputs through env, GlitchTip on its own network (S16-S21)"
  - "[ ] 17. A route for clear_subject that settles cross-organization effect and deduplicates refused-sign-in audit rows (S22)"
  - "[ ] 18. Dependabot scans what deploys, and the prototype's lockfile is audited or excluded by name (S23)"
---
# Security audit, 2026-10-21

A full security audit of `develop` at `bfe6d15`, run on the product owner's instruction of
2026-10-21 22:30 UTC. It covered every route in `apps/api/src/aia_api/routers`, file and source
intake, egress, secrets, the web client, dependencies and the develop deployment configuration.

Chunks 1-8 were merged on 2026-10-22 as #704-#711, one fix per PR, each with a test that fails
before it. Review found a defect in several of the first versions; each was fixed on its PR before
merge (see "Found in review" under each finding). Chunk 14 is on its own PR, after the product
owner's decision. Chunk 11 was closed by #709. Chunks 9, 10, 12, 13 and 15-18 are open.

## What holds

Each claim below carries `file:line @ bfe6d15`, and a test name where one pins it.

- **Cross-organization and cross-client isolation holds on every route.** Every id from a
  path, a query or a body resolves inside the `ScopeResolver` context. The study comes from
  `StudyRow.organization_id` (`application/scope.py:224-242`). Sub-resources are filtered by
  organization, client and study in their repository, and a denial is a uniform 404. No IDOR
  was found.
- **The error contract leaks nothing.** An unhandled exception is a generic 500
  (`apps/api/src/aia_api/observability.py:237-251`), `details` are redacted, `X-Request-ID` is
  sanitised, and the request log carries the path only.
- **Identity is verified.** Cognito pins RS256 and checks `kid`, the signature, `iss`,
  `token_use`, the audience and `exp`/`nbf`. `validate_for_production` refuses any provider but
  Cognito in every deployed environment (`config.py:359-438`). The development provider
  refuses construction outside local and test.
- **The session cookie** is HttpOnly, SameSite=Lax, and Secure when deployed
  (`apps/api/src/aia_api/routers/session.py:79-81`;
  `test_every_active_member_gets_an_httponly_lax_session_cookie`). Only the gate reads it, and
  the gate refuses every method except GET and HEAD (`session.py:49,154`;
  `test_a_page_takes_no_writes_whoever_asks`). The API is bearer-only, so there is no CSRF
  surface.
- **Egress.** `check_url` and `check_address` refuse every non-global address, including the
  IPv4-mapped forms (`packages/aia_core/src/aia_core/domain/deep_research/web.py:150,163`;
  `test_private_link_local_and_multicast_addresses_are_refused`). Every redirect hop is checked
  again (`test_every_redirect_hop_is_checked_and_the_metadata_service_is_never_reached`). A
  connection goes to the checked IP with SNI and `assert_hostname`, so DNS rebinding is closed
  (`infrastructure/web_retrieval_live.py:115-118,137-140`;
  `test_a_host_that_resolves_to_a_private_address_is_refused_before_any_request`). No proxy is
  read from the environment, and bodies are capped while they stream: the response is read
  unpreloaded and stops past `max_bytes` (`infrastructure/web_retrieval_live.py:153,165`; the
  contract, `infrastructure/web_retrieval.py:175`).
- **Storage keys** are built by the server from ids and SHA-256, never from a filename, and
  checked before use (`infrastructure/storage.py:79`, `_validate_key`; `:313`, the filesystem
  root check). Download headers are sanitised and served as `application/octet-stream`
  attachments with `nosniff` (`apps/api/src/aia_api/routers/workspace.py:2283-2296`).
- **Web client.** The only `dangerouslySetInnerHTML` is Temml with `trust: false`, over the
  catalogue's own LaTeX (`apps/web/src/components/aia/settings/MethodologyFormula.tsx:29`;
  `apps/web/src/lib/methodology.ts:91`). The browser's error reporter strips every URL's query
  and fragment, the OAuth `code` with them (`apps/web/src/lib/error-tracking.ts:29,95,131-133`).
- **Develop host.** Only Caddy's ports 80 and 443 are published
  (`deploy/develop/docker-compose.yml:59-62`; `:347`, PostgreSQL deliberately without one). App
  containers are `read_only` with `no-new-privileges` (`docker-compose.yml:125,127`,
  `:202,204`, `:331,333`) and run as non-root users (`deploy/docker/python.Dockerfile:109,152`,
  `USER aia`; `apps/web/Dockerfile:50`, `USER node`).
- **Dependencies.** `npm audit-gate` blocks nothing (`.github/workflows/ci.yml:1002`; one
  dev-only `braces` advisory, allowlisted in `apps/web/audit-allowlist.json`). pip-audit over
  the image's extras reports nothing (`ci.yml:988`); see S8 for the gap in what it read.

## Findings

Each finding is written in the six parts of CLAUDE.md §9. Anchors are at `bfe6d15`.

### Fixed and merged (chunks 1-8)

- **S1. The sign-in's `next` accepts a path the browser turns into another host.**
  1. Claim: `localPath` and `_local_path` refuse `//` and `\` in the raw string. The browser's
     URL parser drops tab, CR and LF, so `/\t/evil.example` becomes `//evil.example`.
  2. Anchor: `apps/web/src/lib/session.ts:17-20`, `apps/api/src/aia_api/routers/session.py:65-69`.
     The redirect is `apps/web/src/app/login/page.tsx:47,53`.
  3. Reproduction: `node -e 'console.log(new URL("/\t/evil.example","https://a").href)'`
     prints `https://evil.example/`. The tests: `session.test.ts` "is a path on this origin,
     never elsewhere", and `test_the_login_redirect_never_leaves_the_origin[/\t/evil.example/]`.
  4. Consequence: a signed-in member who opens
     `https://aia-develop.art-chain.io/login?next=%2F%09%2Fevil.example` is sent straight to
     the attacker's site, from AIA's own origin. It works as a phishing hop.
  5. Fix: the web resolves `next` against a fixed origin with `new URL` and requires the same
     origin. The API refuses any control character.
  6. Tests: as in 3.
- **S2. A sign-in binds by e-mail to an account already bound to another subject.**
  1. Claim: `upsert_user` falls back to e-mail and returns that row even when the row's
     `external_subject` is set and different.
  2. Anchor: `packages/aia_core/src/aia_core/infrastructure/scope_repository.py:156-182`,
     called from `apps/api/src/aia_api/dependencies.py:335-340`.
  3. Reproduction: `test_a_second_subject_with_a_members_email_is_not_that_member` (it gets a
     204 and the owner's session before the fix).
  4. Consequence: whoever holds a token for another subject with the same `email` claim
     becomes that member, OWNER role included. Examples are an address reassigned in the
     Workspace directory, or a second identity provider. Today this needs control of the
     Workspace directory.
  5. Fix: raise `SubjectMismatch`. The API answers 403 `identity_mismatch` and logs the user
     id.
  6. Tests: as in 3, plus `test_an_email_never_hands_one_subjects_account_to_another`.
- **S3. A failure an executor *returns* reaches `error_json` unredacted.**
  1. Claim: only a raised `StepFailed` passed through `_redacted`, and only its top-level
     strings were redacted. A returned `Failed(..., {"message": str(exc)})` was written as it
     came.
  2. Anchor: `apps/worker/src/aia_worker/worker.py:434` (returned) and `:403`, `:545-547`
     (raised, top level only). The returned form is used at `research.py:524`,
     `report.py:125` and `ai_fieldwork.py:381`, among others.
  3. Reproduction: `test_a_failure_an_executor_returns_is_redacted_too_at_any_depth`.
  4. Consequence: a key or token in an exception's text is stored and served to the browser
     through the run's attempts, and reaches the error report. No such exception text was
     traced, so this is the guard on one path only (A8).
  5. Fix: `_record_failure` redacts every failure, at any depth, with a depth bound that
     fails closed.
  6. Test: as in 3.
- **S4. An ODT or ODS `text:s` run expands without a bound.**
  1. Claim: `" " * int(text:c)` is built with no limit.
  2. Anchor: `packages/aia_core/src/aia_core/infrastructure/source_reading.py:216`, read at
     `:245`, `:252` and `:483`.
  3. Reproduction: `test_a_run_of_spaces_never_expands_past_the_bounds`. Before the fix it is
     PARTIAL with 120 MB of spaces. A 247-byte ODT reached 966 MB in the audit.
  4. Consequence: any member's upload exhausts the API's memory.
  5. Fix: one budget per document, `ODF_MAX_SPACES` (the part's own 50 MB bound). Past it, the
     document is refused with `document_zip_bounds`.
  6. Tests: as in 3, plus `test_a_run_of_spaces_within_the_bounds_reads_as_written`.
- **S5. The questionnaire XLSX reader materializes a row up to any column a cell names.**
  1. Claim: the column is decoded from the reference with no limit, and the row is built as
     `range(maxc + 1)`.
  2. Anchor: `packages/aia_core/src/aia_core/infrastructure/questionnaire_file.py:91-112`.
  3. Reproduction: `test_a_sheet_naming_cells_far_past_its_content_is_refused`. In the audit,
     an 800-byte file with `ZZZZZZ1` made a 321-million-element row.
  4. Consequence: `POST …/workspace/questionnaire-import` exhausts the API's memory.
  5. Fix: refuse a column past XFD, and more than 1,000,000 cells, as `unreadable`.
  6. Test: as in 3.
- **S6. A UTF-16 XML part's DTD passes the byte check, and the questionnaire reader has no
  check at all.**
  1. Claim: `_part` looks for `b"<!DOCTYPE"` in the raw bytes, which never occurs in UTF-16.
     The questionnaire reader's `ET.fromstring` has no guard.
  2. Anchor: `source_reading.py:182`, and `questionnaire_file.py:63-87`.
  3. Reproduction: `test_a_dtd_is_refused_in_whatever_encoding_the_part_declares` (READ, with
     the entity expanded, before the fix) and `test_a_workbook_part_declaring_a_dtd_is_not_parsed`.
  4. Consequence: entity expansion bounded only by expat's own 100x amplification limit. A
     50 MB part reaches about 4 GB in the API.
  5. Fix: `document_text.refuse_dtd`, an expat pre-pass whose doctype and entity handlers
     raise before anything is defined. Both readers use it. Cost: one more expat pass over
     each part.
  6. Tests: as in 3.
- **S7. Nothing bounds an API request body before the whole of it is read.**
  1. Claim: uploads are base64 inside JSON. FastAPI reads and parses the whole body before
     dependencies (authentication among them) run, and Caddy sets no `request_body`.
  2. Anchor: the `handle /api/v1/*` block in `deploy/develop/Caddyfile:38-42`. For S12, the
     setting that claims a ceiling: `apps/api/src/aia_api/config.py:216`.
  3. Reproduction: `test_an_api_that_takes_a_body_of_any_size_is_refused`
     (`tools/caddy_routes.py` on the adapted config).
  4. Consequence: an unauthenticated stranger makes the API hold gigabytes before it answers
     401.
  5. Fix: `request_body { max_size 40MiB }`, above the largest upload (25 MiB as base64 in
     JSON). `tools/caddy_routes.py` holds it between 36 and 64 MiB.
  6. Tests: as in 3, plus `test_the_real_caddyfile_adapts_to_routing_that_passes` when `caddy`
     is installed.
- **S8. CI's dependency audit skipped the `errors` extra the images ship.**
  1. Claim: the image installs `aia_core[…,errors]` (sentry-sdk). The audit step installs
     every extra but that one.
  2. Anchor: `.github/workflows/ci.yml:986` and `deploy/docker/python.Dockerfile:55`.
  3. Reproduction: `test_the_audit_installs_every_extra_the_images_ship`.
  4. Consequence: an advisory against sentry-sdk or what it resolves would ship to develop
     without turning CI red. None exists today.
  5. Fix: add `errors` to the audit's install.
  6. Test: as in 3.

### Found in review, fixed before merge

Each first version above had a test that failed before it; review still found these, each
reproduced, fixed with a test that failed first, and merged with its PR. They are the record of
what a bound on one path misses.

- **#705 (S1):** returning the *parsed* path reopened the redirect through dot segments:
  `/.//evil.example` normalises to the pathname `//evil.example`. Fixed by returning `next` as
  given once it resolves to this origin (`0d79eafb`).
- **#710 (S3):** a private copy of the redaction dropped the shared key rule
  (`{"password": "..."}` kept); moving onto the shared `redact` then blanked
  `needed_tokens` / `context_window_tokens` in `analysis.py`'s refusal. Fixed by the shared
  rule, which now keeps numbers (`d230bc89`, `f1435a68`).
- **#704 (S2):** the refusal reached only the application log, and nothing could rebind a
  genuinely changed subject. Fixed by an `AIA_SESSION_DENIED` / `identity_mismatch` audit row
  committed before the 403, and `ScopeRepository.clear_subject` (`6f9b588d`, `fb0901fc`; its
  route is S22).
- **#707 (S4):** the space budget was charged once per ODS cell, but a cell is repeated across
  columns and rows (636 bytes peaked at 1.1 GB). Fixed by `ODS_MAX_CHARS`, charging every kept
  copy (`229a975a`).
- **#708 (S5):** the column bound ran after an unbounded letter run was converted (quadratic:
  300,000 letters took 12 s). Fixed by refusing more than three letters first (`c34ab1b7`).
- **#709 (S6, S11):** the XLSX readers handed the workbook to openpyxl unchecked, and then the
  check chose parts by extension while openpyxl finds them by content type (`xl/s.bin`). Fixed by
  `refuse_dtd` over every member before `load_workbook` (`ed598f8c`, `46e41be2`).

### Open (chunks 9-18)

- **S9. A PDF's table extraction inflates without a bound.**
  1. Claim: `_pdf_tables` says pypdf's inflate bound already held, but pypdf truncates at
     75 MB rather than raising. pdfminer (`pdftypes.py:328`) then inflates the same stream with
     no limit, and the 20 s deadline is only checked between pages.
  2. Anchor: `packages/aia_core/src/aia_core/infrastructure/document_text.py:272-324`, and the
     docstring at `:276-279`.
  3. Reproduction: a one-page PDF whose content stream is FlateDecode of 3 MB of `0 0 m\n`
     takes 8.8 s in `read_pdf`. A 291 KB file inflating to 200 MB was still running at 300 s and
     1.5 GB in the audit. A test still has to be written. Proposed test: `read_pdf` on such a
     file returns within a fixed bound, with no tables and `tables_truncated`.
  4. Consequence: one small source upload ties up the API's CPU and memory. The same holds for
     a Deep Research web PDF in the worker.
  5. Fix: run table extraction in a subprocess with a memory rlimit and a wall-clock kill.
     Alternatively, bound pdfminer's `zlib.decompress` and stop looking for tables on any page
     whose stream reached pypdf's limit.
  6. Test: as in 3.
- **S10. DOCX table cells repeat by `gridSpan` and `vMerge` without a bound.**
  1. Claim: python-docx's `row.cells` yields a cell once per spanned grid column. A
     `vMerge="continue"` cell yields the text of the cell above, so text multiplies by span ×
     rows.
  2. Anchor: `source_reading.py:122-126`.
  3. Reproduction: hypothesis-strength until a test exists. In the audit, a 36 KB DOCX with
     `gridSpan w:val="30000000"` ran for more than 2 minutes and used 300 MB.
  4. Consequence: API memory or CPU exhaustion from one upload.
  5. Fix: read `tr.tc_lst` directly, one segment cell per `w:tc`, with a text budget per
     document. This is the `docx/2` reader: a new name, because the reading changes for
     merged cells.
  6. Test: a DOCX with `gridSpan=30000000` is refused or read within the bound in under a
     second.
- **S11. XLSX entities expand through openpyxl.**
  **Closed by #709** (2026-10-22): every workbook member passes `refuse_dtd` before
  `load_workbook`, so no entity reaches openpyxl's expat; defusedxml is not needed for it.
  1. Claim: defusedxml is not a dependency, so openpyxl's `iterparse` expands internal
     entities.
  2. Anchor: `document_text.py:107,409` (`load_workbook`). `packages/aia_core/pyproject.toml`
     (`documents` extra) has no defusedxml.
  3. Reproduction: in the audit, a sheet with `&a0;` × 200,000 produced a 70 MB cell value
     from about 1 MB of XML. A test still has to be written.
  4. Consequence: memory exhaustion in the API (sources, attachments) and in the worker (web
     XLSX).
  5. Fix: add `defusedxml` to the `documents` extra (openpyxl uses it when it is present), or
     run `refuse_dtd` (S6) over every sheet and shared-strings part before `load_workbook`.
  6. Test: an XLSX whose shared strings declare an entity is refused `document_malformed`.
- **S12. `AIA_MAX_REQUEST_BYTES` is shown on Settings as the request ceiling, and nothing
  enforces it.**
  1. Claim: `max_request_bytes` is read only by the settings document.
  2. Anchor: `apps/api/src/aia_api/config.py:216` and `routers/settings.py:171-175`.
     `grep -rn max_request_bytes apps/api/src` finds nothing else.
  3. Reproduction: POST a 3 MB JSON body to any JSON route. It is parsed, not refused with 413.
  4. Consequence: an operator reads a guard that does not exist. S7 bounds the worst case at
     the proxy only.
  5. Fix: an ASGI middleware that refuses on Content-Length and on the streamed count, at
     `max_request_bytes` by default and at each upload route's own ceiling. Measure the
     largest working-content save first.
  6. Test: a 3 MB body to a JSON route is 413, and a 25 MiB source upload still passes.
- **S13. A web fetch has no overall deadline.**
  1. Claim: `UrllibWire.get` sets only connect (8 s) and per-read (20 s) timeouts.
  2. Anchor: `packages/aia_core/src/aia_core/infrastructure/web_retrieval_live.py:121-170`.
  3. Reproduction: hypothesis. A server that sends one byte every 19 s holds the fetch and
     its host's pacing turn for up to the 20 MB cap.
  4. Consequence: one hostile site in the search results stalls a Deep Research step.
  5. Fix: an overall deadline in the read loop, after which the fetch raises
     `ToolCallFailed(reason="timeout")`.
  6. Test: a stub wire that trickles bytes is cut at the deadline.
- **S14. An ADMIN can promote anyone to OWNER, and can demote every OWNER.**
  1. Claim: `add_member` overwrites an existing membership's role after
     `require_administer()` alone. There is no "only an OWNER sets OWNER" rule and no
     last-owner guard.
  2. Anchor: `apps/api/src/aia_api/routers/scope.py:598-626` and
     `infrastructure/scope_repository.py:208-250`.
  3. Reproduction: `POST /api/v1/members {"email": "<owner>", "role": "MEMBER"}` as an ADMIN
     demotes the owner.
  4. Consequence: today OWNER and ADMIN have the same powers (`may_administer`), so this
     mostly lets an admin lock the owner out, with one audit row as the record.
  5. Fix: needs the product owner's decision on whether OWNER is a distinct authority. If it
     is, only an OWNER grants or removes OWNER, and the last OWNER is never demoted.
  6. Test: an ADMIN's request to set or remove OWNER is 403, and so is demoting the last
     OWNER.
  Status: fixed by #782 (merged as `b6cd4d9e`, 2026-10-22) on option (b): `_guard_owner`,
  `infrastructure/scope_repository.py:343-375 @ 6bfe3760`;
  `test_scope_isolation.py::test_an_admin_neither_grants_nor_removes_owner`. OI-229.
- **S15. `deactivate_user` finds the user by id across every organization.**
  1. Claim: the lookup is `UserRow.user_id == user_id` with no membership filter, and the
     flag it sets is global.
  2. Anchor: `infrastructure/scope_repository.py:252-272`.
  3. Reproduction: no route calls it today, so this is latent. A repository test as org A's
     admin can deactivate org B's member.
  4. Consequence: none until a route exposes it. Then any admin could lock out any account,
     in every organization.
  5. Fix: require a membership in `admin.organization_id`, and decide whether deactivation is
     per membership or per account.
  6. Test: org A's admin deactivating org B's member is `ScopeDenied`.
- **S22. `clear_subject` (#704) has no route, and two things its route must settle.**
  The subject lives on the shared user record, so clearing it in one organization changes that
  person's sign-in in every organization they belong to. Decide whether clearing needs every
  organization's admin, or an operator. A mismatched bearer token also commits one
  `AIA_SESSION_DENIED` row per request (`apps/api/src/aia_api/dependencies.py`, #704), so
  repeated attempts should be deduplicated or rate-limited before the audit fills with them.
  This is a design follow-up; there is no defect to reproduce.
- **S16-S21. Hardening, each low.**
  - S16: Cognito `verify` does not require `email_verified` (`identity/cognito.py:280`). Check
    first that the federated pool maps it before requiring it.
  - S17: there is no Content-Security-Policy (`deploy/develop/Caddyfile:26-33`), while the id
    and refresh tokens sit in sessionStorage (`apps/web/src/lib/auth.ts:18,116-123`).
  - S18: worker log `fields` are merged in unredacted
    (`apps/worker/src/aia_worker/observability.py:45-47`); the API's formatter does redact
    them.
  - S19: the value patterns miss credentials in a URL's userinfo (`scheme://u:p@host`) and AWS
    `AKIA…`/`ASIA…` key ids (`infrastructure/redaction.py:33-44`;
    `apps/web/src/lib/error-tracking.ts:22-28`).
  - S20: `${{ inputs.sha }}` and `${{ inputs.migrate }}` are interpolated into `run:`
    (`.github/workflows/deploy-develop.yml:48-49`, `reference-unit.yml:44`); they should pass
    through `env:`. Third-party actions are pinned by tag rather than by SHA. `caddy:2-alpine`
    and `postgres:16-alpine` float.
  - S21: GlitchTip joins `aia-develop_internal` (`deploy/develop/errors/docker-compose.yml:59,98`)
    and can reach PostgreSQL and the API directly. Give it a network it shares only with the
    API and the worker.
- **S23. Dependabot alerts describe a branch that does not deploy.**
  1. Claim: GitHub's 113 open alerts (2 critical, 67 high) come from `main`'s two npm lockfiles,
     `apps/web/package-lock.json` (81 advisories, `next@16.1.6` the criticals) and the root
     `package-lock.json` (32; fastify, exceljs). `main` is 1,389 commits behind develop and
     nothing deploys it: `deploy-develop.yml` is dispatched only for develop's head.
  2. Anchor: `origin/main` @ `9cf1f585` against `origin/develop` @ `a0514d01`; `ci.yml`'s
     `dispatch-develop` job (`github.ref == 'refs/heads/develop'`).
  3. Reproduction: `npm audit --package-lock-only` over each lockfile (`git show <ref>:<path>`).
     The Dependabot API refuses this session's integration (403), so the counts were reproduced,
     not read: 81 + 32 = 113.
  4. Consequence: the alert count is noise for what ships, and an advisory against develop's own
     lockfiles would sit among 113 stale ones. Develop itself: `apps/web` carries only the
     allowlisted dev-only `braces` (GHSA-vfj7-8cjw-p6xm, recheck 2026-11-20) and a moderate
     `vitest`; `prototypes/research-lead-v2` carries dev-only `vite` 5 advisories in a lockfile CI
     never audits, and nothing builds or ships it.
  5. Fix: the product owner's call -- develop as the default branch, or a release to `main`;
     the prototype's `vite-plugin-singlefile` to 2.3.4 through npm, and its lockfile audited by
     the gate or excluded by name.
  6. Test: the audit gate run over every lockfile in the repository, or a named exclusion list.
- **Dev-only advisory.** pytest 8.4.2 carries PYSEC-2026-1845, fixed in 9.0.3. The dev extra
  pins `pytest>=8.3,<9` (`packages/aia_core/pyproject.toml:56`). It is not in any image, and
  CI's audit does not install dev extras. Lifting the pin is its own change.

## Doc follow-up

- `AGENTS.md`: the URL parser drops tab, CR and LF, so an open-redirect check on the raw string
  is wrong. Wrong: `!next.startsWith("//") && !next.includes("\\")`. Right: `new URL(next, HERE)`
  with a same-origin check (S1).
- `AGENTS.md`: a byte search for `<!DOCTYPE` misses UTF-16. Wrong: `b"<!DOCTYPE" in data`.
  Right: an expat pre-pass with `StartDoctypeDeclHandler` raising (`document_text.refuse_dtd`,
  S6).
- `.planning/open-items.md`: S9-S21, once they have OI numbers.
