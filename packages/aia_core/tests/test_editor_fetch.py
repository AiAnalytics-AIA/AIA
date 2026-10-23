"""The one fetch AIA makes from the report editor's Document Server (artifact-report RPT8c)."""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.infrastructure.editor_fetch import LiveSaveFetcher, SaveFetchRefused, allowed

EDITOR = "https://docs.aia.example.test"


@pytest.mark.parametrize(
    "url",
    [
        f"{EDITOR}/cache/files/data/k/output.docx/output.docx?md5=x&expires=1",
        f"{EDITOR}/cache/files/x.docx",
    ],
)
def test_the_editors_own_file_is_allowed(url: str) -> None:
    assert allowed(url, EDITOR)


@pytest.mark.parametrize(
    "url",
    [
        "http://docs.aia.example.test/cache/files/x.docx",
        "https://evil.example.test/cache/files/x.docx",
        "https://docs.aia.example.test.evil.test/cache/files/x.docx",
        f"{EDITOR}:8443/cache/files/x.docx",
        "https://user@docs.aia.example.test/cache/files/x.docx",
        f"{EDITOR}/healthcheck",
        f"{EDITOR}/cache/files/../../etc/passwd",
        f"{EDITOR}/cache/files/%2e%2e/%2e%2e/etc/passwd",
        f"{EDITOR}/cache/filesx/x.docx",
        f"{EDITOR}/cache/files\\\\..\\\\x",
        "not a url",
    ],
)
def test_anything_else_is_refused(url: str) -> None:
    assert not allowed(url, EDITOR)


def test_the_live_fetcher_refuses_before_sending_anything() -> None:
    fetcher = LiveSaveFetcher(EDITOR)
    with pytest.raises(SaveFetchRefused) as refused:
        fetcher("https://169.254.169.254/latest/meta-data/")
    assert refused.value.reason == "not_the_editors_file"


class _Response:
    def __init__(self, status: int, body: bytes = b"", length: str | None = None) -> None:
        self.status, self._body = status, body
        self.headers = {} if length is None else {"Content-Length": length}
        self.released = False

    def stream(self, size: int) -> Any:
        for i in range(0, len(self._body), size):
            yield self._body[i : i + size]

    def release_conn(self) -> None:
        self.released = True


class _Pool:
    def __init__(self, response: _Response) -> None:
        self.response, self.asked = response, []

    def request(self, method: str, url: str, **kw: Any) -> _Response:
        self.asked.append((method, url, kw))
        return self.response


URL = f"{EDITOR}/cache/files/data/k/output.docx?md5=x&expires=1"


def _fetch(response: _Response, *, limit: int = 1024) -> tuple[bytes, _Pool]:
    fetcher = LiveSaveFetcher(EDITOR, max_bytes=limit)
    pool = _Pool(response)
    fetcher._pool = pool  # type: ignore[assignment]
    return fetcher(URL), pool


def test_a_save_is_fetched_once_without_retry_or_redirect() -> None:
    data, pool = _fetch(_Response(200, b"docx"))
    ((method, url, kw),) = pool.asked
    assert (method, url, data) == ("GET", URL, b"docx")
    assert kw["retries"] is False and kw["redirect"] is False and pool.response.released


@pytest.mark.parametrize(
    ("response", "reason"),
    [
        (_Response(403), "document_server_restarted"),
        (_Response(302), "document_server_answered_302"),
        (_Response(200, b"x" * 2000), "save_too_large"),
        (_Response(200, b"", length="999999"), "save_too_large"),
    ],
)
def test_a_save_not_fetched_whole_is_refused_by_name(response: _Response, reason: str) -> None:
    with pytest.raises(SaveFetchRefused) as refused:
        _fetch(response)
    assert refused.value.reason == reason and response.released
