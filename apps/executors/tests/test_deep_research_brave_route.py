"""Brave's search, composed (plan ``deep-research-web-search.md`` chunk 23d).

``AIA_DEEP_RESEARCH_WEB_SEARCH=brave`` builds Brave Web Search beside the public fetch, from
the deployment's keys alone: its dated price per 1,000 requests, the date it was read, and the
key's presence through its reference. The route is live, priced, outside the EU and Class C
only, so every search reserves against the study (23c) and its organization must sign off
first (44). The key is in no route, identity or repr. Building it sends nothing; a missing
or invalid key stops the worker naming it.
"""

from __future__ import annotations

from typing import Any

import pytest
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.residency import DataClass, ResidencyZone
from aia_core.infrastructure.web_retrieval_brave import BraveSearch
from aia_executors.ai_runtime import AIRuntimeConfigError
from aia_executors.deep_research_runtime import deep_research_runtime, web_search
from test_deep_research_journey import (  # type: ignore[import-not-found]
    ANSWERS,
    DEVELOP_ROUTE,
    RecordedAgents,
    ResearchWorld,
    Signer,
    ai_settings,
    research,  # noqa: F401  (a fixture)
)

#: A fictional key: never a real one, and never expected anywhere but the environment.
KEY = "fictional-brave-key-0000"
BRAVE = {
    "AIA_DEEP_RESEARCH_ENABLED": "true",
    "AIA_DEEP_RESEARCH_WEB_SEARCH": "brave",
    "AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT": "research@aia.example",
    "AIA_DEEP_RESEARCH_BRAVE_API_KEY": KEY,
    "AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000": "5",
    "AIA_DEEP_RESEARCH_BRAVE_PRICES_AS_OF": "2026-10-09",
}


def _compose(world: ResearchWorld, **env: str) -> Any:
    return deep_research_runtime(
        ai_settings(world.client_id, approved_for=DEVELOP_ROUTE),
        env=env,
        transport=RecordedAgents(ANSWERS),
        signer=Signer(),
    )


def test_brave_is_a_priced_class_c_route_outside_the_eu_beside_the_public_fetch(
    research: ResearchWorld,  # noqa: F811
) -> None:
    runtime = _compose(research, **BRAVE)
    retrieval = runtime.retrieval
    search = retrieval.search_route
    assert isinstance(retrieval.search, BraveSearch)
    assert search.route_id == "brave-web-search" and search.retrieval_mode is RetrievalMode.LIVE
    assert search.price_usd_per_call == pytest.approx(0.005)
    assert search.route.zone is ResidencyZone.NON_EU
    assert search.route.approved_for == frozenset({DataClass.CLASS_C_INTERNAL})
    assert retrieval.fetch_route.price_usd_per_call == 0
    assert search.needs_sign_off and runtime.sign_off_routes() == ("brave-web-search",)
    # The key is a reference: in no route, identity, repr or version a run records.
    seen = repr(retrieval.search) + repr(runtime.web_identity()) + repr(runtime.versions())
    assert KEY not in seen and "env:AIA_DEEP_RESEARCH_BRAVE_API_KEY" in repr(retrieval.search)


@pytest.mark.parametrize(
    ("change", "names"),
    [
        ({"AIA_DEEP_RESEARCH_BRAVE_API_KEY": ""}, "needs AIA_DEEP_RESEARCH_BRAVE_API_KEY"),
        ({"AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000": ""}, "AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000"),
        ({"AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000": "0"}, "must be above 0"),
        ({"AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000": "500"}, "at most 100"),
        ({"AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000": "nan"}, "must be above 0"),
        ({"AIA_DEEP_RESEARCH_BRAVE_PRICES_AS_OF": ""}, "AIA_DEEP_RESEARCH_BRAVE_PRICES_AS_OF"),
        ({"AIA_DEEP_RESEARCH_BRAVE_PRICES_AS_OF": "2999-01-01"}, "in the future"),
        ({"AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT": ""}, "brave needs AIA_DEEP_RESEARCH_PUBLIC"),
        ({"AIA_DEEP_RESEARCH_WEB_SEARCH": "google"}, "is not one of off, wikipedia, brave"),
        ({"AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED": "true"}, "turn one of them on, not both"),
        ({"AIA_DEEP_RESEARCH_ENABLED": "false"}, "WEB_SEARCH needs AIA_DEEP_RESEARCH_ENABLED"),
    ],
)
def test_a_brave_route_that_cannot_be_composed_stops_the_worker_naming_its_key(
    research: ResearchWorld,  # noqa: F811
    change: dict[str, str],
    names: str,
) -> None:
    with pytest.raises(AIRuntimeConfigError, match=names) as refused:
        _compose(research, **{**BRAVE, **change})
    assert KEY not in str(refused.value)


def test_the_new_key_names_every_search_route_and_the_old_one_still_reads() -> None:
    assert web_search({}) == "off"
    assert web_search({"AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED": "true"}) == "wikipedia"
    assert web_search({"AIA_DEEP_RESEARCH_WEB_SEARCH": "wikipedia"}) == "wikipedia"
    # What a Compose file's default writes beside the new key is harmless.
    assert (
        web_search(
            {
                "AIA_DEEP_RESEARCH_WEB_SEARCH": "brave",
                "AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED": "false",
            }
        )
        == "brave"
    )


def test_wikipedia_named_by_the_new_key_composes_as_the_old_switch_did(
    research: ResearchWorld,  # noqa: F811
) -> None:
    old = _compose(
        research, AIA_DEEP_RESEARCH_ENABLED="true", AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED="true"
    )
    new = _compose(
        research, AIA_DEEP_RESEARCH_ENABLED="true", AIA_DEEP_RESEARCH_WEB_SEARCH="wikipedia"
    )
    assert new.web_identity() == old.web_identity() and new.sign_off_routes() == ()


def test_a_query_written_from_client_material_never_reaches_brave(
    research: ResearchWorld,  # noqa: F811
) -> None:
    from aia_core.application.web_retrieval import RetrievalGate
    from aia_core.domain.deep_research.tooling import InMemoryToolLedger

    runtime = _compose(research, **BRAVE)
    with research.sessions() as session:
        gate = RetrievalGate(
            retrieval=runtime.retrieval,
            scope=research.lead_scope(session),
            meter=InMemoryToolLedger(budget_usd=None),
            client_terms=(),
            class_a_texts=(),
        )
        assert gate.refusal_for_class(DataClass.CLASS_A_CLIENT_CONFIDENTIAL) == "class_a_query"
        refused = gate.refusal_for_class(DataClass.CLASS_B_DERIVED_CLIENT)
        assert refused is not None and refused.startswith("egress_")
