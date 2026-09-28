"""Internal knowledge: frozen and bounded, classed by kind, retrieved by code, terms listed."""

from __future__ import annotations

from typing import Any

from aia_core.domain.deep_research.contracts import FrozenKnowledge
from aia_core.domain.deep_research.knowledge_access import (
    ITEM_TEXT_CHARS,
    KNOWLEDGE_BYTES,
    UNRESOLVED_LINEAGE,
    client_terms,
    freeze_knowledge,
    retrieve,
)
from aia_core.domain.knowledge import KnowledgeItem, KnowledgeKind
from aia_core.domain.residency import DataClass


def _item(n: int, kind: KnowledgeKind, title: str, **fields: Any) -> KnowledgeItem:
    return KnowledgeItem(
        item_id=f"KNW-{n:014x}",
        client_id="CLI-1",
        kind=kind,
        title=title,
        summary=fields.pop("summary", ""),
        content=fields.pop("content", {}),
        revision=fields.pop("revision", 1),
    )


def test_each_kind_has_its_class_and_unrecorded_lineage_is_named() -> None:
    frozen = freeze_knowledge(
        [
            _item(1, KnowledgeKind.DOCUMENT, "Interní zpráva"),
            _item(2, KnowledgeKind.FACT, "Podíl na trhu"),
            _item(3, KnowledgeKind.DATASET, "Prodeje 2025"),
            _item(4, KnowledgeKind.FINDING, "Zjištění ze studie"),
        ]
    )
    by_kind = {k.kind: k for k in frozen.items}
    assert by_kind["DOCUMENT"].data_class is DataClass.CLASS_A_CLIENT_CONFIDENTIAL
    assert by_kind["FACT"].data_class is DataClass.CLASS_B_DERIVED_CLIENT
    assert by_kind["DATASET"].lineage == (UNRESOLVED_LINEAGE,)
    assert by_kind["FINDING"].lineage == (UNRESOLVED_LINEAGE,)
    assert by_kind["FACT"].lineage == ()


def test_the_frozen_text_is_title_summary_and_text_normalised_with_its_revision() -> None:
    frozen = freeze_knowledge(
        [
            _item(
                5,
                KnowledgeKind.DOCUMENT,
                "Zpráva",
                summary="Shrnutí\u00a0zprávy",
                content={"text": "Tělo   zprávy.", "public": True},
                revision=3,
            )
        ]
    )
    (source,) = frozen.items
    assert source.ref == "KNW-00000000000005@3"
    assert source.text == "Zpráva Shrnutí zprávy Tělo zprávy."
    assert source.public is True and source.truncated is False


def test_nothing_is_cut_silently() -> None:
    long = _item(
        6, KnowledgeKind.DOCUMENT, "Dlouhý", content={"text": "x" * (ITEM_TEXT_CHARS + 50)}
    )
    (source,) = freeze_knowledge([long]).items
    assert source.truncated and len(source.text) == ITEM_TEXT_CHARS
    many = [
        _item(100 + i, KnowledgeKind.DOCUMENT, f"D{i}", content={"text": "y" * 15_000})
        for i in range(12)
    ]
    frozen = freeze_knowledge(many)
    assert sum(len(k.text.encode()) for k in frozen.items) <= KNOWLEDGE_BYTES
    assert frozen.omitted_ids and len(frozen.items) + len(frozen.omitted_ids) == 12


def _frozen() -> FrozenKnowledge:
    return freeze_knowledge(
        [
            _item(
                10, KnowledgeKind.FACT, "Ovesné nápoje", summary="Ovesné nápoje rostou ve městech."
            ),
            _item(11, KnowledgeKind.FACT, "Cenová politika", summary="Ovesné nápoje jsou dražší."),
            _item(12, KnowledgeKind.FACT, "Logistika", summary="Sklady v Brně."),
        ]
    )


def test_retrieval_ranks_title_words_double_and_returns_nothing_unrelated() -> None:
    found = retrieve(_frozen(), ["Proč lidé kupují ovesné nápoje?"], limit=5)
    assert [k.title for k in found] == ["Ovesné nápoje", "Cenová politika"]
    assert retrieve(_frozen(), ["Kosmetika pro psy"], limit=5) == ()
    assert retrieve(_frozen(), ["ovesné"], limit=1)[0].title == "Ovesné nápoje"
    assert retrieve(_frozen(), [], limit=5) == ()


def test_client_terms_are_identity_and_every_non_public_entity_or_term() -> None:
    frozen = freeze_knowledge(
        [
            _item(20, KnowledgeKind.ENTITY, "Pivovar Kotelna"),
            _item(21, KnowledgeKind.TERM, "Projekt Jasan"),
            _item(22, KnowledgeKind.ENTITY, "Veřejná konkurence", content={"public": True}),
            _item(23, KnowledgeKind.FACT, "Fakt, ne termín"),
        ]
    )
    terms = client_terms(
        identity=[("client.name", "Acme Nápoje"), ("client.slug", "acme"), ("study.slug", "x")],
        knowledge=frozen,
    )
    assert [(t.term, t.source) for t in terms] == [
        ("Acme Nápoje", "client.name"),
        ("acme", "client.slug"),
        ("Pivovar Kotelna", "knowledge:KNW-00000000000014@1"),
        ("Projekt Jasan", "knowledge:KNW-00000000000015@1"),
    ]
