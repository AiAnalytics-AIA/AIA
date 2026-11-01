"""Passes to the report editor's origin: a one-time ticket and the docs cookie it buys.

ONLYOFFICE Docs is served at ``docs.<hostname>``, an origin of its own, so its JavaScript
never runs beside AIA's session token (plan report-editor-hosting). AIA's session cookie
is host-only and *is* that token (deployed, ``__Host-aia_session``, which no other host can
set), so it never reaches the editor's origin. Instead:

* a signed **ticket** (60 s) names the person and their organization and carries a random
  id; the API spends it once (``docs_ticket_spends``), on the editor's own origin;
* the **docs cookie** it buys (8 h) names the same two ids and nothing else, and is
  what the docs gate reads on every request to the editor.

Both are ``<payload>.<mac>``: the payload is base64url JSON, the mac an HMAC-SHA256 under
a key derived from the editor's JWT secret, so the cookie's key is never the key ONLYOFFICE
signs with. Pure: no I/O, the clock passed in.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

TICKET_LIFETIME = timedelta(seconds=60)
# A working day: the docs gate cannot renew the cookie mid-session (forward_auth's answer never
# reaches the browser), and it asks again on every request whether the person is still an
# active member, so the cookie's age decides only how long a stolen one is of use.
COOKIE_LIFETIME = timedelta(hours=8)
# Separates this key from the JWT secret it is derived from, and from any later use of it.
_KEY_LABEL = b"aia-docs-pass-1"

Kind = Literal["ticket", "cookie"]


@dataclass(frozen=True)
class DocsPass:
    """What a valid ticket or cookie names. ``ticket_id`` is a ticket's alone."""

    kind: Kind
    user_id: str
    organization_id: str
    expires_at: datetime
    ticket_id: str | None = None


class DocsPasses:
    """Mints and reads passes under one secret."""

    def __init__(self, secret: str) -> None:
        if len(secret) < 32:
            raise ValueError("the docs pass secret must be at least 32 characters")
        self._key = hmac.new(secret.encode(), _KEY_LABEL, hashlib.sha256).digest()

    def ticket(self, *, user_id: str, organization_id: str, now: datetime) -> tuple[str, DocsPass]:
        issued = DocsPass(
            kind="ticket",
            user_id=user_id,
            organization_id=organization_id,
            expires_at=_second(now + TICKET_LIFETIME),
            ticket_id=secrets.token_hex(16),
        )
        return self._sign(issued), issued

    def cookie(self, *, user_id: str, organization_id: str, now: datetime) -> tuple[str, DocsPass]:
        issued = DocsPass(
            kind="cookie",
            user_id=user_id,
            organization_id=organization_id,
            expires_at=_second(now + COOKIE_LIFETIME),
        )
        return self._sign(issued), issued

    def read(self, value: str | None, *, kind: Kind, now: datetime) -> DocsPass | None:
        """The pass ``value`` is, if it is one of ``kind``, signed here and unexpired; else None."""
        if not value or value.count(".") != 1:
            return None
        payload, mac = value.split(".")
        # As bytes: a str compare raises on a non-ASCII value, and a cookie is whatever was sent.
        if not hmac.compare_digest(mac.encode(), _b64(self._mac(payload)).encode()):
            return None
        try:
            data = json.loads(_unb64(payload))
            claims = DocsPass(
                kind=data["k"],
                user_id=data["u"],
                organization_id=data["o"],
                expires_at=datetime.fromtimestamp(data["e"], UTC),
                ticket_id=data.get("j"),
            )
        except (ValueError, KeyError, TypeError, OverflowError, OSError, binascii.Error):
            return None
        if claims.kind != kind or (kind == "ticket") != (claims.ticket_id is not None):
            return None
        if not all(isinstance(v, str) and v for v in (claims.user_id, claims.organization_id)):
            return None
        return claims if now < claims.expires_at else None

    def _sign(self, issued: DocsPass) -> str:
        data: dict[str, object] = {
            "k": issued.kind,
            "u": issued.user_id,
            "o": issued.organization_id,
            "e": int(issued.expires_at.timestamp()),
        }
        if issued.ticket_id is not None:
            data["j"] = issued.ticket_id
        payload = _b64(json.dumps(data, separators=(",", ":"), sort_keys=True).encode())
        return f"{payload}.{_b64(self._mac(payload))}"

    def _mac(self, payload: str) -> bytes:
        return hmac.new(self._key, payload.encode(), hashlib.sha256).digest()


def _second(moment: datetime) -> datetime:
    """The moment as the pass stores it: whole seconds, so what is read is what was issued."""
    return moment.replace(microsecond=0)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
