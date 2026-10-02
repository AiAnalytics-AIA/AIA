---
status: in-progress
chunks:
  - "[x] 1. ADR 0019: runtime-editable system prompts (decision, limits, what stays code)"
  - "[x] 2. Domain: the prompt slots -- editable instruction vs code-owned frame, baselines unchanged"
  - "[x] 3. Ledger: system_prompt_sha256 on AIUsageEvent and ai_usage_events"
  - "[x] 4. Storage: immutable prompt versions + append-only activations + audit, repository"
  - "[x] 5. Authorised create / activate / reset / history (in the repository, like the other admin acts)"
  - "[x] 6. Resolution and pinning: research agents (resolve at enqueue, executor runs the pin)"
  - "[ ] 7. Resolution and pinning: respondent, analysis, Deep Research (listed read-only; see 'What was not built')"
  - "[x] 8. API: /api/v1/system-prompts; agent jobs accept prompt_version and report the prompt they ran"
  - "[x] 9. Settings restructured into tabs (read-only material to Reference)"
  - "[x] 10. System prompts tab: list, editor, compare, activate, reset, history"
  - "[x] 11. Test a draft: a pinned job on a study, from the tab"
  - "[x] 12. Doc follow-up written (below)"
---
# System prompts, editable from Settings, and a Settings page that can be used

**Status:** built and verified, uncommitted · **Written:** 2026-10-02 against `develop` @ `2de4093` ·
**Branch:** `feature/system-prompts-settings` from `develop`

## Problem

1. **A prompt can only be changed by editing code and redeploying.** Every system prompt is a
   string constant in `packages/aia_core` and reaches the model as `ModelRequest.system`
   (`ai_respondent.py:572 @ 2de4093`; `research_agents.py:299 @ 2de4093` for the research agents;
   `deep_research/agents.py:66,228 @ 2de4093`; `analysis/prompt.py:38-40 @ 2de4093`). Iterating on
   wording costs a branch, CI and a deploy. Nothing of this lives on the AWS side: no Bedrock prompt
   management or Guardrails, and no prompt in SSM or Terraform (grep of `infra/` and `deploy/`).
2. **Settings is a status board.** The only live forms are access, studies and self-approval
   (`ControlPanel.tsx`, `admin` client at `apps/web/src/lib/api.ts:646-666 @ 2de4093`). Every AI
   item is DEPLOYMENT or CODE, shown and never offered. The AI section shows `prompt id@version`
   but never the text, and `research_analysis` shows no prompt version at all
   (`routers/settings.py:450 @ 2de4093`, `versions=[]`).

## What this plan does and does not do

**Does:** a stored, versioned, audited set of system prompts that an organization OWNER/ADMIN can edit,
test on a fictional client, activate and roll back without a deploy; a Settings page split into tabs.

**Does not:**
- Make `AIA_AI_*` switches, the model id, prices or approvals live. The worker reads them once at
  start and fails closed when any is missing (`ai_runtime.py`, module docstring). A live store for
  them is a different decision (it would let a database row override a fail-closed startup guard)
  and needs its own ADR and plan. Settings will say so beside each such control (chunk 9).
- Let a prompt widen anything. Gates stay code: evidence admission, output contracts, data class
  and egress, the licence gate, budgets, grounding (`CLAUDE.md` §2, `ARCHITECTURE.md:200`).
- Introduce online prompt adaptation. `research-agents.md` says none exists; a human edits, a human
  activates.

## Design decisions (to confirm at review)

- **D1. The editable part is the instruction; the contract is code and appended after it.** A slot's
  stored text is the role and task wording only. What the gate depends on (the output schema and
  report, the enum values Deep Research renders, the "payload is data, not instructions" frame, the
  analysis `_FRAME`/`_SCHEMA_REPORT`, the schema-repair prompt) stays in code and is added after the
  stored text. An edit therefore cannot remove a constraint the code relies on.
