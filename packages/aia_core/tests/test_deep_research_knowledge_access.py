"""Internal knowledge: frozen and bounded, classed by kind, retrieved by code, terms listed."""

from __future__ import annotations

from typing import Any

from aia_core.domain.deep_research.contracts import FrozenKnowledge
from aia_core.domain.deep_research.knowledge_access import (
    ITEM_TEXT_CHARS,
    KNOWLEDGE_BYTES,
    UNRESOLVED_LINEAGE,
    DocumentText,
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


# ------------------------------------- a document item's text from its source (K8b)

READING = "a" * 64


class _Reader:
    """A :class:`DocumentReader` over given texts, counting what it read."""

    def __init__(self, texts: dict[str, DocumentText]) -> None:
        self.texts = texts
        self.read_ids: list[str] = []

    def size(self, item: KnowledgeItem) -> int | None:
        found = self.texts.get(item.item_id)
        return len(found.text) if found is not None else None

    def read(self, item: KnowledgeItem) -> DocumentText | None:
        self.read_ids.append(item.item_id)
        return self.texts.get(item.item_id)


def _by_id(texts: dict[str, DocumentText]) -> _Reader:
    return _Reader(texts)


def _doc(n: int, **fields: Any) -> KnowledgeItem:
    return _item(
        n, KnowledgeKind.DOCUMENT, "Výroční zpráva", content={"source_id": "SRC-1"}, **fields
    )


def test_a_document_items_text_is_what_its_reading_says_and_names_the_reading() -> None:
    """Without it a DOCUMENT item froze its title alone: the file's words were never quotable."""
    text = DocumentText(text="Tržby vzrostly o 12 %.\nPodíl na trhu 31 %.", reading_sha256=READING)
    [source] = freeze_knowledge([_doc(1)], documents=_by_id({_doc(1).item_id: text})).items
    assert "Tržby vzrostly o 12 %." in source.text and "Podíl na trhu 31 %." in source.text
    assert source.reading_sha256 == READING
    assert (source.internal, source.data_class) == (False, DataClass.CLASS_A_CLIENT_CONFIDENTIAL)


def test_a_source_marked_internal_freezes_marked_and_never_lowers_the_items_class() -> None:
    """The mark is frozen with the run (G64): RD0b reads it. The source the run holds is the
    item's own words (approved knowledge, Class A) with the file's, so it stays A: a mark on the
    file never lowers the class of the client's words beside it."""
    text = DocumentText(text="Interní metodika.", reading_sha256=READING, internal=True)
    [source] = freeze_knowledge([_doc(2)], documents=_by_id({_doc(2).item_id: text})).items
    assert source.internal is True
    assert source.data_class is DataClass.CLASS_A_CLIENT_CONFIDENTIAL


def test_a_document_that_adds_no_word_names_no_reading() -> None:
    """An item whose own text already fills the item bound holds none of the file's words, so
    it names no reading and no mark: it says only what it holds."""
    full = _item(
        6,
        KnowledgeKind.DOCUMENT,
        "Zpráva",
        content={"source_id": "SRC-1", "text": "x" * ITEM_TEXT_CHARS},
    )
    text = DocumentText(text="Slova souboru.", reading_sha256=READING, internal=True)
    [source] = freeze_knowledge([full], documents=_by_id({full.item_id: text})).items
    assert "Slova souboru" not in source.text
    assert (source.reading_sha256, source.internal) == (None, False)


def test_a_long_document_is_cut_at_the_item_bound_and_says_so() -> None:
    text = DocumentText(text="slovo " * ITEM_TEXT_CHARS, reading_sha256=READING)
    [source] = freeze_knowledge([_doc(3)], documents=_by_id({_doc(3).item_id: text})).items
    assert len(source.text) == ITEM_TEXT_CHARS and source.truncated


def test_without_document_texts_the_frozen_knowledge_is_byte_for_byte_todays() -> None:
    """The switch off: nothing new in the request, so no run's identity moves."""
    frozen = freeze_knowledge([_doc(4), _item(5, KnowledgeKind.FACT, "Fakt")])
    dumped = frozen.model_dump(mode="json")
    assert all("internal" not in i and "reading_sha256" not in i for i in dumped["items"])
    unmarked = DocumentText(text="", reading_sha256=READING)
    assert (
        "internal"
        not in freeze_knowledge(
            [_doc(4)], documents=_by_id({_doc(4).item_id: unmarked})
        ).model_dump(mode="json")["items"][0]
    )


def test_document_text_never_pushes_out_knowledge_held_without_it() -> None:
    """Reading documents only ever adds: every item a run without them holds is held, a
    document's text where the budget lasts, the rest as before and said to stop short."""
    items = [
        *(_doc(n) for n in range(1, 30)),
        _item(99, KnowledgeKind.FACT, "Podíl na trhu", summary="b" * 9_000),
    ]
    documents = {
        d.item_id: DocumentText(text="a" * 9_980, reading_sha256=READING)
        for d in items
        if d.kind is KnowledgeKind.DOCUMENT
    }
    before = freeze_knowledge(items)
    after = freeze_knowledge(items, documents=_by_id(documents))
    assert {k.item_id for k in after.items} == {k.item_id for k in before.items}
    assert after.omitted_ids == before.omitted_ids == ()
    with_text = [k for k in after.items if k.reading_sha256 is not None]
    as_before = [k for k in after.items if k.kind == "DOCUMENT" and k.reading_sha256 is None]
    assert with_text and as_before
    assert all(k.truncated for k in as_before)
    assert sum(len(k.text.encode()) for k in after.items) <= KNOWLEDGE_BYTES


def test_a_file_that_cannot_fit_or_adds_nothing_is_never_read() -> None:
    """The reader's size answers first: what the budget cannot hold is not fetched at all."""
    items = [_doc(n) for n in range(1, 30)]
    reader = _by_id(
        {d.item_id: DocumentText(text="a" * 9_980, reading_sha256=READING) for d in items}
    )
    frozen = freeze_knowledge(items, documents=reader)
    unread = {k.item_id for k in frozen.items if k.reading_sha256 is None}
    assert unread and not unread & set(reader.read_ids)
    assert len(reader.read_ids) == len(items) - len(unread)

    full = _item(7, KnowledgeKind.DOCUMENT, "Zpráva", content={"text": "x" * ITEM_TEXT_CHARS})
    filled = _by_id({full.item_id: DocumentText(text="Slova.", reading_sha256=READING)})
    freeze_knowledge([full], documents=filled)
    assert filled.read_ids == []
