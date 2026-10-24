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
from urllib.parse import parse_qs, urlsplit

import jwt

#: A config is opened when the pane loads it; the pane asks for a new one each time it opens.
CONFIG_LIFETIME: Final = timedelta(hours=12)
#: A document URL is fetched when the editor opens; a co-editor joining later gets a new one.
DOCUMENT_LIFETIME: Final = timedelta(minutes=30)
#: A callback URL lasts as long as a session may: a day idle closes it, so a week is ample.
CALLBACK_LIFETIME: Final = timedelta(days=7)
_URL_LABEL: Final = b"aia-report-editor-url-1"
#: What AIA reads of a callback; anything else it carries, registered claims included, is not.
CALLBACK_FIELDS: Final = ("key", "status", "url", "users", "lastsave")
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

    def sign_config(self, config: dict[str, Any], *, now: datetime) -> str:
        """``config`` signed as the Document Server checks it (``config.token``), for
        :data:`CONFIG_LIFETIME`."""
        claims = {**config, "exp": int((now + CONFIG_LIFETIME).timestamp())}
        return jwt.encode(claims, self._secret, algorithm=_ALGORITHM)

    def read_onlyoffice(self, token: str | None, *, url_path: str | None = None) -> dict[str, Any]:
        """The payload of a JWT the Document Server signed, or :class:`TokenRefused`.

        The browser holds a JWT under the same secret, its config's, so a signature alone does
        not show the request is the Document Server's: a token shaped as a config (``document``
        or ``editorConfig``) is refused, and with ``url_path`` the token must name the URL being
        fetched (ONLYOFFICE signs it as ``url``, or ``payload.url``), its path and its query's
        ``token``."""
        if not token:
            raise TokenRefused("no token")
        try:
            claims: dict[str, Any] = jwt.decode(token, self._secret, algorithms=[_ALGORITHM])
        except jwt.PyJWTError as exc:
            raise TokenRefused(str(exc)) from exc
        if "document" in claims or "editorConfig" in claims:
            raise TokenRefused("a config's token, not the Document Server's")
        if url_path is not None and not _names(claims, url_path):
            raise TokenRefused("the token names another URL")
        return claims

    def read_callback(self, body_token: Any, header_token: str | None) -> dict[str, Any]:
        """The callback a Document Server signed, or :class:`TokenRefused`.

        ONLYOFFICE signs a callback once, in the body (``token``, the body's fields beside
        ``iat`` and ``exp``) or in the header (the body as ``payload``, which it may trim when the
        header grows too long), as its ``inBody`` setting says. Either is read; both, when sent,
        must agree on every field AIA acts on (:data:`CALLBACK_FIELDS`) that each carries. The
        signed fields are returned, never the body's own."""
        signed: list[dict[str, Any]] = []
        if body_token is not None:
            if not isinstance(body_token, str):
                raise TokenRefused("a body token is a string")
            signed.append(self.read_onlyoffice(body_token))
        if header_token is not None:
            nested = self.read_onlyoffice(header_token).get("payload")
            if not isinstance(nested, dict):
                raise TokenRefused("a header token signs the body as its payload")
            signed.append(nested)
        if not signed:
            raise TokenRefused("no token")
        first = signed[0]
        for other in signed[1:]:
            if any(f in first and f in other and first[f] != other[f] for f in CALLBACK_FIELDS):
                raise TokenRefused("the body's and the header's tokens disagree")
        return {f: first[f] for f in CALLBACK_FIELDS if f in first}

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


def _names(claims: dict[str, Any], url_path: str) -> bool:
    """Whether ``claims`` name ``url_path`` (a path and its query) as the URL fetched."""
    nested = claims.get("payload")
    url = claims.get("url") or (nested.get("url") if isinstance(nested, dict) else None)
    if not isinstance(url, str):
        return False
    signed, asked = urlsplit(url), urlsplit(url_path)
    return signed.path == asked.path and parse_qs(signed.query).get("token") == parse_qs(
        asked.query
    ).get("token")


def bearer(header: str | None) -> str | None:
    """The token of an ``Authorization: Bearer <token>`` header, else ``None``."""
    if header and header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None
