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

**Status.** Open. Mitigated, honestly reported by the workflow itself, promotion
condition recorded in `ARCHITECTURE.md §8`.

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
