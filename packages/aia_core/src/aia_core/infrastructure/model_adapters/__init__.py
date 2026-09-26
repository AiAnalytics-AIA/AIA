"""Provider adapters: transport under AIA's model gateway.

Each adapter translates one provider's wire format into
:mod:`aia_core.domain.ai_contracts` shapes and classifies its errors into the
ten-way taxonomy. None of them retries, falls back or substitutes; every such
decision is made -- and recorded -- by
:class:`aia_core.application.model_gateway.GovernedModelGateway`.

Adapters depend on a transport protocol, not an HTTP library or an SDK, so they
are tested against recorded exchanges with no network and no credentials. The one
live transport, :mod:`.live_transport` (``urllib3``, never retrying), and the one
signer, :mod:`.aws_signing` (botocore SigV4 with a role credential only), serve the
Bedrock route of ADR 0010; both import their library lazily and are not exported
here, so importing the adapters loads no network or AWS code. Which route may
carry which data is still an ADR 0008 decision, made in configuration.

LiteLLM is not used (ADR 0005 decision B is *Proposed*). If it is ever adopted,
it becomes one more adapter here, never the interface.
"""

from .anthropic import AnthropicMessagesAdapter
from .bedrock import BedrockConverseAdapter, BedrockSigner
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
    "BedrockConverseAdapter",
    "BedrockSigner",
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
