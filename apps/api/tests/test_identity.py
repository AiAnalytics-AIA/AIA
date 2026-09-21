"""Tests for the identity-provider boundary and the Cognito JWT contract.

Every test here runs offline against locally signed tokens. That is the point:
the validation contract must be verifiable without an AWS account, so a mistake
in it is caught in CI rather than in staging.

The attack cases are the reason this file is long. A JWT validator that accepts
the wrong audience, the wrong issuer, an unsigned token or an attacker-chosen
algorithm is worse than no authentication, because it looks like it works.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from aia_api.identity import (
    CognitoIdentityProvider,
    CognitoSettings,
    DevelopmentIdentityForbidden,
    DevelopmentIdentityProvider,
    ExpiredToken,
    IdentityProvider,
    IdentityProviderUnavailable,
    InvalidToken,
    StaticKeySource,
    TestIdentityProvider,
    VerifiedIdentity,
    generate_test_keypair,
    issue_test_jwt,
)

REGION = "eu-central-1"
POOL = "eu-central-1_TestPool"
CLIENT = "test-app-client-id"


@pytest.fixture(scope="module")
def keypair() -> tuple[Any, Any, str]:
    """An RSA key pair, generated once: 2048-bit keygen is not free."""
    return generate_test_keypair("kid-primary")


@pytest.fixture
def settings() -> CognitoSettings:
    return CognitoSettings(region=REGION, user_pool_id=POOL, client_id=CLIENT)


@pytest.fixture
def provider(settings: CognitoSettings, keypair: tuple[Any, Any, str]) -> CognitoIdentityProvider:
    _, public, kid = keypair
    return CognitoIdentityProvider(settings, StaticKeySource({kid: public}))


@pytest.fixture
def token_factory(settings: CognitoSettings, keypair: tuple[Any, Any, str]):
    """Issue a valid-by-default Cognito-shaped token, overridable per test."""
    private, _, kid = keypair

    def issue(**overrides: Any) -> str:
        params: dict[str, Any] = {
            "kid": kid,
            "issuer": settings.issuer,
            "audience": settings.client_id,
        }
        params.update(overrides)
        return issue_test_jwt(private, **params)

    return issue


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #


def test_issuer_and_jwks_url_match_cognito_format(settings: CognitoSettings) -> None:
    """The issuer must match Cognito's exactly or every token will be rejected."""
    assert settings.issuer == f"https://cognito-idp.{REGION}.amazonaws.com/{POOL}"
    assert settings.jwks_url == f"{settings.issuer}/.well-known/jwks.json"


def test_incomplete_configuration_fails_fast() -> None:
    """A half-configured provider must not be constructible."""
    for kwargs in (
        {"region": "", "user_pool_id": POOL, "client_id": CLIENT},
        {"region": REGION, "user_pool_id": "", "client_id": CLIENT},
        {"region": REGION, "user_pool_id": POOL, "client_id": ""},
    ):
        with pytest.raises(ValueError, match="incomplete"):
            CognitoIdentityProvider(CognitoSettings(**kwargs))  # type: ignore[arg-type]


def test_providers_satisfy_the_protocol(
    provider: CognitoIdentityProvider,
) -> None:
    """Every provider is interchangeable behind one interface."""
    assert isinstance(provider, IdentityProvider)
    assert isinstance(TestIdentityProvider(), IdentityProvider)
    assert isinstance(
        DevelopmentIdentityProvider(allow_insecure_local_identity=True), IdentityProvider
    )


# --------------------------------------------------------------------------- #
# The happy path
# --------------------------------------------------------------------------- #


def test_valid_token_yields_the_identity(
    provider: CognitoIdentityProvider, token_factory: Any, settings: CognitoSettings
) -> None:
    """A correctly signed token produces the identity it claims."""
    token = token_factory(subject="cognito-sub-abc", email="lead@art-chain.io")
    identity = provider.verify(token)

    assert identity.subject == "cognito-sub-abc"
    assert identity.email == "lead@art-chain.io"
    assert identity.issuer == settings.issuer


def test_display_name_falls_back_sensibly(
    provider: CognitoIdentityProvider, token_factory: Any
) -> None:
    """A directory without a name attribute still yields something usable."""
    assert (
        provider.verify(token_factory(extra_claims={"name": "Jana Nováková"})).display_name
        == "Jana Nováková"
    )
    assert provider.verify(token_factory(email="ondrej@art-chain.io")).display_name == "ondrej"


