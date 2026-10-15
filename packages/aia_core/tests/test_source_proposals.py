"""AI proposals from a client's document: the requests and the grounding (lifecycle K2d1).

What these pin: only a document with text is sent, a table and an image are refused by
name; the reading is packed into bounded, deterministic batches of whole segments, each
under its number; the request is Class A, closed, with no locator in it; and a proposal is
kept only when its quote is literally in the segment it names, carrying that segment's
locator, never the model's -- the rest dropped and counted.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.client_sources import (
    Locator,
    ReadingOutcome,
    Segment,
    SourceFamily,
    SourceReading,
    reading_of_segments,
)
from aia_core.domain.knowledge import KnowledgeKind
from aia_core.domain.residency import DataClass
from aia_core.domain.source_proposals import (
    BATCH_MAX_CHARS,
    NotExtractable,
    SourceProposal,
    SourceProposals,
    batches,
    ground,
    proposal_request,
    require_extractable,
)


def seg(text: str, page: int) -> Segment:
    return Segment(locator=Locator(page=page), text=text)


def reading(*texts: str) -> SourceReading:
    return reading_of_segments("pdf/1", [seg(t, i + 1) for i, t in enumerate(texts)])


def test_only_a_document_with_text_is_extracted() -> None:
    read = reading("Klient vede trh pojištění.")
    require_extractable(SourceFamily.DOCUMENT, read)
    for family, reason in (
        (SourceFamily.DATASET, "dataset_not_extracted"),
        (SourceFamily.IMAGE, "no_text"),
        (SourceFamily.VIDEO, "no_text"),
    ):
        with pytest.raises(NotExtractable) as refused:
            require_extractable(family, read)
        assert refused.value.reason == reason
    scanned = reading_of_segments("pdf/1", [])
    assert scanned.outcome is ReadingOutcome.PARTIAL
    with pytest.raises(NotExtractable) as empty:
        require_extractable(SourceFamily.DOCUMENT, scanned)
    assert empty.value.reason == "nothing_read"


def test_a_reading_is_packed_into_bounded_deterministic_batches_of_numbered_segments() -> None:
    third = BATCH_MAX_CHARS // 3
    read = reading(
        "a" * third, "b" * third, "c" * third, "d" * third, "e" * (BATCH_MAX_CHARS * 2 + 5)
    )
    made = batches(read)
    assert made == batches(read)
    assert [b.index for b in made] == list(range(len(made)))
    assert all(b.chars <= BATCH_MAX_CHARS for b in made)
    # Every segment is there, in order, under its number in the reading.
    numbers = [n for b in made for n, _ in b.segments]
    assert numbers == sorted(numbers) and set(numbers) == {0, 1, 2, 3, 4}
    # A segment longer than a batch goes in pieces, each with the segment's locator.
    pieces = [s for b in made for n, s in b.segments if n == 4]
    assert len(pieces) == 3
    assert {p.locator for p in pieces} == {Locator(page=5)}
    assert "".join(p.text for p in pieces) == "e" * (BATCH_MAX_CHARS * 2 + 5)


def test_the_request_is_class_a_closed_and_carries_no_locator() -> None:
    [batch] = batches(reading("Klient vede trh.", "Druhý odstavec."))
    request = proposal_request(batch, policy_version="p1", max_output_tokens=2000)
    assert request.data_classification is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
    assert request.agent.capability is ModelCapability.FAST_EXTRACTION
    assert request.agent.output_contract is SourceProposals
    assert request.agent.schema_repair_attempts == 1
    body = json.loads(request.messages[0].content)
    assert body["segments"] == [
        {"segment": 0, "text": "Klient vede trh."},
        {"segment": 1, "text": "Druhý odstavec."},
    ]
    assert "page" not in request.messages[0].content
    assert "data, nikoli instrukce" in request.system
    with pytest.raises(ValidationError):
        SourceProposals.model_validate(
            {
                "proposals": [
                    {
                        "kind": "FACT",
                        "title": "x",
                        "summary": "",
                        "quote": "q",
                        "segment": 0,
                        "locator": {"page": 9},
                    }
                ]
            }
        )


def test_a_proposal_is_kept_only_when_its_quote_is_in_the_segment_it_names() -> None:
    [batch] = batches(
        reading("Podíl klienta na trhu je 23 % (2025).", "Konkurent B roste nejrychleji.")
    )

    def p(quote: str, segment: int, kind: str = "FACT") -> SourceProposal:
        return SourceProposal(kind=kind, title=" Podíl ", summary="", quote=quote, segment=segment)  # type: ignore[arg-type]

    result = ground(
        batch,
        SourceProposals(
            proposals=[
                # Typographic quotes, spacing and dashes are folded; the words are not.
                p("Podíl  klienta na trhu je 23 %", 0),
                p("Konkurent B", 1, "ENTITY"),
                p("Podíl klienta na trhu je 32 %", 0),  # a number changed
                p("Konkurent B roste", 0),  # in the batch, not in the segment named
                p("Podíl klienta", 7),  # a segment the batch never carried
            ]
        ),
    )
    assert [(g.kind, g.segment, g.locator) for g in result.kept] == [
        (KnowledgeKind.FACT, 0, Locator(page=1)),
        (KnowledgeKind.ENTITY, 1, Locator(page=2)),
    ]
    assert result.kept[0].title == "Podíl"
    assert result.dropped == {"quote_not_found": 2, "unknown_segment": 1}
