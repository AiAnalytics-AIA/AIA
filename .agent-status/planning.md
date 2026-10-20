# planning — AIA planning session (master plan, decisions, docs PRs)

Current state, rewritten each update. Observed state only. No secrets.
Updated: 2026-10-20 ~15:50 UTC by session_01RxUnHwTXGVFYjwzfpKi9kT ("AIA planning 2"), which took
over from session_01Y7frLAETBEYvez3sW7FbGF (retired at ~70% context). Works under the PM coordinator
(session_019bYPVpsShVq3LCtWDT5Kr8, `.agent-status/pm-coordinator.md`); Nigel also talks to this
session directly.

## Role
Planner/worker for the MVP plan: puts open decisions to Nigel interactively (one card per question,
**each with a worked example**: he asks for "context with an example" when a question is abstract),
records his answers in the plan files, writes docs-only PRs for doc follow-ups, cross-checks plans
against the code. It does **not** start sessions or workflows (the coordinator does) and does **not**
merge (the coordinator merges reviewed green PRs; Nigel merges when he says so).

## Open PRs this session owns
| PR | Branch | Head | State | Left |
|---|---|---|---|---|
| #511 | `chore/wallet-rename` | `8fb59523` | draft, CI running at handoff (docs/migration touched, so the full suites run, ~35 min) | the money "envelope" renamed "wallet" (Czech UI "Peněženka", Nigel 2026-10-20) across 12 plan/acceptance files + `parity-matrix.json` AC-02/AC-04; recorded in `lead-orchestration#LO0` and master §11.1. Keep green; coordinator reviews and merges. **Doc follow-up in its body:** `overview.md` MVP-13 still says "a per-study envelope" (shared file, not edited) |

Subscribed to PR activity on #511: session_01RxUnHwTXGVFYjwzfpKi9kT (planning 2), 15:50 UTC. CI at that
time: backend + frontend running, every other check green.

## Scope freeze (Nigel, 2026-10-20 ~15:25 UTC)
No feature code until Nigel signs a dated scope baseline in mvp-master-plan.md. Inputs from sessions
1a (crosscheck-tracks-5-7.md), 1b (reverse-scope-audit.md), 1c (client-and-settings-impact.md), 2
(mvp-methodology-packet.md, #510), 3 (Proposed ADRs 0028+), each a docs-only draft PR with "Proposed
master-plan edits". **Step 4 is this session's, when the coordinator asks:** apply the accepted
proposals and write the baseline (in / out / open decisions) for Nigel to sign. Until then
mvp-master-plan.md is not edited except by #511. Decided: the MVP ships `aia-sociomap-5` (MVPQ-13 in #510).

## Merged today from this session
#508 (doc follow-ups of #499-#507, OI-135..138, `signed-off-sociomap-method` registered; plus 2fa78b50 for Codex's three findings), merged by the coordinator as 86ec0cdd. Earlier: #491, #493, #494, #495 (2026-10-19); #506 (owner answers MVPQ-03/05/06/07/08/09 into packet,
cohesion register, master §11, child plans and AC-02/09/13; carried #503), #507 (cross-check
dispositions G47-G57 + 5 corrections + X1/X8/X10 answers).

## Commitments to Nigel not yet done
- None outstanding beyond keeping the open PRs above green and handled through review.
- Standing: when he asks for decisions, ask interactively with a worked example per question.

