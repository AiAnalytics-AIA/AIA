"""A credential named by an ``env:AIA_*`` reference: read at the call, never printed.

The Brave search key is the first credential held this way: the adapter carries
``env:AIA_DEEP_RESEARCH_BRAVE_API_KEY``, and the key exists only in the process
environment and in the one header that carries it.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pytest

from aia_core.domain.ai_contracts import Delivery, ProviderError, ProviderErrorKind
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.infrastructure.model_adapters import EnvironmentCredentials
from aia_core.infrastructure.model_adapters.transport import resolve_secret
from aia_core.infrastructure.web_retrieval import FetchedResponse, ToolCallFailed
from aia_core.infrastructure.web_retrieval_brave import BRAVE_CREDENTIAL_REF, BraveSearch

KEY = "BSAfictional-environment-key-9876543210"
VAR = "AIA_DEEP_RESEARCH_BRAVE_API_KEY"


def test_the_brave_reference_names_its_environment_variable() -> None:
    assert f"env:{VAR}" == BRAVE_CREDENTIAL_REF


def test_a_reference_reads_its_variable_at_the_call() -> None:
    environ: dict[str, str] = {}
    credentials = EnvironmentCredentials(environ)
    with pytest.raises(KeyError):
        credentials.secret(BRAVE_CREDENTIAL_REF)
    environ[VAR] = KEY
    assert credentials.secret(BRAVE_CREDENTIAL_REF) == KEY


def test_the_process_environment_is_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VAR, KEY)
    assert EnvironmentCredentials().secret(BRAVE_CREDENTIAL_REF) == KEY
    monkeypatch.delenv(VAR)
    with pytest.raises(KeyError):
        EnvironmentCredentials().secret(BRAVE_CREDENTIAL_REF)


@pytest.mark.parametrize(
    "reference",
    [
        VAR,  # no scheme
        f"ENV:{VAR}",
        "env:AWS_SECRET_ACCESS_KEY",  # not an AIA variable
        "env:HOME",
        "env:aia_deep_research_brave_api_key",
        "env:AIA_",
        f"env:{VAR} ",
        f"ssm:/aia/develop/{VAR.lower()}",
        "",
    ],
)
def test_only_an_env_reference_to_an_aia_variable_resolves(reference: str) -> None:
    credentials = EnvironmentCredentials(
        {
            VAR: KEY,
            "AWS_SECRET_ACCESS_KEY": KEY,
            "HOME": KEY,
            "aia_deep_research_brave_api_key": KEY,
        }
    )
    with pytest.raises(KeyError):
        credentials.secret(reference)


@pytest.mark.parametrize("environ", [{}, {VAR: ""}, {VAR: "  "}])
def test_resolve_secret_fails_closed_without_naming_a_value(environ: dict[str, str]) -> None:
    with pytest.raises(ProviderError) as missing:
        resolve_secret(EnvironmentCredentials(environ), BRAVE_CREDENTIAL_REF)
    assert missing.value.kind is ProviderErrorKind.MISSING
    assert missing.value.delivery is Delivery.NOT_SENT
    assert BRAVE_CREDENTIAL_REF in str(missing.value)


def test_the_environment_is_kept_out_of_the_repr() -> None:
    credentials = EnvironmentCredentials({VAR: KEY})
    assert KEY not in repr(credentials) and KEY not in str(credentials)


# ------------------------------------------------- the adapter over the env --


@dataclass
class _Resolver:
    hosts: list[str] = field(default_factory=list)

    def resolve(self, host: str) -> tuple[str, ...]:
        self.hosts.append(host)
        return ("93.184.215.14",)


@dataclass
class _Transport:
    status: int = 200
    sent: list[dict[str, str]] = field(default_factory=list, repr=False)
    retrieval_mode: RetrievalMode = RetrievalMode.LIVE

    def get(
        self, url: str, *, address: str, max_bytes: int, headers: Mapping[str, str]
    ) -> FetchedResponse:
        self.sent.append(dict(headers))
        payload: Any = {"web": {"results": [{"url": "https://a.example.cz/", "title": "A"}]}}
        return FetchedResponse(
            status=self.status,
            headers={"content-type": "application/json"},
            body=json.dumps(payload).encode(),
            truncated=False,
        )


def test_the_adapter_holds_the_reference_and_sends_the_key_only_in_its_header() -> None:
    transport = _Transport()
    adapter = BraveSearch(
        credentials=EnvironmentCredentials({VAR: KEY}),
        resolver=_Resolver(),
        transport=transport,
    )
    assert adapter.credential_ref == BRAVE_CREDENTIAL_REF
    answer = adapter.search("káva", max_results=1)
    assert len(answer.hits) == 1
    assert transport.sent == [{"Accept": "application/json", "X-Subscription-Token": KEY}]
    for text in (repr(adapter), str(adapter), repr(vars(adapter)), repr(answer)):
        assert KEY not in text


def test_an_unset_variable_sends_nothing_and_resolves_nothing() -> None:
    transport, resolver = _Transport(), _Resolver()
    adapter = BraveSearch(
        credentials=EnvironmentCredentials({}), resolver=resolver, transport=transport
    )
    with pytest.raises(ToolCallFailed) as missing:
        adapter.search("káva", max_results=1)
    assert missing.value.reason == "missing_credential"
    assert missing.value.delivery is Delivery.NOT_SENT
    assert VAR in str(missing.value)
    assert transport.sent == [] and resolver.hosts == []


@pytest.mark.parametrize("status", [401, 403, 429, 500])
def test_a_refused_key_is_never_repeated(status: int, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    adapter = BraveSearch(
        credentials=EnvironmentCredentials({VAR: KEY}),
        resolver=_Resolver(),
        transport=_Transport(status=status),
    )
    with pytest.raises(ToolCallFailed) as failed:
        adapter.search("káva", max_results=1)
    for text in (str(failed.value), repr(failed.value), repr(vars(failed.value))):
        assert KEY not in text
    assert KEY not in caplog.text
