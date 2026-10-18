"""A pytest plugin that keeps every report DOCX a test renders (``report_preview.py --journey``).

Loaded with ``-p report_journey_capture`` and ``tools/`` on ``PYTHONPATH``; inert unless
``AIA_REPORT_JOURNEY_DIR`` names a directory. Each document ``DocxRenderer.render`` returns is
written there once, by content (the same bytes rendered twice are kept once), named by the order
it first appeared and its report kind: ``01-internal.docx``, ``02-internal.docx`` ... The test
itself is unchanged; nothing here is imported by the product.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _keep_rendered_reports(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    target = os.environ.get("AIA_REPORT_JOURNEY_DIR")
    if not target:
        yield
        return
    out = Path(target)
    out.mkdir(parents=True, exist_ok=True)
    from aia_core.infrastructure.report_docx import renderer

    original = renderer.DocxRenderer.render
    seen = {hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob("[0-9][0-9]-*.docx")}

    def render(self: Any, doc: Any, *args: Any, **kwargs: Any) -> bytes:
        data: bytes = original(self, doc, *args, **kwargs)
        digest = hashlib.sha256(data).hexdigest()
        if digest not in seen:
            seen.add(digest)
            kind = str(getattr(getattr(doc, "meta", None), "kind", "report")).lower()
            (out / f"{len(seen):02d}-{kind.split('.')[-1]}.docx").write_bytes(data)
        return data

    monkeypatch.setattr(renderer.DocxRenderer, "render", render)
    yield
