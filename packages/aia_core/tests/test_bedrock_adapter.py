"""The Bedrock route's adapter, signer and live transport (ADR 0010).

The recorded exchanges under ``fixtures/model_adapters/bedrock/`` run in
``test_model_adapters.py`` beside every other provider's. This file pins what is
Bedrock's own: the Converse request shape, the route binding (one model id, nothing
else is signed or sent), the instance-role-only signer, and the live transport's
two promises -- it never retries, and it says whether a failed request left.

No AWS call is made. The live transport is exercised against a local stub server.
"""

from __future__ import annotations

import asyncio
import http.server
import json
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict

from aia_core.domain.ai_contracts import (
    AdapterRequest,
    Delivery,
    Message,
    ProviderError,
    ProviderErrorKind,
    output_schema,
)
from aia_core.domain.providers import Provider
from aia_core.infrastructure.model_adapters import BedrockConverseAdapter, RecordedTransport
from aia_core.infrastructure.model_adapters.bedrock import SigningUnavailable
from aia_core.infrastructure.model_adapters.transport import HttpRequest, TransportFailure

FIXTURES = Path(__file__).parent / "fixtures" / "model_adapters" / "bedrock"
PROFILE = "eu.example.test-model-v1:0"  # a test id, not a real profile


class Verdict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    verdict: str
    score: int


class Signer:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.signed: list[dict[str, Any]] = []

    def sign(self, *, method: str, url: str, headers: Any, body: bytes) -> dict[str, str]:
        if self.fail:
            raise SigningUnavailable("no role credential")
        self.signed.append({"method": method, "url": url, "body": body})
        return {**dict(headers), "authorization": "AWS4-HMAC-SHA256 test"}


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _request(*, model: str = PROFILE, temperature: float | None = 0.0) -> AdapterRequest:
    return AdapterRequest(
        call_id="CALL-bedrock",
        provider=Provider.AWS_BEDROCK,
        model=model,
        system="Jsi respondent.",
        messages=(Message(role="user", content="Otázka?"),),
        max_output_tokens=512,
        output_schema=output_schema(Verdict),
        schema_name="test_agent",
        temperature=temperature,
    )


def _adapter(transport: Any, signer: Signer | None = None) -> tuple[BedrockConverseAdapter, Signer]:
    signer = signer or Signer()
    return (
        BedrockConverseAdapter(
            transport=transport, signer=signer, region="eu-central-1", model_id=PROFILE
        ),
        signer,
    )


def test_converse_request_shape_and_the_signed_bytes_are_the_sent_bytes() -> None:
    transport = RecordedTransport.from_fixture(_fixture("success_forced_tool"))
    adapter, signer = _adapter(transport)
    asyncio.run(adapter.send(_request()))
    sent = transport.requests[0]
    # The profile id is one percent-encoded path segment, as botocore serialises it.
    assert sent.url == (
        "https://bedrock-runtime.eu-central-1.amazonaws.com/model/"
        "eu.example.test-model-v1%3A0/converse"
    )
    assert sent.method == "POST"
    assert sent.body["messages"] == [{"role": "user", "content": [{"text": "Otázka?"}]}]
    assert sent.body["system"] == [{"text": "Jsi respondent."}]
    assert sent.body["inferenceConfig"] == {"maxTokens": 512, "temperature": 0.0}
    tool = sent.body["toolConfig"]
    assert tool["toolChoice"] == {"tool": {"name": "test_agent"}}
    assert tool["tools"][0]["toolSpec"]["inputSchema"] == {"json": output_schema(Verdict)}
    # What was signed is exactly what the transport sends.
    assert sent.raw_body is not None
    assert signer.signed[0]["body"] == sent.raw_body
    assert json.loads(sent.raw_body) == sent.body
    assert sent.headers["authorization"].startswith("AWS4-HMAC-SHA256")
    assert sent.redacted_headers()["authorization"] == "<redacted>"


def test_no_temperature_means_the_provider_default() -> None:
    transport = RecordedTransport.from_fixture(_fixture("success_forced_tool"))
    adapter, _ = _adapter(transport)
    asyncio.run(adapter.send(_request(temperature=None)))
    assert transport.requests[0].body["inferenceConfig"] == {"maxTokens": 512}


def test_the_adapter_is_bound_to_its_route_model_and_sends_nothing_else() -> None:
    transport = RecordedTransport.from_fixture(_fixture("success_forced_tool"))
    adapter, signer = _adapter(transport)
    with pytest.raises(ProviderError) as refused:
        asyncio.run(adapter.send(_request(model="eu.other.model-v1:0")))
    assert refused.value.kind is ProviderErrorKind.MODEL
    assert refused.value.delivery is Delivery.NOT_SENT
    assert transport.requests == []
    assert signer.signed == []


