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
(`.planning/plans/parity-matrix-and-gates.md`): the `|| true` is gone, every CI
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

**Status.** Open by decision, not by neglect.

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
can emit a Sociomap to a client.

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

## OI-33 · Finding · Resolving an uncertain call corrects the ledger but not the study's spend

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
