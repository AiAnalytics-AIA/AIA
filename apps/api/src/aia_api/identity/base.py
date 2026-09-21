"""The identity-provider boundary.

Authentication answers *who the user is*. Authorization -- which organization,
which clients, which studies, at which role -- is AIA's own question, answered
from PostgreSQL. This split is deliberate and load-bearing:

* A token proves identity. It does **not** carry roles, client ids or study ids,
  so a token cannot grant itself access to a client. If Cognito were
  misconfigured tomorrow to add a group claim, nothing here would start trusting
  it.
* Because authorization is ours, revoking access takes effect on the next
  request rather than at token expiry.

:class:`IdentityProvider` is the only seam. Production uses
``CognitoIdentityProvider``; tests use ``TestIdentityProvider``; local
development uses ``DevelopmentIdentityProvider``, which refuses to start outside
local environments. Domain and application code never imports an AWS SDK.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = [
    "ExpiredToken",
    "IdentityError",
    "IdentityProvider",
    "IdentityProviderUnavailable",
    "InvalidToken",
    "VerifiedIdentity",
]


class IdentityError(Exception):
    """Base class for authentication failures.

    The message reaching a client is deliberately generic. Telling a caller
    *why* a token failed -- wrong audience, wrong issuer, unknown key -- helps an
    attacker calibrate. The specific reason goes to the logs.
    """

    client_message = "Authentication failed."

    def __init__(self, message: str, *, reason: str = "invalid_token") -> None:
        super().__init__(message)
        self.reason = reason


class InvalidToken(IdentityError):
    """The token is malformed, unsigned, or fails a claim check."""


class ExpiredToken(IdentityError):
    """The token is well-formed but past its expiry.

    Distinguished from :class:`InvalidToken` because a client should refresh and
    retry rather than treat this as a hard failure.
    """

    client_message = "Session expired. Sign in again."

    def __init__(self, message: str = "token expired") -> None:
        super().__init__(message, reason="expired_token")


class IdentityProviderUnavailable(IdentityError):
    """The provider could not be reached to verify the token.

    This is a 503, not a 401: the caller may well be authenticated, and we must
    not teach clients that an outage means "sign in again".
    """

    client_message = "Authentication is temporarily unavailable."

    def __init__(self, message: str = "identity provider unavailable") -> None:
        super().__init__(message, reason="provider_unavailable")


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    """What a verified token proved, and nothing more.

    Note what is absent: no roles, no organization role, no client or study ids,
    no permissions. Those are AIA's to decide. ``subject`` is the provider's
    immutable identifier and is what a user record is bound to, so an email
    change does not create a second account.
    """

    subject: str
    email: str | None = None
    display_name: str | None = None
    # Which provider verified this, recorded on the user for audit and to make a
    # future provider migration visible in the data.
    issuer: str = ""
    # Groups the provider asserted. Captured for audit only -- never consulted
    # for an authorization decision. See the module docstring.
    provider_groups: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.subject:
            raise InvalidToken("token has no subject claim", reason="missing_subject")


@runtime_checkable
class IdentityProvider(Protocol):
    """Verifies a bearer credential and returns the identity it proves.

    Implementations must be safe to share across requests and must not block on
    network I/O in the common path -- a signing-key fetch belongs behind a cache.
    """

    @property
    def name(self) -> str:
        """Short identifier used in logs and diagnostics."""
        ...

    def verify(self, credential: str) -> VerifiedIdentity:
        """Verify a credential, or raise an :class:`IdentityError`.

        ``credential`` is the raw bearer token with the ``Bearer `` prefix already
        stripped. Implementations must not log it.
        """
        ...
