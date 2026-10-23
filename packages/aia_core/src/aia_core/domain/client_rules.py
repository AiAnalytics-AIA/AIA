"""A client's rules (settings-backends SB7; deep-research-web-search 53, client-knowledge-
lifecycle K11): its data posture and the ceiling on its studies' wallets, set by an
organization OWNER or ADMIN on Profil → Pravidla.

``OPEN``: the client's material may be researched publicly; ``CLASSIFIED``: it may not. A
posture never set (``None``) is **read as CLASSIFIED**, never as open: absence is not consent.
Whether the posture replaces classification in Deep Research's gates is its own change (53's
second half), reviewed with the security audit; here it is stored, shown and pinned on a run.
Pure.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["DataPosture", "effective_posture"]


class DataPosture(StrEnum):
    OPEN = "OPEN"
    CLASSIFIED = "CLASSIFIED"


def effective_posture(stored: str | None) -> DataPosture:
    """The posture a run pins: the stored one, or CLASSIFIED when none was set. A stored value
    the code no longer knows raises, never guessed open."""
    return DataPosture.CLASSIFIED if stored is None else DataPosture(stored)
