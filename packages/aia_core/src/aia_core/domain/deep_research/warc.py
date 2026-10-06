"""One WARC record, read from one gzip member: bounded, strict, and refused when unsure.

Plan chunk 18. A Common Crawl capture is fetched as the byte range the URL index
names inside a ``.warc.gz`` file. WARC 1.1 ("Record-at-time compression")
compresses each record as its own gzip member, so the range is one complete
member that inflates to one record:

    warc-record = header CRLF block CRLF CRLF
    header      = version warc-fields          ; "WARC/1.1" CRLF, or "WARC/1.0"
    warc-fields = *named-field CRLF

Every way the bytes can disagree with that is a refusal with a stable reason
(:class:`~aia_core.domain.deep_research.web.FetchRefused`), never a best guess:

* the member does not end inside the range (``archive_record_truncated``), more
  follows it (``archive_record_trailing``), it inflates past the bound
  (``archive_record_too_large``) or is not gzip (``archive_record_corrupt``);
* the record is not one ``response`` record carrying an HTTP response
  (``archive_record_invalid``), its ``Content-Length`` disagrees with its block,
  or its ``WARC-Payload-Digest`` (``sha1:``) does not match the body
  (``archive_digest_mismatch``);
* the HTTP body is still transfer- or content-encoded (``archive_body_encoded``):
  AIA reads the payload as stored and does not decode one it was not built for.

Pure: stdlib only.
"""

from __future__ import annotations

import base64
import hashlib
import re
import zlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from .web import MAX_BODY_BYTES, FetchRefused

__all__ = [
    "MAX_HTTP_HEADER_BYTES",
    "MAX_RECORD_INFLATED_BYTES",
    "WarcRecord",
    "inflate_member",
    "parse_response_record",
]

#: An HTTP header block AIA reads from an archived response.
MAX_HTTP_HEADER_BYTES: Final = 64_000
#: WARC headers, HTTP headers and the body a live fetch would keep, and no more.
MAX_RECORD_INFLATED_BYTES: Final = MAX_BODY_BYTES + MAX_HTTP_HEADER_BYTES + 16_000

_INVALID: Final = "archive_record_invalid"
_VERSIONS: Final = (b"WARC/1.0", b"WARC/1.1")
_STATUS_LINE: Final = re.compile(rb"^HTTP/\d(?:\.\d)? (\d{3})(?: .*)?$")
_WARC_DATE: Final = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,9})?Z$")


def _refused(message: str, reason: str) -> FetchRefused:
    return FetchRefused(message, reason=reason)


def inflate_member(data: bytes, *, max_bytes: int = MAX_RECORD_INFLATED_BYTES) -> bytes:
    """The one gzip member ``data`` is, inflated to at most ``max_bytes``.

    Refuses a member that does not end within ``data``, anything after it, an
    output past ``max_bytes`` (inflation stops there: a small range cannot become
    a large allocation) and bytes that are not gzip.
    """
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    inflater = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
    try:
        out = inflater.decompress(data, max_bytes + 1)
    except zlib.error as exc:
        raise _refused(f"the record is not gzip: {exc}", "archive_record_corrupt") from exc
    if len(out) > max_bytes or inflater.unconsumed_tail:
        raise _refused(f"the record inflates past {max_bytes} bytes", "archive_record_too_large")
    if not inflater.eof:
        raise _refused("the gzip member does not end in the range", "archive_record_truncated")
    if inflater.unused_data:
        raise _refused("bytes follow the record's gzip member", "archive_record_trailing")
    return out


@dataclass(frozen=True, slots=True)
class WarcRecord:
    """A ``response`` record: its WARC fields, and the HTTP response it holds."""

    #: WARC named fields, names lower-cased (field names are case-insensitive).
    fields: Mapping[str, str]
    record_id: str
    target_uri: str
    captured_at: datetime
    http_status: int
    #: HTTP headers, names lower-cased; a repeated header keeps its first value.
    http_headers: Mapping[str, str]
    body: bytes
    payload_digest: str | None
    truncated: str | None


