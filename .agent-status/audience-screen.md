# audience-screen

**STATUS: ACTIVE, nothing pushed since the stop.** Development resumed 2026-10-21 23:27 UTC, relayed
by PM coordinator 3. Commit permission for the branches below still needs the product owner's own
words in this session (CLAUDE.md §5). Screen owner for the research stage Cílová skupina (`audience`), Sprint 5.
Cloud session `session_01UNFwAuLksKkUDbej3R6XUA`. Work list: `.planning/plans/artifact-audience.md`.

## Merged

| PR | Chunk | What | Observed |
|---|---|---|---|
| #568 | part of AUD1 | The Lead's `data-aia` targets on AudienceStep: `audience:definition`, `audience:filters`, `audience:filter:<factor>` (on the stored filter's chip), `audience:subpanel:<key>`, `audience:preview`; `workbench_journey.mjs` at 1440/1100/768/390, zero paid | merged 2026-10-21 20:43; CI green on `a96c1c2` |
| #580 | AUD3 | `audience_preview` answers `per_filter` (each filter alone, via `select_audience`); API field; the preview names each filter's count | merged 2026-10-21 16:12; CI green on `f6c33da` |

## Finished, validated, NOT committed (no commit permission was given for these branches)

Both live only in this cloud container and are lost when it is reclaimed. Rebuild from this list.

### AUD1 web half: local branch `feature/audience-contract` (from develop `492453e`)
- New `apps/web/src/lib/artifacts/audience.ts`, on the Brief's pattern (`lib/artifacts/brief.ts`, #600):
  `AUDIENCE_VIEW_OPS = ARTIFACTS.audience.view_ops`; `AUDIENCE_PARTS = [definition, filters,
  preview]`; `audiencePartAia`, `audienceFilterAia`, `audienceSubpanelAia` over `aiaId` (an id
  outside the grammar returns null, so the element is left unmarked instead of throwing at render);
  `storedFilterFactors(project)` (keys of `audience.filters`); `audienceTarget(target, project,
  subpanelKeys)` refusing an unknown part, an unstored filter and an unoffered subpanel;
  `audienceTargets(project, subpanelKeys)`.
- New `apps/web/src/lib/artifacts/audience.test.ts` (6 cases: registry row, marks, out-of-grammar
  ids, reading, refusals including the draft form `audience:kraj`, listing).
- `AudienceStep.tsx`: the local `AUDIENCE_TARGET` / `audienceFactorTarget` /
  `audienceSubpanelTarget` replaced by the contract's builders (`?? undefined` on the two nullable
  marks). `AudienceStep.test.tsx`: the screen's `[data-aia^='audience:']` marks equal
  `audienceTargets(...)`; subpanel marks equal the catalogue's keys.
- `artifact-audience.md` AUD1 text split into web and server halves; the server half cites #624
  (`target_refusal`, `audience_filter_not_stored`, `audience_subpanel_unknown`,
  `test_an_audience_target_names_what_the_working_copy_stores`). AUD1 not ticked: both halves
  must land.
- Observed locally: `make lint`, `typecheck`, `layer_check`, `web_design` 0; `make test-web`
  3096/3096. Journey not re-run (mark values unchanged).

### AUD5 review diff: local branch `feature/audience-proposal-review` (worktree, from develop `bcb2911`)
- Found: `ProposalReview` reads only plan fields (`proposalDiff`), so a `propose_audience` proposal
  (`research_agents.py:809-816`: `audience.description` + `audience.ai_proposal`) showed no change rows.
