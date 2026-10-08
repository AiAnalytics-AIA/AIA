"""Deep Research's free reach, composed (plan ``deep-research-web-search.md`` chunk 23b).

The production composition builds, from the deployment's keys alone: pages fetched from
any public host (``AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT``) and the public dataset
connectors (``AIA_DEEP_RESEARCH_CONNECTORS``), each on a fee-free route approved for
Class C alone. Building them sends nothing; a missing or invalid key stops the worker
naming it; with neither key set the composition is exactly the Wikipedia one.
"""

from __future__ import annotations

from typing import Any

import pytest
from aia_core.application.acquisition_ladder import LadderConfig
from aia_core.domain.deep_research.contracts import RetrievalMode
from aia_core.domain.deep_research.reputation import REPUTATION_REGISTER_V1
from aia_core.domain.deep_research.tooling import ToolKind
from aia_core.domain.residency import DataClass, ResidencyZone
from aia_core.infrastructure.web_retrieval_live import PublicHttpsTransport
from aia_executors.ai_runtime import AIRuntimeConfigError
from aia_executors.deep_research_runtime import deep_research_runtime
from test_deep_research_journey import (  # type: ignore[import-not-found]
    ANSWERS,
    DEVELOP_ROUTE,
    RecordedAgents,
    ResearchWorld,
    Signer,
    ai_settings,
    research,  # noqa: F401  (a fixture)
)

CONTACT = "research@aia.example"
WIKI = {"AIA_DEEP_RESEARCH_ENABLED": "true", "AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED": "true"}


def _compose(world: ResearchWorld, **env: str) -> Any:
    return deep_research_runtime(
        ai_settings(world.client_id, approved_for=DEVELOP_ROUTE),
        env=env,
        transport=RecordedAgents(ANSWERS),
        signer=Signer(),
    )


def _class_c_and_free(route: Any) -> None:
    assert route.retrieval_mode is RetrievalMode.LIVE
    assert route.price_usd_per_call == 0
    assert route.route.approved_for == frozenset({DataClass.CLASS_C_INTERNAL})


def test_with_neither_key_the_composition_is_the_wikipedia_one(
    research: ResearchWorld,  # noqa: F811
) -> None:
    runtime = _compose(research, **WIKI)
    assert runtime is not None and runtime.retrieval is not None
    assert runtime.retrieval.fetch_route.route.route_id == "wikipedia-public-web_fetch"
    assert (runtime.datasets, runtime.archives, runtime.ladder) == ((), (), None)
    assert runtime.inputs().web_retrieval == runtime.retrieval.identity()


def test_the_contact_opens_every_public_host_and_the_register_to_the_ladder(
    research: ResearchWorld,  # noqa: F811
) -> None:
    runtime = _compose(research, **WIKI, AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT=CONTACT)
    retrieval = runtime.retrieval
    # The search is still Wikipedia's; pages come from any public host, robots.txt obeyed.
    assert retrieval.search_route.route.route_id == "wikipedia-public-web_search"
    assert retrieval.fetch_route.route.route_id == "public-web-fetch"
    assert retrieval.fetch_route.adapter_id == "public-https-1"
    # The polite transport, which reads robots.txt and paces each host (chunk 5).
    assert isinstance(retrieval.fetcher._transport, PublicHttpsTransport)
    _class_c_and_free(retrieval.search_route)
    _class_c_and_free(retrieval.fetch_route)
    assert runtime.ladder == LadderConfig(register=REPUTATION_REGISTER_V1)
    assert (runtime.datasets, runtime.archives) == ((), ())


def test_each_listed_connector_is_composed_on_its_own_free_class_c_route(
    research: ResearchWorld,  # noqa: F811
) -> None:
    runtime = _compose(
        research,
        **WIKI,
        AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT=CONTACT,
        AIA_DEEP_RESEARCH_CONNECTORS="datastat, nkod,eurostat,openalex,ares,wayback",
    )
    assert [d.connector.connector_id for d in runtime.datasets] == [
        "csu-datastat-1",
        "nkod-sparql-1",
        "eurostat-statistics-1",
        "openalex-works-1",
        "ares-subject-1",
    ]
    assert [a.connector.connector_id for a in runtime.archives] == ["wayback-cdx-1"]
    for access in (*runtime.datasets, *runtime.archives):
        _class_c_and_free(access.route)
        assert access.route.adapter_id == access.connector.connector_id
        assert access.connector.retrieval_mode is RetrievalMode.LIVE
    assert runtime.archives[0].route.tool is ToolKind.ARCHIVE_LOOKUP
    zones = {d.connector.connector_id: d.route.route.zone for d in runtime.datasets}
    assert zones["csu-datastat-1"] is ResidencyZone.EU
    assert zones["openalex-works-1"] is ResidencyZone.NON_EU
    # The connectors' routes are part of every web track's inputs.
    identity = runtime.inputs().web_retrieval
    assert [row[1] for row in identity["datasets"]] == sorted(
        d.connector.connector_id for d in runtime.datasets
    )
    assert identity["archives"] == [
        ["connector-wayback", "wayback-cdx-1", "LIVE", 0.0],
    ]


@pytest.mark.parametrize(
    ("env", "names"),
    [
        (
            {**WIKI, "AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT": "not an address"},
            "AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT",
        ),
        (
            {
                "AIA_DEEP_RESEARCH_ENABLED": "true",
                "AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT": CONTACT,
            },
            "AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT needs AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED",
        ),
        (
            {**WIKI, "AIA_DEEP_RESEARCH_CONNECTORS": "datastat"},
            "AIA_DEEP_RESEARCH_CONNECTORS needs AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT",
        ),
        (
            {
                **WIKI,
                "AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT": CONTACT,
                "AIA_DEEP_RESEARCH_CONNECTORS": "datastat,google",
            },
            "'google' is not a connector",
        ),
        (
            {
                **WIKI,
                "AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT": CONTACT,
                "AIA_DEEP_RESEARCH_CONNECTORS": "procurement",
            },
            "procurement: no live notice source",
        ),
        (
            {
                **WIKI,
                "AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT": CONTACT,
                "AIA_DEEP_RESEARCH_CONNECTORS": "ares,ares",
            },
            "lists a connector twice",
        ),
    ],
)
def test_a_reach_that_cannot_be_composed_stops_the_worker_naming_its_key(
    research: ResearchWorld,  # noqa: F811
    env: dict[str, str],
    names: str,
) -> None:
    with pytest.raises(AIRuntimeConfigError, match=names):
        _compose(research, **env)


def test_the_reach_keys_are_off_unless_deep_research_is_on(
    research: ResearchWorld,  # noqa: F811
) -> None:
    with pytest.raises(AIRuntimeConfigError, match="needs AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED"):
        _compose(research, AIA_DEEP_RESEARCH_PUBLIC_FETCH_CONTACT=CONTACT)
    with pytest.raises(AIRuntimeConfigError, match="needs AIA_DEEP_RESEARCH_PUBLIC_FETCH"):
        _compose(research, AIA_DEEP_RESEARCH_CONNECTORS="datastat")
    assert _compose(research) is None
