---
status: in-progress
chunks:
  - "[ ] RQC0. A per-respondent checkpoint (OI-64): each answered respondent and its paid-call identity are stored under the lease; a retry resumes; a possibly-billed uncertain call requires recovery and never triggers an automatic paid replay"
  - "[ ] RQC1. One straight-liner definition in `domain/`, called by the Sociomap engine, the run QC and the worker"
  - "[ ] RQC2. The QC node wired into the run: template node, step kind, registry, `AIA_RUN_QC_ENABLED`, the run-key identity"
  - "[ ] RQC3. A `MaterialRule` and lineage for run-derived material sent to a model (QC flags, the map interpreter)"
  - "[ ] RQC4. The flag artifact and the worker's keep-or-flag proposal; the accept destination"
  - "[ ] RQC5. Replace as a new linked run: a start path from a COMPLETED run with an exclusion pin that reuses the other respondents' paid answers; its ADR and deterministic admission rule (ADR 0026 decision 4) come first"
  - "[ ] RQC6. Quotas before a run and a support forecast for the panel path"
  - "[ ] RQC7. The fieldwork event contract: heartbeat, quota-cell fill, a respondent grid, the park reason code"
  - "[ ] RQC8. Readiness reads the worker's egress: a run whose route cannot carry Class A is flagged before it parks"
  - "[x] RQC9. One authority for the valid n: the domain readiness limits, read by the web and the Lead"
  - "[ ] RQC10. A population double composed in both the API and the worker over HTTP, for tier A's AC-05"
  - "[ ] RQC11. Routing in fieldwork (W1, after working-copy-edit-ops WCE13): a conditional question is asked only of respondents whose earlier answer meets its condition, and the dataset records who was not asked"
  - "[ ] RQC4a. W1 flag contract: deterministic QC flags, ids, lineage and accept-target schema before the W3 model-worker proposal"
  - "[ ] RQC12. Weight identity over HTTP: weight_role and weight_column in the run's population note and in the report's method section (G78)"
  - "[ ] RQC13. Fieldwork shows a question's stimulus to each respondent before the question, recorded in the answer's provenance (D-45)"
---
# Run QC and a fieldwork checkpoint

Fieldwork that does not repay on retry, and the run QC that the Fieldwork and Results artifacts show. Written 2026-10-19 from `.planning/evidence/mvp-master-traces/trace-2-sample-execution.md`; OI-64 was owned only by `research-agent-workflows` I4.

**Owner: S2.** Takes the gap rows G26, G27, G29 and interfaces I6, I7 of `mvp-master-plan.md` §6.1 and serves AC-05, AC-06, AC-08 and gate I-1.
Every chunk below is **open**; a chunk is built from this file, not from the master plan.

## Decisions this plan carries (settled by the owner; not re-asked)

- Respondents are population-built by default; invented respondents only for tests (Q17).
- Straight-liners: no pause after fieldwork; a warning, then the worker proposes keep or flag; replace is a new linked run (F18, Q22).
- Fieldwork that is killed loses no work (AC-06); this is an engineering prerequisite, not a product choice (the owner, 2026-10-19).

## Chunks

**RQC0. A per-respondent checkpoint (OI-64): each answered respondent and its paid-call identity are stored under the lease; a retry resumes; a possibly-billed uncertain call requires recovery and never triggers an automatic paid replay**  
Each attempt starts at the first respondent and stores the dataset only at the end (`ai_fieldwork.py:283-326`), `max_attempts=3`, a clean shutdown is a RETRY (`workflow.py:660-686`), and the plain whole-run `retry` of a failed or cancelled run "spends again" (`research.py:835-862`). **Narrowed after the independent review: `retry_analysis` reuses the frozen dataset and never recollects fieldwork (`research.py:865-895`), so the claim covers interrupted fieldwork and the plain retry, not an analysis retry.** Shape: the `client_work_journal` pattern. Test: kill the worker mid-fieldwork; the retry spends nothing for respondents already answered. **First S2 item in W1, before any step that runs after fieldwork.**

**RQC1. One straight-liner definition in `domain/`, called by the Sociomap engine, the run QC and the worker**  
There are three definitions today (`sociomap/engine.py:84-109`, the unit QC `qc.py:200-207`, the workbench D17). Interfaces I6.

