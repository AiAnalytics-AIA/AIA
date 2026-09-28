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

**Smallest fix.** Decision D3 in `PROGRESS.md` — vendor the reference as a
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

## OI-7 · Finding, archive-blocked · The seven enrichment derivations are not recoverable

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

**Status.** Open, blocked on `REF-WITHHELD-REFERENCE-ARCHIVE`. The eight runtime
fields also need a data-owner classification:
`docs/migration/population-derived-fields-decision.md`.

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

## OI-16 · Question · The AIA layout and its declarations need methodology sign-off

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

**Status.** Open — decision package ready, awaiting the owner (D6). **This is the
only methodology decision preventing client use.** It does not block computation.

---

## OI-17 · Requirement · No gate yet stops an unapproved Sociomap reaching a client

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

## OI-22 · Question · Should revoking a researcher stop the runs they started?

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

**Status.** Open. A product/security decision, not an engineering one.

---

## OI-23 · Finding · Secret-redaction patterns are defined twice

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

**Status.** Open. Deliberately not done in the worker change set: it moves code
the API owns, and one logical change per commit.

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

**Consequence.** Simulation is off the MVP path (decision D9 in `PROGRESS.md`), so this
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

## OI-50 · Finding · An empty bound in the audience range filter becomes 0, and the unit then targets the wrong people

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

**Status.** Open; ported as the classic behaves; **decision for the data owner**
before PR B merges.

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

## OI-61 · Decision owed (legal) · May panel-derived microdata be sent to a model provider?

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

**Status.** Open; blocks live AI fieldwork, not PR C.

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

---

## OI-65 · Follow-up · The usage ledger does not record the lineage a call declared

**Claim.** `ai_usage_events` has no lineage column; the licence gate's input for each call
is on the fieldwork dataset's provenance (`provenance.lineage`), not on the ledger row
(`packages/aia_core/src/aia_core/infrastructure/ai_usage_repository.py` `_row` @ `dec2fd1`).

**Consequence.** Auditing which datasets reached a provider needs the artifact as well as
the ledger. Nothing panel-derived can be sent today (OI-61), so nothing is missing yet.

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
proposal routes. Worker half open. It is not fixed there because it needs the failure-class
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

**Status.** Open. Owner: Job 3, with evidence governance, before or together with the aggregate
adapter. It is a rule of the research journey's contract (`docs/architecture/research-journey.md`
§4, §6 rule 6).

*2026-09-27, 18:05 UTC:* Job 3's draft PR #76 @ `7c46e0c` closes the path for native instrument
evidence. Its rows carry the aggregate's origin, and its instrument policy refuses a row that
names none (`domain/evidence/instrument.py:132-139`). The gate's default is unchanged
(`admission.py:91, 244`), so this stays open for any other builder of an `EvidenceRow`. Its
number follows the contract's rule for concurrent entries (§5). It was OI-72 on this entry's branch
until #83 put OI-76 on `develop` (`48bf3e2`, 22:45 UTC). #84 merged OI-77 at 23:09 UTC (`8c13a11`), and #75 still claims OI-72 to OI-75.

---

## OI-79 · Direction recorded, engineering open · Classify actual design inputs before model egress

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
- **The smoke's own `synthetic-client`.** If it is the archived one, the seed still stops, and
  un-archiving it is a person's decision. `access_audit` (`CLIENT_STATUS_CHANGED`) says who
  archived it and when.

## OI-81 · Question · Migrating a closed Study means reopening it, and delivering it again rewrites `delivered_at`

**Claim.** The 18.6.6 content migration leaves a Study that no longer accepts work
(delivered, archived or cancelled) waiting until someone reopens it. Delivering it again
after its migration stamps a new `delivered_at`, so the Study stops saying when it was first
delivered.

**Anchor.** `packages/aia_core/src/aia_core/application/workspace_migration.py:306-307 @ b0ce309`
(the `accepts_work` gate); `packages/aia_core/src/aia_core/infrastructure/scope_repository.py:576-577 @ b0ce309`
(every change to `DELIVERED` stamps `utcnow()`).

**Reproduction.** The cutover dress rehearsal of 2026-09-28, fictional Study S7 (see
`.planning/PROGRESS.md`). This is a rehearsal run, not yet a test.
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