def _fields(block: bytes) -> dict[str, str]:
    """Named fields, continuation lines folded in; the first of a repeated name wins."""
    fields: dict[str, str] = {}
    last: str | None = None
    seen_field = False
    for raw in block.split(b"\r\n"):
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace")
        if line[0] in " \t":
            if not seen_field:
                raise _refused("a continuation line with no field", _INVALID)
            if last is not None:
                fields[last] = f"{fields[last]} {line.strip()}"
            continue
        name, sep, value = line.partition(":")
        if not sep or not name.strip() or name != name.strip():
            raise _refused(f"{line[:80]!r} is not a named field", _INVALID)
        seen_field = True
        key = name.lower()
        # A repeated name keeps its first value; its continuation lines are dropped too.
        last = None if key in fields else key
        fields.setdefault(key, value.strip())
    return fields


def _warc_date(raw: str) -> datetime:
    match = _WARC_DATE.match(raw)
    if match is None:
        raise _refused(f"WARC-Date {raw[:40]!r} is not a UTC timestamp", _INVALID)
    try:
        year, month, day, hour, minute, second = (int(match[i]) for i in range(1, 7))
        return datetime(year, month, day, hour, minute, second, tzinfo=UTC)
    except ValueError as exc:
        raise _refused("WARC-Date is not a date", _INVALID) from exc


def _check_digest(labelled: str, body: bytes) -> None:
    algorithm, sep, value = labelled.partition(":")
    if not sep:
        raise _refused("WARC-Payload-Digest has no algorithm", _INVALID)
    if algorithm.strip().lower() != "sha1":
        # Only sha1 is checked; another algorithm is recorded and left unchecked.
        return
    expected = base64.b32encode(hashlib.sha1(body, usedforsecurity=False).digest()).decode()
    if value.strip().upper() != expected:
        raise _refused("the payload does not match its recorded digest", "archive_digest_mismatch")


def parse_response_record(record: bytes) -> WarcRecord:
    """Read one inflated WARC ``response`` record, or refuse it."""
    head_end = record.find(b"\r\n\r\n")
    if head_end < 0:
        raise _refused("the record has no end of its header", _INVALID)
    version, _, header = record[:head_end].partition(b"\r\n")
    if version not in _VERSIONS:
        raise _refused("the record does not start with WARC/1.0 or WARC/1.1", _INVALID)
    fields = _fields(header)
    if fields.get("warc-type", "").lower() != "response":
        raise _refused("the record is not a response record", _INVALID)
    content_type = fields.get("content-type", "").replace(" ", "").lower()
    if not content_type.startswith("application/http") or "msgtype=response" not in content_type:
        raise _refused("the record does not hold an HTTP response", _INVALID)
    length_raw = fields.get("content-length", "")
    if not length_raw.isdigit():
        raise _refused("the record has no Content-Length", _INVALID)
    length = int(length_raw)
    start = head_end + 4
    block = record[start : start + length]
    if len(block) != length:
        raise _refused("the block is shorter than its Content-Length", "archive_record_truncated")
    if record[start + length :] != b"\r\n\r\n":
        raise _refused("the record does not end where its Content-Length says", _INVALID)
    record_id = fields.get("warc-record-id", "")
    target_uri = fields.get("warc-target-uri", "")
    if not record_id or not target_uri:
        raise _refused("the record lacks its id or its target URI", _INVALID)
    captured_at = _warc_date(fields.get("warc-date", ""))

    http_end = block.find(b"\r\n\r\n")
    if http_end < 0 or http_end > MAX_HTTP_HEADER_BYTES:
        raise _refused("the HTTP header does not end within its bound", _INVALID)
    status_line, _, http_header = block[:http_end].partition(b"\r\n")
    status = _STATUS_LINE.match(status_line)
    if status is None:
        raise _refused("the block does not start with an HTTP status line", _INVALID)
    http_headers = _fields(http_header)
    if http_headers.get("transfer-encoding", "identity").lower() != "identity":
        raise _refused("the archived body is still transfer-encoded", "archive_body_encoded")
    if http_headers.get("content-encoding", "identity").lower() != "identity":
        raise _refused("the archived body is still content-encoded", "archive_body_encoded")
    body = block[http_end + 4 :]
    digest = fields.get("warc-payload-digest")
    if digest:
        _check_digest(digest, body)
    return WarcRecord(
        fields=fields,
        record_id=record_id,
        target_uri=target_uri.strip("<>"),
        captured_at=captured_at,
        http_status=int(status[1]),
        http_headers=http_headers,
        body=body,
        payload_digest=digest or None,
        truncated=fields.get("warc-truncated") or None,
    )
