# UI workbench

AIA's client-first interface (ADR 0015) on one machine, for UI work: the
client workspaces and the re-homed research stages, with the 18.6.6 unit beside
them as the reference to compare a screen with (never part of AIA, ADR 0018), and
a capture of every screen. Plan:
[`.planning/plans/ui-workbench.md`](../../.planning/plans/ui-workbench.md).

```bash
make ui-workbench          # start, or confirm running
make ui-workbench-aia      # AIA alone: the 18.6.6 unit not started, its paths answer 502 (ADR 0018)
make ui-workspace          # on AIA alone: a study's content, file, import, audience, dimensions
make ui-capture            # screenshot every screen -> tmp/ui-workbench/shots/<time>/index.html
make ui-fixtures           # the fictional research projects, bound to AIA studies; prints their links
make ui-research           # one research run in a browser: Run -> Progress -> Results (needs ui-fixtures)
make ui-workbench-status
make ui-workbench-down
python3 tools/ui_workbench/workbench.py up --fresh   # also reset the unit's and the API's state
```

| URL | What |
|---|---|
| <http://127.0.0.1:8780/workbench/sign-in> | Sign in as the seeded operator; opens the client directory |
| <http://127.0.0.1:8780/> | 302 to `/app/clients`, as on develop |
| <http://127.0.0.1:8780/app/clients> | AIA (React, `next dev`: saves show at once) |
| <http://127.0.0.1:8780/classic> | AIA's page saying the 18.6.6 interface is gone, as on develop |
| <http://127.0.0.1:8767/> | The unit, byte for byte: the reference, which AIA never reaches |

`make ui-workbench-aia` (`workbench.py up --no-unit`) starts everything but the unit
and points the facade's unit upstream at a closed port, so a request that still
reaches for the unit answers 502 instead of quietly succeeding. It is how the
product is checked with 18.6.6 stopped: `make ui-fixtures`, `make ui-research` and
`make ui-workspace` all pass on it, and the two journeys fail on any request to a
path the unit serves. `down` first to switch between the two modes.

Routing is read from the committed Caddyfile (`facade.py`): the web client's
matchers, the unit's `@unit` paths, `/api/v1/*` to the API, and every other
path to the web client -- never to the unit, as on develop.

## What runs

| Process | What | Log |
|---|---|---|
| `unit` | the vendored `ui_server.py` on a scratch copy of `app/` (`tmp/ui-workbench/unit/`), `unit_standin.py` | `tmp/ui-workbench/logs/unit.log` |
| `api` | the real `aia_api` on a scratch SQLite file (`tmp/ui-workbench/aia.sqlite`), the `local` environment's development identity, the develop seed for `workbench@example.invalid` (`api_standin.py`); no model is configured; research runs record the fictional fieldwork source (`--fieldwork synthetic_fixture`, legal only in `local`) and artifacts go to `tmp/ui-workbench/artifacts/` | `…/api.log` |
| `worker` | `python -m aia_worker` over the same SQLite file and artifact directory, with the workbench composition (`aia_executors.workbench:build_registry`, `AIA_ENV=local`): the research steps, with fictional respondents at fieldwork (ADR 0016). Started once the API has created the schema | `…/worker.log` |
| `web` | `next dev` for `apps/web` | `…/web.log` |
| `facade` | one origin, routed like the develop Caddyfile minus the gates (`facade.py`) | `…/facade.log` |

The API needs the repository's Python environment (`make setup`): `make
ui-workbench` passes it as `AIA_API_PYTHON`. The sign-in page puts the
operator's e-mail into the tab's session as the bearer credential; the
development identity provider trusts that only in the `local` environment and
refuses to exist anywhere else. The seed gives the operator the synthetic
client and the two fictional clients (Horizont Mobility, Lumen pojišťovna), each
with studies, knowledge and one pending proposal.

## The fictional panel

The population panel is licence-bound and is not in this repository. The unit
runs on a 60-row frame whose every respondent is `FIKTIVNI-###` in a
`Fiktivní kraj`; column names come from the unit's own code and labels, every
value is invented. **Nothing it shows is data, and it is never used for parity**
— that is `tools/legacy_oracle.py` against the running unit (ADR 0011). Screens
that need the real panel show their empty states. The DEMO library ships in
`app/` and fills the project screens.

