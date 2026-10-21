# UI workbench

AIA's client-first interface (ADR 0015) on one machine, for UI work: the
client workspaces and the re-homed research stages, and a capture of every screen.
AIA needs nothing of the 18.6.6 unit here, as on develop (ADR 0018); on request the
unit runs beside it as the reference to compare a screen with, never part of AIA.
Plan: [`.planning/plans/ui-workbench.md`](../../.planning/plans/ui-workbench.md).

```bash
make ui-workbench            # start AIA, or confirm it is running; the 18.6.6 unit is not started
make ui-workbench-reference  # the same, with the 18.6.6 unit beside it at :8767 (fictional panel)
make ui-workspace            # a study's content, file, import, audience, dimensions in a browser
node tools/ui_workbench/ux_journey.mjs # after ui-fixtures + ui-research: 17 routes, four widths, result tabs, map camera, search and keyboard regression
make ui-capture              # screenshot every screen -> tmp/ui-workbench/shots/<time>/index.html
make ui-fixtures             # the fictional research projects, bound to AIA studies; prints their links
make ui-research             # one research run in a browser: Run -> Progress -> Results (needs ui-fixtures)
node tools/ui_workbench/deep_research_journey.mjs # after ui-fixtures: a Design Research run from the panel to its sealed bundle, recorded web, scripted agents, nothing paid
make ui-workbench-status
make ui-workbench-down
python3 tools/ui_workbench/workbench.py up --fresh   # also reset the API's (and the unit's) state
```

| URL | What |
|---|---|
| <http://127.0.0.1:8780/workbench/sign-in> | Sign in as the seeded operator; opens the client directory |
| <http://127.0.0.1:8780/> | 302 to `/app/clients`, as on develop |
| <http://127.0.0.1:8780/app/clients> | AIA (React, `next dev`: saves show at once) |
| <http://127.0.0.1:8780/classic> | AIA's page saying the 18.6.6 interface is gone, as on develop |
| <http://127.0.0.1:8767/> | With `make ui-workbench-reference` only: the unit, byte for byte, the reference AIA never reaches |

`make ui-workbench` starts everything but the unit: it is how the product is checked
with 18.6.6 absent. `make ui-fixtures`, `make ui-research` and `make ui-workspace`
pass on it, and the two journeys fail on any request to a path the unit served.
`make ui-workbench-reference` (`workbench.py up --with-unit`) adds the unit on a port
of its own, so that `make ui-capture` screenshots its screens beside AIA's; the
facade still routes nothing to it. `down` first to switch between the two.

Routing is read from the committed Caddyfile (`facade.py`): the web client's
matchers, `/api/v1/*` to the API, and every other path to the web client, whose own
404 answers the unit's old paths -- never to the unit, as on develop.

## What runs

| Process | What | Log |
|---|---|---|
| `unit` | with `make ui-workbench-reference` only: the vendored `ui_server.py` on a scratch copy of `app/` (`tmp/ui-workbench/unit/`), `unit_standin.py` | `tmp/ui-workbench/logs/unit.log` |
| `api` | the real `aia_api` on a scratch SQLite file (`tmp/ui-workbench/aia.sqlite`), the `local` environment's development identity, the develop seed for `workbench@example.invalid` (`api_standin.py`); no model is configured; research runs record the fictional fieldwork source (`--fieldwork synthetic_fixture`, legal only in `local`) and artifacts go to `tmp/ui-workbench/artifacts/` | `…/api.log` |
| `worker` | `python -m aia_worker` over the same SQLite file and artifact directory, with the workbench composition (`aia_executors.workbench:build_registry`, `AIA_ENV=local`): the research steps, with fictional respondents at fieldwork (ADR 0016), and the six Deep Research steps on a fictional recorded web with scripted agents (`AIA_WORKBENCH_DEEP_RESEARCH_FIXTURES=fixtures/deep_research/`: `web.json` replayed by `deep_research_recorded`, `agents.json` answered by `ScriptedDeepResearchModel`; every request id `workbench-scripted-…`, no token reported, so nothing is priced). Started once the API has created the schema | `…/worker.log` |
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
an aggregate table is shown, every map says whether its method is approved (the
Sociomap register), and no page error occurred. A revision that already has a run
is not run again: the start returns that run and the journey follows it. Screenshots go to
`tmp/ui-workbench/shots/research-<time>/`.

