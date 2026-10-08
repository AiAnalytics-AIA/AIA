"""Crossref's record of a work: the notices that update it, retractions first (chunk 46).

The interface, recorded in ``docs/architecture/deep-research-connectors.md`` § 7a: the
``Update`` object (``updated`` as a partial date, ``DOI``, ``type``, ``label``) is VERIFIED
from Crossref's ``rest-api-doc``; the rest is **unverified** (no answer could be read
first-hand, 2026-10-08; checked against a live answer at the live acceptance, chunk 27):

- ``GET https://api.crossref.org/works/{doi}`` answers ``{"status": "ok",
  "message-type": "work", "message": {...}}`` (Crossref REST API documentation,
  github.com/CrossRef/rest-api-doc);
- a ``mailto=`` parameter puts the request in the "polite" pool (same documentation);
- since Retraction Watch's data joined the API (Crossref blog, "Retraction Watch
  retractions now in the Crossref API"; Crossref documentation, "Retraction Watch"),
  a work that has been updated lists each update under ``message["updated-by"]``: an
  entry with the update's ``type`` (``retraction``, ``correction``, ...), the notice's
  ``DOI``, its ``source`` (``publisher`` or ``retraction-watch``) and when it was
  ``updated`` (``date-parts``). The notice itself carries ``update-to``, which this
  connector does not read: a work is judged by what updates it, never by what it updates.

What it sends is fixed by code: one GET to ``api.crossref.org`` only, the DOI as the
path, and the operator's contact. No key, no cookie, no redirect.

The table: one row per notice, in the order the record lists them. An update type this
connector does not know is kept as a row with status ``unknown``, never mapped by guess.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from typing import Any, Final
from urllib.parse import quote, urlencode

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.contracts import RetrievalMode
from ..domain.deep_research.datasets import DatasetQuery, DatasetResult
from ..domain.deep_research.tooling import ToolKind
from ..domain.deep_research.works import WorkNotice, WorkStatus, normalise_doi
from .dataset_connectors import DatasetResponse, HostScopedClient, build_result, contract_failure
from .web_retrieval import FetchTransport, Resolver, ToolCallFailed

__all__ = [
    "CROSSREF_CONNECTOR_ID",
    "CROSSREF_HOST",
    "CrossrefConnector",
    "crossref_notices",
]

CROSSREF_CONNECTOR_ID: Final = "crossref-works-1"
CROSSREF_HOST: Final = "api.crossref.org"
CROSSREF_PUBLISHER: Final = "Crossref (with Retraction Watch)"
CROSSREF_MAX_BYTES: Final = 1_000_000
_MAILTO: Final = re.compile(r"^[^@\s,&?#/]{1,64}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
#: A DOI as this connector will put it in a path.
_DOI: Final = re.compile(r"^10\.[0-9]{4,9}/[^\s?#]{1,200}$")

#: Crossref's update types (its schema's list), mapped to a work's standing. A partial
#: retraction leaves the rest of the work standing, with a notice: a concern, not a
#: retraction of every finding.
UPDATE_TYPES: Final[Mapping[str, WorkStatus]] = {
    "retraction": WorkStatus.RETRACTED,
    "withdrawal": WorkStatus.WITHDRAWN,
    "removal": WorkStatus.WITHDRAWN,
    "partial_retraction": WorkStatus.EXPRESSION_OF_CONCERN,
    "expression_of_concern": WorkStatus.EXPRESSION_OF_CONCERN,
    "correction": WorkStatus.CORRECTED,
    "corrigendum": WorkStatus.CORRECTED,
    "erratum": WorkStatus.CORRECTED,
    "addendum": WorkStatus.CORRECTED,
    "clarification": WorkStatus.CORRECTED,
}
_COLUMNS: Final = (
    ("type", "Update type (updated-by.type)"),
    ("status", "AIA's reading of it"),
    ("notice_doi", "Notice DOI (updated-by.DOI)"),
    ("source", "Recorded by (updated-by.source)"),
    ("updated", "Updated (updated-by.updated)"),
)


def _not_sent(message: str, reason: str) -> ToolCallFailed:
    return ToolCallFailed(message, reason=reason, delivery=Delivery.NOT_SENT)


class CrossrefConnector:
    """One work's update notices per query (``doi:<DOI>``), from Crossref."""

    connector_id: Final = CROSSREF_CONNECTOR_ID
    tool_kind: Final = ToolKind.DATASET_QUERY

    def __init__(
        self,
        *,
        transport: FetchTransport,
        resolver: Resolver,
        mailto: str | None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if mailto is not None and _MAILTO.fullmatch(mailto) is None:
            raise ValueError("the polite pool's contact is one plain email address, or None")
        self._client = HostScopedClient(
            host=CROSSREF_HOST,
            transport=transport,
            resolver=resolver,
            media_types=("application/json",),
            max_bytes=CROSSREF_MAX_BYTES,
        )
        self._mailto = mailto
        self._clock = clock

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def request_url(self, query: DatasetQuery) -> str:
        """The URL a query becomes, without the operator's contact; or a refusal."""
        if query.connector_id != self.connector_id:
            raise _not_sent("the query is for another connector", "connector_mismatch")
        if query.filters or query.period is not None:
            raise _not_sent("a DOI lookup takes no filter", "filters_unsupported")
        doi = query.dataset_id.removeprefix("doi:")
        if not query.dataset_id.startswith("doi:") or _DOI.fullmatch(doi) is None:
            raise _not_sent("a query is doi:10.<registrant>/<suffix>", "dataset_id_invalid")
        return f"https://{CROSSREF_HOST}/works/{quote(doi, safe='/')}"

    def query(self, query: DatasetQuery) -> DatasetResponse:
        url = self.request_url(query)
        sent = url if self._mailto is None else f"{url}?{urlencode({'mailto': self._mailto})}"
        response = self._client.get(sent)
        try:
            doc = json.loads(response.body)
        except (UnicodeDecodeError, ValueError) as exc:
            raise contract_failure("JSON") from exc
        message = doc.get("message") if isinstance(doc, Mapping) else None
        if not isinstance(message, Mapping):
            raise contract_failure("a Crossref work")
        doi = query.dataset_id.removeprefix("doi:")
        if normalise_doi(str(message.get("DOI", ""))) != normalise_doi(doi):
            raise contract_failure("the work the DOI names")
        updates = message.get("updated-by", [])
        if not isinstance(updates, list) or not all(isinstance(u, Mapping) for u in updates):
            raise contract_failure("updated-by as a list of updates")
        rows = [
            {"key": f"u{i}", "label": f"{i}. {_text(u.get('type')) or 'update'}", "values": _row(u)}
            for i, u in enumerate(updates, 1)
        ]
        titles = message.get("title")
        title = _text(titles[0]) if isinstance(titles, list) and titles else ""
        result = build_result(
            connector_id=self.connector_id,
            dataset_id=query.dataset_id,
            query=query,
            title=f"Crossref record of {doi}: {title}"[:500],
            publisher=CROSSREF_PUBLISHER,
            licence=None,
            source_url=url,
            retrieved_at=self._clock(),
            notes=[] if rows else ["Crossref lists no update for this work."],
            columns=[{"key": k, "label": label} for k, label in _COLUMNS],
            rows=rows,
        )
        return DatasetResponse(
            result=result,
            raw_sha256=hashlib.sha256(response.body).hexdigest(),
            raw_bytes=len(response.body),
            http_status=response.status,
            provider_request_id=response.provider_request_id,
            credits=1,
        )


def _text(value: Any) -> str | None:
    if value is None or isinstance(value, (bool, dict, list)):
        return None
    return str(value).strip()[:300] or None


def _date(update: Mapping[str, Any]) -> str | None:
    updated = update.get("updated")
    parts = updated.get("date-parts") if isinstance(updated, Mapping) else None
    if isinstance(parts, list) and parts and isinstance(parts[0], list) and len(parts[0]) == 3:
        try:
            return date(*(int(p) for p in parts[0])).isoformat()
        except (TypeError, ValueError):
            return None
    return None


def _row(update: Mapping[str, Any]) -> list[str | None]:
    kind = (_text(update.get("type")) or "").lower()
    status = UPDATE_TYPES.get(kind, WorkStatus.UNKNOWN)
    return [
        kind or None,
        status.value,
        normalise_doi(_text(update.get("DOI")) or ""),
        _text(update.get("source")),
        _date(update),
    ]


def crossref_notices(result: DatasetResult) -> tuple[WorkNotice, ...]:
    """The notices a Crossref answer lists, as a work's standing reads them."""
    if result.connector_id != CROSSREF_CONNECTOR_ID:
        raise ValueError("not a Crossref answer")
    at = {c.key: i for i, c in enumerate(result.columns)}
    notices = []
    for row in result.rows:
        values = row.values
        issued = values[at["updated"]]
        notices.append(
            WorkNotice(
                status=WorkStatus(values[at["status"]] or WorkStatus.UNKNOWN.value),
                notice_doi=values[at["notice_doi"]],
                source=(values[at["source"]] or "unstated")[:60],
                issued=date.fromisoformat(issued) if issued else None,
            )
        )
    return tuple(notices)
