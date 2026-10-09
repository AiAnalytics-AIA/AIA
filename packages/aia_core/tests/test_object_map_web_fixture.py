"""The web's object map fixture is what the builder writes, byte for byte.

``apps/web/src/lib/fixtures/object-map.json`` is rendered by the Results page's tests; it
is written by ``tools/object_map_web_fixture.py`` from ``research_sociomaps`` under the
default pins, never by hand, so the browser's reading of a contract-3 map is checked
against the artifact the worker actually stores.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]


def _tool():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "object_map_web_fixture", REPO / "tools/object_map_web_fixture.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_stored_fixture_is_what_the_builder_writes() -> None:
    stored = (REPO / "apps/web/src/lib/fixtures/object-map.json").read_text("utf-8")
    assert stored == _tool().render(), "run python tools/object_map_web_fixture.py"


def test_the_fixture_shows_every_case_the_view_draws() -> None:
    body = json.loads((REPO / "apps/web/src/lib/fixtures/object-map.json").read_text("utf-8"))
    (battery,) = body["sociomap"]["batteries"]
    art = battery["maps"]["aia-sociomap-3"]["artifact"]
    assert art["outcome"] == "MAPPED" and art["terrain"]["status"] == "computed"
    assert art["not_placed"], "a respondent not placed"
    counts = art["status_counts"]
    assert counts["reliable"] and counts["weak"], "both drawn and undrawn pairs"
    meets = art["relations"]["meets_effect_floor"]
    assert any(v is False for row in meets for v in row), "a pair below the effect floor"
