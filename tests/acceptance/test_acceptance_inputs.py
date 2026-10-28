"""The representative study's fixed inputs (``docs/migration/mvp-acceptance.md`` §1; plan
``mvp-acceptance-harness`` chunk 2): pinned, fictional, and taken by the stack as they stand.

The inputs live in ``inputs/``, each pinned by SHA-256 in ``inputs/index.json`` like the golden
fixtures. These tests prove the inputs are the ones committed and that the stack takes each one
over HTTP the way the web client sends it. They prove no acceptance criterion and are listed under
none; the criteria use the inputs as they are wired (chunk 5).
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest

pytestmark = pytest.mark.acceptance

INPUTS = Path(__file__).resolve().parent / "inputs"
INDEX = INPUTS / "index.json"
#: Everything section 1 names, by its key in the index.
KEYS = ("brief", "concepts", "client_document", "client_dataset", "web_page", "past_study")
#: The one column of the dataset the personal-data detector must flag, and why.
PERSONAL_COLUMN = ("E-mail kontaktní osoby", "EMAIL")


def _index() -> dict[str, Any]:
    entries: dict[str, Any] = json.loads(INDEX.read_text("utf-8"))["inputs"]
    return entries


def _bytes(key: str) -> bytes:
    return (INPUTS / str(_index()[key]["file"])).read_bytes()


def _json(key: str) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(_bytes(key))
    return loaded


def _over_template(template: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    """The input's fields over the research template, a nested object merged, as the workbench's
    fixtures lay a project over it (``tools/ui_workbench/fixture_project.py`` ``project_of``)."""
    content: dict[str, Any] = json.loads(json.dumps(template))
    for key, value in fields.items():
        content[key] = {**content.get(key, {}), **value} if isinstance(value, dict) else value
    return content


# --------------------------------------------------------------------------- #
# pinned and fictional, read from the files alone
# --------------------------------------------------------------------------- #


def test_every_input_is_pinned_by_sha256_and_nothing_unpinned_is_kept() -> None:
    index = _index()
    assert tuple(index) == KEYS, list(index)
    for key, entry in index.items():
        actual = hashlib.sha256((INPUTS / entry["file"]).read_bytes()).hexdigest()
        assert actual == entry["sha256"], (key, entry["file"], actual)
    kept = {p.name for p in INPUTS.iterdir()} - {INDEX.name}
    assert kept == {e["file"] for e in index.values()}, kept


def test_the_inputs_name_no_real_person_address_or_site() -> None:
    """Fictional by construction: every e-mail on ``example.test``, the page on ``.example``
    (RFC 2606: never anyone's)."""
    for key in _index():
        text = _bytes(key).decode("utf-8")
        for address in re.findall(r"[\w.+-]+@[\w.-]+", text):
            assert address.endswith("@example.test"), (key, address)
        for url in re.findall(r"https?://[^\s\"'<>]+", text):
            assert (urlsplit(url).hostname or "").endswith(".example"), (key, url)
    host = urlsplit(_index()["web_page"]["url"]).hostname or ""
    assert host.endswith(".example"), host


def test_the_brief_and_the_concepts_are_the_studys_own() -> None:
    """The brief sentence, the audience and n of section 1; five concepts service_a ... e."""
    brief = _json("brief")["content"]
    assert brief["goal"].startswith("Jak hodnotí čeští dospělí ve věku 18")
    assert "pět navrhovaných změn služeb městské knihovny" in brief["goal"]
    assert brief["audience"]["filters"] == {"vek": {"min": 18, "max": 65}}
    assert brief["n"] == 300
    concepts = _json("concepts")["objects"]
    assert [c["id"] for c in concepts] == [f"service_{x}" for x in "abcde"]
    assert len({c["name"] for c in concepts}) == 5


# --------------------------------------------------------------------------- #
# taken by the stack, over HTTP
# --------------------------------------------------------------------------- #


def _client_and_study(
    http: Any, researcher: str, unique: Callable[[str], str], name: str
) -> tuple[str, str]:
    client = http.post(
        "/clients",
        {"slug": unique("acceptance-client"), "name": "Acceptance client (fiktivní)"},
        as_user=researcher,
    )
    assert client.status == 201, client.text
    client_id = str(client.json()["client_id"])
    return client_id, _study(http, researcher, unique, client_id, name)


def _study(
    http: Any, researcher: str, unique: Callable[[str], str], client_id: str, name: str
) -> str:
    study = http.post(
        "/studies",
        {"client_id": client_id, "slug": unique("study"), "name": name, "budget_usd": 25},
        as_user=researcher,
    )
    assert study.status == 201, study.text
    return str(study.json()["study_id"])


def _save(http: Any, researcher: str, study_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """The input saved as the study's working copy; the copy the server then holds."""
    path = f"/studies/{study_id}/workspace/content"
    loaded = http.get(path, as_user=researcher)
    assert loaded.status == 200, loaded.text
    current = loaded.json()
    content = _over_template(current["content"] or current["template"], fields)
    saved = http.put(
        path,
        {"content": content, "base_revision": current["revision"], "reason": "acceptance_input"},
        as_user=researcher,
    )
    assert saved.status == 200, saved.text
    held = http.get(path, as_user=researcher)
    assert held.status == 200, held.text
    body: dict[str, Any] = held.json()
    assert body["revision"] == saved.json()["revision"]
    return body


def test_the_brief_is_saved_as_the_studys_working_copy(
    http: Any, people: Any, signed_in: Callable[[str], None], unique: Callable[[str], str]
) -> None:
    signed_in(people.researcher)
    _, study_id = _client_and_study(http, people.researcher, unique, "MVP acceptance (fiktivní)")
    brief = _json("brief")["content"]
    held = _save(http, people.researcher, study_id, brief)["content"]
    for key in ("title", "goal", "decision_use", "n"):
        assert held[key] == brief[key], key
    for key, value in brief["briefing"].items():
        assert held["briefing"][key] == value, key
    assert held["audience"]["filters"] == brief["audience"]["filters"]


def test_the_past_studys_design_is_submitted_and_reused(
    http: Any, people: Any, signed_in: Callable[[str], None], unique: Callable[[str], str]
) -> None:
    """Project memory's input: the past study's design becomes a Design Revision, and a new
    study of the same client starts from it, citing it."""
    signed_in(people.researcher)
    past = _json("past_study")
    client_id, past_id = _client_and_study(http, people.researcher, unique, past["name"])
    held = _save(http, people.researcher, past_id, past["content"])
    submitted = http.post(
        f"/studies/{past_id}/design/revisions",
        {
            "content": held["content"],
            "source_stage": "questionnaire",
            "workspace_revision": held["revision"],
        },
        as_user=people.researcher,
    )
    assert submitted.status == 201, submitted.text
    revision_id = submitted.json()["revision_id"]

    reused = http.post(
        f"/clients/{client_id}/memory/reuse",
        {
            "source_study_id": past_id,
            "source_revision_id": revision_id,
            "new_study_name": "MVP acceptance z minulé studie (fiktivní)",
        },
        as_user=people.researcher,
    )
    assert reused.status == 201, reused.text
    body = reused.json()
    assert body["created_study"] is True
    assert body["source"]["source_study_id"] == past_id
    assert body["source"]["source_revision_id"] == revision_id
    target = http.get(f"/studies/{body['study_id']}/workspace/content", as_user=people.researcher)
    assert target.status == 200, target.text
    sections = target.json()["content"]["sections"]
    assert [s["id"] for s in sections] == [s["id"] for s in past["content"]["sections"]]


def _add_source(http: Any, researcher: str, client_id: str, key: str) -> dict[str, Any]:
    added = http.post(
        f"/clients/{client_id}/sources",
        {
            "filename": _index()[key]["file"],
            "data_b64": base64.b64encode(_bytes(key)).decode("ascii"),
        },
        as_user=researcher,
    )
    assert added.status == 201, added.text
    assert added.json()["sha256"] == _index()[key]["sha256"]
    detail = http.get(
        f"/clients/{client_id}/sources/{added.json()['source_id']}", as_user=researcher
    )
    assert detail.status == 200, detail.text
    body: dict[str, Any] = detail.json()
    return body


def test_the_client_document_is_kept_and_read(
    http: Any, people: Any, signed_in: Callable[[str], None], unique: Callable[[str], str]
) -> None:
    signed_in(people.researcher)
    client_id, _ = _client_and_study(http, people.researcher, unique, "MVP acceptance (fiktivní)")
    reading = _add_source(http, people.researcher, client_id, "client_document")["reading"]
    assert reading["outcome"] == "READ", reading
    assert any("6 840" in s["text"] for s in reading["segments"]), reading["segments"]


def test_the_client_dataset_has_exactly_one_personal_column(
    http: Any, people: Any, signed_in: Callable[[str], None], unique: Callable[[str], str]
) -> None:
    """The column the data contract must drop is the one the detector flags, and the only one."""
    signed_in(people.researcher)
    client_id, _ = _client_and_study(http, people.researcher, unique, "MVP acceptance (fiktivní)")
    reading = _add_source(http, people.researcher, client_id, "client_dataset")["reading"]
    assert reading["outcome"] == "READ", reading
    (sheet,) = reading["dataset"]["sheets"]
    assert sheet["rows"] == 48, sheet["rows"]
    flagged = [(c["header"], c["personal"]) for c in sheet["columns"] if c["personal"]]
    assert flagged == [PERSONAL_COLUMN], flagged