def test_identity_carries_no_authorization(
    provider: CognitoIdentityProvider, token_factory: Any
) -> None:
    """A token must not be able to grant itself access.

    This is the central design guarantee: even when Cognito asserts group
    membership, the verified identity exposes it only as audit metadata, and no
    field on it can express an organization role, a client or a study.
    """
    token = token_factory(
        extra_claims={"cognito:groups": ["admins", "superusers"], "custom:role": "OWNER"}
    )
    identity = provider.verify(token)

    assert identity.provider_groups == frozenset({"admins", "superusers"})

    fields = set(VerifiedIdentity.__dataclass_fields__)
    for forbidden in (
        "role",
        "roles",
        "organization_role",
        "client_id",
        "study_id",
        "permissions",
    ):
        assert forbidden not in fields, f"VerifiedIdentity must not carry {forbidden}"


def test_access_tokens_are_supported_when_configured(keypair: tuple[Any, Any, str]) -> None:
    """An access-token pool validates the app client from `client_id`, not `aud`."""
    private, public, kid = keypair
    settings = CognitoSettings(
        region=REGION, user_pool_id=POOL, client_id=CLIENT, token_use="access"
    )
    provider = CognitoIdentityProvider(settings, StaticKeySource({kid: public}))

    token = issue_test_jwt(
        private,
        kid=kid,
        issuer=settings.issuer,
        audience=CLIENT,
        token_use="access",
        email=None,
    )
    assert provider.verify(token).subject == "cognito-subject-1"


# --------------------------------------------------------------------------- #
# Rejection cases
# --------------------------------------------------------------------------- #


def test_expired_token_is_distinguished_from_invalid(
    provider: CognitoIdentityProvider, token_factory: Any
) -> None:
    """Expiry must be its own error so a client refreshes instead of giving up."""
    token = token_factory(issued_at=int(time.time()) - 7200, expires_in=3600)
    with pytest.raises(ExpiredToken) as exc:
        provider.verify(token)
    assert exc.value.reason == "expired_token"


def test_token_expiring_within_clock_skew_is_accepted(
    provider: CognitoIdentityProvider, token_factory: Any
) -> None:
    """A few seconds of clock drift must not log everyone out."""
    token = token_factory(issued_at=int(time.time()) - 3605, expires_in=3600)
    assert provider.verify(token).subject


def test_wrong_audience_is_rejected(provider: CognitoIdentityProvider, token_factory: Any) -> None:
    """A token for a different app client must not authenticate here.

    Without this check, any Cognito pool the attacker controls an app client in
    could mint tokens for AIA.
    """
    with pytest.raises(InvalidToken) as exc:
        provider.verify(token_factory(audience="some-other-app-client"))
    assert exc.value.reason == "bad_audience"


def test_wrong_issuer_is_rejected(provider: CognitoIdentityProvider, token_factory: Any) -> None:
    """A token from another user pool must not authenticate here."""
    with pytest.raises(InvalidToken) as exc:
        provider.verify(
            token_factory(issuer=f"https://cognito-idp.{REGION}.amazonaws.com/{REGION}_EvilPool")
        )
    assert exc.value.reason == "bad_issuer"


def test_wrong_token_use_is_rejected(provider: CognitoIdentityProvider, token_factory: Any) -> None:
    """An access token must not stand in for an id token.

    Both are validly signed by the same pool, so only the `token_use` claim
    separates them -- and an access token carries no user attributes.
    """
    with pytest.raises(InvalidToken) as exc:
        provider.verify(token_factory(token_use="access"))
    assert exc.value.reason == "wrong_token_use"


def test_token_signed_by_an_unknown_key_is_rejected(
    provider: CognitoIdentityProvider, settings: CognitoSettings
) -> None:
    """A token signed with a key that is not in the pool's JWKS is rejected."""
    other_private, _, other_kid = generate_test_keypair("attacker-key")
    token = issue_test_jwt(other_private, kid=other_kid, issuer=settings.issuer, audience=CLIENT)
    with pytest.raises(InvalidToken) as exc:
        provider.verify(token)
    assert exc.value.reason == "unknown_kid"


