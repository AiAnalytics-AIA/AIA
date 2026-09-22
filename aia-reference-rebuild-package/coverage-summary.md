# Coverage summary

**Evidence mode: MANIFEST.** Counts of files are established. Counts of
*capabilities*, *routes*, *methodology items* and *lines of code* are not, because
they require contents.

There is deliberately **no "percent migrated" figure** in this document. File
count is not product completeness: one 50-line threshold module can carry more
product methodology than a 600-file demo library.

## Reference size

| Measure | Value | Source |
|---|---|---|
| Canonical files | **1324** | manifest |
| Python files | **266** | manifest |
| — application source | 184 | classified by path |
| — tests | 65 | classified by path |
| — tooling | 17 | classified by path |
| Frontend HTML | **76** | manifest |
| Frontend JavaScript (separate files) | **0** | manifest |
| CSS files | **0** | manifest |
| Methodology / policy files | **82** | classified by name |
| CSV data assets | 154 | manifest |
| Compressed (.gz) data assets | 22 | manifest |
| Documentation (.md) | 216 | manifest |
| Launchers (.bat/.sh/.ps1) | 25 | manifest |
| Python LOC | **UNKNOWN** | needs tree |
| Total size on disk | **UNKNOWN** | needs tree |
| API routes | **UNKNOWN** | needs tree |

**Zero standalone `.js` and zero `.css` files against 76 `.html` files** is itself a
finding: the prototype's frontend behaviour is inline in its HTML. The UI capability
ledger must therefore be derived from the HTML documents themselves, not from a
script directory — and 74 of those 76 live under `demo_library/`, so only 2 HTML
files sit in the application zones.

## Files by zone

| Zone | Files |
|---|---|
| `demo_library` | 622 |
| `(root)` | 379 |
| `docs` | 178 |
| `tests` | 64 |
| `audit_reference` | 28 |
| `SPECIAL_PANELS` | 18 |
| `campaign` | 9 |
| `npc_ingest` | 9 |
| `examples` | 6 |
| `_npc_update_backup` | 5 |
| `npc_tools` | 5 |
| `tools` | 1 |

## Files by type

| Category | Files |
|---|---|
| json_data_or_config | 438 |
| documentation | 216 |
| python_application_source | 184 |
| csv_data_asset | 154 |
| methodology_or_policy | 82 |
| frontend_html | 76 |
| python_test | 65 |
| text | 43 |
| launcher_script | 25 |
| compressed_data_asset | 22 |
| python_tooling | 17 |
| packaging | 1 |
| sql | 1 |

## Disposition counts

| Disposition | Count |
|---|---|
| PORTED | 0 |
| REIMPLEMENTED | 0 |
| REPLACED | 0 |
| DEFERRED | 0 |
| DATA_ASSET | 0 |
| TEST_CHARACTERIZATION | 65 |
| TOOLING_ONLY | 0 |
| SUPERSEDED_LEGACY | 0 |
| INTENTIONALLY_RETIRED | 0 |
| UNKNOWN_NEEDS_DECISION | 1259 |

**1259 of 1324 files are UNKNOWN_NEEDS_DECISION.**

Only `TEST_CHARACTERIZATION` could be assigned without contents, and only because a
file under `tests/` is a test whatever it turns out to test. Every other disposition
is a claim about behaviour and was not guessed.

## Capability coverage

**0 of an unknown total.** The capability map is not built, so capability-level
coverage cannot be reported — and an invented denominator would be worse than none.

## Verifier result

`tools/verify_reference_inventory.py`: **8 checks pass, 2 skipped** (C8 capability-map
references — no map yet; C10 tree hashes — no tree). No check failed.

The verifier reports the UNKNOWN count prominently and states that the audit is not
complete while any record carries it. It is designed to keep failing that way until
the work is genuinely done.
