"""NKOD, the national open-data catalogue: one dataset's record as a table of its distributions.

Registered by nothing yet. The interface, as recorded in
``docs/architecture/deep-research-connectors.md`` (2026-10-05): NKOD's public SPARQL
endpoint is ``https://data.gov.cz/sparql`` (the Digital and Information Agency's own
integration document, ``datagov-cz/nkd``). The request and answer are the W3C
standards: SPARQL 1.1 Protocol (``GET ?query=``) and SPARQL 1.1 Query Results JSON;
the record is DCAT. Whether this endpoint serves the JSON results format is
**unverified**, so anything but that format is a contract failure.

What it sends is one fixed SELECT, written by code, with the dataset's IRI as the
only variable part. The IRI is checked against SPARQL's IRIREF rule (the query id
pattern already excludes every character that could close it) and must be an
``https`` URL. It asks only for W3C DCAT and DCMI terms -- the title, the
publisher, each distribution's format, media type, download and access URLs, and a
``dct:license`` where one is stated. DCAT-AP-CZ's own terms-of-use structure
(``podmínky užití``) is not queried: its shape is not established here.

The table: one row per distribution (keyed ``d1`` … in IRI order, labelled by its
IRI), one column per property; several values of one property are joined in sorted
order. The dataset's title and publisher are notes. The catalogue record's own
licence is not stamped (unverified), so ``licence`` is ``None``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any, Final
from urllib.parse import urlencode

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.contracts import RetrievalMode
from ..domain.deep_research.datasets import DatasetQuery
from ..domain.deep_research.grounding import normalise_text
from ..domain.deep_research.tooling import ToolKind
from ..domain.deep_research.web import FetchRefused, check_url
from .dataset_connectors import DatasetResponse, HostScopedClient, build_result, contract_failure
from .web_retrieval import FetchTransport, Resolver, ToolCallFailed

__all__ = ["NKOD_CONNECTOR_ID", "NKOD_HOST", "NkodConnector", "nkod_query"]

NKOD_CONNECTOR_ID: Final = "nkod-sparql-1"
NKOD_HOST: Final = "data.gov.cz"
NKOD_SPARQL: Final = f"https://{NKOD_HOST}/sparql"
NKOD_PUBLISHER: Final = "Národní katalog otevřených dat (data.gov.cz)"
NKOD_MAX_BYTES: Final = 1_000_000
#: Bindings asked for; an answer that reaches it is refused, never cut short.
NKOD_LIMIT: Final = 400

#: (column key, column label, SPARQL variable), in column order.
_COLUMNS: Final = (
    ("format", "Formát (dct:format)", "format"),
    ("media_type", "Typ média (dcat:mediaType)", "mediaType"),
    ("download_url", "URL ke stažení (dcat:downloadURL)", "downloadURL"),
    ("access_url", "URL přístupu (dcat:accessURL)", "accessURL"),
    ("license", "Licence (dct:license)", "license"),
)


def nkod_query(dataset_iri: str) -> str:
    """The one SELECT this connector sends: a dataset's title, publisher and distributions."""
    return (
        "PREFIX dcat: <http://www.w3.org/ns/dcat#> "
        "PREFIX dct: <http://purl.org/dc/terms/> "
        "SELECT ?title ?publisher ?distribution ?format ?mediaType ?downloadURL ?accessURL "
        "?license WHERE { "
        f"<{dataset_iri}> a dcat:Dataset . "
        f"OPTIONAL {{ <{dataset_iri}> dct:title ?title }} "
        f"OPTIONAL {{ <{dataset_iri}> dct:publisher ?publisher }} "
        f"OPTIONAL {{ <{dataset_iri}> dcat:distribution ?distribution . "
        "OPTIONAL { ?distribution dct:format ?format } "
        "OPTIONAL { ?distribution dcat:mediaType ?mediaType } "
        "OPTIONAL { ?distribution dcat:downloadURL ?downloadURL } "
        "OPTIONAL { ?distribution dcat:accessURL ?accessURL } "
        "OPTIONAL { ?distribution dct:license ?license } } "
        f"}} LIMIT {NKOD_LIMIT}"
    )


def _not_sent(message: str, reason: str) -> ToolCallFailed:
    return ToolCallFailed(message, reason=reason, delivery=Delivery.NOT_SENT)


def _term(binding: Mapping[str, Any], var: str) -> tuple[str, str] | None:
    """(value, language) of one bound variable, or None when it is unbound."""
    term = binding.get(var)
    if term is None:
        return None
    if not isinstance(term, Mapping) or not isinstance(term.get("value"), str):
        raise contract_failure("SPARQL JSON results")
    if term.get("type") not in ("uri", "literal", "typed-literal", "bnode"):
        raise contract_failure("SPARQL JSON results")
    language = term.get("xml:lang", "")
    return normalise_text(term["value"]), language if isinstance(language, str) else ""