## Owner questions still open (as of develop @ 86ec0cdd)
Index: `.planning/plans/mvp-master-plan.md` §11.4; wording: `.planning/mvp-owner-decisions.md`;
answers recorded in `.planning/mvp-cohesion.md` (dated entries at the end).
- **MVPQ-03 (rest)**, methodology owner: segment combinations, support, own dimensions, clustering,
  register entry; reconcile `segment-maps-and-drilldown` 1/9/10 and `sociomap-formula-corrections#3`
  with `aia-sociomap-5` (#504, merged) before building.
- **MVPQ-05 (rest)**, methodology owner: benchmark interval; whether a client survey may ground AI
  respondents; and ADR 0027 **Q4** (a client number's support/metric/interval, master G51,
  `client-data-in-analysis#0`).
- **MVPQ-06 (rest)**, Nigel: Deep Research evaluation tasks, metrics and thresholds (25, 26, 39);
  he owns them, USD 50 allowance.
- **MVPQ-09 (rest)**, methodology owner: any scientific check beyond admitted support.
- **MVPQ-10**, methodology owner: replacement weights and support (`run-qc-and-checkpoint#RQC5`).
- **MVPQ-12**, methodology owner: canonical Sociomap Q5/Q6/Q7, kernel widths, F10, F16.
- **MVPQ-02b**, methodology owner: the open-answer coding method.
- Scope overrides on offer (master §11.3): S2 one meter vs two, S3 shared Lead conversation, S4 strict
  class text for every client, S5 client DOCX only. Not asked; only if Nigel wants them.
The methodology owner is A. Bahbouh (GitHub `Arigamaru`), working in his own AIA sessions (#504).

## Decisions recorded today (don't re-ask)
MVPQ-01, 02, 04, 11 (earlier sessions); MVPQ-03/05/06/09 product parts, 07, 08 (#506); X1 build
segment evidence, X8 build routing end to end, X10 remove Settings' draft-prompt test (#507); wallet
name (wallet PR). AC-13's gate is the minimal one (no "Interní dokument" source, no drill-down content,
no unadmitted number; an unsupported claim blocks approval; no legal review).

## Tools and how this session used them
- `python tools/master_check.py` (register vs plans and `mvp-execution-contracts.md`; fails on a dangling
  `plan#ID`, a plan missing from §3, an AC/G/I row without a resolving chunk, an open core chunk with no
  wave). Run with `python tools/progress.py --check` and `bash tools/exposure_check.sh` before any
  planning push; `python3 -m pytest -q packages/aia_core/tests/test_parity_matrix.py` when
  `docs/migration/` changes (the JSON is rewritten with `json.dumps(m, indent=1, ensure_ascii=True)+"\n"`,
  which round-trips the file byte for byte).
- A new chunk in a core plan needs a front-matter line **and** a wave row in `mvp-execution-contracts.md`
  (§ "Every other open chunk"), or master_check fails.
- Docs-only PRs (only `.planning/`, ADRs, CLAUDE/AGENTS/ARCHITECTURE) run just Documentation checks;
  touching `docs/migration/` runs the full suites (~35 min backend).
- Shared files (CLAUDE.md, ARCHITECTURE.md, AGENTS.md, overview.md, open-items.md, plans/README.md,
  adr/README.md, migration/status.md) change only in docs PRs; a feature PR lists a Doc follow-up.
- Don't push a docs-only commit to `develop` while its CI run is deploying (it cancels the deploy).
- Stacked PRs: base the PR on `develop`, never on another feature branch (#503 was merged into its
  stacked base and never reached develop until #506 carried it).
- The MVP plan page (private artifact, generated from the plan files):
  https://claude.ai/artifact/RAYF6NZ1ctrAxo8qEYFWqR. Its generator lives only in this session's scratch
  (extract.py + template.html), not in the repo; a successor regenerates by re-extracting from
  `mvp-master-plan.md`, `mvp-execution-contracts.md`, the core plans' front-matter and
  `parity-matrix.json`, or republishes from a fresh build.
- The design artifact (design session, renamed to Peněženka): https://claude.ai/artifact/JrWZXosJtKVLckHhArngeV

## Worth knowing
- The cross-check (four code-built track maps vs the master plan; 16 of 101 findings held) is fully
  dispositioned in #507; nothing of it is pending.
- `research-lead-workbench` chunk 26 (Lead at every width) and the wallet/plan card (`lead-orchestration`
  LO1-LO6) are decided and not built.
- Unapplied doc follow-ups, deliberately: #499's ARCHITECTURE §3/§4 and CLAUDE §2 items wait on their
  ADRs being accepted; #504's Web follow-ups are build work.
