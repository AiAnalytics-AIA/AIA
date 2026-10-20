# The MVP cohesion traces (2026-10-19)

Five read-only audits of how AIA's functions connect, written for `mvp-master-plan.md` §5-§7. Each
follows one group of capabilities down and back up the stack (screen, route, service, rule, table,
worker, external call, artifact, back to the screen and the Lead's context) and gives one line per link:
**EXISTS** (anchor), **PARTIAL**, **MISSING** (with the plan chunk that builds it, or NONE) or
**CONTRADICTION** (both sides quoted). Each ends with three lists: gaps with no plan, contradictions,
and interfaces between plans or sessions with no owner.

| File | Group | Links | EXISTS / PARTIAL / MISSING / CONTRADICTION |
|---|---|---|---|
| `trace-1-design.md` | Brief, Design, Questionnaire; the working copy, proposals, two researchers | 99 | 30 / 27 / 29 / 13 |
| `trace-2-sample-execution.md` | Audience, Dimensions, Sample, Fieldwork; population, runs, budget, recovery | 109 | 48 / 21 / 26 / 11 |
| `trace-3-evidence.md` | Results, Sociomap, Analysis, Report; admission, maps, approval and export | 98 | 35 / 16 / 37 / 10 |
| `trace-4-lead-governance.md` | The Lead, orchestration, the ledger, models and route classes, Settings | ~100 | 43 / 10 / 34 / 15 |
| `trace-5-deepresearch-data-infra.md` | Deep Research, client data, AWS, deploy, CI, the harness, the delete path | 123 | 44 / 18 / 40 / 21 |

## What they are, and are not

- **A model-made audit, not a proof.** Each was written by a read-only subagent that opened the code and
  cited `file:line @ SHA` for what it opened and marked the rest ◇. Anchors are at `f7e80bb9` or
  `82be9e03` (the branch head when each ran); the only commit between them adds a plan file, so the code
  anchors hold at both. Nothing was run: no tests, no workbench, no develop host.
- **What the live host holds is unknown.** Develop's switches live in SSM
  (`deploy/develop/bin/write-env.sh:20-37`); "what is on today" is ◇ in every trace that touches it.
- **Spot-checked.** Eight of the findings that contradicted earlier statements in the plans were opened
  against the code before this directory was written, and all eight held: connectors run only under
  `AIA_DEEP_RESEARCH_AGENT_DIRECTED` (default false, `docker-compose.yml:102`); the procurement connector
  has no live source (`deep_research_live.py:364-366`); `SiteCrawl` has no caller outside its test; a
  CLASSIFIED client's Deep Research run fails whole (`plan.py:166-174`); a retry re-pins the current
  settings (`application/deep_research.py:617`); Settings is read-only (`routers/settings.py`); the spend
  limit is a confirmation threshold, `None` meaning never (`application/research.py:452-454`); and an
  accepted proposal is refused when the head moved before its items are compared
  (`proposal_accept.py:117-118`). The rest are the auditors' claims; a person can reproduce each with one
  `git show <sha>:<path>`.
- **They disagree with parts of the plans, on purpose.** Where a plan says one thing and the code
  another, the trace says so and quotes both. The plans are not corrected by these files: the
  consolidated registers in `mvp-master-plan.md` §5 and §6 are, and each gap becomes a chunk in its
  plan (master-plan chunk 2).

A finding is closed by changing its plan or its code and then by re-running the same trace question, not
by editing these files.
