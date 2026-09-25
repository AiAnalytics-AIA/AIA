"""The AI runtime's composition: one governed gateway over ADR 0010's Bedrock route.

``AIA_AI_RUNTIME_ENABLED`` unset or false: no AI runtime is built and a research run
parks at fieldwork, exactly as before this module existed. Enabled: every key below
must be present and valid, or the worker refuses to start -- there is no default
model id, price, route approval, retention or fictional client, because each of
those is a fact somebody must have checked (ADR 0010 § Verification), and a default
would be a guess stamped as one.

======================================  ============================================
key                                     meaning
======================================  ============================================
AIA_AI_ROUTE_ID                         the route id (ADR 0010: ``bedrock-eu-primary``)
AIA_BEDROCK_REGION                      the source region, ``eu-*`` (``eu-central-1``)
AIA_BEDROCK_MODEL_ID                    the pinned EU inference profile id, ``eu.…:N``
AIA_AI_POLICY_VERSION                   the model policy version recorded on every call
AIA_BEDROCK_INPUT_USD_PER_MTOK          price, from the Bedrock pricing page, dated
AIA_BEDROCK_OUTPUT_USD_PER_MTOK         price, from the Bedrock pricing page, dated
AIA_BEDROCK_CACHE_READ_USD_PER_MTOK     optional; absent charges cache reads as input
AIA_BEDROCK_CACHE_WRITE_USD_PER_MTOK    optional; absent charges cache writes as input
AIA_BEDROCK_MAX_OUTPUT_TOKENS           the model's output ceiling
AIA_BEDROCK_CONTEXT_WINDOW_TOKENS       the model's context window
AIA_AI_ROUTE_EU_PROCESSING_APPROVED     ``true`` only after § Verification is recorded
AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING     ``true`` only with the service terms recorded
AIA_AI_ROUTE_APPROVED_FOR               data classes, comma-separated; may be empty
AIA_AI_ROUTE_RETENTION_DAYS             optional; unset = *unspecified*, never zero
AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS      the respondent agent's output cap per call
AIA_AI_FIELDWORK_RESERVATION_USD        budget held per request (primary + one repair)
AIA_AI_FICTIONAL_CLIENT_IDS             optional; clients whose designs are Class C
AIA_BEDROCK_TIMEOUT_SECONDS             optional read timeout, default 300
======================================  ============================================

Retention is left unspecified unless configured, deliberately: the account's Bedrock
data-retention setting is ``inherit``, which is not an explicit zero-retention policy,
and ADR 0008 lets only Class C travel over a route with unspecified retention. The
basis is the model's own terms, recorded in ADR 0010, not this setting.

The route's adapter signs with the host's role (``InstanceRoleSigner``: an
instance or container role, nothing else) and sends with ``Urllib3Transport`` (no
retries). Both are injectable for tests; nothing here makes a call.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from aia_core.application.model_gateway import GovernedModelGateway
from aia_core.domain.ai_models import ModelCapability, parse_model_config
from aia_core.domain.licence_determinations import recorded_policy
from aia_core.domain.providers import Provider
from aia_core.domain.residency import DataClass, EgressPolicy, ProviderRoute, ResidencyZone
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.model_adapters import BedrockConverseAdapter, BedrockSigner
from aia_core.infrastructure.model_adapters.transport import HttpTransport

from .ai_fieldwork import AIFieldwork, AIFieldworkConfig

__all__ = ["AIRuntimeConfigError", "AIRuntimeSettings", "build_ai_fieldwork", "build_gateway"]

_TRUE: Final = {"1", "true", "yes", "on"}
_FALSE: Final = {"0", "false", "no", "off", ""}


class AIRuntimeConfigError(RuntimeError):
    """The AI runtime is enabled but its configuration is incomplete or unsafe."""


def _flag(env: Mapping[str, str], key: str, *, required: bool) -> bool:
    raw = env.get(key)
    if raw is None:
        if required:
            raise AIRuntimeConfigError(f"{key} is required (true or false)")
        return False
    value = raw.strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE and (value or not required):
        return False
    raise AIRuntimeConfigError(f"{key}={raw!r} is not true or false")


def _text(env: Mapping[str, str], key: str) -> str:
    value = (env.get(key) or "").strip()
    if not value:
        raise AIRuntimeConfigError(f"{key} is required when the AI runtime is enabled")
    return value


def _number(env: Mapping[str, str], key: str, *, optional: bool = False) -> float | None:
    raw = (env.get(key) or "").strip()
    if not raw:
        if optional:
            return None
        raise AIRuntimeConfigError(f"{key} is required when the AI runtime is enabled")
    try:
        value = float(raw)
    except ValueError as exc:
        raise AIRuntimeConfigError(f"{key}={raw!r} is not a number") from exc
    if not value >= 0 or value == float("inf"):
        raise AIRuntimeConfigError(f"{key} must be a finite, non-negative number")
    return value


def _positive_int(env: Mapping[str, str], key: str) -> int:
    raw = _text(env, key)
    try:
        value = int(raw)
    except ValueError as exc:
        raise AIRuntimeConfigError(f"{key}={raw!r} is not an integer") from exc
    if value <= 0:
        raise AIRuntimeConfigError(f"{key} must be positive")
    return value


@dataclass(frozen=True, slots=True)
class AIRuntimeSettings:
    """The AI runtime's configuration, validated. Built only by :meth:`from_env`."""

    route_id: str
    region: str
    model_id: str
    policy_version: str
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    cache_read_usd_per_mtok: float | None
    cache_write_usd_per_mtok: float | None
    max_output_tokens: int
    context_window_tokens: int
    eu_processing_approved: bool
    excluded_from_training: bool
    approved_for: frozenset[DataClass]
    retention_days: int | None
    fieldwork_max_output_tokens: int
    fieldwork_reservation_usd: float
    fictional_client_ids: frozenset[str]
    timeout_s: float

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> AIRuntimeSettings | None:
        """``None`` when the AI runtime is off; the settings when on; raise when unsafe."""
        env = os.environ if env is None else env
        if not _flag(env, "AIA_AI_RUNTIME_ENABLED", required=False):
            return None
        region = _text(env, "AIA_BEDROCK_REGION")
        if not region.startswith("eu-"):
            raise AIRuntimeConfigError(
                f"AIA_BEDROCK_REGION={region!r} is not an EU region (ADR 0008, ADR 0010)"
            )
        model_id = _text(env, "AIA_BEDROCK_MODEL_ID")
        if not model_id.startswith("eu.") or model_id.endswith("latest") or ":" not in model_id:
            raise AIRuntimeConfigError(
                f"AIA_BEDROCK_MODEL_ID={model_id!r} must be an EU inference profile id pinned "
                "to a version (eu.…:N), never a floating alias (ADR 0010)"
            )
        classes: set[DataClass] = set()
        for part in (env.get("AIA_AI_ROUTE_APPROVED_FOR") or "").split(","):
            name = part.strip()
            if not name:
                continue
            try:
                classes.add(DataClass(name))
            except ValueError as exc:
                raise AIRuntimeConfigError(f"unknown data class {name!r}") from exc
        if "AIA_AI_ROUTE_APPROVED_FOR" not in env:
            raise AIRuntimeConfigError(
                "AIA_AI_ROUTE_APPROVED_FOR is required (it may be empty: approved for nothing)"
            )
        retention_raw = (env.get("AIA_AI_ROUTE_RETENTION_DAYS") or "").strip()
        retention: int | None = None
        if retention_raw:
            try:
                retention = int(retention_raw)
            except ValueError as exc:
                raise AIRuntimeConfigError("AIA_AI_ROUTE_RETENTION_DAYS is not an integer") from exc
            if retention < 0:
                raise AIRuntimeConfigError("AIA_AI_ROUTE_RETENTION_DAYS cannot be negative")
        fictional = frozenset(
            c.strip()
            for c in (env.get("AIA_AI_FICTIONAL_CLIENT_IDS") or "").split(",")
            if c.strip()
        )
        if fictional and (env.get("AIA_ENV") or "").strip().lower() == "production":
            raise AIRuntimeConfigError(
                "AIA_AI_FICTIONAL_CLIENT_IDS is refused in production: fictional material "
                "does not belong there"
            )
        reservation = _number(env, "AIA_AI_FIELDWORK_RESERVATION_USD")
        assert reservation is not None
        if reservation <= 0:
            raise AIRuntimeConfigError("AIA_AI_FIELDWORK_RESERVATION_USD must be positive")
        input_price = _number(env, "AIA_BEDROCK_INPUT_USD_PER_MTOK")
        output_price = _number(env, "AIA_BEDROCK_OUTPUT_USD_PER_MTOK")
        assert input_price is not None and output_price is not None
        timeout = _number(env, "AIA_BEDROCK_TIMEOUT_SECONDS", optional=True) or 300.0
        settings = cls(
            route_id=_text(env, "AIA_AI_ROUTE_ID"),
            region=region,
            model_id=model_id,
            policy_version=_text(env, "AIA_AI_POLICY_VERSION"),
            input_usd_per_mtok=input_price,
            output_usd_per_mtok=output_price,
            cache_read_usd_per_mtok=_number(
                env, "AIA_BEDROCK_CACHE_READ_USD_PER_MTOK", optional=True
            ),
            cache_write_usd_per_mtok=_number(
                env, "AIA_BEDROCK_CACHE_WRITE_USD_PER_MTOK", optional=True
            ),
            max_output_tokens=_positive_int(env, "AIA_BEDROCK_MAX_OUTPUT_TOKENS"),
            context_window_tokens=_positive_int(env, "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS"),
            eu_processing_approved=_flag(env, "AIA_AI_ROUTE_EU_PROCESSING_APPROVED", required=True),
            excluded_from_training=_flag(env, "AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING", required=True),
            approved_for=frozenset(classes),
            retention_days=retention,
            fieldwork_max_output_tokens=_positive_int(env, "AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS"),
            fieldwork_reservation_usd=reservation,
            fictional_client_ids=fictional,
            timeout_s=timeout,
        )
        if settings.fieldwork_max_output_tokens > settings.max_output_tokens:
            raise AIRuntimeConfigError(
                "AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS exceeds the model's "
                "AIA_BEDROCK_MAX_OUTPUT_TOKENS"
            )
        return settings

    def model_document(self) -> dict[str, Any]:
        """The catalog and policy document for ``parse_model_config`` (fails closed)."""
        pricing: dict[str, Any] = {
            "input_usd_per_mtok": self.input_usd_per_mtok,
            "output_usd_per_mtok": self.output_usd_per_mtok,
        }
        if self.cache_read_usd_per_mtok is not None:
            pricing["cache_read_usd_per_mtok"] = self.cache_read_usd_per_mtok
        if self.cache_write_usd_per_mtok is not None:
            pricing["cache_write_usd_per_mtok"] = self.cache_write_usd_per_mtok
        binding = {
            "provider": Provider.AWS_BEDROCK.value,
            "model": self.model_id,
            "route_id": self.route_id,
        }
        return {
            "models": [
                {
                    "provider": Provider.AWS_BEDROCK.value,
                    "model": self.model_id,
                    # Only what runs today. ADR 0010 lets all generative capabilities
                    # resolve to this model; binding them waits for their agents.
                    "capabilities": [ModelCapability.SIMULATION.value],
                    "max_output_tokens": self.max_output_tokens,
                    "context_window_tokens": self.context_window_tokens,
                    "pricing": pricing,
                    "supports_strict_schema": False,
                }
            ],
            "policies": [
                {
                    "version": self.policy_version,
                    "allowed_providers": [Provider.AWS_BEDROCK.value],
                    "bindings": {ModelCapability.SIMULATION.value: binding},
                }
            ],
        }

    def route(self) -> ProviderRoute:
        """ADR 0010's route, with the facts a person verified, and nothing assumed."""
        return ProviderRoute(
            route_id=self.route_id,
            provider=Provider.AWS_BEDROCK.value,
            zone=ResidencyZone.EU,
            eu_processing_approved=self.eu_processing_approved,
            excluded_from_training=self.excluded_from_training,
            retention_days=self.retention_days,
            approved_for=self.approved_for,
        )


