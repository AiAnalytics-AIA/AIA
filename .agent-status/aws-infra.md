# aws-infra

**STATUS: WAITING ON NIGEL. The report editor (ONLYOFFICE) is ready to activate; it needs his own word in this session.**
Session `session_01LBR1SyjXK8uYR5VdBjGAEJ` ("AIA infra audit"): AWS develop, account 311141567391,
eu-central-1, host `i-07159210266481227` (t3a.large since 2026-10-22), Terraform root `infra/develop`,
IAM user `aia-claude-infra`. Updated 2026-10-23 07:40 UTC. Every fact below was observed, not
assumed.

## Standing rules this session works under

- An AWS or Terraform write needs **Nigel's own word typed in this session**, plus the coordinator's
  approval. A relay through another session is not enough.
- A commit or push needs Nigel's word for that change or branch (CLAUDE.md §5). Hooks don't count.
- Do not affect `makli-bedrock`'s Bedrock usage. Never print the tfvars or any secret.
- This IAM user cannot do `ssm:SendCommand`, `StartSession`, `ssm:DeleteParameter`, or
  `PutParameter` on `/aia/terraform/*`, `/aia/develop/postgres_password`, `/aia/develop/glitchtip_*`
  or the Brave key. It can do `PutParameter` on the other `/aia/develop/*` parameters, Route 53 changes
  in the develop zones, and tagged EC2 modify, stop and start.

## Done (merged)

- #785: ONLYOFFICE hosting, chunks 1-3 (Compose project, the `docs.` site, the docs gate).
- #794: the deploy bundle of an older SHA.
- #829 (merged 2026-10-23 01:37, `08e97b6c`):
  - 3b: a timed force-save every 5 minutes through `deploy/develop/docs/local-production-linux.json`,
    never `local.json`;
  - 4a: the deploy stops the editor when it is switched off; `bin/smoke-docs.sh` rows; `docs.sh`
    works without the secret;
  - the signed `/cache/files/` route without the gate, and logs that drop `md5`, `expires` and the
    ticket.
- Plan `.planning/plans/report-editor-hosting.md`: 5 of 6 chunks done. Chunk 4, activation, is open,
  and its section "Activation on develop (chunk 4): the plan" holds every command and check.
- Preconditions met:
  - F1 `__Host-aia_session`: #831 merged at 01:15 (`ca14a942`);
  - the secret: `/aia/develop/aia_onlyoffice_jwt_secret` exists, SecureString v1, created
    2026-10-23 00:13. Nigel ran the CloudShell command. Checked by name only.
- Reviewed #839 (SB4): the wiring is right. Both requested fixes were merged in, per the coordinator
  (03:40).

## Open decision (Nigel, in this session): which design to activate

Nigel answered in the Zpráva session at about 00:15 (relayed, so not yet confirmed here):
- the editor moves to a registrable domain of its own, not yet named;
- the docs cookie gate goes, and ONLYOFFICE's own JWT protects the editor.

- **If he confirms**, write a hosting PR first. It is the gate's removal, done once:
  - **Caddy:** the editor's site under the new name, no `forward_auth`; keep the `@server_only` 404,
    the `frame-ancestors` CSP and the log filters.
  - **`tools/caddy_routes.py` and its tests:** drop the gate rules; the cache route is absorbed.
  - **`smoke-docs.sh`:** drop the gate rows (`/` 401, `/__aia/session`), keep the server-path 404 and
    forged-link 403 rows.
  - **API:** remove `docs_pass`, the three `/session/docs*` routes and `/__aia/session`. Zpráva left
    them in place for this.
  - **Terraform:** the new domain's zone or record (who registers it?), then the activation steps
    rewritten for that name.
- **If he keeps `docs.aia-develop.art-chain.io`**, the plan's chunk 4 applies as written.

## Activation, once decided (plan chunk 4, every step with its check)

1. **Terraform** from a clean develop worktree, with `TF_DATA_DIR` and the tfvars from SSM
   `/aia/terraform/develop/tfvars` (decrypted to a temp dir, deleted after):
   - import `errors[0]` first:
     `terraform import 'aws_route53_record.errors[0]' Z0491946PNRJDOXB1EWV_errors.aia-develop.art-chain.io_A`;
   - then `plan -target='aws_route53_record.docs[0]'` (or the new domain's record) and show it to
     Nigel. **Stop if the plan shows anything beyond that one record.**
2. **SSM** (String parameters, allowed for this user):
   - `aia_onlyoffice_url` = `https://docs.aia-develop.art-chain.io`, or the new origin;
   - `aia_onlyoffice_enabled` = `true`.
3. **Deploy:** the next merge, or dispatch "Deploy develop". Watch for:
   - "the Document Server is up";
   - the `docs:` smoke rows `ok`;
   - "Confirm from outside" with the SHA.
4. **Verify:** RPT8's round trip on a fictional run (the Zpráva session). Watch CloudWatch memory and
   disk for the first hour.
5. **Rollback:** set `aia_onlyoffice_enabled` to `false`, then deploy. Deleting a parameter is
   Nigel's job; this user is denied it.

## Other open items (not blocking)

- `dev.ai-analytics.ai` cutover: paused by Nigel. The .ai registry still delegates to Webglobe.
- Docs PR for the Doc follow-ups of #785 and #829: not opened (docs sessions own it).
- Develop CI Backend takes about 1 h 40 min; the SQLite domain step alone is about 42 min. Worth a fix
  of its own.

## Tools in this container (lost when it is reclaimed)

Terraform 1.10.5 and AWS CLI v1 sit under the session scratchpad (`tools/`). A new session
reinstalls them, pinned to `infra/develop`'s required version.
