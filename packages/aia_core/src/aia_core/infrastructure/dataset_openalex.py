"""OpenAlex: a work's open-access locations by DOI, or a short list of works. Unregistered.

The interface, as recorded in ``docs/architecture/deep-research-connectors.md``
(2026-10-06, read first-hand from OpenAlex's own documentation source,
``ourresearch/openalex-docs``): ``GET https://api.openalex.org/works/doi:<DOI>``
answers one ``Work``; ``GET /works?search=…`` answers ``{"meta": …, "results": […]}``,
25 a page by default; ``select=`` keeps only root-level fields; ``filter=
publication_year:<year>`` narrows a list; boolean operators in a search are the
UPPERCASE words ``AND``, ``OR``, ``NOT``; a singleton costs 1 credit and a list 10,
against 100,000 a day without a key; ``mailto=`` puts a caller in the "polite pool".
A ``Work`` carries ``open_access`` (``is_oa``, ``oa_status``, ``oa_url``),
``best_oa_location`` and ``locations``, each a ``Location`` with ``is_oa``,
``landing_page_url``, ``pdf_url``, ``license``, ``version`` and ``source``.

This is search-like metadata, not a statistical cube, and it is modelled as what it
is -- a table of records, like the NKOD connector's distributions:

* ``doi:<DOI>`` -- the **ladder's lookup** (plan § 7 rung 7: a paywalled paper's
  lawful open-access copy): one row per location the work lives at, with whether
  it is open access, its version, its licence, its landing page and PDF, its source
  and whether OpenAlex rates it the best open copy. :func:`open_access_copies`
  reads the lawful copies off that table, best first.
* ``works`` with a ``search`` filter (words) and optionally ``publication_year``
  -- one row per work, as OpenAlex ranked them: its OpenAlex id, DOI, title, year
  and open-access status. Search words are letters, digits and hyphens, sent in
  lower case so that no word is a boolean operator; a free-text phrase is the
  search tool's business, not a dataset query's.

Only the fields named above are asked for (``select``): no author, no affiliation,
no abstract -- nothing person-level is received or stored (plan § 4).

``mailto`` is the operator's contact for the polite pool: a configured value, or
nothing; never guessed and never in code. It is sent, and kept out of the
``source_url`` a snapshot stores. No API key exists here.

The licence stated for OpenAlex's own data is CC0 (its documentation's own words:
"Our complete dataset is free under the CC0 license"); a location's ``license`` is
the *work's* licence at that location, a different thing, and is a cell.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final
from urllib.parse import quote, urlencode

from ..domain.ai_contracts import Delivery
from ..domain.deep_research.contracts import RetrievalMode
from ..domain.deep_research.datasets import DatasetQuery, DatasetResult
from ..domain.deep_research.grounding import normalise_text
from ..domain.deep_research.tooling import ToolKind
from .dataset_connectors import DatasetResponse, HostScopedClient, build_result, contract_failure
from .web_retrieval import FetchTransport, Resolver, ToolCallFailed

__all__ = [
    "OPENALEX_CONNECTOR_ID",
    "OPENALEX_HOST",
    "OpenAccessCopy",
    "OpenAlexConnector",
    "open_access_copies",
]

OPENALEX_CONNECTOR_ID: Final = "openalex-works-1"
OPENALEX_HOST: Final = "api.openalex.org"
OPENALEX_API: Final = f"https://{OPENALEX_HOST}"
OPENALEX_PUBLISHER: Final = "OpenAlex (OurResearch)"
#: What OpenAlex's documentation states for its data (connectors doc, VERIFIED).
OPENALEX_LICENCE: Final = "CC0"
OPENALEX_MAX_BYTES: Final = 2_000_000
#: The provider's credits per request (connectors doc, VERIFIED): a singleton, a list.
SINGLETON_CREDITS: Final = 1
LIST_CREDITS: Final = 10
#: Works one search asks for: the provider's default page.
SEARCH_PAGE: Final = 25
MAX_SEARCH_WORDS: Final = 10

_WORK_FIELDS: Final = (
    "id",
    "doi",
    "title",
    "publication_year",
    "type",
    "open_access",
    "best_oa_location",
    "locations",
)
_LIST_FIELDS: Final = ("id", "doi", "title", "publication_year", "open_access")
#: A DOI as this connector will put it in a path: ``10.<registrant>/<suffix>``; OpenAlex
#: refuses an id with ``,`` or ``&`` (connectors doc), so such a DOI is never sent.
_DOI: Final = re.compile(r"^10\.[0-9]{4,9}/[^\s,&]{1,200}$")
_WORD: Final = re.compile(r"^[A-Za-z0-9-]{1,40}$")
_YEAR: Final = re.compile(r"^[0-9]{4}$")
_MAILTO: Final = re.compile(r"^[^@\s,&?#/]{1,64}@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")

#: (column key, label) of a location row, in column order.
_LOCATION_COLUMNS: Final = (
    ("is_oa", "Open access (is_oa)"),
    ("version", "Version (version)"),
    ("license", "Licence at this location (license)"),
    ("landing_page_url", "Landing page (landing_page_url)"),
    ("pdf_url", "PDF (pdf_url)"),
    ("source", "Source (source.display_name)"),
    ("source_type", "Source type (source.type)"),
    ("best_oa", "Best open-access location (best_oa_location)"),
)
_WORK_COLUMNS: Final = (
    ("openalex_id", "OpenAlex ID (id)"),
    ("doi", "DOI (doi)"),
    ("title", "Title (title)"),
    ("publication_year", "Publication year (publication_year)"),
    ("is_oa", "Open access (open_access.is_oa)"),
    ("oa_status", "Open-access status (open_access.oa_status)"),
    ("oa_url", "Open-access URL (open_access.oa_url)"),
)


def _not_sent(message: str, reason: str) -> ToolCallFailed:
    return ToolCallFailed(message, reason=reason, delivery=Delivery.NOT_SENT)


def _text(value: Any) -> str | None:
    """A JSON scalar as published: a string normalised to one line, a number's text, a
    boolean as ``true``/``false``, null as absent. Anything else is not this contract."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return normalise_text(value) or None
    if isinstance(value, int | float):
        return json.dumps(value)
    raise contract_failure("an OpenAlex work with scalar fields")


