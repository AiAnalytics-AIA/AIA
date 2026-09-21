"""Identity providers for tests and for local development.

:class:`TestIdentityProvider` is deterministic and offline.
:class:`DevelopmentIdentityProvider` trusts request headers and **refuses to be
constructed outside a local environment**, so the convenience of header-based
identity cannot reach a deployed environment through a configuration mistake.

:func:`issue_test_jwt` signs a real RS256 token with a locally generated key, so
the Cognito validation contract is exercised against genuine signed tokens with
no AWS account involved.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .base import ExpiredToken, InvalidToken, VerifiedIdentity

__all__ = [
    "DevelopmentIdentityForbidden",
    "DevelopmentIdentityProvider",
    "TestIdentityProvider",
    "generate_test_keypair",
    "issue_test_jwt",
]


@dataclass
class TestIdentityProvider:
    """A deterministic identity provider for tests.

    Tokens are opaque handles registered in advance, so a test can say "this
    caller is authenticated as X" without a signing key or a network call. The
    Cognito JWT contract is verified separately against real signed tokens via
    :func:`issue_test_jwt`; this provider exists so the many tests that merely
    need *an* authenticated caller do not each pay for crypto.
    """

    # Tells pytest this is not a test suite despite the Test* name, which the
    # architecture brief specifies.
    __test__ = False

    identities: dict[str, VerifiedIdentity] = field(default_factory=dict)
    expired_tokens: set[str] = field(default_factory=set)

    @property
    def name(self) -> str:
        return "test"

    def register(
        self,
        token: str,
        *,
        subject: str,
        email: str | None = None,
        display_name: str | None = None,
        groups: frozenset[str] = frozenset(),
    ) -> VerifiedIdentity:
        """Register a token and the identity it proves."""
        identity = VerifiedIdentity(
            subject=subject,
            email=email,
            display_name=display_name,
            issuer="test://identity",
            provider_groups=groups,
        )
        self.identities[token] = identity
        return identity

    def expire(self, token: str) -> None:
        """Mark a registered token as expired, to exercise the refresh path."""
        self.expired_tokens.add(token)

    def verify(self, credential: str) -> VerifiedIdentity:
        """Verify a registered token."""
        token = (credential or "").strip()
        if not token:
            raise InvalidToken("empty credential", reason="missing_token")
        if token in self.expired_tokens:
            raise ExpiredToken()
        try:
            return self.identities[token]
        except KeyError as exc:
            raise InvalidToken("unknown test token", reason="bad_signature") from exc


class DevelopmentIdentityForbidden(RuntimeError):
    """Raised when header-based identity is constructed outside local development.

    This is a startup failure rather than a request failure on purpose: a
    deployment configured this way must fail its health check, not serve traffic
    while trusting client-supplied identity headers.
    """


@dataclass
class DevelopmentIdentityProvider:
    """Trusts ``X-AIA-Subject`` / ``X-AIA-Email`` headers. Local development only.

    This exists so a developer can work without standing up Cognito. It is not a
    fallback: constructing it requires ``allow_insecure_local_identity=True``,
    which :class:`aia_api.config.Settings` only permits when the environment is
    ``local`` or ``test``. Combined with the production auth-gate middleware,
    there are two independent barriers between this class and a deployed
    environment.

    The credential passed to :meth:`verify` is the header value; there is no
    signature, which is precisely why it cannot leave a developer's machine.
    """

    allow_insecure_local_identity: bool = False
    default_email_domain: str = "localhost"

    def __post_init__(self) -> None:
        if not self.allow_insecure_local_identity:
            raise DevelopmentIdentityForbidden(
                "DevelopmentIdentityProvider requires "
                "allow_insecure_local_identity=True, which is only granted in "
                "local and test environments. Configure Cognito instead."
            )

    @property
    def name(self) -> str:
        return "development-insecure"

    def verify(self, credential: str) -> VerifiedIdentity:
        """Treat the credential as a subject identifier, unverified."""
        subject = (credential or "").strip()
        if not subject:
            raise InvalidToken("development identity requires a subject", reason="missing_token")
        # A subject that looks like an email doubles as the email, which keeps
        # local setup to a single header.
        email = subject if "@" in subject else f"{subject}@{self.default_email_domain}"
        return VerifiedIdentity(
            subject=subject,
            email=email,
            display_name=email.split("@")[0],
            issuer="development://insecure",
        )


# --------------------------------------------------------------------------- #
# Real signed tokens, without AWS
# --------------------------------------------------------------------------- #


def generate_test_keypair(kid: str = "test-key-1") -> tuple[Any, Any, str]:
    """Generate an RSA key pair for signing test tokens.

    Returns ``(private_key, public_key, kid)``. 2048 bits: large enough to be a
    realistic RS256 key, small enough not to slow the suite down.
    """
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key(), kid


def issue_test_jwt(
    private_key: Any,
    *,
    kid: str,
    issuer: str,
    audience: str,
    subject: str = "cognito-subject-1",
    email: str | None = "researcher@art-chain.io",
    token_use: str = "id",
    expires_in: int = 3600,
    issued_at: int | None = None,
    algorithm: str = "RS256",
    extra_claims: dict[str, Any] | None = None,
    omit: tuple[str, ...] = (),
) -> str:
    """Sign a Cognito-shaped JWT with a local key.

    ``omit`` drops named claims and ``extra_claims`` overrides them, so a test can
    construct the malformed tokens a real attacker would send -- wrong audience,
    wrong issuer, wrong ``token_use``, missing ``exp`` -- and assert each is
    rejected.
    """
    import jwt

    now = issued_at if issued_at is not None else int(time.time())
    claims: dict[str, Any] = {
        "sub": subject,
        "iss": issuer,
        "aud": audience,
        "token_use": token_use,
        "iat": now,
        "exp": now + expires_in,
        "auth_time": now,
    }
    if email:
        claims["email"] = email
        claims["email_verified"] = True
    if token_use == "access":
        # Access tokens carry the app client in `client_id`, not `aud`.
        claims["client_id"] = audience
        claims.pop("aud", None)
    if extra_claims:
        claims.update(extra_claims)
    for name in omit:
        claims.pop(name, None)

    return jwt.encode(claims, private_key, algorithm=algorithm, headers={"kid": kid})
