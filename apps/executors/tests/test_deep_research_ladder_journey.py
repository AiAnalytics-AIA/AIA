"""The investigator's ``ladder`` action end to end, recorded (plan chunk 10).

The agent-directed journey of ``test_deep_research_investigator_journey.py`` -- worker,
gateway, gate, executors, the fictional ``*-dr.example`` web -- with the almond track
scripted to use the acquisition ladder: it opens a news page, asks the ladder for the
table the page links (rung 1 reaches it; it becomes ``S2``), asks it for a methodology
nobody publishes (an acquisition gap), grounds a finding on the table the ladder
captured, and finishes. Nothing leaves the process.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any

import pytest
from aia_core.application.acquisition_ladder import LadderConfig
from aia_core.application.web_retrieval import DatasetAccess
from aia_core.domain.deep_research.contracts import (
    Channel,
    RetrievalMode,
    StopReason,
    SubjectKind,
    TrackStatus,
)
from aia_core.domain.deep_research.investigator import INVESTIGATOR_VERSION
from aia_core.domain.deep_research.tooling import ToolKind, ToolRoute
from aia_core.domain.residency import DataClass, ProviderRoute, ResidencyZone
from aia_core.infrastructure.dataset_connectors import RecordedDatasetConnector
from aia_core.infrastructure.storage import InMemoryArtifactStore
from deep_research_fixtures import (
    ALMOND,
    ANSWERS,
)
from test_deep_research_investigator_journey import (  # type: ignore[import-not-found]
    TURNS,
    ScriptedInvestigator,
    directed,
    start_web,
    stored,
    track_result,
)
from test_deep_research_journey import (  # type: ignore[import-not-found]
    ResearchWorld,
    drain,
    read,
    research,  # noqa: F401  (a fixture)
    tid,
    worker,
)

W = Channel.WEB
TABLE = "https://stat-dr.example/tabulka-2025"


def _ladder(**fields: Any) -> dict[str, Any]:
    return {
        "kind": "ladder",
        "publisher": None,
        "title": None,
        "phrase": None,
        "doi": None,
        "source": None,
        "link": None,
        **fields,
    }


ALMOND_TURNS: list[dict[str, Any]] = [
    {
        "evidence": [],
        "summary": "Hledám.",
        "leads": [],
        "next": [
            {
                "kind": "search",
                "query": "trh rostlinných nápojů",
                "site": None,
                "phrase": None,
                "lang": "cs",
                "purpose": "najít zdroje",
            }
        ],
    },
    {
        "evidence": [],
        "summary": "",
        "leads": [],
        "next": [{"kind": "open", "ref": "R1", "purpose": "zpráva o trhu"}],
    },
    {
        "evidence": [],
        "summary": "Zpráva jen opakuje čísla úřadu.",
        "leads": [],
        "next": [
            _ladder(
                need="tabulka, ze které čísla zprávy pocházejí",
                phrase="Rostlinné nápoje kupuje 45 % domácností",
                source="S1",
                link="L1",
                purpose="primární zdroj",
            ),
            _ladder(
                need="metodika měření spotřeby",
                publisher="Fiktivní úřad pro nápoje",
                title="Metodika spotřeby nápojů 2025",
                source="S1",
                purpose="metodika",
            ),
            # Nothing code could recognise when found: refused before any call.
            _ladder(need="něco dalšího", purpose="nejasné"),
        ],
    },
    {
        "evidence": [
            {
                "source_id": "S2",
                "quote": (
                    "Spotřeba rostlinných nápojů v Česku vzrostla v roce 2025 o 12,5 % "
                    "na 41 milionů litrů."
                ),
                "claim": (
                    "Spotřeba rostlinných nápojů v Česku vzrostla v roce 2025 o 12,5 % "
                    "na 41 milionů litrů."
                ),
                "measures": [
                    {"value": 12.5, "unit": "%", "period": "2025", "geography": "Česko"},
                    {
                        "value": 41,
                        "scale": 1000000,
                        "unit": "litrů",
                        "period": "2025",
                        "geography": "Česko",
                        "measure_name": "spotřeba rostlinných nápojů",
                        "basis": "preliminary",
                    },
                ],
            }
        ],
        "summary": "Tabulka úřadu.",
        "leads": [],
        "next": [{"kind": "finish", "gaps": []}],
    },
]


@pytest.fixture
def ladder_run(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> tuple[ResearchWorld, ScriptedInvestigator, str]:
    turns = json.loads(json.dumps(TURNS))
    turns[ALMOND] = ALMOND_TURNS
    agents = ScriptedInvestigator(ANSWERS, turns=turns)
    runtime = directed(research, agents)
    run_id = start_web(research)
    assert drain(worker(research, database_url, store, build, runtime)) == 6
    return research, agents, run_id


def test_a_ladder_reaches_the_linked_table_and_names_what_it_could_not_reach(
    ladder_run: tuple[ResearchWorld, ScriptedInvestigator, str], store: InMemoryArtifactStore
) -> None:
    world, agents, run_id = ladder_run
    track = tid(SubjectKind.OBJECT, ALMOND, W)
    _run, bundle = read(world, run_id, store)
    entry = {t.track_id: t for t in bundle.tracks}[track]
    assert (entry.status, entry.stop_reason) == (TrackStatus.COMPLETED, StopReason.AGENT_FINISHED)

    result = track_result(world, store, run_id, track)
    transcript = stored(world, store, result["transcript_artifact_id"])
    ladders = [a for a in transcript["turns"][2]["actions"] if a["kind"] == "ladder"]
    found, gap, unclear = ladders
    # Rung 1: the link the news carries, opened through the gate; the capture is S2.
    assert (found["decision"], found["outcome"], found["source"]) == ("sent", "succeeded", "S2")
    assert found["ladder"]["stop"] == "acquired"
    assert found["ladder"]["acquisition"]["rung"] == "1_direct_link"
    assert found["ladder"]["acquisition"]["url"] == TABLE
    assert found["ladder"]["acquisition"]["match"] == "phrase"
    # Nothing reached the methodology: an acquisition gap naming who, what and why.
    assert (gap["decision"], gap["outcome"], gap["reason"]) == ("sent", "failed", "not_found")
    named = gap["ladder"]["gap"]
    assert (named["publisher"], named["title"], named["reason"]) == (
        "Fiktivní úřad pro nápoje",
        "Metodika spotřeby nápojů 2025",
        "not_found",
    )
    assert named["rungs_tried"][-1] == "11_gap" and named["how_to_obtain"]
    assert (unclear["decision"], unclear["reason"]) == ("refused", "lead_uncheckable")
    assert transcript["counts"]["ladders"] == 3
    assert transcript["counts"]["acquired"] == 1
    assert transcript["counts"]["acquisition_gaps"] == 1

    # The next turn is told, by ref and reason, what each ladder did.
    fourth = agents.payload(ALMOND, 4)
    views = [a for a in fourth["last_turn"] if a["kind"] == "ladder"]
    assert views[0]["ladder"]["rung"] == "1_direct_link" and views[0]["source"] == "S2"
    assert views[1]["ladder"]["gap"]["reason"] == "not_found"
    assert [s["ref"] for s in fourth["sources"]] == ["S1", "S2"]
    assert "https://" not in json.dumps(fourth, ensure_ascii=False)

    # A finding grounded on what the ladder captured; the gap is in the track's gaps.
    # (Q1 grounds the same quote on the same table, so the merge keeps one of the two.)
    [evidence] = result["evidence"]
    assert evidence["source_url"] == TABLE and evidence["track_id"] == track
    assert transcript["turns"][3]["grounded"] == [evidence["evidence_id"]]
    assert any("nedostupné: not_found" in g for g in result["gaps"])


def test_a_set_ladder_configuration_is_part_of_a_track_s_inputs(
    research: ResearchWorld,  # noqa: F811
) -> None:
    runtime = directed(research, ScriptedInvestigator(ANSWERS))
    # None set (every composition today): exactly the investigator's version.
    assert runtime.inputs().investigator == INVESTIGATOR_VERSION
    configured = dataclasses.replace(runtime, ladder=LadderConfig(crawls=("CC-MAIN-2024-10",)))
    identity = LadderConfig(crawls=("CC-MAIN-2024-10",)).identity()
    assert configured.inputs().investigator == f"{INVESTIGATOR_VERSION}/ladder-{identity}"
    assert configured.versions()["investigator"] == configured.inputs().investigator


# --------------------------------------------------------------------------- #
# A dataset route the composition gives reaches the ladder (plan chunk 23a)
# --------------------------------------------------------------------------- #

OPENALEX = "openalex-works-1"
DOI = "10.5555/fikt.2025.7"
PAPER = "Spotřeba rostlinných nápojů 2025"
OA_COLUMNS = [
    "is_oa",
    "version",
    "license",
    "landing_page_url",
    "pdf_url",
    "source",
    "source_type",
    "best_oa",
]


def _openalex() -> RecordedDatasetConnector:
    """OpenAlex, recorded: the DOI's one open-access location is the office's table."""
    return RecordedDatasetConnector(
        connector_id=OPENALEX,
        exchanges={
            f"doi:{DOI}": {
                "result": {
                    "title": PAPER,
                    "publisher": "Fiktivní vydavatel",
                    "source_url": "https://api.openalex.example/works",
                    "columns": [{"key": c, "label": c} for c in OA_COLUMNS],
                    "rows": [
                        {
                            "key": "loc1",
                            "label": "řádek loc1",
                            "values": [
                                "true",
                                "publishedVersion",
                                "cc-by",
                                TABLE,
                                None,
                                "U",
                                "r",
                                "yes",
                            ],
                        }
                    ],
                },
                "raw": "{}",
            }
        },
    )


def _dataset_route(adapter_id: str) -> ToolRoute:
    return ToolRoute(
        route=ProviderRoute(
            route_id="recorded-dataset-query",
            provider="recorded",
            zone=ResidencyZone.EU,
            eu_processing_approved=True,
            excluded_from_training=True,
            retention_days=0,
            approved_for=frozenset({DataClass.CLASS_C_INTERNAL}),
        ),
        tool=ToolKind.DATASET_QUERY,
        adapter_id=adapter_id,
        retrieval_mode=RetrievalMode.RECORDED,
        price_usd_per_call=0.0,
    )


def _with_openalex(runtime: Any, connector: RecordedDatasetConnector) -> Any:
    return dataclasses.replace(
        runtime, datasets=(DatasetAccess(route=_dataset_route(OPENALEX), connector=connector),)
    )


SCHOLARLY_TURNS: list[dict[str, Any]] = [
    ALMOND_TURNS[0],
    ALMOND_TURNS[1],
    {
        "evidence": [],
        "summary": "Zpráva cituje studii podle DOI.",
        "leads": [],
        "next": [
            _ladder(
                need="studie, ze které čísla zprávy pocházejí",
                title=PAPER,
                doi=DOI,
                source="S1",
                purpose="primární zdroj",
            )
        ],
    },
    ALMOND_TURNS[3],
]


def test_a_dataset_route_the_composition_gives_is_one_the_ladder_reaches(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
) -> None:
    turns = json.loads(json.dumps(TURNS))
    turns[ALMOND] = SCHOLARLY_TURNS
    agents = ScriptedInvestigator(ANSWERS, turns=turns)
    openalex = _openalex()
    runtime = _with_openalex(directed(research, agents), openalex)
    run_id = start_web(research)
    assert drain(worker(research, database_url, store, build, runtime)) == 6

    track = tid(SubjectKind.OBJECT, ALMOND, W)
    transcript = stored(
        research, store, track_result(research, store, run_id, track)["transcript_artifact_id"]
    )
    [climb] = [a for a in transcript["turns"][2]["actions"] if a["kind"] == "ladder"]
    # The DOI was resolved through the connector the composition gave, and its open-access
    # copy opened through the gate: the office's table, captured as S2.
    assert f"doi:{DOI}" in openalex.calls
    assert climb["ladder"]["stop"] == "acquired"
    assert climb["ladder"]["acquisition"]["rung"] == "7_scholarly_identity"
    assert (climb["ladder"]["acquisition"]["url"], climb["source"]) == (TABLE, "S2")


def test_dataset_routes_join_a_track_s_inputs_only_when_given(
    research: ResearchWorld,  # noqa: F811
) -> None:
    runtime = directed(research, ScriptedInvestigator(ANSWERS))
    assert runtime.retrieval is not None
    # None given (every composition before chunk 23): exactly the retrieval's identity.
    assert runtime.inputs().web_retrieval == runtime.retrieval.identity()
    given = _with_openalex(runtime, _openalex())
    identity = given.inputs().web_retrieval
    assert identity["datasets"] == [["recorded-dataset-query", OPENALEX, "RECORDED", 0.0]]
    assert {k: v for k, v in identity.items() if k != "datasets"} == runtime.retrieval.identity()


def test_a_dataset_route_without_web_retrieval_is_refused(
    research: ResearchWorld,  # noqa: F811
) -> None:
    runtime = _with_openalex(directed(research, ScriptedInvestigator(ANSWERS)), _openalex())
    with pytest.raises(ValueError, match="need web retrieval"):
        dataclasses.replace(runtime, retrieval=None)


# --------------------------------------------------------------------------- #
# A finding on a retracted work is quarantined at merge (plan chunk 46)
# --------------------------------------------------------------------------- #

CROSSREF = "crossref-works-1"


def _crossref(retracted: bool) -> RecordedDatasetConnector:
    """Crossref, recorded: the table's DOI with a retraction notice, or with none."""
    rows = (
        [
            {
                "key": "u1",
                "label": "1. retraction",
                "values": [
                    "retraction",
                    "retracted",
                    "10.5555/notice.1",
                    "retraction-watch",
                    "2026-01-05",
                ],
            }
        ]
        if retracted
        else []
    )
    return RecordedDatasetConnector(
        connector_id=CROSSREF,
        exchanges={
            f"doi:{DOI}": {
                "result": {
                    "title": f"Crossref record of {DOI}",
                    "publisher": "Crossref (with Retraction Watch)",
                    "source_url": f"https://api.crossref.example/works/{DOI}",
                    "columns": [
                        {"key": k, "label": k}
                        for k in ("type", "status", "notice_doi", "source", "updated")
                    ],
                    "rows": rows,
                },
                "raw": "{}",
            }
        },
    )


