# AGENTS.md — framework gotchas

Tool-agnostic notes for anyone's agent. Everything here cost someone real time in
*this* repository. Each entry shows the wrong version and the right version side
by side, because a rule you can pattern-match is a rule you will follow.

For the project map and the working rules see [CLAUDE.md](CLAUDE.md); for
layering see [ARCHITECTURE.md](ARCHITECTURE.md).

**Adding an entry is not optional.** When you lose an hour to a framework
behaving differently than it reads, it goes here in the same change set — with
the wrong version, the right version, and what it cost. This file exists because
the same debugging session was happening twice.

---

## Make / virtualenv

**Tooling resolves its interpreter. It never assumes one.** CI installs into the
runner's Python and has no `.venv`; a hardcoded path breaks every target that
uses it. `make openapi` died on the first push for exactly this.

```make
# WRONG — works on one machine
PY := .venv/bin/python

# RIGHT — prefers the project venv, falls back to PATH
PY  := $(shell [ -x $(VENV)/bin/python ] && echo $(VENV)/bin/python || command -v python3)
BIN := $(shell [ -d $(VENV)/bin ] && echo $(VENV)/bin/ || echo "")
```

## Tool configuration discovery

`ruff` and `mypy` are invoked **from the repository root** by CI and by
`make check`. Neither discovers per-package `pyproject.toml` from there. Shared
tool configuration therefore lives in the root `pyproject.toml`; per-package
files hold dependencies and build config only.

This is not cosmetic: a `mypy` override sat in a package file and was silently
ignored until the root file existed. The type checker reported clean while not
applying the rule at all.

## Python packaging

**An import with no declared dependency is a broken build waiting for a clean
machine.** `pyjwt[crypto]` was imported by the identity layer and installed by
hand into one working virtualenv; a clean install had no `jwt` module. Before
claiming a change works:

```bash
python3 -m venv /tmp/clean
/tmp/clean/bin/pip install -q -e "packages/aia_core[dev,postgres]" -e "apps/api[dev]"
/tmp/clean/bin/python -m pytest -q
```

An **optional** dependency is imported lazily, inside the one place that needs
it, so the package installs and imports without it:

```python
# WRONG — makes boto3 mandatory for everyone, including the domain tests
import boto3

# RIGHT — inside S3ArtifactStore, on first use, under the lock
if self._client is None:
    with self._lock:
        if self._client is None:
            import boto3
```

## pytest

**A skip is not a pass.** Environment-guarded skips are legitimate — no
PostgreSQL, no legacy reference checkout — but a suite that silently skips its
only real assertions reports green while testing nothing. Where the environment
is a requirement rather than a nicety, turn its absence into a failure:

```yaml
# The concurrency suite must actually RUN. A missing DATABASE_URL must not
# masquerade as a pass.
env:
  AIA_REQUIRE_POSTGRES: "1"
run: pytest packages/aia_core/tests/test_workflow_concurrency.py -q
```

A *static* `@pytest.mark.skip` or `@pytest.mark.xfail` is different again: it
deletes the signal permanently. `make layer_check` rejects both.

**Both test directories are called `tests`,** so they are not importable
packages. Share helpers through `conftest.py` fixtures — never through an import
between test modules.

```python
# WRONG — resolves differently depending on rootdir, or not at all
from tests.helpers import make_project

# RIGHT — a fixture in conftest.py
def test_x(project_factory): ...
```

**A session left open hangs the next fixture's teardown, not the test.** A test
that claims a step on a session it never closes leaves a connection *idle in
transaction* holding row locks; the test passes, and the fixture's `DELETE` at
teardown then waits on those locks forever. The symptom is a suite that stops
printing after a `PASSED`. Every session a test opens is closed in a `finally`,
or opened with `with`:

```python
# WRONG — never closed; its locks outlive the test
_, repo = make_repo()
assert repo.claim_next(worker_id="w") is not None

# RIGHT
session, repo = make_repo()
try:
    assert repo.claim_next(worker_id="w") is not None
    session.commit()
finally:
    session.close()
```

