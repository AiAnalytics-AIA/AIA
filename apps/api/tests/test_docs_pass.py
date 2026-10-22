"""aia_api.docs_pass: the report editor's ticket and cookie, signed and read back.

Pure: each test names its clock. What a pass must never be is the point -- read under
another secret, as the other kind, after its expiry, or with one byte changed.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aia_api.docs_pass import COOKIE_LIFETIME, TICKET_LIFETIME, DocsPasses, Kind

SECRET = "s" * 40
NOW = datetime(2026, 10, 22, 12, 0, 0, 500_000, tzinfo=UTC)


@pytest.fixture
def passes() -> DocsPasses:
    return DocsPasses(SECRET)


def test_a_ticket_reads_back_as_what_was_issued(passes: DocsPasses) -> None:
    token, issued = passes.ticket(user_id="USR-1", organization_id="ORG-1", now=NOW)
    read = passes.read(token, kind="ticket", now=NOW)
    assert read == issued
    assert read is not None and read.ticket_id is not None and len(read.ticket_id) == 32
    assert read.expires_at == (NOW + TICKET_LIFETIME).replace(microsecond=0)


def test_every_ticket_has_its_own_id(passes: DocsPasses) -> None:
    ids = {passes.ticket(user_id="U", organization_id="O", now=NOW)[1].ticket_id for _ in range(50)}
    assert len(ids) == 50


def test_a_cookie_reads_back_and_carries_no_ticket_id(passes: DocsPasses) -> None:
    token, issued = passes.cookie(user_id="USR-1", organization_id="ORG-1", now=NOW)
    read = passes.read(token, kind="cookie", now=NOW + COOKIE_LIFETIME - timedelta(seconds=1))
    assert read == issued and read.ticket_id is None


def test_a_pass_is_never_read_as_the_other_kind(passes: DocsPasses) -> None:
    ticket, _ = passes.ticket(user_id="U", organization_id="O", now=NOW)
    cookie, _ = passes.cookie(user_id="U", organization_id="O", now=NOW)
    assert passes.read(ticket, kind="cookie", now=NOW) is None
    assert passes.read(cookie, kind="ticket", now=NOW) is None


@pytest.mark.parametrize("kind", ["ticket", "cookie"])
def test_a_pass_is_refused_from_its_expiry(passes: DocsPasses, kind: Kind) -> None:
    mint = passes.ticket if kind == "ticket" else passes.cookie
    token, issued = mint(user_id="U", organization_id="O", now=NOW)
    assert passes.read(token, kind=kind, now=issued.expires_at) is None
    assert passes.read(token, kind=kind, now=issued.expires_at - timedelta(seconds=1)) is not None


def test_another_secret_reads_nothing(passes: DocsPasses) -> None:
    token, _ = passes.cookie(user_id="U", organization_id="O", now=NOW)
    assert DocsPasses("t" * 40).read(token, kind="cookie", now=NOW) is None


def test_the_cookie_key_is_not_the_editor_secret(passes: DocsPasses) -> None:
    # The pass is HMAC-signed under a key derived from the secret, never the secret itself,
    # so what ONLYOFFICE signs with and what the gate checks are two keys.
    import base64
    import hashlib
    import hmac

    token, _ = passes.cookie(user_id="U", organization_id="O", now=NOW)
    payload, mac = token.split(".")
    raw = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).digest()
    assert mac != base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def test_a_changed_byte_is_refused(passes: DocsPasses) -> None:
    token, _ = passes.cookie(user_id="USR-1", organization_id="ORG-1", now=NOW)
    payload, mac = token.split(".")
    flipped = payload[:-1] + ("A" if payload[-1] != "A" else "B")
    assert passes.read(f"{flipped}.{mac}", kind="cookie", now=NOW) is None
    assert passes.read(f"{payload}.{mac[:-1]}x", kind="cookie", now=NOW) is None


@pytest.mark.parametrize(
    "value",
    [None, "", "nodot", "a.b.c", ".", "x.y", "é.ü", "%%%.%%%", "e30.e30"],
)
def test_anything_that_is_not_a_pass_is_refused(passes: DocsPasses, value: str | None) -> None:
    assert passes.read(value, kind="cookie", now=NOW) is None


def test_a_short_secret_is_refused() -> None:
    with pytest.raises(ValueError):
        DocsPasses("short")