def _object(value: Any, what: str) -> Mapping[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise contract_failure(f"an OpenAlex work whose {what} is an object")
    return value


def _location_values(location: Mapping[str, Any], *, best: bool) -> list[str | None]:
    source = _object(location.get("source"), "location source") or {}
    return [
        _text(location.get("is_oa")),
        _text(location.get("version")),
        _text(location.get("license")),
        _text(location.get("landing_page_url")),
        _text(location.get("pdf_url")),
        _text(source.get("display_name")),
        _text(source.get("type")),
        "yes" if best else "no",
    ]


class OpenAlexConnector:
    """A work by DOI (its locations), or a short search of works, from OpenAlex."""

    tool_kind: Final = ToolKind.DATASET_QUERY
    connector_id: Final = OPENALEX_CONNECTOR_ID

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
            host=OPENALEX_HOST,
            transport=transport,
            resolver=resolver,
            media_types=("application/json",),
            max_bytes=OPENALEX_MAX_BYTES,
        )
        self._mailto = mailto
        self._clock = clock

    @property
    def retrieval_mode(self) -> RetrievalMode:
        return RetrievalMode.LIVE

    def request_url(self, query: DatasetQuery) -> str:
        """The URL a query becomes, without the operator's contact; or a refusal before sending."""
        if query.connector_id != self.connector_id:
            raise _not_sent("the query is for another connector", "connector_mismatch")
        if query.period is not None:
            raise _not_sent("a year is the publication_year filter", "filters_unsupported")
        if query.dataset_id.startswith("doi:"):
            doi = query.dataset_id.removeprefix("doi:")
            if query.filters:
                raise _not_sent("a DOI lookup takes no filter", "filters_unsupported")
            if _DOI.fullmatch(doi) is None:
                raise _not_sent("a DOI is 10.<registrant>/<suffix>", "dataset_id_invalid")
            select = urlencode({"select": ",".join(_WORK_FIELDS)})
            return f"{OPENALEX_API}/works/doi:{quote(doi, safe='/')}?{select}"
        if query.dataset_id != "works":
            raise _not_sent("a query is doi:<DOI> or works", "dataset_id_invalid")
        filters = {f.dimension: f.values for f in query.filters}
        words = filters.pop("search", ())
        years = filters.pop("publication_year", ())
        if filters:
            raise _not_sent("a search takes search and publication_year", "filters_unsupported")
        if not words or len(words) > MAX_SEARCH_WORDS:
            raise _not_sent("a search names 1 to 10 words", "filter_invalid")
        if any(_WORD.fullmatch(w) is None for w in words):
            raise _not_sent("a search word is letters, digits and hyphens", "filter_invalid")
        if len(years) > 1 or any(_YEAR.fullmatch(y) is None for y in years):
            raise _not_sent("a search takes at most one four-digit year", "filter_invalid")
        params: list[tuple[str, str]] = [("search", " ".join(w.lower() for w in words))]
        if years:
            params.append(("filter", f"publication_year:{years[0]}"))
        params += [("select", ",".join(_LIST_FIELDS)), ("per-page", str(SEARCH_PAGE))]
        return f"{OPENALEX_API}/works?{urlencode(params)}"

    def _sent(self, url: str) -> str:
        if self._mailto is None:
            return url
        return f"{url}&{urlencode({'mailto': self._mailto})}"

    def query(self, query: DatasetQuery) -> DatasetResponse:
        url = self.request_url(query)
        response = self._client.get(self._sent(url))
        try:
            # Numbers as their text, so nothing is re-rounded.
            doc = json.loads(response.body, parse_float=lambda s: s)
        except (UnicodeDecodeError, ValueError) as exc:
            raise contract_failure("JSON") from exc
        if not isinstance(doc, Mapping):
            raise contract_failure("an OpenAlex object")
        if query.dataset_id.startswith("doi:"):
            fields = _work_table(doc, doi=query.dataset_id.removeprefix("doi:"))
            charged = SINGLETON_CREDITS
        else:
            fields = _search_table(doc)
            charged = LIST_CREDITS
        result = build_result(
            **fields,
            connector_id=self.connector_id,
            dataset_id=query.dataset_id,
            query=query,
            publisher=OPENALEX_PUBLISHER,
            licence=OPENALEX_LICENCE,
            source_url=url,
            retrieved_at=self._clock(),
        )
        return DatasetResponse(
            result=result,
            raw_sha256=hashlib.sha256(response.body).hexdigest(),
            raw_bytes=len(response.body),
            http_status=response.status,
            provider_request_id=response.provider_request_id,
            credits=charged,
        )


