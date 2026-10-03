"""Runtime kill switch for native workspace artifacts; independent of AI settings."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class SociomapSettings:
    workspace_enabled: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> SociomapSettings:
        values = os.environ if env is None else env
        value = values.get("AIA_SOCIOMAP_WORKSPACE_ENABLED", "false").strip().lower()
        if value not in {"true", "false", "1", "0"}:
            raise ValueError("AIA_SOCIOMAP_WORKSPACE_ENABLED must be true or false")
        return cls(workspace_enabled=value in {"true", "1"})
