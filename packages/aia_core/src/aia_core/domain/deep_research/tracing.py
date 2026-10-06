"""Primary tracing: whether a finding comes from its number's publisher, by code.

Plan ``deep-research-web-search.md`` § 8.3, chunk 12. Every finding is **primary**
(captured from the publisher of its number), **secondary** (someone else repeating
it), or **undetermined** -- code could not tell, and says so rather than guessing.

What code reads, for one finding, in the quote's context window in its source
(:func:`~.measures.context_window`):

* **named** publishers -- a name variant the reputation register declares, matched
  whole-word on :func:`~.reputation.normalise_name`'s form. The register's rule
  holds: exact variants only, so an inflected name the register does not list
  ("Českého statistického úřadu") is not read; an abbreviation ("ČSÚ") is;
* **linked** publishers -- a link the page carries whose anchor text stands in the
  window and whose host belongs to a registered publisher.

Then, first that holds:

* a named or linked publisher other than the page's own -> ``secondary``; it raises a
  :class:`PrimaryLead` (that publisher, its hosts and data interfaces, the link when
  the page links it: ladder rung 1) unless another finding of the run, captured from
  that publisher, states the same figure (:func:`~.triangulation.same_figure` for
  every measure) -- then the finding is **traced** to it (``traced_to``), and no
  lead is raised;
* the page's publisher is in the register -> ``primary``;
* otherwise ``undetermined``. A Client Knowledge item is ``undetermined`` too: a
  person approved it, and who published its numbers is not something code can read.

A model only proposes: the investigator's leads and the verifier's searches name a
publisher in words, and code resolves it through the register or not at all.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Final
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from .contracts import EvidenceItem, SnapshotLink, digest
from .measures import context_window, render_measure
from .reputation import Publisher, ReputationRegister, normalise_name
from .triangulation import (
    ConflictTolerance,
    PublisherIdentity,
    publisher_identity,
    register_key,
    same_figure,
)

__all__ = [
    "TRACING_VERSION",
    "PrimaryLead",
    "PrimaryStatus",
    "TraceRecord",
    "TraceSource",
    "cited_publishers",
    "trace_findings",
]

#: The tracing rule's version.
TRACING_VERSION: Final = "aia-dr-tracing-1"

#: An anchor text shorter than this is not read as standing in the window.
_MIN_ANCHOR: Final = 4


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PrimaryStatus(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    UNDETERMINED = "undetermined"


class PrimaryLead(_Closed):
    """A secondary finding's lead to the publisher of its number (a ladder's input)."""

    lead_id: str
    evidence_id: str
    publisher: str
    hosts: tuple[str, ...]
    data_interfaces: tuple[str, ...]
    #: The page's own link to that publisher, when it carries one (ladder rung 1).
    link: str | None
    #: What is needed, in Czech: the figure and its publisher.
    need: str = Field(max_length=500)


class TraceRecord(_Closed):
    """What code established about one finding's source."""

    evidence_id: str
    publisher: str
    publisher_name: str
    status: PrimaryStatus
    #: The publishers the quote's context names or links, other than the page's own.
    cited: tuple[str, ...]
    #: For a secondary finding: the finding of its publisher that states the same figure.
    traced_to: str | None
    lead_id: str | None
    detail: str = Field(max_length=1000)


@dataclass(frozen=True, slots=True)
class TraceSource:
    """A captured source as tracing reads it: its normalised text and its links."""

    ref: str
    url: str | None
    text: str
    links: tuple[SnapshotLink, ...] = ()


def cited_publishers(context: str, register: ReputationRegister) -> tuple[Publisher, ...]:
    """The register's publishers a text names, whole-word, in order of first mention."""
    folded = f" {normalise_name(context)} "
    first: dict[str, tuple[int, Publisher]] = {}
    for publisher in register.publishers:
        for name in publisher.all_names:
            key = normalise_name(name)
            at = folded.find(f" {key} ") if key else -1
            if at >= 0 and (
                publisher.canonical_name not in first or at < first[publisher.canonical_name][0]
            ):
                first[publisher.canonical_name] = (at, publisher)
    return tuple(p for _, p in sorted(first.values(), key=lambda x: (x[0], x[1].canonical_name)))


def _linked(
    source: TraceSource, context: str, register: ReputationRegister
) -> list[tuple[Publisher, str]]:
    folded = f" {normalise_name(context)} "
    found = []
    for link in source.links:
        anchor = normalise_name(link.text)
        if len(anchor) < _MIN_ANCHOR or f" {anchor} " not in folded:
            continue
        publisher = register.publisher_for_host(urlsplit(link.url).hostname or "")
        if publisher is not None:
            found.append((publisher, link.url))
    return found


def _link_to(source: TraceSource, publisher: Publisher, register: ReputationRegister) -> str | None:
    for link in source.links:
        found = register.publisher_for_host(urlsplit(link.url).hostname or "")
        if found is not None and found.canonical_name == publisher.canonical_name:
            return link.url
    return None