def test_no_role_credential_is_an_authentication_failure_before_sending() -> None:
    transport = RecordedTransport.from_fixture(_fixture("success_forced_tool"))
    adapter, _ = _adapter(transport, Signer(fail=True))
    with pytest.raises(ProviderError) as refused:
        asyncio.run(adapter.send(_request()))
    assert refused.value.kind is ProviderErrorKind.AUTHENTICATION
    assert refused.value.delivery is Delivery.NOT_SENT
    assert transport.requests == []


def test_the_adapter_refuses_to_be_built_without_a_region_or_a_model() -> None:
    for region, model in (("", PROFILE), ("eu-central-1", " ")):
        with pytest.raises(ValueError):
            BedrockConverseAdapter(
                transport=RecordedTransport(), signer=Signer(), region=region, model_id=model
            )


# --------------------------------------------------------------------------- #
# The signer: botocore for signing only, a role credential or nothing
# --------------------------------------------------------------------------- #

botocore = pytest.importorskip("botocore")


def test_the_signer_refuses_a_static_key_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aia_core.infrastructure.model_adapters.aws_signing import InstanceRoleSigner

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIATESTNOTREAL00000")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret-not-real")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    signer = InstanceRoleSigner(region="eu-central-1")
    with pytest.raises(SigningUnavailable, match="env"):
        signer.sign(method="POST", url="https://example.test/", headers={}, body=b"{}")


def test_the_signer_signs_for_bedrock_in_its_region_with_a_role_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from botocore.credentials import Credentials

    from aia_core.infrastructure.model_adapters import aws_signing

    role = Credentials("ASIATESTNOTREAL00000", "test-secret", "test-token", method="iam-role")

    class Session:
        def get_credentials(self) -> Credentials:
            return role

    monkeypatch.setattr("botocore.session.get_session", lambda: Session())
    signer = aws_signing.InstanceRoleSigner(region="eu-central-1")
    url = "https://bedrock-runtime.eu-central-1.amazonaws.com/model/eu.x-v1%3A0/converse"
    headers = signer.sign(
        method="POST", url=url, headers={"content-type": "application/json"}, body=b"{}"
    )
    assert "/eu-central-1/bedrock/aws4_request" in headers["authorization"]
    assert headers["x-amz-security-token"] == "test-token"
    assert "x-amz-date" in headers


# --------------------------------------------------------------------------- #
# The live transport against a local stub: no retry, delivery stated
# --------------------------------------------------------------------------- #

urllib3 = pytest.importorskip("urllib3")


class _Stub(http.server.BaseHTTPRequestHandler):
    hits = 0
    delay = 0.0

    def do_POST(self) -> None:
        type(self).hits += 1
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length)
        if type(self).delay:
            time.sleep(type(self).delay)
        payload = json.dumps({"echo": json.loads(body or b"{}")}).encode()
        try:
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("x-amzn-RequestId", "stub-request-id")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args: Any) -> None:
        return


@pytest.fixture
def stub() -> Iterator[tuple[str, type[_Stub]]]:
    handler = type("Handler", (_Stub,), {"hits": 0, "delay": 0.0})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", handler
    finally:
        server.shutdown()
        server.server_close()


def _live(url: str) -> HttpRequest:
    raw = b'{"a":1}'
    return HttpRequest(
        method="POST",
        url=url,
        headers={"content-type": "application/json"},
        body={"a": 1},
        raw_body=raw,
    )


def test_live_transport_sends_the_raw_bytes_once(stub: tuple[str, type[_Stub]]) -> None:
    from aia_core.infrastructure.model_adapters.live_transport import Urllib3Transport

    base, handler = stub
    response = asyncio.run(Urllib3Transport().send(_live(base + "/x"), timeout_s=5))
    assert response.status == 200
    assert response.body == {"echo": {"a": 1}}
    assert response.header("x-amzn-requestid") == "stub-request-id"
    assert handler.hits == 1


def test_a_read_timeout_is_uncertain_and_is_never_retried(
    stub: tuple[str, type[_Stub]],
) -> None:
    from aia_core.infrastructure.model_adapters.live_transport import Urllib3Transport

    base, handler = stub
    handler.delay = 1.5
    with pytest.raises(TransportFailure) as failed:
        asyncio.run(Urllib3Transport().send(_live(base + "/x"), timeout_s=0.3))
    assert failed.value.delivery is Delivery.UNKNOWN
    time.sleep(1.6)
    assert handler.hits == 1, "a timed-out request was sent again"


def test_a_refused_connection_was_never_sent() -> None:
    from aia_core.infrastructure.model_adapters.live_transport import Urllib3Transport

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with pytest.raises(TransportFailure) as failed:
        asyncio.run(Urllib3Transport().send(_live(f"http://127.0.0.1:{port}/x"), timeout_s=2))
    assert failed.value.delivery is Delivery.NOT_SENT
