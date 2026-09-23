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

## OI-6 · Gap · `REF-GAP-SOCIO-R-SMACOF` — no fixture for the R smacof layout

**Owners.** parity-quality + A8 sociomapa-deterministic.

**Claim.** The reference chooses its Sociomapping layout algorithm by
`shutil.which("Rscript")`, so the same study yields different coordinates on
different hosts, and only the Python branch is characterised (F4). The size of
that host-dependence is unknown.

**Anchor.** AIA-reference `reference-gaps.md` "REF-GAP-SOCIO-R-SMACOF" @ 678e298;
`docs/migration/parity-matrix.json` `reference_gaps` and fixture
`F12_r_smacof_unfolding_layout` (`SPECIFIED_NOT_CAPTURED`).

**Blocker — wider than the reference records.** The reference lists only
"no Rscript". Its own recipe, step 3, runs
`sociomap.fit_unfolding(ratings, method="r_smacof", seed=20260814)` — legacy code
that exists only inside the **withheld archive**. A host with R but without the
archive cannot capture F12, so this gap is also blocked on
`REF-WITHHELD-REFERENCE-ARCHIVE`. Reproduction:
`grep -n "fit_unfolding" ../aia-reference/reference-gaps.md` shows the call;
`ls ../aia-reference` shows no `sociomap.py`.

**Consequence.** Until production *declares* an algorithm, the R/Python
divergence is also the size of an unrecorded methodology choice.

**Smallest path.** (1) A8 declares the production algorithm on `SociomapSpec`
(the fail-closed refusal already exists:
`test_sociomap_contracts.py::test_require_supported_passes_only_when_every_dimension_is_implemented`).
If it is the Python unfolding, F4 is the gate and F12 only sizes the recorded
difference (`gates_capability: false`). (2) Capture F12 on the host that first
holds both R + `smacof` and the licensed archive; correct the upstream gap
record to name the archive.

**Definition of done.** As in `parity-matrix.json` `reference_gaps`.

**Status.** Open, blocked on environment and on the archive licence decision.

---

## OI-7 · Gap · `REF-GAP-SIMULATION-WORLD-MODEL` — no fixture for world-model inoculation

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

**Consequence.** Simulation is off the MVP path (decision D6 below), so this
blocks no release today; it blocks the first release that ships the Simulation
lifecycle.

**Smallest path.** Freeze one sanitised world model (with its sha256) as fixture
*input* so deterministic parity never depends on a model reproducing tokens;
then capture F13 deterministically. The model call happens once, not per CI run.
A7 decides in the meantime whether production **rejects** out-of-range model
output (the intentional difference `SUB-SIM-BOUNDS`) — that decision needs no
fixture.

**Definition of done.** As in `parity-matrix.json` `reference_gaps`.

**Status.** Open, blocked on credential, egress route and archive.

---

## OI-8 · Finding · The reference links a weighting fixture to cost reservations

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

## OI-9 · Finding · `cost.reservations` ships with no reference-backed parity gate

**Claim.** Study budget reservations are `IMPLEMENTED` and owe **EXACT** parity
with the reference's `cost_controller`, but every test of them is
production-only; nothing compares a reservation decision with the reference's.

**Anchor.** `docs/migration/parity-matrix.json` capability `cost.reservations`
(gates `cost.reservations/contract`, `cost.reservations/contention`, both
`production_contract`).

**Reproduction.** `python tools/parity_status.py` →
`highest-risk unverified: cost.reservations … verdict NOT_RUNNABLE … no reference-backed gate`.

**Consequence.** A divergence in the decision at the limit, in settlement, or in
uncertain-settlement charging would merge green. This is money (high-risk R10)
on the MVP path, which is why the verdict tool ranks it first this cycle.

**Smallest fix.** A characterization suite for the legacy `cost_controller`
(as `test_legacy_job_store_characterization.py` did for `job_store`), then
comparison tests over the same decision matrix — a `reference_characterization`
and a `reference_comparison` gate. Both need the legacy tree, so they run
locally until the archive question is settled.

**Test that would have caught it.** Those gates.

**Status.** Open. Owner unconfirmed (matrix workstream `cost`), with parity-quality.
