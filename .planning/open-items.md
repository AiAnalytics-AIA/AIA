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

## OI-6 · Gap · The reference's Python unfolding cannot be reproduced without its source

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

## OI-7 · Gap · Object-map base layout (`baseObjectLayout66`) is unrecovered

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

## OI-8 · Gap · `REF-GAP-SOCIO-R-SMACOF` — R numerical parity is not claimed

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

## OI-9 · Question · The AIA layout and its declarations need methodology sign-off

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

**Smallest fix.** Methodology owner reviews §4–§5 and either accepts the preset or
names replacements; the answer is recorded here and in the engine document.

**Status.** Open — decision D6 in `PROGRESS.md`.
