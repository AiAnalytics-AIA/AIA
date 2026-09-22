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

Markers are registered in the root `pyproject.toml` and `--strict-markers` is on,
so a typo in a marker name is an error rather than a silently unfiltered run.
Current markers: `parity`, `postgres`.

## SQLAlchemy and PostgreSQL

**SQLite cannot test concurrency.** It is single-writer, so every lease, lock and
budget-reservation test passes vacuously against it — two workers claiming one
step, a lock convoy and a budget overspend race all passed the sequential suite.
Concurrency semantics are tested against real PostgreSQL, with real concurrent
transactions, and CI runs both engines: PostgreSQL for truth, SQLite to keep the
offline development path working.

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

Where a whole library has no stubs and pulling them in is not worth the
dependency, add a narrow `[[tool.mypy.overrides]]` in the root `pyproject.toml`
**with a comment saying why** — as `boto3` has. An unexplained override is
indistinguishable from an abandoned one.

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

### Tailwind 4 and the token theme

**`dark:` follows the OS, not our `data-theme` attribute.** The theme is chosen
per viewer (`<html data-theme="light|dark">`, or no attribute for "system"), and
Tailwind 4's default `dark:` variant is `prefers-color-scheme`. So a viewer who
picked light on a dark OS still gets every `dark:` utility.

```tsx
// wrong — shows the dark asset whenever the OS is dark, whatever the viewer chose
<img src="/brand/aia-wordmark.svg" className="dark:hidden" />
// right — colour comes from tokens, which already follow data-theme
<Wordmark label={t("app.name")} />   // SVG in currentColor + var(--signal)
```

Prefer token utilities (`bg-surface`, `text-ink`), which switch with the
attribute, over any `dark:` variant.

**`@theme inline` must not map a token onto a variable of the same name.**
`--radius-sm: var(--radius-sm)` inside `@theme inline` is a self-reference that
resolves to nothing, and every `rounded-sm` silently loses its radius. The
generator (`scripts/build-tokens.mjs`) writes literal values for radii and a
`-stack` suffix for font variables (`--font-sans: var(--font-sans-stack)`), which
avoids this. Never hand-edit `tokens.css`, `tokens-theme.css` or `tokens.ts`:
`npm run tokens:check` fails CI on drift.

**Check a 404 by status code, never by grepping the page.** A page that calls
`notFound()` does return 404, but the not-found copy also appears in the RSC
payload of *successful* pages, as the boundary's fallback, so a text search
reports a "not found" on a 200. Verify with
`curl -o /dev/null -w "%{http_code}"`.

### React 19 lint: external state goes through `useSyncExternalStore`

`eslint-config-next` enables `react-hooks/set-state-in-effect`, which is an
**error**. Copying `localStorage` into state from an effect trips it:

```tsx
// wrong — setState in an effect body; also renders "system" once, then flips
useEffect(() => { setPref(localStorage.getItem("aia.theme") ?? "system"); }, []);
// right — read the external store directly; the server snapshot keeps hydration stable
const pref = useSyncExternalStore(subscribe, readPreference, () => "system");
```

Read lint's error count, not its last line. `npm run lint | tail -1` prints
"0 errors and 1 warning potentially fixable" even when an unfixable error sits
above it. That is how this rule reached CI once.
