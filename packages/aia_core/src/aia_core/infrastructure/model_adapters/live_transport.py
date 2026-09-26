"""The live :class:`~.transport.HttpTransport`: one HTTPS exchange, never retried.

Built on ``urllib3``, which botocore already depends on, so the route's live path
adds no library of its own (PROGRESS D7 answered for Bedrock). Two properties are
the whole point of this module:

* **No retry, anywhere.** ``urllib3``'s default ``Retry`` re-sends on connection
  errors and some read errors; a re-sent Converse call is a second billed call the
  gateway never recorded. ``retries=False`` on the pool *and* the request.
* **Delivery is stated from the failure.** A failure that provably happens before
  any request byte is written (DNS, a refused connection, a connect timeout, the
  server's certificate refused during the handshake) is ``NOT_SENT``: nothing can
  have been billed. Anything else may have followed the request -- a read timeout,
  a reset, a truncated response, **any other TLS error**, which urllib3 raises the
  same way from the handshake and from reading the answer -- and is ``UNKNOWN``,
  the ``SETTLED_UNCERTAIN`` case. When the kind of failure is unclear, ``UNKNOWN``.

The blocking call runs in a thread so the gateway's ``await`` holds no event-loop
lock; the worker's heartbeat runs on its own thread either way.
"""

from __future__ import annotations

import asyncio
import json
import ssl
from typing import Any

from aia_core.domain.ai_contracts import Delivery

from .transport import HttpRequest, HttpResponse, TransportFailure

__all__ = ["Urllib3Transport"]


def _certificate_refused(error: BaseException) -> bool:
    """True when ``error`` wraps a refused server certificate (a handshake-only failure).

    urllib3 wraps the ``ssl`` exception as the SSLError's argument and chains it;
    both are followed. ``ssl.CertificateError`` is ``SSLCertVerificationError``.
    """
    seen: set[int] = set()
    stack: list[BaseException] = [error]
    while stack:
        current = stack.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, ssl.SSLCertVerificationError):
            return True
        stack.extend(a for a in current.args if isinstance(a, BaseException))
        for linked in (current.__cause__, current.__context__):
            if linked is not None:
                stack.append(linked)
    return False


class Urllib3Transport:
    """:class:`~.transport.HttpTransport` over one ``urllib3.PoolManager``."""

    def __init__(self, *, connect_timeout_s: float = 10.0, ca_certs: str | None = None) -> None:
        import urllib3

        self._urllib3 = urllib3
        self._connect_timeout_s = connect_timeout_s
        kwargs: dict[str, Any] = {"retries": False}
        if ca_certs:
            kwargs["ca_certs"] = ca_certs
        self._pool = urllib3.PoolManager(**kwargs)

    def _send(self, request: HttpRequest, timeout_s: float) -> HttpResponse:
        u = self._urllib3
        body = request.raw_body
        if body is None:
            body = json.dumps(dict(request.body), ensure_ascii=False).encode("utf-8")
        try:
            response = self._pool.request(
                request.method,
                request.url,
                body=body,
                headers=dict(request.headers),
                timeout=u.Timeout(connect=self._connect_timeout_s, read=timeout_s),
                retries=False,
                redirect=False,
            )
        except (u.exceptions.ConnectTimeoutError, u.exceptions.NewConnectionError) as exc:
            # ConnectTimeoutError and NewConnectionError (NameResolutionError is a
            # subclass) are raised before the request is written.
            raise TransportFailure(str(exc), delivery=Delivery.NOT_SENT) from exc
        except u.exceptions.SSLError as exc:
            # urllib3 raises the same SSLError from the handshake and from reading
            # the response (getresponse, the body): the class does not say whether
            # the request was written. Only a certificate-verification failure is
            # provably pre-send -- the client verifies the server during the
            # handshake, before any application data -- so only that is NOT_SENT.
            delivery = Delivery.NOT_SENT if _certificate_refused(exc) else Delivery.UNKNOWN
            raise TransportFailure(str(exc), delivery=delivery) from exc
        except u.exceptions.HTTPError as exc:
            # ReadTimeoutError, ProtocolError (reset, incomplete read) and anything
            # else: the request may have reached Bedrock.
            raise TransportFailure(str(exc), delivery=Delivery.UNKNOWN) from exc

        raw = response.data or b""
        parsed: Any
        try:
            parsed = json.loads(raw.decode("utf-8")) if raw else None
        except (UnicodeDecodeError, ValueError):
            parsed = raw.decode("utf-8", errors="replace")
        return HttpResponse(
            status=int(response.status),
            headers={k.lower(): str(v) for k, v in response.headers.items()},
            body=parsed,
        )

    async def send(self, request: HttpRequest, *, timeout_s: float) -> HttpResponse:
        return await asyncio.to_thread(self._send, request, timeout_s)
