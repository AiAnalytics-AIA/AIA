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
from aia_core.domain.deep_research.contracts import Channel, StopReason, SubjectKind, TrackStatus
from aia_core.domain.deep_research.investigator import INVESTIGATOR_VERSION
from aia_core.infrastructure.storage import InMemoryArtifactStore
from test_deep_research_investigator_journey import (  # type: ignore[import-not-found]
    TURNS,
    ScriptedInvestigator,
    directed,
    start_web,
    stored,
    track_result,
)
from test_deep_research_journey import (  # type: ignore[import-not-found]
    ALMOND,
    ANSWERS,
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
