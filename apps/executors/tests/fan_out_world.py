"""A synthetic Deep Research world of N web tracks, for the fan-out tests and measurements.

Not a test module: ``test_deep_research_fan_out*.py`` import it, and so do the worker
processes the PostgreSQL suite starts (``AIA_WORKER_EXECUTORS=fan_out_world:build_registry``,
with this directory on ``PYTHONPATH``). Everything is fictional and recorded: hosts
``h<k>.fan-dr.example``, one recorded search and one page per subject, model answers from
:class:`TimedAgents` (the journey's recorded agents with an injected latency and a ledger
of every request, written ``O_APPEND`` so processes may share it). Nothing leaves the
process.

A subject ``i`` is "Jak se vyvíjí ukazatel i v Česku?"; its query is the subject itself
(the recorded planner's default); its page says "Ukazatel i dosáhl v roce 2025 hodnoty i
bodů." and the web investigator proposes that sentence as a finding. With the STANDARD
preset each track is one search, one fetch and one investigator request.
"""

from __future__ import annotations

import dataclasses
import json
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aia_core.domain.ai_material import MaterialApproval, material_sha256
from aia_core.domain.residency import DataClass
from aia_core.infrastructure.build_identity import BuildIdentity
from aia_core.infrastructure.db import create_app_engine, create_session_factory
from aia_core.infrastructure.fan_out_coordination import ModelSlots, SharedHostPacer
from aia_core.infrastructure.host_pacing import PacedTransport
from aia_core.infrastructure.model_adapters.transport import HttpRequest, HttpResponse
from aia_core.infrastructure.storage import FilesystemArtifactStore
from aia_core.infrastructure.web_retrieval import (
    FetchedResponse,
    FetchTransport,
    RecordedSearch,
    SearchResponse,
    WebFetcher,
)
from aia_executors.ai_runtime import AIRuntimeSettings, build_gateway
from aia_executors.deep_research import (
    DeepResearchConfig,
    DeepResearchRuntime,
    deep_research_registry,
)
from aia_executors.deep_research_recorded import recorded_runtime
from aia_worker.executor import StepExecutor
from test_deep_research_journey import RecordedAgents, Signer  # type: ignore[import-not-found]

HOST_COUNT = 3
#: One address for every fictional host: public, never contacted (recorded).
ADDRESS = "93.184.215.14"


def subject(i: int) -> str:
    return f"Jak se vyvíjí ukazatel {i} v Česku?"


def sentence(i: int) -> str:
    return f"Ukazatel {i} dosáhl v roce 2025 hodnoty {i} bodů."


def host(i: int) -> str:
    return f"h{i % HOST_COUNT}.fan-dr.example"


def url(i: int) -> str:
    return f"https://{host(i)}/ukazatel-{i}"


def design(n: int) -> dict[str, Any]:
    return {
        "title": f"Syntetický svět o {n} otázkách",
        "goal": "Změřit, jak se běh rozloží mezi procesy.",
        "decision_use": "Měření, ne rozhodnutí.",
        "briefing": "Fiktivní zadání pro test.",
        "research_plan": {"research_questions": [subject(i) for i in range(n)]},
    }


def web(n: int) -> dict[str, Any]:
    return {
        "recorded_at": "2026-09-01T09:00:00+00:00",
        "source_classes": {
            f"h{k}.fan-dr.example": "OFFICIAL_STATISTICS" for k in range(HOST_COUNT)
        },
        "hosts": {f"h{k}.fan-dr.example": [ADDRESS] for k in range(HOST_COUNT)},
        "search": {
            subject(i): {"hits": [{"url": url(i), "title": f"Ukazatel {i}"}], "credits": 1}
            for i in range(n)
        },
        "pages": {
            url(i): {
                "body": (
                    f"<!doctype html><html><head><title>Ukazatel {i}</title>"
                    '<meta property="article:published_time" content="2025-06-30T08:00:00Z">'
                    f"</head><body><h1>Ukazatel {i}</h1><p>{sentence(i)}</p></body></html>"
                )
            }
            for i in range(n)
        },
    }


def answers(n: int) -> dict[str, Any]:
    return {
        "planner": {},
        "internal": {},
        "verifier": {},
        "web": {
            url(i): [
                {
                    "quote": sentence(i),
                    "claim": sentence(i),
                    "evidence_type": "official_report",
                    "source_date": "2025-06-30",
                    "geography": "CZ",
                    "population": "",
                    "topics": [],
                    "outcome_overlap": False,
                    "recommended_use": "context_only",
                    "source_quality": 0.9,
                }
            ]
            for i in range(n)
        },
    }


