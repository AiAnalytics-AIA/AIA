"""The D6 decision package names the presets exactly as the code computes them.

``docs/architecture/sociomapa-methodology-decision.md`` is what the methodology owner
approves; an approval binds a fingerprint. If a preset changed and the package did not, the
owner would approve one method and the runs would compute another.
"""

from __future__ import annotations

import re
from pathlib import Path

from aia_core.domain.sociomap import AIA_SOCIOMAP_V1, AIA_SOCIOMAP_V2, AIA_SOCIOMAP_V3

REPO = Path(__file__).resolve().parents[3]
PACKAGE = REPO / "docs/architecture/sociomapa-methodology-decision.md"


def _fingerprints() -> dict[str, str]:
    """Each section's spec name and the fingerprint its table states."""
    text = PACKAGE.read_text("utf-8")
    pairs = re.findall(
        r"\| Spec \| `(AIA_SOCIOMAP_V\d)`.*?\n\| Spec fingerprint \| `([0-9a-f]{64})` \|", text
    )
    return dict(pairs)


def test_every_preset_the_package_names_has_its_true_fingerprint() -> None:
    stated = _fingerprints()
    assert stated == {
        "AIA_SOCIOMAP_V1": AIA_SOCIOMAP_V1.fingerprint(),
        "AIA_SOCIOMAP_V2": AIA_SOCIOMAP_V2.fingerprint(),
        "AIA_SOCIOMAP_V3": AIA_SOCIOMAP_V3.fingerprint(),
    }


def test_the_current_subject_is_the_preset_new_runs_pin() -> None:
    from aia_core.domain.research_sociomap import default_methods

    text = PACKAGE.read_text("utf-8")
    subject = re.search(r"D6 is now to approve \*\*`([a-z0-9-]+)`\*\*", text)
    assert subject is not None
    assert subject.group(1) in {m.method_id for m in default_methods()}
    assert subject.group(1) == AIA_SOCIOMAP_V3.methodology_version
