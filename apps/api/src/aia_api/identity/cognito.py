"""Amazon Cognito identity provider.

AIA authenticates through a Cognito User Pool federated to the company Google
Workspace directory. There are no local AIA passwords.

The JWT validation contract implemented here is fully testable without AWS: the
provider takes a :class:`KeySource`, and tests inject a local one holding a
generated RSA key. Nothing in this module imports an AWS SDK -- Cognito's JWKS
endpoint is plain HTTPS, so ``boto3`` is not needed to verify a token, and not
depending on it keeps the API container smaller and the tests offline.

**Validation performed**, in order, because a cheap check should reject before an
expensive one:

1. the token parses and its header names a signing algorithm we accept (RS256);
2. the ``kid`` resolves to a key in the pool's JWKS;
3. the signature verifies;
4. ``iss`` equals this pool's issuer exactly;
5. ``token_use`` is the expected kind (``id`` or ``access``);
6. the audience claim matches the configured app client;
7. ``exp`` and ``nbf`` are satisfied, with a small clock skew allowance.

Algorithm confusion is prevented by passing an explicit allow-list to the decoder
rather than trusting the token's own ``alg`` header.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from .base import (
    ExpiredToken,
    IdentityProviderUnavailable,
    InvalidToken,
    VerifiedIdentity,
)

__all__ = [
    "CognitoIdentityProvider",
    "CognitoSettings",
    "JwksKeySource",
    "KeySource",
    "StaticKeySource",
]

logger = logging.getLogger("aia.identity.cognito")

# Only asymmetric RS256 is accepted. Cognito signs with RS256; accepting anything
# symmetric would let a token signed with a *public* key validate.
_ALLOWED_ALGORITHMS = ("RS256",)

# Tolerance for clock drift between this host and Cognito.
_LEEWAY_SECONDS = 30


@dataclass(frozen=True, slots=True)
class CognitoSettings:
    """Configuration for one Cognito User Pool app client."""

    region: str
    user_pool_id: str
    client_id: str
    # `id` tokens carry user attributes such as email; `access` tokens carry
    # scopes. AIA needs the identity, so id tokens are the default.
    token_use: Literal["id", "access"] = "id"
    jwks_cache_seconds: int = 3600

    @property
    def issuer(self) -> str:
        """The exact ``iss`` value this pool produces."""
        return f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"

    @property
    def jwks_url(self) -> str:
        """The pool's public signing keys."""
        return f"{self.issuer}/.well-known/jwks.json"

    def validate(self) -> None:
        """Fail fast on obviously unusable configuration."""
        missing = [
            name for name in ("region", "user_pool_id", "client_id") if not getattr(self, name)
        ]
        if missing:
            raise ValueError(f"Cognito configuration is incomplete: {', '.join(missing)}")


class KeySource(Protocol):
    """Supplies the signing keys a token may have been signed with."""

    def key_for(self, kid: str) -> Any:
        """Return a verification key for ``kid``, or raise :class:`InvalidToken`."""
        ...


@dataclass
class StaticKeySource:
    """A fixed set of keys, for tests and for offline verification.

    This is what makes the Cognito contract testable with no AWS account: a test
    generates a key pair, signs a token, and hands the public key to the provider.
    """

    keys: dict[str, Any] = field(default_factory=dict)

    def key_for(self, kid: str) -> Any:
        try:
            return self.keys[kid]
        except KeyError as exc:
            raise InvalidToken(f"unknown signing key {kid!r}", reason="unknown_kid") from exc


