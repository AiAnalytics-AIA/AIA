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

## OI-6 · Finding · A provider park can auto-resume a possibly-billed call

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

## OI-7 · Question · Should revoking a researcher stop the runs they started?

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
