"""What a fetch may reach: public http(s) only, every hop, every resolved address."""

from __future__ import annotations

import pytest

from aia_core.domain.deep_research.web import (
    FetchRefused,
    check_address,
    check_content_type,
    check_resolution,
    check_url,
)


@pytest.mark.parametrize(
    "url",
    ["https://www.example.org/a", "http://example.org", "https://93.184.215.14/page"],
)
def test_public_http_urls_pass(url: str) -> None:
    assert check_url(url)


@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("ftp://example.org/f", "url_scheme"),
        ("file:///etc/passwd", "url_scheme"),
        ("javascript:alert(1)", "url_scheme"),
        ("https://user:pass@example.org/", "url_credentials"),
        ("https://example.org:8443/", "url_port"),
        ("http://example.org:22/", "url_port"),
        ("https://localhost/admin", "url_internal_host"),
        ("http://metadata.google.internal/computeMetadata", "url_internal_host"),
        ("http://intranet/", "url_internal_host"),
        ("http://printer.local/", "url_internal_host"),
        ("http://169.254.169.254/latest/meta-data/", "address_not_public"),
        ("http://10.0.0.5/", "address_not_public"),
        ("http://127.0.0.1:80/", "address_not_public"),
        ("http://[::1]/", "address_not_public"),
        ("http://[::ffff:10.0.0.1]/", "address_not_public"),
        ("http://100.64.0.1/", "address_not_public"),
        ("http://0.0.0.0/", "address_not_public"),
        ("https:///no-host", "url_invalid"),
        ("http://[not-an-ip/", "url_invalid"),
    ],
)
def test_everything_else_is_refused_with_a_reason(url: str, reason: str) -> None:
    with pytest.raises(FetchRefused) as refused:
        check_url(url)
    assert refused.value.reason == reason


@pytest.mark.parametrize(
    "address",
    ["10.1.2.3", "172.16.0.1", "192.168.1.1", "169.254.169.254", "fd00::1", "fe80::1", "224.0.0.1"],
)
def test_private_link_local_and_multicast_addresses_are_refused(address: str) -> None:
    with pytest.raises(FetchRefused):
        check_address(address)


def test_a_host_must_resolve_and_every_address_must_be_public() -> None:
    check_resolution("example.org", ["93.184.215.14", "2606:2800:21f:cb07:6820:80da:af6b:8b2c"])
    with pytest.raises(FetchRefused) as unresolved:
        check_resolution("example.org", [])
    assert unresolved.value.reason == "address_unresolved"
    # One private answer among public ones is a rebinding attempt, not a choice.
    with pytest.raises(FetchRefused):
        check_resolution("example.org", ["93.184.215.14", "10.0.0.7"])


def test_only_declared_text_types_are_kept() -> None:
    assert check_content_type("text/html; charset=utf-8") == "text/html"
    assert check_content_type("TEXT/PLAIN") == "text/plain"
    for header in ("application/pdf", "image/png", "application/octet-stream", ""):
        with pytest.raises(FetchRefused) as refused:
            check_content_type(header)
        assert refused.value.reason == "content_type"
