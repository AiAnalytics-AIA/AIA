"""Infrastructure adapters: database tables, repositories, storage, providers.

Domain code must not import from this package; the dependency points inward only.
"""

from .db import (
    create_app_engine,
    create_session_factory,
    resolve_database_url,
    session_scope,
)
from .repositories import ProjectNotFound, ProjectPage, ProjectRepository
from .tables import (
    Base,
    ProjectArtifactDependencyRow,
    ProjectArtifactRow,
    ProjectEventRow,
    ProjectRevisionRow,
    ProjectRow,
    ProjectStageRow,
    ProviderEventRow,
    utcnow,
)

__all__ = [
    "Base",
    "ProjectArtifactDependencyRow",
    "ProjectArtifactRow",
    "ProjectEventRow",
    "ProjectNotFound",
    "ProjectPage",
    "ProjectRepository",
    "ProjectRevisionRow",
    "ProjectRow",
    "ProjectStageRow",
    "ProviderEventRow",
    "create_app_engine",
    "create_session_factory",
    "resolve_database_url",
    "session_scope",
    "utcnow",
]
