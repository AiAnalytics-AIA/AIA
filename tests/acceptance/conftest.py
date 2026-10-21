"""The tier-A acceptance stack (``docs/migration/mvp-acceptance.md`` §2): what the criteria run on.

The topology production runs, in separate processes on this machine:

* PostgreSQL 16, an empty database (or one this harness migrated before), named by
  ``AIA_ACCEPTANCE_DATABASE_URL``; tier A has no SQLite variant, because production has none;
* the API, ``uvicorn aia_api.main:app``, configured from its environment alone, behind the
  ``IdentityProvider`` seam (``development``: the bearer credential is the caller's e-mail; the
  provider refuses to exist outside ``local`` and ``test``);
* the worker, ``python -m aia_worker``, with ``aia_executors.acceptance_recorded:build_registry``:
  the production composition over recorded model answers, behind the real gateway.

**One operator bootstrap, then HTTP only.** :data:`BOOTSTRAP` is the only step that is not an
HTTP call: the schema (``alembic upgrade head``) and the organizations, their owners and the
seeded studies (``python -m aia_executors.seed``, the develop seed: no route creates an
organization or its owner). Its commands and what the seed printed are kept on the stack
(:attr:`Stack.bootstrap`) so the acceptance record can name them. Everything after it is a call
the web client makes.

This tree imports nothing of the application, the infrastructure or the apps
(``test_acceptance_harness.py::test_the_tree_imports_nothing_it_drives``): it talks to them the
way a browser and an operator do. Tests share what is here through fixtures, never by import.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
API = "/api/v1"
DATABASE_KEY = "AIA_ACCEPTANCE_DATABASE_URL"
#: The researcher the bootstrap makes the owner of the acceptance organization.
RESEARCHER = "researcher@acceptance.invalid"
#: The develop seed's second organization's owner (``develop_seed.SMOKE_OWNER_EMAIL``): a user
#: of another organization, for AC-01.
OTHER_ORGANIZATION_USER = "smoke.seed@aia-develop.invalid"
#: Generous: a cold start of the API imports the whole application (CLAUDE.md §7).
START_SECONDS = 90.0


def _python() -> str:
    return sys.executable


#: The operator bootstrap, in order. Each entry is argv after the interpreter.
BOOTSTRAP: tuple[tuple[str, ...], ...] = (
    ("-m", "alembic", "upgrade", "head"),
    ("-m", "aia_executors.seed", "--owner-email", RESEARCHER),
)


# --------------------------------------------------------------------------- #
# HTTP, as the web client speaks it
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Reply:
    status: int
    body: bytes
    headers: Mapping[str, str]

    def json(self) -> Any:
        return json.loads(self.body)

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", "replace")


#: The stack is on 127.0.0.1: no proxy from the environment (HTTPS_PROXY, a CI runner's) may
#: stand between the test and it.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@dataclass(frozen=True)
class Http:
    """The API's base URL (``…/api/v1``). Each call names who makes it: the credential is that
    person's e-mail, as the ``development`` identity provider reads it."""

    base: str

    def call(
        self,
        method: str,
        path: str,
        *,
        as_user: str | None,
        body: Any = None,
        timeout: float = 60.0,
    ) -> Reply:
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(self.base + path, data=data, method=method.upper())
        if as_user is not None:
            request.add_header("Authorization", f"Bearer {as_user}")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with _OPENER.open(request, timeout=timeout) as response:
                return Reply(response.status, response.read(), dict(response.headers))
        except urllib.error.HTTPError as error:
            return Reply(error.code, error.read(), dict(error.headers))

    def get(self, path: str, *, as_user: str | None) -> Reply:
        return self.call("GET", path, as_user=as_user)

    def post(self, path: str, body: Any, *, as_user: str | None) -> Reply:
        return self.call("POST", path, as_user=as_user, body=body)

    def put(self, path: str, body: Any, *, as_user: str | None) -> Reply:
        return self.call("PUT", path, as_user=as_user, body=body)


# --------------------------------------------------------------------------- #
# processes
# --------------------------------------------------------------------------- #


