"""The develop host serves AIA whatever state anything else is in.

*Deploy develop* run 10 (2026-09-23) was the first to reach the host with the
18.6.6 unit, and it took the whole site down: the host's env file had none of
the ``AIA_LEGACY_*`` values, so the Caddyfile's legacy site had an empty address
and Caddy could not parse the file; Caddy also waited for the unit to be
healthy, and the unit refuses to start without its data bundle. The services
had already been replaced, so nothing answered on the product hostname. Since
ADR 0018 the product stack has no unit at all: no service, image, volume,
setting, hostname, data sync or health check of it (deploy/reference runs it).

These checks read the files as text, like ``test_deploy_images.py``: the real
proof (Caddy loading through Compose) runs in the ``develop-host-config`` CI
job, which has Docker.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DEVELOP = REPO / "deploy" / "develop"
COMPOSE = DEVELOP / "docker-compose.yml"
DEPLOY = DEVELOP / "bin" / "deploy.sh"
SMOKE = DEVELOP / "bin" / "smoke.sh"
WRITE_ENV = DEVELOP / "bin" / "write-env.sh"
LIB = DEVELOP / "bin" / "lib.sh"


def _service_block(text: str, name: str) -> str:
    """The lines of one top-level Compose service, up to the next one."""
    pattern = rf"^  {re.escape(name)}:\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)"
    match = re.search(pattern, text, re.M | re.S)
    assert match, f"no service {name!r} in {COMPOSE.name}"
    return match.group(1)


def _code(text: str) -> str:
    """The lines that do something: comments dropped, so a note may name the unit."""
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("#"))


def test_the_product_stack_has_nothing_of_the_18_6_6_unit() -> None:
    compose = _code(COMPOSE.read_text(encoding="utf-8"))
    for gone in ("legacy-panel", "aia-legacy-panel", "legacy_state", "legacy-data", "AIA_LEGACY_"):
        assert gone not in compose, gone
    caddy = _service_block(COMPOSE.read_text(encoding="utf-8"), "caddy")
    depends = re.search(r"^    depends_on:\n((?:      .*\n)+)", caddy, re.M)
    assert depends, "caddy should still wait for web and api"


def test_the_caddyfile_reads_no_legacy_setting() -> None:
    # An unset AIA_LEGACY_HOSTNAME left the site address empty and Caddy unable
    # to parse the file (run 10). With no such site, no such setting is read.
    caddyfile = _code((DEVELOP / "Caddyfile").read_text(encoding="utf-8"))
    assert "AIA_LEGACY" not in caddyfile
    assert "legacy-panel" not in caddyfile


def test_the_deploy_checks_the_caddyfile_before_it_touches_anything() -> None:
    text = DEPLOY.read_text(encoding="utf-8")
    check = text.index("caddy validate")
    assert check < text.index('log "starting postgres"')
    assert check < text.index("-T api alembic upgrade head")
    assert check < text.index('log "replacing services"')


def test_the_deploy_pulls_syncs_and_waits_on_nothing_of_18_6_6() -> None:
    text = _code(DEPLOY.read_text(encoding="utf-8"))
    assert '"${COMPOSE[@]}" pull --quiet api worker web\n' in text + "\n"
    assert "legacy-panel" not in text and "aws s3 sync" not in text
    replace = [line for line in text.splitlines() if "up -d" in line and "--wait-timeout" in line]
    assert replace, "the service replacement no longer waits"
    smoke = _code(SMOKE.read_text(encoding="utf-8"))
    assert "the 18.6.6 unit is healthy" not in smoke and "AIA_LEGACY_HOSTNAME" not in smoke
    # The unit's old paths are the web client's 404, not a gate's answer.
    assert "the 18.6.6 unit's paths are AIA's 404" in smoke


def test_the_env_file_quotes_every_value() -> None:
    text = WRITE_ENV.read_text(encoding="utf-8")
    assert 'printf "%s=\'%s\'\\n" "$key" "$value"' in text
    assert 'printf \'%s=%s\\n\' "$key" "$value"' not in text


def test_a_changed_caddyfile_recreates_caddy() -> None:
    """Caddy reads its Caddyfile only at start, and Compose recreates a container
    only when its configuration changes, not when a bind-mounted file does. Run
    14 (2026-09-24) deployed a new Caddyfile that the running Caddy never read
    (OI-45). The file's hash is part of the service's configuration instead."""
    caddy = _service_block(COMPOSE.read_text(encoding="utf-8"), "caddy")
    label = r"^      aia\.caddyfile-sha256: \$\{AIA_CADDYFILE_SHA256:-unset\}$"
    assert re.search(label, caddy, re.M), (
        "caddy's configuration no longer carries the Caddyfile's hash"
    )
    lib = LIB.read_text(encoding="utf-8")
    compose_at = lib.index("COMPOSE=(")
    hash_at = lib.index('AIA_CADDYFILE_SHA256="$(sha256sum "$DEPLOY_DIR/Caddyfile"')
    assert compose_at < hash_at < lib.index("export AIA_CADDYFILE_SHA256")
    # Every script sources lib.sh before its first compose call, so they all agree.
    assert '. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"' in DEPLOY.read_text(encoding="utf-8")


def test_the_smoke_check_proves_caddy_runs_the_deployed_caddyfile() -> None:
    # /classic is AIA's own page only on this Caddyfile; the one before gated it.
    text = SMOKE.read_text(encoding="utf-8")
    assert '"$BASE/classic"' in text
    assert '[ "$classic_code" = "200" ]' in text and "už není součástí AIA" in text
    assert 'code "$BASE/interface-document"' in text and '[ "$direct_code" = "404" ]' in text


def test_aia_needs_no_switch_and_the_smoke_check_proves_its_gate() -> None:
    # ADR 0018: /app has no switch of its own, and the smoke check proves an
    # anonymous browser is sent to sign-in there, never served the screens.
    web = _service_block(COMPOSE.read_text(encoding="utf-8"), "web")
    for gone in (
        "AIA_INTERFACE_REHOME_ENABLED",
        "AIA_INTERFACE_SKIN_ENABLED",
        "AIA_LEGACY_PANEL_URL",
    ):
        assert gone not in web, gone
    text = SMOKE.read_text(encoding="utf-8")
    assert '"$BASE/app/clients"' in text
    assert '[ "$app_location" = "/login?next=%2Fapp%2Fclients" ]' in text


def test_the_smoke_check_proves_the_product_hostname_opens_aia_not_18_6_6() -> None:
    # ADR 0015: / redirects to the client directory; ADR 0018: the 18.6.6
    # interface is not served; and no path falls through to the unit.
    text = SMOKE.read_text(encoding="utf-8")
    assert '[ "$root_code" = "302" ] && [ "$root_location" = "/app/clients" ]' in text
    assert "18.6.6 is not served" in text
    assert '"$BASE/no-such-page"' in text and '[ "$stray_code" = "404" ]' in text
