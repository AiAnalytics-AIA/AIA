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

from aia_core.domain.ai_material import MaterialApproval, material_sha256
from aia_core.domain.ai_models import ModelCapability
from aia_core.domain.client_sources import (
    Locator,
    ReadingOutcome,
    Segment,
    SourceFamily,
    SourceReading,
    reading_of_segments,
)
from aia_core.domain.deep_research.request_limits import window_fits
from aia_core.domain.knowledge import KnowledgeKind
from aia_core.domain.residency import DataClass
from aia_core.domain.source_proposals import (
    BATCH_MAX_BYTES,
    MAX_REQUESTS,
    NotExtractable,
    SourceProposal,
    SourceProposals,
    batch_classification,
    batch_material,
    batches,
    ground,
    proposal_request,
    request_bytes,
    request_window_tokens,
    require_extractable,
    require_within_requests,
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
    third = BATCH_MAX_BYTES // 3 - 40
    longest = "e" * (BATCH_MAX_BYTES * 2 + 5)
    read = reading("a" * third, "b" * third, "c" * third, "d" * third, longest)
    made = batches(read)
    assert made == batches(read)
    assert [b.index for b in made] == list(range(len(made)))
    assert all(b.bytes <= BATCH_MAX_BYTES for b in made)
    # Every segment is there, in order, under its number in the reading.
    numbers = [n for b in made for n, _ in b.segments]
    assert numbers == sorted(numbers) and set(numbers) == {0, 1, 2, 3, 4}
    # A segment longer than a batch goes in pieces, each with the segment's locator.
    pieces = [s for b in made for n, s in b.segments if n == 4]
    assert len(pieces) == 3
    assert {p.locator for p in pieces} == {Locator(page=5)}
    assert "".join(p.text for p in pieces) == longest


@pytest.mark.parametrize(
    "texts",
    [
        # Short lines: ~28 bytes of JSON around each, which characters never counted (K2d6).
        ["x"] * 12_000,
        # Two-byte and four-byte characters, and control characters escaped to six.
        ["ř" * 30_000],
        ["😀" * 20_000],
        ["\x01" * 10_000],
    ],
    ids=["short-lines", "two-byte", "four-byte", "escaped"],
)
def test_a_batch_is_bounded_by_the_bytes_it_sends_whatever_the_text(texts: list[str]) -> None:
    made = batches(reading_of_segments("txt/1", [seg(t, i + 1) for i, t in enumerate(texts)]))
    window = request_window_tokens(4096)
    for batch in made:
        assert batch.bytes <= BATCH_MAX_BYTES
        request = proposal_request(batch, policy_version="p", max_output_tokens=4096)
        assert window_fits(request_bytes(request), window_tokens=window, output_tokens=4096)
    # Nothing lost or reordered: the text comes back whole.
    assert "".join(s.text for b in made for _, s in b.segments) == "".join(texts)


def test_a_document_needing_more_than_the_request_cap_is_refused_before_anything_is_sent() -> None:
    # Pages just over half a batch: each batch holds one, the packing's worst case. The
    # reading's own character cap is lifted here so that only the request cap is tested.
    def pages(n: int) -> SourceReading:
        half = "a" * (BATCH_MAX_BYTES // 2 + 1)
        return reading_of_segments("pdf/1", [seg(half, i + 1) for i in range(n)], limit=10**7)

    at_cap = batches(pages(MAX_REQUESTS))
    assert len(at_cap) == MAX_REQUESTS
    require_within_requests(at_cap)
    over = batches(pages(MAX_REQUESTS + 1))
    with pytest.raises(NotExtractable) as refused:
        require_within_requests(over)
    assert refused.value.reason == "too_many_requests"


def test_a_reading_at_the_character_cap_of_czech_text_fits_the_request_cap() -> None:
    """250,000 characters of two-byte text, in pages just over half a batch -- the packing's
    worst case -- still fit MAX_REQUESTS."""
    page = "ř" * (BATCH_MAX_BYTES // 4 + 10)
    count = 250_000 // len(page)
    made = batches(reading(*[page] * count))
    require_within_requests(made)
    assert len(made) <= MAX_REQUESTS


def test_a_source_marked_internal_is_sent_as_class_c_and_nothing_else_changes() -> None:
    """The owner's rule of 2026-10-19: a source a person marked "Interní dokument" is an
    internal AIA document, Class C; the request is otherwise the same bytes."""
    [batch] = batches(reading("Interní postup AIA.", "Druhý odstavec."))
    client = proposal_request(batch, policy_version="p1", max_output_tokens=2000)
    internal = proposal_request(batch, policy_version="p1", max_output_tokens=2000, internal=True)
    assert internal.data_classification is DataClass.CLASS_C_INTERNAL
    assert client.data_classification is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
    assert (internal.system, internal.messages) == (client.system, client.messages)


def test_an_operator_classification_raises_a_marked_batch_and_never_lowers_one() -> None:
    """Codex on #487: an operator's exact-bytes classification of what a batch sends raises a
    marked source's batch above Class C, as it raises every other rule-classified request;
    one that would lower an unmarked batch below Class A changes nothing."""
    [batch] = batches(reading("Interní postup AIA.", "Druhý odstavec."))

    def approval(data_class: DataClass) -> MaterialApproval:
        return MaterialApproval(
            sha256=material_sha256(batch_material(batch)),
            data_class=data_class,
            provenance="generated wholly by this test",
        )

    raised = batch_classification(
        batch, internal=True, approvals=[approval(DataClass.CLASS_A_CLIENT_CONFIDENTIAL)]
    )
    assert (raised.data_class, raised.source) == (DataClass.CLASS_A_CLIENT_CONFIDENTIAL, "operator")
    request = proposal_request(
        batch,
        policy_version="p1",
        max_output_tokens=2000,
        internal=True,
        approvals=[approval(DataClass.CLASS_A_CLIENT_CONFIDENTIAL)],
    )
    assert request.data_classification is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
    kept = batch_classification(
        batch, internal=False, approvals=[approval(DataClass.CLASS_C_INTERNAL)]
    )
    assert (kept.data_class, kept.source) == (
        DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
        "rule:client_source",
    )


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
