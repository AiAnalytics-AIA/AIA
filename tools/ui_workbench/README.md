# UI workbench

The real 18.6.6 interface and AIA's web client on one machine, for UI work: the
classic screens with the AIA skin (ADR 0013), the React screens that replace
them (ADR 0014), and a capture of every screen. Plan:
[`.planning/plans/ui-workbench.md`](../../.planning/plans/ui-workbench.md).

```bash
make ui-workbench          # start, or confirm running
make ui-capture            # screenshot every screen -> tmp/ui-workbench/shots/<time>/index.html
make ui-workbench-status
make ui-workbench-down
python3 tools/ui_workbench/workbench.py up --fresh   # also reset the unit's state
```

| URL | What |
|---|---|
| <http://127.0.0.1:8780/> | The classic interface as develop serves it after sign-in: skinned |
| <http://127.0.0.1:8780/app> | The rebuilt interface (React, `next dev`: saves show at once) |
| <http://127.0.0.1:8767/> | The same unit, bare, byte for byte |

## What runs

| Process | What | Log |
|---|---|---|
| `unit` | the vendored `ui_server.py` on a scratch copy of `app/` (`tmp/ui-workbench/unit/`), `unit_standin.py` | `tmp/ui-workbench/logs/unit.log` |
| `web` | `next dev` for `apps/web`, skin and re-home switched on | `…/web.log` |
| `skin` | `build-skin.mjs --watch`: `skin.css` rebuilt on every save of `src/skin/*` or `tokens.json` | `…/skin.log` |
| `facade` | one origin, routed like the develop Caddyfile minus the gate (`facade.py`) | `…/facade.log` |

## The fictional panel

The population panel is licence-bound and is not in this repository. The unit
runs on a 60-row frame whose every respondent is `FIKTIVNI-###` in a
`Fiktivní kraj`; column names come from the unit's own code and labels, every
value is invented. **Nothing it shows is data, and it is never used for parity**
— that is `tools/legacy_oracle.py` against the running unit (ADR 0011). Screens
that need the real panel show their empty states. The DEMO library ships in
`app/` and fills the project screens.

## Requirements

Python 3.11+ (the unit's runtime requirements go into `tmp/ui-workbench/venv`,
through `uv` when present), Node 22 with `apps/web`'s modules, and for the
capture, Playwright with a Chromium it can launch (resolved from the
environment; it is not a repository dependency).