def _free_port() -> int:
    """A port free now; another process may take it before the API binds it (a known race,
    left: the API's start then fails visibly and the session fails, never passes)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _tail(path: Path, lines: int = 40) -> str:
    try:
        return "\n".join(path.read_text("utf-8", "replace").splitlines()[-lines:])
    except FileNotFoundError:
        return "(no log)"


@dataclass
class Process:
    """A process of the stack, with its log."""

    name: str
    popen: subprocess.Popen[bytes]
    log: Path

    def tail(self) -> str:
        return f"--- {self.name} ({self.log}) ---\n{_tail(self.log)}"

    def alive(self) -> bool:
        return self.popen.poll() is None

    def stop(self, timeout: float = 30.0) -> int:
        """SIGTERM, as ECS sends it; the exit code."""
        if self.alive():
            self.popen.send_signal(signal.SIGTERM)
        try:
            return self.popen.wait(timeout)
        except subprocess.TimeoutExpired:
            self.popen.kill()
            self.popen.wait(10)
            raise AssertionError(f"{self.name} did not stop on SIGTERM\n{self.tail()}") from None


def _spawn(name: str, argv: list[str], env: Mapping[str, str], home: Path) -> Process:
    log = home / f"{name}.log"
    handle = log.open("wb")
    try:
        popen = subprocess.Popen(
            argv,
            cwd=home,  # no .env of a developer's checkout is read
            env=dict(env),
            stdout=handle,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
        )
    finally:
        handle.close()
    return Process(name=name, popen=popen, log=log)


def _base_env(database_url: str, artifacts: Path) -> dict[str, str]:
    """What every process of the stack shares; nothing of the caller's environment but PATH."""
    return {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", str(artifacts.parent)),
        "PYTHONDONTWRITEBYTECODE": "1",
        "AIA_ENV": "test",
        "DATABASE_URL": database_url,
        "AIA_STORAGE_BACKEND": "filesystem",
        "AIA_STORAGE_ROOT": str(artifacts),
        "AIA_LOG_LEVEL": "WARNING",
    }


#: The API's settings for tier A: analysis on, the reservations its cost ceilings read.
API_ENV: Mapping[str, str] = {
    "AIA_IDENTITY_PROVIDER": "development",
    "AIA_AI_ANALYSIS_ENABLED": "true",
    "AIA_AI_FIELDWORK_RESERVATION_USD": "0.25",
    "AIA_AI_ANALYSIS_RESERVATION_USD": "1.0",
}

#: The worker's AI runtime for tier A: the production keys, test prices (not Bedrock's: the
#: real entry is dated configuration, ADR 0010), a route approved for Classes B and C (a
#: design is Class B by rule), every model request answered by the recorded wire.
WORKER_ENV: Mapping[str, str] = {
    "AIA_WORKER_EXECUTORS": "aia_executors.acceptance_recorded:build_registry",
    "AIA_WORKER_POLL_SECONDS": "0.2",
    "AIA_WORKER_MAINTENANCE_SECONDS": "1",
    "AIA_AI_RUNTIME_ENABLED": "true",
    "AIA_AI_ROUTE_ID": "bedrock-eu-primary",
    "AIA_BEDROCK_REGION": "eu-central-1",
    "AIA_BEDROCK_MODEL_ID": "eu.example.analysis-model-v1:0",
    "AIA_AI_POLICY_VERSION": "aia-model-policy-acceptance-1",
    "AIA_BEDROCK_INPUT_USD_PER_MTOK": "3",
    "AIA_BEDROCK_OUTPUT_USD_PER_MTOK": "15",
    "AIA_BEDROCK_MAX_OUTPUT_TOKENS": "8192",
    "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS": "200000",
    "AIA_AI_ROUTE_EU_PROCESSING_APPROVED": "true",
    "AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING": "true",
    "AIA_AI_ROUTE_APPROVED_FOR": "CLASS_C_INTERNAL,CLASS_B_DERIVED_CLIENT",
    "AIA_AI_ROUTE_RETENTION_DAYS": "0",
    "AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS": "1024",
    "AIA_AI_FIELDWORK_RESERVATION_USD": "0.25",
    "AIA_AI_ANALYSIS_ENABLED": "true",
    "AIA_AI_ANALYSIS_MAX_OUTPUT_TOKENS": "4096",
    "AIA_AI_ANALYSIS_RESERVATION_USD": "1.0",
}