To find the culprit: `SELECT pid, state, query FROM pg_stat_activity WHERE state
LIKE 'idle in%'` — its last query names the call that opened it.

Markers are registered in the root `pyproject.toml` **and** in each package's
own `pyproject.toml`, and `--strict-markers` is on, so a typo in a marker name is
an error rather than a silently unfiltered run. Current markers: `parity`,
`postgres`, `golden`.

**pytest takes its configuration from the nearest `pyproject.toml` to the paths
you pass, not from the root.** `pytest packages/aia_core/tests/…` reads
`packages/aia_core/pyproject.toml`; only `pytest packages/aia_core apps/api`
(common ancestor: the root) reads the root file. A marker registered only at the
root therefore fails collection for a single-package run:

```toml
# WRONG — root pyproject.toml only; `pytest packages/aia_core` errors with
# "'golden' not found in `markers` configuration option"
markers = ["golden: ..."]

# RIGHT — the same line in the root AND in packages/aia_core/pyproject.toml
```

The same rule moves **JUnit paths**: the `file` attribute is relative to that
chosen rootdir, so one test is `tests/test_x.py` in one run and
`packages/aia_core/tests/test_x.py` in another. `tools/parity_status.py` matches
by path suffix for exactly this reason. Found when the golden-fixture marker was
added.

**Exit code 0 is not evidence that anything ran.** A suite whose tests all skip
exits 0. Every CI pytest step writes `--junit-xml … -o junit_family=xunit1`
(xunit1 carries the file path) and `tools/parity_status.py` reads it, so a
skipped parity gate reports `NOT_EXECUTED` rather than green.
`test_parity_matrix.py` fails any CI pytest step that stops writing JUnit.

**Golden fixtures are serialised to ten decimals.** The reference's fixture
builder rounds every float, so an `EXACT` fixture compared with `==` fails on
`1 + 9 * 0.2`, which is `2.8000000000000003`, not the `2.8` on disk. Compare the
*decision* exactly and the value at the serialisation:

```python
# WRONG — fails on float representation, not on behaviour
assert coerce_relation_scale_1_10(m) == fixture["expected_output"]["similarity_0_1"]

# RIGHT — branch exact, values to the fixture's 1e-10 rounding
assert coercion_branch(m) is CoercionBranch.SIMILARITY_0_1
assert all(abs(a - e) <= 1e-9 for a, e in zip(flat(got), flat(want)))
```

**A vendored fixture's filename must pass `make exposure_check`.** Rule 2c rejects
any tracked `.csv`/`.tsv`/`.json` whose name contains a reference-data noun —
`respondent`, `segment`, `panel`, `weights` … — so the reference's
`F7_terrain66_respondent_density.json` fails the build when copied in as-is. It
is vendored as `F7_terrain66_density.json`; the fixture id inside is unchanged
and `fixtures/sociomap/index.json` maps it back. Rename; do not add an exemption.
`exposure_check` reads `git ls-files`, so an untracked file passes until it is
staged — run it after `git add`, not before.

## Pydantic

**An after-validator never sees a boolean in an `int` field.** Lax mode coerces
`True` to `1` *before* a `mode="after"` validator runs, so an
`isinstance(v, bool)` check there is dead code and `max_iterations=True` becomes
one iteration. Reject booleans in a `mode="before"` validator:

```python
# WRONG — v is already 1 by the time this runs
@field_validator("max_iterations")
def _check(cls, v: int) -> int:
    if isinstance(v, bool) or v < 1: ...

# RIGHT
@field_validator("max_iterations", mode="before")
def _not_boolean(cls, v: object) -> object:
    if isinstance(v, bool):
        raise ValueError("expected an integer, not a boolean")
    return v
```

**ruff `RUF001` rejects Greek letters in string literals** — including the
reference's own legend label `"odchylka σ"`. Escape it (`"odchylka \u03c3"`)
rather than suppressing the rule; the comment beside it must not contain the
letter either (`RUF003`).

