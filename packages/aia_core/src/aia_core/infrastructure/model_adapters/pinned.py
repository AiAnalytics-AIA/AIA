"""One route, several pinned models: each model keeps its own route-bound adapter.

The gateway binds one adapter to a route (``GovernedModelGateway.__init__``), and a
:class:`~.bedrock.BedrockConverseAdapter` carries exactly one model id and refuses
any other unsent. A route whose model policy binds a second model -- Deep Research's
light triage model beside the research model, both EU inference profiles on ADR
0010's route -- needs both, and neither adapter may learn to send the other's model.

:class:`PinnedModels` holds one adapter per model id and sends a request through the
adapter pinned to ``request.model``; a model it does not hold is refused here,
unsigned and unsent (``MODEL``, ``NOT_SENT``), exactly as the single adapter refuses
it. It translates nothing and decides nothing else: no retry, no fallback, no
substitution (ADR 0005 A). Which models a route may carry is still the policy's and
the route's decision, made in configuration; this only keeps each one on its own
pinned adapter.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from aia_core.domain.ai_contracts import (
    AdapterRequest,
    AdapterResponse,
    Delivery,
    ProviderError,
    ProviderErrorKind,
)
from aia_core.domain.providers import Provider

__all__ = ["ModelPinnedAdapter", "PinnedModels"]


class ModelPinnedAdapter(Protocol):
    """A provider adapter bound to one model id (``BedrockConverseAdapter``)."""

    @property
    def provider(self) -> Provider: ...

    @property
    def model_id(self) -> str: ...

    async def send(self, request: AdapterRequest) -> AdapterResponse: ...


class PinnedModels:
    """:class:`~aia_core.domain.ai_contracts.ProviderAdapter` over per-model adapters."""

    def __init__(self, adapters: Iterable[ModelPinnedAdapter]) -> None:
        by_model: dict[str, ModelPinnedAdapter] = {}
        providers: set[Provider] = set()
        for adapter in adapters:
            if adapter.model_id in by_model:
                raise ValueError(f"two adapters are pinned to {adapter.model_id}")
            by_model[adapter.model_id] = adapter
            providers.add(adapter.provider)
        if not by_model:
            raise ValueError("a route carries at least one pinned model")
        if len(providers) != 1:
            # A route is approved for one provider (ADR 0008); so is its adapter.
            raise ValueError("every model on one route must be the same provider's")
        self._by_model = by_model
        self._provider = providers.pop()

    @property
    def provider(self) -> Provider:
        return self._provider

    @property
    def model_ids(self) -> frozenset[str]:
        """The model ids this route's adapters are pinned to."""
        return frozenset(self._by_model)

    async def send(self, request: AdapterRequest) -> AdapterResponse:
        adapter = self._by_model.get(request.model)
        if adapter is None:
            raise ProviderError(
                f"this route carries {', '.join(sorted(self._by_model))}, not {request.model}",
                kind=ProviderErrorKind.MODEL,
                delivery=Delivery.NOT_SENT,
            )
        return await adapter.send(request)