- New `apps/web/src/research/audience-proposal.ts`: `AUDIENCE_AGENT_ID =
  "aia.research.propose_audience"` (the result's `provenance.agent_id`); `audienceProposalDiff(project,
  result)` -> null for any other job, else the description before/after (unchanged when equal after
  trim), inclusion and exclusion criteria via `diffLists` against the kept `audience.ai_proposal`,
  limitations + questions_for_user as notes, `changes` count. Test file with 4 cases.
- `ProposalReview.tsx`, additive (coordinator's terms): the heading counts `diff.changes +
  audience.changes`; a `[data-audience-proposal]` block (Popis cílové skupiny; Kdo do cílové skupiny
  patří / Kdo do ní nepatří; Co návrh nepokrývá + "Filtry a proveditelnost návrh nemění"); plan,
  questionnaire and footer paths untouched. `ProposalReview.test.tsx`: 2 cases (audience rows, 4
  changes, footer decision unchanged; no block for another job).
- Before a push: one-line heads-up to Dotazník (`session_019gMM2vp1zH8orLrUeHZJ88`), which edits
  ProposalReview most. AUD5 stays unticked: its test is research-lead-workbench #26f's guard
  (blocked on lead-orchestration LO5a and 27c).
- Observed locally: `make lint`, `typecheck`, `layer_check`, `web_design` 0; `make test-web`
  3096/3096.

### Audit fixes: local branch `fix/audience-copy-and-tap-targets` (worktree, from develop `bfe6d15b`)
Browser audit of Cílová skupina at 1440/1100/768/390 on the workbench, zero paid jobs. Findings are
in `artifact-audience.md` under Findings, on that branch.
- F1 copy: `cs.ts` research.audience `ownText` (now says AIA lacks the upload), `analyticsText` (no
  "NPC Panelu"), `comingSoon` "PŘIPRAVUJEME", `czComingTitle`, `special` "Speciální skupiny",
  `czIntroBold`, `strategyDiscoverText` in Czech. Journeys and `AudienceStep.test.tsx` select
  "Speciální skupiny". New `apps/web/src/i18n/audience-copy.test.ts`.
- F2 tap target: the chip's remove button `size-6` (was 15x16 px). `workbench_journey.mjs` asserts
  each "Odebrat filtr" is at least 24x24 at all four widths, and that the fixture shows a chip.
- F3 stored values the population lacks: `filterProblems(p, catalog)` plus `CATALOGUE_TOP_VALUES = 60`
  in `research/audience.ts`. It names a factor the catalogue does not offer and values a complete
  (<60) value list lacks (`noneKnown`: all of them); it says nothing for a cut list, a range, a
  boolean or no catalogue. On the chip: `data-filter-problem` and the attention style. Below the
  chips: a `role="note"` with cs keys `problemTitle`, `problemFactor`, `problemValues` and
  `problemValuesAll`. Tests: `audience.live.test.ts` (2 cases) and `AudienceStep.test.tsx` (1 case).
- Observed: lint, layer_check and web_design 0; typecheck 0 after one fix; test-web 3212/3213. The one
  failure is develop's own (`lib/artifacts/sample.test.ts:42`, sample:ready no longer pending,
  reproduces untouched; reported to the PM and the coordinator). `workbench_journey` and
  `ui-audience` both pass.

## Self-review (PM's quality bar, 2026-10-21/22)

`/code-review high` was run on all three local branches and every finding was fixed or answered.
- **Audit fixes:** `filterProblems` now has reasons (factor, policy, empty, values) and treats a
  scalar as one value. It compares text values only, so a number never gets a false flag. The notes
  say "výběr" (the preview, or a run drawing from the population) refuses the whole audience. The
  chip names the problem in words. The copy no longer promises segment finding.
  `/security-review` could not run (no origin/HEAD); a manual sweep found no HTML injection, request,
  storage or secret in the diff. Observed: lint, typecheck, layer_check, web_design 0; test-web
  3214/3215 (the one failure is develop's sample.test, fixed by #627); workbench, audience and
  workspace journeys pass on a fresh workbench.
- **AUD1:** `storedFilterFactors` reads through `filterChips` (one reader). `audienceTargets(project,
  {preview, subpanels})` follows what the screen draws. The grammar check is a predicate over
  ID_SOURCE (no throw/catch). Tests cover the no-catalogue and subpanel views. Observed: all checks 0,
  test-web 3097/3097. Answered rather than changed: an out-of-grammar chip stays unmarked (catalogue
  ids all fit the grammar); lead.ts's duplicate parsing was sent to the coordinator.
- **AUD5:** the job's `action` is threaded through `askReview` and `ProposalReview(action=)`. Criteria
  are trimmed via proposal-diff's exported `strings`. Keys are by index. The section is hidden when
  empty, the duplicate filters note is gone, and the headings are "Koho zahrnout" / "Koho vyloučit".
  Observed: all checks 0, test-web 3095/3095; 90 non-test lines.

## Blocked (as of the stop)

- AUD2 (V2 table): `input-interactions#5`.
- AUD4 (assumptions): `assumptions-and-open-answer-coding` AOC1/AOC2.
- AUD6 (audience journey with a filter's own count): needs AUD2.