## SQLAlchemy and PostgreSQL

**SQLite cannot test concurrency.** It is single-writer, so every lease, lock and
budget-reservation test passes vacuously against it — two workers claiming one
step, a lock convoy and a budget overspend race all passed the sequential suite.
Concurrency semantics are tested against real PostgreSQL, with real concurrent
transactions, and CI runs both engines: PostgreSQL for truth, SQLite to keep the
offline development path working.

**An ORM read-check-write is a lost update waiting for a second writer.** The
ORM flushes a changed attribute as `UPDATE … WHERE pk = :id` — the check you made
in Python is not in the statement. The heartbeat did exactly this, and a
reconciler that expired the attempt between the read and the write was silently
overwritten, putting a recovered attempt back to `EXECUTING` so two workers ran
one step. Put the condition in the statement, where the database re-evaluates it
against the committed row:

```python
# WRONG — the status check is Python's; the UPDATE is by primary key only
attempt = session.get(StepAttemptRow, attempt_id)
if attempt.worker_id == worker_id and attempt.status in LIVE:
    attempt.lease_until = deadline          # overwrites a concurrent EXPIRED

# RIGHT — one conditional statement; rowcount says whether it held
result = session.execute(
    update(StepAttemptRow)
    .where(StepAttemptRow.attempt_id == attempt_id,
           StepAttemptRow.worker_id == worker_id,
           StepAttemptRow.status.in_(LIVE))
    .values(lease_until=deadline)
)
accepted = result.rowcount == 1
```

Where a read-then-decide is unavoidable, lock the row first (`with_for_update()`)
— and see the next entry.

**`SELECT … FOR UPDATE` does not refresh an object already in the identity map.**
The lock is taken and the row re-read, but SQLAlchemy keeps the attribute values
it already had for that primary key, so a check made after the lock can still see
a stale status. When the lock is the point, ask for the fresh values too:

```python
# WRONG — locked, but `attempt.status` may be what this session read earlier
attempt = session.scalar(select(StepAttemptRow).where(...).with_for_update())

# RIGHT
attempt = session.scalar(
    select(StepAttemptRow).where(...).with_for_update()
    .execution_options(populate_existing=True)
)
```

