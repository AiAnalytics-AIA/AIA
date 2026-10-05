"""What a web fetch may reach, and the shapes search and fetch return.

A fetch is the one place AIA opens a connection to an address a third party
chose: a search result names a URL, and the URL names a host. So the rules are
the fetcher's first gate, and they fail closed:

* only ``http``/``https``, on their default ports, with no credentials in the URL;
* no host that names the inside of a network (``localhost``, ``*.internal``,
  cloud metadata names);
* every address the host resolves to must be globally routable -- not private,
  loopback, link-local (169.254.169.254 is the metadata service), CGNAT,
  multicast, reserved or unspecified, IPv4-mapped forms included -- and a host
  that resolves to nothing is refused;
* the same checks on **every redirect hop**, at most :data:`MAX_REDIRECTS` of them;
* a body of at most :data:`MAX_BODY_BYTES`, of a declared textual content type.

The fetcher applies these to what its resolver and transport report (see
``aia_core.infrastructure.web_retrieval``). A live transport must connect to the
address that was checked, not resolve again (DNS rebinding); that is a
requirement on the adapter that does not exist yet (DR-2).

Pure: stdlib only.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlsplit

__all__ = [
    "ALLOWED_CONTENT_TYPES",
    "MAX_ALTERNATE_LINKS",
    "MAX_BODY_BYTES",
    "MAX_LINK_TEXT_CHARS",
    "MAX_LINK_URL_CHARS",
    "MAX_REDIRECTS",
    "MAX_SNAPSHOT_LINKS",
    "MAX_TEXT_CHARS",
    "FetchRefused",
    "SearchHit",
    "check_address",
    "check_content_type",
    "check_resolution",
    "check_url",
]

MAX_REDIRECTS: Final = 3
MAX_BODY_BYTES: Final = 2_000_000
#: Normalised text kept per snapshot; beyond it the snapshot says it is truncated.
MAX_TEXT_CHARS: Final = 200_000
ALLOWED_CONTENT_TYPES: Final = frozenset({"text/html", "text/plain", "application/xhtml+xml"})
#: Outbound ``<a href>`` links kept with an HTML snapshot, first in document order.
MAX_SNAPSHOT_LINKS: Final = 200
#: ``<link rel="alternate">`` targets kept with an HTML snapshot (feeds, translations).
MAX_ALTERNATE_LINKS: Final = 20
#: A link's anchor text is normalised and cut to this many characters.
MAX_LINK_TEXT_CHARS: Final = 200
#: A longer link is dropped, never truncated: a cut URL names another resource.
MAX_LINK_URL_CHARS: Final = 2048

_ALLOWED_PORTS: Final = {"http": 80, "https": 443}
_BLOCKED_NAMES: Final = frozenset(
    {"localhost", "metadata", "metadata.google.internal", "instance-data", "kubernetes"}
)
_BLOCKED_SUFFIXES: Final = (
    ".localhost",
    ".local",
    ".internal",
    ".intranet",
    ".lan",
    ".home",
    ".corp",
    ".home.arpa",
    ".localdomain",
)


class FetchRefused(Exception):
    """A URL, an address or a response the fetcher will not use. ``reason`` is stable."""

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class SearchHit:
    """One search result as the search adapter reported it. A pointer, not evidence."""

    url: str
    title: str
    snippet: str
    rank: int


def _ip(host: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return None


def check_address(address: str) -> None:
    """Raise :class:`FetchRefused` unless ``address`` is a globally routable IP."""
    ip = _ip(address)
    if ip is None:
        raise FetchRefused(f"{address!r} is not an IP address", reason="address_invalid")
    mapped = getattr(ip, "ipv4_mapped", None)
    for candidate in (ip, mapped):
        if candidate is not None and not candidate.is_global:
            raise FetchRefused(f"{address} is not a public address", reason="address_not_public")
    if ip.is_multicast:
        raise FetchRefused(f"{address} is a multicast address", reason="address_not_public")


def check_url(url: str) -> str:
    """Return the host of a URL the fetcher may request, or raise :class:`FetchRefused`."""
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise FetchRefused(f"{url!r} is not a URL", reason="url_invalid") from exc
    scheme = parts.scheme.lower()
    if scheme not in _ALLOWED_PORTS:
        raise FetchRefused(f"scheme {scheme or '(none)'!r} is not fetched", reason="url_scheme")
    if parts.username is not None or parts.password is not None:
        raise FetchRefused("a URL carrying credentials is not fetched", reason="url_credentials")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise FetchRefused(f"{url!r} names no host", reason="url_invalid")
    if port is not None and port != _ALLOWED_PORTS[scheme]:
        raise FetchRefused(f"port {port} is not fetched", reason="url_port")
    if _ip(host) is not None:
        check_address(host)
        return host
    if host in _BLOCKED_NAMES or host.endswith(_BLOCKED_SUFFIXES) or "." not in host:
        raise FetchRefused(f"{host} names an internal host", reason="url_internal_host")
    return host


def check_resolution(host: str, addresses: Sequence[str]) -> None:
    """Every address a host resolves to must be public, and there must be one."""
    if not addresses:
        raise FetchRefused(f"{host} does not resolve", reason="address_unresolved")
    for address in addresses:
        check_address(address)


def check_content_type(header: str) -> str:
    """The media type of a response the fetcher keeps, or raise :class:`FetchRefused`."""
    media = header.split(";", 1)[0].strip().lower()
    if media not in ALLOWED_CONTENT_TYPES:
        raise FetchRefused(f"content type {media or '(none)'!r} is not kept", reason="content_type")
    return media
