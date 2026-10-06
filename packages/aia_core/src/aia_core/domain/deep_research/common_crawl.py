"""Common Crawl's URL index: the query code writes, the rows it accepts, what a scan costs.

Plan chunk 18 (``deep-research-web-search.md`` §§ 5.3, 7 rung 9). The URL index is
Common Crawl's columnar index (Parquet, ``s3://commoncrawl/cc-index/table/cc-main/warc/``,
partitioned by ``crawl`` and ``subset``), read through Amazon Athena in ``us-east-1``,
where the data lives. ``docs/architecture/deep-research-common-crawl.md`` records
which of these facts were verified, and where.

**No model writes SQL.** A caller states a :class:`UrlIndexQuery` -- one exact URL,
or a host or registered domain with an optional path prefix; the crawls; the HTTP
statuses and media types wanted; a date window; a row limit -- and every value is
validated against a narrow alphabet before :func:`build_index_sql` writes the one
statement shape this module knows. No value may contain a quote, a backslash or
whitespace, so none can leave its literal; the crawl and subset partitions are
always constrained, so a statement can never scan the whole index.

**A scan's price is configuration.** :class:`AthenaPricing` has no defaults: the
price per terabyte scanned, the minimum billed per query and the billing increment
are set by whoever signs for the account (plan chunk 23), and the cost of a query
is computed from the bytes Athena reports it scanned. A terabyte here is 10^12
bytes (an assumption recorded as unverified in the document above).

Pure: stdlib only.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Final
from urllib.parse import urlsplit

from .web import FetchRefused, check_url

__all__ = [
    "ARCHIVE_HOST",
    "ATHENA_REGION",
    "INDEX_COLUMNS",
    "MAX_CRAWLS_PER_QUERY",
    "MAX_INDEX_ROWS",
    "MAX_WARC_RECORD_BYTES",
    "TERABYTE_BYTES",
    "AthenaPricing",
    "IndexQueryInvalid",
    "IndexRow",
    "IndexRowInvalid",
    "IndexTable",
    "IndexTarget",
    "UrlIndexQuery",
    "archive_url",
    "build_index_sql",
    "parse_index_rows",
]

#: Where the Common Crawl bucket, and so its index, lives (AWS Open Data Registry).
#: A residency fact, not a choice: a query is processed where the data is.
ATHENA_REGION: Final = "us-east-1"
#: Common Crawl's public HTTPS endpoint for its archive files (byte ranges served).
ARCHIVE_HOST: Final = "data.commoncrawl.org"
#: Athena's GetQueryResults returns at most 1,000 rows a page; one page is enough.
MAX_INDEX_ROWS: Final = 1000
#: Each crawl named is another partition scanned and paid for.
MAX_CRAWLS_PER_QUERY: Final = 6
#: One compressed WARC record (one gzip member) AIA will request.
MAX_WARC_RECORD_BYTES: Final = 2_000_000
#: Bytes in a terabyte for Athena's price. Unverified: decimal assumed.
TERABYTE_BYTES: Final = 10**12

#: The columns a query reads, in order. Fewer columns scan fewer bytes.
INDEX_COLUMNS: Final = (
    "url",
    "fetch_time",
    "fetch_status",
    "content_mime_type",
    "content_digest",
    "warc_filename",
    "warc_record_offset",
    "warc_record_length",
    "crawl",
)

_CRAWL: Final = re.compile(r"^CC-MAIN-\d{4}-\d{2}$")
_IDENTIFIER: Final = re.compile(r"^[a-z_][a-z0-9_]{0,63}$")
_HOST: Final = re.compile(
    r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,62}$"
)
_PATH_PREFIX: Final = re.compile(r"^/[A-Za-z0-9/._~%!$&()*+,;=:@-]{0,199}$")
#: An exact URL: RFC 3986's unreserved and reserved characters and ``%``, minus the
#: single quote (it would end a SQL literal; such a URL is not queried).
_URL_CHARS: Final = re.compile(r"^[A-Za-z0-9:/?#\[\]@!$&()*+,;=._~%-]{1,2048}$")
_MIME: Final = re.compile(r"^[a-z0-9][a-z0-9.+-]{0,63}/[a-z0-9][a-z0-9.+-]{0,99}$")
_WARC_FILE: Final = re.compile(r"^crawl-data/CC-MAIN-\d{4}-\d{2}/[A-Za-z0-9._/-]{1,400}\.warc\.gz$")
_DIGEST: Final = re.compile(r"^[A-Za-z0-9:+/=]{1,100}$")
_TIMESTAMP: Final = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?(?: UTC|Z)?$"
)


class IndexQueryInvalid(ValueError):
    """A URL index query that code will not write. Nothing was sent."""


class IndexRowInvalid(ValueError):
    """An index row that does not have the shape this module reads."""


class IndexTarget(StrEnum):
    #: One URL, exactly as the archive recorded it (an archived copy of one page).
    URL = "url"
    #: Every capture on one host name (``url_host_name``).
    HOST = "host"
    #: Every capture on a registered domain and its subdomains (``url_host_registered_domain``).
    DOMAIN = "domain"


_TARGET_COLUMN: Final = {
    IndexTarget.URL: "url",
    IndexTarget.HOST: "url_host_name",
    IndexTarget.DOMAIN: "url_host_registered_domain",
}


@dataclass(frozen=True, slots=True)
class IndexTable:
    """The Athena database and table that hold the index (an operator creates them)."""

    database: str
    table: str

    def __post_init__(self) -> None:
        for name in (self.database, self.table):
            if not _IDENTIFIER.match(name):
                raise IndexQueryInvalid(f"{name!r} is not a plain lower-case identifier")


@dataclass(frozen=True, slots=True)
class UrlIndexQuery:
    """What a caller may ask of the index: validated values, never SQL.

    ``value`` is the URL (``target=URL``) or the host or registered domain. A
    ``path_prefix`` narrows a host or domain to paths starting with it. The
    ``crawls`` are partitions, at least one and at most
    :data:`MAX_CRAWLS_PER_QUERY`; ``statuses`` the HTTP statuses kept (200 unless
    asked); ``mime_types`` the declared media types kept (any when empty); the
    window is on the capture time, both ends inclusive, as UTC dates.
    """

    target: IndexTarget
    value: str
    crawls: tuple[str, ...]
    limit: int
    path_prefix: str | None = None
    statuses: tuple[int, ...] = (200,)
    mime_types: tuple[str, ...] = ()
    captured_from: date | None = None
    captured_to: date | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= MAX_INDEX_ROWS:
            raise IndexQueryInvalid(f"a query returns 1 to {MAX_INDEX_ROWS} rows")
        if not 1 <= len(self.crawls) <= MAX_CRAWLS_PER_QUERY:
            raise IndexQueryInvalid(f"a query names 1 to {MAX_CRAWLS_PER_QUERY} crawls")
        if len(set(self.crawls)) != len(self.crawls):
            raise IndexQueryInvalid("a crawl is named twice")
        for crawl in self.crawls:
            if not _CRAWL.match(crawl):
                raise IndexQueryInvalid(f"{crawl!r} is not a crawl id (CC-MAIN-YYYY-WW)")
        if self.target is IndexTarget.URL:
            if self.path_prefix is not None:
                raise IndexQueryInvalid("an exact URL takes no path prefix")
            if not _URL_CHARS.match(self.value):
                raise IndexQueryInvalid("the URL has a character a query does not carry")
            try:
                check_url(self.value)
            except FetchRefused as exc:
                raise IndexQueryInvalid(f"the URL is not a public web URL: {exc.reason}") from exc
            if urlsplit(self.value).fragment:
                raise IndexQueryInvalid("an archived URL has no fragment")
        else:
            if not _HOST.match(self.value):
                raise IndexQueryInvalid(f"{self.value!r} is not a lower-case host name")
            if self.path_prefix is not None and not _PATH_PREFIX.match(self.path_prefix):
                raise IndexQueryInvalid("the path prefix has a character a query does not carry")
        if not self.statuses or len(self.statuses) > 10:
            raise IndexQueryInvalid("a query keeps 1 to 10 HTTP statuses")
        for status in self.statuses:
            if isinstance(status, bool) or not 100 <= status <= 599:
                raise IndexQueryInvalid(f"{status!r} is not an HTTP status")
        if len(self.mime_types) > 10:
            raise IndexQueryInvalid("a query keeps at most 10 media types")
        for mime in self.mime_types:
            if not _MIME.match(mime):
                raise IndexQueryInvalid(f"{mime!r} is not a lower-case media type")
        if (
            self.captured_from is not None
            and self.captured_to is not None
            and self.captured_from > self.captured_to
        ):
            raise IndexQueryInvalid("the capture window ends before it starts")


def _literal(value: str) -> str:
    """A SQL string literal for a value already validated; refuses anything that could escape."""
    if "'" in value or "\\" in value or any(c.isspace() for c in value):
        raise IndexQueryInvalid("a value with a quote, a backslash or whitespace is not written")
    return f"'{value}'"


def build_index_sql(query: UrlIndexQuery, table: IndexTable) -> str:
    """The one statement shape this module writes, from validated values only.

    The crawl partitions and ``subset = 'warc'`` are always constrained (partition
    pruning: only the named crawls are scanned). Rows come newest first.
    """
    where = [
        "crawl IN (" + ", ".join(_literal(c) for c in query.crawls) + ")",
        "subset = 'warc'",
        f"{_TARGET_COLUMN[query.target]} = {_literal(query.value)}",
    ]
    if query.path_prefix is not None:
        where.append(
            f"substr(url_path, 1, {len(query.path_prefix)}) = {_literal(query.path_prefix)}"
        )
    where.append("fetch_status IN (" + ", ".join(str(int(s)) for s in query.statuses) + ")")
    if query.mime_types:
        where.append(
            "content_mime_type IN (" + ", ".join(_literal(m) for m in query.mime_types) + ")"
        )
    if query.captured_from is not None:
        where.append(f"fetch_time >= TIMESTAMP '{query.captured_from.isoformat()} 00:00:00'")
    if query.captured_to is not None:
        where.append(f"fetch_time <= TIMESTAMP '{query.captured_to.isoformat()} 23:59:59'")
    return (
        "SELECT "
        + ", ".join(INDEX_COLUMNS)
        + f'\nFROM "{table.database}"."{table.table}"'
        + "\nWHERE "
        + "\n  AND ".join(where)
        + "\nORDER BY fetch_time DESC"
        + f"\nLIMIT {int(query.limit)}"
    )


@dataclass(frozen=True, slots=True)
class IndexRow:
    """One capture the index lists: where its WARC record is, and what it was."""

    url: str
    captured_at: datetime
    status: int
    mime_type: str | None
    digest: str | None
    warc_filename: str
    warc_record_offset: int
    warc_record_length: int
    crawl: str


def _timestamp(raw: str) -> datetime:
    match = _TIMESTAMP.match(raw.strip())
    if match is None:
        raise IndexRowInvalid(f"fetch_time {raw!r} is not a timestamp this module reads")
    fraction = (match[7] or "0")[:6].ljust(6, "0")
    try:
        return datetime(
            int(match[1]),
            int(match[2]),
            int(match[3]),
            int(match[4]),
            int(match[5]),
            int(match[6]),
            int(fraction),
            tzinfo=UTC,
        )
    except ValueError as exc:
        raise IndexRowInvalid(f"fetch_time {raw!r} is not a date") from exc


def _integer(raw: str | None, column: str) -> int:
    if raw is None or not re.fullmatch(r"\d{1,12}", raw.strip()):
        raise IndexRowInvalid(f"{column} is not a non-negative integer")
    return int(raw)


def _row(values: Mapping[str, str | None]) -> IndexRow:
    url = values.get("url")
    if url is None or not _URL_CHARS.match(url):
        raise IndexRowInvalid("the row's url is missing or carries an unexpected character")
    try:
        check_url(url)
    except FetchRefused as exc:
        raise IndexRowInvalid(f"the row's url is not a public web URL: {exc.reason}") from exc
    crawl = values.get("crawl") or ""
    if not _CRAWL.match(crawl):
        raise IndexRowInvalid("the row names no crawl")
    filename = values.get("warc_filename") or ""
    if (
        not _WARC_FILE.match(filename)
        or ".." in filename
        or "//" in filename
        or not filename.startswith(f"crawl-data/{crawl}/")
    ):
        raise IndexRowInvalid("the row's WARC file name is not one of its crawl's files")
    length = _integer(values.get("warc_record_length"), "warc_record_length")
    if not 0 < length <= MAX_WARC_RECORD_BYTES:
        raise IndexRowInvalid(f"a WARC record is 1 to {MAX_WARC_RECORD_BYTES} bytes")
    mime = values.get("content_mime_type")
    digest = values.get("content_digest")
    if digest is not None and not _DIGEST.match(digest):
        raise IndexRowInvalid("the row's content digest has an unexpected character")
    status = _integer(values.get("fetch_status"), "fetch_status")
    if not 100 <= status <= 599:
        raise IndexRowInvalid("fetch_status is not an HTTP status")
    return IndexRow(
        url=url,
        captured_at=_timestamp(values.get("fetch_time") or ""),
        status=status,
        mime_type=mime.strip().lower()[:200] if mime else None,
        digest=digest,
        warc_filename=filename,
        warc_record_offset=_integer(values.get("warc_record_offset"), "warc_record_offset"),
        warc_record_length=length,
        crawl=crawl,
    )


def parse_index_rows(
    columns: Sequence[str], rows: Sequence[Sequence[str | None]]
) -> tuple[IndexRow, ...]:
    """The rows of a result whose columns are :data:`INDEX_COLUMNS` (any order).

    A result missing a column, or a row of another width, is refused whole: a
    result this module did not ask for is not read in part.
    """
    missing = [c for c in INDEX_COLUMNS if c not in columns]
    if missing:
        raise IndexRowInvalid(f"the result lacks {', '.join(missing)}")
    if len(rows) > MAX_INDEX_ROWS:
        raise IndexRowInvalid(f"a result holds at most {MAX_INDEX_ROWS} rows")
    parsed: list[IndexRow] = []
    for row in rows:
        if len(row) != len(columns):
            raise IndexRowInvalid("a row's width is not the result's")
        parsed.append(_row(dict(zip(columns, row, strict=True))))
    return tuple(parsed)


def archive_url(row: IndexRow) -> str:
    """The HTTPS URL of the WARC file that holds ``row``'s record."""
    return f"https://{ARCHIVE_HOST}/{row.warc_filename}"