class NkodConnector:
    """One NKOD dataset record per query, over the catalogue's SPARQL endpoint."""

    tool_kind: Final = ToolKind.DATASET_QUERY
    connector_id: Final = NKOD_CONNECTOR_ID

    def __init__(
        self,
        *,
        transport: FetchTransport,
        resolver: Resolver,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._client = HostScopedClient(
            host=NKOD_HOST,
            transport=transport,
            resolver=resolver,
            media_types=("application/sparql-results+json", "application/json"),
            max_bytes=NKOD_MAX_BYTES,
        )
        self._clock = clock

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def request_url(self, query: DatasetQuery) -> str:
        """The one URL a query becomes, or a refusal before anything is sent."""
        if query.connector_id != self.connector_id:
            raise _not_sent("the query is for another connector", "connector_mismatch")
        if query.filters or query.period is not None:
            raise _not_sent("a catalogue record takes no filter or period", "filters_unsupported")
        iri = query.dataset_id
        try:
            check_url(iri)
        except FetchRefused as exc:
            raise _not_sent("a dataset IRI is a public https URL", "dataset_id_invalid") from exc
        if not iri.startswith("https://") or any(ord(ch) <= 0x20 for ch in iri):
            raise _not_sent("a dataset IRI is a public https URL", "dataset_id_invalid")
        return f"{NKOD_SPARQL}?{urlencode({'query': nkod_query(iri)})}"

    def query(self, query: DatasetQuery) -> DatasetResponse:
        url = self.request_url(query)
        response = self._client.get(url)
        try:
            doc = json.loads(response.body)
        except (UnicodeDecodeError, ValueError) as exc:
            raise contract_failure("JSON") from exc
        results = doc.get("results") if isinstance(doc, Mapping) else None
        bindings = results.get("bindings") if isinstance(results, Mapping) else None
        if not isinstance(bindings, list) or not all(isinstance(b, Mapping) for b in bindings):
            raise contract_failure("SPARQL JSON results")
        if len(bindings) >= NKOD_LIMIT:
            raise ToolCallFailed(
                f"the record has {NKOD_LIMIT} or more bindings",
                reason="dataset_too_large",
                delivery=Delivery.RESPONDED,
            )
        if not bindings:
            raise ToolCallFailed(
                "the catalogue holds no such dataset",
                reason="dataset_not_found",
                delivery=Delivery.RESPONDED,
            )
        titles: set[tuple[str, str]] = set()
        publishers: set[str] = set()
        by_distribution: dict[str, dict[str, set[str]]] = {}
        for binding in bindings:
            if (named := _term(binding, "title")) is not None:
                titles.add(named)
            if (publisher := _term(binding, "publisher")) is not None:
                publishers.add(publisher[0])
            distribution = _term(binding, "distribution")
            if distribution is None:
                continue
            cells = by_distribution.setdefault(distribution[0], {k: set() for k, _, _ in _COLUMNS})
            for key, _, var in _COLUMNS:
                if (value := _term(binding, var)) is not None:
                    cells[key].add(value[0])
        czech = sorted(t for t, lang in titles if lang.lower().startswith("cs"))
        other = sorted(t for t, _ in titles)
        title = (czech or other or [query.dataset_id])[0][:500]
        notes = [f"Název datové sady: {t}" for t in sorted({t for t, _ in titles})]
        notes += [f"Poskytovatel (dct:publisher): {p}" for p in sorted(publishers)]
        if not by_distribution:
            notes.append("Záznam neuvádí žádnou distribuci (dcat:distribution).")
        rows = [
            {
                "key": f"d{i}",
                "label": iri,
                "values": [
                    "; ".join(sorted(cells[key])) if cells[key] else None for key, _, _ in _COLUMNS
                ],
            }
            for i, (iri, cells) in enumerate(sorted(by_distribution.items()), 1)
        ]
        result = build_result(
            connector_id=self.connector_id,
            dataset_id=query.dataset_id,
            query=query,
            title=title,
            publisher=NKOD_PUBLISHER,
            licence=None,
            source_url=url,
            retrieved_at=self._clock(),
            notes=[n[:2000] for n in notes][:20],
            columns=[{"key": key, "label": label} for key, label, _ in _COLUMNS],
            rows=rows,
        )
        return DatasetResponse(
            result=result,
            raw_sha256=hashlib.sha256(response.body).hexdigest(),
            raw_bytes=len(response.body),
            http_status=response.status,
            provider_request_id=response.provider_request_id,
        )
