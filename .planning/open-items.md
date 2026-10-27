# Open items

The live defect and question register. One entry per item, never re-filed
elsewhere — *a fix landing under one plan's name while the item stays open under
another's* is the specific failure this file exists to prevent.

A **finding** carries all six: the claim in one sentence, the anchor
(`file:line @ SHA`), a reproduction that fits one command or one test, the
user-visible consequence, the smallest fix, and the test that would have caught
it. Missing the reproduction makes it a **hypothesis** — reproduced or deleted,
never budgeted for.

Close an item by editing it here, in the same commit as the fix.

---

## OI-1 · Finding · CI reports parity as passing when it did not run

**Claim.** The 94 parity and characterization tests never execute in CI, so a
green pipeline is not evidence that domain behaviour still matches the validated
prototype.

**Anchor.** `.github/workflows/ci.yml:129-131 @ df294e2`

**Reproduction.** Open any CI run's *Parity against legacy prototype* job: it
emits `::warning::Legacy prototype not available in CI` and exits 0 through
`|| true`.

**Consequence.** A change to `aia_core.domain.pipeline` that silently diverges
from the prototype merges green. The methodology is the product; parity is the
only evidence it is preserved.

**Smallest fix.** Decision D3 in `overview.md` — vendor the reference as a
private submodule, or publish a fixture pack of recorded prototype outputs.
Until then the mitigation stands and is documented in `CLAUDE.md §10`: anyone
changing domain logic runs `make test-parity` locally against
`AIA_LEGACY_REFERENCE`.

**Test that would catch it.** A CI assertion that the parity job collected more
than zero tests, rather than that it exited zero.

**Status.** **Reporting half closed** by the parity-matrix work
(`.planning/plans/done/parity-matrix-and-gates.md`): the `|| true` is gone, every CI
pytest step writes JUnit, and the `parity-status` job reports each of these
tests' gates as `NOT_EXECUTED` — a skip can no longer read as a pass
(`packages/aia_core/tests/test_parity_status_tool.py::test_a_skipped_gate_is_not_executed_never_passed`,
`test_parity_matrix.py::test_every_ci_pytest_step_writes_junit`). The
*execution* half stays open and is now narrower than D3 implied: the golden
fixtures reach CI through the reference repository with no archive, so what
remains blocked is only the legacy-code comparison, which needs the withheld
archive (`REF-WITHHELD-REFERENCE-ARCHIVE`).

**Widened 2026-09-22.** The evidence-governance parity cases that read the private
reference repository (`AIA_REFERENCE_REPO`, e.g.
`test_evidence_gate_parity.py::test_every_reference_field_rederives_identically`)
skip in CI for the same reason. The recovered decision tables in that module do
not need the reference and run everywhere; the 400-field checks do not. The same
decision (D3) closes both.

---

## OI-2 · Finding · The dependency audit cannot fail

**Claim.** `pip-audit` and `npm audit` both end in `|| true`, so a known-
vulnerable dependency does not stop a merge.

**Anchor.** `.github/workflows/ci.yml:341 @ df294e2` (Python),
`.github/workflows/ci.yml:353 @ df294e2` (npm)

**Reproduction.** `pip install "requests==2.19.1"` into the CI environment and
observe the job still concludes success.

**Consequence.** A published CVE in a direct dependency ships unnoticed.

**Smallest fix.** Drop `|| true` once a first clean run establishes the baseline,
and replace the placeholder `--ignore-vuln GHSA-0000-0000-0000` with a real,
dated, individually justified allowlist. npm side is blocked on the `apps/web`
rewire (Next #4).

**Test that would catch it.** The promotion itself — a blocking audit step.

**Status.** Open, deliberate, with the promotion condition recorded in
`ARCHITECTURE.md §8`. This is the tier working as designed, not an oversight.

**Update 2026-09-24.** The npm side now has its clean baseline:
`cd apps/web && npm audit` reports 0 vulnerabilities after `next` 16.1.6 →
16.3.6, `eslint-config-next` to match, and patch/minor bumps of the transitive
packages (13 advisories before: 1 critical, 8 high, 3 moderate, 1 low). Dropping
`|| true` from `.github/workflows/ci.yml` (*Audit npm dependencies*) is now
unblocked and is a separate change; `pip-audit` is unchanged.

---

## OI-3 · Question · No release branch

**Claim.** `main` is both trunk and release. There is no branch protecting a
released version from in-flight integration work.

**Anchor.** `CLAUDE.md §5` (Branches) @ this change

**Consequence.** None today: nothing is deployed to users from this repository
yet. The moment a deployment exists, a merge to `main` can change what is live
without a separate gate.

**Smallest fix.** Add `develop` as trunk and keep `main` as release, retarget CI
and branch protection. The cost is real (every in-flight branch retargets), so it
is deferred until there is a release to protect.

**Trigger to revisit.** The first production deployment, or Terraform landing
(Next #5) — whichever comes first.

**Status.** **Closed** by the develop deployment: `develop` is the integration
branch, deployed on every green head (ADR 0009), and `main` is the release
branch receiving release PRs (`CLAUDE.md §5`, `.github/workflows/ci.yml`
`on.push.branches`). Branch protection itself is a human action
(`infra/develop/README.md` § Human actions, items 10–11).

---

## OI-4 · Hypothesis, closed · "Unknown scored as good"

**Claim swept.** Anti-pattern A4 — a missing value coalesced to a neutral default
that silently rewards absent data.

**Sweep.** `ARCHITECTURE.md §6 A4`, run at df294e2: 8 hits.

**Outcome.** All 8 reviewed and cleared. Every hit is an empty-aggregate case
where zero is the correct answer, not an unknown — `int(total or 0)` over a SUM
with no rows is genuinely zero spend
(`packages/aia_core/src/aia_core/infrastructure/repositories.py:218 @ df294e2`);
`counts.get(c.client_id, 0)` for a client with no studies is genuinely zero
studies (`apps/api/src/aia_api/routers/scope.py:236 @ df294e2`).

**Status.** Closed. Re-run the sweep when the AI runtime lands — scoring and
budget code is exactly where this bug is expensive.

**Re-run 2026-09-22, AI runtime change set.** 4 new hits, all cleared: an empty
ledger SUM is genuinely zero (`ai_usage_repository.py` `total_cost_usd`); unreported
cache counts are zero only because adapters leave every unattributed token in the
full-rate `input_tokens` (`application/model_gateway.py` `_price`, commented); the
ceiling's `cache_write_usd_per_mtok or 0.0` sits inside a `max` with the input rate
(`domain/ai_models.py` `ceiling_usd`). The companion A7 sweep found one real defect,
fixed in the same change: `parse_duration_seconds("inf")` / `"nan"` crashed the
retry-after computation (`test_model_adapters.py::test_duration_parsing_consumes_the_whole_value`).

---

## OI-5 · Finding · `make deps` installs into the system interpreter, not the venv

**Claim.** On a clean checkout `make deps` creates `.venv` and then installs
every package into whatever `python3` is on `PATH`, leaving the venv empty — and
it never checks that interpreter meets the project's `requires-python = ">=3.12"`.

**Anchor.** `Makefile:10-12 @ df294e2`
(`PY := $(shell …)`, `PIP := $(PY) -m pip`, `BIN := $(shell …)`)

**Reproduction.**

```bash
rm -rf .venv && make -n deps
# test -d .venv || python3 -m venv .venv
# /usr/local/bin/python3 -m pip install -q -e "packages/aia_core[dev,postgres]"
```

`:=` is evaluated once when make **parses** the file — before the `deps` recipe
creates the venv — so `PY` and `BIN` resolve against a tree that has no `.venv`
and stay wrong for the whole run.

**Consequence.** A new developer's `make setup` either fails outright (it does on
a Debian base image: *"Cannot uninstall pip 24.0, RECORD file not found"*) or
silently installs the project into the system Python. The `.venv` it reports
creating is empty, so every later `make test`, `make dev` and `make openapi` runs
against whatever the system happens to have. Where `python3` is older than 3.12 —
common on current LTS images, and the case in this container — the install is
refused with *"Package 'aia-core' requires a different Python"*, which reads like
a packaging error rather than a Makefile one.

CI is unaffected: it has no `.venv` and installs into the runner's interpreter
deliberately, which is why this has stayed invisible. **It fails only for people
setting the project up for the first time**, which is the worst audience for it.

**Smallest fix.** Make both variables lazily expanded (`PY = …`, `BIN = …`, with
`=` not `:=`) so they resolve at recipe time, after the venv exists; and give
`deps` an explicit interpreter floor rather than trusting `python3`:

```make
PYTHON ?= python3.12
deps:
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
```

Note this is the second-order cost of the fix for the *first* Makefile incident
(`ARCHITECTURE.md §6 A2`): resolving the interpreter instead of hardcoding it was
right, but doing it with `:=` moved the assumption rather than removing it.

**Test that would have caught it.** A CI job that runs `make setup && make test`
from a clean checkout on an image whose default `python3` is older than 3.12.

**Status.** Open. Not fixed in the change set that filed it — that change set is
documentation and tooling for the rules themselves, and `CLAUDE.md §5` requires
one logical change per commit. Found while running the §10 verification sequence
for the first time.

---

## OI-6 · Finding · Project content carries a second, unvalidated population identity

**Claim.** A project revision records which population and weight it used as free
text the caller supplies — `population_snapshot`, `weighting` and
`aggregation_policy` in the content, `panel_version` on the revision — and none of
it is checked against the population registry or the import contract, so it can
disagree with the `PopulationBinding` the run actually records.

**Anchor.** `packages/aia_core/src/aia_core/domain/pipeline.py:294,298-299 @ 17c0a6b`
(those keys feed the FIELDWORK and AGGREGATION stage fingerprints);
`packages/aia_core/src/aia_core/infrastructure/repositories.py:407 @ 17c0a6b`
(`panel_version: str = ""`); `infrastructure/tables.py` `ProjectRevisionRow.panel_version`.

**Reproduction.** `ProjectRepository.save(project_id, content={..., "population_snapshot":
{"panel_version": "v99"}, "weighting": "vaha_kalibrovana"})` succeeds, and the stage
fingerprint changes on the string alone.

**Consequence.** R4 one level up: the project can *say* `v17_4_0` / structural
weight while the run was bound to a different version or weight, and a string edit
reopens stages without any population change. Harmless today — no research step
reads the population yet — and a false provenance claim the moment one does.

**Smallest fix.** When research execution lands, derive the FIELDWORK/AGGREGATION
fingerprint inputs from the resolved binding (`version_id`, `content_sha256`,
`weight_column`, `view`) instead of from free text, and reject a `weighting` role
the contract does not declare.

**Test that would catch it.** A pipeline test asserting that two projects with the
same binding and different `population_snapshot` strings fingerprint identically,
and that an undeclared `weighting` role is refused.

**What population-data now exposes for the fix** (consumption readiness): every
`PopulationBinding` carries `version_id`, `content_sha256`, `weight_role`,
`weight_column`, `view`, `dictionary_sha256`, `field_policy_version`,
`companion_set_sha256` and `joint_state` — see `docs/architecture/population.md`.
The fingerprint change itself stays research-engine's.

**Status.** Open, owner research-engine. Filed by the population foundation
(`.planning/plans/done/population-version-foundation.md`), deliberately not fixed
there: it changes stage-fingerprint semantics, which is research-engine scope and
needs the parity suite run against `AIA_LEGACY_REFERENCE`.

---

## OI-7 · Finding, unblocked · The seven enrichment derivations are not recoverable

**Claim.** The ANALYSIS population view needs `audience_dimensions.enrich_panel`'s
seven `*_derived` fields, and their derivation logic exists only in the withheld
archive; no committed evidence in AIA-reference is enough to reconstruct them.

**Anchor.** `packages/aia_core/src/aia_core/application/population.py`
`PopulationRuntime._enrich` (raises `EnrichmentFailed` with no enricher);
archive source `audience_dimensions.py` SHA256 `6ae1d1f8…c754bf`.

**Reproduction.** `tests/test_population_runtime.py::test_the_analysis_view_does_not_load_without_an_enricher`.

**Consequence.** Correct fail-closed behaviour (R1), and a hard blocker for any
research or simulation step that needs the analysis view. The BASE view loads.

**Result of exhausting the reference (outcome B).** Only function names, four
threshold expressions and a truncated docstring are recorded — no formulas, no
inputs, no outputs. The exact missing source, the parity fixture needed (F12,
EXACT) and why no safe reconstruction exists are in
`docs/migration/population-enrichment-archive-dependency.md`. This is now a
data/archive acquisition task, not an engineering one.

**Correction (2026-10-12).** Not archive-blocked. Both files this item pins are vendored in the
extracted unit (ADR 0011), byte-identical: `legacy/npc-panel-18.6.6/app/audience_dimensions.py`
SHA256 `6ae1d1f8…c754bf` (`attach_derived`, `audience_dimensions.py:137-182`) and its specification
`legacy/npc-panel-18.6.6/app/tests/test_audience_dimensions_1793.py` SHA256 `36efe988…a2d602`.
Reproduction: `sha256sum` of either file @ `a099e5e`. The derivation is an engineering task: an
`Enricher` ported from `attach_derived`, EXACT against fixtures from the unit's own function,
[`plans/panel-grounded-respondents.md`](plans/panel-grounded-respondents.md) chunk 2d (found while
porting the audience filter, PR #298). The test that would have caught it: a check that every
archive dependency pinned by hash under `docs/migration/` is absent from `legacy/` before it is
called blocked.

**Derivation landed (2026-10-12).** `domain/population/enrichment.py`
(`AudienceDimensionsEnricher`, `attach_derived` ported) @ `53205e8`, PR #305: EXACT cell by cell
against the unit's own `enrich_panel` on 122 fictional rows
(`tests/test_population_enrichment.py`; `tools/enrichment_capture.py`). A missing flag column
refuses with `EnrichmentInputMissing` where the unit raised an `AttributeError`.

**Status.** Open: derivation landed, not composed. It closes when a step builds
`PopulationRuntime(..., enricher=AudienceDimensionsEnricher())`
(`plans/panel-grounded-respondents.md` chunk 5). The eight runtime fields still need a data-owner
classification (`docs/migration/population-derived-fields-decision.md`): until then the field policy
refuses them for every use, audience filtering included (`policy.py:387`,
`test_population_audience.py::test_an_unclassified_derived_dimension_is_refused_by_the_field_policy`).

---

## OI-8 · Finding, closed · No authorization model for establish and promote

**Claim.** `PopulationRuntime.establish` and `promote_live` required an actor and a
reason but checked no permission, and the actor was a free-text argument.

**Anchor.** `packages/aia_core/src/aia_core/application/population.py`
`establish` / `promote_live` @ `8da7261`.

**Consequence.** Any caller holding a session could move LIVE for every study in
every organization. Latent: nothing exposed either method yet.

**Fix.** A separate platform capability rather than a change to the shared scope
contract: `PopulationPermission` {`POPULATION_ESTABLISH`, `POPULATION_PROMOTE`} and
an unforgeable `PopulationOperatorContext`
(`packages/aia_core/src/aia_core/domain/population/authority.py`), issued only by
`PopulationAuthority` from trusted configuration
(`application/population_authority.py`). Both use cases take the context instead
of `actor_id`, check the permission inside the use case, and record the context's
verified user id. A `StudyContext`, an `OrganizationContext`, a principal, a
tool-shaped dict or `None` is refused by type; an organization OWNER is not an
operator; `make layer_check` refuses an issuance anywhere else. The shared
`Permission` enum and scope roles are untouched, so no integration-architecture
contract change was needed — flagged to them for review in the PR.

**Test that catches it.** `packages/aia_core/tests/test_population_authority.py`
(17 tests).

**Status.** Closed by the population consumption-readiness change
(`.planning/plans/done/population-consumption-readiness.md`, chunk 3). Remaining
decision for the platform: which deployment configuration key names operators, and
who holds it — the composition root does not wire it yet because nothing exposes
establish or promote.

---

## OI-9 · Question · The evidence-role contract is not published

**Claim.** The UI must render every figure's evidence role, but the repository
names only three roles and an ellipsis; the full list lives in the prototype's
data contract, outside this repository.

**Anchor.** `docs/product/README.md:103 @ 17c0a6b`; the Validation & Evidence
context is "not started" in `docs/architecture/domain-map.md @ 17c0a6b`.

**Reproduction.** `grep -rn "MEASURED_JOINT" --include=*.py .` returns nothing.

**Consequence.** Until the enum exists, the frontend cannot bind it with a parity
check, so a new role would arrive unnoticed.

**Interim rule (product-surface).** Any role the UI does not know renders as the
explicit UNKNOWN grade `?` — never as measured, never as the strongest grade.

**Owner.** analysis-governance (A6) publishes the role enum in `aia_core.domain`;
product-surface then adds it to `apps/web/src/design/enums.ts` and the parity
check (`.planning/plans/design-system.md`, chunk 2).

**Update (2026-09-25).** The enum now exists in part: `domain/evidence/field_policy.py`
defines 22 field `EvidenceStatus` values. What is still missing is the **mapping
from those statuses onto the five print grades** (measured / calibrated /
modelled / holdout-pending / unknown). The report takes that mapping as data:
`EvidenceLedger.field_grades` (`domain/report/evidence.py`,
`grade_of`). Until analysis-governance supplies it, the report prints every
measured-basis number as `?` (a `MODELED` basis always prints as modelled).
The rules are pinned by `test_report_model.py::test_a_field_without_a_grade_prints_unknown_never_measured`
and `test_several_fields_not_jointly_measured_never_print_measured`. Decision
R-D4 in `.planning/plans/report-docx.md`.

**Status.** Open. Cross-context dependency.

---

## OI-10 · Question · `ImpactPreviewEstimate` — no cost or duration for an edit

**Claim.** The impact preview must show what re-running the invalidated stages
will cost in money and time, but the domain `ImpactPreview` carries only
`root_stage`, `invalidate`, `preserve` and `presentation_only`.

**Anchor.** `packages/aia_core/src/aia_core/domain/pipeline.py:423 @ 17c0a6b`.

**Consequence.** A researcher commits an edit without seeing its price. The UI
shows cost and duration as explicitly unavailable; it must not compute them.

**Owner.** integration-architecture, with input from research execution
semantics, the cost ledger / historical usage, and possibly runtime duration
history. product-surface owns the UI contract only and does not build the
estimator.

**Status.** Open. Cross-context dependency.

---

## OI-11 · Question · No "what needs this viewer" contract

**Claim.** Portfolio must answer "what needs me today?", but no API states whether
a parked item is actionable by the authenticated viewer; the status enum alone
cannot say it (DS-3: `WAITING_CREDITS` needs a person, not necessarily this one).

**Anchor.** No field exists on any response schema under `apps/api/src/aia_api/schemas/`
@ 7d42285.

**Consequence.** Without it, the UI either guesses (and pages the wrong person) or
shows nothing personal. Until it exists the UI shows the raw system state and
never presents an item as assigned to the viewer.

**Proposed shape (the exact shape is an integration decision).** Per parked item:
`action_required: bool`, `action_kind`, `viewer_can_resolve: bool`,
`required_permission`, `waiting_reason`.

**Owner.** integration-architecture / platform-runtime.

**Status.** Open. Cross-context dependency.

---

## OI-12 · Question · `clients.accent_slot` changes the Client persistence contract

**Claim.** DS-2 persists a presentation slot per client; a hash of the client id
alone collides at five clients (`cl_salvia` and `cl_tecka` both map to 4 under
FNV-1a mod 6).

**Contract.** A smallint in 1–6, assigned server-side at client creation by the
least-used strategy, immutable afterwards, never chosen by browser input. It is a
presentation and scope cue — not a security boundary, not an identifier, not
globally unique. Name, monogram and the scope chrome stay authoritative.

**Owner.** integration-architecture is notified before the migration lands;
product-surface implements it (`.planning/plans/design-system.md`, chunk 4).

**Status.** Open. Migration held until integration-architecture acknowledges.

---

## OI-13 · Gap · The reference's Python unfolding cannot be reproduced without its source

**Claim.** `python_weighted_unfolding` — the layout every local reference run
actually used — is refused by the engine, because fixture F4 pins its output but
not its method, and its source is in the withheld archive.

**Anchor.** `LAYOUT_ALGORITHMS` in `packages/aia_core/src/aia_core/domain/sociomap/layout.py`;
test `test_legacy_algorithms_fail_closed_and_say_why`. Reference:
`golden-fixtures/F4_python_unfolding_layout.json` @ AIA-reference `678e298`.

**Reproduction.** `require_layout_algorithm("python_weighted_unfolding")` raises
`LayoutUnavailable` naming `REF-WITHHELD-REFERENCE-ARCHIVE`. The evidence that it
cannot be reconstructed: ~200 candidate stress definitions (target transform ×
disparity fit × normalisation) evaluated on F4's own coordinates; none gives
`stress_1 = 0.391394498` (closest 0.3923).

**Consequence.** Production maps are laid out by `aia_rowcond_unfolding_v1`,
which is **not numerically comparable to any legacy map**: on F4's ratings the
two configurations differ by Procrustes RMSD 1.91 against a radius of 2.01. A
client comparing a new map to a legacy one would see different geometry.

**Smallest fix.** Read `sociomap.fit_python_unfolding` from the archive once the
licence decision releases it (or have the data owner extract that one function),
port it under its own identifier, and assert F4 at `1e-6`.

**Test that would catch it.** F4 itself, once the port exists:
`test_f4_python_unfolding_matches_the_reference` at tolerance `1e-6`.

**Status.** Open, blocked on `REF-WITHHELD-REFERENCE-ARCHIVE`. Owner:
sociomapa-deterministic.

---

## OI-14 · Gap · Object-map base layout (`baseObjectLayout66`) is unrecovered

**Claim.** The reference places objects on the object map with a 1,235-character
frontend function, `baseObjectLayout66(effectiveMatrix66())`, whose source is
withheld; F8's expected terrain depends on those positions, so F8 is reproduced
only in part.

**Anchor.** `ui-capability-ledger.json` entry `baseObjectLayout66` @ AIA-reference
`678e298`; tests `test_f8_uses_the_reference_constants_and_bounds`,
`test_f8_height_to_elevation_chain`.

**Reproduction.** F8 gives the object matrix and metric values but not positions;
a 2,000-start least-squares inverse fit of four object positions to F8's three
finite samples found no placement consistent with them and with
`finite_hr_cells = 1655`.

**Consequence.** Production object positions come from the ratings unfolding,
not from the relation matrix. A scenario edit to the relation matrix therefore
changes object *heights* but never object *positions*, whereas in the reference
it may move objects. The kernel-weighted-mean semantics, constants and bounds are
verified; the end-to-end F8 field is not.

**Smallest fix.** Obtain the function (or a fixture of its output positions for
F8's matrix), port it as a declared object-layout option, and assert F8 end to end.

**Test that would catch it.** `test_f8_object_terrain_matches_the_reference`,
comparing every sample, `sum_ht` and `finite_hr_cells`.

**Status.** Open, blocked on `REF-WITHHELD-REFERENCE-ARCHIVE`.

---

## OI-15 · Gap · `REF-GAP-SOCIO-R-SMACOF` — R numerical parity is not claimed

**Claim.** No fixture characterises the reference's R branch
(`fit_r_smacof`, R `smacof::unfolding`, row-conditional), so `r_smacof_unfolding`
is refused and no R parity is claimed anywhere.

**Anchor.** `reference-gaps.md` § REF-GAP-SOCIO-R-SMACOF @ AIA-reference `678e298`;
test `test_legacy_algorithms_fail_closed_and_say_why`.

**Reproduction.** Measured in a cloud session on 2026-09-22: `apt-get install
r-base-core` succeeds (R 4.3.3), but CRAN is unreachable through the session's
network policy (`available.packages()` → *cannot open URL …/PACKAGES*) and no
`r-cran-smacof` package exists in the apt archive, so `smacof` cannot be
installed. **The environment is no longer the only blocker:** the gap's recipe
runs the *reference's* `sociomap.fit_unfolding(method="r_smacof")`, whose wrapper
(which `smacof` arguments, which target) is in the withheld archive. Running
`smacof::unfolding` with guessed arguments would characterise R, not the
reference.

**Consequence.** Parity with the reference's primary layout contract is unknown.
The size of the reference's own host-dependence defect (R vs Python coordinates
for one study) is also still unmeasured.

**Smallest fix.** On a host with CRAN access and the archive: run the recipe in
`reference-gaps.md` to emit `F12_r_smacof_unfolding_layout.json`, vendor it here
under `fixtures/sociomap/`, then decide whether `r_smacof_unfolding` becomes an
implemented algorithm (an R adapter in `infrastructure/`, failing closed when R is
absent) or stays refused.

**Test that would catch it.** `test_f12_r_smacof_layout_matches_after_procrustes`,
comparing aligned coordinates *and* pairwise distances at the tolerance the
reference's `parity-plan.md` records for F12.

**Status.** Open. Owners: parity-quality + sociomapa-deterministic.

---

## OI-16 · Question, decided · The AIA layout and its declarations need methodology sign-off

**Claim.** Four spec values in `AIA_SOCIOMAP_V1` are AIA declarations, not
recovered reference behaviour: the dissimilarity target `scale_top_minus_rating`,
the layout `aia_rowcond_unfolding_v1`, the map frame (`max_abs_to_extent`, 45),
and relation missing-data `refuse`.

**Anchor.** `AIA_SOCIOMAP_V1` in `packages/aia_core/src/aia_core/domain/sociomap/specification.py`
(each value is commented with its source); `docs/architecture/sociomapa-deterministic-engine.md` §5.

**Consequence.** Adopting a spec for a client study is a group-D decision
(`sociomapa-deterministic-engine.md` §1). Until a methodology owner accepts these
four values, a production map is reproducible and auditable but its methodology
is the engineering team's, not the product's.

**Smallest fix.** The methodology owner completes the four approval fields in
[`docs/architecture/sociomapa-methodology-decision.md`](../docs/architecture/sociomapa-methodology-decision.md):
ACCEPT, REPLACE or DEFER per declaration, each with the evidence, the
consequence, the real alternatives and legacy comparability. The answer is
recorded there, here and in D6.

**Status.** Decided for `aia-sociomap-3`, 2026-10-13: the product owner chose to use the
current methodology, `aia-sociomap-3`, in reports as it stands (PROGRESS D6), and it is the
Sociomap register's entry (`domain/sociomap_register.py` @ `ab91373`, #385). The four
`aia-sociomap-1` declarations this item lists stay unapproved, so its map stays
`INTERNAL_ONLY`; nothing here asks for them any longer, because new runs draw the object map
of `aia-sociomap-3`.

---

## OI-17 · Requirement, closed · No gate yet stops an unapproved Sociomap reaching a client

**Claim.** Nothing yet checks that a Sociomap entering a client deliverable was
computed under an approved methodology. The engine computes any supported spec
by design, and approval is product policy that the engine must not know.

**Anchor.** `docs/architecture/sociomapa-deterministic-engine.md` §13, rule 2;
`tools/layer_check.sh` "… never substitutes the Sociomap preset" (rule 3, the
part enforceable today).

**Consequence.** As soon as a route, job or export can emit a Sociomap, an
artifact computed under unapproved `aia-sociomap-1` could be delivered. No such
path exists yet — the worker, API and web wiring are all blocked — so there is
no exposure today.

**Smallest fix.** An approved-methodology registry in product policy, entries
`(methodology_version, spec_fingerprint, approver, date)`, and one check at the
client-deliverable boundary that refuses an artifact whose pair is not in it.
Cross-context: **owned by integration-architecture** with product policy; it
belongs with the approval/gate machinery, not in the Sociomap engine.

**Test that would catch it.** A deliverable-boundary test: an artifact under an
unregistered `(version, fingerprint)` pair is refused, the same pair after
registration is accepted, and a registered version with a different fingerprint
is refused.

**Status.** Open, not yet exposed. Must land before, or with, the first path that
can emit a Sociomap to a client. *2026-09-27:* the Consequence's "no such path exists
yet" is stale. The `sociomap` research step and its route exist
(`apps/executors/src/aia_executors/research.py` `SociomapExecutor`,
`apps/api/src/aia_api/routers/research.py` `_RESEARCHERS_ONLY`), and the artifact is
`INTERNAL_ONLY`; `research_sociomap.require_client_facing` refuses it while D6 is open.
The exposure is still nil, and the registry this item asks for is still owed.

*2026-10-13, closed by #385 (complete-study-report B4).* The registry is
`SOCIOMAP_REGISTER` (`packages/aia_core/src/aia_core/domain/sociomap_register.py` @ `21c29a0`):
entries `(method_id, spec_fingerprint, status, decided_by, decided_on, record)`; a map's status
is read from it whenever the map is read; the client composer draws only maps it approves and
`require_client_facing` still refuses any other. Tests:
`test_sociomap_register.py::test_anything_else_is_internal_never_presumed_approved` (an
unregistered pair and a registered id at another fingerprint refused) and
`::test_the_owners_decision_approves_aia_sociomap_3_exactly_as_the_code_computes_it`.

---

## OI-18 · Question · Gate decisions that only the withheld legacy source can confirm

**Claim.** Five decisions in the evidence layer are fail-closed *readings* of the
reference, because the legacy source is withheld with the archive
(`REF-WITHHELD-REFERENCE-ARCHIVE`) and the reference repository records only
excerpts, constants and thresholds for them:

| Decision | Reading taken | Recovered evidence |
| --- | --- | --- |
| `tier_gate.py` Tier B permissions | aggregate, demographic breakdown, internal experimental; nothing else | docstring excerpt stops at "demographic breakdowns ma…" |
| `tier_gate.py` Tier C | internal experimental only | not in the excerpt at all |
| `core_joint._fallback()` values | every `*_allowed` false, no matched block certified | only that it exists and when it is used |
| `uncertainty.py:129` `nlayer < 50` | donor-layer *indicative* line | the threshold, not the branch it guards |
| `factual_layer.py` `fact_kind="fact"` without a source field | refused | docstring excerpt stops at "…wi" |

**Anchor.** Tests `test_evidence_validation.py::test_tier_permits`,
`test_evidence_joint_status.py::test_degraded_status_permits_nothing`,
`test_evidence_support.py::test_donor_layer_support`,
`test_evidence_claims.py::test_metadata_that_would_need_an_invented_fact_is_refused`.

**Reproduction.** With the archive: `export AIA_LEGACY_REFERENCE=…` and read the
five functions; each test above states the decision it pins.

**Consequence.** Each reading is stricter than or equal to any plausible
reference behaviour, so the risk is over-blocking, not an unsupported claim
reaching a client. None is asserted as parity in `test_evidence_gate_parity.py`.

**Smallest fix.** Once the archive is available (D3 / the licence decision),
turn each row into an EXACT parity case against the legacy function and correct
the reading if it differs.

**Status.** Open, blocked on the archive.

---

## OI-19 · Question · RELIGION is donor-matched but not named in the joint certificate

**Claim.** The five `RELIGION` fields are `MATCHED_WHOLE_BLOCK_CANONICAL`
(donor-matched), and the reference certificate's `matched_blocks` lists six
blocks that do not include it. The claim gate therefore refuses every
client-facing claim on them, although the field dictionary marks them eligible.

**Anchor.** `test_evidence_gate_parity.py::test_claim_gate_never_permits_what_the_reference_policy_forbids`
(asserts the narrowing is exactly `{"RELIGION"}` over all 400 fields) and
`test_evidence_joint_status.py::test_uncertified_matched_block_is_refused_client_facing`.

**Reproduction.** `AIA_REFERENCE_REPO=../aia-reference pytest -k never_permits`.

**Consequence.** Religion cannot be reported to a client until this is decided.
The reference enforced neither the dictionary nor the certificate here, so it
would have reported it.

**Smallest fix.** A data-owner decision: either the certificate should name the
block (then it is re-issued and bound to the panel hash as usual), or the
refusal is correct. Not an engineering judgement.

**Status.** Open, with the data owner.
**Decided 2026-10-25 (the owner, OI-19 (b), the audit page, relayed by coordinator 3):** "re-issue the certificate naming the block
(religion)." Open until the certificate is re-issued naming `RELIGION`, bound to the panel hash as
usual, and the parity test's expected narrowing (`{"RELIGION"}`) moves with it.

---

## OI-20 · Finding · Automatic factual-question detection is not ported

**Claim.** The reference `factual_layer.py` classifies common factual survey
questions automatically and maps them to panel fields. Only its explicit-metadata
contract is ported; a question with no metadata resolves to `UNDECLARED`.

**Anchor.** `test_evidence_claims.py::test_no_metadata_is_undeclared_not_factual`.

**Reproduction.** `resolve_factual_contract(QuestionFactMetadata(), book)` returns
`UNDECLARED` for "Kolik je vám let?".

**Consequence.** Until the respondent engine exists nothing consumes this. When
it does, it must treat `UNDECLARED` as "not proven factual" — so a factual
question without metadata is answered by simulation rather than read from the
panel, which is the reference's defect class, inverted: never an invented fact,
but a fact the panel held that was not used.

**Smallest fix.** Port the keyword classification from the legacy source once
the archive is available, with a golden fixture of classified questions.

**Status.** Open, blocked on the archive; must close before Phase 5's respondent
engine ships.

**Update 2026-09-25 (Agent Runtime Foundation) — narrowed, not closed.** The keyword
classification, the choice mapping and the deterministic answer are ported for the AI
respondent (`packages/aia_core/src/aia_core/domain/respondent_facts.py` @ `dec2fd1`),
compared with the vendored unit's own `factual_layer.py`, not the archive
(`test_respondent_facts.py::test_classification_matches_the_unit`, 39 cases;
`::test_choice_mapping_matches_the_unit`, 12). A DIRECT fact is answered from the
persona and never asked; an UNSUPPORTED one refuses the fieldwork step. Still open:
`evidence/factual.py` (the claim gate's contract) does not use it, questions carry no
`fact_kind` / `fact_source_field` metadata, and `harmonize_project_fact_choices` is not
ported.

---

## OI-21 · Finding · A provider park can auto-resume a possibly-billed call

**Claim.** When an attempt fails with `QUOTA` — or `BUDGET_EXCEEDED` or
`APPROVAL_REQUIRED` — while a dispatched paid call has no recorded outcome,
`decide_recovery` parks the step instead of returning `RECOVERY_REQUIRED`, so a
quota park re-issues the call automatically once its reset instant passes.
`PROVIDER_CAPACITY` is not affected: its branch comes after the uncertain-billing
branch, and a test already asserts that ordering.

**Anchor.** `packages/aia_core/src/aia_core/domain/workflow.py:527-558 @ 17c0a6b`
— the approval, budget and quota branches (527, 534, 545) all return before the
`paid_call_dispatched and not paid_call_outcome_known` branch (558).

**Reproduction.**
`packages/aia_core/tests/test_workflow_reservations.py::test_a_park_with_a_call_in_flight_still_records_the_exposure`
— the step goes to `WAITING_PROVIDER` with the call still in flight.

**Consequence.** Possible double billing on resume. The *accounting* is already
safe — the closing rule charges the in-flight reservation as
`SETTLED_UNCERTAIN` whatever the decision — so the budget is not overstated; the
risk is the second provider call itself.

**Why it is not simply reordered.** A quota refusal is a provider *response*:
the call was answered, so its outcome is known and it was not billed. The
contradiction only arises when an executor reports `QUOTA` without recording that
outcome. Whether the fix belongs in `decide_recovery` (billing uncertainty
outranks every park) or in the executor contract (a provider refusal must settle
the call at zero first) is a domain decision, and `decide_recovery` is parity-
covered by `test_legacy_job_store_characterization.py`, which CI cannot run
(OI-1).

**Smallest fix.** Move the uncertain-billing branch above the `QUOTA` branch in
`decide_recovery`, after a parity run confirms the prototype does not depend on
the current order.

**Test that would catch it.** A `decide_recovery` unit test:
`failure=QUOTA, paid_call_dispatched=True, paid_call_outcome_known=False` →
`RECOVERY_REQUIRED`.

**Status.** Open. The worker's executor contract (`aia_worker.executor`) tells
executors to settle a refused call at zero before reporting the refusal, which
closes the path for every executor that follows it.

---

## OI-22 · Question, closed · Should revoking a researcher stop the runs they started?

**Claim.** A worker executes a claimed attempt under a scope issued from the lease
(`ScopeResolver.execution_context`), with the run's `triggered_by` as actor. It
does **not** re-check that the triggering user is still active or still holds a
grant on the study, so a run started by someone since deactivated or revoked runs
to completion.

**Anchor.** `packages/aia_core/src/aia_core/application/scope.py`
`ScopeResolver.execution_context` @ this change — the only denials are
`unknown_attempt`, `lease_not_held`, `scope_mismatch` and `client_archived`.

**Consequence.** None known to be harmful yet: the run was authorised when it was
created (`create_run` requires `RUN_WORKFLOW` on an open study), and a LEAD can
cancel it. But interactive access is revoked immediately on deactivation
(`ScopeResolver._active_user`), and background work is not, which is an
inconsistency somebody should choose deliberately.

**Options.** (a) Keep as is: authority is fixed at run creation. (b) Re-resolve
the triggerer on each attempt and `WorkQueue.refuse` when it fails — fail closed,
at the cost of stranding a leaver's in-flight studies until someone re-triggers
them. (c) (b), but reassign rather than refuse, which needs a product rule for
who inherits.

**Status.** Closed 2026-10-25 by decision: the owner chose (a), "runs keep going when a researcher
leaves" (OI-22 (a), the audit page, relayed by coordinator 3). Authority stays fixed at run creation; nothing to build. Earlier:
Open. A product/security decision, not an engineering one.
**2026-10-05:** since ADR 0019 there are no client or study grants (dropped by #120), so the
only re-check left to decide is that the triggerer is still active and still a member of the
organization; and any Researcher, not only a LEAD, can cancel the run.

---

## OI-23 · Finding, closed · Secret-redaction patterns are defined twice

**Claim.** The provider-key shapes that must never reach a log or an attempt's
`error_json` are defined in the API and restated in the worker, so a new key
shape added to one is silently missing from the other.

**Anchor.** `apps/api/src/aia_api/observability.py` `_SECRET_VALUE_PATTERNS` and
`apps/worker/src/aia_worker/observability.py` `_SECRET_VALUE_PATTERNS` @ this
change. The worker may not import the API (`tools/layer_check.sh`: "the worker
never imports the API"), which is why it was restated rather than shared.

**Reproduction.** Add a pattern to one file and run
`apps/worker/tests/test_worker_loop.py::test_an_unclassified_exception_is_permanent_and_its_message_redacted`
with a key of the new shape: it is not redacted.

**Consequence.** A provider key in an executor's exception text reaches the
database and the worker log. Anti-pattern A6 (producer/consumer drift) in a
security-relevant place.

**Smallest fix.** Move the value patterns and `redact_text` into a pure module
in `aia_core` (no framework imports, so it may live in `domain/`) and import it
from both.

**Test that would catch it.** One parametrised test over both redactors with the
same key fixtures, asserting identical output.

**Status.** Closed by #432: the patterns and `redact_text` live in
`packages/aia_core/src/aia_core/infrastructure/redaction.py` @ `f5383923`, imported by both
observability modules and the error reporter; a JWT shape was added there.
`packages/aia_core/tests/test_error_tracking.py::test_redaction_by_key_and_by_value_shape`.

---

## OI-24 · Finding · Two field policies and two joint certificates, with different rules

**Claim.** The field dictionary's claim policy and the `CORE_JOINT_STATUS` gate are
each implemented twice, under the same names and with different semantics:
`aia_core.domain.evidence` (`FieldPolicyBook`, `JointStatus`, used by the claim
gate, admission and the analysis modules) and `aia_core.domain.population`
(`FieldPolicy`, `JointStatus`, carried by `RuntimePopulation` and recorded on the
run binding). Anti-pattern A6: one concept, two definitions, drifting.

**Anchor.** `packages/aia_core/src/aia_core/domain/evidence/field_policy.py`,
`evidence/joint_status.py` (PR #22) and
`packages/aia_core/src/aia_core/domain/population/policy.py`,
`population/companions.py` @ `121b746` (PR #19).

**Reproduction.** Over the real 400-field dictionary the two disagree on which
fields may back a client-facing measured claim: the evidence policy follows the
reference export (287 eligible, `test_evidence_gate_parity.py::test_every_reference_field_rederives_identically`),
the population policy is deliberately stricter (115, a strict subset, per `c872cd7`).
`layer_check`'s "a joint status is issued only by its loader" rule needs a named
exemption for `companions.py` because the second `JointStatus` is built there.

**Consequence.** An analysis claim is admitted under the evidence policy while the
run that produced the population records the population policy. A field the
population policy refuses for client claims can still be admitted by the evidence
gate, and nothing ties the two versions together.

**Smallest fix.** A decision first: one authority. The likely shape is the
population's `FieldPolicy` and `JointStatus` as the single source (they are bound to
the loaded population and the run), with the evidence claim gate and admission
consuming them in place of their own copies — keeping the evidence layer's
claim rules, joint-unit rules, support and admission, and its parity tests
retargeted. Then drop the `companions.py` exemption.

**Test that would catch it.** One parity test asserting a single eligibility per
field for client measured claims, and `layer_check` green with no exemption.

**Status.** Open, needs a decision from the owner of both.
**Decided 2026-10-25 (the owner, OI-24 (a), the audit page, relayed by coordinator 3):** "the population's policy (stricter, 115
fields) is the one authority." Open until the evidence claim gate and admission consume the
population's `FieldPolicy` and `JointStatus` (the smallest fix above) and the `companions.py`
exemption is dropped; no plan chunk builds it yet. No owner yet; the coordinator is finding one.
**2026-10-25:** owned by `evidence-integrity#5` (S2, W0; "One field-policy authority per evidence source"), agreed by the coordinator 2026-10-25.

---

## OI-27 · Gap · `REF-GAP-SIMULATION-WORLD-MODEL` — no fixture for world-model inoculation

**Owners.** parity-quality + A7 simulation-engine.

**Claim.** The simulation engine's only numerical fixture (F13) is uncaptured,
so `simulation.engine` has no gate that could ever pass.

**Anchor.** AIA-reference `reference-gaps.md` "REF-GAP-SIMULATION-WORLD-MODEL"
@ 678e298; fixture `F13_simulation_world_inoculation` in
`docs/migration/parity-matrix.json`.

**Blocker — wider than the reference records.** The reference lists only a
provider credential. The recipe also runs the legacy `build_world_model` and
`inoculate_population` (withheld archive) against population `v17_4_0`, and the
provider call must leave through an egress route approved under
[ADR 0008](../docs/architecture/adr/0008-eu-data-residency.md) — the boundary
currently approves nothing.

**Consequence.** Simulation is off the MVP path (decision D9 in `overview.md`), so this
blocks no release today; it blocks the first release that ships the Simulation
lifecycle.

**Smallest path.** Freeze one sanitised world model (with its sha256) as fixture
*input* so deterministic parity never depends on a model reproducing tokens;
then capture F13 deterministically. The model call happens once, not per CI run.
A7 decides in the meantime whether production **rejects** out-of-range model
output (the intentional difference `SUB-SIM-BOUNDS`) — that decision needs no
fixture.

**Definition of done.** As in `parity-matrix.json` `reference_gaps`.

**Status.** Open, blocked on credential, egress route and archive. The
deterministic core the fixture would test now exists without it (PR #27,
`aia_core.domain.simulation`), and `test_simulation_parity.py` is the scaffold
that reads F13 through `AIA_REFERENCE_REPO` and skips until it is captured.
The `SUB-SIM-BOUNDS` question above is **decided: production rejects**, one row
per field in `reference.FIELD_POLICY`, gated by `simulation.engine/contract`
(`test_production_rejects_what_the_reference_corrected`,
`test_every_recorded_difference_is_exercised`). Full status:
`docs/architecture/simulation-deterministic-engine.md` §7.

---

## OI-28 · Finding · The reference links a weighting fixture to cost reservations

**Claim.** The reference parity plan lists `F11_analysis_weight_fallback_chains`
as a fixture of `cost.reservations`; F11 exercises no reservation.

**Anchor.** AIA-reference `parity-plan.json`, capability `cost.reservations`,
`fixtures` @ 678e298. Recorded as `REF-DISC-1` in
`docs/migration/parity-matrix.json`.

**Reproduction.**
`python3 -c "import json;print([c['fixtures'] for c in json.load(open('../aia-reference/parity-plan.json'))['capabilities'] if c['capability']=='cost.reservations'])"`
→ `[['F11_analysis_weight_fallback_chains']]`, while
`golden-fixtures/manifest.json` names F11's capability `population.weighting`.

**Consequence.** Carried verbatim, a passing weighting gate would count as
parity evidence for a money control.

**Smallest fix.** Correct the link upstream and re-run
`tools/build_parity_plan.py`; then drop `REF-DISC-1` here.

**Test that would have caught it.** `test_golden_fixtures.py::test_matrix_agrees_with_the_reference_parity_plan`
now asserts every link except the recorded rejection.

**Status.** Open upstream; not carried here.

---

## OI-29 · Finding · `cost.reservations` ships with no reference-backed parity gate

**Claim.** Study budget reservations are `IMPLEMENTED` and owe **EXACT** parity
with the reference's `cost_controller`, but every test of them is
production-only; nothing compares a reservation decision with the reference's.

**Anchor.** `docs/migration/parity-matrix.json` capability `cost.reservations`
(gates `cost.reservations/contract`, `cost.reservations/contention`, both
`production_contract`).

**Reproduction.** `python tools/parity_status.py --markdown /dev/stdout` → the
highest-risk list names `cost.reservations: IMPLEMENTED, EXACT parity, verdict
NOT_RUNNABLE … no reference-backed gate`.

**Consequence.** A divergence in the decision at the limit, in settlement, or in
uncertain-settlement charging would merge green. This is money (high-risk R10)
on the MVP path, which is why the verdict tool ranks it in its top two.

**Smallest fix.** A characterization suite for the legacy `cost_controller`
(as `test_legacy_job_store_characterization.py` did for `job_store`), then
comparison tests over the same decision matrix — a `reference_characterization`
and a `reference_comparison` gate. Both need the legacy tree, so they run
locally until the archive question is settled.

**Test that would have caught it.** Those gates.

**Status.** Open. Owner unconfirmed (matrix workstream `cost`), with parity-quality.

---

## OI-30 · Finding · The module inventory lags the ports that landed

**Claim.** `docs/migration/module-dispositions.json` still records modules as
`not-started` whose behaviour is now ported, so the inventory and the parity
matrix disagree about what exists.

**Anchor.** `docs/migration/module-dispositions.json` entries `sociomap.py`,
`study_validation.py`, `kalibrace.py`, `mrp.py`, `scheduler.py`,
`worker_daemon.py`, `worker_job.py` (`state: not-started`) @ 8978b99; against
`packages/aia_core/src/aia_core/domain/sociomap/`,
`packages/aia_core/src/aia_core/domain/population/`, `apps/worker/`.

**Reproduction.**
`python3 -c "import json;d={m['module']:m['state'] for m in json.load(open('docs/migration/module-dispositions.json'))['modules']};print({k:d[k] for k in ['sociomap.py','worker_job.py','scheduler.py']})"`
→ all `not-started`.

**Consequence.** `test_parity_matrix.py` refuses to call a capability
`IMPLEMENTED` while its modules read `not-started`, so `population.weighting` and
`workflow.dispatch` stay `PARTIAL` although their targets are met; and the
inventory's own completeness guard no longer tells anyone what is done.

**Smallest fix.** Each owning workstream updates its modules' `state` (and
`note`) in the same change that ports them; for these, one catch-up edit per
owner.

**Test that would catch it.** `test_parity_matrix.py::test_implementation_state_agrees_with_the_module_inventory`
already enforces one direction; the other direction needs the ports to name
their modules.

**Status.** Open. Owners: sociomapa-deterministic, population-data, and the
worker's owner, each for its own modules.

---

## OI-31 · Finding · Two different fixtures are both called F12

**Claim.** The reference names F12 the R smacof layout fixture, and this
repository's population enrichment document names a different fixture F12.

**Anchor.** AIA-reference `reference-gaps.md` "REF-GAP-SOCIO-R-SMACOF" step 5
(`F12_r_smacof_unfolding_layout.json`) @ 678e298, and OI-15 here;
`docs/migration/population-enrichment-archive-dependency.md` ("F12 —
`population.enrichment`"). Recorded as `REF-DISC-2` in `parity-matrix.json`.

**Reproduction.** `grep -rn "F12" docs/migration/population-enrichment-archive-dependency.md .planning/open-items.md`.

**Consequence.** Whichever is captured first takes the id, and a gate or pin
naming "F12" then points at the wrong fixture.

**Smallest fix.** Give the enrichment fixture an unused id (F14 or later) in that
document and upstream; the matrix keeps the reference's F12.

**Test that would have caught it.** `test_parity_matrix.py` rejects an unknown
fixture id; a document outside the matrix is not covered.

**Status.** Open. Owner: population-data, with parity-quality.

---

## OI-32 · Finding · `main` accepts a merge before its blocking checks have run

**Claim.** Nothing stops a pull request merging into `main` while its blocking
checks are red or have not started, so a rule that fails correctly still lets
the regression land.

**Anchor.** PR #26 (`coordination/agent-status`): opened 2026-09-23T00:43:20Z,
merged 00:43:31Z, eleven seconds later. Its *Backend (lint, types, tests)* job
started at 00:43:30Z and failed at 00:44:15Z on `exposure_check` rule 4
(`tools/exposure_check.sh`, "No agent coordination state in product history"),
job 106998296094. Merge commit `2dbe2cf`; removed again by `7a022b3`.

**Reproduction.** `./tools/exposure_check.sh` in a worktree of `2dbe2cf` fails
rule 4 on four `.agent-status/*.md` files. The PR's check runs show the failure
landing after `merged_at`.

**Consequence.** Every branch that merged `main` between `2dbe2cf` and
`7a022b3` went red on a failure that was not its own. That included this
simulation PR (#27, CI run 35803607692). The same thing had happened once
before, removed in `026577e`. A guard that is not required is advice.

**Smallest fix.** Branch protection on `main`: require the blocking jobs in
`ARCHITECTURE.md §8`, at least *Backend (lint, types, tests)*, before merge.
This is a repository setting. An agent session cannot apply it (the proxy
refuses settings writes, as with D5), so a human must.

**Test that would have caught it.** None can, from inside the repository: a
test runs in the check that the merge ignored. What a test can prevent is the
other silent path, the rule itself being weakened.
`packages/aia_core/tests/test_exposure_check_tool.py` runs the real script
against a scratch repository and fails if a tracked `.agent-status/` stops
failing the build.

**Status.** Open. Needs a repository admin.
---

## OI-33 · Finding · A repository's `ScopeDenied` reaches the client as a 500

**Claim.** A permission the *repository* checks (not the route dependency) is
unhandled by the API: a VIEWER creating a project gets `500 internal_error`
instead of `403 insufficient_role`.

**Anchor.** `apps/api/src/aia_api/routers/projects.py:146 @ a15be65`
(`repo.create(...)` → `repositories.py:332` `self._scope.require(Permission.EDIT_STUDY)`),
with no `ScopeDenied` handler in `apps/api/src/aia_api/observability.py:244-289 @ a15be65`.

**Reproduction.** In `apps/api/tests`, as the `viewer` client:
`viewer.post(f"/api/v1/studies/{world.study_id()}/projects", json={"title": "x"})`
returns 500 (log: `ScopeDenied: role VIEWER does not permit EDIT_STUDY`).
Confirmed 2026-09-23 against SQLite.

**Consequence.** The refusal is correct but unreadable: the client sees a generic
error and an alert fires for what is a normal authorization outcome. Nothing is
disclosed. The new `runs.py` router maps `ScopeDenied` itself (`_denied`) and so
does not have the defect; the projects and scope routers do.

**Smallest fix.** One `@app.exception_handler(ScopeDenied)` in
`install_exception_handlers`: `insufficient_role` and `study_closed` → 403 with
the scope router's `insufficient_role` shape; every other reason → the 404
`dependencies._not_found_for` already renders. Then delete `runs.py::_denied`.

**Test that would catch it.** `test_a_viewer_cannot_create_a_project_and_is_told_why`
asserting 403 and `code == "insufficient_role"` on `POST …/projects`.

**Status.** Open. Found while writing the run routes; deliberately not fixed in
the deployment change set (it touches every router's error contract).

---

## OI-34 · Finding · The web client has no test runner

**Claim.** `ARCHITECTURE.md §7` requires web tests ("Mount, events, auth
guards"); `apps/web` has no test framework, no test file and no `test` script.

**Anchor.** `apps/web/package.json:6-11 @ a15be65` (`scripts`: dev, build,
start, lint only).

**Reproduction.** `cd apps/web && npm test` → `Missing script: "test"`.

**Consequence.** The PKCE login (`src/lib/auth.ts`) and the API client
(`src/lib/api.ts`) landed with lint, `tsc` and a build as their only gates. Their
pure parts (PKCE encoding, session caching, error mapping) are testable today
and untested.

**Smallest fix.** Vitest with `jsdom`, as `plans/design-system.md` chunk 3 already
schedules; first tests on `auth.ts` (`parseBuildSha`-style pure functions,
`readSession` caching, `completeLogin` state mismatch) and `api.ts` (401 →
`Unauthenticated`). Owner: product-surface, with the design-system plan.

**Test that would catch it.** A CI step `npm test` that fails on a missing script.

**Status.** Runner half **closed**: Vitest landed in `23873d4` (2026-09-24),
`apps/web/package.json` `"test": "vitest run"`, and CI runs `npm test`
(`.github/workflows/ci.yml`, *Frontend*). Still open: `src/lib/auth.ts` and
`src/lib/api.ts`, the two files this item named, have no test file (2026-09-27).

---

## OI-35 · Decision · The browser session lives in `sessionStorage`

**Claim.** The live pages keep the Cognito id and refresh tokens in
`sessionStorage` for the tab's lifetime and send the id token as a bearer header.

**Anchor.** `apps/web/src/lib/auth.ts` (`SESSION_KEY`, `writeSession`) @ this change.

**Consequence.** Correct against CSRF (no cookie), same-origin only, cleared when
the tab closes; exposed to any XSS in the client. Accepted for `develop`
(synthetic data, five internal users) and recorded here so it is not mistaken
for the production shape.

**Smallest fix, when production is provisioned.** A same-site, `HttpOnly` cookie
session minted by the API after verifying the id token once (a `POST
/api/v1/session` that returns a cookie and a CSRF token), the browser holding no
token at all. The `IdentityProvider` seam is unchanged by that move.

**Status.** Open by decision. Trigger: the production environment.
**Decided 2026-10-25 (the owner, OI-35 (a), the audit page, relayed by coordinator 3):** "HttpOnly cookie session before
production." Open until it is built before the first production release; no chunk of
`production-environment.md` builds it yet. No owner yet; the coordinator is finding one.
**2026-10-25:** to be built by `production-environment#PE12` (S3, W1; "The browser holds no token"), added to the plan by #896 (merged as `5d5ed250`).

---

## OI-36 · Finding · Resolving an uncertain call corrects the ledger but not the study's spend

**Claim.** `AIUsageRepository.resolve_uncertain` appends the compensating ledger
entry, but `Study.spent_usd` keeps the full `SETTLED_UNCERTAIN` reservation
amount that `_settle_uncertain` charged, so the two disagree until something
reconciles the reservation -- and nothing does yet.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/ai_usage_repository.py:233`
(`resolve_uncertain`) and
`packages/aia_core/src/aia_core/infrastructure/workflow_repository.py:748`
(`_settle_uncertain`) @ this change.

**Reproduction.** Run
`test_ai_usage_ledger.py::test_worker_killed_mid_call_parks_for_a_person_and_the_ledger_can_find_it`
and, after the resolution, compare `attempt.usage.total_cost_usd()` (0.00027)
with `attempt.workflow.budget_position()["spent_usd"]` (1.0, the reservation).

**Consequence.** After an operator resolves an uncertain call as cheap or unbilled,
the study still shows the reservation as spent, so its budget headroom stays
understated until corrected by hand. The error is in the safe direction --
over-stated spend, never under-stated -- which is why it is filed rather than
patched across the ownership boundary.

**Smallest fix.** A `WorkflowRepository` method, owned by platform-runtime, that
takes a resolved call's compensation and writes a compensating adjustment to the
`SETTLED_UNCERTAIN` reservation and `spent_usd` (atomic, as `_charge_study` is).
The AI side already exposes everything it needs: the resolution entry carries
`reservation_id`, `attempt_id` and the compensation amount.

**Test that would catch it.** The reproduction above, asserting the two figures
agree after resolution.

**Status.** Open. Owner **platform-runtime**. Listed as ask 3 in
`docs/architecture/ai-step-executor-contract.md`.

---

## OI-37 · Finding · The deploy workflow cannot fire until it is on `main`

**Claim.** `deploy-develop.yml` is on `develop` only; GitHub registers
`workflow_run` and `workflow_dispatch` triggers from the default branch alone,
so the first CI-green head of `develop` was never deployed and no manual
rollback dispatch is offered.

**Anchor.** `.github/workflows/deploy-develop.yml:13-18 @ 262a6dd` (the `on:`
block); `git ls-tree origin/main .github/workflows/` lists `ci.yml` only @ `676bc1f`.

**Reproduction.** CI run 35836518940 on `develop` @ `262a6dd` completed
`success` at 2026-09-23 08:24:55 UTC; seventeen minutes later
`GET /repos/AiAnalytics-AIA/AIA/actions/workflows` listed one workflow (`CI`) and
`GET …/actions/workflows/deploy-develop.yml/runs` returned 404. Same check, one
command: `gh api repos/AiAnalytics-AIA/AIA/actions/workflows --jq '.workflows[].path'`.

**Consequence.** The chain `develop → CI → deploy` that the plan calls done stops
after CI, silently: no run, no failure, no *Run workflow* button. The human
actions in `infra/develop/README.md` would have been completed against a
pipeline that could not fire. Nothing was deployed wrongly; nothing was deployed.

**Smallest fix.** Put the file on `main`: a release PR `develop → main` (after
this change `develop ⊇ main`, so it is the repository's normal release and
carries PR #29 with it), or a `chore/` PR into `main` carrying only
`.github/workflows/deploy-develop.yml`. No code change. Recorded as human action
11 in `infra/develop/README.md`. Standing rule, now in `AGENTS.md` § GitHub
Actions: edits to that workflow take effect when they reach `main`, not `develop`.

**Test that would catch it.** Not a unit test — a repository-state property. A
`push`-to-`develop` job that fails when `.github/workflows/deploy-develop.yml`
differs from `main`'s copy (`git diff --quiet origin/main -- .github/workflows/deploy-develop.yml`)
would have turned the first green `develop` head red with the reason. It also
fails, correctly, for the window between merging a workflow change to `develop`
and releasing it; whether that noise is wanted is a human decision, so it is
proposed here and not added.

**Status.** **Closed 2026-09-23.** PR #32 (`fix/register-develop-workflow`)
put the file on `main` at `7f8cb2a`, merged 12:41 UTC;
`GET /repos/AiAnalytics-AIA/AIA/actions/workflows/deploy-develop.yml/runs`
now lists runs, the first (35863981545) dispatched by CI at 12:59 UTC from the
next `develop` merge (PR #33). The standing rule stays in `AGENTS.md` § GitHub
Actions. The first *green* dispatched run is still owed: runs 1–3 failed at
the OIDC trust (fixed by PR #34), the SSM script launch (same PR) and the API's
start-up on `AIA_CORS_ORIGINS=""` (PR #35, merged at `848ec11`). Run 4 on
`848ec11` deployed and failed only its smoke verdict (OI-38). The host is live
at <https://aia-develop.art-chain.io/>.

---

## OI-38 · Finding · The smoke check failed a reused artifact for naming its real producer

**Claim.** `slice_check` required the snapshot artifact's `runtime_version` to
equal the deployed build, but the snapshot executor reuses a VALID artifact
with the same content fingerprint by design, so every second deploy over the
unchanged develop seed reads back the *previous* build's artifact and the smoke
test fails a deployment that worked.

**Anchor.** `apps/executors/src/aia_executors/smoke.py:173-179 @ 848ec11` (the
single check); `apps/executors/src/aia_executors/snapshot.py:88-96 @ 848ec11`
(`put_json(..., input_fingerprint=..., runtime_version=self._build.sha)`, reuse
on) and `packages/aia_core/src/aia_core/infrastructure/artifact_repository.py:287-295 @ 848ec11`
(`find_reusable` returns the existing row, provenance untouched).

**Reproduction.** *Deploy develop* run 35869042785 on `848ec11`: 21 `ok` lines,
then `FAIL slice: the artifact was produced by the deployed build —
runtime_version 'b5c331f…', expected '848ec11…'`. Locally:
`test_slice_check_accepts_an_artifact_reused_from_an_earlier_build` in
`apps/executors/tests/test_seed_and_smoke.py` runs the check under a worker at
one build, then under a worker at another; it failed before the fix.

**Consequence.** The deploy is reported failed although the images, migration,
container replacement and every other check succeeded, and the host already
serves the new build. Operators learn to distrust the verdict; the *Confirm
from outside* step is skipped; the first green automatic deploy is postponed by
a check, not by the system.

**Smallest fix.** Check two facts separately: the step output's
`runtime_version` (the build that *executed* the run) must be the deployed one;
the artifact's `runtime_version` (the build that *produced* the bytes) must
match only when the output says `reused: false`, and otherwise the line reports
the reuse and both builds. Done in this change; the docstring says the same.

**Test that would have caught it.** The test above: two `slice_check` passes
over unchanged content with workers at different builds, the second expecting
its own build and asserting one stored object.

**Status.** Fixed in this change (`apps/executors/src/aia_executors/smoke.py`).
Verified by the dispatched run its merge triggers, not before.

---

## OI-39 · Finding · The oracle is deployed by a workflow that ran before the unit existed, and is unreachable from cloud sessions

**Claim.** The first *Deploy develop* run to build `aia-legacy-panel` failed
before deploying anything, the run that would deploy the unit is waiting on a
human, and no cloud session can reach the develop host to check either — so
Phase 0 of the strangler plan (a healthy, gated oracle) is unproven from here.

**Anchor.** `.github/workflows/deploy-develop.yml:128-141 @ 09810d1`
(`context: legacy/npc-panel-18.6.6`); `git ls-tree 71d3576 -- legacy` (only
`legacy/README.md`); `.planning/plans/legacy-strangler.md` § Phase 0.

**Reproduction.** GitHub Actions *Deploy develop* run 6 (`35880744530`) @
`71d3576`, step *Build and push aia-legacy-panel*: `ERROR: failed to build:
unable to prepare context: path "legacy/npc-panel-18.6.6" not found`. Run 7
(`35883107082`) @ `09810d1` (PR #39, the unit's files): job *Build, push and
deploy* `waiting` since 2026-09-23T15:39:11Z. From a cloud session:
`curl https://aia-develop.art-chain.io/api/v1/health` → `connect_rejected`
(egress policy); `docker ps` → no daemon.

**Consequence.** `legacy-panel` has not been deployed; the oracle parity gate
(`api.http/oracle-contract`) reports `NOT_EXECUTED`; slice 2 of the strangler
plan (HTTP differential recordings) cannot start until an operator either
approves run 7 or dispatches *Deploy develop* for `09810d1` or later, then adds
`AIA_LEGACY_REFERENCE_URL` / `_USER` / `_PASSWORD` as repository secrets for the
`oracle-parity` CI job (`ARCHITECTURE.md` §8 promotion table).

**Smallest fix.** Human: approve or re-dispatch the deploy at a SHA that carries
the unit, confirm `bin/smoke.sh` reports `legacy: hostname answers and the gate
refuses anonymous access (401)`, then provision the three secrets. No code
change: run 6 failed on ordering (PR #38 merged before PR #39), which cannot
recur now that both are on `develop`.

**Test that would have caught it.** None in this repository can: the failure is a
merge order across two PRs. The `oracle-parity` job with
`AIA_REQUIRE_LEGACY_ORACLE=1` is what turns a missing oracle into a red check
from now on.

**Status.** Open — human action. The engineering half (the endpoint contract,
the `oracle` marker, the CI job, `make test-oracle`) landed with slice 1.
2026-09-23 21:23 UTC: the operator cancelled run 7; run 8 (`35920580798`) @
`764f9f7` started in its place and failed pushing `aia-legacy-panel` — a code
defect after all, filed and fixed as OI-41. Still needed from the human, in
order: `terraform apply` in `infra/develop`, re-run run 8, confirm
`bin/smoke.sh`, provision the three secrets.
2026-09-23 23:34 UTC: `legacy-panel` deployed and healthy (run 12, smoke
`legacy: the 18.6.6 unit is healthy`), serving the product hostname behind the
gate (ADR 0012). The oracle hostname is not configured yet, so the parity gate
still reports `NOT_EXECUTED`: remaining are the three optional `aia_legacy_*`
hostname parameters (runbook § Switching the unit on), the DNS record, and the
three repository secrets.
2026-09-27 (ADR 0018 decision 5, increment 5 on `feature/deploy-without-legacy`): the
product deployment no longer runs the unit or serves an oracle hostname. The unit runs
from `deploy/reference/` behind its own basic-auth gate on the host's loopback,
`127.0.0.1:8765`, reached through an SSM port forward (`deploy/reference/README.md` §
Reaching it; `test_reference_setup.py` › *the unit is reached only through the gate on
the hosts loopback*). What the human actions become: the hostname parameters and the DNS
record are no longer needed (the record, if it exists, can be removed); the parity gate
needs a runner that can reach the host's loopback (inside the VPC, or on the host) and
the three repository secrets holding the reference gate's credentials. Until then an
operator runs `make test-oracle` through the port forward, and CI reports `NOT_EXECUTED`.

---

## OI-40 · Finding · The reference's UI ledger leaves `normalizer66` out of the 88 research functions

**Claim.** `AIA-reference/ui-capability-ledger.json` classifies
`ui_app.html::normalizer66` as `PRESENTATION_ONLY` although the reference's own
golden fixture F5 executes it as methodology and its "UI-only methodology rules"
table names its four modes and population-variance sd; the 88-function list a
port would follow therefore misses at least one research function.

**Anchor.** `AIA-reference/ui-capability-ledger.json` `functions[name="normalizer66"]`
(`class: PRESENTATION_ONLY`, `signals: ["compute:1"]`) @ `678e298`;
`AIA-reference/golden-fixtures/manifest.json` `F5_normalizer66_all_modes`;
`docs/migration/legacy-ui-functions.json` row `normalizer66`
(`source: aia_addition`).

**Reproduction.**
`python3 -c "import json;d=json.load(open('../aia-reference/ui-capability-ledger.json'));print([f['name'] for f in d['methodology_functions']+d['computation_functions'] if f['name']=='normalizer66'])"`
→ `[]`.

**Consequence.** A restructuring that ported exactly the 88 would leave the
normaliser in the browser, where it decides what "high" means on every map.

**Smallest fix.** Carry `normalizer66` as a recorded AIA addition in
`docs/migration/legacy-ui-functions.json` (done; discrepancy `REF-DISC-3` in
`docs/migration/parity-matrix.json`) and reclassify upstream in
`AIA-reference/tools/build_ui_ledger.py`; when the re-pinned ledger carries it,
the row's `source` returns to `reference_ledger`. The classifier's `compute:1`
signal on a 900-character numeric function suggests the threshold, not the
function, is the defect — worth a sweep of the other `PRESENTATION_ONLY`
functions with a `compute` signal before slice 7.

**Test that would have caught it.** `test_legacy_ui_functions.py::test_the_ledger_holds_the_88_research_functions_and_names_every_addition`
pins the addition; the sweep above would be its widening.

**Status.** Open — upstream (AIA-reference). Carried here as an addition.

---

## OI-41 · Finding · The deploy role could build the fourth image but not push it

**Claim.** `infra/develop/main.tf` still declared three images, so the ECR
repository `aia-legacy-panel` was never created and the deploy role's push
grant never named it; the first deploy that carried the unit built the image
and was refused at the push.

**Anchor.** `infra/develop/main.tf:12 @ 764f9f7`
(`images = ["aia-api", "aia-worker", "aia-web"]`);
`infra/develop/github.tf:84 @ 764f9f7` (`resources = [for r in
aws_ecr_repository.images : r.arn]`);
`.github/workflows/deploy-develop.yml:128-141 @ 764f9f7` (the fourth push).

**Reproduction.** GitHub Actions *Deploy develop* run 8 (`35920580798`) @
`764f9f7`, step *Build and push aia-legacy-panel*: the build completes, then
`failed to push 311141567391.dkr.ecr.eu-central-1.amazonaws.com/aia-legacy-panel:764f9f7…:
unexpected status from HEAD request to …/v2/aia-legacy-panel/blobs/sha256:4f4fb7…: 403 Forbidden`.
`aia-api` and `aia-worker` pushed in the same run. Locally:
`pytest packages/aia_core/tests/test_deploy_images.py` fails on `764f9f7` and
passes with the fix.

**Consequence.** No deploy of `develop` has succeeded since the unit landed
(runs 6, 7 and 8); the host still runs `85d8d00` (run 5), no migration after it
has been applied, and the oracle is still not deployed (OI-39). The failure
mode is the expensive one: two images pushed, the third refused, the deploy
never reached the host — so nothing is half-deployed, but every push to
`develop` since 15:19 UTC has been silently undeployable.

**Smallest fix.** Add `aia-legacy-panel` to `local.images` — the one list that
is both the repository set and the push grant — with the docs that count the
repositories (done in this change). Then, by the operator: `terraform apply` in
`infra/develop` (plan: one `aws_ecr_repository`, one lifecycle policy, an
in-place update of the `aia-develop-github-deploy` inline policy and the
instance role's pull grant), and *Re-run failed jobs* on run 8.

**Test that would have caught it.** `packages/aia_core/tests/test_deploy_images.py`
(added here): the images the workflow pushes, the images the compose file
pulls and `local.images` in the Terraform must be the same set. Terraform does
not run in CI, so a text-level check is the only one that fires before
`apply`; the test explains why it parses with regular expressions.

**Status.** **Closed.** The operator applied Terraform (PROGRESS, Completed ›
strangler 2), deploy run 12 went green with the unit healthy, and every deploy since
builds and pushes `aia-legacy-panel` (run 26, step *Build and push aia-legacy-panel*,
success, 2026-09-27). The oracle's own secrets remain OI-39.

## OI-42 · Finding · A refused study request's audit row is rolled back with the request

**Claim.** `ScopeResolver` writes `ACCESS_DENIED` and `PERMISSION_DENIED` rows
into the request's session and then raises; the API turns that into a 404 or 403,
and `get_session` rolls the whole transaction back on the error, so no refusal
made through the API is ever recorded.

**Anchor.** `packages/aia_core/src/aia_core/application/scope.py:244` and `:281`
(`self._record(... action="ACCESS_DENIED" / "PERMISSION_DENIED")` before
`raise`) and `apps/api/src/aia_api/dependencies.py:130` (`session.rollback()` in
`get_session`) @ `764f9f7`.

**Reproduction.** In `apps/api/tests`, as the `outsider` of the conftest world:
`GET /api/v1/studies/{primary}/projects` → 404, then
`select(AccessAuditRow).where(action == "ACCESS_DENIED")` → `[]`. Run on this
branch on 2026-09-23 (scratch test, not committed): the assertion failed with `[]`.

**Consequence.** The access audit shows who got in but never who was refused,
though the resolver's own comment says a member reaching for a study they hold
no grant on "is worth seeing". An operator investigating probing would find
nothing.

**Smallest fix.** Record refusals in their own short transaction (a separate
session from the factory, committed before the raise), or have the dependency
commit the audit row before translating `ScopeDenied`. The legacy-panel
session route does the latter for its one refusal
(`apps/api/src/aia_api/routers/panel.py`, `open_session`), which is why its test
passes.

**Test that would have caught it.** The reproduction above as
`apps/api/tests/test_projects_api.py::test_a_refused_study_request_is_audited`,
with its `PERMISSION_DENIED` twin.

**Status.** Open. Found while building ADR 0012's gate; not fixed here because it
changes the transaction shape of every scoped route.

## OI-43 · Question · Three develop-only choices in the 18.6.6 gate need a decision before production

**Claim.** The gate in front of the 18.6.6 interface (ADR 0012) makes three
choices that are right for a handful of develop users and are not a production
design: only organization owners and admins pass; the cookie carries the Cognito
id token itself; and every request to the unit costs one gate round trip with a
user upsert and a membership read.

**Anchor.** `LEGACY_PANEL_ROLES` in `packages/aia_core/src/aia_core/domain/scope.py`,
`_set_cookie` and `gate` in `apps/api/src/aia_api/routers/panel.py`, and the
`forward_auth` block of `deploy/develop/Caddyfile` @ `2326bef`.

**Reproduction.** `apps/api/tests/test_panel_api.py` pins all three:
`test_a_members_session_is_refused_by_the_gate`,
`test_an_administrator_gets_an_httponly_lax_session_cookie` (the cookie value is
the token), `test_the_gate_writes_no_audit_row_per_request`.

**Consequence.** None on develop. In production: researchers without an admin
role could not use the interface; a stolen cookie is a bearer token for an hour;
the gate's cost scales with the interface's request rate (map tiles, polling).

**Smallest fix.** Decide per item when production is planned: the role rule is
reference decision D8 ("default to the most restrictive role and relax
deliberately"); a signed server-side session id replaces the token in the cookie;
the gate's cost is measured on develop first (Caddy access log durations for
`/api/v1/panel/gate`). `Settings.validate_for_production` refuses the panel in
production until then.

**Test that would have caught it.** Not a defect; the production guard is
`test_panel_api.py::test_production_refuses_the_panel`.

**Status.** Open — data owner (D8), then deployment work.

## OI-44 · Finding · The first deploy with the legacy unit took the whole develop site down

**Claim.** *Deploy develop* run 10 @ `9e42f24` replaced every service and left
Caddy unable to start, so nothing answered on the product hostname: the host's
env file had no `AIA_LEGACY_*` values, which made the Caddyfile's legacy site
address empty and the file unparseable, and Caddy also waited for the unit to be
healthy, which it never is without its data bundle.

**Anchor.** `deploy/develop/Caddyfile` legacy site `{$AIA_LEGACY_HOSTNAME} {`,
`deploy/develop/docker-compose.yml` caddy `depends_on: legacy-panel:
condition: service_healthy`, and `deploy/develop/bin/deploy.sh`
`up -d --remove-orphans --wait` @ `9e42f24` (the first two from PR #38, ADR 0011;
the host never ran them before run 10 because runs 6 to 9 failed earlier).

**Reproduction.** Run 10 (`35925591868`) log: `AIA_LEGACY_DATA_PREFIX is unset`,
`The "AIA_LEGACY_HOSTNAME" variable is not set`, `Container
aia-develop-legacy-panel-1 Error`, `dependency failed to start: container
aia-develop-legacy-panel-1 is unhealthy`; Caddy is `Recreated` and never
`Started`. Locally, Caddy 2.11.4 with `AIA_LEGACY_HOSTNAME` empty:
`caddy adapt --config deploy/develop/Caddyfile` → `Error: server block without
any key is global configuration, and if used, it must be first`.

**Consequence.** https://aia-develop.art-chain.io/ down from 22:03 UTC on
2026-09-23 until a deploy carrying the fix. The develop-host-config CI job did
not catch it because it validated the Caddyfile with every value supplied.

**Smallest fix.** Landed on `claude/stoic-fermi-qiw3g1`: Compose defaults the
three values when unset or empty (a `*.localhost` name, a hash of a discarded
random value); Caddy no longer depends on the unit; `bin/deploy.sh` validates
the Caddyfile with the host's `.env` before touching anything and waits only on
AIA's services, with the unit's health as a smoke check; `write-env.sh` quotes
every value, because an unquoted bcrypt hash is mangled by both Compose and the
shell. Still open: Terraform should own the four `aia_legacy_*` parameters
(hostname, user, hash, data prefix) and the oracle's DNS record; until then the
runbook (§ Switching the unit on) gives the commands.

**Test that would have caught it.**
`packages/aia_core/tests/test_develop_host_resilience.py` (fails on the files at
`9e42f24`) and the CI step *Caddy loads through Compose without the oracle's
settings*.

**Status.** Fixed in PR #43 @ `5b51640`: deploy run 11 brought the site back with
the unit unhealthy (every other smoke check passed), and run 12 passed everything
once `aia_legacy_data_prefix` was set. Still open: Terraform ownership of the
four `aia_legacy_*` parameters and the oracle's DNS record.

## OI-45 · Finding · A deploy that changes only the Caddyfile leaves the running Caddy on the old one

**Claim.** *Deploy develop* run 14 (`35968675321`) @ `4dc7966` deployed the
interface skin (PR #45, ADR 0013) and passed every smoke check, but the site
looked exactly as before: the running Caddy kept the routing it started with, so
`/` still went straight to the unit and the web client's injector never saw a
request.

**Anchor.** `deploy/develop/bin/deploy.sh:97-98 @ 4dc7966` (`compose up -d`; no
reload or recreate of `caddy`); `deploy/develop/docker-compose.yml` caddy
`volumes: ./Caddyfile:/etc/caddy/Caddyfile:ro` @ `4dc7966`. Caddy reads its
Caddyfile once, at start; Compose recreates a container only when its image or
its configuration changes, never because a bind-mounted file's contents did.

**Reproduction.** `docker compose config` of the caddy service, rendered from
the same directory, at `cd8113c` and `4dc7966`: identical
(`fc17bc3292e0…`), while the Caddyfile changed (`fae7b5d0…` → `5871bb11…`) and
the web service's configuration changed (`35915de2…` → `a623b1ff…`). So run 14
recreated `web` (with the injector and the switch on) and left `caddy` running.
The data owner reported the unchanged site on 2026-09-24. The same deploy's
smoke checks could not see it: every one of them is answered identically by the
old routing.

**Consequence.** The skin was deployed and switched on and nobody could see it;
more generally, any Caddyfile-only change — a route, a header, a gate — would
ship green and not take effect. Earlier Caddyfile changes took effect only
because each also changed the caddy service's Compose configuration.

**Smallest fix.** `bin/lib.sh` exports `AIA_CADDYFILE_SHA256` (the file's hash)
for every script, and the caddy service carries it as a label, so a changed
Caddyfile changes the service's configuration and `compose up` recreates Caddy;
an unchanged one restarts nothing. The first deploy with the fix recreates Caddy
once (the label is new). A new smoke check asks for `/interface-document`
directly, which only the current Caddyfile answers with Caddy's own 404.

**Test that would have caught it.**
`test_develop_host_resilience.py::test_a_changed_caddyfile_recreates_caddy` and
`::test_the_smoke_check_proves_caddy_runs_the_deployed_caddyfile`; on the host,
the smoke check *caddy: running the deployed Caddyfile*.

**Status.** Fixed in PR #46 (`230ee7e`); deploy run 15 recreated Caddy and its
smoke check *caddy: running the deployed Caddyfile* passed, 2026-09-24.

## OI-46 · Finding · The classic rail says "Core joint · VALID" whatever the joint core's status is

**Claim.** 18.6.6's last `updateState` override writes the rail's second status
line as a literal — `Core joint` / `VALID` — without reading
`BOOT.joint_core.status`, so every user is told the joint core is valid while
the unit reports it is not.

**Anchor.** `legacy/npc-panel-18.6.6/app/ui_app.html:614 @ 7a2a9af`
(`updateState=function(){…core.innerHTML='…Core joint…VALID…'}`).

**Reproduction.** `make ui-workbench`, then
`curl -s 127.0.0.1:8767/api/bootstrap | python3 -c "import json,sys;print(json.load(sys.stdin)['joint_core']['status'])"`
prints `JOINT_UNVALIDATED`, while the classic rail at `127.0.0.1:8780/` reads
*Core joint · VALID*. Whether develop's real panel reports otherwise is not
known from here (no egress); the literal does not depend on it either way.

**Consequence.** A certainty the backend does not grant is shown on every
screen, next to a real one (*Claude Code · READY* does read the provider's
status). This is the "never stamp a guess" failure (CLAUDE.md §8) in the
product surface.

**Smallest fix.** The unit is frozen (ADR 0011). The rebuilt rail
(`apps/web/src/unit/shell.ts`, ADR 0014) prints the status the unit reports and
nothing when it reports none; the classic rail keeps the literal until `/`
moves.

**Test that would have caught it.** `apps/web/src/unit/shell.test.ts`
("prints the joint core status the unit reports, never a stamped VALID").

**Status.** Fixed in the rebuilt interface; standing in the classic one.


## OI-47 · Finding · The classic "Ověření & kontext" step never renders, and nothing links to it or to "Další krok"

**Claim.** `renderVerify` awaits `loadVerifyTargets(false)`, which is defined
nowhere in the document, so the step throws a `ReferenceError` before drawing;
and no rail entry, button or `go('verify')` / `go('next')` call reaches either
`verify` or `next`.

**Anchor.** `legacy/npc-panel-18.6.6/app/ui_app.html:447-448 @ 0932c5d` (the
two `renderVerify` / helper declarations calling `loadVerifyTargets`); the final
`RESEARCH_STEPS` splice lists seven steps without either (char offset 417490).
`grep -c "function loadVerifyTargets\|loadVerifyTargets=" ui_app.html` → `0`.

**Reproduction.** `make ui-workbench`, open `127.0.0.1:8780/`, and in the
console: `LAST_RESULT={main:{summary:{mode:'live',run_id:'x'}}}; go('verify')`.
The title becomes *8. Ověření & kontext*, the previous screen's content stays,
and the page throws `ReferenceError: loadVerifyTargets is not defined`
(verified 2026-09-24; without a result it shows *Nejdřív potřebujete výsledek*).
`grep -c "go('verify')\|go('next')" ui_app.html` → `0`.

**Consequence.** External verification and the "ideal group from results"
step, both backed by working unit routes (`/api/results/verify`,
`/api/discovery/strategy`), are unreachable in the product.

**Smallest fix.** The unit is frozen. The rebuild (research-flow-rehome.md,
chunks 10–11) links both from the results step and draws verify's intended
screen against its routes — new behaviour for users, shown to the data owner
before it merges.

**Test that would have caught it.** A reachability check over the router: every
route in `RESEARCH_ROUTE_SET_1776` is the target of some control. The rebuild's
equivalent is the screen ledger plus a component test per step.

**Status.** Open in the classic interface; to be fixed by the rebuild.

## OI-48 · Finding · The route ledger misses four paths the unit serves as `path in {…}` sets

**Claim.** `docs/migration/legacy-route-ledger.json` has no row for
`POST /api/audience/navrh`, `/api/audience/propose`,
`/api/results/contextual_calibration` or `/api/results/contextual_scenario`,
all served by the unit and two of them called by the classic interface.

**Anchor.** `legacy/npc-panel-18.6.6/app/ui_server.py:2108` and `:2120 @ 0932c5d`
(`if path in {"…","…"}:`); the ledger mirrors the reference's
`api-ledger.json` byte for byte (`test_legacy_route_ledger.py`), whose parser
recognised `path ==`, `startswith` and `endswith` arms but not set membership.

**Reproduction.** `grep -n 'path in {' legacy/npc-panel-18.6.6/app/ui_server.py`
→ 2 lines; `python3 -c "import json;print([r['route'] for r in json.load(open('docs/migration/legacy-route-ledger.json'))['routes'] if 'propose' in r['route'] or 'contextual' in r['route']])"` → `[]`.

**Consequence.** The strangler's state omits two live capabilities (AI audience
proposal, contextual scenario), and the rebuilt interface's client — which may
call only ledger rows — could not reach them.

**Smallest fix.** An `addenda` section in the ledger: each missed path with its
`ui_server.py` line, verified against the unit by the ledger test, kept apart
from the pinned 153 rows until the reference's parser is fixed upstream
(`AiAnalytics-AIA/AIA-reference`, not reachable from this session).

**Test that would have caught it.** `test_legacy_route_ledger.py`: every
`path ==` / `path in {…}` literal in `ui_server.py`'s dispatch is a row or an
addendum.

**Status.** Fixed in-repo: `addenda` in the ledger, checked by
`test_legacy_route_ledger.py::test_the_addenda_are_exactly_the_set_arms_the_reference_missed`.
The reference's parser (upstream) still misses the form.

## OI-49 · Finding · The questionnaire's "AI: zlepšit blok" does nothing

**Claim.** Every question block has an *AI: zlepšit blok* button that calls
`quickClaude(...)`, which returns at once unless an element `#chatInput`
exists, and no code in the document creates one.

**Anchor.** `legacy/npc-panel-18.6.6/app/ui_app.html:579 @ 8444bda`
(`function quickClaude(t){let inp=$('#chatInput');if(!inp)return;…}`); the
button is in `questionSection`. `grep -c 'id="chatInput"\|id=.chatInput' ui_app.html` → `0`;
all five `chatInput` references are lookups.

**Reproduction.** `grep -o "chatInput" legacy/npc-panel-18.6.6/app/ui_app.html | wc -l` → 5,
and every occurrence is `$('#chatInput')` (a lookup); in the workbench, the
button on any question block changes nothing and starts no job.

**Consequence.** A person asks the AI to improve a block and nothing happens,
with no message.

**Smallest fix.** A decision, not a port: drop the button, or wire it to the
AI assistant (new behaviour). The rebuild leaves it out and lists it.

**Test that would have caught it.** A reachability check that every `on…`
handler's first guard can pass on some screen.

**Status.** Open in the classic interface; **decision for the data owner** (PR B).

## OI-50 · Finding, closed · An empty bound in the audience range filter becomes 0, and the unit then targets the wrong people

**Claim.** `setAudienceRange1793` reads both inputs with `Number(...)`, and
`Number('')` is `0`, so a range with one bound left empty is stored with the
other bound `0`; the unit then orders the pair, so *od 25* (no upper bound)
selects ages 0–25.

**Anchor.** `legacy/npc-panel-18.6.6/app/ui_app.html:1053 @ 8444bda`
(`let a=Number($('#'+minId)?.value),b=Number($('#'+maxId)?.value);…{min:Number.isFinite(a)?a:null,…}`).

**Reproduction.** Under Node, the effective binding with only the lower input
filled stores `{"vek":{"min":25,"max":0}}`; the workbench unit answers
`POST /api/audience {"filtry":{"vek":{"min":25,"max":0}},"n":300}` with
`"filtry": {"vek": [0.0, 25.0]}` (verified 2026-09-24; support 8 of 60 instead
of the over-25s). The rebuild's characterization test:
`audience.parity.test.ts` › *an empty bound is stored as 0, as the classic does (OI-50)*.

**Consequence.** A person who asks for "25 and older" researches people under
25, and the preview shows a plausible support number, so nothing looks wrong.
Clearing both inputs stores `0–0`, an empty audience; a range can only be
removed with its chip.

**Smallest fix.** Read an empty input as "no bound" (`null`) and delete the
filter when both are empty. This changes who is sampled, so it is a
methodology decision.

**Test that would have caught it.** The characterization test above, asserting
`null` instead of `0`.

**Status.** Closed (below). Ported as the classic behaves, a **decision for the data owner**
before PR B merges. **Update 2026-10-12 (#345, panel-grounded-respondents 6e):** AIA's
live range editor leaves an empty bound out, so the population's own bound stands
(`apps/web/src/research/audience.ts` `setRange`; `audience.live.test.ts` › *leaves an
empty bound out, where the classic stored 0*). The classic `setAudienceRange` stays,
characterised, as the parity port only; no product code calls it
(`AudienceStep.tsx:369 @ b0ec403e` commits through `setRange`). **Closed** 2026-10-12 by
#345 (merged as `b0ec403e`).

## OI-51 · Finding · Picking a special-audience preset keeps the previous subpanel and its filters

**Claim.** `chooseSpecialPreset` for a *special* or *coming soon* preset sets
the new source but leaves `builtin_subpanel` and `filters` from a population
preset picked before it, and `setAnalyticsChoice('special')` does not clear
`filters` either.

**Anchor.** `legacy/npc-panel-18.6.6/app/ui_app.html:372 @ 8444bda`
(`chooseSpecialPreset`), `:350` (`setAnalyticsChoice`).

**Reproduction.** Under Node with the effective bindings: `chooseSpecialPreset('doctors')`
then `chooseSpecialPreset('foreign_prague')` leaves
`{"dataset_name":"Cizinci žijící v Praze","builtin_subpanel":"medical_doctors","filters":{"profese":["lékař"]},"source_mode":"special_audience"}`
and `audienceReady1789()` → `true` (verified 2026-09-24). The rebuild's
characterization test: `audience.parity.test.ts` › *a special preset keeps the
previous subpanel and filters, as the classic does (OI-51)*.

**Consequence.** The screen says *Vybráno: Cizinci žijící v Praze* and lets the
person continue, while the project still carries the doctors' filters; a
*coming soon* preset asks for the person's own data but shows no upload on that
screen (its scroll target `#audFile` is on the *own* screen). **What the run
does with this state is a hypothesis:** not traced through the unit's sampler.

**Smallest fix.** Clear `builtin_subpanel`, `filters` and `segment` whenever a
preset or the special branch is chosen. It changes a project's audience, so it
is a decision.

**Test that would have caught it.** The characterization test above, asserting
the cleared state.

**Status.** Open; ported as the classic behaves; **decision for the data owner**.
**Decided 2026-10-25 (the owner, OI-51 (a), the audit page, relayed by coordinator 3):** "clear the subpanel and filters on every
preset change." Open until the audience step clears them (the smallest fix above) and the
characterization test asserts the cleared state; no chunk builds it yet. To be built by the audience session's fix PR (`fix/audience-preset-clears-filters`).
**Closed 2026-10-26 by #910** (merged as `40b16d58`): every preset change clears the subpanel, the filters and the
segment (`presetReset`, `apps/web/src/research/audience.ts @ 40b16d58`). #917 (`d6f7f977`) also resets the strategy and the
support figures on a preset change and keeps the description (the product owner, 2026-10-25, "Clear both"). The
preset's other writes are an open owner question, recorded in `artifact-audience.md` § Findings.

## OI-52 · Question · Is a questionnaire of tracked sets only a questionnaire?

**Claim.** The wizard's *Další · cílová skupina* is enabled only when some
section has `questions`; a questionnaire made only of tracked object sets
(which have `objects`, not `questions`) cannot use it, but the editor's own
*Dotazník mám → Koho se ptát* continues with no check at all.

**Anchor.** `legacy/npc-panel-18.6.6/app/ui_app.html:955 @ 8444bda`
(`questionnaireHasQuestions1789`), `:960` (the wizard), `questionnaireEditorHtml`
(the unconditional button), `:588` (`continueQuestionnaireToAudience`).

**Reproduction.** `questionnaire.parity.test.ts` › *a questionnaire of tracked
sets only has no questions, as the classic counts (OI-52)*.

**Consequence.** Two buttons on one screen disagree about whether the
questionnaire is ready.

**Smallest fix.** Decide the rule (a set counts, or it does not), then apply it
to both buttons. The rebuild keeps both as they are.

**Status.** Open; **question for the data owner**.
**Decided 2026-10-25 (the owner, OI-52 (b), the audit page, relayed by coordinator 3):** "a questionnaire needs at least one plain
question." A tracked set alone does not count. Open until both buttons apply the rule; no chunk
builds it yet. To be built by the questionnaire session's fix PR (`fix/questionnaire-plain-question`, QF-17).
**Closed 2026-10-25 by #899** (merged as `0b278552`): readiness's questionnaire check FAILs a design with no plain
question (QF-17 in `artifact-questionnaire.md`).

## OI-53 · Finding · "AI doporučí" approves dimensions that are not in the catalogue

**Claim.** The effective `suggestPersonaAI` sets the approved dimensions to the
model's list, canonicalised, without checking it against the dimension
catalogue; an earlier binding, now dead, filtered to the catalogue and warned
about the rest.

**Anchor.** `legacy/npc-panel-18.6.6/app/ui_app.html:1070 @ 8444bda`
(`PROJECT.persona_dimensions.approved=(r.dimensions||[]).map(canonicalPersonaDim).filter(Boolean)`);
the dead one at `:402` (`…filter(x=>allowed.has(x))…toast('AI navrhla i dimenze mimo katalog…')`).

**Reproduction.** `persona.parity.test.ts` › *the model's dimensions are
approved without the catalogue check, as the classic does (OI-53)*.

**Consequence.** A dimension with no definition in the system can be switched
on by the model and is shown by its raw id; the screen says the catalogue is
the primary source. `canonicalPersonaDim` also maps by substring, so the
model's *vztah k AI* is approved as `vztahy` (*Vztahy / domácnost*), a
different dimension (same test).

**Smallest fix.** Filter to the catalogue and list the rest as requests, as the
earlier binding did. A methodology decision.

**Status.** Open; ported as the classic behaves; **decision for the data owner**.
**Decided 2026-10-25 (the owner, OI-53 (a), the audit page, relayed by coordinator 3):** "filter to the catalogue." The owner's
note: "the buttons should not be part of the UI but a card in the Lead researcher." Open until the
suggestion is filtered to the catalogue (the rest listed as requests) and offered as a Lead card
instead of the stage's buttons; no chunk builds it yet. To be built by `lead-orchestration` LO22; the classic button is removed as DIM5.

## OI-54 · Finding · The optional dimensions can never all be removed

**Claim.** `personaApproved` replaces an empty approval with the recommended
set while the screen draws, so removing the last optional dimension brings the
recommended ones back.

**Anchor.** `legacy/npc-panel-18.6.6/app/ui_app.html:407 @ 8444bda`
(`if(!Array.isArray(PROJECT.persona_dimensions.approved)||!PROJECT.persona_dimensions.approved.length)PROJECT.persona_dimensions.approved=suggestedPersonaDims();`).

**Reproduction.** `persona.parity.test.ts` › *removing the last dimension
brings the recommended ones back, as the classic does (OI-54)*.

**Consequence.** A study cannot run with the fixed sociodemographic base only;
the screen offers *Zatím není vybraná žádná volitelná dimenze* but never shows it.

**Smallest fix.** Refill only when the approval has never been set. A
methodology decision.

**Status.** Open; ported as the classic behaves; **decision for the data owner**.

## OI-55 · Question · The AI steps disagree about provider checks and time limits

**Claim.** Building a questionnaire, proposing an audience and suggesting
dimensions check the provider first; optimising the questionnaire and deep
research do not. Two callers pass `maxMs` (240 s, 300 s) that the job never
reads: only `warnMs` has an effect, and nothing stops a job client-side.

**Anchor.** `legacy/npc-panel-18.6.6/app/ui_app.html:338-339 @ 8444bda`
(`optimizeQuestionnaireAI`, `runProjectDeepResearch`: no `ensureClaudeReady1776`);
`:305` (`job`: reads `opt.warnMs` only).

**Reproduction.** `grep -o "maxMs" legacy/npc-panel-18.6.6/app/ui_app.html | wc -l`
counts the callers; `python3 tools/ui_functions.py show job | grep -c maxMs` → `0`.

**Consequence.** Optimising with an unready provider fails only after the job
starts, with the provider's error; a caller's stated limit is not a limit.

**Smallest fix.** None needed for parity; the rebuild keeps both behaviours.
Worth deciding when the AI steps move behind the governed gateway.

**Status.** Open; **question**, no decision needed for PR B.

## OI-56 · Finding, fixed · A change made just before moving to another research step was lost

**Claim.** Each research step was its own page with its own project store, and
leaving a page disposed its store by cancelling the pending debounced save; the
next step then loaded the project from the unit without that change.

**Anchor.** `apps/web/src/unit/research/store.ts` `dispose()` and
`apps/web/src/components/rehome/research/ResearchScreen.tsx` (one
`ResearchStore` per page) `@ 8444bda`.

**Reproduction.** In the workbench, open `/app/research/<planned>/plan` and
click *Další · dotazník* (it sets `questionnaire_path` and moves on at once):
`/api/projects/load` is requested again and no `/api/projects/save` is sent
(Playwright, 2026-09-24: loads 2 → 4, saves `[]`). Tests:
`store.test.ts` › *saves a change still waiting for its debounce when the person
leaves the project*; `ResearchScreen.test.tsx` › *keeps one project session
while each step's page mounts afresh, as Next mounts them*.

**Consequence.** Any edit made less than 1.8 s before a step change (a rail
link, a *Další* button) silently disappeared, and the save indicator had said
*Změny se uloží za chvíli*.

**Fix.** The `/app/research/<id>` layout holds one `ResearchSession` (store and
page memory) for all the project's steps, since a layout is not re-rendered when
only the step changes; a new project's store is handed to its new route instead
of reloaded; `dispose()` saves a pending change instead of dropping it. After
the fix: loads stay 2, saves `["questionnaire_path"]`.

**Status.** Fixed in PR B (`feature/research-flow-b`).

## OI-57 · Finding · A failed audience catalogue is requested again on every draw of Dimenze, without limit

**Claim.** The 1793 `renderPersona` wrapper draws its society-factor card only
once `AUDIENCE_DIM_CATALOG_1793` is set; until then it calls
`ensureAudienceDimensionCatalog1793()` and redraws when that settles. A failed
load returns `null` and leaves the global unset, so the redraw asks again at
once: one request per round trip for as long as the step stays open.

**Anchor.** `legacy/npc-panel-18.6.6/app/ui_app.html:1071 @ 8444bda`
(`if(!cat){ensureAudienceDimensionCatalog1793().then(()=>{if(CURRENT==='persona')renderPersona()});return}`);
`ensureAudienceDimensionCatalog1793` (`catch(e){console.error(e);return null}`).

**Reproduction.** `persona.parity.test.ts` › *a catalogue that fails to load is
asked for again on every draw, with no limit, as the classic does (OI-57)*: a
stub that fails nineteen times is asked twenty. Without the twentieth answer
the run never ends (Node, 2026-09-24).

**Consequence.** While `/api/audience/dimensions` fails, an open Dimenze step
loads the unit with back-to-back requests and each redraw rebuilds the page
under the person's hands; the card never appears.

**Smallest fix.** Ask once per visit; on failure leave the card out. That is
what the rebuild does (research-flow-rehome.md, deliberate differences): the
visible result, no card, is the classic's.

**Status.** Open; **decision**: confirm the rebuild's single request.

## OI-58 · Migration debt · The unit's project store holds the rebuilt research stages' working content

**Claim.** The research stages rebuilt in PR #49 and #50 read and write their working content in
the 18.6.6 unit's single-tenant project store (`/api/projects/load|save`), not in AIA-owned,
study-scoped storage; ADR 0015 bridges it with an explicit AIA-owned binding, `study_workspaces`
(AIA Study ↔ unit project), and that bridge is temporary.

**Anchor.** `apps/web/src/unit/research/store.ts:42-63,144-152 @ 8e7a6db` (the unit load and
save); `docs/architecture/adr/0015-client-first-product-interface.md` decision 5.

**Rules while it exists.** Access always resolves the study through `ScopeResolver` first and
reads the unit project id from the binding; a unit project id supplied by the browser is never
authorization and no route finds a study by one; the binding is written once per study, through
an issued `StudyContext` with `EDIT_STUDY`, and never to a unit project already bound elsewhere.
The Study stays canonical for scope, identity, lifecycle, permissions, budgets and costs,
approvals, provenance, artifacts and history; the unit copy is working content only.

**Tests.** `packages/aia_core/tests/test_study_workspaces.py` ›
*a unit project id is never a way into a study* and *a unit project bound to one study cannot be
bound to another*; `apps/api/tests/test_client_api.py` › *the workspace of another client's study
is not found*.

**Consequence of leaving it.** The unit store would harden into the data model: study state
outside AIA's audit, cost and provenance contracts, isolated only by the binding and the
owner/admin gate (OI-59), with no row-level scope of its own.

**Removal condition.** The research (then simulation) stage state is stored and served by AIA's
study-scoped contracts (`/api/v1/studies/{study_id}/…`); the rebuilt stages no longer call the
unit's project store; the bound working content is migrated into AIA. Then ADR 0015 decision 5
is retired and `study_workspaces.unit_project_id` is history only (ADR 0018 keeps the table: it
names each Study's AIA working project). The unit remains only as the oracle and a frozen
reference, never a runtime fallback (ADR 0018; the "fallback" wording here was stale, handed over
by [#73](https://github.com/AiAnalytics-AIA/AIA/pull/73) § 10).

**Carried from OI-66.** Some bindings already name unit projects that no longer exist (four
at the time of OI-66). The migration accounts for each one explicitly: a study with a
recoverable copy (a submitted Design Revision) is migrated from that copy with its provenance;
a study with none is given an explicit "no recoverable working content" state. It never
creates an empty stand-in and never rebinds a study to another project. The AIA-owned store
keeps two invariants the unit lacked: seed or fixture data never overwrites working content,
and a study whose content is missing says so by name rather than "Projekt/revize nenalezena".

**Status.** Open; **migration debt**, accepted temporarily by the data owner (2026-09-24).
Being retired by [ADR 0018](../docs/architecture/adr/0018-aia-runs-without-18-6-6.md)
([plan](plans/legacy-phase-out.md)):

- **Landed in code (`feature/native-research-workspace`, 2026-09-27):** the stages load and
  save a Study's working content in AIA (`GET`/`PUT /api/v1/studies/{study_id}/workspace/content`,
  `StudyWorkspaceRepository`, owned working project); the binding route
  `PUT /studies/{id}/workspace` is gone; every existing binding became `AWAITING_MIGRATION`
  (migration `5b1d0f3e9a21`), which refuses edits so the content cannot fork. The two
  invariants above hold by construction: nothing but a person's save writes a working
  project, and a missing or lost content says so by state. Tests:
  `test_study_workspaces.py`, `test_workflow_concurrency.py` ›
  *two editors saving from one revision cannot overwrite each other*,
  `test_client_api.py` › *a save from a stale revision is a conflict…*.
- **Landed (same branch, chunk 3):** the brief's attachments are artifacts of the working
  project in AIA's storage (`POST`/`GET /api/v1/studies/{study_id}/workspace/attachments`),
  their text read by the unit's own libraries and compared with the unit's function
  (`test_document_text.py`); nothing of the brief reaches the unit. Tests:
  `test_study_workspaces.py` › *an attachment is served only through its own study*,
  `test_client_api.py` › *a file is attached in AIA and downloaded only through its study*.
- **Landed (chunk 5):** Audience and Dimenze call nothing of the unit. Dimensions come from
  the client's approved knowledge and a request is a knowledge proposal; what the unit
  computed from its panel or audience store says it is not in AIA. With chunks 1-4, the
  research flow reaches no unit route: `ResearchScreen`, `BriefStep`, `PlanStep`,
  `QuestionnaireStep`, `AudienceStep`, `PersonaStep` tests fail on any unit URL.
- **Landed (chunk 4):** a questionnaire file is read in AIA and only its sections come back
  (`POST …/workspace/questionnaire-import`), normalized by the unit's rules and compared with
  the unit's own import (`test_questionnaire_import.py`); the template is AIA's own workbook.
- **Landed (chunk 7, `feature/legacy-workspace-migration`):** the migration command,
  `python -m aia_executors.legacy_workspace` (ADR 0018 decision 2): from a copy of the unit's
  store and attachment directory, as a named person through their own grants; every revision
  one for one, author unknown, lineage kept; every file into AIA storage or reported; the copy
  checked against the unit's own hashes before writing and the result after; dry run unless
  `--apply`; each Study its own transaction. The OI-66 cases are decided only with
  `--recover-missing`: `RECOVERED` from the newest Design Revision, else `UNRECOVERABLE`.
  Tests: `test_workspace_migration.py` › *a study gets every revision and file and keeps who
  it belongs to*, *what does not validate is rolled back and left waiting*, *a project missing
  from the copy waits until the copy is said complete*, *the operator migrates only what their
  own grants let them edit*, *a second run changes nothing and says what was done before*;
  `apps/executors/tests/test_legacy_workspace.py`.
- **Landed (chunk 9, `feature/interface-without-classic`):** the last caller of the unit's
  store, the classic projects screens at `/app/settings/classic-projects`, is removed with the
  typed unit client (`apps/web/src/unit/`); the web client calls no path of the unit. A Study's
  bound content comes over by the migration, and a unit project no Study refers to stays in the
  unit's volume, listed in the migration's report. Tests: `NotInAia.test.tsx` › *settings offer
  no way into the classic interface or its project store*; the research flow's tests above.
- **Landed (chunks 10–11, `feature/deploy-without-legacy`):** the product deployment has no
  unit (ADR 0018 decision 5), and its volume is kept: the first deploy without it stops the
  old container as its service did and fails if the volume vanished, and nothing removes the
  volume, the data directory, the data bundle or the images (`deploy/develop/bin/deploy.sh`,
  `bin/lib.sh` › `retire_product_unit` @ `9138977`; `test_develop_unit_retirement.py` ›
  *the deploy stops the unit before replacing services and proves the volume after*). The
  migration's copies are taken from the volume in throwaway containers of the unit's image,
  not from a running unit (runbook § Migrating 18.6.6 content), checked on a stand-in volume:
  a store whose writer was killed with committed rows only in its WAL was copied with those
  rows, and the attachments came out, with no container left. The copier needs the unit's own
  user (AGENTS.md § Docker and Compose): run as another user, it cannot open a WAL store
  read-only. The unit's databases are backed up by the reference setup
  (`deploy/reference/bin/backup-state.sh`), no longer by the product's nightly dump.
- **Still open:** **running** the migration on develop -- an operator action on the live
  host, by the runbook (`deploy/develop/README.md` § Migrating 18.6.6 content), not done by
  any change here -- preceded by a copy of the unit's databases taken before the first deploy
  without it (`bin/backup.sh pre-adr-0018`, with the data owner's approval, runbook § The
  first deploy without the unit). Until it runs, the develop Studies bound to 18.6.6 stay
  `AWAITING_MIGRATION` and their content stays in the unit's volume, untouched.

## OI-59 · Temporary restriction, closed · `/app` admits organization owners and admins only

**Claim.** The client-first shell at `/app` sits behind the panel gate, which admits only
organization owners and admins (`LEGACY_PANEL_ROLES`), because the rebuilt stages still depend on
the single-tenant unit (OI-58); this is a temporary restriction, **not the authorization model**.

**Anchor.** `deploy/develop/Caddyfile:84-99 @ 8e7a6db` (`/app` → `forward_auth
/api/v1/panel/gate`); `packages/aia_core/src/aia_core/domain/scope.py:120-128 @ 8e7a6db`
(`LEGACY_PANEL_ROLES`).

**Reproduction.** `apps/api/tests/test_panel_api.py` ›
*test_a_members_session_is_refused_by_the_gate*: a member with client and study grants, but no
admin role, is refused.

**Target.** *Authenticated user → organization membership → client grant → study grant*, exactly
as every `/api/v1` route resolves it through `ScopeResolver`. Nothing in the client shell may
depend on the caller being an owner or admin: every page's data already comes from scoped API
routes, which apply the grants, not the gate.

**Consequence of leaving it.** Researchers who hold the right client and study grants cannot use
the product; owners and admins become the only users by accident of the migration. **In
production, `/app` cannot be served at all:** its gate answers only when
`AIA_LEGACY_PANEL_ENABLED` is on (`apps/api/src/aia_api/routers/panel.py` `_require_enabled`),
and `Settings.validate_for_production` refuses that setting
(`apps/api/src/aia_api/config.py:213-215 @ 043b0dd`). So this item blocks a production `/app`,
not only its audience (recorded 2026-09-27).

**Removal condition.** Stage state is fully AIA-scoped for the stages a researcher uses (OI-58);
then `/app` moves to a gate that admits any provisioned member, and the unit's own paths keep the
owner/admin gate until the unit is out of the stage path.

**Status.** Open; **temporary restriction**, accepted by the data owner for this PR (2026-09-24).
Being retired by [ADR 0018](../docs/architecture/adr/0018-aia-runs-without-18-6-6.md) decision 3:

- **Landed in code (`feature/aia-session-gate`, 2026-09-27):** `/app` is behind AIA's own gate,
  `GET /api/v1/session/gate`, which admits any active member of the organization with an AIA
  session (`POST /api/v1/session`, cookie `aia_session`) and nothing else. Admission is
  `ScopeResolver.authorize_session`, recorded in the access audit (`AIA_SESSION`). No setting
  turns it off and no legacy setting touches it, so the production blocker above is gone for
  `/app`. The pages' data is authorized per call, as before. The gate refuses every method but
  GET and HEAD, because the pages take no writes. The web client's `/app` switch
  (`AIA_INTERFACE_REHOME_ENABLED`) no longer decides whether `/app` is served. Tests:
  `apps/api/tests/test_session_api.py` › *every active member gets an httponly lax session cookie*,
  *a members session passes the gate* (a researcher, a viewer, a member with no client grant),
  *the session and its gate do not depend on the legacy panel*;
  `packages/aia_core/tests/test_caddy_routes.py` › *app behind the 18 6 6 panels gate is refused*;
  `apps/web/src/app/login/page.test.tsx`.
- **Landed (chunk 9, `feature/interface-without-classic`):** `/classic` no longer serves 18.6.6:
  it is the web client's public page saying so, with no data and no gate; `/login` no longer
  opens the panel's session, and sign-out still clears a panel cookie an earlier sign-in left.
  Tests: `NotInAia.test.tsx` › *tells an old link the interface is gone, and leads into AIA*;
  `test_caddy_routes.py` › *the classic hand off coming back is refused*;
  `apps/web/src/lib/session.test.ts` › *clears AIA's session and a panel cookie left from
  before, then the sign-in*.
- **Closed (chunk 11, `feature/deploy-without-legacy` @ `caa7ed8`):** the product deployment
  no longer runs the unit, so its paths are gone from the product hostname, and the panel's
  gate with them: `apps/api/src/aia_api/routers/panel.py`, `ScopeResolver.authorize_legacy_panel`,
  `LEGACY_PANEL_ROLES` and the `AIA_LEGACY_PANEL_*` settings are removed, and
  `/api/v1/panel/*` answers 404. Nothing in AIA depends on a caller being an owner or admin
  to be let in. Tests: `apps/api/tests/test_session_api.py` › *the session and its gate need
  nothing of 18 6 6* (no legacy setting exists; the panel routes answer 404);
  `test_caddy_routes.py` › *app behind the 18 6 6 panels gate is refused* and *the unit
  coming back on its own paths is refused*; CI's API contract fails a `/api/v1/panel` path.

## OI-60 · Finding, fixed · `GET /api/v1/access-audit` always failed

**Claim.** The access-audit route built each response entry from a dict that
always carries `payload`, into a response model that forbids extra fields and
had no `payload`, so every call raised a validation error (HTTP 500) once the
organization had any audit entry — which it has from its first grant.

**Anchor.** `apps/api/src/aia_api/routers/scope.py:160-172,510 @ 8e7a6db`
(`AuditEntryResponse`, `extra="forbid"`, no `payload`); `application/scope.py:731 @ 8e7a6db`
(`"payload": dict(r.payload or {})`).

**Reproduction.** `apps/api/tests/test_scope_api.py` ›
*test_the_access_audit_lists_entries_with_their_payload* (fails at `8e7a6db`).

**Consequence.** The one review surface for break-glass access (`CLIENT_SELF_GRANT`,
denials) was unusable; nobody noticed because no API test exercised the scope router.

**Fix.** `AuditEntryResponse.payload`, the before/after record the audit exists to show.

**Status.** Fixed, merged in PR #51 (`develop` @ `4ad5f66`).

## OI-61 · Decision, closed · May panel-derived microdata be sent to a model provider?

**Claim.** Whether PIAAC, ISSP and the Czech population panel built from them — or anything computed
from their rows, such as a synthetic respondent's grounded profile — may be transmitted to any model
provider (Bedrock included) is unresolved.

**Anchor.** AIA-reference `open-decisions.md` D3 (storage jurisdiction, sending to model providers,
showing to clients; `legal_gate` records licensing as "reviewed outside" the system);
`population-subsystem.md:28-73` (the panel's lineage).

**Engineering rule until it is resolved (ADR 0016 decision 5).** Fail closed: material may reach a
provider only when every dataset it derives from has a determination approving that provider.
Every panel-derived source is recorded as *not approved*. The rule is code; the determination is
policy data, changed by the data owner with legal's confirmation, never by an engineer to unblock a
feature.

**Where the rule lives.** `packages/aia_core/src/aia_core/domain/licence.py` (`LicencePolicy.authorise`)
and the determinations `domain/licence_determinations.py` @ `ee5aac0`, enforced in
`GovernedModelGateway` beside residency; `test_licence_gate.py`,
`test_model_gateway.py::test_licence_is_a_second_gate_refused_before_dispatch`. Resolving this item
means replacing the UNDETERMINED record of each source in that file, nothing else.

**Consequence.** AI fieldwork (the Agent Runtime PR) cannot go live against the panel until this is
resolved per source. It can be built and tested on synthetic or explicitly cleared data.

**What resolves it.** A source-specific determination (per dataset: which providers, which data
classes, by whom, when, on what basis) from legal and the data owner.

**Status.** Closed 2026-10-12: the data owner determined that panel-derived sources may reach
`bedrock-eu-primary` alone (`domain/licence_determinations.py`, `PANEL_APPROVED_ROUTE`; the
licence gate stays beside residency and refuses every other route). Legal's confirmation is
still owed (ADR 0024, Open). *The line read "Open" under a "closed" heading until 2026-10-13
(OI-108).*

## OI-62 · Decided (engineering, on evidence) · Bootstrap intervals need not follow NumPy's random stream

**Claim.** The unit's aggregation intervals are a donor-cluster bootstrap whose resamples come from
`np.random.default_rng(seed).integers(...)` (PCG64). The question was whether AIA must reproduce that
stream exactly (a pure-Python PCG64 in a stdlib-only domain, ARCHITECTURE.md §2) or whether the same
estimator, deterministic under AIA's own generator, is enough.

**Anchor.** `legacy/npc-panel-18.6.6/app/uncertainty.py:144-181` (`_cluster_multipliers`,
`bootstrap_weighted_mean`, `bootstrap_weighted_distribution`) @ `7e0fa7c`; the call sites and their
seeds, `dotaznik.py:1450-1578` (`20260816`, `20260818`, `20260816+i`, `20260820`–`20260824`,
`20260830+i`). The research half of PROGRESS D11; D11's simulation half (the withheld `FS_*` formula
bodies) is unchanged.

**What the unit does with the random stream.** The random stream decides only the interval bounds.
Point estimates (`weighted_mean`, `weighted_distribution`), Kish n, donor counts, `support_status`
and suppression are computed without it. No 18.6.6 research code makes a decision from a bound: the
report draws them and hides a value without an interval (`report_html.py:33-36`), and the only
comparison against a bound is simulation truth-coverage (`full_simulation.py:783`), outside research
aggregation. AC-09 asks for effective-n suppression on every client-facing number
(`docs/migration/mvp-acceptance.md:79`), not for equal bounds. AIA's own evidence gate needs a finite
interval that contains its estimate (`domain/evidence/support.py:206-224`).

**Evidence.** `tmp/ui-workbench/venv/bin/python tools/bootstrap_seed_sensitivity.py` runs the
unit's own, unmodified `uncertainty.py` (NumPy 2.4.6) with 400 resamples on fictional cells, at the
unit's seed and 199 others:

| cell | support | estimate moves with seed | 1–5 mean: unit bounds | unit's own range, low / high | other seeds giving the unit's bounds | % option A: unit bounds | unit's own range, low / high | other seeds giving the unit's bounds |
|---|---|---|---|---|---|---|---|---|
| 450 rows, 287 donors | REPORTABLE | no | 3.29 [3.18, 3.39] | 3.15–3.20 / 3.38–3.41 | 23.5% | 40.5 [35.7, 45.6] | 34.5–36.3 / 44.6–46.5 | 0.5% |
| 450 rows, 146 donors | REPORTABLE | no | 3.29 [3.18, 3.40] | 3.16–3.20 / 3.37–3.42 | 21.0% | 40.5 [35.4, 45.1] | 34.6–36.4 / 44.5–46.3 | 1.5% |
| 120 rows, 53 donors | REPORTABLE | no | 3.24 [2.99, 3.44] | 2.98–3.06 / 3.41–3.50 | 0.5% | 42.1 [32.4, 51.7] | 31.0–34.1 / 49.6–52.9 | 0.5% |
| 60 rows, 24 donors | SUPPRESS | no | 3.10 [2.78, 3.40] | 2.74–2.86 / 3.35–3.45 | 1.5% | 40.2 [30.1, 50.5] | 28.7–32.1 / 49.2–54.1 | 0.5% |

On the unit's own terms, a bound moves by up to 12 rounding steps (0.01 on the mean, 0.1 pp on
a share) when only the seed changes. The unit's seed is one draw of a Monte Carlo estimator. Matching
it exactly would be matching NumPy's PCG64 and its bounded-integer algorithm, which says nothing
about the method.

**Decision.** No PCG64. The aggregation contract (PR C chunk 5) is:
- **EXACT against the unit's captured output:** weights, Kish n, donor support and its status,
  suppression, point estimates (1e-9 before the unit's rounding, identical after it).
- **Intervals — the same estimator, not the same stream:** donor clusters of the selected layer
  (a missing id is its own cluster), uniform resampling of clusters with replacement, weight ×
  multiplicity, the call site's resample count, the 2.5/97.5 percentiles with linear interpolation,
  the unit's rounding. A fixture records the unit's bounds for each cell at K seeds, and AIA's bound
  must fall inside that envelope.
- **Deterministic:** AIA draws with `random.Random(seed)` using only `random()`, the one sequence
  Python guarantees across versions. The cluster index is `floor(u·m)`. The same input and seed give
  the same bounds, pinned by an AIA fixture of its own.
- `parity-matrix.json` `statistics.uncertainty` keeps NUMERICAL 1e-9 for support and estimates. The
  bounds get a documented deviation, landing with chunk 5's gate.

**Revisit when** a consumer needs AIA's bounds to equal an 18.6.6 report's printed numbers
(re-issuing a delivered report), or an acceptance criterion names bound equality. Only then is a
PCG64 port justified, and it would need its own named exception to §2.

**Status.** Decided for research aggregation, and implemented: `packages/aia_core/src/aia_core/domain/research_aggregate.py`, `test_research_aggregate.py` (EXACT fields, bounds within the unit's seed spread, AIA's bounds pinned), parity-matrix deviation D5.

**Resolution (2026-10-12).** The data owner determined that the PIAAC, ISSP and Czech panel
licences permit transmission to a model provider, approved for AIA's EU Bedrock route alone.
Recorded as policy data: `packages/aia_core/src/aia_core/domain/licence_determinations.py`
(`PANEL_APPROVED_ROUTE = "bedrock-eu-primary"`) @ `a7616ef`, PR #289; each determination names
the decider, the date and the basis. Any other route refuses panel lineage as
`licence_not_approved_for_route`
(`test_licence_gate.py::test_each_panel_derived_dataset_reaches_the_eu_bedrock_route_and_no_other`).
Residency is unchanged. **Not recorded:** legal's confirmation, which this item asked for beside
the data owner's; the basis is the owner's determination alone. Grounding respondents in the panel
is [`plans/panel-grounded-respondents.md`](plans/panel-grounded-respondents.md); until its chunk 5
lands no persona source reads the panel (OI-97).

**Status.** Closed by PR #289 (`a7616ef`).
---

## OI-63 · Direction recorded, engineering open · A fictional-client flag is not production data authority

**Claim.** A respondent request is `CLASS_C_INTERNAL` only when its personas are the
fictional roster *and* the Study's client is listed in `AIA_AI_FICTIONAL_CLIENT_IDS`
(`packages/aia_core/src/aia_core/domain/ai_respondent.py` `classify_material` @ `dec2fd1`);
every other questionnaire is treated as a client's design, Class A. The list is an
operator's deployment setting, refused in production.

**Anchor.** `apps/executors/tests/test_ai_fieldwork.py::test_a_real_clients_design_is_class_a_and_the_class_c_route_refuses_it`;
`packages/aia_core/tests/test_ai_respondent.py::test_material_is_class_c_only_when_client_and_personas_are_both_fictional`.

**Reproduction.** Unset `AIA_AI_FICTIONAL_CLIENT_IDS`: the run parks with
`egress_route_not_approved_for_class` and zero requests.

**Consequence.** On develop, only the seed's *(fiktivní)* clients, once listed, can
exercise AI fieldwork over ADR 0010's Class C route. Anyone who can set the parameter
can downgrade a client's designs to Class C.

**Data-owner direction (2026-09-28).** Stop treating a Study as fictional. A Study's production
state and the actual provenance/content of each item determine what can be sent. Do not add a
product "fictional client" attribute or promote this operator list into production authority.
Keep the existing allowlist confined to local/test synthetic fixtures, where the runtime already
refuses it in production. OI-79 owns the design-input classification gap; the respondent source
and any production Class A/B route also need their own approval and proof.

**Status.** Direction decided; implementation and production-route acceptance open. A local
fixture's Class C path is not evidence that client work has an approved egress route.

**2026-10-19 (#487).** The allowlist no longer lowers a design: fieldwork classifies the run's
design Class B by the owner's rule, raised and never lowered by an operator's classification or
the personas' class (`apps/executors/src/aia_executors/ai_fieldwork.py:418-432 @ 64cc1380`), so a
listed client's respondent request is Class B and a route approved for Class C alone refuses it
(`test_ai_fieldwork.py::test_an_unclassified_questionnaire_is_class_b_by_rule_and_a_class_c_route_refuses_it`).
The downgrade in *Consequence* is gone; the route's Class B approval and its retention are
ADR 0010's amendment of the same date. Production-route acceptance stays open.

---

## OI-64 · Follow-up · AI fieldwork restarts every respondent when an attempt is retried

**Claim.** A fieldwork attempt is one unit: a retry (transport failure, a quota park
resumed) asks every respondent again, and the earlier attempt's answered calls stay
charged (`apps/executors/src/aia_executors/ai_fieldwork.py` `AIFieldwork.produce` @ `dec2fd1`).

**Anchor / reproduction.** `apps/executors/tests/test_ai_fieldwork.py::test_throttling_parks_for_quota_after_one_request_and_charges_nothing`
parks on call 1; a park on call N would repeat calls 1..N-1 on resume.

**Consequence.** Cost, not correctness: at N=20 x 3 blocks the worst case repeats 59
calls. At production N it matters.

**Smallest fix.** Checkpoint each respondent's answers as a per-attempt artifact keyed by
(spec fingerprint, persona, block) and reuse it on the next attempt of the same run.

**Test that would catch it.** A resumed attempt sends only the calls the previous one did
not complete.

**Status.** Open; plan follow-up 2. *Re-confirmed at `ceee2dc`, 2026-09-27:* each attempt starts
at the first persona (`ai_fieldwork.py:167-173`), and `context.checkpoint()` only checks for a
stop and persists nothing (`apps/worker/src/aia_worker/context.py:125-138`). The attempts that
trigger it include a quota or capacity park resuming, a retryable failure, and a lapsed lease
with no call in flight. An uncertain call still goes to `RECOVERY_REQUIRED` and is never
retried. Owner: Job 6, inside the existing executor and recovery contract. Until it is fixed,
no acceptance claims to be retry-safe (`docs/architecture/research-journey.md` §7, line 6).
*Fixed behind a switch by #654 (merged as `d3f9df40`, 2026-10-22; `run-qc-and-checkpoint` RQC0):*
with `AIA_AI_FIELDWORK_CHECKPOINT` on, each answered respondent block is kept in
`fieldwork_journal` under the lease and replayed on a resumed attempt or a retry of the run
(`apps/executors/src/aia_executors/ai_fieldwork.py:166`, `ai_runtime.py:681 @ 6bfe3760`;
`infrastructure/fieldwork_journal.py`, migration `d1f3a5c7e9b2`;
`apps/executors/tests/test_ai_fieldwork.py::test_a_retry_of_interrupted_fieldwork_pays_only_for_the_blocks_never_answered`).
The switch is off by default and off on develop (`deploy/develop/docker-compose.yml:282 @ 6bfe3760`,
`${AIA_AI_FIELDWORK_CHECKPOINT:-false}`), so this stays open until it is on where runs are paid
for.
*2026-10-25 (the owner, AUD-8 (a), the audit page, relayed by coordinator 3):* turn the fieldwork checkpoint on, an operator
change through SSM; the infra session is preparing it. Open until it is on for develop.

---

## OI-65 · Follow-up · The usage ledger does not record the lineage a call declared

**Claim.** `ai_usage_events` has no lineage column; the licence gate's input for each call
is on the fieldwork dataset's provenance (`provenance.lineage`), not on the ledger row
(`packages/aia_core/src/aia_core/infrastructure/ai_usage_repository.py` `_row` @ `dec2fd1`).

**Consequence.** Auditing which datasets reached a provider needs the artifact as well as
the ledger. Panel lineage may now reach `bedrock-eu-primary` (OI-61, closed), but no persona
source reads the panel until `plans/panel-grounded-respondents.md` chunk 5, which needs this first.

**Smallest fix.** `AIUsageEvent.data_lineage` + a column + migration, written by the
gateway from the request. **Status.** Open; plan follow-up 6.



---

## OI-66 · Reproduced defect · Legacy startup overwrites saved study projects

**Claim.** Startup hydration replaces an edited `state_seed` with archive bytes,
losing working projects while PostgreSQL retains their study bindings.

**Anchor.** `legacy/npc-panel-18.6.6/runtime/hydrate_data.py:74` @ `0310091`.

**Reproduction.** Run `pytest packages/aia_core/tests/test_legacy_state_hydration.py`:
first hydrate, save a SQLite project, hydrate again. On the original code the
saved project vanishes. Live startup logged one copied data file; the Lumen
binding names `PRJ-bd16268b772b4c`, absent from the working project database.

**User consequence.** Research stages fail with “Projekt/revize nenalezena”.
Four older bound projects are absent; newer saved drafts still exist.

**Smallest fix.** Preserve existing `state_seed` files and retain strict checking
for new seeds/immutable assets. Add live SQLite backups before deployment, using
SQLite's backup API to include WAL. Keep the pinned application unchanged.

**Coverage.** `test_restart_preserves_saved_project_and_still_verifies_assets`;
`test_backup_captures_wal_edits_and_other_state_databases`.

**Recovery.** Two missing projects have native submitted design copies. No saved
copy has yet been found for the two other fictional demos. Recovery or explicit
recreation must preserve study identity and must not invent original content.

**Status.** Fixed in code: PR #57 @ `ff463a3`, deployed by run 25 (2026-09-27). The
recovery above is still open, and it is operational. The fix is a hand edit inside the frozen
unit (OI-68).

---

## OI-67 · Reproduced defect · A deploy under SSM stops on `HOME: unbound variable`

**Claim.** `ecr_login` reads `$HOME` under `set -u`, and SSM Run Command starts the
deploy as root with no `HOME`, so every deploy since PR #59 stops before pulling.

**Anchor.** `deploy/develop/bin/lib.sh:62 @ 043b0dd`
(`local config_dir="${DOCKER_CONFIG:-$HOME/.docker}"`); *Deploy develop* run 26
(`36309424041`), host output `bin/lib.sh: line 62: HOME: unbound variable`.

**Reproduction.** `pytest packages/aia_core/tests/test_develop_registry_credentials.py`
on PR #64's branch with `lib.sh` reverted: the two HOME-less tests fail with that
message.

**Consequence.** The host stays on `ff463a3`. PRs #59, #61, #54 and #62 are merged but
not deployed, and every dispatched deploy fails red.

**Smallest fix.** Resolve the config directory as docker does: `DOCKER_CONFIG`, then
`HOME`, then the passwd entry's home. Refuse, with a message, when none exists.
PR #64.

**Test that would have caught it.**
`test_a_deploy_without_home_writes_the_config_docker_reads`,
`test_a_deploy_with_no_home_anywhere_stops_and_says_why`.

**Status.** **Closed.** PR #64, merged 2026-09-27 10:29 (`96581bc`). Proven on the host by *Deploy
develop* run 28 (`36313351584`) @ `e0edf2a`: the SSM step passed, smoke passed every check, and
`/api/v1/health` and `/version` both report `e0edf2a`.

---

## OI-68 · Hypothesis · The OI-66 fix lives in a generated file that re-extraction would overwrite

**Claim.** PR #57 fixed OI-66 by editing `legacy/npc-panel-18.6.6/runtime/hydrate_data.py`
by hand (`65b5e9d`, `3932e5d`). `legacy/README.md` says the whole `npc-panel-18.6.6/`
tree is generated by `AIA-reference/tools/extract_legacy.py`, and that "nothing under it
is edited by hand". CLAUDE.md §2's map says "Frozen: regenerated, never edited", though its
prose narrows the rule to `app/`. Unless the same change is in the extractor's
copy, the next extraction restores the code that deleted saved projects.

**Anchor.** `legacy/README.md:5-8 @ 46b7337`; `git log -- legacy/npc-panel-18.6.6/runtime/`.
The file is not pinned by `runtime-assets.SHA256SUMS.txt` or `EXTRACTION.json`, so no
verification step would notice either way.

**Reproduction.** None here. The extractor is in the private reference repository,
which this session cannot read. A hypothesis until someone re-runs the extraction into
a scratch tree and diffs `runtime/`.

**Consequence.** If the hypothesis holds, a routine re-extraction silently brings back
OI-66's data loss.

**Smallest fix.** Land the same change in the reference repository's `runtime/` source.
Or state `runtime/` as an AIA-owned exception to "never edited" in `legacy/README.md` and
CLAUDE.md §2, and make the extractor refuse to overwrite it.

**Test that would have caught it.** `test_legacy_state_hydration.py` already fails on the
old code, so a re-extraction that reverts the fix turns CI red. The risk is a
re-extraction merged on a red CI, which OI-32's branch protection closes.

**Status.** Open (2026-09-27). Owner: whoever next runs `extract_legacy.py`.

---

## OI-69 · Reproduced defect · Two API test modules run a worker on in-memory SQLite

**Claim.** `test_research_api.py` and `test_runs_api.py` start a real `Worker` on
`:memory:` SQLite. The heartbeat thread's session close rolls back the shared
connection, and a step's artifact dependency then fails its foreign key.

**Anchor.** `apps/api/tests/conftest.py` `settings` (`:memory:` default) and
`packages/aia_core/src/aia_core/infrastructure/db.py` (`StaticPool`) @ `043b0dd`.
Diagnosed on PR #54 (comment, 2026-09-25).

**Reproduction.** Run
`pytest "apps/api/tests/test_research_api.py::test_research_artifacts_are_read_only_through_the_run_that_produced_them"`
40 times with `DATABASE_URL` unset: 3 failures in 41 runs on 2026-09-27.

**Consequence.** A red *Backend* job on any PR, unrelated to that PR's change.

**Smallest fix.** A file-backed database per test in those two modules, the rule
`AGENTS.md` already states. PR #65; 0 failures in 60 runs after it.

**Test that would have caught it.** The test itself, run repeatedly. The rule is now named
in `AGENTS.md` beside the worker's own conftest.

**Status.** Fixed: PR #65, merged 2026-09-27 10:30 (`e0edf2a`). Before it landed, the same race
also crashed CI on `develop` @ `46b7337` with a segmentation fault inside this test (run
36312008574; the crashing thread was in a worker transaction on the shared connection).

**Structural fix, 2026-09-27 (`claude/loving-hopper-qiflcr`).** PR #65 fixed the two modules; it
did not stop a third from doing the same. `Worker.__init__` now refuses a session factory
whose engine `shares_one_connection` (`apps/worker/src/aia_worker/worker.py`,
`_require_a_connection_per_thread`). The race is reproduced deterministically by
`apps/worker/tests/test_shared_connection.py::test_a_heartbeat_session_closing_mid_step_breaks_only_a_shared_connection`,
which closes a second session straight after the artifact row flushes and gets the reported
`IntegrityError` (foreign key, "Query-invoked autoflush", `project_artifact_dependencies`) on
`:memory:` and none with a connection per session. With PR #65's override removed, the
research test now fails 3 of 3 runs with that `ValueError`, instead of about one in fourteen.
The hypothesis of a duplicate edge on content-hash reuse is refuted: the Sociomap step's
`depends_on` is `[spec_id, dataset_id]`, two distinct ids, and the failing insert is the first
edge, whose parent row had been rolled back.

The known-flakes entry for this test in CLAUDE.md, added by `08bf3c7` and merged to `develop`
with PR #67 (`2beafd9`), was measured at `46b7337`, before `e0edf2a`, and named the wrong cause.
PR #69 removes it.

---

## OI-70 · Observed flake · BriefStep's problem-type toggle is read before it re-renders

**Claim.** `apps/web/src/components/rehome/research/BriefStep.test.tsx` › *a problem type
is a toggle that fills an empty goal with its default* clicks a tile and synchronously
expects `aria-pressed="true"`. It failed once with `expected 'false' to be 'true'`
(`BriefStep.test.tsx:99`).

**Anchor.** `BriefStep.test.tsx:97-99` @ `cfb1532` (2026-09-24); unchanged by PR #63.

**Reproduction.** Intermittent: 1 failure in 26 full `npm test` runs on a 4-core machine
(2026-09-27; 20 on #63 merged with `develop`, 6 on #63 before the merge). The same failure
hit CI once, on #68's *Frontend* job @ `78f1473` (a docs-only commit). The same day it was
reproduced 2 times in 61 runs of the test alone (`repeats: 60`), and 2 times in 6 full suites.

**Cause (confirmed).** The tile can be on screen before the research store is subscribed:
`useSyncExternalStore` subscribes in a passive effect, which runs after the commit that drew
the tile, and `findByRole` can resolve in between. The click's `store.update` then has no
subscriber, so nothing renders until the effect subscribes. With a log at the click, the 2
failures in 61 runs were exactly the 2 in which the same commit's other effect (the agents'
`agent-jobs` request) had not run yet; all 59 passes had it. The product renders the click a
moment later, so no click is lost; only the test's synchronous read is wrong.

**Consequence.** A red *Frontend* job on any PR, unrelated to that PR's change.

**Smallest fix.** Assert through `await waitFor(...)`, or find the pressed tile with
`findByRole("button", { name: …, pressed: true })`, not a synchronous read after the
click.

**Test that would have caught it.** The test itself, run repeatedly under load.

**Status.** Fixed in code: PR #71 (2026-09-27). The test waits for the pressed tile
(`findByRole(..., { pressed: true }, { timeout: 5_000 })`). 305 runs passed, 2 of them with
the click before the effects, and the full web suite passed 772 of 772. `AGENTS.md`
§ Next.js / TypeScript has the trap.

---

## OI-71 · Finding · Smoke reads the 18.6.6 unit's health before its first probe has passed

**Claim.** `smoke.sh` reads the unit's health once, about 20 s after `bin/deploy.sh` recreates it.
Docker reports `starting` until the unit's first healthcheck probe passes. The probes run every
15 s during a 120 s start period, so a healthy unit that is not up by the first probe (15 s) fails
the deploy.

**Anchor.** `deploy/develop/bin/smoke.sh:101-104 @ 85fa951` (one `docker inspect`, no wait);
`legacy/npc-panel-18.6.6/Dockerfile:50 @ 85fa951` (`--interval=15s --start-period=120s`).

**Reproduction.** *Deploy develop* runs 29 (`36314741586`) and 30 (`36315831550`): the host printed
`replacing services`, then `smoke tests` 19 s later, and `FAIL  legacy: the 18.6.6 unit is healthy`
with `state 'starting'`. Every other check passed. Run 28 (`36313351584`) had the same 19 s gap and
passed, because its unit was up by the first probe, and run 31 (`36316771795`, `2beafd9`) passed
too: 2 of the 4 deploys that reached smoke on 2026-09-27 failed on it. Offline:
`packages/aia_core/tests/test_develop_legacy_unit_health.py` on PR #70 fails all 5 tests against
the scripts @ `85fa951`.

**Consequence.** *Deploy develop* goes red although the new build is serving, and "Confirm from
outside" is skipped. The failure message points the operator at the data bundle, which was fine.

**Smallest fix.** Wait out `starting` in the smoke read only, bounded (PR #70:
`lib.sh` › `legacy_unit_health`, at most `LEGACY_START_WAIT_SECONDS`, default 150). The fix is not
`compose up --wait` on the unit, which OI-44 removed so that a broken unit cannot keep the site
down.

**Test that would have caught it.** `test_develop_legacy_unit_health.py` (PR #70).

**Status.** Fix in code: PR #70 (draft, 2026-09-27). It is proven on the host only by the first
deploy that carries it. **Fixed:** #70 merged into `develop` at 15:52. **Moot** once increment 5
of ADR 0018 lands (`feature/deploy-without-legacy` @ `9138977`): the product's smoke no longer
reads the unit's health, and `legacy_unit_health` and `test_develop_legacy_unit_health.py` go
with the unit; the smoke checks instead that no unit path answers and no unit container of
the product project exists (`test_develop_unit_retirement.py` › *the smoke check says the
product runs no unit and kept its volume*).

---

## OI-72 · Finding, fixed in code · Settings said AIA runs on the Claude Code subscription

**Claim.** `GET /api/v1/settings` presented `claude_code_subscription` under `CLAUDE_CODE_ONLY`
as AIA's AI default, listed the prototype's providers and policies as choices, and offered a
project provider policy and a per-project API ceiling "on the project screen", while the worker
builds exactly one provider, Bedrock, and holds native spend to the Study budget.

**Anchor.** `apps/api/src/aia_api/routers/settings.py:172-184, 204-220, 386-387 @ ceee2dc`;
`apps/web/src/components/aia/settings/ControlPanel.tsx:135-147, 489-517 @ ceee2dc`;
the card above it, `apps/web/src/components/aia/GlobalPages.tsx:110-124 @ ceee2dc`
("Připojení spravuje AIA" whatever the switch said). The worker's one provider:
`apps/executors/src/aia_executors/ai_runtime.py:259-298 @ ceee2dc`.

**Reproduction.** `apps/api/tests/test_settings_api.py` ›
`test_no_native_choice_or_default_is_spelled_as_the_prototype` fails against the router
@ `ceee2dc`; on develop, the *AI poskytovatelé a modely* section of `/app/settings`.

**Consequence.** A researcher reading Settings was told AIA needs a Claude Code subscription
and that project fields steer model choice and spend; neither is true of a native run.

**Smallest fix.** Describe the native runtime from code, show the switches from `/config`,
never claim a connection, and keep the prototype's identifiers as history
([plan](plans/truthful-ai-controls.md)).

**Test that would have caught it.** The test above;
`test_the_runtime_is_bedrock_from_code_and_claims_no_connection`;
`apps/executors/tests/test_settings_presentation.py`; `ControlPanel.test.tsx` › *what powers AIA*.

**Status.** Fix in code on `fix/truthful-ai-controls` (draft PR). Not merged, not deployed.

---

## OI-73 · Handoff · Research editing and the classic projects screen still speak the subscription runtime

**Claim.** The research stages' unit-backed jobs, their store and the classic projects screen
still label or write work in the prototype's subscription terms: the job cost line
"subscription · API $0 · tokeny po dokončení", the pause note "Čekám na dostupnost Claude
Pro.", `run_policy.provider = "claude_code_subscription"` written into the unit's project, the
provider tag "Claude Code" and "Projekt čeká na obnovení Claude Code kreditů".

**Anchor.** `apps/web/src/unit/research/jobs.ts:86-87, 137 @ ceee2dc` (imported by
`components/rehome/research/JobPanel.tsx`); `unit/research/model.ts:61` (`PROVIDER_FORCED`),
`unit/research/brief.ts:141, 176`, `unit/research/questionnaire.ts:359-393`,
`unit/research/store.ts:49`; `unit/projects.ts:239, 247`,
`components/rehome/projects/ProjectCard.tsx:46`; the unused rail labels
`rehome.navSettingsClaude`, `rehome.statusClaude` (`i18n/cs.ts:468, 471 @ ceee2dc`).

**Reproduction.** `grep -rn 'claude_code\|Claude Pro\|subscription · API' apps/web/src/unit apps/web/src/components/rehome`.

**Consequence.** Wherever a stage still follows a unit job, a researcher can see subscription
wording that Settings no longer uses; the unit's stored project names a provider no native
run reads.

**Smallest fix.** Owned by the phase-out agent (research draft serialization, classic
screens, legacy navigation): drop the subscription branches when each stage leaves the
unit's store (OI-58), and delete the two unused rail labels.

**Test that would have caught it.** A text check like `ControlPanel.test.tsx`'s `OVERCLAIM` /
`LOGIN` patterns over the research job panel.

**Status.** Open. Found by the truthful-ai-controls audit, deliberately not edited there.

---

## OI-74 · Question · The generic project API still stores provider fields no native run reads

**Claim.** `PATCH /api/v1/studies/{study_id}/projects/{project_id}` still accepts and stores
`preferred_provider`, `provider_policy` and `max_api_cost_usd`; no native execution path reads
them (native models come from the worker's policy, native spend from the Study budget).

**Anchor.** `apps/api/src/aia_api/schemas/projects.py:31-35 @ ceee2dc`;
`packages/aia_core/src/aia_core/infrastructure/repositories.py:532-577 @ ceee2dc`.

**Reproduction.** `grep -rn "max_api_cost\|provider_policy\|preferred_provider" apps/*/src packages/aia_core/src/aia_core/application`
finds the project repository and schema only.

**Consequence.** An API client can set a value that looks like a control and changes nothing;
Settings now says so (`ai_history`), but the route still accepts it.

**Question.** Freeze them (read-only, kept for persisted projects) or retire them from the
request schema? Owner: whoever owns the generic projects API. Not a blocker for anything.

---

## OI-75 · Question · Should Settings show recorded evidence that the runtime answered?

**Claim.** Settings can say a capability is switched on in configuration, never that it works:
the only truthful *verified* signal without a probe is the usage ledger's last `SUCCEEDED`
call per activity, and reading it for Settings would be an organization-wide query across
every client's studies.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/tables.py:1203-1290 @ ceee2dc`
(`ai_usage_events` carries `organization_id`, `capability`, `model`, `route_id`, `outcome`);
`ARCHITECTURE.md` §3 ("only the work queue may query across studies").

**Question.** Is an aggregate (last success time, model and build per activity, no client or
study identifiers, owners and admins only) an acceptable second cross-study read, or does
evidence stay on each Study's runs? Until decided, Settings says *Neověřeno* and points at the
runs. Data owner + integration-architecture.

**Status.** Decided 2026-10-25 (the owner, OI-75 (a), the audit page, relayed by coordinator 3): "allow the aggregate" (last
success time, model and build per activity, no client or study identifiers, owners and admins
only). Open until Settings reads it, as a named second cross-study read in `ARCHITECTURE.md` §3;
no chunk builds it yet. To be built by `settings-redesign` F14.
**Closed 2026-10-26 by #922** (merged as `f7b2f381`): `GET /settings/ai-activity` answers each activity's last answered
call from the usage ledger (`infrastructure/ai_usage_repository.py:463 @ f7b2f381` `last_answered_calls`), OWNER and
ADMIN, no client, study, person or cost; recorded in `ARCHITECTURE.md` §3 as the second cross-study read.

---

## OI-76 · Finding, fixed · Native Research screen tests fail on a /config failure an earlier test left cached

*Filed as "Observed flake · Native research-agent screen tests outrun their 15 s budget under
load" on `fix/truthful-ai-controls` (PR #75), and closed here, where the fix lands. When #75
merges, this entry replaces its copy.*

**Claim.** In a full web run, a research test file's native jobs can all fail at their first
request: the file's first test can leave `loadConfig()` holding a rejected `/config` read, and
`loadConfig()` kept it for every later test in the file. A test waiting for a review dialog then
times out at its full 15 s wait; one waiting for the failure card fails fast on its message.

**Anchor.** `apps/web/src/lib/auth.ts:30-40 @ dd27f68` (`loadConfig` keeps its first promise,
rejection included, and nothing resets it); `apps/web/src/components/rehome/research/useResearchAgents.tsx:43-46 @ dd27f68`
(the mount effect's `refresh()`, the request that outlives its test) and
`apps/web/src/lib/api.ts:22-25 @ dd27f68` (`request()` awaits the token, then `loadConfig()`). As
first reported: `test-native-agents.ts:53 @ ceee2dc` (`NATIVE_JOB_WAIT`). Failing tests:
`AudienceStep.test.tsx` › *reviews an audience proposal while preserving researcher-controlled
filters*; `BriefStep.test.tsx` › *runs the analysis as a job…*, *requests a frozen native
context…*, *explains the unavailable design capability…* and *shows the native failure…* (the
fast one); `PlanStep.test.tsx` › *answers the follow-up questions…* and *comments on selected
text…*, found here.

**Reproduction.** Deterministic, one file: give `BriefStep.test.tsx` a
`beforeAll(() => loadConfig().catch(() => {}))`, so its first `/config` read goes through the real
`fetch` as the leaked request's does, and run `npx vitest run src/components/rehome/research/BriefStep.test.tsx`
in `apps/web`. On `dd27f68` 4 of 9 fail, OI-76's pattern exactly: three at 15.1 s and *shows the
native failure…* at 139 ms. Under load, as first seen: the full `npx vitest run`, one 4-core cloud
container, 2026-09-27. `dd27f68` failed 2 of 10 runs (AudienceStep at 15 093 ms; the two PlanStep
tests at 15 252 and 15 277 ms). The first report had `ceee2dc` 2 of 6 and `fix/truthful-ai-controls`
1 of 8. Every failing file passes alone.

**Cause (confirmed).** A research screen's first request is the agents' `agent-jobs` read, from
the mount effect of `useResearchAgents`. A file's first test can end on a `findBy*` that resolved on
the commit that drew the screen, before that commit's passive effects ran (the OI-70 gap). The
`afterEach` then calls `cleanup()`, and React runs the pending mount effect while it unmounts
(`cleanup → unmount → flushPendingEffects → flushPassiveEffects`). The effect's request is still
awaiting its token when `vi.unstubAllGlobals()`, the next line, restores the real `fetch`. Its next
step, `loadConfig()`, finds the cache empty and reads `/config` through the real `fetch`, which under
jsdom rejects a relative URL at once (`TypeError: Failed to parse URL from /config`). `loadConfig()`
kept that rejection, so every native request later in the file failed at `loadConfig()`. The jobs
never reached review, and the failure card and the agents' notice both read *Failed to parse URL
from /config*. The fast failure is the same cause, not fallout from the test before it: its card
showed the config error where the test expects `MODEL_TIMEOUT: nic se nevrátilo`. Measured with
probes on the mount effect, on `loadConfig()` and on the real `fetch` (an experiment, not
committed): 5 of 10 instrumented full runs failed, and each had exactly one research request through
the real `fetch`: `/config`, from the failing file's first test, with the cache empty. The 5 passing
runs had none. With the full stack recorded, the effect that leaked ran inside `cleanup()`, the only
one of that run's 62 that did. Not a timer, and not load: in the 10 baseline runs the same tests
passed in at most 0.9 s (at most 0.99 s in the 20 runs with the fix), and failed only at the full
15 s.

**Consequence.** A red *Frontend* job on pull requests that never touched the research screens,
because CI runs the whole Vitest suite. The same code in the product: once a page's one `/config`
read failed (a deploy replacing the web container, a dropped connection), every later API call on
that page failed with it until a reload. That follows from the code and `auth.test.ts` pins it;
nobody has reported it from a browser.

**Smallest fix.** Two changes, each enough on its own for the reproduction:
1. `loadConfig()` does not keep a failed read; the next call reads `/config` again, as `loadBoot()`
   already does (`apps/web/src/lib/auth.ts` › `loadConfig`).
2. `nativeAgentFixture` empties the config cache (`resetConfigCache()`, tests only) before each
   test stubs `fetch`, and again when the test finishes, so a test's requests read `/config`
   through its own stub (`test-native-agents.ts`).

No wait was changed: a larger one would only have made the failures slower. The leaked request
still runs, harmlessly. `request()` takes no abort signal, and giving it one would change
`useResearchAgents` (PR #74's file), which this fix leaves alone.

**Test that would have caught it.** `apps/web/src/lib/auth.test.ts` › *does not keep a failed read:
the next call reads /config again* and *does not keep a refused answer either*; both fail against
`dd27f68`'s `loadConfig` given only the reset hook. The one-file reproduction above.

**Status.** Merged in PR #83 (`fix/native-tests-config-cache`, 2026-09-27). The reproduction passes
9 of 9 with both changes, and with each alone. Full runs with the fix, on the same container:
20 of 20 passed, 776 tests each, where `develop` @ `dd27f68` failed 2 of 10. Under doubled load
(both trees' full suites at once, the Python suites alongside), `develop` passed 8 of 8 and this
branch 7 of 8. That one failure was an unrelated test, `ClientFirst.test.tsx` › *loads the working
content its AIA binding names…*: a separate race that `develop` has too, since it fails the same way
on `dd27f68` when the stage's load starts 30 ms late (described in PR #83). `AGENTS.md`
§ Next.js / TypeScript has the trap. Owner of the research screens: job 6 / the phase-out agent.
PRs #74 and #77 touch neither `auth.ts` nor `test-native-agents.ts`, and their rewritten tests
call `nativeAgentFixture`, so they carry the reset.

---

## OI-77 · Reproduced defect · A corrupt artifact's CORRUPT mark is rolled back with the read that found it

**Claim.** `ArtifactRepository.read` flushes `CORRUPT` onto an artifact whose bytes fail
verification (a hash mismatch or a missing object) and re-raises, and every caller then ends its
transaction on that exception, so the mark is rolled back and the artifact stays `VALID`.

**Anchor.** All @ `ceee2dc`, unchanged at `dd27f68`:
- `packages/aia_core/src/aia_core/infrastructure/artifact_repository.py:411-418`: `read` marks,
  flushes and re-raises. `:262-267`: `find_reusable` checks only that the object exists.
- The API: `apps/api/src/aia_api/routers/runs.py:325` and `routers/research.py:611` answer 409
  `artifact_corrupt`; `routers/research.py:671-686` (`_agent_errors`) maps no storage error, so the
  proposal read at `packages/aia_core/src/aia_core/application/research.py:328` becomes a 500;
  `apps/api/src/aia_api/dependencies.py:129-131`: `get_session` rolls back on either.
- The worker: `apps/worker/src/aia_worker/context.py:267-269` (`StepContext.transaction` rolls
  back), `apps/worker/src/aia_worker/worker.py:383-390` (the step fails `UNKNOWN`), with the readers
  `apps/executors/src/aia_executors/research.py:114-116` (`_read_spec`, first called at `:228`) and
  `apps/executors/src/aia_executors/research_agents.py:121-123` (the proposal reuse check).

**Reproduction.** Reported 2026-09-27 on `develop` @ `ceee2dc` with PostgreSQL 16; reproduced the
same day at `dd27f68` on PostgreSQL 16 and on file-backed SQLite.
- *API, as reported.* `apps/api/tests/test_runs_api.py::test_a_corrupt_artifact_stays_marked_corrupt_after_the_409`
  and `test_research_api.py::test_a_corrupt_research_artifact_stays_marked_corrupt_after_the_409`,
  each `[tampered]` and `[missing]`: 4 of 4 answered 409, then failed on
  `assert 'VALID' == 'CORRUPT'`.
- *API, the proposal read.* `test_research_agent_jobs_api.py::test_a_corrupt_proposal_is_a_409_and_stays_marked_corrupt`:
  `GET …/research/agent-jobs/{run}/result` and `POST …/accept` answered 500 `internal_error`
  (read through a `TestClient` with `raise_server_exceptions=False`), and the row stayed `VALID`.
- *Worker.* With `test_research_api.py`'s `submit`, `start` and `_real_worker(app, workbench=False)`:
  run one step (compile), tamper with the spec's object (`damage_artifact`), run the next. Preflight
  fails `UNKNOWN` and the spec is still `VALID`. Retry the run: its compile reuses the same spec
  (same artifact id), and its preflight fails `UNKNOWN` again. A scratch test, run once on
  PostgreSQL 16, not committed.

**Consequence.** A tampered or truncated artifact reads `VALID` in every listing (the client
overview's recent outputs among them), and nothing durable tells an operator. `find_reusable` keeps
offering it, so a retried research run reuses the corrupt artifact and fails the same way: the run
cannot recover by retry. The proposal routes answered 500 instead of 409. On the worker the step's
`error_message`, which the browser reads, is the storage error's text, and that carries the
storage key (`org/…/client/…/study/…`), which a client is never to receive
(`docs/architecture/artifacts.md` § Read protocol).

**Deep Research (#81, not merged).** Its six steps read the same way, inside
`StepContext.transaction`: every upstream record and every reused unit goes through `_Step._read`
(`apps/executors/src/aia_executors/deep_research/_shared.py:176-177` @ `65eb50c`, unchanged at
`ae6f55f`), and a reusable unit is found by `find_reusable`, which checks only that the object
exists. Reproduced once at `ae6f55f` on file-backed SQLite, a scratch test not committed:
`apps/executors/tests/test_deep_research_journey.py`'s `pass_one`, then the stored bytes (not the
row) of a completed track that pass 2 reuses altered, then pass 2. Investigate fails `UNKNOWN`
with an `IntegrityError` whose message carries the storage key, no paid call is dispatched, and
the track is still `VALID`; retrying the run fails the same way. Reuse there is across runs, by
fingerprint, so one corrupt completed track, snapshot or verification batch fails every later run
of that Study that plans the same unit. The worker fix, once decided, is needed in `_Step` too, and
its recompute question is the same one: a recomputed track costs model requests and tool calls.

**Smallest fix.** *API:* commit the mark before raising, in one place: `routers/runs.py` ›
`artifact_corrupt`, used by both artifact routes and by `_agent_errors`. Not taken: the repository
recording `CORRUPT` in its own short transaction. That changes the shared "flush, never commit"
contract, and a second connection that writes the row once the request holds its lock waits on the
request itself. Measured 2026-09-27 with a scratch table, after an uncommitted `UPDATE` on the first
connection, as `read` leaves it: the second connection's `UPDATE` waited out a 2 s `lock_timeout` on
PostgreSQL 16 (with no timeout it waits for ever, since the request is waiting on it) and got
`database is locked` after SQLite's busy timeout. On in-memory SQLite's single shared connection it
would instead commit the caller's half-done work (`AGENTS.md` § SQLAlchemy and PostgreSQL,
*In-memory SQLite cannot serve two threads*). *Worker:* an executor that reads an upstream artifact
returns a `Failed` outcome from inside `StepContext.transaction` instead of raising, so the
transaction commits the mark, with a message that names the step and not the key. Still to decide:
the failure class (`MISSING_CONFIGURATION`, as `_missing_upstream` uses for an upstream step with no
artifact, or a new one), and whether the proposal executor's reuse check falls through to a fresh,
paid call.

**Test that would have caught it.** The API tests above, which read the stored status from a
session of their own (`apps/api/tests/conftest.py` › `artifact_status`), not only the response. For
the worker, the reproduction as an executor test: the stored status after the failed step, and a
retried run that recomputes the spec.

**Status.** API half merged: PR #84 (`8c13a11`, 2026-09-27), both artifact routes and the
proposal routes. The native attachment download is also fixed in #86 (`e4690b4`):
`routers/workspace.py` › `download_study_file` uses `artifact_corrupt` to commit the
mark before its 409. Regression: `test_client_api.py::test_a_damaged_attachment_stays_marked_corrupt_after_the_409`
(tampered and missing objects). Worker half open. It is not fixed there because it needs the failure-class
decision and, for design jobs, a decision to spend on a recompute. The native analysis
executor (#80) keeps the mark already. Every source refusal, `source_corrupt` included, is
returned from inside its transaction as `SCHEMA_VIOLATION`, the class it gives every
other source refusal, and the message names no storage key
(`test_analysis_executor.py::test_a_corrupt_ai_dataset_fails_the_module_and_stays_marked_corrupt`,
`test_analysis_results.py::test_a_corrupt_source_is_refused_by_reason_without_its_storage_key`).
The recompute question belongs to the step that produced the artifact, not to that reader.
If the decision picks another class, `_sources_refused` in `aia_executors/analysis.py` is the
one place to change.

---

## OI-78 · Finding · An evidence row that names no data origin is admitted as observed data

**Claim.** `EvidenceRow.data_origin` defaults to `None`, and the admission gate refuses a
client-facing claim only when the origin is in `NON_EVIDENCE_ORIGINS`. A row that does not say
where its respondents came from is therefore admitted client-facing, as if it were observed
data: *unknown* scored as *good* (CLAUDE.md §8).

**Anchor.** `packages/aia_core/src/aia_core/domain/evidence/admission.py:91` (the default) and
`:244` (the check) @ `ceee2dc`. `DataOrigin` has no value for observed data at all, only the two
synthetic ones (`domain/fieldwork.py:50-68`).

**Reproduction.** `pytest packages/aia_core/tests/test_analysis_runner.py::test_a_passing_first_draft_completes`.
It uses the shared `evidence_row` fixture, which sets no `data_origin` (`tests/conftest.py:807-839`),
and completes a `CLIENT_FACING` module from it.

**Consequence.** Nothing is wrong yet, because no production code builds an `EvidenceRow`. But
the first adapter from a fieldwork aggregate to an `EvidenceTable` (Job 3) needs only to forget
to copy `aggregate["data_origin"]` (`domain/research_aggregate.py:571`). With that one omission,
fictional respondents become client-facing claims, and no error is raised.

**Smallest fix.**
- Make `data_origin` required on `EvidenceRow`, with an explicit value for observed data once
  real fieldwork exists.
- Until then, refuse a `CLIENT_FACING` claim whose row names no origin.
- Every adapter copies the dataset's origin onto each row it builds.

Changing the gate changes the shared test fixture as well; that is the point.

**Test that would have caught it.** Admitting a `CLIENT_FACING` claim from a row with
`data_origin=None` is refused.

**Status.** Closed 2026-10-25 (see the dated line below; was: Open. Owner: Job 3, with evidence governance, before or together with the aggregate
adapter). It is a rule of the research journey's contract (`docs/architecture/research-journey.md`
§4, §6 rule 6).

*2026-09-27, 18:05 UTC:* Job 3's draft PR #76 @ `7c46e0c` closes the path for native instrument
evidence. Its rows carry the aggregate's origin, and its instrument policy refuses a row that
names none (`domain/evidence/instrument.py:132-139`). The gate's default is unchanged
(`admission.py:91, 244`), so this stays open for any other builder of an `EvidenceRow`. Its
number follows the contract's rule for concurrent entries (§5). It was OI-72 on this entry's branch
until #83 put OI-76 on `develop` (`48bf3e2`, 22:45 UTC). #84 merged OI-77 at 23:09 UTC (`8c13a11`), and #75 still claims OI-72 to OI-75.
**2026-10-25:** closed. `packages/aia_core/src/aia_core/domain/evidence/admission.py:241 @ 5d5ed250` admits a `CLIENT_FACING` claim only from a row whose origin is in `CLIENT_ADMISSIBLE_ORIGINS`, so a row naming no origin is refused; test `packages/aia_core/tests/test_evidence_instrument.py::test_a_row_with_no_origin_no_longer_slips_the_origin_gate` (on develop since #729's merge, `4c142761`, 2026-10-22).

---

## OI-79 · Direction recorded, engineering closed (#487) · Classify actual design inputs before model egress

**Claim.** A native design job sends the brief's attachment text to the model, and classifies the
request by only two things: the client allowlist and the approved knowledge. A study of an
allowlisted fictional client with no approved knowledge sends its attachments' text as
`CLASS_C_INTERNAL`. No rule classifies an attachment's content on its own.

**Anchor** (all @ `56b5768`):

- `context_snapshot` copies the whole design into the context
  (`packages/aia_core/src/aia_core/domain/research_agents.py:218-251`; `:225`);
- the request's class comes from `fictional_client` and knowledge only (`:273, 294-296`);
- the snapshot is the whole Design Revision (`application/research.py:245-248`), and
  `fictional_client` is the allowlist (`apps/executors/src/aia_executors/research_agents.py:129`);
- the brief keeps each file's `context_excerpt` and up to 22 000 characters of attachment text in
  `briefing.attachments_context`, as 18.6.6's `briefAttachmentContext1785` did
  (`apps/web/src/unit/research/brief.ts:101-111`);
- the documented rule names knowledge, not attachments (`docs/architecture/research-agents.md:49-53`).

**Reproduction.** Prints `CLASS_C_INTERNAL True`:

```
python -c "from aia_core.domain.research_agents import ResearchAction as A, agent_request, context_snapshot; r = agent_request(A.ANALYZE, context_snapshot({'briefing': {'attachments': [{'kind': 'file', 'filename': 'zadani.docx', 'context_excerpt': 'TEXT Z PRILOHY'}]}}, []), instruction='', policy_version='p', fictional_client=True, max_output_tokens=512); print(r.data_classification.value, 'TEXT Z PRILOHY' in r.messages[0].content)"
```

**Consequence.**

- Nothing is sent today: the design jobs are off on develop (`AIA_AI_RESEARCH_AGENTS_ENABLED`,
  `deploy/develop/docker-compose.yml:176`).
- Once they are on, a document someone attaches to an allowlisted client's study leaves AIA
  under ADR 0010's Class C approval, which does not cover confidential material, up to the 64 KB
  context cap. Pasting the same text into the brief does the same. The allowlist (OI-63) is the
  only control.
- A real client's requests are Class A, and the approved route refuses them.
- The phase-out owner's draft PR #74 stores attachments in AIA and fills the same fields
  (`POST /api/v1/studies/{id}/workspace/attachments`), so this path no longer runs through the
  unit.

**Data-owner direction (2026-09-28).** A Study is not declared fictional to decide egress.
Classify each material input by actual provenance and content, including a file's extracted text
and text pasted into the brief. Client-supplied or unknown content cannot inherit Class C merely
because a local test client is allowlisted. A request takes the most restrictive class of its
parts; unknown classification refuses the model call. Class A/B material still needs an approved
route before any live send. A generated test fixture may exercise Class C only when its own
synthetic provenance is established; that does not authorize a production Study.

**Engineering fix.** Job 6, owner of the design jobs' context and request, must carry the
classification of attached and pasted material into `agent_request`, or omit unclassified text
from a Class C request. Preserve the exact material fingerprint and the resulting class in the
request's audit record. Add tests where (1) a synthetic local fixture uses its recorded Class C
route, (2) an allowlisted local client with uploaded or pasted client/unknown text is refused
before dispatch, and (3) approved knowledge and another client's material cannot lower the
request's class. The existing reproduction above must change from `CLASS_C_INTERNAL True` to a
refusal or a more restrictive request under the chosen implementation.

**Status.** Direction decided; code still has the unsafe inheritance shown above, and design
jobs must remain off for studies with unclassified attachments or pasted material. Numbered
OI-73 on this entry's earlier branch until #83 put OI-76 on `develop`; renumbered under the
contract's concurrent-entry rule (§5). This is not a new approval for Class A/B egress.

**2026-10-19 (#487).** The unsafe inheritance is gone: a design job's design, its pasted text and
attachment excerpts included, is Class B by the owner's rule, a nonempty instruction too, and
approved knowledge raises the request to A (`packages/aia_core/src/aia_core/domain/research_agents.py:638-686 @ 64cc1380`,
`design_classification`, `agent_request`; no client flag is read). The reproduction above, without
the `fictional_client` argument that no longer exists, prints `CLASS_B_DERIVED_CLIENT True` at
`0b4e05e5`; such a request goes only on a route approved for Class B
(`test_research_agent_executor.py::test_an_edited_design_or_instruction_is_sent_as_class_b_by_rule`).
That the excerpts are B as design while the same bytes as a client source are A is the owner's
decision (OI-130). The engineering fix is done; what remains is the route's Class B approval
(ADR 0010, Amendment 2026-10-19).

---

## OI-80 · Finding, one cause fixed in code · The develop smoke's `ScopeDenied: not found` has three reproducible causes

**Claim.** `seed_develop` resolved the operator's organization context before adding a
returning operator who was not a member, so its "becomes one" branch could never run. A
changed `AIA_SEED_OWNER_EMAIL` was denied as `not_a_member`. Two other host states give the
same bare message: an archived seed client (`client_archived`) and a deactivated owner
(`user_deactivated`). The smoke printed none of the reasons.

**Anchor.** `packages/aia_core/src/aia_core/application/develop_seed.py:204-210 @ 8017b54`
(context before membership); `apps/executors/src/aia_executors/smoke.py:237-238 @ 8017b54`
(no reason printed); the denials in `application/scope.py:108, 122, 245`.

**Reproduction.** `apps/executors/tests/test_seed_and_smoke.py` ›
`test_seed_admits_a_new_operator_to_an_existing_world` fails before the fix;
`test_seed_names_why_an_archived_seed_client_is_denied` pins the archived case.

**Consequence.** Deploy runs 36, 37 and 38 replaced every service and then failed smoke, and
the operator could not tell which row to look at.

**Smallest fix.** Add the operator as owner before resolving the context (done); print a
denial's reason in the smoke line (done, `smoke.describe_failure`). An archived client or a
deactivated owner is a person's decision, which the seed does not undo.

**Status.** The operator membership is fixed on `develop` by #87 (`28eedce`) and in the
release (`73d3136`). Deploy run 40 of `28eedce` then named the develop host's state:
`client_archived`, an archived client in the seed organization.
- **An archived showcase client.** The seed resolved a context on each of its two showcase
  clients, so archiving either one failed every deploy. #88 makes the seed leave such a
  client as it is, with a test that fails before it:
  `test_seed_leaves_an_archived_fictional_client_as_it_was`.
- **The smoke's own `synthetic-client`.** Deploy run 41 of `92a0bdd`, #88's merge, still read
  `client_archived`. With the showcase clients left alone, that is `synthetic-client`: the smoke's
  own client is archived on the host.
  - The seed does not undo that. Un-archiving it in Settings is a person's decision, and
    `access_audit` (`CLIENT_STATUS_CHANGED`) says who archived it and when.
  - If it was archived on purpose, the smoke needs a client of its own.

**Open:** that decision. Every code cause found is fixed.

## OI-81 · Question · Migrating a closed Study means reopening it, and delivering it again rewrites `delivered_at`

**Claim.** The 18.6.6 content migration leaves a Study that no longer accepts work
(delivered, archived or cancelled) waiting until someone reopens it. Delivering it again
after its migration stamps a new `delivered_at`, so the Study stops saying when it was first
delivered.

**Anchor.** `packages/aia_core/src/aia_core/application/workspace_migration.py:306-307 @ b0ce309`
(the `accepts_work` gate); `packages/aia_core/src/aia_core/infrastructure/scope_repository.py:576-577 @ b0ce309`
(every change to `DELIVERED` stamps `utcnow()`).

**Reproduction.** The cutover dress rehearsal of 2026-09-28, fictional Study S7 (see
`.planning/overview.md`). This is a rehearsal run, not yet a test.
1. A `DELIVERED` Study bound to an 18.6.6 project is reported `NOT_MIGRATED`: *the Study is
   DELIVERED: reopen it to migrate*.
2. After `ACTIVE`, then `--apply --study <id>`, then `DELIVERED` again, its `delivered_at`
   moved from 19:52:23 to 19:57:26 UTC.

**Consequence.** After the cutover the unit is out of the product, so such a Study's
content cannot be read in AIA until it is reopened, and reopening it rewrites its delivery
time. How many such Studies the develop host has is not known until its dry run.

**Options.**
1. Let the migration write a closed Study's content without reopening it. The migration moves
   storage and starts no work. This is a change to that gate, with a test.
2. Keep the gate, and stamp `delivered_at` only on the first delivery, with a test.
3. Change nothing: the owner reopens the Study and accepts the new time.

The data owner decides; nothing changes until then.

**Status.** Open. It needs an answer before the cutover only if the host's dry run lists a
closed Study.
**Decided 2026-10-25 (the owner, OI-81 (b), the audit page, relayed by coordinator 3):** "keep the gate; stamp the delivery date
only once" (option 2). The owner's note, verbatim: "lets delete old studies"; the coordinator is
asking what it means, and it is recorded here unapplied until clarified. Open until
`delivered_at` is stamped on the first delivery only, with a test; no chunk builds it yet. The gate stays where it is; deleting old studies is the plan `study-deletion.md`.
**2026-10-25:** "Smazat studii" is planned in `study-deletion.md` (#894, merged as `b2606edc`), with ADR 0043 (`docs/architecture/adr/0043-study-deletion.md`) Proposed; nothing built until the owner answers its SD0. The `delivered_at` fix above is unchanged.
**2026-10-26:** the owner answered `study-deletion` Q1-Q8 (Q1 (b), a 7-day window; Q2-Q8 as recommended) and accepted ADR 0043; SD0 is done, SD1-SD11 wait on scheduling.

## OI-82 · Requirement · A Knowledge change an AI writes will need its own approval-ledger row

**Claim.** ADR 0019 gate 1 records every accept of what the AI produced in the approval ledger.
Today the only AI proposal is a research agent's design proposal, and its accept is recorded
(`subject_type = 'ai_proposal'`, #123). No code path lets an AI author a Knowledge proposal, so
`ClientKnowledgeRepository.decide` writes no such row, on purpose: every Knowledge proposal is a
person's, and recording it as the AI's would stamp a guess.

**Anchor.** `propose_from_study` has two callers, a person's route
(`apps/api/src/aia_api/routers/workspace.py:1225 @ 0c42547`) and the develop seed
(`packages/aia_core/src/aia_core/application/develop_seed.py:453 @ 0c42547`); no executor
proposes Knowledge. The design accept's row: `WorkflowRepository.record_ai_proposal_acceptance`
(`packages/aia_core/src/aia_core/infrastructure/workflow_repository.py @ b643a70`).

**Reproduction.** Not a defect today: there is nothing to record.
`grep -rn "propose_from_study\|\.propose(" --include=*.py packages apps` lists the callers.

**Consequence.** None yet. The day an executor proposes Knowledge, its accepts will be missing
from the ledger unless that change adds them.

**Smallest fix.** In the change that first lets an AI propose Knowledge: mark the proposal as
AI-authored, and make `decide` write one `ai_proposal` row for it, in the same transaction.

**Test that would catch it.** The one #123 added for design accepts
(`apps/executors/tests/test_research_agent_executor.py`
› `test_worker_stores_proposal_and_review_creates_a_new_revision`), written for Knowledge.

**Status.** Open, waiting on the first AI author of Knowledge. Plan
`two-roles-human-ai-gates.md` § Findings.

## OI-83 · Finding · `deploy.sh` replaces the services before it knows the new API is healthy, and does not roll back

**Claim.** `deploy/develop/bin/deploy.sh` stops the running services and starts the new ones,
then waits on `compose up --wait`. When the new API never becomes healthy, the deploy fails and
leaves the site without an API; it does not restore the previous SHA.

**Anchor.** `deploy/develop/bin/deploy.sh:91 @ 063a3cf`
(`up -d --remove-orphans --wait --wait-timeout 180`, with nothing after a failure that restores
the previous services); PR #122, Findings.

**Reproduction.** Deploy runs from run 54 (2026-10-02 18:18 UTC, `dfd8612`, PR #108) to the
merge of #122 (2026-10-05): each applied the migrations, then `aia-develop-api-1` never became
healthy, and the API stayed down.

**Consequence.** A configuration error that one container rejects becomes a site outage of
several days: every later merge's deploy failed the same way, and nothing reached the host.

**Smallest fix.** Roll back to the previous SHA when `up --wait` fails, and print the unhealthy
container's logs into the deploy output.

**Test that would catch it.** A deploy-script test with a stand-in API that never turns
healthy: the previous services are running again afterwards and the logs are printed.

**Status.** Open. Not fixed by #122, which fixed the cause of this outage only.

## OI-84 · Finding, closed · The API and the worker held two copies of the fictional-material rule

**Claim.** The API refused `AIA_AI_FICTIONAL_CLIENT_IDS` whenever `is_production`, which
included `staging`; the worker refused it only when `AIA_ENV` was exactly `production`. The
develop host ran as `staging` with fictional clients set, so the worker accepted the
configuration and the API refused it.

**Anchor.** `apps/api/src/aia_api/config.py:165-167, 233-237 @ 0c42547`;
`apps/executors/src/aia_executors/ai_runtime.py:195 @ 0c42547`;
`deploy/develop/docker-compose.yml:28 @ 0c42547` (`AIA_ENV: staging`).

**Reproduction.** `Settings(env=staging, ai_fictional_client_ids="C1", ...).validate_for_production()`
raises `AIA_AI_FICTIONAL_CLIENT_IDS is refused in production` at `056eca2`.

**Consequence.** Every develop deploy from 2026-10-02 18:18 UTC failed its health check, while
CI stayed green (OI-83 made it an outage).

**Fix.** #122 (`3d315e0`): `aia_core.domain.deployment` holds the one rule
(`fictional_material_problem`), both processes call it, and develop runs as `AIA_ENV=develop`.

**Test that catches it.** `apps/executors/tests/test_develop_host_configuration.py` runs both
startup checks against the real `deploy/develop/docker-compose.yml`; with the Compose file back
on `staging`, the API check fails with the error the host hit.

**Status.** Closed by #122.

## OI-85 · Finding · Deep Research grounding accepts a number whose population the claim changed

**Claim.** `ground` checks that a claim's numbers occur in its quote, not that the claim keeps
their unit, period, geography or population, so a claim restating a household share as a share
of adults is accepted.

**Anchor.** `packages/aia_core/src/aia_core/domain/deep_research/grounding.py:190-192 @ b2d43f7`.

**Reproduction.** `ground(source_ref="S1", quote="kupuje rostlinné nápoje 45 % domácností",
claim="Rostlinné nápoje kupuje 45 % všech dospělých lidí v Česku.", sources={"S1":
GroundableSource("S1", "Podle průzkumu kupuje rostlinné nápoje 45 % domácností v Česku.",
False)})` returns `Grounding(span=(15, 54), failure=None)` (2026-10-05).

**Consequence.** A brief can state a figure about households as one about adults; only the
verifier's `overstated` verdict stands in the way, and nothing requires it to notice.

**Fix.** Chunk 7 of [deep-research-web-search.md](plans/deep-research-web-search.md): attribute
checks against the quote's context and a `MEASURE_NOT_IN_SOURCE` quarantine.

**Test that would have caught it.** This reproduction as a grounding unit test (chunk 7's first).

**Status.** Closed by chunk 7 (#144, `e61540d`): the reproduction now returns
`failure=MEASURE_NOT_IN_SOURCE` ("the claim gives 45 the population 'dospělých' (ADULTS); the
quote's context in the source does not name it"), re-run 2026-10-06 on `579b7ab`; pinned by
`test_deep_research_measures.py::test_a_household_share_claimed_as_a_share_of_adults_is_quarantined`.

---

## OI-86 · Finding · A released planned Deep Research track sent its search and model request twice

**Claim.** A planned web track whose step was released between rounds (a deploy's `SIGTERM`, a
crash between calls) started again at its first query: the search was sent again, the round's
paid investigator request asked again, and the allowance, charged for both, cut the track short.

**Anchor.** `apps/executors/src/aia_executors/deep_research/investigate.py:419-440 @ f6199d0`:
`_web` looped over the plan's queries from the first on every attempt; the resumed meter counted
earlier dispatches but nothing recorded what they returned.

**Reproduction.** `apps/executors/tests/test_deep_research_planned_recovery.py`: release the
investigate step after a search, after one of a round's fetches, after a round's answer, or
(fanned out) in a track's own step; before the fix every case fails on its dispatch counts.

**Consequence.** With a live provider: a duplicate query and a duplicate paid model request after
every deploy during a planned investigation, and less coverage for the same money.

**Fix.** `_PlannedLog` stores every external outcome before the next call -- the search with its
hits in order, each fetch, the round, the answer before grounding -- and a resumed step replays
them; a journaled dispatch with no stored outcome ends the track `TOOL_OUTCOME_UNCERTAIN`
(`docs/architecture/deep-research-fan-out.md` § 8).

**Test that would have caught it.**
`test_deep_research_planned_recovery.py::test_a_released_planned_track_continues_and_sends_nothing_twice`
and `::test_a_dispatch_with_no_record_of_its_outcome_ends_the_track_and_sends_nothing_more`.

**Status.** Closed by #166 (`63693fa`, merged as `579b7ab`).

---

## OI-87 · Hypothesis · A model slot may be taken over while its holder is still calling

**Claim (unreproduced).** `ModelSlots` treats a slot as free when its holder attempt's lease has
passed (`infrastructure/fan_out_coordination.py`, "a slot expires with the lease of the attempt
that took it", `deep-research-fan-out.md` § 4 @ `579b7ab`). A worker that is alive and mid-request
but whose heartbeat fell behind its lease would lose its slot to another taker, so more requests
than the limit could be in flight for a moment.

**What would make it a finding.** A test that stalls one attempt's heartbeat past
`lease_until` while it holds a slot and a request is in flight, and shows a second attempt
acquiring that slot before the first request returns. Until then it is a hypothesis: reproduced or
deleted, never budgeted for (#166 recorded it as such).

**Status.** Open (hypothesis).

---

## OI-88 · Limitation, closed · Interpretation Research is frozen, never executed, until chunk 30

**Claim.** Interpretation execution is intentionally unavailable until chunk 30, because
target-derived research subjects and mission do not yet exist. ADR 0021's result-side freeze
resolves an interpretation target and pins its lineage exactly, but its engine request would still
be the one frozen from the producing run's Design Revision; a run would be labelled
`INTERPRETATION_RESEARCH` while researching the design's subjects. So the one enqueue boundary
(`application/deep_research.py` `DeepResearchRuns._enqueue`) refuses every
`INTERPRETATION_RESEARCH` spec (`InterpretationNotReady`, `interpretation_not_ready`), and a
stored interpretation row is never retried. No knowingly mislabelled output exists in AIA.

**Reproduction.** `apps/executors/tests/test_deep_research_lineage.py`:
`::test_the_enqueue_boundary_refuses_any_interpretation_spec`,
`::test_interpretation_execution_fails_closed_until_target_subjects_exist` and
`::test_an_interpretation_row_is_never_retried_until_chunk_30` (no new run, no model or
retrieval call). With the guard removed, these fail.

**Consequence.** No Interpretation Research runs yet; the freeze, the target and lineage
validation and the provenance contract are available to build on.

**Fix.** [web-search plan](plans/deep-research-web-search.md) chunk 30: derive the mission from
the exact target, build the engine request from it, then enable enqueueing and the result-side
route together.

**Status.** Closed by chunk 30 (PR #193, merged at `67af44e`). The mission is built by
`interpretation_mission` (`packages/aia_core/src/aia_core/domain/deep_research/interpretation.py:176
@ 67af44e`) from the pinned specification and the Design Revision only, and the enqueue boundary
checks it (`application/deep_research.py:560 @ 67af44e`, `require_interpretation_mission`).
Tests: `test_deep_research_lineage.py::test_interpretation_enqueues_its_mission_and_runs_to_a_sealed_bundle`,
`::test_a_design_derived_request_under_an_interpretation_label_is_refused`,
`::test_design_and_interpretation_share_the_engines_reusable_tracks`. The three tests named under
Reproduction were replaced by these when the guard was lifted.

---

## OI-89 · Finding, closed · A research agent run started before the hook's mount effect lost its review

**Claim.** `useResearchAgents`' mount effect reset `review`, `busy` and `notice`, so a click
landing between React's commit and its passive effects started a run whose review dialog the
effect then closed, leaving the decision promise pending and the job never settled.

**Anchor.** The reset moved into the effect's cleanup:
`apps/web/src/components/rehome/research/useResearchAgents.tsx:69 @ 67af44e` (fix `296c330`,
PR #184).

**Reproduction.** `QuestionnaireStep.test.tsx` › *reviews the native brief analysis…*, six
single-test runs in parallel on a 4-core container: 8 of 72 failed before the fix (each with the
mount effect logged after `askReview`), 0 of 90 after; 50 of 50 sequential runs pass.

**Consequence.** In the test, a 15 s wait for *Použít návrh* that ran out. Outside it, the same
order cleared a running job's busy flag and re-enabled its buttons.

**Fix.** Landed: clear the state in the cleanup, when the study is left; a first mount starts from
`useState`'s initial values. Recorded in `AGENTS.md` (*A mount effect must not reset state that
an event handler may already own*).

**Status.** Closed by PR #184 (`7a2673a`). The test that catches it is the one above, unchanged.

---

## OI-90 · Question · Declaring a context object moves the PRIMARY relations under F2

**Claim.** The integration plan's I2 acceptance line "adding context objects alone does not
change PRIMARY scores or terrain" cannot hold under the audit's F2, which rescales each person
over *every* item they rated, context objects included.

**Anchor.** `packages/aia_core/src/aia_core/domain/research_sociomap.py:270 @ 67af44e`
(`rating_universe`); `packages/aia_core/src/aia_core/domain/sociomap/relations.py:319 @ 67af44e`
(`person_minmax`); the audit's F2 (p. 22).

**Reproduction.** Add a sixth object to `DESIGN` in
`packages/aia_core/tests/test_sociomap_rating_universe.py` and declare it in `context_objects`:
the five PRIMARY objects' r~ move, because the new item moves people's bounds.

**Consequence.** Declaring a context object is not a free presentation choice: it changes the
relations the PRIMARY scores are read from.

**Fix.** Not engineering's: either F2's universe excludes SECONDARY items (a change to F2), or the
line reads "a context object's own pairs never enter a PRIMARY score", which holds and is tested.
For the audit's author, with group B of the plan's § 8a
([sociomap-formula-corrections](plans/sociomap-formula-corrections.md), slice S3, F-S3-1).

**Test.** The second reading: `test_sociomap_rating_universe.py::test_a_context_object_has_no_score_and_scores_nobody`.

---

## OI-91 · Limitation · A study's selected dimensions and audience filters are recorded, not applied

**Claim.** `persona_dimensions.approved` and `audience.filters` reach the run's specification as
`SpecSelection` with `applied: false`, but nothing selects the run's respondents by them, because
no dimension materialization or population binding exists in AIA.

**Anchor.** `packages/aia_core/src/aia_core/domain/research_design.py:159,166 @ 67af44e`
(`SELECTION_NOT_APPLIED`, `SpecSelection`).

**Reproduction.** `packages/aia_core/tests/test_research_selection.py::test_the_selection_says_it_was_not_applied`;
`::test_readiness_names_the_dimensions_it_will_not_apply`.

**Consequence.** Two designs differing only in a dimension or an age filter are two
specifications and two runs, but their respondents are drawn alike; readiness WARNs which
dimensions will not be applied, and the specification says so.

**Fix.** Dimension materialization and a population binding for the run (I1 of
[sociomap-formula-corrections](plans/sociomap-formula-corrections.md) § 8.1), never reconstructed
inside the Sociomap.

**Status.** Open; I1 stays open until it lands.

---

## OI-92 · Question · K100's percentile interval sits above its point near zero

**Claim.** Where an object's pairs are near zero, the audit's percentile bootstrap interval for
K100 lies above the full sample's K100, often excluding it, because K is a mean of |r| and a
resample's duplicated rows add noise that |.| folds upward.

**Anchor.** `packages/aia_core/src/aia_core/domain/sociomap/metrics.py:724 @ 67af44e`
(`connectedness_100`).

**Reproduction.** `packages/aia_core/tests/test_sociomap_connectedness_100.py::test_near_zero_the_percentile_interval_sits_above_its_point`
(200 respondents, 20 independent objects, B = 100: 10 of 20 intervals wholly above their point,
none below).

**Consequence.** A weakly connected object is shown with a margin that does not contain its own
score. Nothing reads K100 yet (chunk 5).

**Fix.** Not engineering's: a bias-corrected (BCa) or basic bootstrap interval, or a debiased K,
is a methodology change to F9. For the audit's author with group B
([sociomap-formula-corrections](plans/sociomap-formula-corrections.md), chunk 4a, F-4a-1).

**Test.** The reproduction above.

## OI-93 · Finding · The methodology editor shows the domain's refusals as English sentences

**Claim.** A specification check's problem is an English sentence, and the Metodika editor
shows it verbatim on a Czech page.

**Anchor.** `packages/aia_core/src/aia_core/domain/sociomap/specification.py:535 @ 8265af7`
(`n_min {n} is below 4: the Fisher interval needs four raters`).

**Reproduction.** `POST /api/v1/methodology/sociomap/check` with `relation.n_min` 2, or the
editor on the workbench (`make ui-workbench`, Nastavení → Metodika → Upravit metodiku).

**Consequence.** The methodologist reads why an edit is refused in English.

**Fix.** A problem code beside each message, Czech words for the codes in `cs.ts`, the English
as the fallback. Belongs with the specification validators' rewrite, chunk S2 of
[methodology-tab](plans/methodology-tab.md) (plan finding H4).

**Test.** One web test per code.

## OI-94 · Finding, closed · The reference set's K100 was copied from a map that reads Kish's n

**Claim.** With the F9 bootstrap on, `battery_sociomap` copied the body's K100 from any object
map with the same B, seed, n_min, confidence and roles. `aia-sociomap-3`, pinned in every new
run, matches all five but decides its pair statuses on Kish's effective n, the body on the
respondent count.

**Anchor.** `packages/aia_core/src/aia_core/domain/research_sociomap.py:438 @ e9d68b4` (the
guard before the fix).

**Reproduction.** `packages/aia_core/tests/test_research_sociomap_k100_copy.py`: 45 respondents
of case A01, one in three weighted 20 times the others.

**Consequence.** With `AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED` on, the stored body
recorded no K100 for any object where its own bootstrap gives, for example, kava 36.97
[.., 61.43]. No screen read it; the stored internal artifact was wrong.

**Fix.** #260 (`3583908`, merged to develop by #265): the copy also requires the map's
evidence basis to be the body's (`research_sociomap.py:511 @ 8265af7`). With the switch on, the
body pays for its own bootstrap again (about 90 s per large set). Plan finding H5.

**Test that catches it.** The reproduction above; it also asserts the map's K100 differs on
that panel, so it cannot pass vacuously.

**Status.** Closed by #260.

## OI-95 · Limitation · Four population companions are not in the 18.6.6 data bundle

**Claim.** The Czech contract requires 15 companions, and four of them are not in the unit's
licence-bound data bundle (`legacy/npc-panel-18.6.6/data-manifest.json`): `CORE_JOINT_STATUS.json`,
`PERSONA_VALUE_LABELS_v17.json`, `BUILTIN_SUBPANELS_v17.json` and
`SPECIAL_PANEL_REGISTRY_v17.json`. They are the frozen unit's own configuration, in Git under
`legacy/npc-panel-18.6.6/app/`.

**Anchor.** `deploy/develop/population/v17.files:22 @ 078da08` (origin `unit`), and the bundle
step of `.github/workflows/deploy-develop.yml @ 078da08` that copies them beside the list.

**Reproduction.** `apps/executors/tests/test_population_carry_over.py::test_every_unit_file_is_the_frozen_units_own_bytes`.

**Consequence.** A host gets its companions from two places: 15 files from the EU bucket and
these four from the deploy bundle. Anyone who uploads or describes "the data bundle" as the
whole population would miss them.

**Fix.** Nothing to fix while `extract_legacy.py` keeps them as configuration. If the
population ever gets a prefix of its own in the bucket, upload all 19 files there and make
every origin `bucket`.

**Test.** The reproduction above, and `test_the_list_is_exactly_the_contracts_versions_dictionary_and_companions`.

## OI-96 · Finding · The first population import ran as the AWS account's root user

**Claim.** P6b (2026-10-11) was run with a sign-in as the root user of the account that also
hosts other production systems, because no narrower identity existed for it.

**Anchor.** `.planning/plans/population-operations.md` § P6b @ 078da08; the runbook
`deploy/develop/README.md:423 @ 078da08` (step 1) names no identity.

**Reproduction.** Hypothesis only for anything beyond that run: nothing in the repository
creates or names an operator role.

**Consequence.** A later import, or a promotion, would again need credentials that can change
anything in the account, and the session that holds them can too.

**Fix.** An IAM role (or Identity Center permission set) limited to `ssm:SendCommand` and
`ssm:GetCommandInvocation` on the develop instance and `ssm:PutParameter` / `ssm:GetParameter`
under `/aia/develop/`, in `infra/develop`, named in the runbook's step 1.

**Test.** A Terraform plan test that the role's policy names only those actions and resources.

---

## OI-97 · Finding, closed · Opening the licence gate let a non-fictional persona cost money before failing

**Claim.** With the panel approved for the EU route and no guard, a non-fictional persona passed
preflight, every respondent's blocks were sent and paid for, and only then did `assemble_dataset`
refuse the dataset, ending the attempt `UNKNOWN`.

**Anchor.** The late refusal: `packages/aia_core/src/aia_core/domain/ai_respondent.py:682 @ 5d545eb`.
The guard: `apps/executors/src/aia_executors/ai_fieldwork.py` `AIFieldwork.produce` @ `a7616ef`.

**Reproduction.** Remove the guard and run `pytest apps/executors/tests/test_ai_fieldwork.py -k panel`:
it fails with `FailureClass.UNKNOWN` after calls reached the adapter.

**Consequence.** None in production: `fictional_roster` is the only persona source. A future source
built without the guard would have paid for a whole run's fieldwork and kept nothing.

**Fix.** Landed in PR #289: the fieldwork step fails `persona_source_unsupported` before anything is
reserved or sent. `plans/panel-grounded-respondents.md` chunk 5 replaces it with the panel source.

**Status.** Closed by PR #289 (`a7616ef`). The test that catches it:
`test_ai_fieldwork.py::test_panel_derived_personas_fail_before_any_call_while_no_panel_source_exists`.

---

## OI-98 · Finding, closed · 18.6.6's fallback quotas can give a full cell a seat, and the sample then fails

**Claim.** When capped cells pass their seats on, `_quota_vector_fallback` adds its tie-break noise to
every cell, full ones included, so a full cell can win a seat it has no row for, and the draw raises
"Buňka … nemá dost respondentů".

**Anchor.** `legacy/npc-panel-18.6.6/app/representative_sampling.py:124` (the noise), `:153` (the
refusal). AIA's rule: `packages/aia_core/src/aia_core/domain/population/sampling.py` `quotas` @ `a1fcc60`.

**Reproduction.** `pytest packages/aia_core/tests/test_population_sampling.py -k overfilled`: fixtures
D15 (663 of a 663-row audience) and D16 (640 of 663), both refused by the unit's own function.

**Consequence.** In 18.6.6, only where the MILP was unavailable: a sample near its audience's size
failed though it could be drawn.

**Fix.** A full cell takes no seat (PR #308); wherever the unit produced a sample the quotas are
identical.

**Status.** Closed by PR #308 (`a1fcc60`). The test that catches it:
`test_population_sampling.py::test_where_the_unit_overfilled_a_cell_aia_keeps_every_quota_within_its_rows`.

---

## OI-99 · Decision, open · Small samples are refused as unrepresentative on the stdlib quota path

**Claim.** AIA's sampler (18.6.6's fallback, chosen 2026-10-12 because the domain is stdlib only)
balances only the joint cells of `pohlavi x vek_skupina x kraj`; a sample holding none of an
education or employment category cannot be raked to its target, and the weighted deviation passes
`max(0.25, 100/n)`, so the sample is refused (`sampling_unrepresentative`, the unit's own rule).

**Anchor.** `legacy/npc-panel-18.6.6/app/representative_sampling.py:142-144,165-166`;
`packages/aia_core/src/aia_core/domain/population/sampling.py` `judge` @ `a1fcc60`. The unit's
`attempts=40` is never read (`representative_sampling.py:131-173`), though `pipeline.py:288-292`
says it draws repeatedly and keeps the best.

**Reproduction.** `representative_draw` + `judge` over the fixture's whole audience
(`tests/fixtures/representative_draw/`, 3,000 fictional rows, 60 joint cells), seeds 0-39:
n = 5-40 refused 40/40; 50 12/40; 60 9/40; 75 1/40; 100 2/40; 150 1/40; 200, 300, 500 0/40. The
unit's own fallback refuses n = 8, 20 and 30 in the fixture (D08, D03, D12).

**Consequence.** Once chunk 5 draws panel personas, a small study is refused before fieldwork, and
stays refused (the seed is fixed per run, `fieldwork_seed(spec)`) until its n or audience changes.
v17 has 14 regions, which raises the floor.

**Options (owner).** (a) accept it and state the minimum n where the study is set; (b) a stdlib
integer calibration of all five margins, parity then by property only; (c) the attempts the
unit's comment describes: redraw under derived seeds and keep the first that passes, recorded in
the sample.

**Status.** Open; needed before `plans/panel-grounded-respondents.md` chunk 5.
**2026-10-25 (the owner, OI-99 (c), the audit page, relayed by coordinator 3):** "redraw with new seeds and keep the first that
passes." The owner's note, verbatim: "lets create an individual artifact to explore and decide
this". **Still open:** the coordinator is building that artifact, and the decision is taken there.

---

## OI-100 · Finding · 18.6.6 sampled and styled only rows aged 18 or more; AIA's sampler takes every row

**Claim.** `Panel(df, min_vek=18)` drops rows whose `vek` is missing or under 18 before anything
else; `draw_panel_sample` has no such step.

**Anchor.** `legacy/npc-panel-18.6.6/app/pipeline.py:147-152`;
`packages/aia_core/src/aia_core/domain/population/sampling.py` `draw_panel_sample` @ `a1fcc60`.

**Reproduction.** Hypothesis for v17: no row is affected (its core donors are PIAAC 18-65 and
ISSP 66+, `CORE_JOINT_STATUS.json` `core_sources`); not verified, no panel rows in the repository.
The guard's own tests: `test_panel_persona.py::test_a_persona_that_cannot_be_built_as_18_6_6_built_it_is_refused[minor]`,
`[no_age]`.

**Consequence.** If wrong, AIA could sample a row 18.6.6 never could, and a column's type (hence a
filter's keys) could differ from the unit's.

**Fix taken.** `panel_personas` refuses a population with any such row
(`persona_age_out_of_scope`, `domain/panel_persona.py` @ `09c93f0`, PR #315), so a run fails closed
before fieldwork.

**Status.** Open until the first panel run on develop reports the count on `v17_4_0`. Chunk 5
(PR #332) composes the refusal into fieldwork: a panel run on such a population fails
`persona_age_out_of_scope` before any call.

---

## OI-101 · Finding, closed · 18.6.6 ranked an empty-priority persona signal by Python version

**Claim.** An empty `priority` in the persona signal catalog reads NaN, and the unit sorts the
candidate signals on `(-score, column)`, so a NaN score lands wherever the sort leaves it: the
unit's own persona text for such a row differs between Python versions.

**Anchor.** `legacy/npc-panel-18.6.6/app/persona_grounded.py:290`; AIA's rule
`packages/aia_core/src/aia_core/domain/persona_signals.py` `grounded_text` @ `341ea3b`.

**Reproduction.** PR #315's first CI run (38250340111):
`test_persona_profile.py::test_the_grounded_signals_are_the_units[3]` failed on CI's Python with a
fixture captured on 3.13; `test_a_signal_with_an_unknown_priority_ranks_last` pins AIA's rule.

**Consequence.** None known in production: whether v17's catalog has an empty priority is not
checked here. A persona's signal order, and so its text, would depend on the interpreter.

**Fix.** AIA ranks a NaN score last (unknown is never ranked as good); every other order stays
EXACT.

**Status.** Closed by PR #315 (`341ea3b`).

---

## OI-102 · Hypothesis · A superseded Sociomap method can still be put in force as an edited version

**Claim.** `aia-sociomap-2` remains a registered base preset, so an administrator can store and
activate `aia-sociomap-2+e<n>`, and new runs would then pin a method that no unedited new run pins
any more (new runs pin `aia-sociomap-1` + `-3`, `research_sociomap.py` `default_methods`).

**Anchor.** `packages/aia_core/src/aia_core/domain/methodology/sociomap.py:623`,
`apps/web/src/components/aia/settings/MethodologyVersions.tsx:319-323`,
`apps/api/src/aia_api/routers/methodology.py:620, 665, 708`,
`packages/aia_core/src/aia_core/domain/methodology/pins.py:60-71` @ `cd6da1e1`
(`mvp-workflow-assurance.md` F3, #307).

**Reproduction.** Not yet run: a `POST …/methodology/…/versions` with `base_preset =
"aia-sociomap-2"`, its activation, then a run start, and read the run's pinned methods. Until it
runs, this is a hypothesis.

**Consequence.** A new run could compute a method the in-force default (-3) replaced, without
anyone choosing -2 for new work on purpose.

**Smallest fix.** If the owner confirms -2 is historical only, refuse it as a base for a new
version while keeping it readable for stored runs and versions.

**Test.** An API test that the version POST refuses a superseded base, and that a stored -2 run
still reads and retries.

**Status.** Open; reproduce or delete.

---

## OI-103 · Finding · A client-facing number can print "měřeno" beside "modelováno: AI respondenti z populace"

**Claim.** The print grade follows the claim's basis and the composer's `field_grades`, never
the row's origin, and since ADR 0024 §2 the only client-admissible origin is
`MODELLED_AI_PANEL`; so a measured-basis claim on a population field graded `MEASURED` prints the
measured mark beside the modelled disclosure.

**Anchor.** `packages/aia_core/src/aia_core/domain/report/evidence.py:58-65` (`grade_of`) @
`5f204ce1`; the disclosure, `report_docx/tables.py` caption @ `88fbacef` (PR #329).

**Reproduction.** `pytest packages/aia_core/tests/test_report_docx_tables.py -k caption_numbers`:
the caption reads "n = 480; měřeno; modelováno: AI respondenti z populace".

**Consequence.** Once a client report exists, a reader sees two contradictory words on one
number. No production composer passes `field_grades` today (OI-9), so no report prints it yet.

**Smallest fix.** With OI-9: a `MODELLED_AI_PANEL` row grades `MODELLED` whatever its basis, or
such a row cannot back a measured claim at admission.

**Test.** A ledger test asserting a modelled-panel row never grades `MEASURED`.

**Status.** Open; decided 2026-10-26: fix it, the print grade follows the row's origin (the product
owner, ADR 0024 Q6 (a), Decision Review, relayed by the PM coordinator). Owner: `report-delivery` RD13 (W2).

## OI-104 · Finding, closed · A panel start with no population asked to confirm its cost first

**Claim.** `ResearchRuns.start` applied the spend-confirmation gate before the panel
persona source's population check, so a panel start with no LIVE population, in a study
whose limit the run reaches, raised `CostConfirmationRequired` (or `CostCeilingUnknown`)
instead of `PanelPopulationMissing`.

**Anchor.** `packages/aia_core/src/aia_core/application/research.py:373-393 @ abd3ce88`
(the cost gate, then `_population_for`).

**Reproduction.**
`test_research_runs.py::test_a_panel_start_with_no_population_is_refused_as_that_before_any_cost_is_asked`
fails on the old order with `CostConfirmationRequired`.

**Consequence.** A person is asked to confirm the cost of a run that can never start; a yes
only leads to the refusal.

**Smallest fix / status.** Resolve and check the population before the cost gate. Found by
Codex on #332 after it merged; fixed in #345 (panel-grounded-respondents).


## OI-105 · Finding, closed · A panel run over a selected child could not read the child

**Claim.** The worker's panel loader read only the shared population's directory, so a panel
run over a client's materialized child (selected at start since #343) could not load the
child, which lives in the population store.

**Anchor.** `apps/executors/src/aia_executors/ai_runtime.py:529 @ a7ef6acc` (the panel loader
over `FilesystemPopulationSource` alone) and `apps/executors/src/aia_executors/registry.py:163
@ a7ef6acc` (no store handed to it).

**Reproduction.**
`apps/executors/tests/test_ai_fieldwork.py::test_without_the_store_a_panel_run_over_a_child_parks_and_sends_nothing`:
the fieldwork step waits `RUNTIME_UNAVAILABLE`, with no request and no ledger row.

**Consequence.** Selecting a child for a panel run did nothing: the run parked at fieldwork.
Nothing was sent, drawn or substituted.

**Smallest fix / status.** Give the panel loader the population store as the materialize step
has it (`ai_runtime.panel_population_source`, one store built in `registry.population_store`).
Found in #343 (population-operations P4e2) as a hypothesis, reproduced and fixed in #351;
`test_a_panel_run_over_the_clients_child_reads_it_from_the_population_store` covers it.


## OI-106 · Finding, closed · The UX journey had drifted from develop twice

**Claim.** `tools/ui_workbench/ux_journey.mjs` failed on develop for two reasons unrelated to
any change under test: it clicked the 3D camera's "Otočit vpravo", which had moved into a closed
disclosure, and it counted `GET …/design/source`'s 404 (which means "not reused") as an error.

**Anchor.** `apps/web/src/components/rehome/research/ObjectMapView.tsx:302` (the disclosure, since
`1eb36ab`) and `DesignSourceNote` (since `213d491`), against the journey's last update `19d1179`;
develop @ `b05b698`.

**Reproduction.** `node tools/ui_workbench/ux_journey.mjs` on develop @ `b05b698` with the
workbench up: a timeout on the hidden button, then an error for the expected 404.

**Consequence.** The research UX regression check could not pass, so it proved nothing.

**Smallest fix / status.** Open the disclosure, name the expected 404 and judge a logged 404 by
its request. Fixed in #382 (research-lane-redesign, F1).

**Also reported as** client-workspace F-CW1 (#380, `.planning/plans/client-workspace.md`
§ Findings): the same timeout at the rotate button, seen on that branch after merging develop
`04c8830`, before #382 landed. One cause, one fix; no separate item.

## OI-107 · Finding, closed · A report could never be approved

**Claim.** `ArtifactRepository.approve` had no caller for reports, so every report's
`review_state` stayed `DRAFT_UNAPPROVED`.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/artifact_repository.py:523` @
`b05b698`.

**Reproduction.** `grep -rn "\.approve(" apps/api/src packages/aia_core/src/aia_core/application`
@ `b05b698` finds no report route.

**Consequence.** "Koncept čeká na schválení" could never change.

**Smallest fix / status.** `approve_report` and `POST …/report/approve`, through the one approve
method. Fixed in #385 (complete-study-report B2);
`test_research_api.py::test_a_person_approves_a_runs_stored_report_once_and_only_that`.
The buttons for every stored report (internal, client, with literature) are on Výsledky's report
card since #393, each approving the document its download named (`X-AIA-Artifact-Id`);
`ExecutionSteps.test.tsx` "Internal report" and "Interpretation research".

## OI-108 · Finding, closed · OI-61's status line said Open under a "closed" heading

**Claim.** OI-61's heading reads "Decision, closed" while its Status line read "Open; blocks live
AI fieldwork".

**Anchor.** `.planning/open-items.md:2080` and `:2108` @ `b05b698`.

**Consequence.** A reader of the item could believe live panel fieldwork was still blocked.

**Smallest fix / status.** Correct the Status line from `licence_determinations.py`. Fixed in this
docs PR (research-lane-redesign F3).

## OI-109 · Hypothesis · Fictional data prints the grade "modelováno"

**Claim.** Every native evidence row has basis MODELED and `grade_of` prints MODELED as
"modelováno", so a table of a fictional (SYNTHETIC_FIXTURE) run reads "(n = 56; modelováno)".

**Anchor.** `packages/aia_core/src/aia_core/domain/analysis/native.py` (`_Rows.add`,
`basis=ClaimBasis.MODELED`) and `packages/aia_core/src/aia_core/domain/report/evidence.py:59`
(`grade_of`) @ `04c8830`.

**Reproduction.** Render the DOCX of
`test_analysis_results.py::test_every_question_prints_its_numbers_through_admission_after_the_methodology`
and read a table caption.

**Consequence.** On an internal draft of fictional data the caption says modelled while the
report's frame says fictional; the frame is right. The client report is unaffected (a fictional
run has none).

**Smallest fix.** A print grade for a non-evidence origin (SIMULATED), chosen by `origin_kind`
beside the basis.

**Test.** A caption assertion on a SYNTHETIC_FIXTURE table.

**Status.** Open; analysis-governance's call, with OI-9 and OI-103 (complete-study-report F1).

## OI-110 · Finding, closed · A client source kept before its format had a reader is never read again

**Claim.** A source is read once, when it is first kept; the same bytes added again only add an
occurrence, so a file stored as `UNSUPPORTED` / `reader_pending` stays unread after its format
gains a reader.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/client_source_repository.py:200-203`
@ `afc2056` (`add` reuses the row found by (client, sha256) and calls `_keep` only when there is
none) and `:260` @ `afc2056` (`_keep` is the only place `read_source` runs).

**Reproduction.** Keep a `.xlsx` (read as `reader_pending` until K2c), land the dataset reader,
add the same file again: `GET /clients/{id}/sources/{source_id}` still answers `UNSUPPORTED`.

**Consequence.** Material a client added early never yields text or proposals, and the page says
"reader pending" for a format AIA reads.

**Smallest fix.** A re-read of a source whose stored reader is absent or older than the current
one: read the kept original again, store the new reading beside the old (the reader is in its key),
move the row's outcome; never change the original.

**Test.** A source kept as `reader_pending`, then re-read after the reader is registered: `READ`,
the first reading still in storage.

**Status.** Fixed in #398 (client-knowledge-lifecycle K2c): `ClientSourceRepository.reread` and
`POST /clients/{id}/sources/{source_id}/reading` read a source again when its format's current
reader is not the one that read it, as does adding the same bytes again; the original never
changes and the first reading stays beside the new one (`CLIENT_SOURCE_REREAD`). Test:
`test_source_datasets.py::test_a_source_kept_before_its_reader_is_read_again_and_its_first_reading_kept`.

## OI-111 · Finding, closed · Approving an older knowledge edit replaced a newer correction

**Claim.** An approval did not check whether the item had changed after the proposal was made, so
approving an edit written from an older revision silently replaced a newer correction.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/client_knowledge_repository.py:250-296,
353-387, 516-527` @ `67af44e`; `ProposalCreate` and `DecisionRequest` in
`apps/api/src/aia_api/routers/workspace.py:385-405` @ `67af44e` carried no reviewed base revision
(client-knowledge-lifecycle F-K1).

**Reproduction.** A FACT at revision 1; a study proposes an edit of it; a person corrects it to
revision 2; approving the study's edit succeeded as revision 3 with the older text current.

**Consequence.** A validly authorized acceptance could undo a newer correction; only the revision
history still held it.

**Smallest fix.** Record the base revision on a revising proposal and compare it under the item lock
before applying; refuse a stale one by name.

**Test.** `test_client_knowledge.py::test_an_edit_written_before_a_newer_correction_is_refused_and_changes_nothing`.

**Status.** Fixed in #401 (client-knowledge-lifecycle K3a): `client_knowledge_proposals.base_revision`
(migration `d4f6a8c0e2b5`); `_require_current_base` in `client_knowledge_repository.py` @ `60150f61`
raises `StaleKnowledgeProposal` (409 `knowledge_proposal_stale`, both revisions named) unless the
reviewer names the current revision as `reviewed_revision`, which the new revision's provenance
records. A pending edit filed before the column has an unknown base and is treated as stale. The
API test is `test_client_api.py::test_an_edit_written_from_an_older_revision_is_a_409_until_the_reviewer_names_the_current`.
Widened by #542 (merged as `8a71b83`, 2026-10-21, lifecycle K3): `domain/knowledge.py`
`reviewed_decision` refuses a reviewer's named revision that is not the current one whatever the
edit's base, and the decision is stored as AUTHORED, ACCEPTED, ACCEPTED_OVER or REJECTED with the
`reviewed_revision` named (migration `a3c5e7f9b1d4`); naming a revision for a new item is 422
`no_revision_to_review`.

## OI-112 · Finding, closed · A retry's run froze on Průběh

**Claim.** After an action, Průběh showed the run the API answered (a retry's new run) without
reading it again, so the poll, stopped when the old run finished, never restarted, and `?run=` still
named the old run.

**Anchor.** `apps/web/src/components/rehome/research/ExecutionSteps.tsx:621` @ `1879783` (a poll is
scheduled only inside `read`) and `:638` (`useRun` handed out the bare `setRun`).

**Reproduction.** `ExecutionSteps.test.tsx` "follows the run a retry starts and keeps reading it, so
its steps move on screen" fails on `1879783`: `?run=RUN-1`, the step stays RUNNING.

**Consequence.** Reported by the product owner 2026-10-14: "Znovu spustit" left the new run's first
step on "Běží" while the worker went on; a reload went back to the old run, and a second click looked
like a resume. It was the same run: a retry's idempotency key carries the run it retries
(`packages/aia_core/src/aia_core/application/research.py:464` @ `1879783`), so nothing was started or
paid twice.

**Smallest fix.** `useRun`'s setter follows the run it is given: `?run=` rewritten, read again at
once, the poll restarted; every action goes through it.

**Test.** The reproduction above.

**Status.** Fixed in #423 (progress-follows-retry F1).

## OI-113 · Finding, closed · The report card's tests clicked an option before it was offered

**Claim.** "offers the client report only for modelled data…" and the PDF test clicked a radio that
is disabled until the report's status is read.

**Anchor.** `apps/web/src/components/rehome/research/ExecutionSteps.test.tsx` @ `1879783`, both tests.

**Reproduction.** The client-report test alone: 1 failure in 3 runs.

**Consequence.** A red web suite unrelated to the change under test (also seen in #417).

**Smallest fix.** Wait until the option is offered (`offered`) before clicking it.

**Test.** Both tests, now waiting.

**Status.** Fixed in #423 (progress-follows-retry F2); develop carried the same wait independently.

---

## OI-114 · Finding · Orphaned artifact objects are never reaped

**Claim.** `ArtifactRepository.put` uploads the object before it adds the row, so a transaction
that rolls back after the upload leaves an object in the store that no row references; the
docstrings and `docs/architecture/artifacts.md` said a reaper removes these, and none exists.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/artifact_repository.py:347` (upload),
`:386` (row), `:312` and `:600` (the "reaped later" docstrings) @ `80dc2167`; no function in
`packages/` or `apps/` sweeps unreferenced objects (#443).

**Reproduction.** `DATABASE_URL=postgresql+psycopg://… AIA_REQUIRE_POSTGRES=1 pytest
apps/worker/tests/test_stale_lease_artifacts.py -k orphans_its_object`: an executor block that
raises after its upload rolls the row back, and after the step's successor completes, the store
still holds two objects against one row.

**Consequence.** Storage grows by one object for every executor block that fails after its upload;
nothing a person sees is wrong, and nothing reclaims the space or the data those objects hold.

**Related, latent: `delete` is not transactional with its object.** It flushes the row's deletion and
deletes the object at once, before the caller commits (`artifact_repository.py:610-612 @ 223621d5`).
A successful delete leaves no orphan; a delete whose transaction rolls back afterwards restores a
row pointing at a deleted object, the hazard the upload order exists to avoid. No product code calls
`delete` (only `test_artifact_repository.py`), so nothing reaches it today. Smallest fix, when a
caller arrives: delete the object after the commit (an after-commit hook), and a test that rolls
back a delete and reads the artifact. Hypothesis until that test exists (CLAUDE.md §9).

**Smallest fix.** A periodic sweep that deletes store keys under the artifact prefix that no
`project_artifacts.storage_key` names and that are older than a grace period longer than any
transaction; or a decision that orphans are kept, with the docstrings at `:312` and `:600` saying
so (they still claim a reaper).

**Test.** The reproduction above, turned to assert the orphan is gone after a sweep past its grace
period, and kept before it.

**Status.** Open. The docs now say no reaper exists; the docstrings change with the code that
settles this.

---

## OI-115 · Finding, closed · The client's budget said nothing was held while client holds existed

**Claim.** `ScopeRepository.client_budget` built the position from budget and spend alone, so
`reserved_usd` was 0 whatever the client's own work held.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/scope_repository.py:462-470 @ 80dc2167`
(plan `client-budget.md` F-CB3).

**Reproduction.** `test_client_paid_holds.py::test_a_client_hold_is_checked_against_and_charged_to_the_client_alone`:
with $6 of $10 held, the budget said $10 available where a reservation would allow $4.

**Consequence.** A person deciding a lift saw more room than the client had.

**Smallest fix.** `reserved_usd` is the sum of the client's open holds that name no study.

**Test.** The reproduction above.

**Status.** Fixed in #445 (Codex review of #438).

---

## OI-116 · Finding, closed · Two concurrent lifts could lower the client's budget

**Claim.** `lift_client_budget_wait` compared the offer with an unlocked read and only then locked
to write, so a lift decided on the old budget could overwrite a larger one made meanwhile.

**Anchor.** `packages/aia_core/src/aia_core/application/client_work.py:113-118 @ 80dc2167`
(plan `client-budget.md` F-CB4).

**Reproduction.** `test_client_budget_lift.py::test_a_lift_decided_on_a_stale_budget_never_lowers_one_raised_meanwhile`
(PostgreSQL, two threads): $8 without the lock, $10 with it.

**Consequence.** A raised client budget could silently fall back.

**Smallest fix.** Read the budget under the client row's lock before comparing
(`client_budget(for_update=True)`); a later lock order fix takes the run's lock first.

**Test.** The reproduction above.

**Status.** Fixed in #445.

---

## OI-117 · Finding, closed · Two first requests could each create the client's work project

**Claim.** `client_work_project` read, then inserted, with no constraint.

**Anchor.** `packages/aia_core/src/aia_core/application/client_work.py:37-50 @ 80dc2167`
(plan `client-budget.md` F-CB5).

**Reproduction.** `test_client_work_start.py::test_a_client_has_one_work_project_even_when_two_first_requests_race`.

**Consequence.** A client's own runs could split across two projects.

**Smallest fix.** Partial unique index `uq_projects_client_work` (migration `b3d5f7a9c1e4`); the
losing insert rolls back to its savepoint and answers with the project the other made.

**Test.** The reproduction above.

**Status.** Fixed in #445.

---

## OI-118 · Finding, closed · Two green PRs merged into a worker that crashed every client-work attempt

**Claim.** #432 tagged each attempt with `claim.scope.study_id`; #438 introduced the client's own
work, whose `ClientWorkContext` has no study. Each PR was green alone; together the worker raised
`AttributeError` before any client-work executor ran.

**Anchor.** `apps/worker/src/aia_worker/worker.py:341 @ 80dc2167`.

**Reproduction.** The three client-work tests in `apps/worker/tests/test_worker_loop.py` at
`80dc2167`.

**Consequence.** None user-visible: no route started client work until #446.

**Smallest fix.** Tag the payer's study (none for client work) and the client.

**Test.** The worker-loop tests above.

**Status.** Fixed in #440 (#445 carried an equivalent fix and kept #440's line on merge).

---

## OI-119 · Finding, closed · A document's AI requests were bounded neither in number nor in size

**Claim.** K2d1 packed batches by characters, so the stated cap of 21 requests per document did not
hold and a request of short lines could exceed the model's window.

**Anchor.** `batches` in `packages/aia_core/src/aia_core/domain/source_proposals.py @ 4b15e6f6`
(plan `client-knowledge-lifecycle.md` F-K4).

**Reproduction.** 41 pages of 6,001 characters made 41 requests; 12,000 one-character lines made
one request of 338,949 bytes.

**Consequence.** A document's burst and cost were not what the plan said.

**Smallest fix.** Batches bounded by bytes (`BATCH_MAX_BYTES`), `MAX_REQUESTS` refused before any
call, the hold sized to the request's window.

**Test.** `test_a_batch_is_bounded_by_the_bytes_it_sends_whatever_the_text`,
`test_a_document_needing_more_than_the_request_cap_is_refused_before_anything_is_sent`.

**Status.** Fixed in #446 (K2d6).

---

## OI-120 · Finding, closed · A document stopped between batches paid for its answered batches again

**Claim.** A document's answers lived only in the attempt's memory, so a step parked at the
client's budget or released by its worker restarted at batch 0.

**Anchor.** The batch loop in `apps/executors/src/aia_executors/client_source_proposals.py @ 43e20119`
(plan `client-knowledge-lifecycle.md` F-K5).

**Reproduction.** `test_a_document_parked_between_batches_resumes_without_paying_twice`: 3
requests without the journal, 2 with it.

**Consequence.** Every lifted or released multi-batch document billed its first batches twice.

**Smallest fix.** `client_work_journal` (migration `c5e7a9b1d3f6`) keeps each answer under the
lease the moment it returns; a resumed step replays it.

**Test.** The reproduction above; `test_client_work_journal.py`.

**Status.** Fixed in #446 (Codex review).

---

## OI-121 · Finding, closed · A document's proposals run stopped for recovery could never be asked again

**Claim.** With one attempt, a retryable failure whose outcome is known ends in
`RECOVERY_REQUIRED`, and asking again counted only failed and cancelled runs as ended.

**Anchor.** `_ENDED_WITHOUT_RESULT` in `packages/aia_core/src/aia_core/application/source_proposals.py @ 43e20119`
(plan `client-knowledge-lifecycle.md` F-K6).

**Reproduction.** `test_a_run_stopped_for_recovery_restarts_only_when_no_paid_call_is_uncertain`.

**Consequence.** Such a document's proposals were stuck for good.

**Smallest fix.** A run is `restartable` when it failed, was cancelled, or stopped for recovery with
every paid call's outcome known; one with an uncertain paid call is never restarted from there.

**Test.** The reproduction above.

**Status.** Fixed in #446 (Codex review).

---

## OI-122 · Hypothesis · A web report-card test failed once under the full suite

**Claim.** `ExecutionSteps.test.tsx` › "offers the report's PDF when the run stored one, and says
why when it could not" failed once in a full `npx vitest run` (1 of 1,511, 2026-10-15).

**Anchor.** `apps/web/src/components/rehome/research/ExecutionSteps.test.tsx` @ `43e20119`
(plan `client-knowledge-lifecycle.md` F-K3).

**Reproduction.** None: it passed alone twice and in the next full run.

**Consequence.** A red web suite unrelated to the change under test, if it recurs.

**Smallest fix.** Unknown until reproduced; OI-113 was the same family (a click before the option
was offered).

**Test.** Run the full suite repeatedly; if it recurs, capture the assertion and its timing.

**Status.** Hypothesis: reproduce or delete (CLAUDE.md §9).

---

## OI-123 · Finding, closed · Develop's SQLite step ran no test while every pull request was green

**Claim.** Two test modules shared the basename `test_error_reporting.py` in `apps/api/tests`
and `apps/worker/tests`, which are not packages, so the one pytest session over all four test
trees (the `Domain tests on SQLite` step) failed collection with "import file mismatch" and ran
nothing. Every per-tree step passed, and the SQLite step runs only on a push to `develop`, so no
pull request showed it.

**Anchor.** `apps/worker/tests/test_error_reporting.py` and `apps/api/tests/test_error_reporting.py`
@ `3f7fc500`; `.github/workflows/ci.yml` `Domain tests on SQLite`
(`if: github.event_name != 'pull_request'`) @ `80dc2167`.

**Reproduction.** At `223621d5` (before #449): `DATABASE_URL= pytest packages/aia_core apps/api apps/worker
apps/executors -q --collect-only` gives 8,277 collected, 1 error, "Interrupted: 1 error during
collection". Develop run 38746704500 at `1d7dbc05` shows the same in CI.

**Consequence.** From #432 until #449, develop's SQLite step tested nothing and blocked the develop
deploy dispatch. The offline SQLite path was unverified for that whole time.

**Smallest fix.** Unique basenames across the four trees (#449 renamed both to
`test_api_error_reporting.py` and `test_worker_error_reporting.py`).

**Test.** CI's `Every test tree collects in one session` step, the same collect-only command on
every pull request (#451).

**Status.** Fixed in #449; guarded by #451.

---

## OI-124 · Finding, closed · GlitchTip never turned healthy on develop

**Claim.** The GlitchTip image's health check asks `http://localhost:8000/_health/`, and
`ALLOWED_HOSTS` named only `errors.<hostname>` and `glitchtip`, so Django answered 400: the service
ran and served traffic but its container never turned healthy.

**Anchor.** `deploy/develop/errors/docker-compose.yml` `ALLOWED_HOSTS` @ `f5383923`; the image's
`/code/healthcheck.py` at GlitchTip v6.2.6.

**Reproduction.** `bin/errors.sh up` on develop (2026-10-16): "application not healthy after 5m0s"
while `docker compose -p aia-errors logs glitchtip` shows granian listening on :8000.

**Consequence.** `bin/errors.sh up` timed out, and every deploy with `aia_errors_enabled` would warn
that GlitchTip did not start; error tracking itself worked.

**Smallest fix.** Add `localhost` to `ALLOWED_HOSTS` (#469).

**Test.** None automatic: CI validates the Compose file but does not run the image.

**Status.** Fixed in #469.

---

## OI-125 · Hypothesis · An API 500's error body may lose its request id

**Claim.** `RequestContextMiddleware` resets `request_id_var` in its `finally` before Starlette's
`ServerErrorMiddleware` runs the `Exception` handler, so `_error` may read an empty id and a 500's
body carry `"request_id": null`.

**Anchor.** `apps/api/src/aia_api/observability.py` `RequestContextMiddleware.dispatch` and
`install_exception_handlers._unhandled` @ `f5383923`.

**Reproduction.** Not yet: a test that raises in a route and asserts the 500 body's `request_id`
equals the sent `X-Request-ID` would decide it.

**Consequence.** A person quoting "the request id" from a 500 has none to quote; the error report is
unaffected (it is tagged when the request starts, `apps/api/tests/test_api_error_reporting.py`).

**Smallest fix.** Read the id before the reset (keep it on `request.state`) and use that in `_error`.

**Status.** Hypothesis: reproduce or delete (CLAUDE.md §9).

---

## OI-126 · Question, answered · How is Research Lead chat material classified on develop?

**Claim.** Every Research Lead turn on develop parks before any call with
`egress_unclassified_material`: a turn's class follows the design agents' rule, which classifies
the design, the study's and client's names, every message, the focus label and any changed SOUL,
USER or note by their exact bytes only, and a chat message is new bytes every time.

**Anchor.** `packages/aia_core/src/aia_core/domain/research_lead.py:858` `lead_request` @
`c7327072` (its `data_classification` at `:897`, from `context_data_class`, `:816-855`);
`deploy/develop/env.example:78-83 @ c7327072` (client ids do not classify material;
`AIA_AI_MATERIAL_CLASSIFICATIONS=[]`).

**Reproduction.** `apps/executors/tests/test_research_lead_executor.py::test_unclassified_material_parks_the_turn_before_any_call`;
on develop, any message in the Lead pane, which says why in Czech
(`apps/web/src/components/workbench/LeadPane.tsx:39 @ c7327072`).

**Consequence.** The Lead (#484, ADR 0026) is switched on for develop but answers nothing there;
its cost per turn (plan `research-lead-workbench` chunk 10) cannot be measured until this is
decided.

**Options.** (a) A researcher's per-message declaration, recorded with the turn, as a prompt
author declares a saved prompt Class C (`domain/prompts.py:49-51`, `:127 @ c7327072`). (b) Lead
material is Class A, sent only on a route approved for Class A. Either way, unknown stays a
refusal.

**Status.** Answered by the product owner, 2026-10-19 (ADR 0008, Amendment 2026-10-19; #487):
neither option. A chat message and focus label take the study's class, B; the design and the
study's and client's names are B; the Lead's name, SOUL, USER and personal notes C; its
client-scoped notes A -- each by rule, an operator's exact-bytes classification only raising it
(`packages/aia_core/src/aia_core/domain/material_rules.py:79-91` `RULE_CLASSES` @ `64cc1380`;
`domain/research_lead.py:835` `context_classification` @ `64cc1380`; test
`packages/aia_core/tests/test_research_lead.py::test_the_design_names_and_a_message_are_class_b_by_rule_with_no_operator_step`).
Material no rule names still refuses. The Lead answers on develop once an operator approves the
route for Class B with its retention stated (ADR 0010, Amendment 2026-10-19;
`deploy/develop/README.md` § AI route classes); until then a route approved for Class C alone
refuses a turn for its class, no longer for unclassified material (ADR 0008's amendment: a rule
approves no route). Closed.

---

## OI-127 · Question · A person's own design job is not held to the study's spend limit

**Claim.** `ResearchAgentJobs.start` holds a reservation but never reads the study's
`spend_confirm_usd`, so a design job a person starts from a stage's AI help never asks for the
confirmation a research run's start, or a Lead-prepared job's approval, asks for.

**Anchor.** `packages/aia_core/src/aia_core/application/research.py:1311-1408 @ c7327072`
(`ResearchAgentJobs.start`; called by `POST …/research/agent-jobs`,
`apps/api/src/aia_api/routers/research.py:2735-2754`). Beside it the limit is applied by
`ResearchRuns.start` (`research.py:725-741`) and by the Lead's `approve_request`
(`application/research_lead.py:675-684`;
`apps/api/tests/test_research_lead_api.py::test_a_prepared_job_is_approved_under_the_spend_limit_once`).

**Reproduction.** Set a study's spend limit below `AIA_AI_RESEARCH_RESERVATION_USD`, then start
any design job from a stage: no confirmation is asked (plan `research-lead-workbench.md` F1).

**Consequence.** A study's spend limit stops a run and a Lead-prepared job but not a job a person
starts directly.

**Smallest fix.** If the owner wants the limit there too: the same reservation check as
`approve_request`, 409 `cost_confirmation_required` before the job is queued, the yes recorded.

**Test.** A start under a limit below the reservation is refused without `confirm_cost_usd`.

**Status.** Open: whether a person's own button is held to the limit is the product owner's call
(ADR 0026 decision 7 applies it to Lead-prepared jobs only). Still true at `c7327072`.

---

## OI-128 · Finding, closed · Accepting an AI proposal could overwrite an edit made in another tab

**Claim.** The browser's guard compared only its own store and the server compared only Design
Revisions, so a proposal made from one working copy was applied over a newer one that had changed
the very items the proposal changes (or was refused whole for an unrelated change).

**Anchor.** `apps/web/src/components/rehome/research/useResearchAgents.tsx:85` and
`packages/aia_core/src/aia_core/infrastructure/study_design_repository.py:180-183` @ `50547cdc`
(plan `research-lead-workbench.md` F2).

**Reproduction.** Accept a proposal after a second session saved the working copy with a change
to an item the proposal changes.

**Consequence.** A person's edit silently lost on accept.

**Smallest fix.** The accept on the server, in one transaction, checked item by item against the
working revision the proposal's design names (`application/proposal_accept.py:92-157 @ c7327072`).

**Test.** `apps/executors/tests/test_research_agent_executor.py::test_a_job_started_after_an_edit_is_checked_against_its_designs_working_revision`.

**Status.** Fixed by 5dff12a5 (#485).

---

## OI-129 · Decision · Deep Research keeps an operator's exact-bytes classification of a design

**Claim.** Deep Research's plan step classifies a run's design by the operator's exact-bytes
record alone and gives every web query that class; its web routes carry Class C only. Taking the
owner's design rule (Class B, never lowered by an operator) there would refuse every web track of
every run, the synthetic fixtures an operator classified Class C included.

**Anchor.** `apps/executors/src/aia_executors/deep_research/plan.py:163` (`classify_material`,
the operator's record only) and `:260` (`gate.refusal_for_class(dclass)`) @ `64cc1380`;
`deep_research_live.py:115` and `deep_research_recorded.py:69`
(`approved_for=frozenset({DataClass.CLASS_C_INTERNAL})`) @ `64cc1380`; the refusal itself,
`packages/aia_core/src/aia_core/application/web_retrieval.py:618-632 @ 64cc1380`
(`RetrievalGate.refusal_for_class`).

**Reproduction.** Replace the plan step's `classify_material(...)` with
`classify_by_rule(..., MaterialRule.DESIGN, ...)` and run
`pytest apps/executors/tests/test_deep_research_journey.py`: the web tracks are refused
(hypothesis on the exact count; the gate's rule above is not). Plan `usable-classification` F1.

**Consequence.** A Deep Research run on an edited design parks (`egress_unclassified_material`,
"Zadání nemá klasifikaci vstupních dat. Nic nebylo odesláno.") until an operator classifies its
exact bytes (`AIA_AI_MATERIAL_CLASSIFICATIONS`), while the Lead and the design jobs run on the
same design by rule.

**Decision (the product owner, 2026-10-19).** Deep Research keeps operator-only classification of
a design. Its web routes stay Class C only; no query class of its own is made for a query a model
writes from a Class B design. A run on an edited design parks until an operator classifies its
exact bytes. Recorded in ADR 0008, Amendment 2026-10-19, *Addendum*; it narrows DR-2b
(`overview.md`, a digest of a design as Class B), which is not decided by it.

**Test.** What holds the decision: `test_deep_research_journey.py` runs on designs an operator
classified; a design classified by rule there would be the test of any later change.

**Status.** Decided. Nothing to build. On develop, decided again and implemented as advisory (the
product owner, 2026-10-21, Q65/Q66; plan `develop-class-advisory` chunk 5; #594, merged as `fdd27c9`;
ADR 0008, Amendment 2026-10-21): under `AIA_DATA_CLASS_GATES=advisory` an unclassified design takes
the design rule's class (B), recorded on the plan step's event
(`test_deep_research_class_advisory.py::test_under_advisory_an_unclassified_design_takes_the_design_rule_and_says_so`);
an operator's classification is kept. Still open for staging and production, where enforce applies.

---

## OI-130 · Decision · AI-written design text built from Class A knowledge is Class B once accepted

**Claim.** A design job's request is Class A when the client has approved knowledge (its snapshot
carries it), and what it writes into the study -- the brief analysis, an accepted questionnaire,
an accepted Lead edit -- is then design, Class B by rule, in every later request.

**Anchor.** `packages/aia_core/src/aia_core/domain/research_agents.py:679-686 @ 64cc1380`
(knowledge raises the job's request to A); `domain/research_lead.py:871 @ 64cc1380`
(`_part("design_analysis", …, MaterialRule.DESIGN)`); `apps/executors/src/aia_executors/ai_fieldwork.py:429`
and `analysis.py:584` @ `64cc1380` (`classify_by_rule(design, MaterialRule.DESIGN, …)`).
Plan `usable-classification` F7.

**Reproduction.** `apps/executors/tests/test_research_lead_executor.py::test_a_turn_is_answered_once_and_its_reply_is_read_from_the_step`
records the design part as `("design", "CLASS_B_DERIVED_CLIENT", "rule:design")`, whatever wrote
it.

**Consequence.** Text a model derived from Class A knowledge travels, once in the design, on a
route approved for Class B.

**Decision (the product owner, 2026-10-19).** Chosen for usability: AI-written design text built
from Class A approved knowledge is design, Class B, once a person accepts it into the study.
Brief attachment excerpts stay B as design, while the same bytes kept as a client source are A.
An operator may still raise a design's exact bytes to A. Recorded in ADR 0008, Amendment
2026-10-19, *Addendum*.

**Test.** `packages/aia_core/tests/test_material_rules.py::test_every_rule_has_the_class_the_owner_decided`
pins `rule:design` at B.

**Status.** Decided. Nothing to build.

---

## OI-131 · Decision · One batch may leave as Class C when a source is unmarked as it is sent

**Claim.** The "Interní dokument" mark is read before each request of a source's AI proposals, in
a transaction that ends before the gateway sends it; an unmark committed in those milliseconds
lets that one batch go as Class C, and every later batch is stopped (`source_class_changed`).

**Anchor.** `apps/executors/src/aia_executors/client_source_proposals.py:279-292 @ 64cc1380`
(`marked_internal`, then `caller.invoke`). Plan `usable-classification` F8.

**Reproduction.** None in one command: the window is the time between that transaction's commit
and the request leaving. A hypothesis on its width; its existence follows from the code.

**Consequence.** At most one batch of a document a person has just unmarked leaves as Class C,
the class its requests were built under.

**Smallest fix (not taken).** Hold the source row's lock across each model call, so an unmark
waits for the request in flight.

**Decision (the product owner, 2026-10-19).** The window is accepted over the wait. Recorded in
ADR 0008, Amendment 2026-10-19, *Addendum*.

**Test.** `apps/executors/tests/test_client_source_proposals.py::test_a_replayed_answer_keeps_the_class_it_was_sent_as_when_the_mark_changes`
(each answer keeps the class it was sent as).

**Status.** Decided: accepted.

---

## OI-132 · Hypothesis · A clicked accept may lose what is typed while the gate answers

**Claim.** A clicked accept of a Lead edit flushes, asks the gate, then reloads through the
session, which disposes the store; a change typed while the gate answers would be saved by
`dispose` against the old base, refused 409 with no listener, and lost.

**Anchor.** `apps/web/src/components/workbench/Workbench.tsx:429 @ 0b4e05e5` (`reload()` after a
decision), `apps/web/src/components/rehome/research/ResearchScreen.tsx:94 @ 0b4e05e5`
(`store?.dispose()`), `:104` (`retry` is the reload). The automatic accept had this race and
reads the copy in place instead (plan `inline-decisions`, Findings (fixed) 1, @ `eced14ab`).

**Reproduction.** Not reproduced. A `ResearchScreen` test that types while a deferred `/edits`
answer is held, then expects the text on screen and the save state `conflict`.

**Consequence.** A researcher typing during a click on Přijmout would lose what they typed.

**Smallest fix.** Read the copy in place as the automatic accept does:
`store.reload(undefined, { since })` with the copy as it was before the call.

**Test.** The reproduction above.

**Status.** Hypothesis: reproduce or delete (CLAUDE.md §9).

---

## OI-133 · Finding · `lead_journey.mjs` passes once per workbench

**Claim.** The Research Lead's browser journey checks that a personal note is absent from Můj
Vedoucí by its first 40 characters, which carry no timestamp, so a second run on the same
workbench finds the first run's kept note and fails.

**Anchor.** `tools/ui_workbench/lead_journey.mjs:121 @ 0b4e05e5` (unchanged since `2e5028cc`).
Plan `inline-decisions`, Findings.

**Reproduction.** Run `node tools/ui_workbench/lead_journey.mjs` twice on one
`make ui-workbench`: the second fails "a personal note waits for the researcher".

**Consequence.** The journey is rerun only on `python tools/ui_workbench/workbench.py up --fresh`.

**Smallest fix.** A run-unique marker at the start of the note.

**Test.** The journey run twice on one workbench.

**Status.** Open.

---

## OI-134 · Hypothesis · Two web tests time out under load and pass alone

**Claim.** In the full web suite on a loaded machine `MethodologyVersions.test.tsx` › "guided
methodology editing" exceeds its 5 s timeout, and `QuestionnaireStep.test.tsx` › "offers the three
paths…" misses its heading within `findByRole`'s 1 s; each failed once in two runs of 1,838 tests
@ `7c01686c` (2026-10-19), and both pass alone. The first fails the same way on `6c5cd620`.

**Anchor.** `apps/web/src/components/aia/settings/MethodologyVersions.test.tsx:411` and
`apps/web/src/components/rehome/research/QuestionnaireStep.test.tsx:96` @ `0b4e05e5`. Plan
`inline-decisions`, Findings. Of a kind with OI-122.

**Reproduction.** `make test-web` under load; not reproduced on demand.

**Consequence.** A red web suite with no defect behind it.

**Smallest fix.** Hypothesis: load, not a defect. If it recurs, give the waits room
(CLAUDE.md §7: size timing assertions generously) rather than a retry.

**Test.** The suite under load.

**Status.** Reproduced and closed by #536 (merged as `fd523a8`, 2026-10-21; plan `input-interactions`,
Findings WT-1, which carries all six parts). At load average ~7 the suite failed 3 tests, at ~13 it
failed 24 in 9 files, every file passing alone: CPU starvation against idle-sized budgets (vitest's
5 s per test, testing-library's 1 s per lookup), no shared state. Fix: `testTimeout: 30_000`
(`apps/web/vitest.config.mts`) and `asyncUtilTimeout: 10_000` (`apps/web/vitest.setup.ts`); three
full runs on a loaded host passed 2448 of 2448. Recorded in CLAUDE.md §7, Known flakes. WT-1 takes
no number of its own: it is this item.

---

## OI-135 · Finding · A design agent job ignores the study's spend limit

**Claim.** `ResearchAgentJobs.start` holds a reservation but never reads `spend_confirm_usd`, the
per-start confirmation threshold `ResearchRuns.start` applies, so a direct agent-job start (and a
rebuild) is never asked to confirm a cost that reaches the limit.

**Anchor.** `packages/aia_core/src/aia_core/application/research.py:1311-1407 @ 854c2092` (no read of
`spend_confirm_usd` in `start`); `ResearchRuns.start` applies it at `research.py:454` and `:826 @
854c2092`. Plan `research-lead-workbench`, Findings F1; confirmed by the cross-check (`mvp-master-plan.md`
§11.2, `lead-orchestration#LO15`).

**Reproduction.** Set a study's spend limit below `AIA_AI_RESEARCH_RESERVATION_USD`, then start any
design job: no confirmation is asked.

**Consequence.** Removing the stage's AI buttons does not close it: the start and rebuild routes stay
reachable, so the limit binds a research run and not a design job.

**Smallest fix.** The same check `ResearchRuns.start` has, inside `ResearchAgentJobs.start` and
`rebuild` (`lead-orchestration#LO15`, W0).

**Test.** A start whose reservation reaches the limit without a confirmation is refused, and with one
it is recorded in the approval ledger.

**Status.** Closed by #541 (merged as `b3984d4`, 2026-10-21, `lead-orchestration` LO15):
`ResearchAgentJobs.spend_gate` applies `money.threshold_verdict` to the job's reservation at start and
rebuild; the routes take `confirm_cost_usd` and answer 409 `cost_confirmation_required`. Tests:
`packages/aia_core/tests/test_research_agent_spend.py`, `apps/api/tests/test_research_agent_spend_api.py`.

---

## OI-136 · Finding · An accept could overwrite an edit made in another tab

**Claim.** An agent proposal's accept compared only Design Revisions on the server and only the
browser's own store in the web, so a working-copy save from a second session on an item the
proposal changes was overwritten by the accept.

**Anchor.** Before: `useResearchAgents.tsx:85` and `study_design_repository.py:180-183 @ 50547cdc`.
After: `application/proposal_accept.py:118-140 @ 854c2092` (`StaleProposal`: `design_moved`,
`unknown_baseline`, `items_changed`). Plan `research-lead-workbench`, Findings F2, closed by its chunk 8.

**Reproduction.** Before the fix: accept a proposal after another session saved a change to an item
the proposal touches; the other session's change is lost.

**Consequence.** Silent loss of a person's edit.

**Smallest fix.** Done: the item-level stale rule in one transaction under the study lock (chunk 8).

**Test.** `test_two_reviewed_design_proposals_cannot_overwrite_each_other`
(`test_workflow_concurrency.py`) and
`test_a_proposal_on_a_design_with_no_working_revision_is_refused_as_unknown`
(`test_research_agents.py`). No test is named for the exact second-session save; the plan names that
as the test that would have caught it.

**Status.** Closed (chunk 8).

---

## OI-137 · Finding · Settings lists no prompt version for the analysis modules

**Claim.** The settings document gives `research_analysis` an empty version list, so Settings cannot
say which analysis prompt a run used, although `system-prompts-settings` chunk 8 is ticked as having
filled it.

**Anchor.** `apps/api/src/aia_api/routers/settings.py:486-492 @ 854c2092`
(`NativeActivity(key="research_analysis", …, versions=[])`). Plan `system-prompts-settings`, Findings
F4 and its cross-check correction (master plan §6.2).

**Reproduction.** `GET /api/v1/settings` as any member: the `research_analysis` activity has
`versions: []`.

**Consequence.** AC-03 ("every worker's prompt editable and pinned") cannot be shown for the eight
analysis modules from Settings.

**Smallest fix.** `system-prompts-settings#7` lists the analysis harness and its prompt id and version.

**Test.** `test_settings_api` asserts `research_analysis` lists its versions after chunk 7.

**Status.** Open.

---

## OI-138 · Finding · The migration chain does not run on SQLite

**Claim.** `alembic upgrade head` fails on SQLite, while the tests build SQLite schemas with
`create_all`, so a migration is verified only on PostgreSQL.

**Anchor.** Plan `system-prompts-settings`, Findings F5 (`NotImplementedError: No support for ALTER of
constraints in SQLite`).

**Reproduction.** `DATABASE_URL=sqlite:///x.db alembic upgrade head`.

**Consequence.** None for the product, which runs PostgreSQL; a drift between the models and the
migrations shows only on PostgreSQL.

**Smallest fix.** None needed for the product. CI already runs `alembic upgrade head` / `alembic check`
on PostgreSQL (`ARCHITECTURE.md` §8); `AGENTS.md` § Alembic says to verify migrations there.

**Test.** CI's `alembic check` on PostgreSQL.

**Status.** Open; accepted as a property of the test setup, not a defect.

---

## OI-139 · Finding · The Lead's request card shows no cost and starts the job on one click

**Claim.** A Lead turn's request card starts a paid agent job on "Spustit úlohu" without showing its
price; the only ceiling is the flat `AIA_AI_RESEARCH_RESERVATION_USD`, raised only as a 409 when it
reaches the study's limit, and the turn returns no cost.

**Anchor.** `apps/web/src/components/workbench/LeadPane.tsx:471-488`, `Workbench.tsx:258-279`,
`apps/api/src/aia_api/routers/lead.py:458-462`, `application/research_lead.py:720-734 @ 242523e`.
Plan `lead-orchestration`, Findings CR-1 (the coordinator's card review, 2026-10-20).

**Reproduction.** `make ui-workbench` with in-process scripted model answers and
`AIA_AI_ANALYSIS_ENABLED=true`, then `make ui-fixtures`; a Lead turn proposing an agent job, then
"Spustit úlohu".

**Consequence.** A person approves paid work without seeing its price.

**Smallest fix.** The card path's price step (`lead-orchestration` LO4, LO10): the turn returns
`ceiling_usd`, the card shows "až X USD" and sends `confirm_cost_usd`.

**Test.** A request card renders its ceiling, and approving it without `confirm_cost_usd` at or above
the limit is refused.

**Status.** Open.

---

## OI-140 · Finding, closed · A design job waiting for budget reads as a failure with "Zkusit znovu"

**Claim.** When a stage's design job stops at the study's budget, the stage shows a fault card whose
"Zkusit znovu" starts a new job, while the real budget lift sits out of sight.

**Anchor.** `apps/web/src/lib/research-agent-jobs.ts:28, 45-47`,
`components/rehome/research/useAiStep.tsx:47, 58-80`; `AgentBudgetWaits` mounted only at
`ResearchScreen.tsx:319, 363 @ 242523e`. Plan `two-roles-human-ai-gates`, Findings CR-2.

**Reproduction.** `make ui-workbench` with in-process scripted model answers and
`AIA_AI_ANALYSIS_ENABLED=true`, then `make ui-fixtures`; a study with no budget left, then any stage's
AI job.

**Consequence.** "Zkusit znovu" starts a new job instead of lifting the budget; the real lift is
hidden in "Připravenost a pomoc".

**Smallest fix.** `followAgentJob` reports an `AWAITING_BUDGET` step as its own kind (and `waiting`
counts `AWAITING_*`); `AiFailureCard` renders `AgentBudgetWaits` for it.

**Test.** A job whose step is `AWAITING_BUDGET` shows the budget lift in place, never a retry.

**Status.** Closed by #533 (merged as `5116723`, 2026-10-21).

---

## OI-141 · Finding, closed · One budget lift releases one analysis step, so a run's eight steps need eight lifts

**Claim.** Progress draws a budget form under every waiting step, and the lift passes only that one
step to `lift_study_budget_waits`, so a run whose eight analysis modules stopped at the cap needs
eight lifts.

**Anchor.** `components/rehome/research/ExecutionSteps.tsx:1285-1287` (a `BudgetLift` per step),
`application/research.py:1036-1049 @ 242523e` (line 1048 passes `[step]` to
`lift_study_budget_waits`). Plan `two-roles-human-ai-gates`, Findings CR-3.

**Reproduction.** `make ui-workbench` with in-process scripted model answers and
`AIA_AI_ANALYSIS_ENABLED=true`, then `make ui-fixtures`; a run whose analysis steps stop at the
study's cap, then one 20 USD lift on Progress.

**Consequence.** Eight forms, eight clicks, the budget raised each time, eight ledger rows.

**Smallest fix.** Lift every `AWAITING_BUDGET` step of the run (`run["steps"]`; the helper already
filters) and render one run-level lift.

**Test.** One lift on a run with several waiting steps resumes them all, in one ledger row.

**Status.** Closed by #533 (merged as `5116723`, 2026-10-21).

---

## OI-142 · Finding, closed · A client with DATASET, ARTIFACT or FINDING knowledge cannot run any AI design job

**Claim.** A design job over a client whose knowledge holds a DATASET, ARTIFACT or FINDING item carries the
placeholder lineage `unclassified-client-knowledge`, which the licence gate refuses, so that client
gets no AI help although only titles and summaries reach the model.

**Anchor.** `domain/research_agents.py:688-690` (the placeholder lineage
`unclassified-client-knowledge`), `domain/licence.py:158-164`, no such entry in
`domain/licence_determinations.py @ 242523e`; `knowledge_entries` (`research_agents.py:545-562`)
carries no lineage. Plan `client-data-in-analysis`, Findings CR-4.

**Reproduction.** `make seed-develop`, then any design job for Horizont Mobility: refused
`licence_dataset_unknown`.

**Consequence.** The seeded client, and any real client with a dataset, artifact or finding, gets no
AI help.

**Smallest fix.** The lineage is the union of the items' recorded datasets (`provenance.datasets`),
the placeholder only when one is unrecorded; the seed records `aia_synthetic_fixture`.

**Test.** A design job over a client with DATASET, ARTIFACT and FINDING knowledge, each recording its
dataset, passes the licence gate; one over an item of any of the three kinds with no recorded dataset
is still refused by name.

**Status.** Closed by #537 (merged as `fe85aa54`, 2026-10-22; the fix is `40df02ab`): the lineage
is the union of the items' recorded `provenance.datasets` (`research_agents.knowledge_lineage`,
`packages/aia_core/src/aia_core/domain/research_agents.py:577-580 @ 6bfe3760`;
`domain/knowledge.py:410-420`), the placeholder `UNRECORDED_KNOWLEDGE_LINEAGE` only for a
DATASET/ARTIFACT/FINDING item recording none, for the design jobs and the Lead's turn alike; the
develop seed records `aia_synthetic_fixture`. Tests:
`test_a_design_job_over_the_seeded_client_declares_its_recorded_datasets`,
`test_knowledge_lineage_is_the_recorded_datasets_else_the_placeholder`,
`test_a_turn_declares_recorded_datasets_and_the_placeholder_for_an_unrecorded_one`. Earlier: the EU
Bedrock route was unblocked by #582's determination (merged as `7cd7acd`, 2026-10-21;
`CLIENT_KNOWLEDGE_DATASET` APPROVED for `bedrock-eu-primary` alone, OI-187), so an unrecorded item
still refuses on any other route (`not_approved_for_route`). Develop's already-seeded items show the
fix only on a fresh seed.

---

## OI-143 · Finding, closed · The report card said "Modelovaná data" for a run of fictional respondents

**Claim.** The report card's "Omezení, původ dat a příloha evidence" part was a static string that
never read the run's origin, so a fictional run was labelled modelled.

**Anchor.** Before: `apps/web/src/components/rehome/research/CompleteReport.tsx:66 @ 242523e`, a
static string in `reportParts` that never read `runOriginKinds` (`lib/research-execution.ts:186-205`).
After: `04ed258f` (#530), `reportParts` takes the run's origin kinds and words them through
`originWords`. Plan `report-delivery`, Findings CR-5.

**Reproduction.** Before the fix: `make ui-research` (fictional fieldwork), then Výsledky's report
card.

**Consequence.** A fictional run was labelled modelled, against the rule that every label reads the
origin.

**Smallest fix.** Done: "Fiktivní data", "Modelovaná data", "Neznámý původ dat" (an unknown origin,
or none stated yet), a mixed run every kind.

**Test.** `CompleteReport.test.tsx` "the report card's origin (CR-5)".

**Status.** Closed (`04ed258f`, #530).

---

## OI-144 · Finding · The sample size is silently clamped

**Claim.** Typing 20 in "Počet respondentů" stores 50, and an empty field stores the recommendation,
with no message.

**Anchor.** `apps/web/src/research/persona.ts:180 @ 44b66ef`; the field at
`apps/web/src/components/rehome/research/PersonaStep.tsx:407 @ 44b66ef`. Audit
`.planning/evidence/input-interactions-audit.md` §6, IA-1.

**Reproduction.** A Vitest on `setSampleSize(p, "20").project.n === 50`.

**Consequence.** The researcher believes n is what they typed.

**Smallest fix.** Refuse out-of-range at the field (input standard I2, I9; `input-interactions`
chunk 5).

**Test.** The stepper's unit test asserting 20 is shown as an error and not stored.

**Status.** Closed by #539 (merged as `c7d2d65`, 2026-10-21, `run-qc-and-checkpoint` RQC9):
`research/persona.ts` `setSampleSize` refuses a value outside the server's valid n
(`GET …/research/limits`) and never clamps; test `PersonaStep.test.tsx` "the sample: a value outside
the server's valid n is refused and said, never clamped (IA-1)".

---

## OI-145 · Finding · Scale ends accept nonsense, and the domain truncates 2.5 to 2

**Claim.** A scale question's minimum and maximum save min 8 / max 3, 2.5 and an empty field (stored
0) to the working copy; compile refuses min ≥ max only at readiness, turns 2.5 into 2 with `int()`,
and makes an empty minimum a 0–10 scale.

**Anchor.** `apps/web/src/components/rehome/research/QuestionnaireStep.tsx:777,779 @ 44b66ef`
(`setScaleEnd` with `+raw`); `packages/aia_core/src/aia_core/domain/research_design.py:405 @ 44b66ef`
(`_scale`). Audit `input-interactions-audit.md` §6, IA-2.

**Reproduction.** A unit test compiling a scale question with `skala: [2.5, 10]` gets `(2, 10)` and no
problem.

**Consequence.** Fieldwork asks a scale the researcher did not set.

**Smallest fix.** Bounded steppers (audit A9) and the domain refusing a non-integer end (audit §5.7).

**Test.** A Vitest on `setScaleEnd`; a domain test that `[2.5, 10]` is `invalid_scale`.

**Status.** Partly fixed: the domain refuses a non-integer end (`invalid_scale`) since #538 (merged as `45ffa12`, input-interactions 3b1); the editor's field check is `input-interactions#3b2`, open.

---

## OI-146 · Finding · The n slider cannot reach the field's range

**Claim.** The sample-size slider runs 200–2000 while the field beside it runs 50–5000, so a stored n
of 3000 puts the slider at its end.

**Anchor.** `apps/web/src/components/rehome/research/PersonaStep.tsx:380` (200–2000) vs `:407`
(50–5000) `@ 44b66ef`. Audit `input-interactions-audit.md` §6, IA-3.

**Reproduction.** Type 3000 in the field; the slider shows 2000.

**Consequence.** The slider misrepresents the value.

**Smallest fix.** One stepper (audit B1).

**Test.** As OI-144.

**Status.** Open.

---

## OI-147 · Finding, closed · The knowledge search sends a request on every keystroke

**Claim.** The client library's search sends one GET per keystroke.

**Anchor.** `apps/web/src/components/aia/clients/KnowledgeLibrary.tsx:85-88 @ 44b66ef`. Audit
`input-interactions-audit.md` §6, IA-4.

**Reproduction.** Type "segmentace" with the network panel open: ten GETs.

**Consequence.** Wasted requests; results flicker.

**Smallest fix.** A 300 ms debounce, as `MemorySearch.tsx:43`.

**Test.** A Vitest with fake timers counting requests.

**Status.** Closed by #569 (merged as `ec75af1`, 2026-10-21): the library's search is debounced (300 ms).

---

## OI-148 · Finding · A contact is deleted with one click

**Claim.** "Odebrat" on a client's contact sends the DELETE at once, with no confirmation and no undo.

**Anchor.** `apps/web/src/components/aia/clients/ProfileArea.tsx:260 @ 44b66ef`. Audit
`input-interactions-audit.md` §6, IA-5.

**Reproduction.** `make ui-workbench` + `make ui-fixtures`; Profil, then "Odebrat" on a contact.

**Consequence.** A slip loses a contact, with nothing to bring it back.

**Smallest fix.** Undo (input standard I6).

**Test.** The client journey removing and restoring a contact.

**Status.** Open.

---

## OI-149 · Hypothesis · Selects that act on change

**Claim.** Several selects fire their action on change, so a keyboard user moving through the options
can fire it.

**Anchor.** `apps/web/src/components/aia/clients/KnowledgeLibrary.tsx:241,259,268,382,406`,
`apps/web/src/components/aia/clients/KnowledgeArea.tsx:494 @ 44b66ef`. Audit
`input-interactions-audit.md` §6, IA-6.

**Reproduction.** Not reproduced. Reproduce in Chrome on Windows, where a closed `<select>` changes on
arrow keys, before budgeting.

**Consequence.** An action fires that the person did not choose.

**Smallest fix.** A menu button (audit D11).

**Test.** A component test that arrow keys do not call the action.

**Status.** Open; a hypothesis until reproduced. The replacement control exists since #532 (merged as
`700eab5`: `apps/web/src/components/ui/MenuButton.tsx`, arrows move without acting); no call site above
has moved to it yet. Since #569 (merged as `ec75af1`, 2026-10-21) the knowledge library's call sites
file by menu, so the hypothesis is moot there; it stands for `apps/web/src/components/aia/clients/IntakeSheet.tsx:329, 347 @ c98836c` (the
intake sheet's folder and label selects).

---

## OI-150 · Finding · A scale question's labels never reach respondents

**Claim.** A scale question's labels (`popisky_skaly`) are never compiled, so AI respondents see bare
numbers while a tracked set's ends are sent.

**Anchor.** `packages/aia_core/src/aia_core/domain/ai_respondent.py:379-388 @ 44b66ef` builds a scale
question's item without labels, and `research_design.py` never reads `popisky_skaly`. Audit
`input-interactions-audit.md` §6, IA-7.

**Reproduction.** Compile a question with `popisky_skaly: ["vůbec", "zásadně"]`: the `SpecQuestion`
carries no labels and the respondent prompt shows the numbers alone.

**Consequence.** AI respondents answer "1–10" without knowing which end is which; the researcher's
labels look honoured on screen and are not.

**Smallest fix.** Compile and send them (`input-interactions` chunk 3b, § Scales). It moves the
respondent-system fingerprint the holdout validation binds to, and the wording rule is the
methodology owner's (`mvp-master-plan.md` § The scope baseline, Open).

**Test.** A domain test that the question's prompt carries "1 = vůbec, 10 = zásadně".

**Status.** Fixed behind a switch: #538 (merged as `45ffa12`, input-interactions 3b1) compiles the labels and sends them to respondents under `AIA_AI_SCALE_LABELS_IN_PROMPT`, off by default; switching it on moves the respondent-system fingerprint and waits on the methodology owner's wording rule. Open until it is on.

---

## OI-151 · Finding · The Lead's rolling summary that ADR 0026 promised is not built

**Claim.** ADR 0026 decision 2 promises "a rolling summary of older turns, stored as an artifact of
the Lead's run"; none exists, and `freeze_context` keeps 12 turns and counts the rest.

**Anchor.** `packages/aia_core/src/aia_core/domain/research_lead.py:121,796-827 @ 237fd0a`. Plan
`lead-conversation`, Findings F1 (#529).

**Reproduction.** Post 13 messages in one study; turn 14's stored context has `omitted_turns: 1` and
no summary.

**Consequence.** The Lead forgets the start of a long study's conversation.

**Smallest fix.** `lead-conversation` LC3 (the decision digest), then LC7 (ADR 0041, Proposed).

**Test.** LC3's "turn 3 in turn 40" test.

**Status.** Open, partly addressed. #731 (merged as `1cc87e25`, 2026-10-22; `lead-conversation` LC3)
carries what the conversation decided into every next turn: the decision digest
(`packages/aia_core/src/aia_core/domain/lead_digest.py:163 @ 6bfe3760`, `decision_digest`), the
context's `memory` layer (`domain/research_lead.py`, `freeze_context(… memory=)`). The rolling summary
of older turns' words is still not built; it is LC7's.

---

## OI-152 · Finding, closed · ADR 0026 said one conversation per study, shared by everyone

**Claim.** ADR 0026's *Consequences* said "one conversation per study … shared by everyone who opens
the study", contradicting its own *Accepted with* 6 and the code (one conversation per researcher).

**Anchor.** `docs/architecture/adr/0026-research-lead-proposes-a-person-decides.md:455 @ 3d98e9e`;
the code scopes a turn by `user_id` (ADR 0026 decision 8). Plan `lead-conversation`, Findings F2
(#529).

**Reproduction.** Read the two places side by side.

**Consequence.** Docs only: a reader could build a shared conversation that the owner ruled out.

**Smallest fix.** Done in this docs PR: the line reads "one conversation per researcher per study".

**Test.** None; a documentation defect.

**Status.** Closed (this docs PR).

---

## OI-153 · Finding · A rendered report's DOCX does not record which ledger ref a number came from

**Claim.** On every render path that prints a number (prose values, table cells, KPI tiles, captions,
charts, the map chapters), the DOCX writes plain text runs or an image; no element carries the ledger
ref, apart from the evidence appendix's visible text.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/report_docx/blocks.py:116-123 @ e09a6c99`
(`write_value`), with the full path table P1-P15 in
`.planning/evidence/editor-spike-2026-10-21.md` § F-ED1 (#531).

**Reproduction.** Render any sample report (`make report-preview`), unzip `word/document.xml`, and
search it for a ledger ref id: the only hits are the appendix's visible text.

**Consequence.** Once a person edits the DOCX in any document editor, AIA cannot tell an evidenced or
machine-written number from one someone typed; a report's numbers cannot be checked through a DOCX
round trip.

**Smallest fix.** For `report-delivery#RD6`: the renderer wraps every printed group in a locked content
control (`w:sdt`, `sdtContentLocked`) tagged with its source, and a census on save refuses a lost or
changed control and a changed numeric token outside one (the evidence file states the rule).

**Test.** A renderer test over one `ReportDocument` holding every path P1-P15: every source has a tag,
no tag lacks a source, and every numeric token outside a field result sits inside a tagged control.

**Status.** Open.

---

## OI-154 · Finding, closed · A segmented control had no arrow keys

**Claim.** `Segmented` made every option its own Tab stop and ←/→ did nothing, against the input
standard's I11 (roving tabindex).

**Anchor.** `apps/web/src/components/rehome/step.tsx:139 @ e09a6c99`. Plan `input-interactions`,
Findings IA-8.

**Reproduction.** `step.test.tsx` › "Segmented is one Tab stop whose arrows move and choose
(input-interactions I11)" fails on `e09a6c99`.

**Consequence.** A keyboard user tabs through every option of every segmented control.

**Smallest fix.** Done: `lib/roving.ts` (`rovingIndex`, `tabStop`) in `Segmented`, as in ChoiceChips.

**Test.** The `step.test.tsx` test above.

**Status.** Closed by #532 (merged as `700eab5`, 2026-10-21).

---

## OI-155 · Finding, closed · The web's applyLeadEdit wrote a different working copy from the server's apply_edit

**Claim.** An accepted Lead edit was applied in the browser by hand-copied rules that had drifted from
the server's `apply_edit`, so the screen's copy after an automatic accept differed from the saved one.

**Anchor.** `apps/web/src/lib/lead.ts:180-238 @ 6b76eef4` against
`packages/aia_core/src/aia_core/domain/research_lead.py:1200-1320 @ 6b76eef4`. Plan
`working-copy-edit-ops`, Findings F-WCE0-1.

**Reproduction.** The shared case file's test against that `lead.ts` fails 10 of 25 apply cases: five
on behaviour (both problem-summary cases, a research question added and one reworded, options on a
scale dropped where the server refuses `options_on_non_selection`) and five because it gave no
refusal word.

**Consequence.** "Vrátit" read the wording to put back from a copy that was not the one saved, until
the reload.

**Smallest fix.** Done: `applyLeadEdit` mirrors `apply_edit` and returns the server's refusal word,
held to `packages/aia_core/tests/fixtures/edit_ops/cases.json`.

**Test.** `apps/web/src/lib/edit-ops.cases.test.ts`.

**Status.** Closed by #534 (merged as `3a89dfe`, 2026-10-21, working-copy-edit-ops WCE0).

---

## OI-156 · Finding · The web and the server fold case differently when they match a list item

**Claim.** The Lead's list edits match an item by its folded wording, and the browser folds with
`toLocaleLowerCase("cs")` while the server uses `str.casefold`, so a wording `casefold` expands is
found by one side and not the other.

**Anchor.** `apps/web/src/lib/lead.ts:139 @ 25f2623` (`norm`, `toLocaleLowerCase("cs")`) against
`packages/aia_core/src/aia_core/domain/edit_ops.py:337-339 @ 25f2623` (`_key`, `casefold`). Plan
`working-copy-edit-ops`, Findings F-WCE0-2.

**Reproduction.** `python -c "print('STRASSE'.casefold() == 'straße'.casefold())"` prints `True`;
`"STRASSE".toLocaleLowerCase("cs") === "straße".toLocaleLowerCase("cs")` is `false` in Node.

**Consequence.** A list item spelled with `ß` (or another character `casefold` expands) is found by the
server and not by the screen; rare in Czech content.

**Smallest fix.** One fold on both sides. WCE1 (#543) gave item identity the server's fold
(`apps/web/src/research/item-ids.ts`, `case-folds.ts`), but `applyLeadEdit`'s `norm` still folds its
own way; it takes `item-ids.ts`'s fold, or keys by id (WCE2).

**Test.** A case in `tests/fixtures/edit_ops/cases.json` with `ß`.

**Status.** Open (`working-copy-edit-ops` WCE2).

---

## OI-157 · Finding, closed · touches() and locked_items() keyed a repeated question differently

**Claim.** `touches()` keyed a question and a section by its raw id while `locked_items()` used
`design_items`' occurrence key, so on a copy with a repeated id the two disagreed.

**Anchor.** `domain/edit_ops.py` `touches` against `locked_items` (`item_values`, `occurrence_keys`)
at #534's head (`b5b369ae`). Plan `working-copy-edit-ops`, Findings F-WCE0-3.

**Reproduction.** A copy with two questions `id: "Q1"`, the second `sociomap_rating`: `locked_items`
holds `content:question:Q1#2`; a `question_edit` of `Q1` touches `content:question:Q1`; a section with
no id is `#<i>` in `design_items` and `""` in `touches`.

**Consequence.** None on well-formed content; on a malformed copy the lock and the touch set disagree.

**Smallest fix.** Done: `touches` is the field diff of applying the edit (`domain/design_fields.py`),
so both read one keying.

**Test.** `test_two_people_adding_questions_to_one_section_touch_different_keys`,
`test_a_section_move_is_an_item`.

**Status.** Closed by #543 (merged as `ea2a6a5`, 2026-10-21, working-copy-edit-ops WCE1).

---

## OI-158 · Finding · An approved Deep Research run limit bounds nothing

**Claim.** `budgets.run_limit.<preset>` ("Most a Standard run may cost") is an approved, pinned
setting that no executor or enqueue reads.

**Anchor.** `packages/aia_core/src/aia_core/domain/deep_research/settings.py:366-378 @ c88fd7fd`; its
one reader checks a scoped test policy against its cap
(`infrastructure/deep_research_settings_repository.py:284 @ c88fd7fd`). Plan
`mvp-acceptance-harness`, Findings F-2.

**Reproduction.** `grep -rn "run_limit" packages/aia_core/src apps/executors/src --include=*.py`: two
hits, neither stops a run.

**Consequence.** An organization's per-run ceiling is not held; a run is bounded only by the study's
budget and the start's confirmation, so tier B's lines A06-A08 are held by the runbook alone.

**Smallest fix.** The enqueue refuses, by name, a run whose `deep_research_cost_ceiling` exceeds the
pinned run limit.

**Test.** An enqueue whose ceiling exceeds an approved run limit answers 409 naming it.

**Status.** Open; decided 2026-10-26: the product owner chose to remove the setting rather than enforce it
(ADR 0022 Q2 (b), "Remove the setting", Decision Review, relayed by the PM coordinator). Closes when
`deep-research-web-search#61` lands; the test becomes "the catalogue has no `budgets.run_limit.*` key".

---

## OI-159 · Finding, closed · The acceptance study cannot use a scoped Deep Research test policy

**Claim.** A study test policy requires the study's budget to be at most USD 20, and the representative
acceptance study's is USD 25.

**Anchor.** `infrastructure/deep_research_settings_repository.py:458-467 @ c88fd7fd`;
`docs/migration/mvp-acceptance.md` §1. Plan `mvp-acceptance-harness`, Findings F-4.

**Reproduction.** Propose a test policy for a study budgeted USD 25: refused, "test budget must cover
this study and be at most USD 20".

**Consequence.** Tier B's live Deep Research needs the organization's own live approvals (ADR 0022),
not the sandbox.

**Smallest fix.** An owner choice: the organization's approvals for the acceptance organization, or a
USD 20 study.

**Test.** The existing guard, `test_deep_research_sandbox_policy.py`.

**Status.** Closed 2026-10-25 by decision: the owner chose (a), "use the organisation's live
approvals for the acceptance organisation" (OI-159 (a), the audit page, relayed by coordinator 3). The owner's note, verbatim:
"deep research uses budget of the study it pertains to." Nothing to build: the acceptance study
stays at USD 25 and its priced Deep Research calls are held against that study's budget; the
approvals themselves are the owner's clicks on Settings → Deep Research (DR-SIGNOFF (a), the same
day).

---

## OI-160 · Finding · A respondent's model calls are not readable over HTTP

**Claim.** The fieldwork dataset is never inlined and an artifact's response carries no provenance,
so AC-15's per-number walk has no HTTP read for fieldwork calls.

**Anchor.** `apps/api/src/aia_api/routers/research.py:156` and `routers/runs.py:181-200 @ c88fd7fd`.
Plan `mvp-acceptance-harness`, Findings F-5 (chunk 16, G65).

**Reproduction.** `GET …/research/runs/{id}/artifacts/{fieldwork artifact}` answers `payload: null`
and no `provenance`.

**Consequence.** Tier A reconciles fieldwork calls only through the study's spend.

**Smallest fix.** A run's usage lines over HTTP (call ids, request ids, model, cost), no respondent
content.

**Test.** Over HTTP, a run's usage lists each respondent call's provider request id.

**Status.** Open (`mvp-acceptance-harness#16`).

---

## OI-161 · Finding · Most client routes check the request before the client's scope

**Claim.** Another organization's user who sends `{}` to 26 of the 37 routes naming a client (and no
study) gets 422, not 404, because each route validates its body and path before it resolves the
client context.

**Anchor.** For example `POST /clients/{client_id}/contacts`, `apps/api/src/aia_api/routers/workspace.py
@ c170c921`. Plan `mvp-acceptance-harness`, Findings F-6.

**Reproduction.** `test_mvp_acceptance.py::test_ac01_a_user_of_another_organization_cannot_tell_a_client_from_an_absent_one`
asserts the weaker rule; tightening it to 404 fails on those 26 routes.

**Consequence.** Nothing is disclosed (an absent client gets the same 422), but the client routes do
not keep the study routes' rule that scope answers first.

**Smallest fix.** Resolve the client context as a dependency, as `get_study_context` does for studies.

**Test.** The client probe with the 404 rule.

**Status.** Open.

---

## OI-162 · Finding, closed · A write's 2xx was sent before its transaction committed

**Claim.** `get_session` commits after its `yield`, and under FastAPI's default scope for a `yield`
dependency (since 0.118.0) that code runs after the response has been sent.

**Anchor.** `apps/api/src/aia_api/dependencies.py:168-181 @ fd523a81`, taken as `Depends(get_session)`
at `:323`, `:368`, `:441`, `:448` and `SessionDep` `:455`. Plan `mvp-acceptance-harness`, Findings
F-AH1.

**Reproduction.** `pytest apps/api/tests/test_commit_before_response.py` with the scope removed: under
uvicorn `POST /members` answers 201 while the commit is still running, and a commit refused at
`before_commit` still answers 201.

**Consequence.** A client reading right after a write saw the state before it: the acceptance step's
`POST /members` then `POST /session` inserted the user twice (UniqueViolation `uq_users_email`, a 500),
about 1 run in 4; a failed commit was rolled back after a 201.

**Smallest fix.** Done: `SessionDep = Annotated[Session, Depends(get_session, scope="function")]`, every
user through that alias, `fastapi>=0.121.1`.

**Test.** `test_a_write_is_committed_before_its_response_is_sent`,
`test_a_commit_that_fails_is_the_response`, `test_every_route_takes_its_session_in_function_scope`.

**Status.** Closed by #540 (merged as `fcf048a`, 2026-10-21).

---

## OI-163 · Finding, closed · The confirmation threshold's rule had three inline copies

**Claim.** The Deep Research start, the Lead's approve path and a validation start each compared
`confirm_cost_usd` inline beside `money.threshold_verdict`.

**Anchor.** `application/deep_research.py:648-651`, `application/research_lead.py:724-729`,
`application/validation.py:200-203 @ fd523a81`. Plan `lead-orchestration`, Findings F-LO0-1.

**Reproduction.** `grep -n "confirm_cost_usd <" packages/aia_core/src/aia_core/application/*.py` at
`fd523a81` lists the three.

**Consequence.** None while all four agreed; a change to the rule made in one place would have left the
others on the old one.

**Smallest fix.** Done: each calls `threshold_verdict` (the Lead's path through `spend_gate`), keeping
its own refusal for an unknown ceiling.

**Test.** `test_every_start_path_applies_the_one_domain_rule` (`test_research_agent_spend.py`).

**Status.** Closed by #541 (merged as `b3984d4`, 2026-10-21, `lead-orchestration` LO15).

---

## OI-164 · Finding, closed · A non-finite number in a request body answered 500

**Claim.** `Infinity` or `NaN` in a JSON body (which Python's parser accepts) was refused by
validation, and then the 422 failed to serialise its echo of the input.

**Anchor.** `apps/api/src/aia_api/observability.py:206-213 @ 8e3f55dd`. Plan `lead-orchestration`,
Review of #541, Finding F-E03-1.

**Reproduction.** `test_a_confirmation_outside_its_bound_or_not_finite_is_refused[Infinity]` against
that line.

**Consequence.** A malformed client got a 500 and an error report instead of a 422.

**Smallest fix.** Done: the echo keeps non-finite constants as text (`parse_constant=str`).

**Test.** The test above.

**Status.** Closed by #541 (merged as `b3984d4`, 2026-10-21).

---

## OI-165 · Finding, closed · A reword accepted on the server does not carry its research-question links

**Claim.** Until WCE2, a Lead `list_replace` of a linked research question accepted by click leaves
its questionnaire links dangling, while the same edit accepted automatically in the browser (with
`AIA_WEB_STABLE_ITEM_IDS` on) carries them.

**Anchor.** `application/research_lead.py` `decide_edits` saves `edit_ops.apply_edit`'s result, which
does not call `settle_item_ids`, at #543's head (`2931fa6c`). Plan `working-copy-edit-ops`, Findings
F-WCE1-1.

**Reproduction.** With `AIA_WEB_STABLE_ITEM_IDS` on, accept such an edit by click: the trace names a
dangling link; accepted with `auto` it does not.

**Consequence.** A dangling link, only with the switch on (off by default).

**Smallest fix.** WCE2's one writer settles every write.

**Test.** A WCE2 test of the accept route asserting no dangling link.

**Status.** Closed by #801 (merged as `1ab6a012`, 2026-10-22; `working-copy-edit-ops` WCE2d):
`decide_edits` applies a turn's accepted edits through `application/working_copy.py`
`apply_edit_ops` (`:53 @ 6bfe3760`; called from `application/research_lead.py:846`), which settles
the copy's ids on every write.
`packages/aia_core/tests/test_lead_edits_logged.py::test_a_reworded_research_question_keeps_its_links_in_a_copy_that_keeps_ids`.

---

## OI-166 · Finding · A whole-list replacement with a stale id list moves links onto another research question

**Claim.** A writer that replaces a whole plan list and keeps its old id list is read as rewords, so
with the switch on the web moves questionnaire links onto an unrelated research question.

**Anchor.** `domain/item_ids.py` `reconcile` (the equal-count gap rule) with `follow_rewords`, reached
by `apps/web/src/research/plan.ts` `applyVariant` and `plan-edit.ts` `applyNarrative` at #543's head
(`2931fa6c`). Plan `working-copy-edit-ops`, Findings F-WCE1-2.

**Reproduction.** `settle_item_ids` with before `["Kdo kupuje kávu?", "Jak často?", "Kde nakupují?"]`,
Q1 linked to "Jak často?", after `["Proč nekupují?", "Které značky znají?", "Kde nakupují?"]`: Q1 now
links "Které značky znají?".

**Consequence.** A stamped guess: a measure moved onto an unrelated research question. With the switch
off nothing stores id lists, so links never move. Blocks switching `AIA_WEB_STABLE_ITEM_IDS` on.

**Smallest fix.** Writers that replace a whole list drop its id list, and `follow_rewords` follows
only a reword the binding vouches for, never a gap match.

**Test.** The reproduction, asserting the link dangles rather than moves.

**Status.** Open (`working-copy-edit-ops` WCE8b with WCE2).

---

## OI-167 · Finding · touches and lock_refusal answer differently from before WCE1

**Claim.** Since `touches` became the field diff of applying the edit, a `question_edit` that changes
nothing on a locked rating question passes the lock, and an edit `apply_edit` refuses touches nothing
and is refused with its own word, not the lock's.

**Anchor.** `domain/edit_ops.py` `touches` at #543's head (`2931fa6c`). Plan `working-copy-edit-ops`,
Findings F-WCE1-3.

**Reproduction.** The independent review's probe over set_text, list ops, question add / edit /
remove, set_n, malformed content and a locked question and battery: no refusal became an apply.

**Consequence.** None today: `lock_refusal` is not wired.

**Smallest fix.** WCE2 asks `refusal` before the lock.

**Test.** WCE2's every-writer lock tests.

**Status.** Open; a prerequisite of WCE2 and of switching `AIA_WEB_STABLE_ITEM_IDS` on.

---

## OI-168 · Hypothesis · Switching stable item ids on rewrites every loaded study's design bytes

**Claim.** With `AIA_WEB_STABLE_ITEM_IDS` on, the store writes id lists into every study it loads and
saves the copy before a submit, which moves each design's exact bytes.

**Anchor.** The store's `completed` copy (`apps/web/src/research/store.ts`) and `research_agents.py`
`proposal_result` spreading model output over a plan carrying `*_ids`, at #543's head (`2931fa6c`).
Plan `working-copy-edit-ops`, Findings F-WCE1-4.

**Reproduction.** Hypothesis-grade until the switch is turned on: load a study with the switch on and
compare the saved design's SHA-256 with the one before.

**Consequence.** Deep Research classifies a design by its exact bytes (OI-129), so those designs park
until an operator classifies them again; a model can echo stale id entries back (OI-166's input).

**Smallest fix.** Before switching on: a rollout note, the agents' context without id lists (or
WCE8b), and the re-classification planned.

**Test.** A switch-on test that a design job's context carries no `*_ids`.

**Status.** Open; a hypothesis until reproduced (CLAUDE.md §9), and a switch-on prerequisite.

---

## OI-169 · Hypothesis · Turning stable item ids on and then off leaves stale id lists

**Claim.** Stored id lists stay after the switch is turned off and go stale under writers that ignore
them; the server keeps reading them by the gap rule.

**Anchor.** `domain/item_ids.py` `reconcile` at #543's head (`2931fa6c`). Plan `working-copy-edit-ops`,
Findings F-WCE1-5.

**Reproduction.** Hypothesis-grade: switch on, load a study, switch off, edit its plan lists in a
stage, and read the stored id lists.

**Consequence.** Identity read from stale lists after a later switch-on (links never move on the
server).

**Smallest fix.** Strip the id lists when off, or record that turning off is one-way until WCE2.

**Test.** An off-after-on test that no stale id list survives a save.

**Status.** Open; a hypothesis until reproduced (CLAUDE.md §9), and a switch-on prerequisite.

---

## OI-170 · Finding · A retry drains the study's wallet

**Claim.** A retry is a new run, so it takes its own wallet charge at its full ceiling while the
original's hold is never released.

**Anchor.** `infrastructure/study_wallet_repository.py` `charge` (unique `run_id`, no release) at #544's
head (`253a0330`). Plan `lead-orchestration`, Findings F-LO1-1.

**Reproduction.** Charge run A at USD 5, retry it as run B and charge B: USD 10 held for one run's
work.

**Consequence.** A few retries exhaust the wallet (once LO3/LO5 call it; the wallet is off by
default, `AIA_STUDY_WALLET_ENABLED`).

**Smallest fix.** LO3's step-retry rule says whether a retry's charge replaces the original's,
decided with the release question in ADR 0028.

**Test.** A retried plan step's wallet holds one ceiling, not two.

**Status.** Open (`lead-orchestration` LO3). *Linked (2026-10-22):* the stage's analysis retry
(`POST …/analysis/retry`) and the typed "Zopakuj analýzu" (#744, merged as `ec6c6bc8`) charge the
wallet nothing today, by the product manager's decision (b)
(`packages/aia_core/src/aia_core/application/lead_chat_start.py:28-31 @ 6bfe3760`). When this item
is decided, both change together, in one PR.

---

## OI-171 · Finding · The wallet is not bounded by what the budget has left

**Claim.** `effective_cap` takes `budget_usd`, not its remainder after spend and open reservations.

**Anchor.** `domain/wallet.py` `effective_cap` at #544's head (`253a0330`). Plan `lead-orchestration`,
Findings F-LO1-2.

**Reproduction.** Budget USD 10, wallet USD 10, a person-started run spends USD 9: the wallet still
shows USD 10 remaining.

**Consequence.** Display only, since the budget's reservation still stops the spend; a plan step would
start and then park `AWAITING_BUDGET` rather than be stopped at start.

**Smallest fix.** Bound remaining by the budget's remainder when LO4 shows the meters.

**Test.** The wallet's remaining never exceeds the budget's.

**Status.** Open (`lead-orchestration` LO4).

---

## OI-172 · Finding · The wallet migration's downgrade drops a client's wallet ceiling

**Claim.** The downgrade refuses while a raise or a charge is stored, but drops
`clients.wallet_ceiling_usd` an OWNER or ADMIN set.

**Anchor.** `migrations/versions/20261021_60ccc9ff42cf_the_study_wallet_its_raises_and_charges.py` `downgrade` at #544's head (`253a0330`).
Plan `lead-orchestration`, Findings F-LO1-3.

**Reproduction.** Set a ceiling on a client, then `alembic downgrade -1`: the column and its value are
gone.

**Consequence.** None yet: nothing sets the column until K11.

**Smallest fix.** Refuse the downgrade while any ceiling is non-null, when K11 ships its setter.

**Test.** The downgrade refuses with a ceiling set.

**Status.** Open (`client-knowledge-lifecycle` K11).

---

## OI-173 · Finding, closed · The Lead's greeting made a new study's first save stale

**Claim.** On a study with no working copy, the greeting's `post` saved the bare template as working
revision 1 behind the browser, which had loaded the study EMPTY, so the person's first save (base
`null`) was refused `stale_revision`.

**Anchor.** `LeadPane.tsx:178`, `research_lead.py:427, 561, 811`, `store.ts:233`,
`study_workspace_repository.py:268 @ 962652b1`. Plan `research-lead-workbench`, Findings F3.

**Reproduction.** `pytest apps/api/tests/test_research_lead_api.py -k new_study` (both fail on
`962652b1`); in a browser, the workbench with a hatched Lead, a new study, two sentences in Zadání:
"Uloženo jinde · změny zde neuloženy".

**Consequence.** The person's first words were not saved, and "Načíst znovu" would have dropped them;
an automatic accept of the greeting's text edits was refused too.

**Smallest fix.** Done: `domain/workspace.py` `edited_from_current` (a copy naming no revision was
edited from the current one while that is still the bare template with no analysis), asked by the save
and by the Lead's accept; `post` names the template revision it froze the turn from.

**Test.** `test_a_greeting_on_a_new_study_does_not_make_the_persons_first_save_stale`,
`test_a_first_save_is_not_stale_over_the_bare_template_a_server_writer_saved`,
`test_edited_from_current_names_the_current_revision_or_the_bare_template`.

**Status.** Closed by #546 (merged as `722dd75`, 2026-10-21).

---

## OI-174 · Finding, closed · A Lead turn parked on the study's budget held the conversation for ever

**Claim.** A message sent with no study budget parked its turn in `AWAITING_BUDGET`, the parked turn
counted as busy, and nothing ever released it, so every later message queued behind it.

**Anchor.** `_holds` (`research_lead.py:224-232`), `lead_busy` (`:420-423`), `LeadPane.tsx:48, 193`,
`workflow_repository.py:2211-2213 @ 095a3e68`. Plan `research-lead-workbench`, Findings F4.

**Reproduction.** `test_setting_the_study_budget_sends_the_message_that_waited_for_it`
(`apps/api/tests/test_research_lead_api.py`) against `095a3e68`.

**Consequence.** The chat stayed stuck after the budget was set, and the pane said "Vedoucí se
zastavil (budget_exceeded)."

**Smallest fix.** Done, on the owner's Q39 (2026-10-21, 11:41 UTC: no "Pokračovat" button; "once the
budget is set or raised, it should automatically resend the message the researcher attempted to send
in the first place"): a parked turn holds nothing; `PUT /studies/{id}/budget` runs
`release_lead_budget_waits`, lifting each parked turn whose recorded hold now fits through
`resume_budget_waits`, one ledger row under the person who set the budget; a message written before
then replaces the parked turn; `leadReasonWords` says what happens.

**Test.** `test_setting_the_budget_sends_the_parked_message_and_records_the_person`,
`test_a_budget_still_too_small_leaves_the_turn_parked`,
`test_a_parked_turn_whose_hold_is_unknown_stays_parked`
(`test_research_lead_application.py`).

**Status.** Closed by #547 (merged as `a89e912`, 2026-10-21).

---

## OI-175 · Finding, closed · No web path turns a Design Research proposal into a Design Revision

**Claim.** The API's Design Research proposal accept exists, but the web only reads the proposal.

**Anchor.** `apps/api/src/aia_api/routers/deep_research.py:768-796`,
`application/design_research.py:90-157`; the web's one reference is the GET at
`apps/web/src/lib/api.ts:1412 @ 095a3e68`. Plan `research-lead-workbench`, Findings F-DRL-1.

**Reproduction.** `git grep -n 'design-proposal' 095a3e68 -- apps/web/src` lists api.ts:1412 and a
test's GET stub alone.

**Consequence.** ADR 0021's checkpoint 1 (human-reviewed proposals → a new Design Revision) cannot be
completed in the product.

**Smallest fix.** `research-lead-workbench` 7b (Design Research proposal review).

**Test.** 7b's Vitest that the review posts the ticked `item_ids` with both expected revisions, and its
journey step.

**Status.** Closed by #554 (merged as `bef820b`, 2026-10-21): `DesignResearchReview.tsx` on Dotazník posts the ticked items to `POST …/design-proposal/accept`, then reloads the working copy; tests `lib/design-research-review.test.ts`, `DesignResearchReview.test.tsx`.

---

## OI-176 · Finding, closed · A Deep Research ceiling is never computed unless the study has a threshold

**Claim.** A Deep Research start computes its cost ceiling only when the study's confirmation
threshold is set.

**Anchor.** `packages/aia_core/src/aia_core/application/deep_research.py:635-655 @ 095a3e68`. Plan
`deep-research-web-search`, chunk 55, Findings F-DRL-2.

**Reproduction.** Start a run on a study with `spend_confirm_usd = null`: the run's metadata has no
`cost_ceiling_usd`, and no route returns one.

**Consequence.** OI-139 again, for Deep Research: a card cannot show "až X USD", and the wallet
(charged at the ceiling) has nothing to charge.

**Smallest fix.** Chunk 55: always computed, and a read-only quote.

**Test.** A create with no threshold stores `cost_ceiling_usd`, and the quote equals it.

**Status.** Closed by #555 (merged as `7275fcc`, 2026-10-21): every new run stores `cost_ceiling_usd`, threshold or not, and `POST …/deep-research/quote` reads the same admission (`DeepResearchRuns._admit`).

---

## OI-177 · Finding, closed · A Deep Research ceiling is priced from the API's own environment copy

**Claim.** The prices a Deep Research ceiling is computed from are read in the API router alone.

**Anchor.** `apps/api/src/aia_api/routers/deep_research.py:261-387 @ 095a3e68`. Plan
`deep-research-web-search`, chunk 55, Findings F-DRL-3 (I22).

**Reproduction.** `git grep -n "def deep_research_prices" 095a3e68` finds it only in the router.

**Consequence.** A plan step in the worker cannot price a run the way the API does.

**Smallest fix.** Chunk 55: one pricing function both processes call.

**Test.** Chunk 55's key-combination fixture.

**Status.** Closed by #555 (merged as `7275fcc`, 2026-10-21): `application/deep_research_pricing.py` `DeepResearchPricingSettings`, built by each composition root.

---

## OI-178 · Finding · The Lead cannot see a Deep Research run

**Claim.** The Lead's frozen context lists only research runs, so a Design or Interpretation Research
run never reaches it.

**Anchor.** `application/research_lead.py:858-866 @ 095a3e68` (runs with `workflow_type=RESEARCH`, at
most five). Plan `lead-orchestration`, Findings F-DRL-4.

**Reproduction.** Start a Design Research run, post a Lead turn, read the turn's frozen context: no
Deep Research run is in it.

**Consequence.** "Kde jsme?" omits a running or finished rešerše, and the Lead may prepare a
duplicate.

**Smallest fix.** LO5a.1's `deep_research` context layer.

**Test.** LO5a.1's "a Deep Research run appears in the context".

**Status.** Open (`lead-orchestration` LO5a.1).

---

## OI-179 · Finding · The Interpretation Research target is fixed in the browser

**Claim.** The web always sends `ANALYSIS_MODULE` `research_questions` as the Interpretation target.

**Anchor.** `apps/web/src/lib/api.ts:1380-1385 @ 095a3e68`. Plan `lead-orchestration`, Findings
F-DRL-5.

**Reproduction.** `git show 095a3e68:apps/web/src/lib/api.ts | sed -n 1380,1385p`.

**Consequence.** Six of ADR 0021's seven target kinds have no way in from the product, although
`POST …/runs/interpretation` accepts them.

**Smallest fix.** LO5a.1's code-built candidates, every result kind (Q44).

**Test.** An LO5a.2 approval over a battery-object candidate starts a run whose target is that object.

**Status.** Open (`lead-orchestration` LO5a.1).

---

## OI-180 · Finding, closed · The UI workbench cannot run Deep Research at all

**Claim.** The workbench composition has no Deep Research runtime, so a run parks at plan.

**Anchor.** `apps/executors/src/aia_executors/workbench.py:158-173 @ 095a3e68`. Plan
`research-lead-workbench`, Findings F-DRL-6.

**Reproduction.** `make ui-workbench`, `make ui-fixtures`, then start Design Research on a fixture
study: the run waits at plan.

**Consequence.** No browser journey can prove D-12's acceptance with zero paid calls.

**Smallest fix.** `research-lead-workbench` 12a: recorded web retrieval in the workbench.

**Test.** 12a's "a run on the fixture completes with a sealed bundle marked `RECORDED_FIXTURE`".

**Status.** Closed by #578 (merged as `b7f6363`, 2026-10-21): `research-lead-workbench` 12a; `deep_research_journey.mjs` completes a Design Research run on recorded web, 20 ledger rows on `workbench-scripted`, 0 priced. The interpretation exchange on the workbench is not built (the PR's proposed `research-lead-workbench#12a.2`, not yet a chunk line).

---

## OI-181 · Finding, closed · AIA_DEEP_RESEARCH_LEAD reads as the Research Lead

**Claim.** `AIA_DEEP_RESEARCH_LEAD` / `settings.deep_research_lead` is the Deep Research engine's lead
researcher mode, not the Research Lead (Vedoucí výzkumu), and nothing said so.

**Anchor.** `apps/api/src/aia_api/config.py:182 @ 095a3e68`. Plan `deep-research-web-search`,
Findings F-DRL-7.

**Reproduction.** `git grep -n deep_research_lead 095a3e68 -- apps/api`.

**Consequence.** A reader or an agent can take one for the other.

**Smallest fix.** Done in this docs PR: one line in `docs/architecture/deep-research.md`; the plans say
"the engine's lead mode".

**Test.** None; a wording defect.

**Status.** Closed (this docs PR).

---

## OI-182 · Finding, closed · Two flushes waiting behind one save sent the same base revision

**Claim.** `ResearchStore.flush` let every caller waiting behind an in-flight save resume together,
each building its body from the same `state.revision`, so the second was refused `stale_revision`;
and a flush saved only the snapshot it took, so an edit typed during the flight stayed pending after
it resolved.

**Anchor.** `apps/web/src/research/store.ts:225-233 @ 054cf007` (`if (this.inflight) await
this.inflight;`, then `base_revision: s.revision` with no re-check). Plan `research-lead-workbench`,
Findings F-STORE-1.

**Reproduction.** The three store tests below fail on `722dd75c`; a scratch Vitest on `054cf007`
sent bases `[3, 4, 4]`.

**Consequence.** After a fast edit, a false "Uloženo jinde" conflict whose only way on is a reload
that drops the edit; and a caller that took one flush to mean "saved" (an accept, a job start) acted
on a revision without the person's last edit.

**Smallest fix.** Done: saves serialised; `flush` waits for whichever save is in flight, reads the
copy again and saves what is still owed from the revision the previous save returned, at most
`MAX_FLUSH_ROUNDS` (4) saves, then `FlushIncomplete` with the change kept pending.

**Test.** `store.test.ts`: "serialises the saves of callers waiting behind one: each names the
revision the one before returned", "saves an edit made during the flight in the same flush, which
resolves only once it is saved", "says when the copy kept changing through every round, and keeps
the change waiting for its save".

**Status.** Closed by #556 (merged as `b3b5581`, 2026-10-21).

---

## OI-183 · Finding, closed · An identifier's digits ground a number the Lead invents

**Claim.** The Lead's number guard reads digits inside identifiers in its context as numbers, so a
number the Lead made up passes unrepaired whenever an id in the context happens to start with its
digits.

**Anchor.** `packages/aia_core/src/aia_core/domain/project.py:80` (`"REV-" + uuid4().hex[:16]`),
frozen into the Lead's design layer at `application/research_lead.py:1112`; `_NUMBER`
(`domain/research_lead.py:334`) starts a number after a hyphen and ends it at the first non-digit,
so `REV-7a…` reads as 7; `lead_contract` (`:368`) allows every number in the prompt and the message
(`:860`) @ `c98836c`. Plan `research-lead-workbench`, Findings F-CLOCK-1 (on #557's branch).

**Reproduction.** `apps/executors/tests/test_research_lead_executor.py::test_a_reply_that_stays_invented_after_its_repair_fails_the_turn`
failed in CI on #554 (run 39604369392, `1 == 2` at line 338); #557's
`test_a_number_only_an_identifier_holds_is_still_invented` pins every revision id to start `7a` and
fails the same way on `c98836c`. About one revision id in forty starts with 7 then a letter.

**Consequence.** A number the Lead invented reaches the researcher as if grounded; and the test above
fails about 2.5 % of runs, which reads as a flake.

**Smallest fix.** #557: `context_identifiers` (the values under `id`, `*_id`, `*_ids`, `*_version`
and focus targets, a bare-number id skipped), blanked in the allowed text and the reply before
numbers are read.

**Test.** #557's `test_a_number_only_an_identifier_holds_is_still_invented`,
`test_an_identifiers_digits_ground_no_number`, `test_the_context_names_its_identifiers`,
`test_a_request_holds_a_reply_to_the_context_without_its_identifiers`.

**Status.** Closed by #557 (merged as `bcb2911e`, 2026-10-21): `context_identifiers`
(`domain/research_lead.py:428 @ bfe6d15b`) blanks every identifier before numbers are read, on the
allowed side (`:963`) and in the reply alike.

---

## OI-184 · Finding · A tracked set labelled point by point is told the wrong ends

**Claim.** `SpecBattery.told_ends`, from `_develop_ends`, returns a set's first two labels, so a set
labelled on every point tells respondents and the map legend that its top end is the second point.

**Anchor.** `packages/aia_core/src/aia_core/domain/research_design.py:535` (`_develop_ends`), read
at `:363` (`told_ends`), sent at `domain/ai_respondent.py:611-614` and printed at
`domain/research_sociomapping.py:206 @ c98836c` (first recorded `@ 25f26232`, #559).

**Reproduction.** `pytest packages/aia_core/tests/test_ai_respondent.py::test_on_a_set_is_read_by_the_new_rule`:
a set labelled `bod 1` … `bod 10` reads `told_ends == ("bod 1", "bod 2")`.

**Consequence.** With the labels off the prompt, respondents read "1 = bod 1, 10 = bod 2" and the map
legend prints the same, for any set labelled point by point. Today the editor keeps sets to two ends
(input-interactions 3b2), so no screen writes such a set yet.

**Smallest fix.** Read a valid per-point list as its first and last label in `_develop_ends`.

**Test.** A compile of a set labelled on every point whose `told_ends` is `("bod 1", "bod 10")`, and a
respondent request reading "10 = bod 10".

**Status.** Open (for input-interactions 3b3 or a server fix).

---

## OI-185 · Finding, closed · The client journey's bulk filing check passed without filing anything

**Claim.** The journey's "the ticked item is moved into the folder" check matched the item's own
title, so it passed whether or not the item was filed.

**Anchor.** `tools/ui_workbench/client_journey.mjs:136 @ 25f26232` (`row.getByText(names.folder)`,
where the item's title `Cesta ${stamp}: pobočky` contains the folder's `Cesta ${stamp}` and
`getByText` matches a substring). Plan `input-interactions`, Findings CJ-1.

**Reproduction.** Remove the bulk "Přesunout do složky" step from the journey @ `25f26232` and run
it: the check at line 136 resolves at once, on the title.

**Consequence.** The browser evidence for bulk filing proved nothing; a broken bulk move would have
shipped green.

**Smallest fix.** Done: `{ exact: true }` on the folder and label checks.

**Test.** The journey itself: a substring match now fails in strict mode (two elements).

**Status.** Closed by #569 (merged as `ec75af1`, 2026-10-21).

---

## OI-186 · Finding · Dotazník's outline covers half the screen when it wraps under the editor

**Claim.** The questionnaire outline is `sticky` at every width, so wrapped under the editor it covers
about half the viewport at 390 px and in the workbench at 1100 px, Závislosti included.

**Anchor.** `apps/web/src/components/rehome/research/QuestionnaireStep.tsx:560 @ c98836c`
(`className="sticky top-[136px] …"`; recorded at `:545 @ 25f26232`). Plan `artifact-questionnaire`,
Finding QF-1.

**Reproduction.** `node tools/ui_workbench/questionnaire_journey.mjs` (#572): its
`390-dependencies-section.png`.

**Consequence.** On a phone, or the workbench at its narrowest split, half the questionnaire is
hidden under the outline.

**Smallest fix.** Sticky only while it sits beside the editor (a container query).

**Test.** A journey assertion that the dependencies section is not covered at 390 px.

**Status.** Open (`artifact-questionnaire`).

---

## OI-187 · Finding, closed · Every Lead turn of a client with DATASET, ARTIFACT or FINDING knowledge was refused

**Claim.** A Lead turn over a client with any approved DATASET, ARTIFACT or FINDING knowledge item
declares the lineage `unclassified-client-knowledge`, which no licence determination named, so every
turn parked `licence_dataset_unknown`.

**Anchor.** `packages/aia_core/src/aia_core/domain/research_lead.py:835-838 @ 871c62c5`, with no
determination in `domain/licence_determinations.py @ 871c62c5`; the refusal at
`domain/licence.py:158-164`. PR #564, Finding 1.

**Reproduction.** `pytest apps/executors/tests/test_research_lead_executor.py::test_a_dataset_in_the_client_knowledge_reaches_the_eu_bedrock_route`
on `871c62c5`: 0 requests sent.

**Consequence.** No Lead for that client (and, OI-142, no AI design job).

**Smallest fix.** Done: the product owner's determination as data owner (2026-10-21, /pmstatus Q60
(a)): `CLIENT_KNOWLEDGE_DATASET` APPROVED for `bedrock-eu-primary` alone; every other route still
refuses `not_approved_for_route`.

**Test.** `test_a_dataset_in_the_client_knowledge_reaches_the_eu_bedrock_route`;
`packages/aia_core/tests/test_research_lead.py::test_a_turn_over_dataset_derived_knowledge_passes_the_licence_gate_on_eu_bedrock_only`.

**Status.** Closed by #582 (merged as `7cd7acd`, 2026-10-21). Per-item recorded lineage stays OI-142
(#537).

---

## OI-188 · Finding, closed · No report kept its document model

**Claim.** The worker composed every report as a `ReportDocument`, rendered it to DOCX and dropped
the document, so only DOCX bytes said what a report held.

**Anchor.** `apps/executors/src/aia_executors/report.py:121-167 @ e09a6c99` (`101-146 @ 25f26232`);
`.planning/evidence/editor-spike-2026-10-21.md` § F-ED3.

**Reproduction.** `git show 25f26232:apps/executors/src/aia_executors/report.py | sed -n 101,146p`:
only the DOCX is stored.

**Consequence.** The Zpráva pane's claim chips, tracked changes, the sentence-level claim check and
the Lead's report edits had no paragraph to name and no ledger to resolve against (`report-delivery`
RD5-RD7).

**Smallest fix.** Done (`report-delivery` RD5a): `domain/report/document_model.py`
(`aia-report-document-1`), stored as `research_internal_document` beside the internal DOCX and
`research_client_document` beside the client report's, read by `GET …/report/document` and
`GET …/report/client/document`.

**Test.** `packages/aia_core/tests/test_report_document_model.py`
(`test_every_section_and_block_has_a_unique_positional_id`, `test_every_cited_ref_resolves_in_the_ledger`,
`test_the_ledger_prints_what_the_docx_prints`).

**Status.** Closed by #584 (merged as `9f99c78`, 2026-10-21), for the internal draft and the client
report; the report with literature is retired for new reports by Q58.

---

## OI-189 · Finding, closed · A renamed folder or label lost focus on a busy runner

**Claim.** Renaming a folder or label scheduled the row's focus on the next animation frame, which
could run before React mounted the row, so focus fell to the page and never came back.

**Anchor.** `apps/web/src/components/aia/clients/KnowledgeOrganizers.tsx:98-101 @ a15c9917` (#569,
merged as `ec75af1`): `setRenaming(false)` then `requestAnimationFrame(() => row.current?.focus())`.

**Reproduction.** `apps/web/src/components/aia/clients/KnowledgeLibrary.test.tsx:366` ("The row is
back, under its new name, and focus with it") failed in the Frontend job of #563 (job 119340985792),
#586 (job 119341510278) and #585 with `document.activeElement` `<body>`; with every frame callback run
at once it fails on the old hook every run.

**Consequence.** After a rename, a keyboard user's focus jumps to the page; and an unrelated PR's CI
went red.

**Smallest fix.** Done: `stop` marks a refocus owed, and an effect keyed on `renaming` focuses the row
after the render that mounted it (`KnowledgeOrganizers.tsx:91-110 @ c98836c`).

**Test.** The same `KnowledgeLibrary.test.tsx` test, now running every `requestAnimationFrame`
callback at once, so the losing order is pinned.

**Status.** Closed by #596 (merged as `233881c`, 2026-10-21). Develop's own CI did not report it,
because its runs were cancelled (OI-191).

---

## OI-190 · Finding, closed · Výsledky's "Kish n" column shows the donor-adjusted n

**Claim.** The rated-set table's column labelled Kish n reads `result.effective_n`, the
donor-adjusted combined support size, instead of Kish's effective n, which the aggregate stores as
`effective_n_kish`.

**Anchor.** `apps/web/src/lib/result-reading.ts:130 @ c98836c`
(`const effectiveN = finite(result.effective_n) ? result.effective_n : null;`); Codex review on #566
at the same line @ `72e3b27b`.

**Reproduction.** A fixture aggregate where the two differ (125.0 against 401.8) shows 125 under
"Kish n".

**Consequence.** The evidence size printed beside each mean on Výsledky is the wrong one, smaller by
up to a factor of three where respondents share donors.

**Smallest fix.** Read `effective_n_kish`, and show "—" when it is not stored, never 0.

**Test.** A `result-reading.test.ts` case with 401.8 against 125.0 that expects 401 in the column.

**Status.** Closed by #611 (merged as `dffd36fc`, 2026-10-21): the column reads `kishN` from
`effective_n_kish` (`apps/web/src/lib/result-reading.ts:135 @ bfe6d15b`), null when not stored;
`result-reading.test.ts` expects 401.8 where `effective_n` is 125.0.

---

## OI-191 · Finding, closed · Back-to-back merges cancelled develop's CI for almost six hours

**Claim.** `ci.yml` cancels an in-progress run when a newer one starts on the same ref, develop push
runs included, so with merges every few minutes no develop run completed and nothing was deployed.

**Anchor.** `.github/workflows/ci.yml:17-19 @ c98836c` (`concurrency: group: ci-${{ github.ref }}`,
`cancel-in-progress: true`); deploy-develop is dispatched only after CI succeeds
(`ci.yml:7-9`).

**Reproduction.** `gh api "repos/AiAnalytics-AIA/AIA/actions/runs?branch=develop&event=push&created=2026-10-21&per_page=100"`:
63 CI push runs on 2026-10-21 (to 20:22 UTC), 57 cancelled, 5 succeeded, 1 in progress. The last to
complete was `25f26232` (finished 14:32 UTC); the next 37 (`871c62c5` at 14:41 to `13c36ea9` at 20:07)
were all cancelled, about 5 h 40 min with no completed develop run.

**Consequence.** Develop was neither verified nor deployed for that stretch, across 37 pushes (merges) to
it; a failure that only develop's merged state shows (OI-189) went unreported there, and the
deployed site lagged every merge of the afternoon.

**Smallest fix.** Keep cancelling superseded pull-request runs, never develop's or main's push runs:
`cancel-in-progress: ${{ github.event_name == 'pull_request' }}` in `ci.yml`'s `concurrency` block.
GitHub then lets the running develop run finish and keeps only the newest pending one, so a develop
run completes at least once per run time. Batching merges is the no-code alternative.

**Test.** A CI-contract test that reads `ci.yml` and asserts `cancel-in-progress` is false for a push
to `develop` and `main`; and, after the change, the same listing showing completed develop runs on a
busy day.

**Status.** Closed by #620 (merged as `9d1e7e04`, 2026-10-21): `cancel-in-progress` is true only for
`pull_request` runs, so a develop or main push run is never cancelled by a newer one.

---

## OI-192 · Finding · The draft report's Segments chapter loses its only producer when the refusal lands first

**Claim.** `evidence-integrity#9b` refuses report composition while any analysis module has no
supported finding, and the Segments module (report chapter ch-5) has no admitted producer until
`segment-maps-and-drilldown#10` (segment evidence) lands; built in the other order, no run reaches a
draft. The same census found the coded open answers' chapter (`ch-coding`) belongs right after
ch-questions, and the assumptions chapter (`ch-assumptions`) right before ch-6.

**Anchor.** `.planning/plans/evidence-integrity.md` chunk 9b and
`.planning/plans/segment-maps-and-drilldown.md` chunk 10 @ c98836c; the execution contracts had 10
before 9b but not before `artifact-chain-to-draft-report#CHN10`.

**Reproduction.** Hypothesis until 9b is built: a fictional run with a segment question, after 9b
and before 10, is refused at composition with the Segments module named.

**Consequence.** Every draft report would be refused.

**Smallest fix.** The order recorded in the contracts and in both plans: 10 before 9b and CHN10.

**Test.** The chain's acceptance (`artifact-chain-to-draft-report#CHN11`) on a run with segments.

**Status.** Open: recorded as an ordering in this PR (the coordinator's census finding PM-2,
2026-10-21); closes when 10 lands before 9b.

---

## OI-193 · Hypothesis · Per-researcher spend counts any settled hold without a ledger row as tool spend

**Claim.** "Spend outside the ledger" on the per-researcher report is every settled hold that no
usage-ledger row names; today that is exactly the priced tool calls, but a model hold settled
without its ledger row would be counted there too, as tool spend.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/researcher_spend_repository.py:121-123 @ bfe6d15b`
(`in_ledger = exists().where(AIUsageEventRow.reservation_id == BudgetReservationRow.reservation_id)`),
folded by `domain/spend_attribution.py` `researcher_spend` (`:254`). Plan `develop-spend-attribution`,
Findings (chunk 7) F-SA7-1, #583 (merged as `e78dfa8b`).

**Reproduction.** Hypothesis: no path today settles a model hold without writing its ledger row; a
test would settle a `budget_reservations` model hold with no `ai_usage_events` row and read it under
"mimo ledger". `test_the_fold_separates_model_tool_reserved_and_uncertain` covers only the intended
split.

**Consequence.** If it ever happens, a model call's cost is shown as tool spend, never lost: the
person's total stays right, its parts do not.

**Smallest fix.** `deep-research#4` gives tool calls their own ledger and
`develop-spend-attribution#5b` reads tool spend from it, so "outside the ledger" is no longer
inferred from an absence.

**Test.** After #4, a hold with neither a usage row nor a tool-ledger row read as unknown, never as
tool spend.

**Status.** Open: closes with `deep-research#4` and `develop-spend-attribution#5b`.

---

## OI-194 · Question, closed · Who pays for the holds after a budget lift

**Claim.** `charged_to` books every hold a run makes after a budget lift to the person who lifted
it, not the run's starter; Q40 said only "whoever approves or starts", so the rule was a reading.

**Anchor.** `packages/aia_core/src/aia_core/domain/spend_attribution.py:74-86 @ bfe6d15b` (rule 1,
`if lift_approver: return lift_approver`); plan `develop-spend-attribution`, Findings (chunk 7)
F-SA7-2, #583 (merged as `e78dfa8b`).

**Reproduction.** `packages/aia_core/tests/test_spend_attribution.py::test_a_budget_lift_books_the_holds_after_it_to_the_lifter`.

**Consequence.** A researcher who lifts a colleague's run's budget sees the rest of that run's spend
under their own name on "Útrata podle výzkumníka".

**Smallest fix.** None needed: the product owner answered Q67 (a) on 2026-10-21, 20:12, "Whoever
lifts the budget pays for what runs after the lift" (`mvp-owner-decisions.md`). Had the answer been
the starter, the change was rule 1's removal and its test.

**Test.** The reproduction above.

**Status.** Closed: decided by the owner (Q67 (a)) and built in #583.

---

## OI-195 · Finding · The internal draft's cover, and the client report, still do not say what the person asked for

**Claim.** The brief's title does not reach the internal draft's cover or introduction, and the client
report's design chapter carries neither the brief's goal nor its decision use; only the internal draft's
design chapter (and the report with literature's) now opens with them.

**Anchor.** `apps/executors/src/aia_executors/report.py:89 @ 6bfe3760` (`study_name=study.name`),
printed at `packages/aia_core/src/aia_core/application/report.py:208`; the client report calls
`compose_design_sections(sources.specification, sources.research_questions)` with no `brief`
(`application/client_report.py:178 @ 6bfe3760`; `report_design.py:143-151` takes one). Plan
`research-lead-workbench.md` F19 (from #778's `acceptance_journey.mjs`), with `artifact-report.md`
§ Findings F19 (first recorded @ `e508e483`).

**Reproduction.** `node tools/ui_workbench/acceptance_journey.mjs` on a fresh workbench: the draft's
cover reads "Workbench · empty" although the brief's title is "Akceptace · ranní nápoj pro
dojíždějící (fiktivní)".

**Consequence.** A person reads a report named by the study record; a client reads no statement of the
decision the study serves.

**Smallest fix.** A product call, not a code gap: #792's review kept the cover on the study record
(a brief's title is the template's "Nový výzkum" until edited, and a reused design carries the earlier
study's) and left the client report unchanged (its internal-marker scan would refuse a person's own
brief words). Either decide both stay, and close this, or take the design's title when it was edited
and pass the client report a brief its marker scan reads.

**Test.** A report composed from a revision with an edited title prints it on the cover; a client
report from a revision with a goal prints it under the design chapter.

**Status.** Open, partly closed by #792 (merged as `f188646a`, 2026-10-22): the design chapter opens
with "Cíl studie" and "Rozhodnutí, které má výzkum podpořit", an empty one "V zadání neuvedeno."
(`application/report_design.py:4-10,131 @ 6bfe3760`;
`test_report_design.py::test_the_chapter_opens_with_what_the_brief_asked_for_before_how_it_was_measured`).
The plan entry at `research-lead-workbench.md:1761 @ 6bfe3760` still reads "open" whole.

---

## OI-196 · Finding, closed · Five workbench tests waited 4 s for a Lead turn the pane polls every 1.5 s

**Claim.** `Workbench.layout.test.tsx` overrode the suite's 10 s wait (OI-134) with `{ timeout: 4000 }`
in five places, each waiting for a turn that arrives only after LeadPane's 1.5 s poll.

**Anchor.** `apps/web/src/components/workbench/Workbench.layout.test.tsx:258, 382, 394, 420, 686 @ eb0c7d47`;
`LeadPane.tsx:27` (`POLL_MS`). Plan `research-lead-workbench.md` F20.

**Reproduction.** With three busy loops on CPU 0, `taskset -c 0 npx vitest run
src/components/workbench/Workbench.layout.test.tsx -t "leaves nothing pending"` failed after 5.5 s.

**Consequence.** A red web suite on a loaded runner, unrelated to the change under test.

**Smallest fix.** Done: the five overrides removed.

**Test.** The reproduction above passes; the file passes (38).

**Status.** Closed by #793 (merged as `111b3e01`, 2026-10-22).

---

## OI-197 · Finding, closed · "leaves nothing pending" took its guard off before the Lead's move was tried

**Claim.** The test removed its leave guard as soon as the turn's chip appeared; when the passive
effect that runs the turn's view had not run yet, `cleanup()` flushed it after the guard was gone.

**Anchor.** `apps/web/src/components/workbench/Workbench.layout.test.tsx:407-424 @ eb0c7d47`;
`LeadPane.tsx:166`. Plan `research-lead-workbench.md` F21.

**Reproduction.** About one run in ten of the file on the earlier version failed at `:424`
("expected <aside …> to be null") after 2.2 s, with no load.

**Consequence.** A red web suite now and then.

**Smallest fix.** Done: the test waits until its guard has stopped the move (`stopped === 1`).

**Test.** The same file, run repeatedly, never fails at `:424`.

**Status.** Closed by #793 (merged as `111b3e01`, 2026-10-22).

---

## OI-198 · Finding, closed · Every fresh page mounted the classic layout and then the workbench

**Claim.** `useWorkbenchSwitch` read `false` until `/config` answered, so a stage rendered the classic
layout first, then the workbench, which read everything again.

**Anchor.** `apps/web/src/components/rehome/research/ResearchScreen.tsx:237-238 @ 9607ee09`. Plan
`research-lead-workbench.md` F22.

**Reproduction.** `ResearchScreen.workbench.test.tsx` "mounts a stage once on a fresh page, not the
classic layout first and then the workbench" (two `/design/source` reads before the fix); one Dimenze
visit on the UI workbench made 44 API requests.

**Consequence.** Twice the reads on every stage a person opens fresh, and both layouts' effects.

**Smallest fix.** Done: the switch is `null` until read, and the stage shows its chrome with the
loading line meanwhile.

**Test.** The test above; the same visit now makes 36 requests.

**Status.** Closed by #807 (merged as `a201e951`, 2026-10-22).

---

## OI-199 · Finding · Návrh's follow-up answers saved twice put the same block in the brief twice

**Claim.** `answerFollowUps` appends a "Doplnění k analýze" block to `briefing.what_is_known` on every
save, and the form clears afterwards, so the same answers can be saved again.

**Anchor.** `apps/web/src/research/plan.ts:189-194 @ 6bfe3760` (first recorded `:189 @ 491024f1`).
Plan `artifact-design.md` F-DSN-3 (#796).

**Reproduction.** Answer a follow-up, "Uložit odpovědi", type the same answer, save again:
`what_is_known` holds the block twice.

**Consequence.** A duplicated block in the brief the Lead and the analysis read; a reworded answer sits
beside the old one.

**Smallest fix.** `answerFollowUps` replaces its own earlier block instead of appending, recorded as a
parity deviation (a product call; parity kept for now, the coordinator 2026-10-22).

**Test.** `plan.test.ts`: the same answers applied twice leave one block.

**Status.** Open (`artifact-design`).

---

## OI-200 · Hypothesis · A script on docs.<hostname> could plant a session cookie AIA's pages read

**Claim.** `docs.<hostname>` is a subdomain of the product hostname, so script running there can set
`aia_session` with `Domain=<product hostname>`; AIA's own cookie is host-only but has no `__Host-`
prefix to refuse such a planted twin.

**Anchor.** `apps/api/src/aia_api/routers/session.py:68 @ 6bfe3760` (`SESSION_COOKIE = "aia_session"`),
set at `:171`; recorded `@ 8b51875b`. Plan `report-editor-hosting.md` F1 (#785).

**Reproduction.** A hypothesis until shown: it needs script execution on `docs.<hostname>`, i.e. a
defect in ONLYOFFICE.

**Consequence.** A person could be working in AIA as somebody else (login CSRF); never another
organization's data read unseen.

**Smallest fix.** The session cookie as `__Host-aia_session` in deployed environments (Secure, Path=/,
no Domain), read by the gate and the session routes.

**Test.** The gate refuses a request whose only session cookie is the unprefixed name, in production
settings.

**Status.** Closed 2026-10-25 by #831 (was: Open; it gated `report-editor-hosting` chunk 4, activation on develop, whose precondition
was this fix).
**2026-10-25:** closed by #831 (merged as `ca14a942`, 2026-10-23): the cookie is `__Host-aia_session` deployed (`apps/api/src/aia_api/routers/session.py:73 @ 5d5ed250`), read by `_session_credential` (`:131`) and `session_cookie` (`:120`), and a name sent twice is no session. Tests: `apps/api/tests/test_session_api.py::test_a_deployed_gate_reads_only_the_host_prefixed_cookie`, `::test_a_session_cookie_sent_twice_is_no_session`. `report-editor-hosting` chunk 4's precondition (F1) is met.

---

## OI-201 · Question · Dotazník in the workbench shows its own "Spustit veřejný výzkum"

**Claim.** In the workbench, a stage shows no AI start of its own (#550) and the Lead's contract lists
`design_research` among Dotazník's starts, yet Dotazník renders `DeepResearchPanel` with its own start.

**Anchor.** `apps/web/src/components/rehome/research/QuestionnaireStep.tsx:352-359 @ 6bfe3760`
(`<DeepResearchPanel />`, no `leadOwnsAiStarts` guard); `packages/aia_core/src/aia_core/domain/lead_artifacts.py:284`.
Plan `artifact-questionnaire.md` QF-13 (#797).

**Reproduction.** Open Dotazník in the workbench (`AIA_WEB_RESEARCH_WORKBENCH=true`): "Před uzavřením
dotazníku" offers the start.

**Consequence.** The one AI start a workbench stage still owns; hiding it today leaves no way to run
Design Research, since no typed command or Lead card starts it yet.

**Smallest fix.** #808 ("Leave Design Research to the Lead on Dotazník in the workbench"), once the
Lead can start Design Research.

**Test.** A `QuestionnaireStep` workbench test that finds no start of its own.

**Status.** Open: #797's Doc follow-up said "closed by #808", but #808 is not merged @ `6bfe3760`.

---

## OI-202 · Finding, closed · Two owners of "the client version" could approve a version nobody read

**Claim.** With the report card and the Zpráva pane each holding a client version, synced by events,
the card could approve a version the person had not read (a stale pinned draft after a toggle, a
missed one-shot event, a version leaking across runs, a pane never showing an approval).

**Anchor.** Branch `fix/report-client-pinned-read` (`df1fb276`, `0bb8ebbe`, pushed, never merged).
Plan `artifact-report.md` F-RPT-1.

**Reproduction.** Two `/code-review high` passes on that branch.

**Consequence.** None on develop: the design was dropped before merge.

**Smallest fix.** Done: RPT3a, one owner of the version approved, the approval on the document being
read.

**Test.** RPT3a's "the version approved is the version shown" at every width.

**Status.** Closed by RPT3a: the client report in #741 (merged as `5e19ad00`), the internal draft in
#758 (`03989975`), the report with literature in #775 (`359dfd22`), all 2026-10-22.

---

## OI-203 · Finding · A PDF's table extraction inflates without a bound

**Claim.** `_pdf_tables` relies on pypdf's inflate bound, but pypdf truncates at 75 MB rather than
raising; pdfminer then inflates the same stream with no limit, and the 20 s deadline is checked only
between pages.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/document_text.py:306-330 @ 6bfe3760`
(the docstring's claim at `:311-312`, the deadline at `:328`); recorded at `:272-324 @ bfe6d15`. Plan
`security-audit-2026-10.md` S9.

**Reproduction.** A one-page PDF whose content stream is FlateDecode of 3 MB of `0 0 m\n` takes 8.8 s
in `read_pdf`; a 291 KB file inflating to 200 MB was still running at 300 s and 1.5 GB in the audit. A
test still has to be written.

**Consequence.** One small source upload ties up the API's CPU and memory; the same for a Deep
Research web PDF in the worker.

**Smallest fix.** Table extraction in a subprocess with a memory rlimit and a wall-clock kill; or bound
pdfminer's `zlib.decompress` and skip tables on any page whose stream reached pypdf's limit.

**Test.** `read_pdf` on such a file returns within a fixed bound, with no tables and
`tables_truncated`.

**Status.** Open (`security-audit-2026-10` chunk 9).

---

## OI-204 · Hypothesis · DOCX table cells repeat by gridSpan and vMerge without a bound

**Claim.** python-docx's `row.cells` yields a cell once per spanned grid column, and a
`vMerge="continue"` cell yields the text of the cell above, so text multiplies by span × rows.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/source_reading.py:132-142 @ 6bfe3760`
(`for cell in row.cells` at `:139`); recorded at `:122-126 @ bfe6d15`. Plan
`security-audit-2026-10.md` S10.

**Reproduction.** Hypothesis-strength until a test exists: in the audit a 36 KB DOCX with
`gridSpan w:val="30000000"` ran for more than 2 minutes and used 300 MB.

**Consequence.** API memory or CPU exhaustion from one upload.

**Smallest fix.** Read `tr.tc_lst` directly, one segment cell per `w:tc`, with a text budget per
document, as a new reader name, since merged cells then read differently.

**Test.** A DOCX with `gridSpan=30000000` is refused or read within the bound in under a second.

**Status.** Open (`security-audit-2026-10` chunk 10).

---

## OI-205 · Finding · AIA_MAX_REQUEST_BYTES is shown as the request ceiling, and nothing enforces it

**Claim.** `max_request_bytes` is read only by the settings document.

**Anchor.** `apps/api/src/aia_api/config.py:234 @ 6bfe3760` and `routers/settings.py:171-172`; no
other reader in `apps/api/src`. Plan `security-audit-2026-10.md` S12.

**Reproduction.** `grep -rn max_request_bytes apps/api/src`; POST a 3 MB JSON body to any JSON route:
it is parsed, not refused with 413.

**Consequence.** An operator reads a guard that does not exist; Caddy's 40 MiB body bound (S7, #706)
is the only one.

**Smallest fix.** An ASGI middleware refusing on Content-Length and on the streamed count, at
`max_request_bytes` by default and at each upload route's own ceiling, after measuring the largest
working-content save; or remove the setting from Settings.

**Test.** A 3 MB body to a JSON route is 413, and a 25 MiB source upload still passes.

**Status.** Open (`security-audit-2026-10` chunk 12).

---

## OI-206 · Hypothesis · A web fetch has no overall deadline

**Claim.** `UrllibWire.get` sets only a connect (8 s) and a per-read (20 s) timeout, and its read loop
has no deadline of its own.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/web_retrieval_live.py:128-170 @ 6bfe3760`
(the timeout at `:150`, the loop at `:163-167`). Plan `security-audit-2026-10.md` S13.

**Reproduction.** Hypothesis: a server that sends one byte every 19 s would hold the fetch, and its
host's pacing turn, up to the 20 MB cap.

**Consequence.** One hostile site in the search results stalls a Deep Research step.

**Smallest fix.** An overall deadline in the read loop, after which the fetch raises
`ToolCallFailed(reason="timeout")`.

**Test.** A stub wire that trickles bytes is cut at the deadline.

**Status.** Open (`security-audit-2026-10` chunk 13).
**Closed 2026-10-26 by #999** (merged as `6850ff6c`): one 120 s deadline per fetch, with a watchdog from the TLS
handshake on (`infrastructure/web_retrieval_live.py:126-149 @ 6850ff6c`, `deadline_s`). DNS resolution stays outside the
deadline. The Brave wire is a new item (S13b, below).

---

## OI-207 · Finding · deactivate_user deactivates an account of another organization

**Claim.** `deactivate_user` finds the user by id across every organization; a user with no membership
in the admin's organization passes the owner guard and has the global `is_active` flag cleared. Latent:
no route calls it.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/scope_repository.py:376-403 @ 6bfe3760`
(`select(UserRow).where(UserRow.user_id == user_id)`, then `_guard_owner(…, previous=None, …)`, which
returns at `:349-350`). Plan `security-audit-2026-10.md` S15.

**Reproduction.** A repository test as organization A's admin deactivating organization B's member
succeeds.

**Consequence.** None until a route exposes it; then any admin could lock out any account in every
organization.

**Smallest fix.** Require a membership in `admin.organization_id`, and decide whether deactivation is
per membership or per account.

**Test.** Organization A's admin deactivating organization B's member is `ScopeDenied`.

**Status.** Closed 2026-10-25 by #830 (was: Open, `security-audit-2026-10` chunk 15).
**2026-10-25:** closed by #830 (merged as `32475bdc`, 2026-10-23), S15 fixed: the target is resolved through the acting admin's organization (`packages/aia_core/src/aia_core/infrastructure/scope_repository.py:412` `deactivate_user`, `:445` `_member_row` @ `5d5ed250`), and deactivation is per membership. Test: `packages/aia_core/tests/test_member_deactivation.py::test_an_admin_cannot_deactivate_a_user_of_another_organization`.

---

## OI-208 · Question · Cognito verify does not require email_verified

**Claim.** The Cognito provider takes the token's `email` claim without checking `email_verified`, and
a sign-in binds to a pre-provisioned user by e-mail.

**Anchor.** `apps/api/src/aia_api/identity/cognito.py:280 @ 6bfe3760` (`email=(claims.get("email") or
None)`); `verify` at `:222`. Plan `security-audit-2026-10.md` S16 (chunk 16, hardening, low).

**Reproduction.** `grep -n email_verified apps/api/src/aia_api/identity/cognito.py` finds nothing.

**Consequence.** Low: whether an unverified address can reach the pool depends on the federated pool's
attribute mapping, which is to be checked first.

**Smallest fix.** Check that the Google Workspace federation maps `email_verified`; then require it.

**Test.** A token with `email_verified: false` is refused.

**Status.** Open (`security-audit-2026-10` chunk 16).

---

## OI-209 · Finding · The product hostname sends no Content-Security-Policy

**Claim.** The product site's header block sets HSTS, nosniff, frame and referrer policies but no
Content-Security-Policy, while the id and refresh tokens sit in sessionStorage.

**Anchor.** `deploy/develop/Caddyfile:39-46 @ 6bfe3760` (only `docs.` sets a CSP, `frame-ancestors`, at
`:147`); `apps/web/src/lib/auth.ts:96,118`. Plan `security-audit-2026-10.md` S17.

**Reproduction.** `curl -sI https://aia-develop.art-chain.io/app/clients | grep -i content-security`
prints nothing.

**Consequence.** Low: any script injection would read the tokens with nothing limiting where it sends
them.

**Smallest fix.** A CSP on the product hostname (`script-src 'self'` with Next.js's needs measured,
`connect-src` to the API and the error reporter).

**Test.** `tools/caddy_routes.py` asserts the header on the product hostname.

**Status.** Open (`security-audit-2026-10` chunk 16).
**2026-10-25:** #875 (merged as `0d2c07a4`) re-found this from the report editor's side: the product's pages send no CSP, so there is no policy for the editor's origin to join (`deploy/develop/Caddyfile:45-52 @ 5d5ed250`, still none; only `docs.` sets one, at `:160`). Filed here, not again. The editor's own script gate is OI-234.

---

## OI-210 · Finding · The worker's log fields are written unredacted

**Claim.** The worker's JSON formatter redacts the message and the exception but merges a record's
`fields` as given; the API's formatter redacts them.

**Anchor.** `apps/worker/src/aia_worker/observability.py:45-47 @ 6bfe3760`. Plan
`security-audit-2026-10.md` S18.

**Reproduction.** A record logged with `extra={"fields": {"api_key": "sk-ant-api03-…"}}` through
`_JsonFormatter` prints the key as given (a unit test to write; the code path is the three lines
above).

**Consequence.** Low: a secret passed as a structured field reaches the worker's log.

**Smallest fix.** Pass `fields` through the shared `redact` (`infrastructure/redaction.py`).

**Test.** That record's line holds `[redacted]`.

**Status.** Open (`security-audit-2026-10` chunk 16).

---

## OI-211 · Finding · Redaction misses credentials in a URL and AWS access key ids

**Claim.** The value patterns redact provider keys, bearer tokens, JWTs and `token=` assignments, but
not a URL's userinfo (`scheme://u:p@host`) or an AWS `AKIA…`/`ASIA…` key id, in the backend or the
browser.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/redaction.py:33-45 @ 6bfe3760`;
`apps/web/src/lib/error-tracking.ts:23-28`. Plan `security-audit-2026-10.md` S19.

**Reproduction.** Applying `_SECRET_VALUE_PATTERNS` to
`https://user:hunter2secret@example.com/x AKIAIOSFODNN7EXAMPLE` leaves it unchanged (checked
2026-10-22 with the patterns extracted from the file @ `6bfe3760`).

**Consequence.** Low: such a value in a message or error report is kept.

**Smallest fix.** Two patterns in both places: userinfo before `@` in a URL, and `(AKIA|ASIA)[A-Z0-9]{16}`.

**Test.** The string above redacts to `https://[redacted]@example.com/x [redacted]` in both suites.

**Status.** Open (`security-audit-2026-10` chunk 16).

---

## OI-212 · Finding · Workflow inputs are interpolated into run steps, and images and actions float

**Claim.** `${{ inputs.sha }}` and `${{ inputs.migrate }}` are interpolated into `run:` scripts;
third-party actions are pinned by tag, not SHA; `caddy:2-alpine` and `postgres:16-alpine` float.

**Anchor.** `.github/workflows/deploy-develop.yml:48-49 @ 6bfe3760`, `reference-unit.yml:44`;
`.github/workflows/ci.yml:51` (`actions/checkout@v4`) and the rest; `deploy/develop/docker-compose.yml:60,348`,
`deploy/develop/errors/docker-compose.yml:74`. Plan `security-audit-2026-10.md` S20.

**Reproduction.** `grep -n 'inputs\.' .github/workflows/deploy-develop.yml .github/workflows/reference-unit.yml`.

**Consequence.** Low: a dispatch input is shell text; a moved tag changes what runs.

**Smallest fix.** Pass inputs through `env:`; pin actions and images by digest.

**Test.** A CI-contract test that no `run:` block contains `${{ inputs.`.

**Status.** Open (`security-audit-2026-10` chunk 16).

---

## OI-213 · Finding · GlitchTip shares the product's internal network

**Claim.** GlitchTip joins `aia-develop_internal`, so it can reach PostgreSQL and the API directly.

**Anchor.** `deploy/develop/errors/docker-compose.yml:59 @ 6bfe3760` (`networks: [aia, errors]`),
`:94-98` (`aia` is `aia-develop_internal`). Plan `security-audit-2026-10.md` S21.

**Reproduction.** Read the compose file above.

**Consequence.** Low: a defect in GlitchTip reaches AIA's database network.

**Smallest fix.** A network GlitchTip shares only with Caddy, the API and the worker.

**Test.** `deploy/develop` config check that GlitchTip's networks exclude the database's.

**Status.** Open (`security-audit-2026-10` chunk 16).

---

## OI-214 · Follow-up · clear_subject has no route, and its route must settle two things

**Claim.** `ScopeRepository.clear_subject` (#704) has no route; the subject lives on the shared user
record, so clearing it in one organization changes the person's sign-in in every organization, and a
mismatched bearer token commits one `AIA_SESSION_DENIED` row per request.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/scope_repository.py:228 @ 6bfe3760`
(`clear_subject`); the audit row per request at `apps/api/src/aia_api/dependencies.py:345-346`. Plan
`security-audit-2026-10.md` S22.

**Reproduction.** A design follow-up: there is no defect to reproduce.

**Consequence.** A genuinely changed subject can be cleared only from code; repeated refused sign-ins
fill the audit.

**Smallest fix.** Decide whether clearing needs every organization's admin or an operator; deduplicate
or rate-limit the refused-sign-in rows; then the route.

**Test.** The route's tests for both decisions.

**Status.** Open (`security-audit-2026-10` chunk 17).

---

## OI-215 · Finding · Dependabot alerts describe a branch that does not deploy

**Claim.** GitHub's open Dependabot alerts (113 at the audit: 2 critical, 67 high) come from `main`'s
two npm lockfiles; `main` is far behind develop and nothing deploys it.

**Anchor.** `origin/main` @ `9cf1f585`, 3,455 commits behind `6bfe3760` and none ahead
(`gh api repos/AiAnalytics-AIA/AIA/compare/main...6bfe3760`, 2026-10-22; a shallow clone's
`git rev-list --count` undercounts); `ci.yml:1095-1098 @ 6bfe3760` (`dispatch-develop` only for
`refs/heads/develop`). Plan `security-audit-2026-10.md` S23.

**Reproduction.** `npm audit --package-lock-only` over `git show origin/main:apps/web/package-lock.json`
and `:package-lock.json`: 81 + 32 advisories at the audit.

**Consequence.** The alert count is noise for what ships, and an advisory against develop's own
lockfiles would sit among the stale ones. `prototypes/research-lead-v2`'s lockfile is not audited.

**Smallest fix.** The product owner's call: develop as the default branch, or a release to `main`; the
prototype's lockfile audited by the gate or excluded by name.

**Test.** The audit gate run over every lockfile in the repository, or a named exclusion list.

**Status.** Open (`security-audit-2026-10` chunk 18).

---

## OI-216 · Finding · The Lead's notes past the newest 40 or 16 KB leave its context uncounted

**Claim.** `notes_layer` stops silently at 40 notes or 16 KB, and the context records no omitted count,
so neither the turn nor its manifest says how many notes were left out.

**Anchor.** `packages/aia_core/src/aia_core/domain/research_lead.py:887-900 @ 6bfe3760`
(`NOTES_IN_CONTEXT`, `NOTES_MAX_BYTES` at `:196-197`); recorded at `:733-746 @ bfe6d15`. Plan
`lead-conversation.md` F4 (#699).

**Reproduction.** `notes_layer` over 41 notes returns 40 and nothing else.

**Consequence.** A researcher with many notes has some silently missing from the Lead's context; LC1's
manifest names the bound in words but cannot count what was left.

**Smallest fix.** LC4: the layer carries its omitted count once its bytes may change.

**Test.** A context over 41 notes records one omitted note.

**Status.** Open (`lead-conversation` LC4).

---

## OI-217 · Finding · Some warnings fixed on Spuštění itself send "Opravit →" away from it

**Claim.** A `dimensions` warning when fictional respondents will not use the dimensions, an
`audience` warning when no filters apply, and an unknown `support_forecast` on a panel run are fixed by
"Kdo bude odpovídat" on Spuštění, but share their ids with checks fixed elsewhere, so the fix link
leaves the page.

**Anchor.** `apps/web/src/components/rehome/research/ExecutionSteps.tsx:414-427 @ 6bfe3760` (`FIX_STEP`),
`apps/web/src/lib/sample-view.ts:91-95` (`checkStage`); the checks at
`packages/aia_core/src/aia_core/domain/research_design.py:1540-1585` and `domain/support_forecast.py`.
Plan `artifact-fieldwork.md` F-FLD-2 (#662).

**Reproduction.** Readiness without `filters_applied` and with dimensions selected: "Opravit →" opens
Dimenze.

**Consequence.** The real fix is on the page the person just left.

**Smallest fix.** The domain's `ReadinessCheck` names the stage that fixes it, and the web reads it,
replacing `FIX_STEP` and `checkStage`.

**Test.** One shared case file of check, status and stage, read by both suites.

**Status.** Open (`artifact-fieldwork`).

---

## OI-218 · Finding · An older method's run is told how to use a map it does not draw

**Claim.** The Sociomapa card prints `mapToolNotInAia` ("Mapu můžete prohlížet shora nebo jako 3D
terén, otáčet…") above every battery, also when every battery is an older method's with no `-5` map.

**Anchor.** `apps/web/src/components/rehome/research/ExecutionSteps.tsx:1672 @ 6bfe3760` (the hint),
`:2260` (`olderMethodOnly`); recorded at `:1666 @ 9607ee09`. Plan `artifact-sociomap.md` § Findings
(SOC2, #803).

**Reproduction.** `node tools/ui_workbench/sociomap_journey.mjs` (after `--prepare`), then
`tmp/ui-workbench/sociomap-journey/390-older-method.png`.

**Consequence.** A person on such a run reads how to turn a map that is not there.

**Smallest fix.** Print the hint only when some battery draws a map (`!olderMethodOnly(b)` for one).

**Test.** The `ExecutionSteps.test.tsx` older-method case expects no `mapToolNotInAia`.

**Status.** Open (`artifact-sociomap` SOC2; `ExecutionSteps` is Výsledky's).
**2026-10-25:** fixed on the workbench's Sociomapa stage by #815 (merged as `a25d2435`): the stage prints no map hint above an older method's notice (`ExecutionSteps.test.tsx` › "says a set stored under an older method draws no map, with no map hint above the notice"). Still open on Výsledky's Sociomapy tab, which prints `mapToolNotInAia` above that notice (`apps/web/src/components/rehome/research/ExecutionSteps.tsx:1702 @ 5d5ed250`): Výsledky's to fix.

---

## OI-219 · Finding · A respondent's detail on the map is reached only by a click on the canvas

**Claim.** On Respondenti the "Respondent" card fills only from a canvas hit; no control opens it from
the keyboard.

**Anchor.** `apps/web/src/components/rehome/research/ObjectMapPanel.tsx:262 @ 6bfe3760` (`setPerson`
only in `onUp`'s hit test); recorded `@ 03989975`. Plan `artifact-sociomap.md` § Findings (#770).

**Reproduction.** On a `-5` run, Respondenti, Tab through the panel: no stop opens a respondent's card.

**Consequence.** A keyboard or screen-reader user reads the counts and segments but no single
respondent's placement.

**Smallest fix.** A way to reach a respondent without the pointer (a list or a "next respondent"
control): a layout decision inside the panel, the methodology owner's.

**Test.** A test that Tabs on Respondenti and expects a control naming a respondent.

**Status.** Open, for the methodology owner.

---

## OI-220 · Question · The map's legend and tool column cover the map on a phone

**Claim.** At 390 px the `-5` panel's legend card (260 px, bottom-left) covers the lower third of the
map, and the tool column (top-right) covers object labels near the right edge.

**Anchor.** `apps/web/src/components/rehome/research/ObjectMapPanel.tsx` (the panel's layout, header
comment at `:5 @ 6bfe3760`). Plan `artifact-sociomap.md` § Findings ("For the methodology owner").

**Reproduction.** `node tools/ui_workbench/sociomap_journey.mjs` at 390 px (the browser audit of
2026-10-21; "Borealis" covered).

**Consequence.** Part of the map and its labels are unreadable on a phone.

**Smallest fix.** The methodology owner's: the panel's layout is theirs (Q50).

**Test.** A journey check that no object label sits under the legend or tool column at 390 px.

**Status.** Closed 2026-10-25 by SOC13, #815 (was: Open, for the methodology owner).
**2026-10-25:** closed by SOC13 (#815, merged as `a25d2435`, 2026-10-23): at 390 px the legend is a chip until opened, and the view controls moved to a rail bottom right, off the labels (`artifact-sociomap.md:242-243`). Labels near the edge passing under the bar or the chip stay open as OI-240.

---

## OI-221 · Question · The Lead's labels and hide_weak map filters have no control on the -5 panel

**Claim.** The registry's `labels` and `hide_weak` Sociomap filters have no control on the `-5` panel,
and `view: top|relief` is the panel's camera, not a toggle, so a Lead `filter` on them has nothing to
set.

**Anchor.** `apps/web/src/lib/workbench-artifacts.ts:166 @ 6bfe3760`
(`sociomap: ["view", "labels", "hide_weak", "mode", "battery"]`); `lib/artifacts/sociomap.ts:85`. Plan
`artifact-sociomap.md` SOC3 (#625).

**Reproduction.** A Lead turn with `filter` `hide_weak` on the `-5` map is refused by name (SOC2's
wiring), never applied.

**Consequence.** Two filters the Lead's contract names cannot act on the map people read.

**Smallest fix.** The methodology owner decides whether the panel offers them; otherwise drop them
from `VIEW_FILTERS.sociomap` and the server's contract together.

**Test.** `lead_artifacts` contract fixture and the panel agree on the filters offered.

**Status.** Open, for the methodology owner.

---

## OI-222 · Question · AiaMark is rendered by no page

**Claim.** `apps/web/src/components/brand/AiaMark.tsx` is rendered by no page; only `AiaMark.test.tsx`,
which pins its geometry to `public/skin/brand/aia-mark.svg`, holds it.

**Anchor.** `apps/web/src/components/brand/AiaMark.tsx @ 6bfe3760`; `login-handoff.md:89 @ 9607ee09`.
Plan `code-health-2026-10.md` § Findings (#805).

**Reproduction.** `grep -rln AiaMark apps/web/src` lists only the component and its test.

**Consequence.** Dead code the knip check allows only because a test names it.

**Smallest fix.** Remove both (one file plus its test), on the PM's word.

**Test.** `make web_unused` stays green after the removal.

**Status.** Open, for the PM.
**Closed 2026-10-26 by #995** (merged as `646780a3`): AiaMark and its test are removed; `src/components/brand/` holds
Wordmark alone of the identity. `.planning/plans/login-handoff.md:89`'s mention is marked removed.

---

## OI-223 · Hypothesis · Remove buttons under 24 px at a phone's width on Zadání and Návrh

**Claim.** The browser audit of 2026-10-22 measured remove buttons under WCAG 2.5.8's 24 px at 390 px:
Zadání "Odebrat pole …" 16×20, Návrh "Odebrat …" 12×20 (also Dotazník's option × 20×20 and the audience
filter's 15×16, since fixed by #703 and #717).

**Anchor.** Recorded `@ bfe6d15b`; each lives in its stage's own component. Plan
`research-lead-workbench.md` § The workbench frame audit, H1 (#647).

**Reproduction.** Hypothesis: the audit script was not committed; not re-measured @ `6bfe3760`.

**Consequence.** Small targets on a phone.

**Smallest fix.** `size-6` (or `TOUCH`) on each remaining remove button.

**Test.** A journey assertion that every "Odebrat" control is at least 24 × 24 at four widths, as
`workbench_journey.mjs` does for the audience filter.

**Status.** Open, for the stages' owners.

---

## OI-224 · Hypothesis · GET …/design/source is read again on every stage mount

**Claim.** `DesignSourceNote` reads the study's design source on every mount, and a 404 ("not reused")
is logged by the browser each time; a per-study cache would read it once.

**Anchor.** `apps/web/src/components/rehome/research/DesignSourceNote.tsx:21-26 @ 6bfe3760`. Plan
`research-lead-workbench.md` H3 (#647).

**Reproduction.** Measured by #807 (OI-198): one Dimenze visit on `next dev` reads `/design/source`
twice after that fix (four before).

**Consequence.** Repeated requests and console 404s; no wrong state.

**Smallest fix.** Cache the answer per study for the page's life.

**Test.** One `/design/source` read across two stage mounts of one study.

**Status.** Open.

---

## OI-225 · Hypothesis · Výsledky's standalone links are not touch targets

**Claim.** After F-FLD-5 (#677), Výsledky's own standalone links still carry no `TOUCH` class: the
report's "see progress" and the stale analysis's repair link, and the blocked claims' link.

**Anchor.** `apps/web/src/components/rehome/research/ExecutionSteps.tsx:1821, 1897 @ 6bfe3760`
(`inline-block underline`), `:1635`; `AnalysisBlocked.tsx:67`. Plan `artifact-fieldwork.md` F-FLD-5
("Left: Výsledky's own standalone links").

**Reproduction.** Hypothesis: not measured; F-FLD-5 measured the same class of link at 18-20 px.

**Consequence.** Small targets on a phone.

**Smallest fix.** `TOUCH_LINK` (`components/ui/parts.tsx:58`) on each.

**Test.** `results_journey.mjs` asserting every standalone link is a touch target at four widths.

**Status.** Open, for Výsledky's owner.

---

## OI-226 · Finding · A develop CI run takes an hour and a half, so most merges are never verified on their own

**Claim.** Develop's push runs are serialised (OI-191: a running one is never cancelled, GitHub keeps one
pending and supersedes the rest), and one run now takes about 1 h 30 min, so on a busy merge day develop
is verified and deployed at most about once per 1.5 h and most merges' own runs are cancelled while
pending.

**Anchor.** `.github/workflows/ci.yml:17-23 @ 6bfe3760` (`concurrency`, `cancel-in-progress` only for a
pull request); `:266-275` ("Domain tests on SQLite", push only, re-running the whole suite after the
PostgreSQL steps in the same Backend job; its comment still says "about 3.7 of this job's 11.6
minutes").

**Reproduction.** `gh api repos/AiAnalytics-AIA/AIA/actions/runs/39825786647/jobs` (#793's merge,
`111b3e01`, success): created 17:47:44, done 19:17:44 UTC; Backend 17:50:05-19:16:04 (1 h 26 min);
"Domain and repository tests (PostgreSQL)" 12.5 min, "API tests (PostgreSQL)" 19 min, executors 15 min,
"Domain tests on SQLite" 18:40:29-19:15:59 (35.5 min, the largest step); Frontend 4 min. Runs 39808787084
(#787) and 39795265033 (#776) took 1 h 58 and 1 h 44 including queue.
`gh api "repos/AiAnalytics-AIA/AIA/actions/workflows/ci.yml/runs?branch=develop&event=push&created=2026-10-22&per_page=100"`:
182 develop push runs that day; of the newest 100, 92 cancelled, 5 succeeded, 2 failed, 1 in progress.

**Consequence.** A defect only develop's merged state shows is reported up to an hour and a half
later, against a batch of merges rather than one; the deployed site lags every merge by as much.

**Smallest fix.** A proposal, not decided: run the SQLite domain suite in its own job, parallel to the
Backend job (the deploy dispatch still needing both), or only on a schedule.

**Test.** The same listing on a busy day shows develop runs completing within the Backend job's
PostgreSQL time (about 50 min).

**Status.** Open.

---

## OI-227 · Finding, closed · A control character a person typed failed the whole draft

**Claim.** A research question, a question's wording or a study's name holding a character XML 1.0
cannot hold reached python-docx as written, and lxml refused the run: no draft at all.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/report_docx/renderer.py:53 @ 09571504`.
Plan `artifact-report.md` F-RPT-2 (found by #792's stand-in review).

**Reproduction.** `packages/aia_core/tests/test_report_design.py::test_a_control_character_a_person_typed_never_fails_the_render`
(fails before the fix).

**Consequence.** One pasted vertical tab or bell character stopped the report.

**Smallest fix.** Done: `domain/report/printable.py` (`xml_text`, `printable`), applied by
`DocxRenderer.render` and by the document model before it is stored.

**Test.** The reproduction above; `test_report_printable.py`.

**Status.** Closed by #810 (merged as `6bfe3760`, 2026-10-22).

---

## OI-228 · Finding, closed · A deploy of a SHA older than #785 failed before reaching the host

**Claim.** `deploy-develop.yml` runs from develop's head but checks out the SHA it deploys, and its
bundle step named `deploy/develop/docs` unconditionally, which a SHA before #785 lacks.

**Anchor.** `.github/workflows/deploy-develop.yml:165-170 @ 07b2fa31`. Plan `report-editor-hosting.md` F2.

**Reproduction.** Deploy run 39811181434 (`inputs.sha` `013f2e11`) failed with
`cp: cannot stat 'deploy/develop/docs'`.

**Consequence.** A rollback or re-dispatch of an older SHA could not deploy; the site stayed on the SHA
it ran.

**Smallest fix.** Done: the bundle carries `errors/` and `docs/` only where they exist
(`deploy-develop.yml:162-170 @ 6bfe3760`).

**Test.** CI's "The deploy bundle of an older SHA" step (`ci.yml:963 @ 6bfe3760`), run on `013f2e11` and
on the current tree.

**Status.** Closed by #794 (merged as `1838330a`, 2026-10-22).

---

## OI-229 · Finding, closed · An ADMIN could promote anyone to OWNER and demote every OWNER

**Claim.** `add_member` overwrote an existing membership's role after `require_administer()` alone,
with no "only an OWNER sets OWNER" rule and no last-owner guard.

**Anchor.** `apps/api/src/aia_api/routers/scope.py:598-626` and
`infrastructure/scope_repository.py:208-250 @ bfe6d15`. Plan `security-audit-2026-10.md` S14.

**Reproduction.** `POST /api/v1/members {"email": "<owner>", "role": "MEMBER"}` as an ADMIN demoted the
owner.

**Consequence.** An admin could lock the owner out, with one audit row as the record.

**Smallest fix.** Done, on the product owner's option (b) of 2026-10-22: only an OWNER grants or
removes OWNER, and the last active OWNER is never demoted or deactivated, the organization row locked
while it counts (`scope_repository.py:343-375 @ 6bfe3760`, `_guard_owner`); a refusal is audited
`MEMBER_ROLE_DENIED`.

**Test.** `packages/aia_core/tests/test_scope_isolation.py::test_an_admin_neither_grants_nor_removes_owner`,
`test_owner_role_race.py::test_two_owners_demoting_each_other_at_once_leave_one`.

**Status.** Closed by #782 (merged as `b6cd4d9e`, 2026-10-22); the plan's S14 entry and chunk 14 are marked
fixed in the same docs PR.

---

## OI-230 · Finding, closed · XLSX entities expanded through openpyxl

**Claim.** defusedxml is not a dependency, so openpyxl's parser expanded internal entities in a
workbook's parts.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/document_text.py:107,409 @ bfe6d15`
(`load_workbook`). Plan `security-audit-2026-10.md` S11.

**Reproduction.** In the audit, a sheet with `&a0;` × 200,000 produced a 70 MB cell value from about
1 MB of XML.

**Consequence.** Memory exhaustion in the API (sources, attachments) and in the worker (web XLSX).

**Smallest fix.** Done: every workbook member passes `refuse_dtd` before `load_workbook`
(`document_text.py:124-143, 469-472 @ 6bfe3760`), so no entity reaches openpyxl.

**Test.** `packages/aia_core/tests/test_source_readers.py::test_a_workbook_part_declaring_a_dtd_is_refused_before_openpyxl_parses_it`,
`test_questionnaire_import.py::test_a_workbook_part_declaring_a_dtd_is_not_parsed`.

**Status.** Closed by #709 (merged as `dc6da479`, 2026-10-22).

---

## OI-231 · Finding, closed · A panel run whose sample the sampler refuses read ready and started

**Claim.** A refused panel draw was named in `sample_composition.refused` but was no readiness check:
readiness read ready, and a start created the run, which fieldwork then failed on the same refusal.

**Anchor.** `packages/aia_core/src/aia_core/application/research.py:696-758 @ 4568badd` (the draw came
after the `DesignNotReady` check). Plan `run-qc-and-checkpoint.md` F-RQC6-1.

**Reproduction.** A panel design whose filter the population cannot apply (`fiktivni_pole`) read
`ready: true` and `POST …/research/runs` answered 201.

**Consequence.** A run created only to fail in fieldwork.

**Smallest fix.** Done: `domain/panel_source.py:110 @ 6bfe3760` `with_panel_refusal`, a FAIL
`panel_sample` check from the one draw, added by readiness and by start (`application/research.py:759-760`);
a population that will not load stays unknown.

**Test.** `apps/api/tests/test_population_double_api.py::test_a_sample_the_sampler_refuses_fails_readiness_and_refuses_the_start`.

**Status.** Closed by #745 (merged as `c7fbd15a`, 2026-10-22).

---

## OI-232 · Finding · Deleting a client frees its respondent system's once-per-organization holdout confirmation

**Claim.** `erase_client_holdouts` deletes the deleted client's `holdout_confirmations` rows, the only
thing holding `holdout_confirmation_once_per_system`, so another study of the organization may then
start a second confirmation of the same respondent system.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/holdout_repository.py:264-272 @ 5d5ed250`
(the delete), called from `packages/aia_core/src/aia_core/application/client_deletion.py:194`; the
constraint `infrastructure/tables.py:1064-1096` (`holdout_confirmation_once_per_system` at `:1095`); the
refusals it feeds, `holdout_repository.py:217-221` and `application/validation.py:181-185`. Plan
`study-deletion.md` Finding F1 (recorded `@ f7762d72`), on the owner's review page as REV-SD-F1-NOW.

**Reproduction.** Run 2026-10-25 on SQLite with the real table and helper (plan F1, item 3): a
confirmation of fingerprint X for client A; a second for client B is refused; after
`erase_client_holdouts(session, client_id="client-a")` the second is accepted (`before delete: second
confirmation refused (once per system)` / `after client-a deleted: second confirmation ACCEPTED`). Not yet
a committed test.

**Consequence.** A failed holdout confirmation can be erased by deleting its client and run again until
one passes; a passing confirmation is what lifts a modelled number's `INTERNAL_ONLY`
(`domain/evidence/validation.py:151` `lifts_internal_only`), so evidence could reach a client report on a
validation that was chosen, not preregistered.

**Smallest fix.** Keep the confirmation row (content-free: fingerprint, sha, run id, who, when) under the
tombstone and erase only the preregistration's content; drop its foreign key to the preregistration, or
keep the preregistration row content-free.

**Test.** `test_client_deletion.py::test_a_deleted_clients_confirmation_still_holds_its_system`: delete a
client whose validation study started a confirmation; a second study's start of the same fingerprint is
refused `holdout_system_confirmation_started`.

**Status.** Open, 2026-10-25. Owner: `study-deletion` SD7 (with `settings-backends` SB5, which built the
client deletion). *2026-10-26: to be built now, as its own small fix PR ahead of the rest of
`study-deletion`* (REV-SD-F1-NOW (a), "Yes, a small fix PR now", the product owner in the Decision
Review, relayed by the PM coordinator; Q4 (a), "Keep it, without content"); SD7 is W1.
**Closed 2026-10-26 by #1012** (merged as `9d25112d`): `erase_client_holdouts` keeps the confirmation and blanks the
preregistration's content. Test: `packages/aia_core/tests/test_holdout_repository.py::test_a_deleted_clients_confirmation_still_holds_its_system`.
The study half waits for `study-deletion` (SD7).

---

## OI-233 · Finding · The report editor's edit hold fails open when the Document Server's clock runs ahead

**Claim.** The edit hold counts an edit as held when AIA received its report no later than the version's
`content_at`, the save's `lastsave` on the Document Server's clock capped at AIA's receipt; a Document
Server clock running ahead of AIA's by more than the gap between a save's last change and the next edit's
report lets that save hold the edit.

**Anchor.** `packages/aia_core/src/aia_core/domain/report/editor.py:152-171 @ 5d5ed250`
(`unsaved_edits`, the comparison at `:169`); `apps/api/src/aia_api/routers/report_editor.py:491-501`
(`_held_through`, the cap to receipt), applied at `:463`. Plan `artifact-report.md:576-583` (RPT8f, "Every
rule fails closed but one"); #880 (merged as `ee20550f`), #877's clock note (`fb949290`).

**Reproduction.** `apps/api/tests/test_report_editor_api.py::test_a_lastsave_ahead_of_aias_clock_counts_as_aias_receipt_and_never_holds_a_later_edit`
shows the cap (a `lastsave` five minutes ahead is kept as the receipt, and an edit reported after it is
held off); it does not close the window below the cap: a skew smaller than the time to receipt is kept as
sent.

**Consequence.** An edited report version approved without an edit the person typed just after its save.

**Smallest fix.** NTP time on both hosts, or a skew check: the Document Server's `Date` header on each
callback beside AIA's receipt, refusing a save beyond a bound. #877 named the bound it assumes: the two
clocks within 1 s.

**Test.** A callback dated ahead of AIA's receipt beyond the bound is refused, and stores no koncept.

**Status.** Open, 2026-10-25. Not reachable on develop: the Document Server and the API share one host,
and the editor is off (`AIA_ONLYOFFICE_URL` unset, `deploy/develop/docker-compose.yml:206`). A
prerequisite of moving the Document Server off the develop host, beside RPT8e (OI-234).

---

## OI-234 · Finding, closed · The report editor's api.js is loaded without Subresource Integrity

**Claim.** Zpráva loads the Document Server's `api.js` into AIA's own page from the origin the API names,
with no `integrity` attribute, so whatever that origin serves runs with the page's privileges.

**Anchor.** `apps/web/src/components/rehome/research/ReportEditor.tsx:50-62 @ 5d5ed250` (`loadDocsApi`:
`script.src = url`, no `integrity`); `apps/web/src/lib/report-editor.ts:42-52` (the URL, https origin
only). Plan `artifact-report.md:18` (RPT8e); #875 (merged as `0d2c07a4`).

**Reproduction.** `grep -n integrity apps/web/src/components/rehome/research/ReportEditor.tsx` prints
nothing.

**Consequence.** A defect or compromise on `docs.<hostname>` would run script in AIA's pages, where the id
and refresh tokens sit in sessionStorage (OI-35).

**Smallest fix.** RPT8e: the script loaded with SRI, its hash taken from the pinned Document Server
image's own `api.js` and configured beside `AIA_ONLYOFFICE_URL`, verified against the real Document Server
with CORS.

**Test.** A `ReportEditor` test that the script element carries the configured hash and
`crossorigin`, and that no hash configured loads no script.

**Status.** Closed 2026-10-25 by #895 (merged as `1fed2969`): `loadDocsApi(url, integrity)` loads api.js
only under the integrity the API names, with `crossorigin="use-credentials"`
(`apps/web/src/components/rehome/research/ReportEditor.tsx:57-63 @ 1fed2969`), and `report_editor_on`
requires `AIA_ONLYOFFICE_API_INTEGRITY` (`apps/api/src/aia_api/config.py:307-315`). The one check left is
activation's, against the real Document Server (`artifact-report.md`, RPT8e). The product CSP the editor's
origin would join is OI-209.

---

## OI-235 · Follow-up · A multi-tenant deployment needs an operator gate for Stav systému and error tracking

**Claim.** Smoke results and GlitchTip's issues belong to the whole deployment, so an organization's
OWNER or ADMIN reads them only while the deployment holds that one organization; with more, both routes
refuse 409 `deployment_shared`, and no operator gate exists to serve them.

**Anchor.** `packages/aia_core/src/aia_core/application/system_status.py:40-54 @ 5d5ed250`
(`_single_tenant`); `apps/api/src/aia_api/routers/system_status.py:11,43-47`. Plan `settings-backends.md`
SB4; #839 (merged as `f392c1e9`).

**Reproduction.** `apps/api/tests/test_system_status_api.py::test_with_a_second_organization_both_are_refused_as_the_deployments`.

**Consequence.** On a deployment with a second organization, Settings → Stav systému and the error card
say an operator reads them, and nobody in AIA can.

**Smallest fix.** An operator role apart from organization membership (as `AIA_POPULATION_OPERATORS` is
for the population), checked by both routes in place of the tenant count.

**Test.** With two organizations, an operator reads both routes and each organization's ADMIN is still
refused `deployment_shared`.

**Status.** Open, 2026-10-25. Develop holds one organization (the smoke seed not counted), so nothing is
refused there; needed before a deployment serves a second tenant.

---

## OI-236 · Question · The report's sentence-check word lists are provisional

**Claim.** The RD7 sentence check marks a comparison stated in words with no ledger number; which words
make a comparison is AIA's starting reading of Czech, PROVISIONAL until the methodology owner reviews it.

**Anchor.** `packages/aia_core/src/aia_core/domain/report/sentence_check.py:12,38 @ 5d5ed250` (the
PROVISIONAL marks); cases in `packages/aia_core/tests/fixtures/report_sentences/cases.json`. #884 (merged
as `156d339c`), `report-delivery` RD7.

**Reproduction.** `pytest packages/aia_core/tests/test_sentence_check.py`: the cases the lists decide.

**Consequence.** A sentence is marked `unsupported_comparison`, or left unmarked, by a list nobody
responsible for the methodology has read; it marks and never refuses (RD0's rule), so the cost is a wrong
warning or a missing one.

**Smallest fix.** The methodology owner reviews `COMPARISON_WORDS` and the exceptions; the fixture records
the answer.

**Test.** `cases.json` holds a case for each word the owner adds or removes.

**Status.** Open, 2026-10-25, for the methodology owner.

---

## OI-237 · Finding · The approval ledger's `map_snapshot` subject has no writer

**Claim.** `ApprovalSubject.MAP_SNAPSHOT` was admitted by LO16 for RD4, but RD4 approves a map snapshot as
an artifact (subject `artifact`), so nothing writes the subject.

**Anchor.** `packages/aia_core/src/aia_core/domain/approval_ledger.py:58,94,110 @ 5d5ed250`;
`application/map_snapshots.py` (the snapshot, approved as an artifact). Plan `report-delivery.md:184-185`
(Finding RD4a, for LO16); #886 (merged as `5f089474`).

**Reproduction.** `git grep -n "MAP_SNAPSHOT\b" origin/develop -- packages apps` lists only the
declaration in `approval_ledger.py`.

**Consequence.** A reader of the ledger looking for snapshot approvals under `map_snapshot` finds none;
they are under `artifact`. A dead value in a closed set.

**Smallest fix.** LO16's owner decides: drop the subject (a migration narrowing the check constraint), or
record it as reserved.

**Test.** A test that every `ApprovalSubject` has a writer or is listed as reserved.

**Status.** Open, 2026-10-25. Owner: `lead-orchestration` LO16 (`domain/approval_ledger.py` is LO16's, the
PM on #886).

---

## OI-238 · Hypothesis · A warm methodology comparison takes 8-9 s

**Claim.** With the numba kernels compiled, Metodika's "Porovnat s metodikou v platnosti" still takes
8-9 s: six `aia-sociomap-5` maps at about 1.4 s each, with the noise rule's 100 permutations and the
layout's restarts; unprofiled, so it may be what `-5` costs or a defect of its own.

**Anchor.** `packages/aia_core/src/aia_core/domain/methodology/sociomap_check.py:304 @ 5d5ed250`
(`compare_with_in_force`). Plan `settings-redesign.md:75`; #871 (merged as `effa698e`), which measured
8,116-9,173 ms over five warm runs.

**Reproduction.** A hypothesis until profiled; the timing is the settings journey's
(`tools/ui_workbench/settings_journey.mjs`, five runs on a warm cache, #871).

**Consequence.** An administrator waits about 10 s on each comparison; the editor says so after 10 s.

**Smallest fix.** Profile one comparison first; nothing is changed before that.

**Test.** A timing bound on one comparison of the three check panels, sized generously (§7), once the
profile says what it should be.

**Status.** Open, 2026-10-25 (a hypothesis).

---

## OI-239 · Question · The Sociomapa stage's method text is new wording

**Claim.** The Sociomapa stage's "Jak byla spočtena" and the gauges' sentences restate the signed-off
method in new plain-language words, and "± N %" reads `credibility.uncertainty_radius` as a share of the
typical distance between objects; the methodology owner has not confirmed either.

**Anchor.** `apps/web/src/i18n/cs.ts:3721 @ 5d5ed250` (`research.exec.mapStage`);
`apps/web/src/lib/map-explained.ts:89` (`uncertainty_radius`). Plan `artifact-sociomap.md:230-236`
(Findings, "For the methodology owner"); #815 (merged as `a25d2435`).

**Reproduction.** `node tools/ui_workbench/sociomap_journey.mjs` (after `--prepare`): the stage's text
under the `-5` map.

**Consequence.** A researcher reads the method in words its owner has not checked.

**Smallest fix.** The methodology owner reads and confirms or corrects the `mapStage` copy.

**Test.** None beyond the copy; the owner's answer is recorded in the plan.

**Status.** Open, 2026-10-25, for the methodology owner.

---

## OI-240 · Hypothesis · Object labels near the map's edge pass under the bar or the legend chip

**Claim.** `drawObjectMap` places object labels without insets, so a label near the map's edge can pass
under the overlay bar (top left) or the legend chip.

**Anchor.** `apps/web/src/lib/object-map-panel.ts:423 @ 5d5ed250` (`drawObjectMap`). Plan
`artifact-sociomap.md:244-246` (Findings, "Open"); #815 (merged as `a25d2435`, SOC13).

**Reproduction.** A hypothesis: no case is recorded; the plan names it from SOC13's layout.

**Consequence.** An object's name hidden on the map.

**Smallest fix.** An `insets` parameter to the map's projection (centre shifted, scale reduced).

**Test.** A label's box never meets the bar's or the legend chip's.

**Status.** Open, 2026-10-25 (`artifact-sociomap`).

---

## OI-241 · Finding · ADR 0026 promises `403 human_gate_required`, and no code raises it

**Claim.** ADR 0026 says a human-only command is refused `403 human_gate_required` unless a person's
request invokes it directly, but the code has no such refusal.

**Anchor.** `docs/architecture/adr/0026-research-lead-proposes-a-person-decides.md:177 @ 5d5ed250`; the
typed command registry is `packages/aia_core/src/aia_core/domain/lead_commands.py` (#574). Recorded as
MISSING in `.planning/evidence/mvp-master-traces/trace-4-lead-governance.md:102`.

**Reproduction.** `git grep -n human_gate_required origin/develop` lists only the ADR and the trace.

**Consequence.** The ADR is believed: a reader expects a refusal code no route sends. What holds today is
that a Lead turn only prepares a card, and a person approves it through `…/turns/{turn_id}/request` under
`APPROVE_GATE`; nothing names that as the ADR's gate.

**Smallest fix.** A decision first: amend ADR 0026 to name the mechanism that exists (a card a person
approves), or raise `human_gate_required` where a human-only command is reached without a person's
request.

**Test.** For each human-only command in the ADR's table, a test that a Lead turn alone cannot start it,
asserting the refusal the decision names.

**Status.** Open, 2026-10-25. Owner: `lead-orchestration` (the command registry; ADR 0026 decision 4).

---

## OI-242 · Finding, closed · A questionnaire file replaced the questionnaire with no way back

**Claim.** Loading a questionnaire file replaced every block, question and set already there, with no word
before and no way back.

**Anchor.** `QuestionnaireStep.tsx:456-458 @ 382b418a`. Plan `artifact-questionnaire.md` Finding QF-15
(browser audit 3, 2026-10-22).

**Reproduction.** On Dotazník with a questionnaire, load the template: it is gone.

**Consequence.** A person with a questionnaire who tried the template lost it on the first file.

**Smallest fix.** Done: the upload card says a file replaces the questionnaire there is, and an import over
one is offered back with Vrátit (input standard I6): the sections and the plan's status as they were.

**Test.** `QuestionnaireStep.test.tsx`.

**Status.** Closed by #826 (merged as `1fb7b176`, 2026-10-23).

---

## OI-243 · Finding, closed · A questionnaire file that failed to import was said in English

**Claim.** A questionnaire file that failed to import for any reason but the import's own rules was said in
the API's English ("The request body or parameters are invalid.", "Failed to fetch"); the template's
download too.

**Anchor.** `QuestionnaireStep.tsx:461,470 @ 82541803` (the raw `e.message`). Plan
`artifact-questionnaire.md` Finding QF-16 (audit 3, 2026-10-22).

**Reproduction.** Import an empty file on Dotazník.

**Consequence.** A Czech researcher read an English sentence that did not say what to do.

**Smallest fix.** Done: an empty or too large file is refused before it is sent; a 422 keeps its Czech
words, anything else is said in the Brief's upload words (`research/brief-upload.ts`).

**Test.** `QuestionnaireStep.test.tsx` "says an empty file, a refusal without words of its own and a lost
connection in Czech" and "says a template the API would not give in Czech".

**Status.** Closed by #833 (merged as `7294ceda`, 2026-10-23).

---

## OI-244 · Finding, closed · Every stage change drew the Lead's pane anew and read the whole study again

**Claim.** Each stage was the page of its own route segment, and Next.js remounts a page when its dynamic
segment changes, so the Lead's pane, its draft and scroll, and every study read were made again.

**Anchor.** `apps/web/src/components/aia/ResearchStudy.tsx:131-137 @ 82541803`. Plan
`research-lead-workbench.md:1839` (F23).

**Reproduction.** `apps/web/src/components/aia/ResearchStudy.stages.test.tsx` "keeps the Lead's pane, its
draft and the study's reads when the stage changes" fails with the screen keyed by its step; in a browser,
297-381 ms and 22-26 API reads per stage change.

**Consequence.** A lag and a flash of the conversation on every stage click.

**Smallest fix.** Done: the study's layout draws the stages (`ResearchStages`, `useSelectedLayoutSegment`,
`ResearchStudy.tsx:140 @ 5d5ed250`); the stage page only answers an unknown stage with 404.

**Test.** The reproduction above.

**Status.** Closed by #835 (merged as `8e4b0913`, 2026-10-23).

---

## OI-245 · Finding, closed · Two first reads of the client report could store two drafts

**Claim.** The client report's store-on-first-read looked up and stored without a lock, so two first reads
of the same sources could store two drafts, and an approval of the first was then not the one read next.

**Anchor.** `application/client_report.py` `_client_report` (before the fix). Plan
`report-delivery.md:172-182` (Finding, RD4a review).

**Reproduction.** `apps/api/tests/test_research_api.py::test_two_first_reads_of_the_client_report_store_one_draft`
(PostgreSQL; fails without the lock).

**Consequence.** A client report approved that was not the one handed over next.

**Smallest fix.** Done: `_client_report` takes the run's row (`WorkflowRepository.lock_run`) before it looks
for a stored draft (`packages/aia_core/src/aia_core/application/client_report.py:371 @ 5d5ed250`).

**Test.** The reproduction above.

**Status.** Closed by #888 (merged as `0e868b75`, 2026-10-25).

---

## OI-246 · Finding, closed · Two approvals of one report at once recorded two decisions

**Claim.** `approve_report` read a report's review and approved it without a lock, so two approvals at once
recorded two decisions.

**Anchor.** `application/report_approval.py` `approve_report` (before the fix). Plan
`report-delivery.md:174-182` (Finding, RD4a review).

**Reproduction.** `apps/api/tests/test_research_api.py::test_two_approvals_of_one_report_at_once_record_one_decision`
(PostgreSQL; fails without the lock).

**Consequence.** Two ledger rows for one report's approval.

**Smallest fix.** Done: `approve_report` takes the run's row before it reads the review, before any line
lock, as a snapshot's approval does
(`packages/aia_core/src/aia_core/application/report_approval.py:134 @ 5d5ed250`).

**Test.** The reproduction above.

**Status.** Closed by #888 (merged as `0e868b75`, 2026-10-25).

---

## OI-247 · Finding · A batch of waiting messages answered by a turn that then fails is never sent again

**Claim.** A queued batch (up to five messages) answered by a Lead turn that then failed, or parked for a reason other than the budget, is marked answered by that turn and not resent.

**Anchor.** `packages/aia_core/src/aia_core/application/research_lead.py:744 @ 1fed2969` (`_start_turn`). Plan `lead-conversation.md` F5 (#817).

**Reproduction.** Recorded by the plan from #817's review; no committed test yet.

**Consequence.** The researcher's messages get no answer and must be sent again by hand.

**Smallest fix.** LC10's retry, which regenerates a failed turn.

**Test.** LC10's.

**Status.** Open; owner `lead-conversation#LC10`.

---

## OI-248 · Finding · The Lead's state can return fewer turns than its limit

**Claim.** `ResearchLead.state(limit=100)` counts withdrawal rows within its limit, so it can return fewer than 100 turns.

**Anchor.** `packages/aia_core/src/aia_core/application/research_lead.py:554 @ 1fed2969`. Plan `lead-conversation.md` F6 (#817).

**Reproduction.** Recorded by the plan; no committed test yet.

**Consequence.** Harmless at today's sizes; a long conversation shows fewer of its older turns.

**Smallest fix.** Count turns, not rows, against the limit.

**Test.** A conversation with withdrawals returns `limit` turns.

**Status.** Open, low.

---

## OI-249 · Finding · A queued person turn no longer records its design revision

**Claim.** A person turn that waits in the queue no longer stores `design_revision_id`.

**Anchor.** Plan `lead-conversation.md` F7 (#817), `application/research_lead.py` @ 1fed2969.

**Reproduction.** Recorded by the plan.

**Consequence.** None today: nothing reads it on a person turn, and the Lead turn that answers names its revision.

**Smallest fix.** None needed unless a reader appears; then store it at queueing.

**Test.** —

**Status.** Open, informational.

---

## OI-250 · Hypothesis · A retried Lead message is stored twice

**Claim.** `POST …/lead/turns` takes no idempotency key, so a retry after a lost response stores the message twice, and with the queue both copies wait to be answered.

**Anchor.** `apps/api/src/aia_api/routers/lead.py:566 @ 1fed2969` (it predates LC5a). Plan `lead-conversation.md` F8 (#817); the coordinator's review of #817.

**Reproduction.** Not reproduced; a hypothesis until it is.

**Consequence.** A duplicated message, answered twice.

**Smallest fix.** A client-chosen key on the post, unique per researcher and study, answering the stored turn on a repeat.

**Test.** The same key posted twice stores one turn.

**Status.** Open, hypothesis.

---

## OI-251 · Finding, closed · The stage navigator shifted and resized with the current stage

**Claim.** The current stage was drawn bold, so its button grew and every later stage moved; the bar
used part of the width, the phase labels hid below 1500 px, and a stage's status was an 11 px glyph alone.

**Anchor.** `apps/web/src/components/workbench/workbench.css:89-99 @ a25d2435`. Plan
`research-lead-workbench.md` F24 (the navigator's; the file has a second F24, the review drawer).

**Reproduction.** On the UI workbench at 1440 px, Dotazník's slot is 96 px wide when current and 94 px
otherwise; every later slot moves 1-4 px.

**Consequence.** "the menu resizes depending on what stage you're currently on … it looks chaotic" (the
product owner, 2026-10-22).

**Smallest fix.** The six phases as labelled groups across the width, a fixed slot per stage, the current
stage a fill and an underline, never a weight; status by glyph, word and tone strip.

**Test.** `Workbench.layout.test.tsx` "the stage navigator: a steady, full-width bar"; `workbench_journey.mjs`.

**Status.** Closed 2026-10-26 by #840 (merged as `978d1789`, research-lead-workbench 35).

---

## OI-252 · Finding · Settings' near-limit tile reads spent alone; the server counts spent plus held

**Claim.** The "Téměř vyčerpané" tile and each row's ⚠ compare spent alone with the budget, while the
server's `near_limit` counts an open study's spent plus held, so a study whose budget is taken by open
holds is near to the server and not on Settings.

**Anchor.** `apps/web/src/lib/researcher-spend.ts:129 @ a1a9a45c` (`nearLimit`, >= 0.9); the server's rule
`domain/spend_attribution.py` `NEAR_LIMIT_SHARE`, served by `GET /settings/organization-spend`. Plan
`settings-redesign.md` F7 (#892).

**Reproduction.** Hypothesis until the test below is written: a study with a budget of 10, spent 5 and
held 5 is near on `GET /settings/organization-spend` and not on the tile.

**Consequence.** An administrator does not see a study about to stop at its cap.

**Smallest fix.** Read `near_limit` from `/settings/organization-spend` for an OWNER or ADMIN (it refuses a
member 403); keep the client rule for a member's own rows.

**Test.** A held-heavy study is near on the tile.

**Status.** Open (`settings-redesign`).

---

## OI-253 · Finding, closed · A question's condition editor dropped keyboard focus to the page

**Claim.** "Podmínka zobrazení" and "Upravit podmínku" unmounted as the form replaced them, and Uložit,
Zrušit, Escape and Odebrat podmínku unmounted what had focus, so a keyboard user started again from the top.

**Anchor.** `apps/web/src/components/rehome/research/QuestionCondition.tsx:69 @ ffce5c72`. Plan
`artifact-questionnaire.md` QF-18.

**Reproduction.** The test below, on `ffce5c72`.

**Consequence.** The condition editor could not be used from the keyboard.

**Smallest fix.** The form opens with focus on the chosen question; every way out puts focus on the first
enabled button left in the condition's box, else the question's wording.

**Test.** `QuestionnaireStep.test.tsx` "moves focus into the condition form and back to its button when it closes".

**Status.** Closed 2026-10-26 by #905 (merged as `e55cfb50`).

---

## OI-254 · Finding · A Lead's self-update of SOUL or USER is not checked for client facts

**Claim.** ADR 0030 decision 3 says a proposed personal text naming a client or holding a number is refused
as `client_fact_in_personal_file`; #919 built the check for hatching only, and a self-update still is not run
through it, only seen by the person before it is kept.

**Anchor.** `packages/aia_core/src/aia_core/application/research_lead.py:1091 @ a1a9a45c`
(`decide_self_update`), `domain/research_lead.py:962` (`split_self_update`), the check
`domain/lead_hatch.py:148` (`personal_text_refusal`). Plan `lead-identity.md` F1.

**Reproduction.** Hypothesis until the test below is written: `git grep client_fact_in_personal_file` finds
it only in `lead_hatch.py` and its tests.

**Consequence.** A client's name or figure can land in the Lead's personal files, which every client's study
then reads.

**Smallest fix.** Run `personal_text_refusal` on a self-update's name, SOUL, USER and personal notes in
`split_self_update`'s waiting half.

**Test.** A self-update naming a client is refused by name.

**Status.** Open; owner `lead-orchestration` LO11.

---

## OI-255 · Finding · The experimental Sociomapping view prints the run id outside Technické údaje

**Claim.** On the Sociomapa stage the experimental Sociomapping view's provenance row and report line print
the artifact, SHA-256 and run id outside `map-tech`.

**Anchor.** `apps/web/src/components/rehome/research/SociomappingView.tsx:318 @ a1a9a45c` (and its report
line, `:383 @ ce25a1b8`), rendered from `ExecutionSteps.tsx:1664 @ ce25a1b8`. Plan `artifact-sociomap.md`
§ Findings.

**Reproduction.** `node tools/ui_workbench/sociomap_journey.mjs` after `--prepare` on a fresh workbench:
"no run or method id outside Technické údaje" fails.

**Consequence.** A researcher reads internal ids on a stage meant to print none.

**Smallest fix.** Those two lines go inside a Technické údaje disclosure on the stage.

**Test.** The same journey check.

**Status.** Open; owner the map-first stage (SOC9-SOC11).

---

## OI-256 · Finding, closed · Opening Výsledky opened a report editor session

**Claim.** Opening Výsledky POSTed `…/report/editor` twice on the page's load, before the person asked for
the editor.

**Anchor.** `apps/web/src/lib/api.ts:1428 @ ce25a1b8`. Plans `artifact-sociomap.md` § Findings, `artifact-report.md`
§ Findings.

**Reproduction.** `sociomap_journey.mjs`: "nothing written but the stage opened" failed on `ce25a1b8`.

**Consequence.** A read of the results wrote editor sessions.

**Smallest fix.** Open the editor only once its results panel is shown.

**Test.** The same journey check.

**Status.** Closed 2026-10-26 by #964 (merged as `b969dca7`, `panel-shown.ts`).

---

## OI-257 · Finding, closed · An administrator's role change stamped the member's last activity

**Claim.** `ScopeRepository.upsert_user` wrote `last_seen_at = utcnow()` on every upsert of an existing user,
and `add_member` upserts the member it adds or re-roles, so an administrator's edit was read as the member's
last activity.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/scope_repository.py:214 @ 25ce6493`.

**Reproduction.** The tests below, on `25ce6493`.

**Consequence.** Naposledy showed a guess as a fact (CLAUDE.md §8).

**Smallest fix.** `upsert_user(…, seen=False)`; only the API's identity path passes `seen=True`.

**Test.** `apps/api/tests/test_member_last_seen_api.py`.

**Status.** Closed 2026-10-26 by #940 (merged as `3323de75`). A member whose last stamp came from an
administrator's edit keeps it until their next request.

---

## OI-258 · Finding · A member's last activity is the person's, not the membership's

**Claim.** `last_seen_at` lives on `users`, not on `organization_members`, so a request made in one
organization moves the Naposledy another organization's administrator reads.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/tables.py:458 @ a1a9a45c`.

**Reproduction.** Hypothesis until the test below is written: a member of two organizations makes a request
in one; the other's `GET /members` moves.

**Consequence.** None today: one deployment holds one organization (`deployment_shared`). Across
organizations it leaks a person's activity.

**Smallest fix.** A `last_seen_at` per membership (a migration), stamped for the organization the request
resolves to, read by `members()` from the membership.

**Test.** The reproduction above, asserting the other organization's value does not move.

**Status.** Open, low (#940's stand-in review).

---

## OI-259 · Finding · Návrh's research-question list hides questions the server reads

**Claim.** The list reads the analysis alone, while readiness traces `research_plan.research_questions`, so a
design whose questions are only in its research plan shows "Zatím žádné".

**Anchor.** `apps/web/src/research/plan-narrative.ts:25 @ 25ce6493` (`narrativeOf`). Plan `artifact-design.md`
F-DSN-4.

**Reproduction.** The workbench's `deep_research` fixture (`tools/ui_workbench/fixture_project.py:316 @
25ce6493`).

**Consequence.** A person adds the questions again while the run answers the ones they cannot see. Mitigated
by DSN2b (#942): the traced questions are listed under the list with their coverage.

**Smallest fix.** The list falls back to the research plan's questions when the analysis states none; it
changes what an edit writes, so it is DSN3's to decide.

**Test.** `PlanStep.test.tsx` "lists what the server reads as a research question that the list does not show…".

**Status.** Open, mitigated; owner `artifact-design` DSN3.

---

## OI-260 · Finding · The decided 365-day retention of kept spend and audit rows is enforced nowhere

**Claim.** MVPQ-07's 365 days for the kept AI spend, approval and audit rows is decided, but nothing erases
such a row after 365 days; every `kept_for` reads indefinite.

**Anchor.** `packages/aia_core/src/aia_core/application/client_deletion.py:252-282 @ 3aed0643`.

**Reproduction.** `grep -n "365" packages/aia_core/src/aia_core/application/client_deletion.py` finds nothing.

**Consequence.** Rows are kept past the agreed retention, and Settings' lhůta says "bez lhůty".

**Smallest fix.** An operator command beside `lead_retention.py` that erases them after 365 days; then
`kept_for` and the lhůta read 365 days.

**Test.** A kept row older than 365 days is gone after the command runs.

**Status.** Open (#980, `settings-redesign` F22).

---

## OI-261 · Hypothesis · The Brave search wire has no overall deadline

**Claim.** `web_retrieval_brave.py`'s urllib3 request has connect and read timeouts and no overall deadline.

**Anchor.** `packages/aia_core/src/aia_core/infrastructure/web_retrieval_brave.py:403 @ a1a9a45c` (its
timeouts). Plan `security-audit-2026-10.md` S13b.

**Reproduction.** Hypothesis: the same trickle as OI-206, from the search API's host.

**Consequence.** A stalled Brave answer holds a priced search step.

**Smallest fix.** The same watchdog and deadline as `UrllibWire`, or the request made through it.

**Test.** A trickling local server behind the Brave wire is cut at its deadline.

**Status.** Open (`security-audit-2026-10` S13b).

---

## OI-262 · Hypothesis · A priced tool call still out counts as held, not uncertain

**Claim.** In the spend fold Settings and Průběh share, a priced tool call dispatched and not yet answered
counts as held, while a model call in the same state counts as uncertain.

**Anchor.** Plan `artifact-results.md` F-R10 (#1004); the fold `domain/spend_attribution.py @ a1a9a45c`.

**Reproduction.** Hypothesis until a test is written: a run with one priced tool call in flight reads it in
`held`, not `uncertain_calls`.

**Consequence.** A run's spend reads as known while a priced call's outcome is not.

**Smallest fix.** Count a dispatched, unanswered priced tool call as uncertain in the fold.

**Test.** The reproduction above.

**Status.** Open (backend, the spend fold's).