Every number on those screens comes from fictional respondents and says so.
**Nothing here is a finding, and nothing here is parity**; the aggregate is
compared with the unit by `packages/aia_core/tests/test_research_aggregate.py`.
What the develop host does instead -- the same run parks at fieldwork -- is in
`tools/develop_routing_proof.py`.

## The whole product as one researcher, and the reports as a reader sees them

The productization pass of 2026-10-17 (`.planning/plans/productization-coherence.md`) walked
AIA end to end this way, and anyone can repeat it, a person or an agent, on fictional data and
at no cost:

```bash
make ui-workbench && make ui-fixtures   # AIA on this machine, its fictional studies
make ui-research                        # one run: Run -> Průběh -> Výsledky
make ui-coherence                       # the walk below -> tmp/ui-workbench/coherence-journey/<time>/
make report-journey                     # the reports a run composes -> tmp/report-journey/
```

`make ui-coherence` (`coherence_journey.mjs`) opens every global page and the fixture client's
six areas; starts a new study from the client page and checks its Dimenze start with none chosen;
starts (or finds) the `persona` study's run, follows it to its results and checks that the stage
track says what Průběh says; reads Výsledky's three tabs; changes the design after the run and
checks the Run stage names the newer revision; then delivers the study and checks that every
stage says so, the design is read-only, nothing is saved, nothing starts and the report stays
downloadable, before reopening it. Every page is kept as a full-page screenshot **and its text**
(`NN-<name>.png`, `NN-<name>.txt`), so what a screen said can be read and diffed rather than
remembered; `report.json` lists each check, every API answer of 400 or more and every page error.
It fails like the other journeys on a request to a path the unit served or a 502.

`make report-journey` (`tools/report_preview.py --journey`) runs the executor journey test that
composes a run's reports (150 fictional respondents, scripted models, recorded web: no model is
called) with `tools/report_journey_capture.py` keeping every DOCX it renders, then converts each
with LibreOffice as the worker does and prints the lines of text on every page, so a chapter alone
on a near-empty page shows without opening the PDF. The PDFs and page images stay in
`tmp/report-journey/` for reading.

**Not repeated here: the AI itself.** The workbench has no model, and its fieldwork is the fixture's
invented respondents, so analysis and the internal report do not run in `make ui-coherence` (the
report card says the run makes no report). The AI runtime signs only with an EC2 instance or ECS
task role (ADR 0010, `infrastructure/model_adapters/aws_signing.py`), which a laptop or a cloud
session does not have; a paid end-to-end run happens on develop, against a fictional client, with
the same journeys pointed at it (`--facade https://aia-develop.art-chain.io` after signing in is a
next step, not built: the journeys sign in with the workbench's development identity).

None of the browser journeys runs in CI. They drift when the interface's words change (the
research journey waited for "Dokončeno" after #458 renamed the state; the client journey for
"Přidat znalost" after the intake sheet; OI-106 recorded two earlier drifts), so run them after
changing a screen's words.

## The audience step from a population

The workbench's API holds a fictional LIVE population (`fictional_population.py`: the
sampler's 3,000 invented rows on 400 invented donors, under a contract of its own, its
catalogue kept), and points the audience routes at it through the composition root's one
seam (`app.state.audience_population`, `app.state.audience_previewer`); research runs still
record the Czech LIVE, which the workbench never establishes. The first start takes about
15 s more for it; `api_standin.py --no-audience-population` leaves it out.

`make ui-audience` (`audience_journey.mjs`, needs `make ui-fixtures`) chooses ČR 18+ → narrow
on a new study, picks a region and an age from the catalogue and checks they are saved as
chosen (an empty bound left out) and read back; asks the preview and reads its count and
verdict; then picks a built-in subpanel on Special Audience and checks that one the policy
refuses cannot be chosen. It fails on a request to a path the unit served, a 502 or a page
error. Screenshots go to `tmp/ui-workbench/shots/audience-<time>/`. Every count is of
fictional rows.

## Requirements

Python 3.11+ (the unit's runtime requirements go into `tmp/ui-workbench/venv`,
through `uv` when present), Node 22 with `apps/web`'s modules, and for the
capture, Playwright with a Chromium it can launch (resolved from the
environment; it is not a repository dependency).
