"""The product hostname must survive a missing or unhealthy 18.6.6 unit.

*Deploy develop* run 10 (2026-09-23) was the first to reach the host with the
legacy unit, and it took the whole site down: the host's env file had none of
the ``AIA_LEGACY_*`` values, so the Caddyfile's legacy site had an empty address
and Caddy could not parse the file; Caddy also waited for the unit to be
healthy, and the unit refuses to start without its data bundle. The services
had already been replaced, so nothing answered on the product hostname.

These checks read the files as text, like ``test_deploy_images.py``: the real
proof (Caddy loading through Compose with and without the settings) runs in the
``develop-host-config`` CI job, which has Docker.
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


def _service_block(text: str, name: str) -> str:
    """The lines of one top-level Compose service, up to the next one."""
    pattern = rf"^  {re.escape(name)}:\n(.*?)(?=^  [a-z][a-z0-9-]*:\n|\Z)"
    match = re.search(pattern, text, re.M | re.S)
    assert match, f"no service {name!r} in {COMPOSE.name}"
    return match.group(1)


def test_caddy_does_not_wait_for_the_legacy_unit() -> None:
    caddy = _service_block(COMPOSE.read_text(encoding="utf-8"), "caddy")
    depends = re.search(r"^    depends_on:\n((?:      .*\n)+)", caddy, re.M)
    assert depends, "caddy should still wait for web and api"
    assert "legacy-panel" not in re.sub(r"#.*", "", depends.group(1))


def test_every_legacy_setting_caddy_reads_has_a_default() -> None:
    caddy = _service_block(COMPOSE.read_text(encoding="utf-8"), "caddy")
    for name in ("AIA_LEGACY_HOSTNAME", "AIA_LEGACY_BASIC_USER", "AIA_LEGACY_BASIC_HASH"):
        value = re.search(rf"^      {name}: (.+)$", caddy, re.M)
        assert value, f"caddy no longer receives {name}"
        # `:-` covers unset *and* empty; Caddy's own `{$VAR:default}` does not.
        assert value.group(1).startswith(f"${{{name}:-"), f"{name} has no Compose default"


def test_the_default_hostname_never_asks_for_a_public_certificate() -> None:
    caddy = _service_block(COMPOSE.read_text(encoding="utf-8"), "caddy")
    default = re.search(r"AIA_LEGACY_HOSTNAME: \$\{AIA_LEGACY_HOSTNAME:-([^}]+)\}", caddy)
    assert default
    assert default.group(1).endswith(".localhost")


def test_the_deploy_checks_the_caddyfile_before_it_touches_anything() -> None:
    text = DEPLOY.read_text(encoding="utf-8")
    check = text.index("caddy validate")
    assert check < text.index('log "starting postgres"')
    assert check < text.index("-T api alembic upgrade head")
    assert check < text.index('log "replacing services"')


def test_the_deploy_waits_only_on_aias_services_and_smoke_checks_the_unit() -> None:
    text = DEPLOY.read_text(encoding="utf-8")
    waits = [line for line in text.splitlines() if "up -d" in line and "--wait" in line]
    replace = [line for line in waits if "--wait-timeout" in line]
    assert replace, "the service replacement no longer waits"
    for line in replace:
        assert "legacy-panel" not in line
        assert line.rstrip().endswith("postgres api worker web caddy")
    assert "the 18.6.6 unit is healthy" in SMOKE.read_text(encoding="utf-8")


def test_the_env_file_quotes_every_value() -> None:
    text = WRITE_ENV.read_text(encoding="utf-8")
    assert 'printf "%s=\'%s\'\\n" "$key" "$value"' in text
    assert 'printf \'%s=%s\\n\' "$key" "$value"' not in text