def write_world(directory: Path, n: int) -> Path:
    """The recorded web for ``n`` subjects, as the recorded composition reads it."""
    path = directory / f"web-{n}.json"
    path.write_text(json.dumps(web(n), ensure_ascii=False), encoding="utf-8")
    return path


def settings_for(client_id: str, n: int) -> AIRuntimeSettings:
    """The test route (Class C), with the synthetic design approved as fictional material."""
    settings = AIRuntimeSettings.from_env(
        {
            "AIA_ENV": "test",
            "AIA_AI_RUNTIME_ENABLED": "true",
            "AIA_AI_ROUTE_ID": "bedrock-eu-primary",
            "AIA_BEDROCK_REGION": "eu-central-1",
            "AIA_BEDROCK_MODEL_ID": "eu.test-research-v1:0",
            "AIA_AI_POLICY_VERSION": "test-deep-research-v1",
            "AIA_BEDROCK_INPUT_USD_PER_MTOK": "3",
            "AIA_BEDROCK_OUTPUT_USD_PER_MTOK": "15",
            "AIA_BEDROCK_MAX_OUTPUT_TOKENS": "8192",
            "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS": "200000",
            "AIA_AI_ROUTE_EU_PROCESSING_APPROVED": "true",
            "AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING": "true",
            "AIA_AI_ROUTE_APPROVED_FOR": "CLASS_C_INTERNAL",
            "AIA_AI_ROUTE_RETENTION_DAYS": "0",
            "AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS": "1024",
            "AIA_AI_FIELDWORK_RESERVATION_USD": "0.25",
            "AIA_AI_RESEARCH_AGENTS_ENABLED": "true",
            "AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS": "8192",
            "AIA_AI_RESEARCH_RESERVATION_USD": "2",
            "AIA_AI_FICTIONAL_CLIENT_IDS": client_id,
            "AIA_AI_MATERIAL_CLASSIFICATIONS": "["
            + MaterialApproval(
                sha256=material_sha256(design(n)),
                data_class=DataClass.CLASS_C_INTERNAL,
                provenance="generated wholly by the fan-out tests; class explicitly set",
                synthetic=True,
            ).model_dump_json()
            + "]",
        }
    )
    assert settings is not None
    return settings


def _append(path: Path | None, record: Mapping[str, Any]) -> None:
    if path is None:
        return
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        os.write(fd, (json.dumps(record, ensure_ascii=False) + "\n").encode())
    finally:
        os.close(fd)


def ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line]


@dataclass
class TimedAgents(RecordedAgents):
    """The recorded agents, each answer ``latency_s`` late, every request on a ledger."""

    latency_s: float = 0.0
    ledger_path: Path | None = None

    def _synthesizer(self, payload: dict[str, Any]) -> dict[str, Any]:
        """The journey's brief, within the contract's bounds for a run of many subjects."""
        answer = super()._synthesizer(payload)
        return {**answer, "findings": answer["findings"][-30:], "gaps": answer["gaps"][:10]}

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
        start = time.time()
        time.sleep(self.latency_s)  # a blocking provider: the worker's thread waits
        response = await super().send(request, timeout_s=timeout_s)
        _append(
            self.ledger_path,
            {
                "pid": os.getpid(),
                "role": self._role(request),
                "start": start,
                "end": time.time(),
                "request_id": response.headers.get("x-amzn-requestid"),
            },
        )
        return response


@dataclass
class TimedTransport:
    """A fetch transport that takes ``latency_s`` and writes every request on a ledger.

    ``hang`` names a URL whose request never returns (a worker killed in flight); it is
    on the ledger as started before it hangs.
    """

    inner: FetchTransport
    latency_s: float = 0.0
    ledger_path: Path | None = None
    hang: str | None = None
    calls: list[str] = field(default_factory=list)

    @property
    def retrieval_mode(self) -> Any:
        return self.inner.retrieval_mode

    def get(self, url: str, *, address: str, max_bytes: int) -> FetchedResponse:
        start = time.time()
        self.calls.append(url)
        if url == self.hang:
            _append(
                self.ledger_path, {"pid": os.getpid(), "url": url, "start": start, "hang": True}
            )
            time.sleep(3600)
        time.sleep(self.latency_s)
        response = self.inner.get(url, address=address, max_bytes=max_bytes)
        _append(
            self.ledger_path,
            {
                "pid": os.getpid(),
                "url": url,
                "host": url.split("/")[2],
                "start": start,
                "end": time.time(),
            },
        )
        return response