def _need(item: EvidenceItem, publisher: Publisher) -> str:
    figures = [p for m in item.measures if (p := render_measure(m)) is not None]
    what = "; ".join(figures) if figures else item.claim[:200]
    return f"Primární zdroj údaje {what} u vydavatele {publisher.canonical_name}."[:500]


def trace_findings(
    items: Sequence[EvidenceItem],
    sources: Mapping[str, TraceSource],
    *,
    register: ReputationRegister | None,
    tolerance: ConflictTolerance | None = None,
) -> tuple[tuple[TraceRecord, ...], tuple[PrimaryLead, ...]]:
    """Every finding's trace, in ``items`` order, and the leads the secondary ones raise.

    Without a register nothing is named, linked or registered: every web finding is
    ``undetermined`` and no lead is raised.
    """
    tolerance = tolerance or ConflictTolerance()
    identities: dict[str, PublisherIdentity] = {
        item.evidence_id: publisher_identity(
            url=item.source_url, source_ref=item.source_ref, register=register
        )
        for item in items
    }
    records: list[TraceRecord] = []
    leads: list[PrimaryLead] = []
    for item in items:
        page = identities[item.evidence_id]
        source = sources.get(item.source_ref)
        if item.source_url is None or source is None or register is None:
            records.append(
                TraceRecord(
                    evidence_id=item.evidence_id,
                    publisher=page.key,
                    publisher_name=page.name,
                    status=PrimaryStatus.UNDETERMINED,
                    cited=(),
                    traced_to=None,
                    lead_id=None,
                    detail=(
                        "a Client Knowledge item: its numbers' publisher is not read"
                        if item.source_url is None
                        else "no register: no publisher can be named or resolved"
                        if register is None
                        else "the source is not held"
                    ),
                )
            )
            continue
        lo, hi = context_window(source.text, item.quote_span)
        context = source.text[lo:hi]
        own = page.name if page.registered else None
        cited: dict[str, Publisher] = {
            p.canonical_name: p
            for p in cited_publishers(context, register)
            if p.canonical_name != own
        }
        for publisher, _url in _linked(source, context, register):
            if publisher.canonical_name != own:
                cited.setdefault(publisher.canonical_name, publisher)
        if cited:
            publisher = next(iter(cited.values()))
            traced = _traced_to(item, items, identities, register_key(publisher), tolerance)
            lead = None
            if traced is None:
                lead = PrimaryLead(
                    lead_id="PL-" + digest([item.evidence_id, publisher.canonical_name])[:12],
                    evidence_id=item.evidence_id,
                    publisher=publisher.canonical_name,
                    hosts=publisher.hosts,
                    data_interfaces=publisher.data_interfaces,
                    link=_link_to(source, publisher, register),
                    need=_need(item, publisher),
                )
                leads.append(lead)
            records.append(
                TraceRecord(
                    evidence_id=item.evidence_id,
                    publisher=page.key,
                    publisher_name=page.name,
                    status=PrimaryStatus.SECONDARY,
                    cited=tuple(cited),
                    traced_to=traced,
                    lead_id=lead.lead_id if lead is not None else None,
                    detail=(
                        f"the quote's context cites {publisher.canonical_name}; "
                        + (
                            f"traced to {traced}"
                            if traced is not None
                            else "its figure is not captured from it yet"
                        )
                    ),
                )
            )
        elif page.registered:
            records.append(
                TraceRecord(
                    evidence_id=item.evidence_id,
                    publisher=page.key,
                    publisher_name=page.name,
                    status=PrimaryStatus.PRIMARY,
                    cited=(),
                    traced_to=None,
                    lead_id=None,
                    detail=f"captured from {page.name}, which the quote's context cites no one for",
                )
            )
        else:
            records.append(
                TraceRecord(
                    evidence_id=item.evidence_id,
                    publisher=page.key,
                    publisher_name=page.name,
                    status=PrimaryStatus.UNDETERMINED,
                    cited=(),
                    traced_to=None,
                    lead_id=None,
                    detail=f"{page.name} is not in the register and the context cites no publisher",
                )
            )
    return tuple(records), tuple(leads)


def _traced_to(
    item: EvidenceItem,
    items: Sequence[EvidenceItem],
    identities: Mapping[str, PublisherIdentity],
    publisher_key: str,
    tolerance: ConflictTolerance,
) -> str | None:
    """The first finding (by id) captured from ``publisher_key`` stating every figure."""
    if not item.measures:
        return None
    for other in sorted(items, key=lambda i: i.evidence_id):
        if other.evidence_id == item.evidence_id or identities[other.evidence_id].key != (
            publisher_key
        ):
            continue
        if all(any(same_figure(m, n, tolerance) for n in other.measures) for m in item.measures):
            return other.evidence_id
    return None