**In-memory SQLite cannot serve two threads.** `create_app_engine` gives
`:memory:` a single shared connection (`StaticPool`) so separate sessions see one
database — which also means a second thread (the worker's heartbeat) shares that
connection mid-transaction. Tests with more than one thread use a **file-backed**
SQLite database per test (`apps/worker/tests/conftest.py`).


**SQLite hands back naive timestamps.** `DateTime(timezone=True)` round-trips an
aware `datetime` on PostgreSQL and a **naive** one on SQLite, which has no
timestamp type. The same repository code therefore builds a valid domain object
on one engine and trips a "must be timezone-aware" guard on the other — found
when the population registry's `DatasetVersion` refused its own rows on SQLite
only.

```python
# WRONG — passes on PostgreSQL, raises on SQLite
imported_at=row.imported_at

# RIGHT — every value this schema writes is UTC, so a naive read is UTC
from .tables import as_utc
imported_at=as_utc(row.imported_at)
```

Convert at the row → domain boundary, never by loosening the domain guard.

Anything touching the database lives in `infrastructure/`. See
[ARCHITECTURE.md §3](ARCHITECTURE.md#3-enforcement--make-layer_check).

## Alembic

Three checks, and each catches something the others do not:

```bash
alembic upgrade head    # the migration applies
alembic check           # the schema matches the models — catches a model
                        # changed without a migration, which otherwise surfaces
                        # as a runtime error after deploy
alembic downgrade base && alembic upgrade head   # it is reversible
```

`migrations/versions/` is excluded from `mypy` and from `ruff`'s extended
selection: revisions are generated code, and they are verified by being executed
in CI rather than type-checked.

## mypy --strict

**An untyped third party leaks `Any` straight through a declared return type.**
`jwt.encode` is untyped; a function annotated `-> str` returning its result type-
checked clean while returning `Any`. Narrow at the boundary, explicitly:

```python
# WRONG — declared str, actually Any, and mypy is satisfied
def make_token(claims: dict[str, Any]) -> str:
    return jwt.encode(claims, key, algorithm="RS256")

# RIGHT — the untyped boundary is one line, and it is visible
def make_token(claims: dict[str, Any]) -> str:
    token: str = str(jwt.encode(claims, key, algorithm="RS256"))
    return token
```

**`aia_core` ships no `py.typed`, so check every source tree in one run.** Run on
its own, `mypy apps/worker/src` treats `aia_core` as an untyped third party and
reports eighteen `import-untyped` errors; run together with
`packages/aia_core/src` it resolves the source directly. `make typecheck` and CI
therefore pass all three trees to a single `mypy` invocation. Splitting that
command "for speed" silently changes what is checked.

Where a whole library has no stubs and pulling them in is not worth the
dependency, add a narrow `[[tool.mypy.overrides]]` in the root `pyproject.toml`
**with a comment saying why** — as `boto3` has. An unexplained override is
indistinguishable from an abandoned one.

## Python control flow

**An exception an executor must not swallow is a `BaseException`.** Executor code
is full of `except Exception:` — retry loops, provider adapters, "log and carry
on". A cancellation or a lost lease raised as an ordinary `Exception` is caught by
the first of those, and the executor keeps spending money on a step it no longer
owns. `asyncio.CancelledError` became a `BaseException` in Python 3.8 for exactly
this reason, and the worker's `StopExecution` follows it:

```python
# WRONG — any `except Exception` in an executor swallows it
class CancellationRequested(Exception): ...

# RIGHT — only code that names it (the worker) catches it
class StopExecution(BaseException): ...
class CancellationRequested(StopExecution): ...
```

The worker's own `except Exception` for an unclassified executor error therefore
does not catch these either; it names them explicitly, first.

## FastAPI

**A passing unit test does not prove the process boots.** `TestClient` does not
exercise the real ASGI server, a real database or the real startup ordering. CI
therefore migrates, starts `uvicorn`, and curls `/health` and `/ready` before
believing anything.

**Refusal must be explicit.** Assert the status code, not merely the absence of
data — an unhandled route and a correctly refused one both return no content:

```bash
# WRONG — passes when the route silently 500s, or does not exist
curl -fsS "$BASE" | grep -qv secret

# RIGHT
test "$(curl -s -o /dev/null -w '%{http_code}' "$BASE")" = "401"
```

**Route handlers hold no business rules.** No `Session`, no ORM table, no
decision. `dependencies.py` is the composition root and the only place that wires
engine, sessions, identity and scope.

## Pydantic settings

**Invalid production configuration fails at startup, not at first use.**
`Settings` validates on construction and raises, so a wildcard CORS origin or a
missing secret cannot reach a request:

```python
if "*" in self.cors_origins:
    problems.append("wildcard CORS origin is not permitted in production")
...
raise RuntimeError("invalid production configuration: " + "; ".join(problems))
```

An empty `cors_origins` means same-origin only, which is the correct default.
**Never `*`.**

## CI contracts

**A contract assertion that outlives the contract is worse than none.** CI
asserted `/api/v1/projects` after projects had moved under
`/api/v1/studies/{study_id}/projects`; the check passed on a route that no longer
existed. Two habits fix it:

- Move the assertion in the same commit as the contract.
- Add the **inverse** assertion where absence is what matters. Any project route
  *outside* a study prefix now fails the build, because that would mean scope had
  stopped being carried in the path.

## Next.js / TypeScript

`npm run lint`, `npx tsc --noEmit` and `npm run build` are three different
gates and all three are blocking. `apps/web` has its own lockfile, so CI caches
on `apps/web/package-lock.json` — caching on a branch name gives a stale
`node_modules` that fails for reasons unrelated to the change.

The client renders state the server computed. `GET …/impact` exists precisely so
no component reasons about which stages an edit invalidates.