**RQC2. The QC node wired into the run: template node, step kind, registry, `AIA_RUN_QC_ENABLED`, the run-key identity**  
`evidence-integrity` 2 and 3 produce the artifact and its display; this chunk puts it in the graph.

**RQC3. A `MaterialRule` and lineage for run-derived material sent to a model (QC flags, the map interpreter)**  
`material_rules.py:59-70` has none. Interfaces I16.

**RQC4. The flag artifact and the worker's keep-or-flag proposal; the accept destination**  
Per F18 nothing pauses; a proposal waits. The accept destination is a field of the run's QC record.

**RQC5. Replace as a new linked run: a start path from a COMPLETED run with an exclusion pin that reuses the other respondents' paid answers**  
Per F18 replacement is a new linked run. **Prerequisite (ADR 0026 decision 4, Accepted):** respondent replacement gets no command until its own ADR and a deterministic admission rule exist (respondents are drawn once per run); the feature is settled, the ADR is the work. The weighting and support meaning of a replacement is a **methodology dependency** and sits in the master decision register (`mvp-master-plan.md` §11.4); the chunk builds the mechanism the owner decided and labels its limits.

**RQC6. Quotas before a run and a support forecast for the panel path**  
The preview drops the composition and readiness does not call the previewer for the panel; `support_forecast` is unknown for a panel run today.

**RQC7. The fieldwork event contract: heartbeat, quota-cell fill, a respondent grid, the park reason code**  
Written first by S2; consumed by the Fieldwork artifact (`research-lead-workbench` 19). Interfaces I7.

**RQC8. Readiness reads the worker's egress: a run whose route cannot carry Class A is flagged before it parks**  
The panel default needs the route widened and the API reads no egress key. Shares the composition record of `lead-orchestration#LO12b`.

**RQC9. One authority for the valid n: the domain readiness limits, read by the web and the Lead**  
Four ranges today: web 50-5000, Lead 30-40,000, readiness 20-10,000, the sampler.

**RQC10. A population double composed in both the API and the worker over HTTP, for tier A's AC-05**  
Fictional rows cannot meet the v17 contract, so the existing panel tests inject a loader. Written with the acceptance harness (`mvp-acceptance-harness` 4).

## Open: owner clarifications

- The weighting and support meaning of a replaced respondent (a method question; RQC5 builds the mechanism and labels the limit).


## Execution predecessors (2026-10-20)

RQC9-RQC10 land in W0: the single valid-n contract and population double precede the W1 UI and
HTTP journey. RQC0 is first in W1 before resumed fieldwork; RQC1-RQC3, RQC4a and RQC6-RQC8
then supply the deterministic QC contract/node, readiness/support and Fieldwork events. The
Fieldwork artifact cannot be called integrated before it consumes RQC7's real payload.

RQC4's model-worker proposal/accept implementation and RQC5's linked replacement land in W3,
after the shared contracts: RQC4's accept-result type precedes LO9b's binding; the executable proposal follows that binding. RQC4a separates the earlier typed
flag contract from that paid worker. Replacement also needs its own ADR and approved weighting,
effective-n and support semantics; preparing storage/refusal tests does not approve those semantics.

## Cross-check additions (2026-10-20)

From the independent cross-check of the master plan against the code (`mvp-master-plan.md` §6.1, G47-G57). Anchors are `@ 085abe0`.

**RQC11. Routing in fieldwork (G53, X8; the owner, 2026-10-20: build routing end to end).** Fieldwork today asks every respondent every question, and readiness refuses a conditional one. With `working-copy-edit-ops#WCE13` storing valid conditions, this chunk evaluates each condition on the respondent's own earlier answer, in questionnaire order, asks the question only when it holds, and records "not asked" distinctly from a missing answer, so the filtered base is computable. The checkpoint (RQC0) keeps routing state per respondent. Tests: Q7 is asked only of respondents who answered "never" to Q2; the dataset distinguishes not asked from not answered; a resumed run routes the same way.

## Scope freeze (2026-10-20)

Source: the owner's answers of 2026-10-20 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, decision ids from `decision-list.md`), applied by freeze step 4; the proposals they settle are in `proposed-edits.md`.

