# NPC Panel 18.6.6 — extracted product

**Generated. Do not edit files under `app/` by hand.** Regenerate with
`AIA-reference/tools/extract_legacy.py`; every file in `app/` is byte-identical
to the audited 18.6.6 archive (`app-manifest.json` carries the hashes).

| | |
| --- | --- |
| Source archive | `86b70bfb5c1b4a7984b392cc6187c0842edc5cd28d37d2dd72dcf15d58d53216` |
| Policy | `extraction-policy.json` v1 (`f1b713cee999ba15`) |
| Extracted | 2026-09-23T15:21:57Z |
| `app/` | 924 files, 10.2 MB |
| Data (mounted, not in Git) | 245 files, 54.5 MB — `data-manifest.json` |
| Client material excluded | 69 files |
| Debris left in the archive | 327 files |

## What this is

The UI and logic of the working prototype, unchanged, packaged so AIA's
infrastructure can run it as one service. It is the day-one baseline the
production rebuild reproduces, and the live oracle its parity tests compare
against. See `AIA-INTEGRATION.md` for the compose service, the Caddy site and
the guard exemptions this needs.

## Running

```bash
docker build -t aia-legacy-panel:local .
docker run --rm -p 127.0.0.1:8765:8765 \
  -v /path/to/legacy-data:/data:ro -v npc-state:/app aia-legacy-panel:local
open http://localhost:8765/
```

`/data` holds the files listed in `data-manifest.json` at their relative paths
(produce it with `extract_legacy.py --data-out`, then keep it in EU object
storage). At start the supervisor copies the baked tree into `/app`, hydrates
the data files into it with hash verification, verifies the 22 runtime assets,
then starts the worker and the server exactly as the original launcher did.

Without `/data` the container refuses to start and lists what is missing.
