---
status: done
chunks:
  - "[x] 1. AiOrb: the thinking-orbs package behind one component, tinted with the theme's ai-ink"
  - "[x] 2. Which activity is AI thinking: one pure mapping, agent jobs, run steps, Deep Research steps"
  - "[x] 3. The orb where AI thinks: the job panel, Progress, the Deep Research panel"
---
# An orb while AI is thinking

**Drafted:** 2026-10-07 · **Base:** `develop` @ `d2e038a` · **Owner:** the product owner, who asked for
the thinking orbs (`thinking-orbs` on npm, MIT, Jakub Antalik) "only when AI is thinking", "in the
theme's colours".

## Decisions (the owner's, 2026-10-07)

1. **An orb while a step runs.** First "only when AI is thinking", then widened the same day to
   "thinking or working": an orb shows beside any step the API reports `RUNNING`, and at no other
   time: not while it is queued (`RUNNABLE`), blocked, waiting (`WAITING_*`, `AWAITING_*`), failed,
   cancelled or done, and never for a page load or a save. This keeps the design brief's rule that
   motion "must never imply progress the backend cannot verify"
   (`docs/design/aia-design-system-brief.md:365`): the orb is indeterminate and shown only on a state
   the API reports.
2. **The theme's colours, and AI told apart from code.** A step that calls a model is tinted with
   `ai-ink` (the "AI úloha" badge); a step that is code with `status-running` (the running chip).
   Both are read from the CSS custom property that applies where the orb is mounted (`--ai-ink`,
   `--status-running`), so they follow light, dark and an ancestor `data-theme` without a second copy
   of a token. No token is added or changed. Tinting code as AI would tell a person a model is at
   work when none is.

## What calls a model (the evidence for the mapping)

| Surface | Step | Calls a model because |
|---|---|---|
| Research agent job | its agent step | `apps/executors/src/aia_executors/research_agents.py` (StepModelCaller) |
| Research run | `run`, only when `fieldwork_source == "ai_runtime"` | `aia_executors/ai_fieldwork.py` |
| Research run | `analysis_<module>` | `aia_executors/analysis.py` |
| Deep Research | `plan`, `investigate` and its tracks `investigate/<track>`, `verify`, `synthesize` | `deep_research/{plan,investigate,lead,review}.py`, `SynthesizeExecutor` in `publish.py` |
| Deep Research | `merge`, `publish` | none: code only |

## Orb states

One table per surface in `apps/web/src/lib/activity-orb.ts`, so a change of taste is one line.
AI: agent actions (analyze_brief searching, build_questionnaire composing, optimize_questionnaire
solving, propose_audience connecting, suggest_dimensions shaping, critique_design searching,
design_copilot working, answer_memory weaving); AI fieldwork listening; analysis modules working;
Deep Research plan shaping, investigate searching, verify solving, synthesize composing.
Code: compile shaping, preflight solving, fixture fieldwork listening, aggregate weaving, Sociomap
connecting, reports composing; Deep Research merge weaving, publish composing; a running step no
table names (a kind added later) working.

## Accessibility

The orb is decoration beside text that already says the state (the job panel's live phase, the
step's status chip, the Deep Research status line), so it is `aria-hidden`. The package draws a still
frame under `prefers-reduced-motion` and pauses offscreen.

## Cost

One runtime dependency in `apps/web` (`thinking-orbs`, ~25 KB unminified, no dependencies, React peer,
plain 2D canvas, no network). No API, worker, token or migration change.

## Verified (2026-10-07)

- `npx vitest run`: 38 files, 615 tests pass, including `src/lib/activity-orb.test.ts` (the mapping),
  `JobPanel.test.tsx` and the two orb cases in `ExecutionSteps.test.tsx` (Progress).
- `tsc --noEmit`, eslint on the changed files, `make web_design`, `make layer_check`,
  `make exposure_check`, `next build`: clean.
- In Chromium, over the real `tokens.css`: an AI orb paints with `--ai-ink` (`#8a2783` light,
  `#f0a6e8` dark), a code orb with `--status-running` (`#3557e0` / `#8aa2ff`), and both re-tint when an ancestor's `data-theme` changes. jsdom has no canvas, so the
  component tests assert where an orb is mounted, not its pixels.

## Not done

- No component test for the Deep Research panel's orb; its rule is `deepResearchRunOrb`, unit-tested
  (a running step that thinks wins over one that works).
- On the dark theme the package's depth ramp fades far dots toward black, so the orb reads quieter
  than the `ai-ink` badge text. Accepted; `dotSize` / `dots` can bolden it if wanted.

## Findings

- **Hypothesis (not reproduced):** `QuestionnaireStep.test.tsx` › "reviews the native brief analysis
  and questionnaire before opening the editor" timed out at 15 s in one full `npx vitest run` on this
  branch on 2026-10-07; it takes ~340 ms alone (twice), and the next full run passed 615/615. Its
  stubbed job is `COMPLETED` with `steps: []` (`src/components/rehome/research/test-native-agents.ts:29`),
  so no orb mounts on its path. Suspect: `followAgentJob`'s real 1 s poll
  (`src/lib/research-agent-jobs.ts`) under four-worker load. Needs a reproduction before it is an item.