def test_token_signed_by_a_different_key_under_a_known_kid_is_rejected(
    provider: CognitoIdentityProvider, settings: CognitoSettings, keypair: tuple[Any, Any, str]
) -> None:
    """Claiming a known key id does not help without the matching private key."""
    _, _, kid = keypair
    attacker_private, _, _ = generate_test_keypair("irrelevant")
    token = issue_test_jwt(attacker_private, kid=kid, issuer=settings.issuer, audience=CLIENT)
    with pytest.raises(InvalidToken) as exc:
        provider.verify(token)
    assert exc.value.reason == "bad_signature"


def test_unsigned_token_is_rejected(
    provider: CognitoIdentityProvider, settings: CognitoSettings, keypair: tuple[Any, Any, str]
) -> None:
    """The classic `alg: none` attack must be refused before key lookup."""
    import jwt

    _, _, kid = keypair
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "attacker",
            "iss": settings.issuer,
            "aud": CLIENT,
            "token_use": "id",
            "exp": now + 3600,
        },
        key="",
        algorithm="none",
        headers={"kid": kid},
    )
    with pytest.raises(InvalidToken) as exc:
        provider.verify(token)
    assert exc.value.reason == "bad_algorithm"


def test_symmetric_algorithm_confusion_is_rejected(
    provider: CognitoIdentityProvider, settings: CognitoSettings, keypair: tuple[Any, Any, str]
) -> None:
    """An HS256 token must not verify against the RSA public key.

    This is the algorithm-confusion attack: the public key is, by definition,
    public, so if HS256 were accepted anyone could forge a token with it. The
    explicit algorithm allow-list is what prevents it.
    """
    import base64
    import hashlib
    import hmac
    import json as jsonlib

    from cryptography.hazmat.primitives import serialization

    _, public, kid = keypair
    public_pem = public.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    # Hand-rolled: PyJWT refuses to *encode* HS256 with a PEM public key, so the
    # attack token has to be assembled directly -- which is exactly what an
    # attacker would do.
    def b64(raw: bytes) -> bytes:
        return base64.urlsafe_b64encode(raw).rstrip(b"=")

    now = int(time.time())
    header = b64(jsonlib.dumps({"alg": "HS256", "typ": "JWT", "kid": kid}).encode())
    payload = b64(
        jsonlib.dumps(
            {
                "sub": "attacker",
                "iss": settings.issuer,
                "aud": CLIENT,
                "token_use": "id",
                "exp": now + 3600,
            }
        ).encode()
    )
    signing_input = header + b"." + payload
    signature = b64(hmac.new(public_pem, signing_input, hashlib.sha256).digest())
    token = (signing_input + b"." + signature).decode()

    with pytest.raises(InvalidToken) as exc:
        provider.verify(token)
    assert exc.value.reason == "bad_algorithm"


def test_token_without_a_key_id_is_rejected(
    provider: CognitoIdentityProvider, settings: CognitoSettings, keypair: tuple[Any, Any, str]
) -> None:
    """Without a `kid` there is no way to choose a key, so the token is refused."""
    import jwt

    private, _, _ = keypair
    now = int(time.time())
    token = jwt.encode(
        {
            "sub": "x",
            "iss": settings.issuer,
            "aud": CLIENT,
            "token_use": "id",
            "exp": now + 3600,
        },
        private,
        algorithm="RS256",
    )
    with pytest.raises(InvalidToken) as exc:
        provider.verify(token)
    assert exc.value.reason == "missing_kid"


@pytest.mark.parametrize("claim", ["exp", "sub", "iss"])
def test_required_claims_are_enforced(
    provider: CognitoIdentityProvider, token_factory: Any, claim: str
) -> None:
    """A token missing a required claim is rejected, not defaulted."""
    with pytest.raises(InvalidToken):
        provider.verify(token_factory(omit=(claim,)))


@pytest.mark.parametrize(
    "credential",
    ["", "   ", "not-a-jwt", "a.b", "a.b.c", "Bearer something", "null", "."],
)
def test_malformed_credentials_are_rejected(
    provider: CognitoIdentityProvider, credential: str
) -> None:
    """Garbage input produces a clean rejection, never a crash."""
    with pytest.raises(InvalidToken):
        provider.verify(credential)


def test_error_messages_do_not_leak_the_reason_to_clients(
    provider: CognitoIdentityProvider, token_factory: Any
) -> None:
    """The client-facing message is generic; the specific reason goes to logs.

    Telling a caller whether the audience or the issuer was wrong helps them
    calibrate an attack.
    """
    with pytest.raises(InvalidToken) as exc:
        provider.verify(token_factory(audience="wrong"))

    assert exc.value.client_message == "Authentication failed."
    assert "audience" not in exc.value.client_message


