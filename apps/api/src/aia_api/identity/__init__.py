"""Identity providers.

Authentication is answered here; authorization is answered by
``aia_core.application.scope`` from PostgreSQL. A token proves identity and
nothing else -- see ``base.py`` for why that separation matters.
"""

from .base import (
    ExpiredToken,
    IdentityError,
    IdentityProvider,
    IdentityProviderUnavailable,
    InvalidToken,
    VerifiedIdentity,
)
from .cognito import (
    CognitoIdentityProvider,
    CognitoSettings,
    JwksKeySource,
    KeySource,
    StaticKeySource,
)
from .testing import (
    DevelopmentIdentityForbidden,
    DevelopmentIdentityProvider,
    TestIdentityProvider,
    generate_test_keypair,
    issue_test_jwt,
)

__all__ = [
    "CognitoIdentityProvider",
    "CognitoSettings",
    "DevelopmentIdentityForbidden",
    "DevelopmentIdentityProvider",
    "ExpiredToken",
    "IdentityError",
    "IdentityProvider",
    "IdentityProviderUnavailable",
    "InvalidToken",
    "JwksKeySource",
    "KeySource",
    "StaticKeySource",
    "TestIdentityProvider",
    "VerifiedIdentity",
    "generate_test_keypair",
    "issue_test_jwt",
]