@dataclass
class Stack:
    """The running stack: its URL, its processes, and what the bootstrap did."""

    http: Http
    api: Process
    database_url: str
    artifacts: Path
    home: Path
    bootstrap: list[dict[str, Any]]
    seeded: Mapping[str, Any]
    workers: list[Process] = field(default_factory=list)

    @contextmanager
    def worker(self, name: str = "worker", **env: str) -> Iterator[Process]:
        """A worker process over this stack's database and store, stopped on SIGTERM after."""
        process = _spawn(
            name,
            [_python(), "-m", "aia_worker"],
            {
                **_base_env(self.database_url, self.artifacts),
                **WORKER_ENV,
                "AIA_WORKER_ID": f"acceptance-{name}",
                **env,
            },
            self.home,
        )
        self.workers.append(process)
        try:
            yield process
        except BaseException:
            # The test's own failure is the one to report; the worker is stopped all the same.
            process.stop()
            raise
        code = process.stop()
        assert code == 0, f"the worker exited {code} on SIGTERM\n{process.tail()}"

    def logs(self) -> str:
        return "\n".join(p.tail() for p in (self.api, *self.workers))


def _database_url() -> str:
    url = (os.environ.get(DATABASE_KEY) or "").strip()
    if not url.startswith("postgresql"):
        pytest.fail(
            f"the acceptance stack needs {DATABASE_KEY}: a PostgreSQL database this harness may "
            "migrate and seed (tier A runs on PostgreSQL 16, as production does; "
            "`make test-acceptance` documents it)"
        )
    return url


def _run_bootstrap(env: Mapping[str, str]) -> tuple[list[dict[str, Any]], Any]:
    done: list[dict[str, Any]] = []
    seeded: Any = None
    for args in BOOTSTRAP:
        argv = [_python(), *args]
        # From the checkout, where alembic.ini names its migrations; DATABASE_URL is the env's.
        completed = subprocess.run(
            argv, cwd=REPO, env=dict(env), capture_output=True, timeout=300, check=False
        )
        out = completed.stdout.decode("utf-8", "replace")
        if completed.returncode != 0:
            pytest.fail(
                f"bootstrap step {' '.join(args)} exited {completed.returncode}\n"
                f"{out}\n{completed.stderr.decode('utf-8', 'replace')}"
            )
        done.append({"argv": list(args), "exit": completed.returncode})
        if "aia_executors.seed" in args:
            seeded = json.loads(out[out.index("{") :])
    return done, seeded


def _wait_for_health(http: Http, api: Process) -> None:
    deadline = time.monotonic() + START_SECONDS
    while time.monotonic() < deadline:
        if not api.alive():
            pytest.fail(f"the API exited {api.popen.returncode} at start\n{api.tail()}")
        try:
            if http.get("/health", as_user=None).status == 200:
                return
        except OSError:
            pass
        time.sleep(0.25)
    pytest.fail(f"the API did not answer /health within {START_SECONDS:.0f} s\n{api.tail()}")


@pytest.fixture(scope="session")
def stack(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Stack]:
    """Bootstrap once, start the API, and hand out HTTP and workers."""
    database_url = _database_url()
    home = tmp_path_factory.mktemp("acceptance")
    artifacts = home / "artifacts"
    artifacts.mkdir()
    base = _base_env(database_url, artifacts)
    bootstrap, seeded = _run_bootstrap(base)

    port = _free_port()
    api = _spawn(
        "api",
        [
            _python(),
            "-m",
            "uvicorn",
            "aia_api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-access-log",
        ],
        {**base, **API_ENV},
        home,
    )
    http = Http(f"http://127.0.0.1:{port}{API}")
    try:
        _wait_for_health(http, api)
        yield Stack(
            http=http,
            api=api,
            database_url=database_url,
            artifacts=artifacts,
            home=home,
            bootstrap=bootstrap,
            seeded=seeded,
        )
    finally:
        api.stop()
        if os.environ.get("AIA_ACCEPTANCE_KEEP") != "1":
            shutil.rmtree(artifacts, ignore_errors=True)


@pytest.fixture(scope="session")
def http(stack: Stack) -> Http:
    return stack.http


@dataclass(frozen=True)
class People:
    """Who acts: the bootstrap's researcher, and a user of another organization."""

    researcher: str = RESEARCHER
    other_organization: str = OTHER_ORGANIZATION_USER


@pytest.fixture(scope="session")
def people() -> People:
    return People()


@pytest.fixture
def unique() -> Callable[[str], str]:
    """A slug no earlier run of the harness on the same database has taken."""
    stamp = f"{time.time_ns():x}"

    def make(prefix: str) -> str:
        return f"{prefix}-{stamp}"

    return make


@pytest.fixture
def signed_in(http: Http) -> Callable[[str], None]:
    """Sign a person in as the web client does: ``POST /session`` (an AIA session, ADR 0018)."""

    def sign_in(email: str) -> None:
        reply = http.post("/session", {}, as_user=email)
        assert reply.status == 204, (email, reply.status, reply.text)

    return sign_in
