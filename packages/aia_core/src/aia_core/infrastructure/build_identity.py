"""The build a process is running: its git commit, read once from the environment.

Every deployed process -- API, worker, executors -- must be able to say exactly
which revision it is, so that a bug report, an artifact's provenance and the
running containers can be matched to one commit. The deployment bakes
``AIA_BUILD_SHA`` (and optionally ``AIA_BUILD_TIME``) into each image; a process
that is not told its build reports ``None``, never a placeholder, so nothing
downstream can mistake "unknown" for a real revision (``ARCHITECTURE.md`` A5).
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final

__all__ = ["BUILD_SHA_VAR", "BUILD_TIME_VAR", "BuildIdentity", "parse_build_sha"]

BUILD_SHA_VAR: Final = "AIA_BUILD_SHA"
BUILD_TIME_VAR: Final = "AIA_BUILD_TIME"

# A full or abbreviated git object name. Anything else -- "latest", "develop", a
# branch name, a truncated 6-character prefix -- is refused rather than recorded,
# because a wrong non-null revision in provenance is worse than none (A5).
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{7,40}$")


def parse_build_sha(raw: str | None) -> str | None:
    """Return a lower-case git SHA, or None when the value is blank or malformed.

    A malformed value raises rather than returning None: a deployment that sets
    ``AIA_BUILD_SHA=develop`` has a broken build step, and reporting "unknown"
    would hide it.
    """
    value = (raw or "").strip().lower()
    if not value:
        return None
    if not _GIT_SHA.match(value):
        raise ValueError(f"{BUILD_SHA_VAR} must be a 7-40 character hex git SHA, got {raw!r}")
    return value


@dataclass(frozen=True, slots=True)
class BuildIdentity:
    """What this process was built from. ``sha`` is None when not configured."""

    sha: str | None
    built_at: str | None = None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> BuildIdentity:
        source = os.environ if env is None else env
        return cls(
            sha=parse_build_sha(source.get(BUILD_SHA_VAR)),
            built_at=(source.get(BUILD_TIME_VAR) or "").strip() or None,
        )

    @property
    def short_sha(self) -> str | None:
        """The first twelve characters, for logs and footers."""
        return self.sha[:12] if self.sha else None

    def as_record(self) -> dict[str, str | None]:
        """The shape reported by health endpoints and start-up logs."""
        return {"sha": self.sha, "built_at": self.built_at}
