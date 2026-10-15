"""What every outbound HTTP adapter shares: the model adapters and the web routes alike.

The model adapters (:mod:`.model_adapters`), the live web retrieval routes
(:mod:`.web_retrieval_live`, :mod:`.web_retrieval_brave`) and the Common Crawl
index (:mod:`.common_crawl`) each speak to a remote service over their own
transport. Three things are common to them, and live here so that nothing outside
the model adapters has to import :mod:`.model_adapters` to get them -- an import of
the model adapters is a model-call path, and ``lint-imports`` allows it only to
the executor compositions that build one:

* :func:`certificate_refused` -- whether a failure was the server's certificate
  refused during the handshake, the one TLS failure that provably sent nothing;
* :class:`CredentialSource` -- a credential reference resolved to its secret;
* :class:`SigningUnavailable` -- no acceptable credential could sign a request.
"""

from __future__ import annotations

import ssl
from typing import Protocol

__all__ = ["CredentialSource", "SigningUnavailable", "certificate_refused"]


def certificate_refused(error: BaseException) -> bool:
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


class CredentialSource(Protocol):
    """Resolves a credential reference to its secret. Raises ``KeyError`` if absent.

    The adapter holds a *reference*, never the secret, so configuration and logs
    can name which credential a route uses without containing it.
    """

    def secret(self, reference: str) -> str: ...


class SigningUnavailable(Exception):
    """No acceptable credential could sign the request. Nothing was sent."""
