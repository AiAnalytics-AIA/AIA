"""Which :class:`~aia_core.infrastructure.storage.ArtifactStore` a process uses.

One definition, read by every composition root -- the API's ``dependencies.py``
and the executors' registry factory -- so the API and the worker never disagree
about where a study's artifacts live. The backend is selected from typed
configuration, never from an environment check inside the store
(``ARCHITECTURE.md`` §4).

Environment:

``AIA_STORAGE_BACKEND``     ``s3`` | ``filesystem`` | ``memory`` (default ``memory``)
``AIA_STORAGE_BUCKET``      the S3 bucket; required for ``s3``
``AIA_STORAGE_REGION``      the bucket's region; required for ``s3``
``AIA_STORAGE_PREFIX``      optional key prefix inside the bucket
``AIA_STORAGE_KMS_KEY_ID``  optional customer-managed KMS key; SSE-S3 otherwise
``AIA_STORAGE_ENDPOINT``    optional S3-compatible endpoint (MinIO), local only
``AIA_STORAGE_ROOT``        directory for ``filesystem`` (default ``./data/artifacts``)

S3 credentials are never read here. ``boto3`` resolves them from its default
chain, which in a deployment is the instance or task role and locally is the
``AWS_*`` variables; the application holds no storage secret of its own.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal, get_args

from .storage import (
    ArtifactStore,
    FilesystemArtifactStore,
    InMemoryArtifactStore,
    S3ArtifactStore,
)

__all__ = ["StorageBackend", "StorageSettings", "build_artifact_store"]

StorageBackend = Literal["s3", "filesystem", "memory"]
_BACKENDS: Final[tuple[str, ...]] = get_args(StorageBackend)


@dataclass(frozen=True, slots=True)
class StorageSettings:
    """Typed storage configuration. Validated on construction."""

    backend: StorageBackend = "memory"
    bucket: str = ""
    region: str = ""
    prefix: str = ""
    kms_key_id: str = ""
    endpoint_url: str = ""
    root: str = "./data/artifacts"

    def __post_init__(self) -> None:
        if self.backend not in _BACKENDS:
            raise ValueError(
                f"AIA_STORAGE_BACKEND must be one of {', '.join(_BACKENDS)}, got {self.backend!r}"
            )
        if self.backend == "s3" and not self.bucket.strip():
            raise ValueError("AIA_STORAGE_BUCKET is required when AIA_STORAGE_BACKEND=s3")
        if self.backend == "filesystem" and not self.root.strip():
            raise ValueError("AIA_STORAGE_ROOT is required when AIA_STORAGE_BACKEND=filesystem")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> StorageSettings:
        """Read the ``AIA_STORAGE_*`` variables. Blank values take the defaults."""
        source = os.environ if env is None else env

        def get(name: str, default: str = "") -> str:
            return (source.get(name) or "").strip() or default

        backend = get("AIA_STORAGE_BACKEND", "memory").lower()
        if backend not in _BACKENDS:
            raise ValueError(
                f"AIA_STORAGE_BACKEND must be one of {', '.join(_BACKENDS)}, got {backend!r}"
            )
        return cls(
            backend=backend,  # type: ignore[arg-type]  # validated against _BACKENDS above
            bucket=get("AIA_STORAGE_BUCKET"),
            region=get("AIA_STORAGE_REGION"),
            prefix=get("AIA_STORAGE_PREFIX"),
            kms_key_id=get("AIA_STORAGE_KMS_KEY_ID"),
            endpoint_url=get("AIA_STORAGE_ENDPOINT"),
            root=get("AIA_STORAGE_ROOT", "./data/artifacts"),
        )

    def deployment_problems(self) -> list[str]:
        """Why this configuration is unacceptable in a deployed environment.

        Empty means acceptable. A deployed process keeps artifacts in S3 and
        nowhere else: memory vanishes with the container, a container filesystem
        is unshared, and an endpoint override points at something that is not S3
        (a MinIO on the host, say), which the hosted environments do not run.
        """
        problems: list[str] = []
        if self.backend != "s3":
            problems.append(
                f"AIA_STORAGE_BACKEND must be 's3' in a deployed environment, not '{self.backend}'"
            )
            return problems
        if not self.region:
            problems.append("AIA_STORAGE_REGION is required for S3 in a deployed environment")
        if self.endpoint_url:
            problems.append(
                "AIA_STORAGE_ENDPOINT must not be set in a deployed environment; "
                "artifacts live in S3 itself"
            )
        return problems


def build_artifact_store(settings: StorageSettings) -> ArtifactStore:
    """Construct the configured store. The S3 client is created lazily, on first use."""
    if settings.backend == "s3":
        return S3ArtifactStore(
            settings.bucket,
            endpoint_url=settings.endpoint_url or None,
            region_name=settings.region or None,
            kms_key_id=settings.kms_key_id or None,
            prefix=settings.prefix,
        )
    if settings.backend == "filesystem":
        return FilesystemArtifactStore(settings.root)
    return InMemoryArtifactStore()
