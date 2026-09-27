# `legacy/` — the vendored NPC Panel 18.6.6 product

Decision: [ADR 0011](../docs/architecture/adr/0011-vendor-legacy-product-unit.md).

`npc-panel-18.6.6/` is **generated**. It is produced from the audited archive by
`AiAnalytics-AIA/AIA-reference/tools/extract_legacy.py`, and every file under its
`app/` is byte-identical to that archive (`app-manifest.json` carries the hashes).
Nothing under it is edited by hand: a change to what it contains is a change to
the extraction policy in the reference repository.

```bash
# in a checkout of AiAnalytics-AIA/AIA-reference, with the archive at hand
python3 tools/extract_legacy.py \
    --source "/path/to/NPC_PANEL_18.6.6_CURRENT_DEMOS_UPDATED_GEMO_REPUTACNI_SCENARE_2026-09-11_FULL (1).zip" \
    --dest  /path/to/AIA/legacy/npc-panel-18.6.6 \
    --data-out /path/to/legacy-data
```

The first command writes the unit here; the second output, the data bundle, is
uploaded once to the EU ops bucket (`deploy/develop/env.example`,
`AIA_LEGACY_DATA_PREFIX`) and never committed.

What the unit is for, how it is deployed and what it does not do are in its own
`README.md` and `AIA-INTEGRATION.md`, and in ADR 0011.