@dataclass(frozen=True, slots=True)
class AthenaPricing:
    """What a query costs, as configured: no default anywhere.

    ``usd_per_tb_scanned`` is the price per :data:`TERABYTE_BYTES` scanned; a query
    is billed at least ``minimum_billed_bytes`` and in whole
    ``billing_increment_bytes``. The values come from the account's dated price
    list (plan chunk 23), never from code.
    """

    usd_per_tb_scanned: float
    minimum_billed_bytes: int
    billing_increment_bytes: int

    def __post_init__(self) -> None:
        if not math.isfinite(self.usd_per_tb_scanned) or self.usd_per_tb_scanned <= 0:
            raise ValueError("a scan price is a finite, positive number")
        if self.minimum_billed_bytes < 0 or self.billing_increment_bytes <= 0:
            raise ValueError("billing is in positive increments over a non-negative minimum")

    def billed_bytes(self, scanned_bytes: int) -> int:
        """The bytes a query that scanned ``scanned_bytes`` is billed for."""
        if scanned_bytes < 0:
            raise ValueError("bytes scanned are not negative")
        increment = self.billing_increment_bytes
        rounded = -(-scanned_bytes // increment) * increment
        return max(self.minimum_billed_bytes, rounded)

    def cost_usd(self, scanned_bytes: int) -> float:
        """The money a query that scanned ``scanned_bytes`` costs."""
        return self.billed_bytes(scanned_bytes) * self.usd_per_tb_scanned / TERABYTE_BYTES
