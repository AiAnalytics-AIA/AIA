"""Provider adapters: transport under AIA's model gateway.

Each adapter translates one provider's wire format into
:mod:`aia_core.domain.ai_contracts` shapes and classifies its errors into the
ten-way taxonomy. None of them retries, falls back or substitutes; every such
decision is made -- and recorded -- by
:class:`aia_core.application.model_gateway.GovernedModelGateway`.

Adapters depend on a transport protocol, not an HTTP library or an SDK, so they
are tested against recorded exchanges with no network and no credentials. A live
transport is a thin implementation of :class:`HttpTransport` or
:class:`CliRunner`, and is deliberately not part of this change: which provider
and route may carry which data is an ADR 0008 decision, not a default.

LiteLLM is not used (ADR 0005 decision B is *Proposed*). If it is ever adopted,
it becomes one more adapter here, never the interface.
"""

from .anthropic import AnthropicMessagesAdapter
from .claude_code import ClaudeCodeCliAdapter
from .openai import OpenAIChatAdapter
from .transport import (
    CliResult,
    CliRunner,
    CredentialSource,
    HttpRequest,
    HttpResponse,
    HttpTransport,
    RecordedCliRunner,
    RecordedTransport,
    StaticCredentials,
    TransportFailure,
)

__all__ = [
    "AnthropicMessagesAdapter",
    "ClaudeCodeCliAdapter",
    "CliResult",
    "CliRunner",
    "CredentialSource",
    "HttpRequest",
    "HttpResponse",
    "HttpTransport",
    "OpenAIChatAdapter",
    "RecordedCliRunner",
    "RecordedTransport",
    "StaticCredentials",
    "TransportFailure",
]
