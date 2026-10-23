"""The one way AIA fetches a saved report from the report editor's Document Server (RPT8c).

A callback names the file it saved by a URL the Document Server signs itself (its secure link:
``md5`` and ``expires``). AIA fetches it, and nothing else, by one rule (:func:`allowed`): ``GET``
on the editor's exact origin (``AIA_ONLYOFFICE_URL``: https, its host, no other port, no user
info), under ``/cache/files/``, never a redirect, at most :data:`MAX_SAVE_BYTES`. A callback
cannot point AIA anywhere else: a URL off that origin or path is refused before anything is sent.

The Document Server draws a new secure-link secret each time it starts, so a link it handed out
before a restart answers 403: :class:`SaveFetchRefused` says ``document_server_restarted``, and
the caller stores nothing and says so (the PM's note, 2026-10-22).
"""

from __future__ import annotations

import posixpath
from collections.abc import Callable
from typing import Any, Final
from urllib.parse import unquote, urlsplit

__all__ = [
    "MAX_SAVE_BYTES",
    "LiveSaveFetcher",
    "SaveFetchRefused",
    "SaveFetcher",
    "allowed",
]

#: A report with its fonts embedded is a few megabytes; this is ample, and bounds the read.
MAX_SAVE_BYTES: Final = 64 * 1024 * 1024
CACHE_PATH: Final = "/cache/files/"
_CHUNK: Final = 64 * 1024

#: What fetches a saved file: the URL in, the bytes out, or :class:`SaveFetchRefused`.
SaveFetcher = Callable[[str], bytes]


class SaveFetchRefused(Exception):
    """A save AIA did not fetch, or fetched and refused. ``reason`` is stable."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def allowed(url: str, origin: str) -> bool:
    """Whether ``url`` is a file of the Document Server at ``origin``: https, the same host and
    port, no user info, a path under ``/cache/files/`` that no ``..`` or encoding leaves."""
    try:
        target, editor = urlsplit(url), urlsplit(origin)
        port, editor_port = target.port, editor.port
    except ValueError:
        return False
    path = unquote(target.path)
    return (
        target.scheme == "https"
        and editor.scheme == "https"
        and target.hostname is not None
        and target.hostname == editor.hostname
        and port == editor_port
        and "@" not in target.netloc
        and not target.fragment
        and path.startswith(CACHE_PATH)
        and posixpath.normpath(path).startswith(CACHE_PATH)
        and "\\" not in path
    )


class LiveSaveFetcher:
    """:data:`SaveFetcher` over ``urllib3``: no retry, no redirect, a bounded read.

    ``urllib3`` is imported here, as the other live transports do: it comes with the ``bedrock``
    extra the images install, and the API's import path must not need it."""

    def __init__(
        self,
        origin: str,
        *,
        max_bytes: int = MAX_SAVE_BYTES,
        connect_timeout_s: float = 10.0,
        read_timeout_s: float = 60.0,
        ca_certs: str | None = None,
    ) -> None:
        import urllib3

        self._urllib3 = urllib3
        self._origin = origin
        self._max = max_bytes
        self._timeout = urllib3.Timeout(connect=connect_timeout_s, read=read_timeout_s)
        kwargs: dict[str, Any] = {"retries": False}
        if ca_certs:
            kwargs["ca_certs"] = ca_certs
        self._pool = urllib3.PoolManager(**kwargs)

    def __call__(self, url: str) -> bytes:
        if not allowed(url, self._origin):
            raise SaveFetchRefused("not_the_editors_file")
        try:
            response = self._pool.request(
                "GET",
                url,
                preload_content=False,
                retries=False,
                redirect=False,
                timeout=self._timeout,
            )
        except self._urllib3.exceptions.HTTPError as exc:
            raise SaveFetchRefused("document_server_unreachable") from exc
        try:
            if response.status == 403:
                raise SaveFetchRefused("document_server_restarted")
            if response.status != 200:
                raise SaveFetchRefused(f"document_server_answered_{response.status}")
            return _bounded(response, self._max)
        finally:
            response.release_conn()


def _bounded(response: Any, limit: int) -> bytes:
    declared = response.headers.get("Content-Length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise SaveFetchRefused("save_too_large")
    parts: list[bytes] = []
    size = 0
    for chunk in response.stream(_CHUNK):
        size += len(chunk)
        if size > limit:
            raise SaveFetchRefused("save_too_large")
        parts.append(chunk)
    return b"".join(parts)