def _table_names_its_doi(tmp: Any) -> Any:
    """The investigator journey's web, with the office's table naming its own DOI."""
    from test_deep_research_investigator_journey import WEB  # type: ignore[import-not-found]

    web = json.loads(WEB.read_text(encoding="utf-8"))
    page = web["pages"][TABLE]
    page["body"] = page["body"].replace(
        "</title>", f'</title><meta name="citation_doi" content="https://doi.org/{DOI}">', 1
    )
    path = tmp / "web_with_doi.json"
    path.write_text(json.dumps(web, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.mark.parametrize("retracted", [True, False])
def test_a_finding_resting_on_a_retracted_work_is_quarantined_at_merge(
    research: ResearchWorld,  # noqa: F811
    database_url: str,
    store: InMemoryArtifactStore,
    build: Any,
    tmp_path: Any,
    retracted: bool,
) -> None:
    turns = json.loads(json.dumps(TURNS))
    turns[ALMOND] = ALMOND_TURNS
    agents = ScriptedInvestigator(ANSWERS, turns=turns)
    crossref = _crossref(retracted)
    base = directed(research, agents, fixture=_table_names_its_doi(tmp_path))
    runtime = dataclasses.replace(
        base,
        datasets=(
            DatasetAccess(route=_dataset_route(OPENALEX), connector=_openalex()),
            DatasetAccess(route=_dataset_route(CROSSREF), connector=crossref),
        ),
    )
    run_id = start_web(research)
    assert drain(worker(research, database_url, store, build, runtime)) == 6

    # The merge asked Crossref about the table's DOI once, however many tracks cited it.
    assert crossref.calls == [f"doi:{DOI}"]
    _run, bundle = read(research, run_id, store)
    on_table = [a for a in bundle.accepted if a.evidence.source_url == TABLE]
    reasons = {q.reason for q in bundle.quarantined}
    if retracted:
        assert on_table == []
        assert "retracted_source" in {r.value for r in reasons}
        (q,) = [q for q in bundle.quarantined if q.reason.value == "retracted_source"][:1]
        assert DOI in q.detail and "10.5555/notice.1" in q.detail
    else:
        assert on_table, "a work with no notice stands"
        assert "retracted_source" not in {r.value for r in reasons}
