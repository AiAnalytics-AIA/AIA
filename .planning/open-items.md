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

## OI-6 · Question · Gate decisions that only the withheld legacy source can confirm

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

## OI-7 · Question · RELIGION is donor-matched but not named in the joint certificate

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

## OI-8 · Finding · Automatic factual-question detection is not ported

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
