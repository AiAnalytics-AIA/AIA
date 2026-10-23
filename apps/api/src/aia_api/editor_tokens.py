"""What the report editor's routes sign and check (artifact-report RPT8c), pure.

Two kinds of signature, under two keys:

* **ONLYOFFICE's JWT** (HS256 under ``AIA_ONLYOFFICE_JWT_SECRET`` itself, the secret the
  Document Server is configured with): the editor config the API signs, and the token the
  Document Server sends with every request it makes to AIA (its ``Authorization`` header, and a
  callback's body too). It proves the request comes from *that* Document Server.
* **AIA's URL token** (HS256 under a key derived from the same secret, so a JWT ONLYOFFICE would
  accept is never one AIA's URLs do, nor the reverse): the document URL names one version of one
  session for :data:`DOCUMENT_LIFETIME`; the callback URL names one session for
  :data:`CALLBACK_LIFETIME`. It proves the Document Server was handed that URL by AIA for that
  version or session, and nothing else.

The clock is passed in.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Final, Literal

import jwt

#: A document URL is fetched when the editor opens; a co-editor joining later gets a new one.
DOCUMENT_LIFETIME: Final = timedelta(minutes=30)
#: A callback URL lasts as long as a session may: a day idle closes it, so a week is ample.
CALLBACK_LIFETIME: Final = timedelta(days=7)
_URL_LABEL: Final = b"aia-report-editor-url-1"
_ALGORITHM: Final = "HS256"

Kind = Literal["document", "callback"]


class TokenRefused(ValueError):
    """A token that is missing, expired, of another kind, or not signed by the key."""


@dataclass(frozen=True)
class UrlClaim:
    kind: Kind
    document_key: str
    #: The version a document URL serves; ``None`` for a callback URL.
    artifact_id: str | None


class EditorTokens:
    """Signs and reads the editor's tokens under one secret."""

    def __init__(self, secret: str) -> None:
        if len(secret) < 32:
            raise ValueError("the editor's secret must be at least 32 characters")
        self._secret = secret
        self._url_key = hmac.new(secret.encode(), _URL_LABEL, hashlib.sha256).hexdigest()

    # -- ONLYOFFICE's JWT ----------------------------------------------------

    def sign_config(self, config: dict[str, Any]) -> str:
        """``config`` signed as the Document Server checks it (``config.token``)."""
        return jwt.encode(config, self._secret, algorithm=_ALGORITHM)

    def read_onlyoffice(self, token: str | None) -> dict[str, Any]:
        """The payload of a JWT the Document Server signed, or :class:`TokenRefused`."""
        if not token:
            raise TokenRefused("no token")
        try:
            claims: dict[str, Any] = jwt.decode(token, self._secret, algorithms=[_ALGORITHM])
        except jwt.PyJWTError as exc:
            raise TokenRefused(str(exc)) from exc
        return claims

    # -- AIA's URL tokens ----------------------------------------------------

    def url_token(
        self, kind: Kind, *, document_key: str, now: datetime, artifact_id: str | None = None
    ) -> str:
        if (kind == "document") != (artifact_id is not None):
            raise ValueError("a document token names its version; a callback token none")
        lifetime = DOCUMENT_LIFETIME if kind == "document" else CALLBACK_LIFETIME
        claims: dict[str, Any] = {
            "kind": kind,
            "key": document_key,
            "exp": int((now + lifetime).timestamp()),
        }
        if artifact_id is not None:
            claims["artifact"] = artifact_id
        return jwt.encode(claims, self._url_key, algorithm=_ALGORITHM)

    def read_url(self, token: str | None, kind: Kind, *, now: datetime) -> UrlClaim:
        """A URL token of ``kind``, unexpired at ``now``, or :class:`TokenRefused`."""
        if not token:
            raise TokenRefused("no token")
        try:
            claims = jwt.decode(
                token,
                self._url_key,
                algorithms=[_ALGORITHM],
                options={"verify_exp": False, "require": ["exp", "kind", "key"]},
            )
        except jwt.PyJWTError as exc:
            raise TokenRefused(str(exc)) from exc
        if claims["kind"] != kind or int(claims["exp"]) <= int(now.timestamp()):
            raise TokenRefused("expired or of another kind")
        artifact = claims.get("artifact")
        if (kind == "document") != isinstance(artifact, str):
            raise TokenRefused("a document token names one version")
        return UrlClaim(kind, str(claims["key"]), artifact)


def bearer(header: str | None) -> str | None:
    """The token of an ``Authorization: Bearer <token>`` header, else ``None``."""
    if header and header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None
