"""Client Knowledge for Deep Research: frozen at enqueue, retrieved by code, classed by kind.

The internal channel's access contract (ADR 0017 decision 3). What a run may read
is decided once, when it is enqueued, by the application layer calling
``ClientKnowledgeRepository.for_study`` under an issued ``StudyContext``: the
study's own client's approved items, never another's (ADR 0015). This module turns
those items into the bounded :class:`FrozenKnowledge` the run holds, and nothing
reads knowledge after that: a later approval does not change a queued job.

Retrieval over the frozen items is lexical and deterministic (:func:`retrieve`):
no model chooses which item is read, and no knowledge text ever reaches the web
channel -- the query proposer is never shown it (plan decision I-3).

Classes follow the kinds (the plan's table): raw material (documents, sources,
datasets, artifacts) is Class A; approved facts, findings, terms, entities,
dimensions and audiences, which are derived summaries, are Class B. An item whose
lineage nobody recorded -- a dataset, an artifact, a finding -- carries a named
unresolved lineage, and the licence gate refuses it at the next model call, as it
does for the design jobs.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from ..knowledge import KnowledgeItem, KnowledgeKind
from ..residency import DataClass
from .classification import fold
from .contracts import ClientTerm, FrozenKnowledge, KnowledgeSource
from .grounding import normalise_text

__all__ = [
    "ITEM_TEXT_CHARS",
    "KNOWLEDGE_BYTES",
    "KNOWLEDGE_CLASS",
    "RETRIEVAL_LIMIT",
    "UNRESOLVED_LINEAGE",
    "client_terms",
    "freeze_knowledge",
    "retrieve",
]

#: The repository's own window (``client_knowledge_repository._MAX_RESULTS``).
RETRIEVAL_LIMIT: Final = 200
#: Text a run holds, across all items; items beyond it are omitted by id, visibly.
KNOWLEDGE_BYTES: Final = 128_000
#: Text held per item; a longer item is truncated and says so.
ITEM_TEXT_CHARS: Final = 16_000

#: The lineage a knowledge item carries when nobody recorded which datasets it came from.
UNRESOLVED_LINEAGE: Final = "unclassified-client-knowledge"

KNOWLEDGE_CLASS: Final[dict[KnowledgeKind, DataClass]] = {
    KnowledgeKind.SOURCE: DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
    KnowledgeKind.DOCUMENT: DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
    KnowledgeKind.DATASET: DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
    KnowledgeKind.ARTIFACT: DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
    KnowledgeKind.FACT: DataClass.CLASS_B_DERIVED_CLIENT,
    KnowledgeKind.FINDING: DataClass.CLASS_B_DERIVED_CLIENT,
    KnowledgeKind.TERM: DataClass.CLASS_B_DERIVED_CLIENT,
    KnowledgeKind.ENTITY: DataClass.CLASS_B_DERIVED_CLIENT,
    KnowledgeKind.DIMENSION: DataClass.CLASS_B_DERIVED_CLIENT,
    KnowledgeKind.AUDIENCE: DataClass.CLASS_B_DERIVED_CLIENT,
}

_UNRESOLVED_KINDS: Final = frozenset(
    {KnowledgeKind.DATASET, KnowledgeKind.ARTIFACT, KnowledgeKind.FINDING}
)
_TERM_KINDS: Final = frozenset({KnowledgeKind.ENTITY, KnowledgeKind.TERM})


def _source(item: KnowledgeItem) -> KnowledgeSource:
    body = item.content.get("text")
    parts = [item.title, item.summary, body if isinstance(body, str) else ""]
    text = normalise_text("\n".join(p for p in parts if p))
    return KnowledgeSource(
        ref=f"{item.item_id}@{item.revision}",
        item_id=item.item_id,
        revision=item.revision,
        kind=item.kind.value,
        title=item.title,
        text=text[:ITEM_TEXT_CHARS],
        data_class=KNOWLEDGE_CLASS[item.kind],
        lineage=(UNRESOLVED_LINEAGE,) if item.kind in _UNRESOLVED_KINDS else (),
        truncated=len(text) > ITEM_TEXT_CHARS,
        public=item.content.get("public") is True,
    )


def freeze_knowledge(items: Sequence[KnowledgeItem]) -> FrozenKnowledge:
    """The bounded knowledge a run holds: by item id, until the byte budget is spent.

    Never silently cut: every item left out is named in ``omitted_ids``, and an item
    kept short says ``truncated``. The retrieval limit is the repository's.
    """
    kept: list[KnowledgeSource] = []
    omitted: list[str] = []
    used = 0
    for item in sorted(items, key=lambda k: k.item_id)[:RETRIEVAL_LIMIT]:
        source = _source(item)
        size = len(source.text.encode("utf-8"))
        if used + size > KNOWLEDGE_BYTES:
            omitted.append(item.item_id)
            continue
        kept.append(source)
        used += size
    omitted += [k.item_id for k in sorted(items, key=lambda k: k.item_id)[RETRIEVAL_LIMIT:]]
    return FrozenKnowledge(
        items=tuple(kept), omitted_ids=tuple(omitted), retrieval_limit=RETRIEVAL_LIMIT
    )


def retrieve(
    knowledge: FrozenKnowledge, texts: Sequence[str], *, limit: int
) -> tuple[KnowledgeSource, ...]:
    """The items sharing the most words with ``texts``: title words count double.

    Words of four letters or more, folded (case, diacritics). An item sharing none is
    never returned, so a track whose subject no approved knowledge mentions reads
    nothing and costs nothing. Ties go to the lower ref, so the result is stable.
    """
    wanted = {w for t in texts for w in fold(t).split() if len(w) >= 4}
    if not wanted or limit <= 0:
        return ()
    scored: list[tuple[int, str, KnowledgeSource]] = []
    for item in knowledge.items:
        title = {w for w in fold(item.title).split() if len(w) >= 4}
        body = {w for w in fold(item.text).split() if len(w) >= 4}
        score = 2 * len(wanted & title) + len(wanted & body)
        if score > 0:
            scored.append((-score, item.ref, item))
    scored.sort(key=lambda s: (s[0], s[1]))
    return tuple(s[2] for s in scored[:limit])


def client_terms(
    *, identity: Sequence[tuple[str, str]], knowledge: FrozenKnowledge
) -> tuple[ClientTerm, ...]:
    """The terms that make material client-identifying, with where each came from.

    ``identity`` is the client's and study's own names and slugs, as
    ``(source, term)``. Every approved ENTITY and TERM item is a term too, unless
    the person who approved it marked it public: the list only grows by default.
    """
    terms: list[ClientTerm] = []
    seen: set[str] = set()

    def add(term: str, source: str) -> None:
        folded = fold(term)
        if len(folded) >= 2 and folded not in seen:
            seen.add(folded)
            terms.append(ClientTerm(term=term.strip()[:300], source=source[:300]))

    for source, term in identity:
        add(term, source)
    for item in knowledge.items:
        if KnowledgeKind(item.kind) in _TERM_KINDS and not item.public:
            add(item.title, f"knowledge:{item.ref}")
    return tuple(terms)