def test_verified_identity_requires_a_subject() -> None:
    """An identity with no subject cannot be bound to a user record."""
    with pytest.raises(InvalidToken):
        VerifiedIdentity(subject="")


# --------------------------------------------------------------------------- #
# Key source behaviour
# --------------------------------------------------------------------------- #


def test_unavailable_key_source_is_not_an_authentication_failure() -> None:
    """A JWKS outage is a 503, not a 401.

    Returning 401 would teach clients that an outage means "sign in again",
    producing a login storm exactly when the provider is already struggling.
    """

    class BrokenKeys:
        def key_for(self, kid: str) -> Any:
            raise IdentityProviderUnavailable()

    provider = CognitoIdentityProvider(
        CognitoSettings(region=REGION, user_pool_id=POOL, client_id=CLIENT), BrokenKeys()
    )
    private, _, kid = generate_test_keypair()
    token = issue_test_jwt(private, kid=kid, issuer=provider.settings.issuer, audience=CLIENT)

    with pytest.raises(IdentityProviderUnavailable):
        provider.verify(token)


def test_key_rotation_is_picked_up(settings: CognitoSettings) -> None:
    """A new signing key becomes usable without a restart."""
    old_private, old_public, old_kid = generate_test_keypair("kid-old")
    new_private, new_public, new_kid = generate_test_keypair("kid-new")

    source = StaticKeySource({old_kid: old_public})
    provider = CognitoIdentityProvider(settings, source)

    old_token = issue_test_jwt(old_private, kid=old_kid, issuer=settings.issuer, audience=CLIENT)
    new_token = issue_test_jwt(new_private, kid=new_kid, issuer=settings.issuer, audience=CLIENT)

    assert provider.verify(old_token).subject
    with pytest.raises(InvalidToken):
        provider.verify(new_token)

    source.keys[new_kid] = new_public
    assert provider.verify(new_token).subject


# --------------------------------------------------------------------------- #
# The development provider must be impossible to enable by accident
# --------------------------------------------------------------------------- #


def test_development_provider_refuses_to_construct_by_default() -> None:
    """Header-based identity is opt-in, and the opt-in is not a default.

    A deployment that reaches for this class without the explicit flag fails at
    startup rather than serving traffic while trusting client headers.
    """
    with pytest.raises(DevelopmentIdentityForbidden) as exc:
        DevelopmentIdentityProvider()
    assert "local and test environments" in str(exc.value)

    with pytest.raises(DevelopmentIdentityForbidden):
        DevelopmentIdentityProvider(allow_insecure_local_identity=False)


def test_development_provider_names_itself_insecure() -> None:
    """The name reaches logs and diagnostics, so it must be unmistakable."""
    provider = DevelopmentIdentityProvider(allow_insecure_local_identity=True)
    assert provider.name == "development-insecure"


def test_development_provider_accepts_a_subject_header() -> None:
    """Local development needs exactly one header to identify a user."""
    provider = DevelopmentIdentityProvider(allow_insecure_local_identity=True)

    identity = provider.verify("researcher@art-chain.io")
    assert identity.subject == "researcher@art-chain.io"
    assert identity.email == "researcher@art-chain.io"
    assert identity.issuer == "development://insecure"

    bare = provider.verify("alice")
    assert bare.email == "alice@localhost"


def test_development_provider_still_requires_a_subject() -> None:
    """Even the insecure provider does not authenticate an anonymous caller."""
    provider = DevelopmentIdentityProvider(allow_insecure_local_identity=True)
    for bad in ("", "   "):
        with pytest.raises(InvalidToken):
            provider.verify(bad)


# --------------------------------------------------------------------------- #
# The test provider
# --------------------------------------------------------------------------- #


def test_test_provider_round_trip() -> None:
    """Registered tokens verify; unregistered ones do not."""
    provider = TestIdentityProvider()
    provider.register("tok-1", subject="sub-1", email="a@art-chain.io")

    assert provider.verify("tok-1").subject == "sub-1"
    with pytest.raises(InvalidToken):
        provider.verify("tok-unknown")


def test_test_provider_can_simulate_expiry() -> None:
    """The refresh path needs to be exercisable without waiting an hour."""
    provider = TestIdentityProvider()
    provider.register("tok-1", subject="sub-1")
    provider.expire("tok-1")

    with pytest.raises(ExpiredToken):
        provider.verify("tok-1")