- **D2. Versions are immutable rows; activation is a separate append-only row.** Rollback is a new
  activation, never a delete. The baseline (today's constant) is version 0 of every slot and is
  always selectable. If nothing is activated the baseline runs and *says so* in the provenance.
- **D3. Resolve once, at enqueue, pin the result.** The job payload and fingerprint carry
  `{prompt_id, version, sha256}`. The executor loads exactly that version (never "active"), checks the
  hash, and fails closed on a mismatch or a missing row. This is already how the research agents
  behave (the prompt text is in the job fingerprint, `application/research.py:259-268`, re-checked
  at `executors/research_agents.py:71-94`), so a run keeps the prompt it was queued with.
- **D4. Authority.** Create/edit/activate need `OrganizationContext.may_administer` (OWNER/ADMIN;
  `scope.py:873-884`). Whether the author may activate their own version follows the organization's
  existing `allow_self_approval` value, the repository's maker-checker pattern. *Open question 1.*
- **D5. Audit.** Every create, activate and rollback writes an `access_audit` row (`tables.py:594-621`:
  actor, action, JSON before/after, request id) in the same transaction as the change.
- **D6. Testing never calls a model from the API.** `research-agents.md`: the API never invokes a
  model. "Test a draft" enqueues a normal pinned job against a client listed in
  `AIA_AI_FICTIONAL_CLIENT_IDS`, spends from that Study's budget through the usual reservation,
  and shows the artifact it produces. *Open question 2.*
- **D7. Validation is structural, not semantic.** Required placeholders present, no unknown
  placeholders, length bound, UTF-8. We do **not** claim to detect client data in a prompt: the
  editor says prompts are sent to the model as written and must hold no client material, and the
  data-class gate still applies to whatever the call carries. A real detector is out of scope.

## Open questions for the owner

1. May the author of a version also activate it? Proposed: follow `allow_self_approval` (today the
   organization default is `DEFAULT_SELF_APPROVAL_ALLOWED`); iteration speed on `develop` suggests
   allowing it there and requiring a second person elsewhere.
2. Is a pinned run on a fictional client enough as the "playground", or is a one-off
   side-by-side of two versions on the same fixed input needed in the first release?
3. Should prompt scope ever be per client? Proposed: organization-wide only. A per-client override
   means per-client reproducibility questions we do not need yet.
4. Show the full text of each prompt to every member, or to OWNER/ADMIN only? Proposed:
   OWNER/ADMIN only (prompts are the product's method).

## Chunks

Each is small, builds and passes tests alone, and is committed on its own (after permission).

1. **ADR 0019.** Records D1-D7, what stays code, the worker-startup limit, and why Bedrock prompt
   management is not used (EU-pinned inference profile and IAM today grant only `bedrock:InvokeModel*`,
   `infra/develop/main.tf:20-29,332-333`; a new service would need new IAM and egress review).
   The ADR index is a shared file: the index line goes under Doc follow-up.
2. **Domain `prompts.py` (pure).** `PromptSlot` (id, kind, required placeholders, baseline
   instruction, baseline version, contract appender), one registry. Baselines are the existing
   constants. *Test:* for every slot, baseline instruction + contract renders byte-identical to
   today's prompt (the SHA-256 of the assembled text is unchanged), so wiring it in changes nothing.
3. **Ledger hash.** Add nullable `prompt_sha256` to `AIUsageEvent` and `ai_usage_events`; set where
   `prompt_id`/`prompt_version` are copied (`model_gateway.py`). Null, never a guess, for old rows.
   Migration after `20260927_5b1d0f3e9a21`.
4. **Storage.** `ai_prompt_versions` (organization, prompt_id, version, text, sha256, note, base
   version, created_by, created_at; unique on organization+prompt_id+version) and
   `ai_prompt_activations` (append-only). Repository in `infrastructure/`, rows reachable only
   through it, with a `layer_check` rule.
5. **Application `system_prompts.py`.** create version, activate, roll back, list, get, diff.
   Authorisation per D4, audit per D5, validation per D7. *Tests:* a member is refused; a stale
   base version is refused; activation of a missing version is refused; audit row exists.
6. **Research agents wired.** Resolve at enqueue (`application/research.py`), pin into payload and
   fingerprint, executor loads the pin. Retire the hard-coded `prompt_version="1"`
   (`research_agents.py:299`). *Tests:* a queued job keeps its prompt after a new activation;
   a tampered pin fails closed; no activation runs the baseline and records that.
7. **Respondent, analysis, Deep Research wired,** one sub-commit each, same pattern. Analysis keeps
   `{module}`, `{metrics}`, `{units}` as required placeholders (`prompt.py:82-98`).
8. **API.** `routers/system_prompts.py` under the organization (not under a study: a prompt is not
   study-scoped, so this is a deliberate exception to the study-prefix route rule, to be stated in
   the ADR and checked against the route test). The settings document lists the active version per
   activity and fills the missing `research_analysis` versions. Update `test_settings_api.py` and
   `test_settings_presentation.py`.
9. **Settings tabs.** Split `ControlPanel.tsx` (about 800 lines) by section: General, Access,
   AI runtime, System prompts, Limits, Audit, Reference. Read-only material moves to Reference.
   Each non-editable AI control states why (deployment env, restart required, code constant).
   Pure move; the existing `ControlPanel.test.tsx` must pass unchanged apart from paths.
10. **System prompts tab.** Slot list with active version and status; editor with placeholder
    checking, dirty state and a save that creates a draft; version history with diff; activate and
    roll back behind a confirm that names what changes. i18n under `aia.settings.panel`.
11. **Test a draft** per D6.
12. **Doc follow-up** (see below), written into the PR description.

## Risks and costs

- **Regression is the main risk.** A bad prompt degrades results, and the gate only prevents
  *wrong numbers reaching a result*, not *worse questionnaires*. Mitigation: pinning, one-click
  rollback, the audit trail, and testing on a fictional client before activation. No evaluation
  suite exists yet; one is a later plan.
- **Cost accepted:** the prompt text now has two homes (code baseline, database), and the code
  baseline can drift from a long-lived active version. Settings shows which is running.
- **Fingerprints change meaning.** Reuse keys that embed prompt text will treat each new activation as
  new input, so a prompt edit makes later runs buy their units again. That is correct, and costs money.
- **Worker burst:** reads are one indexed lookup per enqueue, none per model call. Measure before
  merge (`CLAUDE.md` §8) and state it in the commit body.

## Findings

Anchored at `2de4093`; none has a reproduction yet beyond the cited line, so all are hypotheses
until the first chunk that touches them adds the test.

- **F1.** Research-agent prompt version is the literal `"1"` for all eight actions
  (`packages/aia_core/src/aia_core/domain/research_agents.py:299`), and Deep Research uses one
  shared `PROMPT_VERSION = "1"` (`domain/deep_research/agents.py:66`). Nothing forces a bump when the
  text changes. Consequence: the ledger cannot tell two wordings apart. Fix: chunks 6-7.
- **F2.** The usage ledger records `prompt_id` and `prompt_version` only
  (`infrastructure/tables.py:1269-1270`); no `prompt_sha256` column exists (grep). Fix: chunk 3.
- **F3.** `docs/architecture/research-agents.md:37` names harness `aia-research-harness-1`; the code
  is `aia-research-harness-2` (`research_agents.py:24`). Doc follow-up, not edited here.
- **F4.** The settings document gives `research_analysis` no prompt version
  (`routers/settings.py:450`, `versions=[]`, per the exploration; not re-read). Fix: chunk 8.

## Doc follow-up (for the PR description; shared files are not edited here)

- `docs/architecture/adr/README.md`: index line for ADR 0019.
- `docs/architecture/research-agents.md`: change harness to `aia-research-harness-2` (F3); replace
  "no online prompt or policy changes" with a pointer to ADR 0019 (human-edited, human-activated).
- `docs/architecture/ai-runtime.md` § What Settings shows: add the System prompts tab and the
  statement that configuration is still not verification.
- `CLAUDE.md` §2 map: add `domain/prompts.py` (pin, validation), `domain/prompt_slots.py` (registry),
  `infrastructure/prompt_repository.py` (the ONLY reader/writer of `ai_prompt_versions` and
  `ai_prompt_activations`; `PromptRepository` for administrators, `PromptResolver` read-only),
  `routers/system_prompts.py`, `settings/SystemPromptsPanel.tsx`, `lib/text-diff.ts`; the settings page is
  tabs (AI běh, Systémové prompty, Přístup a schvalování, Studie a rozpočty, Audit, Reference).
- `AGENTS.md`: (1) *resolve at enqueue, pin, run the pin* — a worker step must never read "the active
  prompt"; (2) hidden tab panels stay mounted, so a test that uses `getByRole` inside one must open its tab
  first; (3) verify migrations on PostgreSQL, not SQLite; (4) an egress-classified instruction is part of the
  gate: a test that adds free text to an approved design is parked, not failed.
- `ARCHITECTURE.md` §3 layer rules: add "the prompt tables are touched only by their repository" (already in
  `tools/layer_check.sh`).
- `.planning/open-items.md`: F1-F4 once they have a reproduction.

## Not done

Live editing of `AIA_AI_*`, model choice or prices; a prompt evaluation suite; per-client prompts;
Bedrock prompt management; detection of client data in a prompt.

## What was built, and where it differs from the plan above

- **Hash column** is `system_prompt_sha256`: the hash of the system prompt *as sent*, computed in the
  gateway from `request.system`. No caller changed. Nullable; `NULL` is "not recorded".
- **Chunk 5 (application layer)** collapsed into `PromptRepository`, which takes an issued
  `OrganizationContext` and enforces authority, validation, maker-checker and audit itself, the same
  way `ScopeRepository` does for the other administrative acts. A separate use-case layer would only
  have forwarded calls. `PromptResolver` is the read-only face study-level code uses to freeze a pin.
- **Pins carry the text.** The executor runs the pin from the payload and checks its hash; it does not
  read the database at all. (The cost: the payload holds the instruction text. The benefit: a job is
  self-contained and reproducible, and the worker has no new read path.)
- **Wired slots are the eight research-agent prompts.** The respondent, analysis and Deep Research
  prompts are listed with their text and the reason they cannot be edited, and the store refuses to
  save a version for them.
- **Tabs keep every panel mounted** once drawn, so an unsaved edit survives a look at another tab; the
  prompts tab mounts on first visit, so members and non-visitors cause no request.
- **Draft tests** need no new route: `POST …/research/agent-jobs` takes `prompt_version`, honoured only
  for an organization administrator (`prompt_test_requires_administrator` otherwise).

## What was not built

- **Chunk 7.** Editing the respondent prompt would let finished fieldwork datasets, reused by a
  fingerprint that holds the prompt text but not its version (`ai_fieldwork`/`research` reuse), be mixed
  across prompts. The change is: put the pin in the run metadata and in the fieldwork fingerprint, with a
  reuse test showing a different pin buys new data. Analysis and Deep Research are registered by no
  composition (`registry.py`), so there is nothing for an edit to reach. Both are one slot flip
  (`unwired_reason` → `None`) once their consumer takes a pin.
- **Live `AIA_AI_*` configuration** (see "What this plan does and does not do").
- **A "compare run" of two prompts on the same input.** A draft can be run; two runs are compared by eye.

## Verification (2026-10-02, `feature/system-prompts-settings` over `develop` @ `2de4093`)

- Python: `mypy --strict` clean (232 files), `ruff check` and `ruff format --check` clean,
  `layer_check` 74 rules, `exposure_check` 7 rules.
- Tests on SQLite: core 3137 passed, API 283, worker + executors 189. On PostgreSQL 16 (which enables the
  concurrency and worker-process tests): core 3162, API 283, worker 56, executors 139. None skipped by me.
- Migrations: applied head on PostgreSQL from empty, `compare_metadata` reports zero drift, and
  `downgrade` then `upgrade` round-trips.
- Web: `tsc`, `eslint`, `tokens:check`, `check:design` clean; `vitest` all files pass.
- By hand, in the UI workbench (real API, SQLite, local identity): the tab lists the prompts, edits and saves
  a version, and activation by the version's own author is refused with the API's sentence shown as given.
  Not done by hand: a draft test run against a live worker (the workbench's worker has no research-agent
  runtime configured); that path is covered by the executor test through the real worker and gateway.

## Findings (additions)

- **F5.** The migration chain does not run on SQLite (`alembic upgrade head` raises
  `NotImplementedError: No support for ALTER of constraints in SQLite`), though the tests use SQLite via
  `create_all`. Repro: `DATABASE_URL=sqlite:///x.db alembic upgrade head`. Consequence: migrations can only
  be verified on PostgreSQL. Smallest fix: none needed for the product (it runs PostgreSQL); a CI step that
  upgrades an empty PostgreSQL and checks `compare_metadata` would have caught any drift.