**New chunks.** RQC12 (W1). RQC13 (W2, after `working-copy-edit-ops#WCE14`); a stimulus changes the
respondent's input, so its prompt part is pinned with the run like the rest of the respondent system.

**Existing chunks, changed.**

- **RQC4 / RQC5 (D-36).** After a replacement the report and the Lead read the newer run and name
  both.
- **RQC9.** The valid-n authority is the organization's readiness methodology in force, not a code
  constant.
- The attention check (D-43) is **out**.

## RQC9, delivered (2026-10-20, branch `feature/w0-n-authority-population-double`)

**The rule.** `sample_size_problem(n, limits)` in `domain/research_design.py` is the one judgement of
a valid n: a whole number within the readiness limits in force, both bounds included; a boolean, a
fraction or text is `sample_size_missing`, a whole number outside the range
`sample_size_out_of_range`. Nothing clamps. Readiness's `sample_size` check calls it.

**The authority.** `application/research.py` `readiness_in_force(session, scope)`: the
organization's readiness methodology in force (a stored version, else the preset
`aia-readiness-1`, 20-10,000), as the scope-freeze note on RQC9 requires. A run start pins it as
before (`ResearchRuns._readiness` now calls it); the three readers below read the same function.

- **The web** reads `GET /api/v1/studies/{study_id}/research/limits` (`ResearchLimitsResponse`:
  `methodology_version`, `version`, `sample_size {min, max}`). Its own 50-5,000 copy is gone
  (`research/persona.ts` `setSampleSize`, `PersonaStep.tsx` `SampleInput`). A value outside the
  range, an empty field or anything but a whole number is **refused and said, never stored and never
  clamped** (finding IA-1 closed): the field keeps what the person typed, `role="alert"` says the
  range, the presets and the recommendation are disabled where the range does not admit them, the
  slider's thumb range sits inside it. Limits not yet read disable the field; limits that cannot be
  read refuse every value and say so (unknown is never presumed to admit a value).
- **The Lead** is frozen with the limits (`design.readiness` in the turn's context,
  `domain/research_lead.py` `readiness_layer`). `ground_edits(…, sample_size=)` drops a `set_n`
  outside them by name at the turn; `apply_edit(…, sample_size=)` refuses it at the accept under the
  limits in force *then* (`decide_edits`), so a version activated while the Lead worked is what is
  enforced. The closed schema keeps only `ge=1`: its old 30-40,000 was the fourth range. The harness
  moved to `aia-research-lead-2`, so a turn queued under 1 (no limits frozen) is refused by the
  executor's existing harness check rather than grounded without limits.
- **The sampler** is not a fourth authority: it draws the n the run was started with, and a start
  is refused below or above the readiness limits before any draw.

**Tests.** `test_research_design.py::test_the_one_rule_for_a_valid_n_refuses_and_never_clamps`,
`::test_a_valid_n_is_judged_by_the_limits_given_not_the_preset`;
`test_research_lead.py::test_a_set_n_is_held_to_the_readiness_limits_at_the_turn_and_at_the_accept`,
`::test_a_set_n_with_no_limits_known_is_dropped_and_refused_never_presumed_valid`;
`test_methodology_api.py::test_the_study_reads_the_valid_n_in_force_and_an_activation_moves_it`;
`test_research_lead_api.py::test_a_sample_size_is_accepted_only_within_the_readiness_limits_in_force`;
`test_research_lead_executor.py::test_a_sample_size_outside_the_frozen_readiness_limits_is_dropped_by_name`;
`PersonaStep.test.tsx` "the sample: a value outside the server's valid n is refused and said, never
clamped (IA-1)", "… a narrower range in force disables …", "… with the range unread nothing is
stored …"; `persona.parity.test.ts` "the input: a value the classic stored as typed is stored the
same; one it clamped is refused".

**A deliberate departure from 18.6.6.** The classic input's clamp (`PROJECT.n=Math.max(50,
Math.min(5000, …))`) is not ported: the parity test now pins what still matches (an in-range value
is stored as the classic stored it) and asserts the refusal where the classic clamped.

**Left for the input-interactions plan (not this chunk).** IA-3, one stepper replacing the field and
the slider, is that plan's B1; the slider here only stays inside the range.
