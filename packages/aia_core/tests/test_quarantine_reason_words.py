"""Every reason Deep Research quarantines a finding for has Czech words on the Run screen
(plan run-recovery-and-truth 3d), held here equal to the web's ``trace.quarantine``; every
source class a finding's source is scored as has words beside it (``research.deep.sourceClass``,
D4), never its code."""

from __future__ import annotations

import re
from pathlib import Path

from aia_core.domain.deep_research.contracts import QuarantineReason
from aia_core.domain.deep_research.sources import SourceClass

CS_TS = Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "i18n" / "cs.ts"


def _web_reasons() -> set[str]:
    source = CS_TS.read_text(encoding="utf-8")
    block = re.search(r"\n\s*quarantine: \{\n(.*?)\n\s*\},", source, re.S)
    assert block is not None, "the web has no trace.quarantine block"
    return set(re.findall(r"^\s*([a-z_]+):", block.group(1), re.M))


def _web_source_classes() -> set[str]:
    source = CS_TS.read_text(encoding="utf-8")
    block = re.search(r"\n\s*sourceClass: \{\n(.*?)\n\s*\},", source, re.S)
    assert block is not None, "the web has no research.deep.sourceClass block"
    # Upper case: the codes; ``other`` is the words for a code the web does not know.
    return set(re.findall(r"^\s*([A-Z_]+):", block.group(1), re.M))


def test_every_quarantine_reason_has_words_on_the_run_screen() -> None:
    assert _web_reasons() == {r.value for r in QuarantineReason}


def test_every_source_class_has_words_beside_a_finding() -> None:
    assert _web_source_classes() == {c.value for c in SourceClass}