@dataclass
class LedgeredSearch(RecordedSearch):
    """The recorded search, every query on a ledger (one line per search sent)."""

    ledger_path: Path | None = None

    def search(self, query: str, *, max_results: int) -> SearchResponse:
        _append(self.ledger_path, {"pid": os.getpid(), "query": query, "start": time.time()})
        return super().search(query, max_results=max_results)


def runtime_for(
    *,
    client_id: str,
    n: int,
    fixture: Path,
    agents: TimedAgents,
    fan_out: bool,
    sessions: Any | None,
    model_limit: int = 3,
    host_interval_s: float = 0.0,
    fetch_latency_s: float = 0.0,
    fetch_ledger: Path | None = None,
    search_ledger: Path | None = None,
    hang: str | None = None,
) -> DeepResearchRuntime:
    """The recorded composition over the synthetic world; fan-out with its shared limits."""
    settings = settings_for(client_id, n)
    runtime = recorded_runtime(
        gateway=build_gateway(settings, transport=agents, signer=Signer()),
        config=DeepResearchConfig(
            policy_version=settings.policy_version,
            max_output_tokens=settings.research_max_output_tokens,
            context_window_tokens=settings.context_window_tokens,
            prices=settings.model_prices(),
            fictional_client_ids=settings.fictional_client_ids,
            material_approvals=settings.material_approvals,
            fan_out=fan_out,
        ),
        fixture=fixture,
        env={"AIA_ENV": "test"},
    )
    retrieval = runtime.retrieval
    assert retrieval is not None and isinstance(retrieval.search, RecordedSearch)
    search = LedgeredSearch(
        adapter_id=retrieval.search.adapter_id,
        exchanges=retrieval.search.exchanges,
        ledger_path=search_ledger,
    )
    fetcher = retrieval.fetcher
    transport: FetchTransport = TimedTransport(
        fetcher._transport,
        latency_s=fetch_latency_s,
        ledger_path=fetch_ledger,
        hang=hang,
    )
    if fan_out:
        assert sessions is not None
        transport = PacedTransport(
            transport, pacer=SharedHostPacer(sessions, poll_s=0.005), interval_s=host_interval_s
        )
    paced = WebFetcher(
        transport=transport,
        resolver=fetcher._resolver,
        adapter_id=fetcher.adapter_id,
        clock=fetcher._clock,
    )
    return dataclasses.replace(
        runtime,
        retrieval=dataclasses.replace(retrieval, search=search, fetcher=paced),
        model_slots=(
            ModelSlots(sessions, pool="bedrock:fan-out-test", limit=model_limit, poll_s=0.005)
            if fan_out and sessions is not None
            else None
        ),
    )


def build_registry() -> dict[str, StepExecutor]:
    """The worker processes' registry: ``AIA_WORKER_EXECUTORS=fan_out_world:build_registry``.

    Read from the environment the test sets: the world's directory and size, the
    fictional client, the limits, the latencies, and a URL to hang on (a worker to kill).
    The artifact store is a directory every process shares.
    """
    env = os.environ
    directory = Path(env["AIA_TEST_FAN_OUT_DIR"])
    n = int(env["AIA_TEST_FAN_OUT_TRACKS"])
    sessions = create_session_factory(
        create_app_engine(env["DATABASE_URL"], pool_size=2, max_overflow=4)
    )
    agents = TimedAgents(
        answers(n),
        latency_s=float(env.get("AIA_TEST_FAN_OUT_MODEL_LATENCY", "0")),
        ledger_path=directory / "models.jsonl",
    )
    runtime = runtime_for(
        client_id=env["AIA_TEST_FAN_OUT_CLIENT"],
        n=n,
        fixture=directory / f"web-{n}.json",
        agents=agents,
        fan_out=True,
        sessions=sessions,
        model_limit=int(env["AIA_TEST_FAN_OUT_MODEL_LIMIT"]),
        host_interval_s=float(env.get("AIA_TEST_FAN_OUT_HOST_INTERVAL", "0")),
        fetch_latency_s=float(env.get("AIA_TEST_FAN_OUT_FETCH_LATENCY", "0")),
        fetch_ledger=directory / "fetches.jsonl",
        search_ledger=directory / "searches.jsonl",
        hang=env.get("AIA_TEST_FAN_OUT_HANG") or None,
    )
    return deep_research_registry(
        store=FilesystemArtifactStore(directory / "store"),
        build=BuildIdentity(sha="fan-out-test", built_at="2026-10-06T00:00:00Z"),
        runtime=runtime,
    )
