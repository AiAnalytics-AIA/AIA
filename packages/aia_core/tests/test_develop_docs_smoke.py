"""The smoke's rows for the report editor's origin (plan report-editor-hosting, chunk 4a).

``bin/smoke-docs.sh`` is run here as ``bin/smoke.sh`` runs it: sourced beside smoke's own
``pass``, ``fail``, ``warn``, ``code`` and ``status_of`` (read from smoke.sh itself), with
``curl`` and ``docker`` stubbed on the PATH. What AIA serves on docs.<hostname> fails the
smoke; the Document Server's health only warns, since it never fails a deploy.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

BIN = Path(__file__).resolve().parents[3] / "deploy" / "develop" / "bin"
HELPERS = ("pass", "fail", "warn", "code", "status_of")
CACHE_LINK = (
    "/cache/files/data/smoke/output.docx/output.docx?md5=AAAAAAAAAAAAAAAAAAAAAA&expires=4102444800"
)
GOOD = {
    "/": 401,
    "/healthcheck": 404,
    "/coauthoring/CommandService.ashx": 404,
    "/9.4.0-1/coauthoring/CommandService.ashx": 404,
    "//info/info.json": 404,
    "/AI-PROXY/x": 404,
    CACHE_LINK: 403,
    "/__aia/session": 401,
}

CURL = """import json, os, sys
args = sys.argv[1:]
url = args[-1]
path = url.split("docs.aia.test", 1)[1]
with open(os.environ["CALLS"], "a") as f: f.write(path + "\\n")
status = json.loads(os.environ["CODES"])[path]
if status == 0:  # nothing answered: curl writes 000 for -w, nothing for -D, and fails
    if "-w" in args: print("000", end="")
    sys.exit(6)
if "-w" in args: print(status, end="")
else:
    print(f"HTTP/2 {status} \\r")  # as curl writes an HTTP/2 status line
    if os.environ["COOKIE"]: print(f"set-cookie: {os.environ['COOKIE']}=x; HttpOnly\\r")
"""
DOCKER = """import os, sys
args = sys.argv[1:]
if args[:1] == ["ps"]:
    if os.environ["HEALTH"] != "absent": print("docs-container")