## No AI, ever

The workbench never reaches a model, even on a machine with a signed-in Claude
Code CLI or an API key (an agent session has both). `unit_standin.py` switches
every provider off three ways: the scratch copy's `BUILD_EDITION.json`, which
every part of the unit reads; provider credentials and the CLI's directory
removed from the unit's environment; and the unit's CLI lookup finding nothing.
The unit's own AI jobs have no worker, so an AI step started on one of the
unit's screens stays queued until it is cancelled. AIA's worker runs the research
steps (compile, preflight, fieldwork, aggregate, Sociomap), none of which calls a
model; at fieldwork it uses fictional respondents instead of the AI runtime, which
is not configured here. An AI step started in an AIA stage is a job of the study;
the research agents are not configured either, so the job parks (`WAITING_PROVIDER`,
`ai_runtime_unavailable`) and the stage shows the step's message ("AI návrhy
výzkumu nejsou zapnuté. Zadání zůstává uložené."). Screens that show an AI answer
are seen from fixture projects.

## Fixture research projects

The workbench never calls a model, so a research step that shows an AI answer
(the plan's understanding, a built questionnaire, a proposed audience) is seen
from a study that already holds one. `make ui-fixtures`
(`fixture_project.py`) makes a research study of Horizont Mobility for each
(`POST /api/v1/clients/<client>/studies`) and saves the fixture as its working
content through AIA's own route, `PUT /api/v1/studies/<study>/workspace/content`,
over the template AIA serves (ADR 0018). Nothing reaches the unit. The studies are
kept in `tmp/ui-workbench/studies.json`, so a second run saves a new revision of
the same studies.
Every word is written in the script and fictional. The projects grow as the
research chunks land ([research-flow-rehome.md](../../.planning/plans/research-flow-rehome.md)):

| Key | Holds | For |
|---|---|---|
| `empty` | nothing but a title | Zadání as a new project sees it |
| `planned` | brief + the plan's analysis (two comparable sets, questions for the user, three design variants) | Zadání, Návrh |
| `questionnaire` | the `planned` project with a question block (every question type) and a tracked set, on the editor | Dotazník |
| `audience` | the `questionnaire` project on the ČR 18+ branch, narrowed by a region and an age range | Audience |
| `persona` | the `questionnaire` project with three catalogue dimensions, one requested dimension and N=450 | Dimenze; Kontrola & spuštění, Průběh, Výsledky (it passes AIA's readiness) |

A ledger screen in `docs/migration/interface-screens.json` that names a
`fixture` is captured a second time on that project: the AIA screen at its
`react_path` with the fixture's study for `<id>` and its client for `<client>`
(`<screen>@<fixture>` in the contact sheet). Every AIA screen of the ledger's
`aia_screens` is captured too, under the same client. The unit's own screens are
captured bare, as shipped, only when the workbench runs it.

## A research run, end to end

`make ui-research` (`research_journey.mjs`) signs in as the operator, opens the
`persona` study's Run stage, where the design is submitted as a Design Revision
and AIA's readiness is shown; starts one run; follows it on Progress until the
worker has finished all five steps; and reads Results. It fails unless the
fictional-data notice is on Progress and Results, every step is `SUCCEEDED`,
an aggregate table is shown, the Sociomap is labelled INTERNAL_ONLY (PROGRESS
D6), and no page error occurred. Screenshots go to
`tmp/ui-workbench/shots/research-<time>/`.

Every number on those screens comes from fictional respondents and says so.
**Nothing here is a finding, and nothing here is parity**; the aggregate is
compared with the unit by `packages/aia_core/tests/test_research_aggregate.py`.
What the develop host does instead -- the same run parks at fieldwork -- is in
`tools/develop_routing_proof.py`.

## Requirements

Python 3.11+ (the unit's runtime requirements go into `tmp/ui-workbench/venv`,
through `uv` when present), Node 22 with `apps/web`'s modules, and for the
capture, Playwright with a Chromium it can launch (resolved from the
environment; it is not a repository dependency).
