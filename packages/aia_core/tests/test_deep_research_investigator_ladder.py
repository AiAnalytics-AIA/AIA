"""The investigator's ``ladder`` action as code plans it: refs into a lead, or a refusal.

Plan chunk 10. The model names refs and checkable text, never a URL; code resolves
the refs it created into an :class:`AcquisitionLead`, and counts what a climb sent
against the track's allowance. Fictional ``.example`` pages; no network.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import Any

from aia_core.domain.deep_research.acquisition import (
    AcquisitionLead,
    LadderRecord,
    LadderStop,
    LeadOrigin,
)
from aia_core.domain.deep_research.agents import InvestigatorTurn
from aia_core.domain.deep_research.contracts import (
    RetrievalMode,
    SnapshotLink,
    SourceSnapshot,
)
from aia_core.domain.deep_research.investigator import (
    ActionDecision,
    ActionOutcome,
    ActionRecord,
    Allowance,
    HitRecord,
    Refusal,
    TrackRefs,
    TrackState,
    plan_actions,
    turn_input,
)
from aia_core.domain.deep_research.sources import SOURCE_TABLE_V1
from aia_core.domain.residency import DataClass

NEWS = "https://zpravy.example/trh"
STAT = "https://stat.example/tabulka"
WIDE = Allowance(turns=6, searches=4, opens=8)


def snapshot(url: str, text: str, links: tuple[SnapshotLink, ...] = ()) -> SourceSnapshot:
    sha = hashlib.sha256(text.encode()).hexdigest()
    return SourceSnapshot(
        snapshot_id="SNP-" + sha[:24],
        url=url,
        canonical_url=url,
        final_url=url,
        redirects=(),
        title="Titulek stránky",
        retrieved_at=datetime(2026, 9, 1, tzinfo=UTC),
        http_status=200,
        content_type="text/html",
        raw_sha256=sha,
        raw_bytes=len(text),
        text=text,
        text_sha256=sha,
        truncated=False,
        adapter="recorded",
        request_id=None,
        retrieval_mode=RetrievalMode.RECORDED,
        instructions_detected=(),
        links=links,
    )


NEWS_PAGE = snapshot(
    NEWS,
    "Trh rostlinných nápojů roste, uvádí úřad ve své tabulce.",
    (SnapshotLink(kind="anchor", url=STAT, text="Tabulka spotřeby"),),
)


def state_with_news() -> TrackState:
    state = TrackState(refs=TrackRefs(SOURCE_TABLE_V1))
    state.apply(
        [
            ActionRecord(
                index=0,
                kind="search",
                purpose="p",
                query="trh nápojů",
                lang="cs",
                decision=ActionDecision.SENT,
                outcome=ActionOutcome.SUCCEEDED,
                data_class=DataClass.CLASS_C_INTERNAL,
                hits=(HitRecord(url=NEWS, title="Zpráva", snippet="", rank=1),),
            )
        ],
        {},
    )
    state.apply(
        [
            ActionRecord(
                index=0,
                kind="open",
                purpose="p",
                ref="R1",
                url=NEWS,
                decision=ActionDecision.SENT,
                outcome=ActionOutcome.SUCCEEDED,
                snapshot_artifact_id="A1",
            )
        ],
        {"A1": (NEWS_PAGE, date(2025, 6, 1))},
    )
    return state


def ladder(**fields: Any) -> dict[str, Any]:
    return {
        "kind": "ladder",
        "need": "tabulka spotřeby",
        "publisher": None,
        "title": None,
        "phrase": "Tabulka 7",
        "doi": None,
        "source": None,
        "link": None,
        "purpose": "primární zdroj",
        **fields,
    }


def turn(*actions: dict[str, Any]) -> InvestigatorTurn:
    return InvestigatorTurn.model_validate(
        {"evidence": [], "summary": "", "leads": [], "next": list(actions)}
    )


def test_a_ladder_s_refs_become_a_lead_code_resolved() -> None:
    state = state_with_news()
    [planned] = plan_actions(
        turn(ladder(source="S1", link="L1", publisher="Úřad", title="Ročenka 2025")),
        state,
        WIDE,
    )
    assert planned.record is None and planned.kind == "ladder"
    assert planned.source == "S1" and planned.ref == "L1"
    assert planned.lead == AcquisitionLead(
        need="tabulka spotřeby",
        publisher="Úřad",
        title="Ročenka 2025",
        phrases=("Tabulka 7",),
        urls=(STAT,),
        cited_on=NEWS,
        origin=LeadOrigin.INVESTIGATOR,
    )


def test_a_ladder_is_refused_for_an_unknown_or_wrong_ref_or_an_uncheckable_lead() -> None:
    state = state_with_news()
    planned = plan_actions(
        turn(
            ladder(source="S9"),
            ladder(source="R1"),  # a result is not a captured source
            ladder(link="S1"),  # a source is not a link to open
            ladder(phrase=None),  # nothing code could recognise when found
            ladder(doi="not-a-doi"),
        ),
        state,
        WIDE,
    )
    assert [(p.record.decision, p.record.reason) for p in planned if p.record] == [
        (ActionDecision.REFUSED, Refusal.UNKNOWN_REF),
        (ActionDecision.REFUSED, Refusal.NOT_READABLE),
        (ActionDecision.REFUSED, Refusal.NOT_OPENABLE),
        (ActionDecision.REFUSED, Refusal.LEAD_UNCHECKABLE),
        (ActionDecision.REFUSED, Refusal.LEAD_UNCHECKABLE),
    ]


def test_a_ladder_with_no_allowance_left_is_refused() -> None:
    [planned] = plan_actions(
        turn(ladder()), state_with_news(), Allowance(turns=6, searches=0, opens=1)
    )
    assert planned.record is not None and planned.record.reason == Refusal.ALLOWANCE_SPENT


def test_what_a_climb_sent_counts_against_the_track_and_is_shown_next_turn() -> None:
    state = state_with_news()
    lead = AcquisitionLead(need="n", phrases=("Tabulka 7",), origin=LeadOrigin.INVESTIGATOR)
    record = LadderRecord(
        lead=lead,
        stop=LadderStop.GAP,
        acquisition=None,
        gap=None,
        rungs_tried=(),
        attempts=(),
        requests=5,
        searches=3,
        fetches=2,
    )
    before = (state.searches_used, state.opens_used)
    state.apply(
        [
            ActionRecord(
                index=0,
                kind="ladder",
                purpose="p",
                decision=ActionDecision.SENT,
                outcome=ActionOutcome.FAILED,
                reason="not_found",
                ladder=record,
            )
        ],
        {},
    )
    assert (state.searches_used, state.opens_used) == (before[0] + 3, before[1] + 2)
    # A ladder never counts toward the refusal limit: it ran.
    assert not state.refusals()
    view = turn_input(
        state,
        track=_track(),
        brief=_brief(),
        sub_questions=(),
        suggested_queries=(),
        turn=4,
        allowance=WIDE,
        stop={},
        findings=(),
        reading=(),
        waiting=(),
    )["last_turn"][0]
    assert view["kind"] == "ladder" and view["reason"] == "not_found"
    assert view["ladder"] == {"stop": "gap", "rungs_tried": [], "requests": 5}


def _track() -> Any:
    class _Subject:
        kind = type("K", (), {"value": "object"})()
        text = "Mandlový nápoj"

    return type("T", (), {"track_id": "DRT-1", "subject": _Subject()})()


def _brief() -> Any:
    return type("B", (), {"title": "Brief", "goal": "Cíl"})()