def _work_table(doc: Mapping[str, Any], *, doi: str) -> dict[str, Any]:
    """A ``Work`` as a table of its locations; refused if it is another work or another shape."""
    answered = doc.get("doi")
    if not isinstance(answered, str) or answered.casefold() != f"https://doi.org/{doi}".casefold():
        raise contract_failure("the work the DOI names")
    locations = doc.get("locations")
    if not isinstance(locations, list) or not all(isinstance(x, Mapping) for x in locations):
        raise contract_failure("an OpenAlex work with its locations")
    best = _object(doc.get("best_oa_location"), "best_oa_location")
    open_access = _object(doc.get("open_access"), "open_access") or {}
    title = _text(doc.get("title"))
    notes = [
        f"DOI: {_text(answered)}",
        f"OpenAlex ID: {_text(doc.get('id')) or 'not stated'}",
        f"Title: {(title or 'not stated')[:1900]}",
        f"Publication year: {_text(doc.get('publication_year')) or 'not stated'}",
        f"Type: {_text(doc.get('type')) or 'not stated'}",
        f"Open access (open_access.is_oa): {_text(open_access.get('is_oa')) or 'not stated'}",
        f"Open-access status (open_access.oa_status): "
        f"{_text(open_access.get('oa_status')) or 'not stated'}",
        f"Open-access URL (open_access.oa_url): {_text(open_access.get('oa_url')) or 'none'}",
    ]
    if best is not None and best not in locations:
        notes.append("The best open-access location is not among the work's locations.")
    if not locations:
        notes.append("OpenAlex lists no location for this work.")
    rows = []
    for i, location in enumerate(locations, 1):
        source = _object(location.get("source"), "location source") or {}
        name = _text(source.get("display_name")) or "source not stated"
        rows.append(
            {
                "key": f"loc{i}",
                "label": f"{i}. {name}"[:1000],
                "values": _location_values(location, best=best is not None and location == best),
            }
        )
    return {
        "title": (title or doi)[:500],
        "notes": [n[:2000] for n in notes],
        "columns": [{"key": k, "label": label} for k, label in _LOCATION_COLUMNS],
        "rows": rows,
    }


