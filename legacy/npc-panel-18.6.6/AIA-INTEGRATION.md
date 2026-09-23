# Integrating the extracted unit into AiAnalytics-AIA/AIA

Target layout: `legacy/npc-panel-18.6.6/` in the AIA repository, built as a
fifth image `aia-legacy-panel` next to `aia-api`, `aia-worker` and `aia-web`,
and published by Caddy on its **own hostname**. The reference UI calls
absolute paths (`/api/...`, `/health`, `/brand/`) that collide with AIA's
`/api/*`, so a path prefix on the main hostname is not an option.

## 1. `deploy/develop/docker-compose.yml` — add the service

```yaml
  legacy-panel:
    image: ${AIA_IMAGE_REGISTRY}/aia-legacy-panel:${AIA_IMAGE_TAG}
    restart: unless-stopped
    environment:
      NPC_VERIFY: strict
      NPC_START_WORKER: "1"
      # Provider credentials only if live AI runs are wanted on the baseline.
      # ANTHROPIC_API_KEY: ${LEGACY_ANTHROPIC_API_KEY:-}
    expose: ["8765"]
    volumes:
      - legacy_state:/app
      - /opt/aia/develop/legacy-data:/data:ro
    networks: [internal]
    security_opt: ["no-new-privileges:true"]
    stop_grace_period: 30s
    logging: *logging
```

and `legacy_state:` under `volumes:`. The working tree is written at runtime
(SQLite state, logs, runs), so this service is **not** `read_only`.

## 2. `deploy/develop/Caddyfile` — a second site

```
{$AIA_LEGACY_HOSTNAME} {
	encode zstd gzip
	# The reference API has NO authentication of its own (AIA-reference
	# high-risk-behaviors.md R14). Never publish it without a gate.
	basic_auth {
		{$AIA_LEGACY_BASIC_USER} {$AIA_LEGACY_BASIC_HASH}
	}
	reverse_proxy legacy-panel:8765
	log {
		output stdout
		format json
	}
}
```

`AIA_LEGACY_HOSTNAME`, `AIA_LEGACY_BASIC_USER` and `AIA_LEGACY_BASIC_HASH`
(`caddy hash-password`) go into `env.example` and SSM like the other values.
The container's own relay rewrites `Host`/`Origin` for the reference's origin
guard, so Caddy needs no header rewriting. Forward-auth to Cognito can replace
`basic_auth` later; a gate of some kind is not optional.

## 3. `.github/workflows/deploy-develop.yml` — build the image

```yaml
      - name: Build and push aia-legacy-panel
        uses: docker/build-push-action@v6
        with:
          context: legacy/npc-panel-18.6.6
          push: true
          tags: |
            ${{ env.REGISTRY }}/aia-legacy-panel:${{ env.SHA }}
            ${{ env.REGISTRY }}/aia-legacy-panel:develop
          build-args: |
            AIA_BUILD_SHA=${{ env.SHA }}
          cache-from: type=gha,scope=legacy
          cache-to: type=gha,scope=legacy,mode=max
          provenance: false
```

and `legacy-panel` in `bin/deploy.sh`'s `compose pull` list.

## 4. The data bundle

`extract_legacy.py --data-out <dir>` writes every `data-manifest.json` file
at its relative path. Upload it once to the EU ops bucket and sync it onto
the host before the service starts:

```bash
aws s3 sync <dir> s3://$AIA_OPS_BUCKET/legacy-data/86b70bfb5c1b/ --only-show-errors
# on the host, in bin/deploy.sh before `compose up`:
aws s3 sync "s3://$AIA_OPS_BUCKET/legacy-data/86b70bfb5c1b/" /opt/aia/develop/legacy-data --only-show-errors
```

The population panels derive from PIAAC 2023 CZ / ISSP 2022 CZ microdata
(open decision D3). They stay in EU object storage; they never enter Git or an
image. The container verifies every hydrated file's hash before starting.

## 5. AIA's guards — three deliberate, named exemptions

These guards were written for the earlier strategy (clean-room rebuild, no
prototype code in the repository). Vendoring the working product is a decided
change of strategy; record it in the rules rather than working around them.

**`.gitignore`**: nothing to change (`legacy_reference/` and
`npc-panel-reference/` stay ignored; this unit lives at `legacy/npc-panel-18.6.6/`).

**`tools/exposure_check.sh`**: exempt the unit's path from rules **2a**
(`npc[-_]panel` in a path), **2b** (content hash equals a reference file — every
file in `app/` does, by design), **2c** (dataset nouns in csv/json names — the
reference's config files carry them) and, in rule **3**, the four *fictional*
demo-brand tokens `STREAMIO|AURORA|NEXORA|RAILMOVE` (publication-safety-report.md
Result 3 records them as invented). Keep `GEMO` and `MMC_GEMO` enforced on
**paths** everywhere including this unit: the extraction guarantees no path in
`app/` carries them. Their **content** rule is different: the reference code
refers to its own canonical demos by identifier (`demo_showcase.py`, a browser
smoke test, a shipped sums file, …), and the extraction does not edit code.
`exposure-report.json` lists every such file with a hit count. The data owner
either accepts those identifiers in a private repository (then exempt the
unit's path from the content rule) or names the files to drop from the policy.

Suggested shape, matching the script's own convention of naming exemptions in
the rule:

```bash
LEGACY_UNIT='^legacy/npc-panel-18\.6\.6/'
# 2a / 2b / 2c: add  | grep -Ev "$LEGACY_UNIT"  after the first `git ls-files`
# 3, names and contents: split CLIENT_TOKENS into REAL='GEMO|MMC_GEMO' (all
#    paths) and FICTIONAL='STREAMIO|AURORA|NEXORA|RAILMOVE' (all paths except
#    $LEGACY_UNIT)
```

**`ARCHITECTURE.md` §2**: add a row `— | Legacy unit | legacy/npc-panel-18.6.6/ |
Frozen extraction of 18.6.6; the baseline and parity oracle. Receives no
edits. | Nothing.` so the layer table says what the directory is. `layer_check`,
`ruff`, `mypy` and `pytest` already scan only `packages/`, `apps/` and
`migrations/`, so the unit is outside every code-quality gate by construction.

## 6. What it does not solve

- Live AI runs need a provider credential and, for the edition's default
  provider, the Claude Code subscription runtime. The baseline runs everything
  deterministic without either.
- The unit is single-tenant and unauthenticated by design. It is a baseline
  and an oracle behind a gate, not a product surface.
