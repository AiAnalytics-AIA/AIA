"""One WARC record from one gzip member: read when it is exactly what it says, refused otherwise.

The records are built here, by the WARC 1.1 grammar, around fictional pages.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
from datetime import UTC, datetime

import pytest

from aia_core.domain.deep_research.warc import (
    MAX_RECORD_INFLATED_BYTES,
    inflate_member,
    parse_response_record,
)
from aia_core.domain.deep_research.web import FetchRefused

PAGE = b"<html><head><title>Zprava</title></head><body><p>Fiktivni trh.</p></body></html>"


def record(
    body: bytes = PAGE,
    *,
    version: bytes = b"WARC/1.0",
    warc_type: str = "response",
    http_headers: str = "Content-Type: text/html; charset=utf-8",
    digest: str | None = "auto",
    length_delta: int = 0,
    ending: bytes = b"\r\n\r\n",
    extra: str = "",
) -> bytes:
    block = b"HTTP/1.1 200 OK\r\n" + http_headers.encode() + b"\r\n\r\n" + body
    if digest == "auto":
        digest = "sha1:" + base64.b32encode(hashlib.sha1(body).digest()).decode()
    fields = [
        f"WARC-Type: {warc_type}",
        "WARC-Date: 2024-02-21T10:11:12Z",
        "WARC-Record-ID: <urn:uuid:00000000-0000-4000-8000-000000000001>",
        "WARC-Target-URI: https://stats.example/zprava/2023",
        "Content-Type: application/http; msgtype=response",
        f"Content-Length: {len(block) + length_delta}",
    ]
    if digest is not None:
        fields.append(f"WARC-Payload-Digest: {digest}")
    if extra:
        fields.append(extra)
    return version + b"\r\n" + "\r\n".join(fields).encode() + b"\r\n\r\n" + block + ending


def _reason(call: object) -> str:
    with pytest.raises(FetchRefused) as caught:
        call()  # type: ignore[operator]
    return caught.value.reason


def test_a_member_inflates_and_its_response_record_is_read() -> None:
    raw = record(extra="WARC-Truncated: length")
    parsed = parse_response_record(inflate_member(gzip.compress(raw)))
    assert parsed.target_uri == "https://stats.example/zprava/2023"
    assert parsed.record_id == "<urn:uuid:00000000-0000-4000-8000-000000000001>"
    assert parsed.captured_at == datetime(2024, 2, 21, 10, 11, 12, tzinfo=UTC)
    assert parsed.http_status == 200
    assert parsed.http_headers["content-type"] == "text/html; charset=utf-8"
    assert parsed.body == PAGE
    assert parsed.truncated == "length"
    assert parsed.payload_digest is not None and parsed.payload_digest.startswith("sha1:")
    assert parse_response_record(record(version=b"WARC/1.1", digest=None)).payload_digest is None


def test_a_truncated_member_is_refused() -> None:
    member = gzip.compress(record())
    assert _reason(lambda: inflate_member(member[:-9])) == "archive_record_truncated"


def test_a_member_that_inflates_past_its_bound_is_refused_without_inflating_it_all() -> None:
    bomb = gzip.compress(b"\0" * (MAX_RECORD_INFLATED_BYTES + 1))
    assert len(bomb) < 50_000
    assert _reason(lambda: inflate_member(bomb)) == "archive_record_too_large"
    assert _reason(lambda: inflate_member(gzip.compress(b"x" * 101), max_bytes=100)) == (
        "archive_record_too_large"
    )


def test_bytes_after_the_member_or_bytes_that_are_not_gzip_are_refused() -> None:
    two = gzip.compress(record()) + gzip.compress(record())
    assert _reason(lambda: inflate_member(two)) == "archive_record_trailing"
    assert _reason(lambda: inflate_member(b"WARC/1.0\r\n")) == "archive_record_corrupt"


@pytest.mark.parametrize(
    ("raw", "reason"),
    [
        (record(version=b"WARC/0.9"), "archive_record_invalid"),
        (record(warc_type="request"), "archive_record_invalid"),
        (record(length_delta=5), "archive_record_truncated"),
        (record(length_delta=-5), "archive_record_invalid"),
        (record(ending=b""), "archive_record_invalid"),
        (record(digest="sha1:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"), "archive_digest_mismatch"),
        (record(http_headers="Content-Encoding: gzip"), "archive_body_encoded"),
        (record(http_headers="Transfer-Encoding: chunked"), "archive_body_encoded"),
        (b"WARC/1.0\r\nWARC-Type: response", "archive_record_invalid"),
    ],
)
def test_a_record_that_disagrees_with_itself_is_refused(raw: bytes, reason: str) -> None:
    assert _reason(lambda: parse_response_record(raw)) == reason


def test_a_record_without_its_id_target_or_date_is_refused() -> None:
    for field in (b"WARC-Record-ID", b"WARC-Target-URI", b"WARC-Date"):
        raw = record().replace(field + b":", b"X-Other:", 1)
        assert _reason(lambda raw=raw: parse_response_record(raw)) == "archive_record_invalid"


def test_another_digest_algorithm_is_kept_and_left_unchecked() -> None:
    parsed = parse_response_record(record(digest="sha256:whatever"))
    assert parsed.payload_digest == "sha256:whatever"