elif args[:1] == ["inspect"]: print(os.environ["HEALTH"])
elif args[:1] == ["exec"]: print(os.environ["RUNNING_SRI"], end="")
elif args[:1] == ["compose"] and "printenv" in args: print(os.environ["API_SRI"], end="")
"""
SRI = "sha384-GvDXeDqc5phAYnmC9y4Xcqp2tUzLFpycvFBKZUTmcHC7L9EGcn65wreOdiDiSd7G"
# The same template under upstream's per-minute tag of a start at 2026-10-25 23:30.
SRI_23_30 = "sha384-c0+Tg0ShBLxn6IsOfEpBXXR0qio14ZB1lofsFqr8IRzE4+tYxS7dYEgHfoZgfeYM"
ROW = "api.js is the one Zpráva's integrity names"


def _helpers() -> str:
    smoke = (BIN / "smoke.sh").read_text(encoding="utf-8")
    lines = [
        m.group(0)
        for name in HELPERS
        for m in [re.search(rf"^{name}\(\) \{{.*\}}$", smoke, re.M)]
        if m
    ]
    assert len(lines) == len(HELPERS), "smoke.sh no longer defines every helper the rows use"
    return "\n".join(lines)


def _run(
    tmp_path: Path,
    *,
    enabled: bool = True,
    codes: dict[str, int] | None = None,
    cookie: str = "",
    health: str = "healthy",
    integrity: str = SRI,
    running: str = SRI,
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    shims = tmp_path / "shims"
    shims.mkdir()
    for name, program in (("curl", CURL), ("docker", DOCKER)):
        source = shims / f"{name}.py"
        source.write_text(program)
        shim = shims / name
        shim.write_text(
            f'#!/bin/sh\nexec {shlex.quote(sys.executable)} {shlex.quote(str(source))} "$@"\n'
        )
        shim.chmod(0o755)
    driver = tmp_path / "driver.sh"
    driver.write_text(
        "set -euo pipefail\nFAILED=0\nCOMPOSE=(docker compose)\n"
        + _helpers()
        + f'\n. {shlex.quote(str(BIN / "smoke-docs.sh"))}\ndocs_checks\nexit "$FAILED"\n'
    )
    calls = tmp_path / "calls"
    calls.touch()
    env = {
        **os.environ,
        "PATH": f"{shims}:{os.environ['PATH']}",
        "AIA_PUBLIC_HOSTNAME": "aia.test",
        "AIA_ONLYOFFICE_ENABLED": "true" if enabled else "false",
        "CODES": json.dumps({**GOOD, **(codes or {})}),
        "COOKIE": cookie,
        "HEALTH": health,
        "CALLS": str(calls),
        "RUNNING_SRI": running,
        # What the API's environment holds (docker-compose.yml's default, or SSM's).
        "API_SRI": integrity or "",
    }
    result = subprocess.run(
        ["bash", str(driver)], env=env, text=True, capture_output=True, timeout=30
    )
    return result, calls.read_text().splitlines()


def test_off_it_says_so_and_asks_nothing(tmp_path: Path) -> None:
    result, calls = _run(tmp_path, enabled=False, health="absent")
    assert result.returncode == 0, result.stderr
    assert result.stdout == "info  docs: the report editor is off (aia_onlyoffice_enabled)\n"
    assert calls == []


def test_off_but_still_running_warns_that_the_stop_failed(tmp_path: Path) -> None:
    result, calls = _run(tmp_path, enabled=False, health="healthy")
    assert result.returncode == 0, result.stderr
    assert (
        "WARN  docs: the report editor is off and its Document Server is stopped" in result.stdout
    )
    assert calls == []


def test_on_and_sound_every_row_passes(tmp_path: Path) -> None:
    result, calls = _run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    rows = result.stdout.splitlines()
    assert len(rows) == 6 and all(r.startswith("ok    docs: ") for r in rows), rows
    assert calls == list(GOOD)


@pytest.mark.parametrize(
    "codes,cookie,row",
    [
        ({"/": 200}, "", "refused by the docs gate"),
        ({"/": 404}, "", "refused by the docs gate"),
        ({"/9.4.0-1/coauthoring/CommandService.ashx": 200}, "", "own paths are refused"),
        ({"//info/info.json": 200}, "", "own paths are refused"),
        ({"/__aia/session": 302}, "", "without a ticket opens nothing"),
        ({}, "aia_docs", "without a ticket opens nothing"),
        ({}, "__Host-aia_docs", "without a ticket opens nothing"),
        ({CACHE_LINK: 200}, "", "forged signature is refused"),
        ({CACHE_LINK: 302}, "", "forged signature is refused"),
        # The gate's 401 or a 404: the route without the gate is gone, and no save is fetched.
        ({CACHE_LINK: 401}, "", "forged signature is refused"),
        ({CACHE_LINK: 404}, "", "forged signature is refused"),
    ],
)
def test_what_aia_serves_there_fails_the_smoke(
    tmp_path: Path, codes: dict[str, int], cookie: str, row: str
) -> None:
    result, _ = _run(tmp_path, codes=codes, cookie=cookie)
    assert result.returncode == 1
    failed = [r for r in result.stdout.splitlines() if r.startswith("FAIL")]
    assert len(failed) == 1 and row in failed[0], result.stdout


def test_nothing_answering_is_a_failed_row_never_an_aborted_smoke(tmp_path: Path) -> None:
    # DNS or Caddy's certificate not ready: curl fails. Under errexit an unguarded probe would end
    # the smoke there, with no row and no verdict.
    result, calls = _run(tmp_path, codes=dict.fromkeys(GOOD, 0))
    assert result.returncode == 1, result.stdout + result.stderr
    failed = [r for r in result.stdout.splitlines() if r.startswith("FAIL")]
    assert len(failed) == 7, result.stdout  # the gate, the five server paths, the ticket exchange
    assert "nothing answered" in result.stdout
    assert calls == list(GOOD)
    assert result.stdout.splitlines()[-2:] == [
        "ok    docs: the Document Server is healthy",
        "ok    docs: the editor's api.js is the one Zpráva's integrity names",
    ]


def test_a_gate_without_its_settings_says_which_are_missing(tmp_path: Path) -> None:
    result, _ = _run(tmp_path, codes={"/": 404, "/__aia/session": 404})
    assert result.returncode == 1
    assert result.stdout.count("AIA_ONLYOFFICE_URL and AIA_ONLYOFFICE_JWT_SECRET") == 2


def test_a_cache_link_with_nothing_behind_it_only_warns(tmp_path: Path) -> None:
    result, _ = _run(tmp_path, codes={CACHE_LINK: 502}, health="absent")
    assert result.returncode == 0, result.stdout
    assert "WARN  docs: a cache link with a forged signature is refused" in result.stdout


@pytest.mark.parametrize("health", ["unhealthy", "starting", "absent"])
def test_the_document_servers_health_only_warns(tmp_path: Path, health: str) -> None:
    result, _ = _run(tmp_path, health=health)
    assert result.returncode == 0, result.stdout
    assert "WARN  docs: the Document Server is healthy" in result.stdout
    assert ("not running" if health == "absent" else health) in result.stdout


def test_the_smoke_runs_the_rows_before_its_verdict() -> None:
    smoke = (BIN / "smoke.sh").read_text(encoding="utf-8")
    sourced = smoke.index('. "$DEPLOY_DIR/bin/smoke-docs.sh"')
    assert sourced < smoke.index("\ndocs_checks\n") < smoke.index('echo "smoke: all checks passed')


@pytest.mark.parametrize(
    "integrity,running,why",
    [
        # A restart under upstream's per-minute tag, or an image changed without its integrity.
        (SRI, SRI_23_30, "refuses the editor"),
        ("", SRI, "AIA_ONLYOFFICE_API_INTEGRITY is empty"),
        (SRI, "", "the running file is unreadable"),
    ],
)
def test_an_api_js_the_apis_integrity_does_not_name_warns(
    tmp_path: Path, integrity: str, running: str, why: str
) -> None:
    # The Document Server's own file, as its health is: said, never a failed deploy.
    result, _ = _run(tmp_path, integrity=integrity, running=running)
    assert result.returncode == 0, result.stdout
    lines = result.stdout.splitlines()
    warned = [r for r in lines if r.startswith("WARN")]
    assert len(warned) == 1 and ROW in warned[0], result.stdout
    assert why in lines[lines.index(warned[0]) + 1], result.stdout  # warn() writes its reason below


def test_the_integrity_is_read_only_from_a_healthy_server(tmp_path: Path) -> None:
    # Starting, its api.js may still carry upstream's per-minute tag: the health row says why.
    result, _ = _run(tmp_path, health="starting", running="sha384-other")
    assert result.returncode == 0, result.stdout
    assert "api.js" not in result.stdout