class JwksKeySource:
    """Fetches and caches a Cognito pool's JWKS over HTTPS.

    Cached because verifying every request against a network call would make
    authentication as slow and as fragile as the network. A cache miss on an
    unknown ``kid`` forces one refresh, so a key rotation is picked up without
    waiting for the TTL -- but at most once per ``min_refresh_interval`` seconds,
    so an attacker sending random ``kid`` values cannot turn this into a
    request amplifier against Cognito.
    """

    def __init__(
        self,
        jwks_url: str,
        *,
        cache_seconds: int = 3600,
        timeout_seconds: float = 5.0,
        min_refresh_interval: float = 60.0,
    ) -> None:
        self._url = jwks_url
        self._cache_seconds = cache_seconds
        self._timeout = timeout_seconds
        self._min_refresh_interval = min_refresh_interval
        self._keys: dict[str, Any] = {}
        self._fetched_at = 0.0
        self._last_attempt = 0.0
        self._lock = threading.Lock()

    def _fetch(self) -> dict[str, Any]:
        """Fetch the JWKS document."""
        try:
            request = urllib.request.Request(self._url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.warning(
                "jwks fetch failed", extra={"context": {"url": self._url}}, exc_info=True
            )
            raise IdentityProviderUnavailable("could not fetch signing keys") from exc

        from jwt import PyJWK

        keys: dict[str, Any] = {}
        for entry in payload.get("keys", []):
            kid = entry.get("kid")
            if not kid:
                continue
            try:
                keys[kid] = PyJWK.from_dict(entry).key
            except Exception:
                logger.warning("skipping unusable jwks entry", extra={"context": {"kid": kid}})
        if not keys:
            raise IdentityProviderUnavailable("signing key set is empty")
        return keys

    def _refresh_locked(self) -> None:
        self._keys = self._fetch()
        self._fetched_at = time.monotonic()

    def key_for(self, kid: str) -> Any:
        now = time.monotonic()
        stale = (now - self._fetched_at) > self._cache_seconds

        with self._lock:
            if not self._keys or stale:
                self._last_attempt = now
                self._refresh_locked()

            if kid in self._keys:
                return self._keys[kid]

            # Unknown kid: refresh once, rate-limited, to pick up a rotation.
            if (now - self._last_attempt) >= self._min_refresh_interval:
                self._last_attempt = now
                self._refresh_locked()
                if kid in self._keys:
                    return self._keys[kid]

        raise InvalidToken(f"unknown signing key {kid!r}", reason="unknown_kid")


class CognitoIdentityProvider:
    """Verifies Cognito-issued JWTs.

    Stateless and safe to share across requests; the only mutable state is the
    signing-key cache inside the key source.
    """

    def __init__(self, settings: CognitoSettings, key_source: KeySource | None = None) -> None:
        settings.validate()
        self._settings = settings
        self._keys = key_source or JwksKeySource(
            settings.jwks_url, cache_seconds=settings.jwks_cache_seconds
        )

    @property
    def name(self) -> str:
        return "cognito"

    @property
    def settings(self) -> CognitoSettings:
        return self._settings

    def verify(self, credential: str) -> VerifiedIdentity:
        """Verify a Cognito JWT and return the identity it proves."""
        import jwt

        token = (credential or "").strip()
        if not token:
            raise InvalidToken("empty credential", reason="missing_token")

        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise InvalidToken("malformed token", reason="malformed") from exc

        algorithm = header.get("alg")
        if algorithm not in _ALLOWED_ALGORITHMS:
            # Reject before touching keys. An attacker choosing "none" or an HMAC
            # algorithm must not reach the decoder at all.
            raise InvalidToken(
                f"unsupported signing algorithm {algorithm!r}", reason="bad_algorithm"
            )

        kid = header.get("kid")
        if not kid:
            raise InvalidToken("token header has no key id", reason="missing_kid")

        key = self._keys.key_for(kid)

        # Cognito puts the app client id in `aud` for id tokens and in `client_id`
        # for access tokens, so audience verification is done explicitly below
        # rather than by the decoder.
        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=list(_ALLOWED_ALGORITHMS),
                issuer=self._settings.issuer,
                leeway=_LEEWAY_SECONDS,
                options={
                    "require": ["exp", "iss", "sub"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iss": True,
                    "verify_aud": False,
                },
            )
        except jwt.ExpiredSignatureError as exc:
            raise ExpiredToken() from exc
        except jwt.InvalidIssuerError as exc:
            raise InvalidToken("issuer mismatch", reason="bad_issuer") from exc
        except jwt.PyJWTError as exc:
            raise InvalidToken("token verification failed", reason="bad_signature") from exc

        self._check_token_use(claims)
        self._check_audience(claims)

        return VerifiedIdentity(
            subject=str(claims.get("sub") or ""),
            email=(claims.get("email") or None),
            display_name=(
                claims.get("name")
                or claims.get("given_name")
                or (claims.get("email") or "").split("@")[0]
                or None
            ),
            issuer=self._settings.issuer,
            provider_groups=frozenset(claims.get("cognito:groups") or ()),
        )

    def _check_token_use(self, claims: dict[str, Any]) -> None:
        """Reject a token of the wrong kind.

        An access token and an id token from the same pool are both validly
        signed. Accepting either interchangeably would mean an access token with
        no user attributes could authenticate a session, so the kind is pinned.
        """
        actual = claims.get("token_use")
        if actual != self._settings.token_use:
            raise InvalidToken(
                f"expected a {self._settings.token_use} token, got {actual!r}",
                reason="wrong_token_use",
            )

    def _check_audience(self, claims: dict[str, Any]) -> None:
        """Verify the token was issued for this app client."""
        expected = self._settings.client_id
        if self._settings.token_use == "id":
            audience = claims.get("aud")
            values = audience if isinstance(audience, list) else [audience]
        else:
            values = [claims.get("client_id")]

        if expected not in [v for v in values if v]:
            raise InvalidToken("audience mismatch", reason="bad_audience")
