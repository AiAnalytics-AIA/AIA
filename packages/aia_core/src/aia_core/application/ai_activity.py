"""Settings → AI běh: each activity's last answered call (settings-redesign F14, OI-75 (a)).

An organization OWNER or ADMIN reads, per native AI activity, when it last answered, on which
model and by which build: the usage ledger's newest ``SUCCEEDED`` call of each, across every
study of the organization -- the second cross-study read besides the work queue, an aggregate
naming no client, study, person, text or cost (the product owner, 2026-10-25). Read-only.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..domain.ai_activity import ACTIVITY_AGENT_IDS, LastAnswered, RuntimeActivity, last_answered
from ..domain.scope import OrganizationContext
from ..infrastructure.ai_usage_repository import last_answered_calls

__all__ = ["last_answered_by_activity"]


def last_answered_by_activity(
    session: Session, admin: OrganizationContext
) -> dict[RuntimeActivity, LastAnswered]:
    """Each activity's last answered call in the caller's organization; an activity that has
    none recorded is absent. OWNER or ADMIN (``ScopeDenied`` ``insufficient_role`` otherwise)."""
    admin.require_administer()
    return last_answered(
        last_answered_calls(
            session, organization_id=admin.organization_id, agent_ids=ACTIVITY_AGENT_IDS
        )
    )