def _search_table(doc: Mapping[str, Any]) -> dict[str, Any]:
    """A list answer as a table of works, in the provider's order."""
    meta = _object(doc.get("meta"), "meta") or {}
    results = doc.get("results")
    if not isinstance(results, list) or not all(isinstance(w, Mapping) for w in results):
        raise contract_failure("an OpenAlex list with its results")
    if len(results) > SEARCH_PAGE:
        raise contract_failure("an OpenAlex page of the size asked for")
    rows = []
    for i, work in enumerate(results, 1):
        open_access = _object(work.get("open_access"), "open_access") or {}
        openalex_id = _text(work.get("id"))
        rows.append(
            {
                "key": f"w{i}",
                "label": f"{i}. {openalex_id or 'work without an id'}",
                "values": [
                    openalex_id,
                    _text(work.get("doi")),
                    _text(work.get("title")),
                    _text(work.get("publication_year")),
                    _text(open_access.get("is_oa")),
                    _text(open_access.get("oa_status")),
                    _text(open_access.get("oa_url")),
                ],
            }
        )
    count = _text(meta.get("count"))
    return {
        "title": "OpenAlex works search",
        "notes": [
            f"Works matching (meta.count): {count or 'not stated'}",
            "Rows are in the provider's relevance order; only the first page is asked for.",
        ],
        "columns": [{"key": k, "label": label} for k, label in _WORK_COLUMNS],
        "rows": rows,
    }


@dataclass(frozen=True, slots=True)
class OpenAccessCopy:
    """One lawful open copy of a work: where it is, which version, under which licence."""

    row_key: str
    url: str
    version: str | None
    licence: str | None
    best: bool


def open_access_copies(result: DatasetResult) -> tuple[OpenAccessCopy, ...]:
    """The open-access locations of a DOI lookup, OpenAlex's best first, then in its order.

    Only a location OpenAlex marks ``is_oa`` is a copy: one readable "without needing
    to pay money or log in". Its URL is the PDF where there is one, else the landing
    page; a location with neither is no copy.
    """
    if result.connector_id != OPENALEX_CONNECTOR_ID or not result.dataset_id.startswith("doi:"):
        raise ValueError("not an OpenAlex DOI lookup")
    at = {c.key: i for i, c in enumerate(result.columns)}
    copies: list[OpenAccessCopy] = []
    for row in result.rows:
        v = row.values
        if v[at["is_oa"]] != "true":
            continue
        url = v[at["pdf_url"]] or v[at["landing_page_url"]]
        if url is None:
            continue
        copies.append(
            OpenAccessCopy(
                row_key=row.key,
                url=url,
                version=v[at["version"]],
                licence=v[at["license"]],
                best=v[at["best_oa"]] == "yes",
            )
        )
    return tuple(sorted(copies, key=lambda c: not c.best))
