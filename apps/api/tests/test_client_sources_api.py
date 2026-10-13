"""A client's sources over HTTP (lifecycle K2a).

A file is kept for the client, read at once with every segment's place in the original,
kept once per client by its bytes, served only as a download, and never found under
another client (404).
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any
from urllib.parse import quote

from fastapi.testclient import TestClient

API = "/api/v1"
FIXTURES = (
    Path(__file__).resolve().parents[3] / "packages/aia_core/tests/fixtures/attachment_text/inputs"
)


def upload(c: TestClient, client_id: str, name: str, data: bytes) -> Any:
    return c.post(
        f"{API}/clients/{client_id}/sources",
        json={"filename": name, "data_b64": base64.b64encode(data).decode()},
    )


def test_a_file_is_kept_read_and_listed_and_the_same_bytes_are_one_source(
    lead: TestClient, world: Any
) -> None:
    client = world.client_id("primary")
    pdf = (FIXTURES / "prezentace.pdf").read_bytes()
    first = upload(lead, client, "Zadání.pdf", pdf)
    assert first.status_code == 201, first.text
    body = first.json()
    assert (body["created"], body["family"], body["outcome"], body["reader"]) == (
        True,
        "DOCUMENT",
        "READ",
        "pdf/1",
    )
    assert body["filename"] == "Zadání.pdf" and body["segments"] == 2

    again = upload(lead, client, "kopie.pdf", pdf)
    assert again.status_code == 200 and again.json()["created"] is False
    assert again.json()["source_id"] == body["source_id"]
    assert [o["filename"] for o in again.json()["occurrences"]] == ["kopie.pdf", "Zadání.pdf"]

    listed = lead.get(f"{API}/clients/{client}/sources").json()
    assert [s["source_id"] for s in listed] == [body["source_id"]]

    detail = lead.get(f"{API}/clients/{client}/sources/{body['source_id']}").json()
    assert [s["locator"]["page"] for s in detail["reading"]["segments"]] == [1, 2]
    assert detail["reading"]["outcome"] == "READ"


def test_the_original_is_only_ever_a_download_under_the_name_as_written(
    lead: TestClient, world: Any
) -> None:
    client = world.client_id("primary")
    kept = upload(lead, client, "Poznámky.md", b"# Fakt").json()
    got = lead.get(f"{API}/clients/{client}/sources/{kept['source_id']}/original")
    assert got.status_code == 200 and got.content == b"# Fakt"
    assert got.headers["content-type"] == "application/octet-stream"
    assert got.headers["x-content-type-options"] == "nosniff"
    disposition = got.headers["content-disposition"]
    assert disposition.startswith('attachment; filename="Pozn_mky.md"')
    assert f"filename*=UTF-8''{quote('Poznámky.md')}" in disposition


def test_another_clients_source_is_not_found(
    lead: TestClient, other_client_lead: TestClient, world: Any
) -> None:
    client = world.client_id("primary")
    kept = upload(lead, client, "a.txt", b"Fakt.").json()
    other = world.client_id("other")
    assert other_client_lead.get(f"{API}/clients/{other}/sources").json() == []
    for path in ("", "/original"):
        # Under the other client's own path, the source is not there.
        assert (
            other_client_lead.get(
                f"{API}/clients/{other}/sources/{kept['source_id']}{path}"
            ).status_code
            == 404
        )


def test_what_cannot_be_kept_or_read_says_so_by_name(lead: TestClient, world: Any) -> None:
    client = world.client_id("primary")
    for name, data, code in (
        ("a.exe", b"MZ", "unsupported_format"),
        ("a.txt", b"", None),
    ):
        refused = lead.post(
            f"{API}/clients/{client}/sources",
            json={"filename": name, "data_b64": base64.b64encode(data).decode()},
        )
        assert refused.status_code == 422
        if code:
            assert refused.json()["code"] == code
    not_b64 = lead.post(
        f"{API}/clients/{client}/sources", json={"filename": "a.txt", "data_b64": "@@@"}
    )
    assert not_b64.status_code == 422 and not_b64.json()["code"] == "not_base64"

    image = upload(lead, client, "logo.png", (FIXTURES / "obrazek.png").read_bytes()).json()
    assert (image["outcome"], image["reason"]) == ("UNREADABLE", "not_text_media")
    pending = upload(lead, client, "data.xlsx", (FIXTURES / "tabulka.xlsx").read_bytes()).json()
    assert (pending["outcome"], pending["reason"]) == ("UNSUPPORTED", "reader_pending")


def test_an_unknown_source_id_is_404(lead: TestClient, world: Any) -> None:
    client = world.client_id("primary")
    assert lead.get(f"{API}/clients/{client}/sources/SRC-0000000000000000").status_code == 404
    assert lead.get(f"{API}/clients/{client}/sources/not-an-id").status_code == 422