def build_gateway(
    settings: AIRuntimeSettings,
    *,
    transport: HttpTransport | None = None,
    signer: BedrockSigner | None = None,
) -> GovernedModelGateway:
    """The one gateway, over one route, one adapter, the recorded licence determinations."""
    if transport is None:
        from aia_core.infrastructure.model_adapters.live_transport import Urllib3Transport

        transport = Urllib3Transport()
    if signer is None:
        from aia_core.infrastructure.model_adapters.aws_signing import InstanceRoleSigner

        signer = InstanceRoleSigner(region=settings.region)
    adapter = BedrockConverseAdapter(
        transport=transport,
        signer=signer,
        region=settings.region,
        model_id=settings.model_id,
        timeout_s=settings.timeout_s,
    )
    return GovernedModelGateway(
        registry=parse_model_config(settings.model_document()),
        egress=EgressPolicy(routes=(settings.route(),)),
        licence=recorded_policy(),
        adapters={settings.route_id: adapter},
    )


def build_ai_fieldwork(
    settings: AIRuntimeSettings,
    *,
    build: BuildIdentity,
    transport: HttpTransport | None = None,
    signer: BedrockSigner | None = None,
) -> AIFieldwork:
    """The ``ai_runtime`` fieldwork producer for a configured composition."""
    return AIFieldwork(
        gateway=build_gateway(settings, transport=transport, signer=signer),
        config=AIFieldworkConfig(
            policy_version=settings.policy_version,
            provider=Provider.AWS_BEDROCK,
            reservation_usd=settings.fieldwork_reservation_usd,
            max_output_tokens=settings.fieldwork_max_output_tokens,
            fictional_client_ids=settings.fictional_client_ids,
        ),
        build=build,
    )
