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

**A dev extra that names a sibling distribution installs in dependency order.**
`apps/api[dev]` depends on `aia-worker` and `aia-executors` (its slice test
drives a real worker over the API's database). pip resolves those names only if
they are already installed or in the same `pip install` invocation, so the
Makefile and CI install `packages/aia_core`, `apps/worker`, `apps/executors`
and then `apps/api[dev]` — `pip install -e "apps/api[dev]"` on its own fails
on a clean machine with "No matching distribution found for aia-executors".

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

**There is no `pytest-asyncio`.** The model gateway is `async`; tests drive it
with `asyncio.run(gateway.invoke(...))` rather than adding a plugin and a marker.
To simulate a worker dying mid-call, raise a `BaseException` subclass from the
adapter: the gateway catches `Exception` (an adapter defect becomes an
*uncertain* call), and a process death must not be caught by anything.

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
`postgres`, `golden`, `oracle`.

**`skipif` is a static skip to `layer_check`.** The rule that rejects
`@pytest.mark.skip` matches `@pytest.mark.skipif` too, on purpose: a condition
evaluated at import time (``shutil.which("node") is None``) is decided before the
test exists and never reports *why* in the run. Skip at run time instead, where
the reason lands in the JUnit file that `tools/parity_status.py` reads:

```python
# WRONG -- rejected by `make layer_check`, and the reason is lost
@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")
def test_capture_reproduces_every_fixture(): ...

# RIGHT
def test_capture_reproduces_every_fixture():
    if shutil.which("node") is None:
        pytest.skip("capture reproducibility needs Node.js on PATH")
```

**A module imported by path must be registered in `sys.modules` before it runs.**
`tools/` is a script directory, so tests load a tool with
`importlib.util.spec_from_file_location`. With `from __future__ import
annotations`, `@dataclass` resolves string annotations through
`sys.modules[cls.__module__]`, and a module that was never registered crashes at
class-definition time with ``AttributeError: 'NoneType' object has no attribute
'__dict__'`` -- from inside `dataclasses.py`, naming nothing of yours. Register
first; `conftest.load_tool` does.

```python
# WRONG -- executes, then dies in dataclasses.py on the first @dataclass
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# RIGHT
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)
```

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

**A reused local PostgreSQL test database keeps the old table after a model
change.** The worker and executor suites create the schema on PostgreSQL and never
drop it (they truncate, so a killed run leaves no rows), and `create_all` skips a
table that already exists -- it never adds a column. Add a column to a model,
run the core suite against the same `aia_test`, and every test touching that table
errors with `column … does not exist` (PR C chunk 1b: 51 failed and 192 errors
until the core suite's own `drop_all` rebuilt it). CI starts from an empty
database, so this is local only. After a schema change, drop the local test
schema first:

```bash
psql "$TEST_DB" -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'
```

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

## ruff and Czech text

**`RUF001` rejects the characters Czech prose is made of.** Real report text uses
an en dash between numbers (`18–29 let`) and non-breaking spaces as thousands
separators (`12 345`), and a test of the prose number checker must use them — a
hyphen and an ordinary space test a different code path. Written literally, ruff
flags them as "ambiguous unicode" and some editors silently normalise them.

```python
# WRONG — flagged by RUF001, and invisible in review when it is an NBSP
("lidé 18–29 let", ((18.0, 0), (29.0, 0))),

# RIGHT — the escape is the character, and the diff shows it
("lidé 18\u201329 let", ((18.0, 0), (29.0, 0))),
```

The same applies to regex character classes in source: write `[ \u00a0\u202f]`,
never the literal characters.

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

**A flush is not durable.** Repositories here flush and never commit, which is
right for a state change and wrong for a record that must survive the process
dying *during* a side effect. The paid-call dispatch mark is exactly that: if it
is only flushed when the HTTP request leaves, a worker killed mid-call rolls it
back, the lapsed lease then looks safe, and the reconciler retries a call that
may already have been billed.

```python
# WRONG -- the mark lives in an open transaction while the money leaves
workflow.mark_paid_call_dispatched(attempt_id)     # flush only
response = await adapter.send(request)

# RIGHT -- committed before anything is sent (WorkflowCallJournal does this)
workflow.mark_paid_call_dispatched(attempt_id)
session.commit()
response = await adapter.send(request)
```

`test_ai_usage_ledger.py::test_without_a_committed_dispatch_the_same_crash_is_retried`
runs the crash both ways.

**A `before_update` listener guards the ORM, not the table.** `project_revisions`
rows are immutable, and `tables.py` refuses an ORM flush that would UPDATE one.
That hook fires only for objects the session flushes; a bulk `update()` statement
goes straight to SQL and never calls it. So the guard is paired with a layer rule
that forbids the bulk form:

```python
# Caught -- the listener raises on flush
row = session.scalars(select(ProjectRevisionRow).where(...)).one()
row.content = {...}
session.flush()                      # RuntimeError: ... is immutable

# NOT caught by the listener -- make layer_check forbids it instead
session.execute(update(ProjectRevisionRow).where(...).values(content={...}))
```

A "harmless" stamp on a just-inserted row is still an UPDATE. Chunk 1 of PR C set
`reason` on the revision `create()` had just written, and that would have tripped
the listener; the fix was for `create()` to take the reason, so the INSERT carries
it. `test_design_revisions.py::test_a_revision_row_is_never_updated`.

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

## The AI runtime: HTTP, SigV4, model output (Bedrock, 2026-09-25)

**urllib3 retries by default.** A `PoolManager()` re-sends on connection and some
read errors. For a metered call that is a second billed call nobody ledgered.

```python
# wrong: the default Retry re-sends a Converse request after a reset
pool = urllib3.PoolManager()
pool.request("POST", url, body=raw)
# right: no retry on the pool AND the request; the gateway decides (it never retries)
pool = urllib3.PoolManager(retries=False)
pool.request("POST", url, body=raw, retries=False, redirect=False)
```

Delivery follows from the exception: `NewConnectionError` / `ConnectTimeoutError`
happen before the request is written (`NOT_SENT`); anything else
(`ReadTimeoutError`, `ProtocolError`) may have reached Bedrock (`UNKNOWN`).

**`urllib3.exceptions.SSLError` does not say when it happened.** urllib3 2.x raises
it from the handshake (`_validate_conn`) *and* from reading the answer
(`conn.getresponse()`, the preloaded body): a corrupted or truncated TLS record
after a complete request is the same class as a handshake failure. Treating every
`SSLError` as `NOT_SENT` made a possibly billed call look free and retryable -- the
attempt was re-sent three times in
`test_an_ssl_failure_after_sending_needs_recovery_and_is_never_settled_as_free`.

```python
# wrong: every SSLError was "not sent"
except urllib3.exceptions.SSLError as exc:
    raise TransportFailure(str(exc), delivery=Delivery.NOT_SENT)
# right: only a refused server certificate is provably pre-send (the client verifies
# it during the handshake, before any application data); everything else is UNKNOWN
except urllib3.exceptions.SSLError as exc:
    sent = Delivery.NOT_SENT if _certificate_refused(exc) else Delivery.UNKNOWN
```

`_certificate_refused` looks for `ssl.SSLCertVerificationError` in the exception's
arguments and cause chain: urllib3 wraps the `ssl` error as `SSLError(e)`.

**Sign the bytes you send.** A SigV4 signature covers the body bytes. Serialising the
dict again in the transport (other separators, key order) sends different bytes and
AWS answers 403 `InvalidSignatureException`.

```python
# wrong: sign json.dumps(body), let the transport json.dumps it again
# right: serialise once, sign those bytes, send them (HttpRequest.raw_body)
raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
headers = signer.sign(method="POST", url=url, headers=h, body=raw)
HttpRequest(method="POST", url=url, headers=headers, body=body, raw_body=raw)
```

**A Bedrock model id in the path is one encoded segment.** `eu.anthropic.…-v1:0`
goes into `/model/{modelId}/converse` as `…-v1%3A0` (botocore's non-greedy label:
`quote(id, safe="-._~")`). Build the URL already encoded and give *that* URL to
`AWSRequest`; `SigV4Auth` encodes the path once more for the canonical request
(`%253A`), which is what the service expects. Do not decode it first.

**botocore's credential chain takes whatever it finds first**, including an
`AWS_ACCESS_KEY_ID` left in the environment or a shared credentials file. For a
route approved on the host's role, check where the credential came from:

```python
creds = botocore.session.get_session().get_credentials()
if creds.method not in {"iam-role", "container-role"}:   # "env", "shared-credentials-file", ...
    raise SigningUnavailable(...)
```

**`max(0.0, nan)` is `0.0`.** Clipping a model's probability vector with `max`
silently turns a NaN into a plausible zero. Refuse non-finite values *before*
clipping (`respondent_behavior.normalise`), as the unit does before `np.clip`.

**A per-request Pydantic contract keyed by arbitrary ids.** Question ids are not
Python identifiers you control. Name fields positionally and put the id in the
alias; `model_json_schema()` and `model_validate_json()` both use the alias by
default, so the provider sees and must return the real ids:

```python
create_model("RespondentBlock", __config__=ConfigDict(extra="forbid"),
             item_0=(Probabilities5, Field(alias="q1")), item_1=(Open, Field(alias="q-2")))
```

The class is rebuilt per request, so `isinstance(output, block_contract(block))` is
always False; compare `model_fields` instead.

**pytest can spend minutes rendering one failed assertion.** `assert "x" not in
big_string` over 60 request bodies took 104 s to *fail*, all of it in pytest's
diff of the string; the passing run took 4 s. Assert on a small, specific marker
(`"(ID q_sex)" not in sent`), or compute the boolean first and assert on it.

**Importing a vendored module that defines dataclasses, by path.**
`importlib.util.module_from_spec` + `exec_module` fails inside `@dataclass` with
`AttributeError: 'NoneType' object has no attribute '__dict__'` unless the module
is in `sys.modules` first:

```python
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module          # dataclasses resolve their module by name
spec.loader.exec_module(module)
```

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

**A dependency must read the settings the app was built with, not the
environment.** `create_app(settings)` takes an explicit, validated `Settings`
and stores it on `app.state`; a `Depends(get_settings)` constructs a fresh one
from the process environment. The two agree in a deployment and disagree in
every test that builds its own settings, so a route gated on a flag answers as
if the flag were unset. Found when the legacy-panel gate returned 404 in all its
tests with `legacy_panel_enabled=True`.

```python
# WRONG -- re-reads os.environ; ignores the Settings passed to create_app
SettingsDep = Annotated[Settings, Depends(get_settings)]

# RIGHT -- the validated instance the application was built with
SettingsDep = Annotated[Settings, Depends(get_app_settings)]   # request.app.state.settings
```

**An error raised after a write rolls the write back, audit rows included.**
`get_session` is a `yield` dependency that commits on success and rolls back on
any exception, and FastAPI propagates an `HTTPException` raised in the handler
or a later dependency into it. A refusal that writes an audit row and then
raises a 403 therefore records nothing (OI-42). Commit the row you mean to keep
before raising, or write it in a session of its own.

```python
# WRONG -- the LEGACY_PANEL_DENIED row is rolled back with the 403
resolver.authorize_legacy_panel(principal, audit=True)   # adds the row, raises

# RIGHT
except ScopeDenied as exc:
    session.commit()          # keep the refusal's audit row
    raise _forbidden(...) from exc
```

**A closed response model rejects a repository's extra key at runtime, not in
mypy.** `GET /access-audit` answered 500 for every organization with a grant,
because `audit_trail()` returns a `payload` key that `AuditEntryResponse`
(`extra="forbid"`) did not declare; no API test had called the route with data
in it. Fixed by declaring the field (`87da177`). Every route needs one API test
that returns *data*, not only one that is refused.

## Pydantic strict mode

**Strict *Python* mode rejects what JSON can express.** `model_validate(data,
strict=True)` on a dict parsed from JSON refuses `"a"` for an enum field ("Input
should be an instance of E") and an ISO string for a datetime, because in Python
mode strict means "already the right type". Strict *JSON* mode accepts those and
still rejects `"12"` for an integer, which is the strictness actually wanted when
validating a model's answer or a config file.

```python
# WRONG -- fails on every enum value in a JSON-shaped document
Contract.model_validate(json.loads(text), strict=True)

# RIGHT -- strict about types, fluent in JSON
Contract.model_validate_json(text, strict=True)
```

The model gateway, the tool registry and `parse_model_config` all validate this
way; a dict is re-serialised with `canonical_json` first.

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

**A list-typed setting is JSON-decoded from the environment before any
validator runs.** pydantic-settings treats `list[str]` as a complex field and
calls `json.loads` on the raw environment value itself; only the result reaches
a `mode="before"` validator. So the comma-splitting validator on `cors_origins`
never sees a bare string from the environment, and an empty value is a parse
error at start-up, not an empty list. This took the API container down on the
first develop deployment (run 35866350052; PR #35). Measured with
pydantic-settings 2.15.0: `""` and `"a,b"` both raise `SettingsError`; `"[]"`
and `'["a","b"]'` parse.

```yaml
# WRONG -- "" is not JSON; Settings() raises SettingsError before any validator
AIA_CORS_ORIGINS: ""
AIA_CORS_ORIGINS: "https://a.example,https://b.example"   # also not JSON

# RIGHT -- a JSON list, the empty one included
AIA_CORS_ORIGINS: "[]"
AIA_CORS_ORIGINS: '["https://a.example","https://b.example"]'
```

The alternative is `Annotated[list[str], NoDecode]` on the field, which hands
the raw string to the validator; it was not taken, so that `.env.example`,
Compose and the validator all agree on one shape. Note that constructing
`Settings(cors_origins="a,b")` in a test bypasses the environment decoding and
*does* reach the validator, which is why a unit test does not catch this.

## GitHub Actions

**A `workflow_dispatch` workflow must be registered on the default branch.**
GitHub registers it from `main` here. A workflow that lives only on `develop`
is not listed under *Actions* and has no *Run workflow* button. `push` and
`pull_request` triggers behave differently: they run the file from the pushed
branch, which is why `ci.yml` ran on `develop` while `deploy-develop.yml`, beside
it, did not. A `workflow_run` event also uses the default-branch ref; that
cannot enter our `develop` Environment, whose branch rule accepts only develop.

```
# WRONG -- merged to develop only; CI went green there and nothing deployed
.github/workflows/deploy-develop.yml   on: workflow_dispatch

# RIGHT -- register the dispatchable workflow on main with a workflow-only PR.
# After every required CI check succeeds on a develop push, CI dispatches the
# workflow using ref=develop and sha=$GITHUB_SHA. GitHub's environment branch
# rule then sees develop, and the deploy checks out the exact verified SHA.
```

Two consequences to carry:

- Keep the registered copy on `main` and the selected-ref copy on `develop`
  compatible. Dispatch uses the `develop` ref, so test a workflow edit there
  before relying on it and update `main`'s registration when its trigger or
  inputs change.
- Verify a registration, do not assume it:
  `GET /repos/<owner>/<repo>/actions/workflows` lists what GitHub will run; a
  file missing from that list will not fire. OI-37 records the first time this
  was learned here.

## Caddy

**Inside `handle`, Caddy re-sorts directives into its fixed order.** The
directive order puts `rewrite` before `forward_auth`, so a block that is written
gate-then-rewrite runs rewrite-then-gate: the gate sees the rewritten URI and
builds its `/login?next=` from it, sending a signed-out visitor back to an
internal path after sign-in. Proven by adapting both forms and reading the
handler order (`.github/workflows/ci.yml`, *The interface document is served
only through the gate*). `route` keeps the written order:

```caddyfile
# WRONG — the rewrite runs first
handle /classic {
	forward_auth api:8000 { uri /api/v1/panel/gate }
	rewrite * /interface-document
	reverse_proxy web:3000
}

# RIGHT
handle /classic {
	route {
		forward_auth api:8000 { uri /api/v1/panel/gate }
		rewrite * /interface-document
		reverse_proxy web:3000
	}
}
```

**A Caddyfile change does not reach a running Caddy by itself.** Caddy reads
the file once, at start, and `docker compose up -d` recreates a container only
when its image or its Compose configuration changes. A bind-mounted file's
*contents* are not part of that configuration, so a deploy that changes only
the Caddyfile leaves Caddy on the old one and every smoke check still passes
(OI-45: run 14 shipped the ADR 0013 routing and nobody could see it). Make the
file's hash part of the service's configuration:

```yaml
# WRONG — editing ./Caddyfile never recreates Caddy
caddy:
  volumes: ["./Caddyfile:/etc/caddy/Caddyfile:ro"]

# RIGHT — bin/lib.sh exports AIA_CADDYFILE_SHA256=$(sha256sum Caddyfile)
caddy:
  labels:
    aia.caddyfile-sha256: ${AIA_CADDYFILE_SHA256:-unset}
  volumes: ["./Caddyfile:/etc/caddy/Caddyfile:ro"]
```

And smoke-check something only the new file answers (here: `/` is Caddy's own
`302 /app/clients`, and `/classic` the gate's `302 /login?next=%2Fclassic`),
because checks the old routing also passes prove nothing. `/interface-document`
answering 404 no longer tells the two apart: the file before ADR 0015 said the
same.

**`redir`'s first argument is a matcher when it starts with `/`.** `redir
/app/clients 302` reads `/app/clients` as a path matcher and `302` as the
target: a redirect to `Location: 302` that fires only for `/app/clients`, a path
that never reaches `handle /`, so `/` gets no redirect at all. `caddy validate`
accepts both; only the adapted JSON shows it (`tools/caddy_routes.py` caught it):

```caddyfile
# WRONG — Location: 302
handle / {
	redir /app/clients 302
}

# RIGHT — `*` is the matcher, then the target and the status
handle / {
	redir * /app/clients 302
}
```

## DOCX (python-docx) and embedded fonts

**Word embeds only TrueType or OpenType, never WOFF2.** The web client's fonts are
WOFF2, so the report vendors the upstream TTFs of the same releases
(`infrastructure/report_docx/fonts/`). Converting WOFF2 to TTF would be a
modification of an OFL font, and both families reserve their names.

**An embedded face is matched by its family name (`name` ID 1).** A weight with
no Bold slot in its family, such as Plex's SemiBold (`IBM Plex Sans SmBld`) or
Source Serif's Semibold, is its own Word font. Ask for it by that name, not as
"bold".

```python
# wrong — Word synthesises bold from Regular, which is 700, not the design's 600
run.font.name = "IBM Plex Sans"; run.bold = True
# right — the face the file actually declares
run.font.name = "IBM Plex Sans SmBld"; run.bold = False
```

**Word's built-in styles carry theme-font attributes that override an explicit
font.** `Heading 1`, `Title` and others set `w:asciiTheme="majorHAnsi"`. With it
present, `w:ascii="IBM Plex Sans SmBld"` is ignored, and the heading renders in
the theme font (in LibreOffice, DejaVu). Found by a prototype: body text embedded
correctly while every heading fell back.

```python
# wrong — python-docx sets w:ascii, but w:asciiTheme still wins
style.font.name = "IBM Plex Sans SmBld"
# right — strip the theme attributes first
for a in ("w:asciiTheme", "w:hAnsiTheme", "w:cstheme", "w:eastAsiaTheme"):
    rfonts.attrib.pop(qn(a), None)
```

**Word enforces schema order in `settings.xml`; LibreOffice does not.** A file
LibreOffice opens can still be one Word calls corrupt. Insert settings children
in `CT_Settings` order (`embed._insert_in_order`), and never append them.

**LibreOffice ignores `w:ptab`.** An absolute-position tab to the right margin
would right-align a running head on any page width, but LibreOffice renders it
as nothing, and the chapter name lands mid-header. Use a right tab stop in the
Header / Footer *style* (at the text width) and a plain `w:tab` in the run.

**python-docx's `add_section` adds an empty paragraph.** It moves the previous
`sectPr` into a new, unstyled paragraph. The renderer instead moves it into the
section's own last paragraph (`layout.end_section`) and resets the body
`sectPr` — including dropping `pgNumType/@w:start`, which the clone would
otherwise carry into every later section and restart the page numbers.

```python
# wrong — an extra empty Normal paragraph, and page numbers restart again
document.add_section(WD_SECTION.NEW_PAGE)
# right
layout.end_section(ctx, layout.last_paragraph(ctx))
```

**A `Normal` paragraph has no `w:pStyle`.** python-docx omits the element for
the default style, so "every paragraph names its style" means "has a `pStyle`
or is `Normal`". `lint.lint_docx` checks the real rule: no formatting element in
`pPr`/`rPr`/`tblPr`/`trPr`/`tcPr` beyond style names and structure.

**A TOC's cached page numbers stay empty until Word updates the field.**
LibreOffice shows a TOC field's cached result as-is and does not evaluate the
`PAGEREF`s inside it; the renderer cannot know page numbers. Word updates them
on open (`w:updateFields`). A LibreOffice preview therefore shows the entries
and leaders without numbers — expected, not a defect. `STYLEREF` and `PAGE` in
running heads LibreOffice does evaluate.

**LibreOffice pads an inline picture by ~3 mm a side unless told not to.**
python-docx writes `wp:inline` without `distT/B/L/R`. Word reads them as 0;
LibreOffice as its default wrap distance, so a 2.5 mm evidence mark sat in a
gap three times its size. `images.add_vector_image` sets all four to `"0"`.

**An exact line height crops a picture to one line.** A style with
`w:spacing w:lineRule="exact"` (every text style in the report) clips an inline
picture to its leading in LibreOffice and Word alike: seven charts rendered as
7 mm slivers. The Figure paragraph style uses auto (single) spacing
(`Para(exact=False)`).

**The file-writing tool turns `\u00a0` / `\u2013` escapes into literal
characters.** Grep a newly written file for NBSP, en dash and minus before
running ruff; RUF001 then catches the rest.

**python-docx writes the current time into the zip.** Two renders of the same
document differ in bytes unless the package is rewritten with fixed timestamps
(`renderer._normalise_zip`) and the core properties are dated explicitly.

**Look at the pages, not only the XML.** Every layout defect in the report
renderer so far — the header tab, padded marks, cropped charts, a row split
from its interval — passed the structural tests and showed on the first
render. `make report-preview` (or `tools/report_preview.py some.docx`) renders
through LibreOffice with a private profile, so a running instance or a stale
lock never blocks it.

**Verifying a DOCX by eye needs LibreOffice Writer, not just its core.** A
container with `libreoffice-core` alone answers every conversion with "source
file could not be loaded", even for a document python-docx wrote itself. Install
`libreoffice-writer` (and `poppler-utils` for `pdftoppm`). It is a verification
tool, never a runtime dependency.

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

**`next dev` writes `apps/web/AGENTS.md` and `apps/web/CLAUDE.md`.** Next.js 16.3
generates both on every dev start (`node_modules/next/dist/server/lib/generate-agent-files.js`):
a boilerplate "this is NOT the Next.js you know" block and an `@AGENTS.md` include. They are
**not committed** unless their diff carries an intentional canonical instruction change (data
owner, 2026-09-24); the project's instructions live in the root `CLAUDE.md` and this file.
Keep them out of `git add` by path, or list them in your checkout's `.git/info/exclude`:

```bash
# WRONG — sweeps the regenerated files into a commit
git add -A
# RIGHT — stage named paths; the generated pair stays untracked
git add apps/web/src/... docs/...
```

`npm run lint`, `npx tsc --noEmit` and `npm run build` are three different
gates and all three are blocking.

**npm 10 cannot add Vitest 4 to this lockfile.** `npm install --save-dev
vitest@^4.1.11` fails inside arborist with `Cannot read properties of null
(reading 'edgesOut')` (`#loadPeerSet`), from a clean `node_modules` too, and
declaring `vite` explicitly does not help. It is an npm bug in peer-set loading,
not a real conflict. npm 11 resolves the same request, and the lockfile it
writes is still `lockfileVersion: 3`, which CI's npm 10 installs with `npm ci`.

```bash
# WRONG — fails, and every retry leaves the same error
npm install --save-dev vitest@^4.1.11

# RIGHT — change the lockfile with npm 11, then prove it with CI's npm
npx -y npm@11 install --save-dev vitest@^4.1.11
rm -rf node_modules && npm ci && npm test
```

Do not settle for Vitest 3.2.x to dodge it: every release before 4.1.11 carries
GHSA-82fw-gwwq-j7x9.

**`next` 16.3 lints every relative `window.location.assign`.** The
`@next/next/no-location-assign-relative-destination` rule (new in
`eslint-config-next` 16.3) warns on a hard navigation to a relative path and
suggests `router.push`. On the develop host that advice is wrong for `/`: it is
not a page of this app but the 18.6.6 document behind Caddy's `forward_auth`
gate (`deploy/develop/Caddyfile`, `handle /`), and a client-side transition
would render the Next route instead of going through the gate. Keep the full
navigation and say why at the call site (`src/lib/auth.ts`, `logout`).

```ts
// WRONG — skips the gate and the unit's document
router.push("/");
// RIGHT — a real request Caddy can gate
// eslint-disable-next-line @next/next/no-location-assign-relative-destination
window.location.assign("/");
```

A patched `next` needs 16.3.3 or later: every 16.1.x and 16.2.x release up to
16.2.12 still carries a critical advisory (npm's bulk advisory endpoint,
2026-09-24), so a 16.2 patch bump does not clear the audit.

**A `var()` with no fallback invalidates the whole declaration.** The design
branch's generator wrote `--font-sans-stack: var(--font-plex-sans), "Segoe UI", …`
for `next/font` variables. Where the layout does not define `--font-plex-sans`,
the *entire* `font-family` using that stack is invalid at computed-value time
and the element inherits its parent's font — no fallback face is tried. The
18.6.6 skin has no `next/font` at all, so the stack names the self-hosted
families directly and `fonts.css` declares them (`scripts/build-tokens.mjs`,
`FACES`):

```css
/* WRONG — invalid wherever the variable is undefined */
--font-sans-stack: var(--font-plex-sans), "Segoe UI", system-ui, sans-serif;
/* RIGHT */
--font-sans-stack: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
```

**Standalone output roots itself at the nearest lockfile above the app.** With
`output: "standalone"`, Next found the repository's root `package-lock.json`,
treated the monorepo as the workspace, and emitted
`.next/standalone/apps/web/server.js` — while an image built from `apps/web`
alone emits `.next/standalone/server.js`. The same Dockerfile then works in one
place and not the other. Pin the trace root to the package:

```ts
// WRONG — layout depends on what is above apps/web
const nextConfig: NextConfig = { output: "standalone" };

// RIGHT — apps/web/next.config.ts
const nextConfig: NextConfig = {
  output: "standalone",
  outputFileTracingRoot: path.join(__dirname),
};
```

**`NEXT_PUBLIC_*` is baked in at `next build`.** A value the browser needs that
differs per environment (the Cognito domain and client id) cannot be an
environment variable of the *running* container if it is read through
`process.env.NEXT_PUBLIC_…` in a client component: the SHA-tagged image becomes
environment-specific. Serve it from a route handler that reads `process.env` at
request time (`apps/web/src/app/config/route.ts`, `dynamic = "force-dynamic"`)
and fetch it once on the client.

**`react-hooks/set-state-in-effect` is an error under `eslint-config-next` 16.**
Reading `sessionStorage` into state inside `useEffect` fails lint, and reading
it during render breaks hydration (the server has no storage). The shape that
passes both is an external store with a server snapshot of `null`, and a cached
snapshot so React sees a stable object:

```ts
// WRONG — lint error, and a hydration mismatch if moved into render
useEffect(() => { setSession(readSession()); }, []);

// RIGHT — apps/web/src/lib/auth.ts
export function useSession() {
  return useSyncExternalStore(() => () => {}, readSession, () => null);
}
```

Errors derived from the URL (`useSearchParams`) are computed during render, not
set in an effect; only the asynchronous outcome of a promise is `setState`d. `apps/web` has its own lockfile, so CI caches
on `apps/web/package-lock.json` — caching on a branch name gives a stale
`node_modules` that fails for reasons unrelated to the change.

**A constant exported from a `"use client"` module is not a constant on the
server.** A server component that imports it gets a client *reference*, and
`className={inputClass}` renders the text of a thrown error into the HTML. Only
components cross that boundary; shared constants live in a plain module.

```ts
// WRONG -- ActionForm.tsx starts with "use client"
export const inputClass = "h-8 rounded-md …";   // imported by a server component

// RIGHT -- components/settings/styles.ts, no directive
export const inputClass = "h-8 rounded-md …";
```

The client renders state the server computed. `GET …/impact` exists precisely so
no component reasons about which stages an edit invalidates.

**`react-hooks/set-state-in-effect` flags a load function called from an
effect**, even when every `setState` in it runs after an `await`: the rule sees
a state-setting function called in the effect body. Start the fetch in the effect
and set state only in its promise callbacks, with a counter to reload:

```tsx
// WRONG — flagged: load() sets state, and is called from the effect body
useEffect(() => { void load(); }, [load]);

// RIGHT — state is set in callbacks; `setVersion(v => v + 1)` reloads
useEffect(() => {
  let live = true;
  unit("projects").then(parseProjectRows).then((r) => live && setRows(r), (e) => live && setError(msg(e)));
  return () => { live = false; };
}, [version]);
```

A dialog that must start from a new initial value each time is a child that
mounts per question (`useState(initial)`), not an effect that copies a prop.

**`tsc --noEmit` fails while `next dev` regenerates `.next/**/types`.** Changing
`next.config.ts` restarts the dev server, and for a few seconds
`.next/dev/types/validator.ts` references routes that are not yet written
(`TS2305 … AppRouteHandlerRoutes`). It is not the source: re-run when the dev
log says *Ready*. CI never runs `next dev`, so it never sees this.

**jsdom has no `<dialog>` modality.** `HTMLDialogElement.prototype.showModal` is
missing; a component test stubs it to set `open` (`ProjectsScreen.test.tsx`).

**jsdom's `Blob` has no `arrayBuffer()`.** Every current browser has it, so app
code calls `file.arrayBuffer()` directly (`fileToBase64` in
`src/unit/research/brief.ts`); a component test that uploads a `File` fails with
an error the screen then shows, not a thrown one, which reads as a rendering
bug. Polyfill it in the test through `FileReader`, never in app code
(`BriefStep.test.tsx`).

**Don't list the router in a load effect's dependencies.** A test's
`vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }))` returns a
new object on every render, so an effect keyed on `router` re-runs on every
render and reloads the project: an edit appears to do nothing, because the
store it went into was just replaced. Keep the router (and anything else the
load only *reads later*) in a ref, and key the load on what it loads
(`ResearchScreen.tsx`; pinned by "loads a project once, however often the
screen re-renders").

```tsx
// WRONG: reloads whenever the router object is new
useEffect(() => { load(projectId, (id) => router.replace(`/x/${id}`)) }, [projectId, router]);
// RIGHT
const routerRef = useRef(router);
useEffect(() => { routerRef.current = router; }, [router]);
useEffect(() => { load(projectId, (id) => routerRef.current.replace(`/x/${id}`)) }, [projectId]);
```

**Stub a list route with what the API returns, not with the full object.** A
fetch stub whose list route returns full runs lets a screen render steps it will
never get: `GET …/research/runs` returns summaries (`steps: []`,
`artifact_ids: []`), so Progress read from the list showed a completed run with
no steps, and every component test passed. Type the list item as what it is
(`ResearchRunSummary = Omit<ResearchRun, "steps" | "artifact_ids">`) and make the
stub return that shape (`listed(...)` in `ExecutionSteps.test.tsx`); the
workbench journey (`make ui-research`) is what found it.

```ts
// WRONG: the stub is richer than the API, so the bug is invisible
"GET /api/v1/studies/S/research/runs": () => ({ items: [COMPLETED] }),
// RIGHT: the list as the API sends it; the run in full at its own path
"GET /api/v1/studies/S/research/runs": () => ({ items: [{ ...COMPLETED, steps: [], artifact_ids: [] }] }),
"GET /api/v1/studies/S/research/runs/RUN-1": () => COMPLETED,
```

**A fragment-only navigation does not reload the page.** Following
`/#aia:open=PRJ-1` from `/` changes `location.hash` and nothing else: no
document load, so a script that reads the fragment once on load never sees it.
Read it on load *and* on `hashchange` (`apps/web/public/skin/handoff.js`).
Playwright's `page.goto` to the same path with a new fragment is the same trap in
tests: go to `about:blank` first.

## The 18.6.6 unit, run outside its container

**It registers its population files at import, not at first request.**
`population_context.py` bootstraps `data/population_registry.sqlite` the first
time it connects, which happens while `prototype_server` is imported; a panel
file that does not exist at that moment is silently skipped, and every later
`/api/bootstrap` answers `Population CZ_STATIC_REFERENCE není inicializována`.
The registry then remembers the empty state, so writing the file afterwards does
not help until the scratch copy is reset (`workbench.py up --fresh`).

```python
# WRONG — the registry is already built, without the panel
import prototype_server as core
frame.to_csv("FINALNI_KOMPLETNI_PANEL_v17_4_0.csv.gz")

# RIGHT — both files the registry names (STATIC v17_1_2, LIVE v17_4_0) first
for name in PANEL_FILES:
    frame.to_csv(name, index=False)
import prototype_server as core
```

**A missing panel column is an `AttributeError`, not a `KeyError`.**
`audience_dimensions.attach_derived` reads flags with `out.get('is_parent', 0)`;
on a frame without the column that is the int `0`, and `pd.to_numeric(0)` has no
`.fillna`. A stand-in frame needs every column the unit reads that way
(`tools/ui_workbench/unit_standin.py` lists them), invented values only.

**It uses whatever AI the machine it runs on has.** `claude_code_setup.executable`
finds any `claude` on `PATH`, and `claude_code_provider.health` then reports
`SUBSCRIPTION_READY` for the signed-in account, so a local copy of the unit on a
developer's machine or in an agent session will spend that account on the first
AI step anyone clicks. An `ANTHROPIC_API_KEY` in the environment is the same, billed
per token. A copy that is not meant to reach a model has to be told so, and in
more than one place, because the unit's edition flags, its CLI lookup and its
children's environment are read by different code:

```python
# WRONG: the unit's default edition allows all three providers
runpy.run_path("ui_server.py", run_name="__main__")

# RIGHT (tools/ui_workbench/unit_standin.py no_ai): edition flags off, with a
# provider list that is not empty (empty means "all" to allowed_providers),
# credentials and the CLI's directory out of the environment, the lookup stubbed
no_ai(here, os.environ)
claude_code_setup.executable = claude_code_provider.executable = lambda: None
```


## Hydrating legacy working state

**A seed database is installed once, not restored on every container start.**
The working SQLite project's hash changes after a save. Comparing it to the
archive seed and copying the seed on mismatch silently deletes projects while
PostgreSQL retains their study bindings (2026-09-26, reproduced loading the Lumen
study after PR #56 deployed). Runtime `hydrate_data.py` preserves any existing
`state_seed` file; immutable assets and first installation remain hash-checked.
Install the first seed through a temporary file in the same directory, sync the
complete copy, then atomically rename it. A direct copy interrupted by a process
or host stop leaves a partial regular file that the preservation rule would
mistake for saved working state (PR #57 review).

```python
# WRONG: a legitimate edit is treated as drift and replaced from the archive.
if sha256_of(target) != digest:
    shutil.copyfile(seed, target)

# RIGHT: working state survives a restart; a new state file is still verified.
if entry.get("class") == "state_seed" and target.is_file():
    continue
```

Back up live SQLite with `Connection.backup`, not a copy of the main file:
committed project content can still be in WAL. The host feeds the backup source
to the old image before replacing it; a backup helper present only in the new
image cannot protect the deployment that installs it.

## Docker registry credentials on the develop host

**`docker login` keeps the registry token, and so does the ECR helper's cache.**
`aws ecr get-login-password | docker login` writes the token base64-encoded, not
encrypted, into `~/.docker/config.json`; Docker prints "credentials are stored
unencrypted" on every deploy. Amazon's credential helper asks the instance role on
each pull instead, but by default it caches the same token in plain text in
`~/.ecr/cache.json`. Name the helper per registry and turn its cache off
(`deploy/develop/bin/lib.sh` › `ecr_login`, 2026-09-27).

```bash
# WRONG: a 12-hour token at rest in ~/.docker/config.json
aws ecr get-login-password | docker login --username AWS --password-stdin "$REGISTRY"

# RIGHT: nothing at rest; the instance role is asked on every pull
export AWS_ECR_DISABLE_CACHE=true
jq --arg r "$REGISTRY" \
  '.credHelpers[$r] = "ecr-login" | if has("auths") then .auths |= del(.[$r]) else . end' config.json
```

**A host package does not go in user-data.** cloud-init runs once per instance, so
a package added to `infra/develop/user-data.yaml.tftpl` never reaches the running
host, and with `user_data_replace_on_change = false` a changed `user_data` makes
the AWS provider stop and start the instance on the next `terraform apply`. The
deploy script installs what it needs, idempotently.
