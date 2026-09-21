"""Artifact blob storage.

**Metadata in PostgreSQL. Bytes in object storage. Never the reverse.**

The database row is authoritative for identity, provenance and validity; the
object is just the payload. The prototype stored artifacts as filesystem paths
under the application directory, which breaks the moment there is more than one
process: a worker elsewhere cannot read another's disk, a redeploy loses the
files, and nothing is backed up.

Three implementations behind one protocol:

* :class:`S3ArtifactStore` -- production, S3 or any S3-compatible endpoint.
* :class:`FilesystemArtifactStore` -- local development, same semantics on disk.
* :class:`InMemoryArtifactStore` -- tests. Deterministic, no I/O.

All three enforce the same invariants, so a test that passes against the
in-memory store is meaningful: content is verified by hash on read, keys are
validated against traversal, and a missing object raises rather than returning
empty bytes.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Protocol, runtime_checkable

__all__ = [
    "ArtifactStore",
    "FilesystemArtifactStore",
    "InMemoryArtifactStore",
    "IntegrityError",
    "ObjectNotFound",
    "S3ArtifactStore",
    "StorageError",
    "StorageKey",
    "StoredObject",
    "build_storage_key",
    "sha256_bytes",
]


class StorageError(RuntimeError):
    """Base class for storage failures."""


class ObjectNotFound(StorageError):
    """The object does not exist.

    Distinct from empty content: a caller must never mistake a missing artifact
    for a zero-length one, because an empty analysis would be served as a valid
    result.
    """


class IntegrityError(StorageError):
    """The stored bytes do not match the recorded hash.

    For a system that makes research claims, serving unverified content as a
    finding is worse than failing. This is raised rather than returning the
    bytes.
    """


# Keys are built by this module, but a key also arrives from the database, where
# an older or hand-edited row could carry anything. Validation is applied on
# every read and write rather than trusting provenance.
_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9/_.\-]{0,1023}$")


def _validate_key(key: str) -> str:
    """Validate a storage key, rejecting traversal and absolute paths.

    ``..`` is rejected outright rather than normalised: a key that needed
    normalising was constructed wrongly, and silently rewriting it would mask the
    bug while still possibly escaping a tenant prefix.
    """
    if not key or not _SAFE_KEY.match(key):
        raise StorageError(f"unsafe storage key: {key!r}")
    if ".." in key.split("/") or key.startswith("/") or "//" in key:
        raise StorageError(f"unsafe storage key: {key!r}")
    return key


def sha256_bytes(data: bytes) -> str:
    """Return the SHA256 hex digest of ``data``."""
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True, slots=True)
class StorageKey:
    """A parsed artifact storage key."""

    organization_id: str
    client_id: str
    study_id: str
    project_id: str
    revision: int
    stage_type: str
    artifact_id: str

    def render(self) -> str:
        """Return the key string."""
        return build_storage_key(
            organization_id=self.organization_id,
            client_id=self.client_id,
            study_id=self.study_id,
            project_id=self.project_id,
            revision=self.revision,
            stage_type=self.stage_type,
            artifact_id=self.artifact_id,
        )


def build_storage_key(
    *,
    organization_id: str,
    client_id: str,
    study_id: str,
    project_id: str,
    revision: int,
    stage_type: str,
    artifact_id: str,
) -> str:
    """Build the storage key for one artifact.

    The prefix runs organization -> client -> study, outermost first, so that
    bucket policies, lifecycle rules, per-client metering and a client-wide
    deletion can all be expressed as prefix operations. Putting the project first
    would make "delete everything for this client" a full-bucket scan.
    """
    parts = [
        "org",
        organization_id,
        "client",
        client_id,
        "study",
        study_id,
        "proj",
        project_id,
        "rev",
        str(int(revision)),
        stage_type,
        artifact_id,
    ]
    for part in parts:
        if not part or "/" in part:
            raise StorageError(f"invalid storage key component: {part!r}")
    return _validate_key("/".join(parts))


@dataclass(frozen=True, slots=True)
class StoredObject:
    """The result of storing an object."""

    key: str
    sha256: str
    size_bytes: int
    content_type: str


@runtime_checkable
class ArtifactStore(Protocol):
    """Stores and retrieves artifact bytes.

    Implementations must be safe to share across threads. ``put`` is idempotent
    for identical content at the same key: storing the same bytes twice is not an
    error, which matters because a duplicate SQS delivery may re-run a step.
    """

    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        """Store ``data`` at ``key`` and return what was stored."""
        ...

    def get(self, key: str, *, expected_sha256: str | None = None) -> bytes:
        """Return the bytes at ``key``, verifying the hash when one is given."""
        ...

    def open(self, key: str) -> BinaryIO:
        """Return a readable stream for ``key``, for content too large to buffer."""
        ...

    def exists(self, key: str) -> bool:
        """True when an object exists at ``key``."""
        ...

    def delete(self, key: str) -> None:
        """Delete the object at ``key``. Deleting a missing object is not an error."""
        ...

    def presigned_url(self, key: str, *, expires_seconds: int = 300) -> str | None:
        """Return a time-limited download URL, or None when unsupported.

        Clients never receive a storage key or a path. A store that cannot issue
        a URL returns None and the caller streams the bytes through the API
        instead.
        """
        ...


class _BaseStore:
    """Shared verification logic, so every backend behaves identically."""

    def _verify(self, key: str, data: bytes, expected_sha256: str | None) -> bytes:
        """Raise :class:`IntegrityError` when the content hash does not match."""
        if expected_sha256 is not None:
            actual = sha256_bytes(data)
            if actual != expected_sha256:
                raise IntegrityError(
                    f"content hash mismatch for {key}: "
                    f"expected {expected_sha256[:12]}…, got {actual[:12]}…"
                )
        return data


class InMemoryArtifactStore(_BaseStore):
    """An in-memory store for tests. Deterministic, no I/O.

    Enforces the same key validation and hash verification as the production
    store, so a test passing here is evidence about production behaviour rather
    than about a permissive stub.
    """

    def __init__(self) -> None:
        self._objects: dict[str, tuple[bytes, str, dict[str, str]]] = {}
        self._lock = threading.Lock()

    @property
    def keys(self) -> list[str]:
        """Every stored key, for assertions."""
        with self._lock:
            return sorted(self._objects)

    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        _validate_key(key)
        with self._lock:
            self._objects[key] = (bytes(data), content_type, dict(metadata or {}))
        return StoredObject(
            key=key,
            sha256=sha256_bytes(data),
            size_bytes=len(data),
            content_type=content_type,
        )

    def get(self, key: str, *, expected_sha256: str | None = None) -> bytes:
        _validate_key(key)
        with self._lock:
            entry = self._objects.get(key)
        if entry is None:
            raise ObjectNotFound(key)
        return self._verify(key, entry[0], expected_sha256)

    def open(self, key: str) -> BinaryIO:
        return io.BytesIO(self.get(key))

    def exists(self, key: str) -> bool:
        _validate_key(key)
        with self._lock:
            return key in self._objects

    def delete(self, key: str) -> None:
        _validate_key(key)
        with self._lock:
            self._objects.pop(key, None)

    def presigned_url(self, key: str, *, expires_seconds: int = 300) -> str | None:
        """Not supported: there is no URL for memory."""
        return None


class FilesystemArtifactStore(_BaseStore):
    """A local-filesystem store for development.

    Writes are atomic -- temporary file, ``fsync``, rename -- so a crash or a
    concurrent reader never observes a partially written artifact. The prototype
    used the same technique and it is worth keeping.

    Not for production: a container filesystem is disposable and unshared.
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        """Resolve a key to a path, refusing anything outside the root."""
        _validate_key(key)
        path = (self._root / key).resolve()
        # Second barrier: even if key validation were bypassed, a path outside the
        # root is refused.
        if not path.is_relative_to(self._root):
            raise StorageError(f"storage key escapes the root: {key!r}")
        return path

    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)

        temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            with open(temp, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)

        return StoredObject(
            key=key,
            sha256=sha256_bytes(data),
            size_bytes=len(data),
            content_type=content_type,
        )

    def get(self, key: str, *, expected_sha256: str | None = None) -> bytes:
        path = self._path(key)
        try:
            data = path.read_bytes()
        except FileNotFoundError as exc:
            raise ObjectNotFound(key) from exc
        return self._verify(key, data, expected_sha256)

    def open(self, key: str) -> BinaryIO:
        path = self._path(key)
        try:
            return open(path, "rb")
        except FileNotFoundError as exc:
            raise ObjectNotFound(key) from exc

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def delete_prefix(self, prefix: str) -> int:
        """Delete every object under ``prefix``. Returns the count removed."""
        base = self._path(prefix)
        if not base.exists():
            return 0
        count = sum(1 for p in base.rglob("*") if p.is_file())
        shutil.rmtree(base)
        return count

    def presigned_url(self, key: str, *, expires_seconds: int = 300) -> str | None:
        """Not supported: a local path must never be handed to a client."""
        return None


class S3ArtifactStore(_BaseStore):
    """Production store backed by S3 or an S3-compatible endpoint.

    ``boto3`` is imported lazily so that the domain and application layers, and
    every test that does not touch S3, never load an AWS SDK.

    Server-side encryption is requested on every write. When ``kms_key_id`` is
    set, objects are encrypted with that customer-managed KMS key; otherwise S3
    managed encryption is used. Encryption is never silently omitted.
    """

    def __init__(
        self,
        bucket: str,
        *,
        client: Any = None,
        endpoint_url: str | None = None,
        region_name: str | None = None,
        kms_key_id: str | None = None,
        prefix: str = "",
    ) -> None:
        if not bucket:
            raise StorageError("an S3 bucket name is required")
        self._bucket = bucket
        self._kms_key_id = kms_key_id
        self._prefix = prefix.strip("/")
        self._client = client
        self._endpoint_url = endpoint_url
        self._region_name = region_name
        self._lock = threading.Lock()

    def _s3(self) -> Any:
        """Return the S3 client, creating it on first use."""
        if self._client is None:
            with self._lock:
                if self._client is None:
                    import boto3

                    self._client = boto3.client(
                        "s3",
                        endpoint_url=self._endpoint_url,
                        region_name=self._region_name,
                    )
        return self._client

    def _full_key(self, key: str) -> str:
        """Apply the configured prefix to a validated key."""
        _validate_key(key)
        return f"{self._prefix}/{key}" if self._prefix else key

    def _encryption_args(self) -> dict[str, str]:
        """Return the server-side encryption arguments for a write."""
        if self._kms_key_id:
            return {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": self._kms_key_id}
        return {"ServerSideEncryption": "AES256"}

    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> StoredObject:
        digest = sha256_bytes(data)
        self._s3().put_object(
            Bucket=self._bucket,
            Key=self._full_key(key),
            Body=data,
            ContentType=content_type,
            # Recorded on the object as well as in PostgreSQL, so an operator
            # inspecting the bucket directly can still verify integrity.
            Metadata={**(metadata or {}), "sha256": digest},
            **self._encryption_args(),
        )
        return StoredObject(key=key, sha256=digest, size_bytes=len(data), content_type=content_type)

    def get(self, key: str, *, expected_sha256: str | None = None) -> bytes:
        try:
            response = self._s3().get_object(Bucket=self._bucket, Key=self._full_key(key))
            data: bytes = response["Body"].read()
        except Exception as exc:
            if _is_missing(exc):
                raise ObjectNotFound(key) from exc
            raise StorageError(f"could not read {key}") from exc
        return self._verify(key, data, expected_sha256)

    def open(self, key: str) -> BinaryIO:
        try:
            response = self._s3().get_object(Bucket=self._bucket, Key=self._full_key(key))
            stream: BinaryIO = response["Body"]
        except Exception as exc:
            if _is_missing(exc):
                raise ObjectNotFound(key) from exc
            raise StorageError(f"could not open {key}") from exc
        return stream

    def exists(self, key: str) -> bool:
        try:
            self._s3().head_object(Bucket=self._bucket, Key=self._full_key(key))
            return True
        except Exception as exc:
            if _is_missing(exc):
                return False
            raise StorageError(f"could not stat {key}") from exc

    def delete(self, key: str) -> None:
        try:
            self._s3().delete_object(Bucket=self._bucket, Key=self._full_key(key))
        except Exception as exc:
            if not _is_missing(exc):
                raise StorageError(f"could not delete {key}") from exc

    def presigned_url(self, key: str, *, expires_seconds: int = 300) -> str | None:
        """Return a short-lived download URL.

        Five minutes by default: long enough for a browser to start the download,
        short enough that a URL leaked into a log or a referrer is of little use.
        """
        expires = max(1, min(int(expires_seconds), 3600))
        url: str = self._s3().generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": self._full_key(key)},
            ExpiresIn=expires,
        )
        return url


def _is_missing(exc: BaseException) -> bool:
    """True when a botocore exception means "no such key".

    Matched structurally rather than by importing botocore, so this module stays
    importable without the AWS SDK.
    """
    code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
    return code in {"NoSuchKey", "404", "NotFound"} or exc.__class__.__name__ in {
        "NoSuchKey",
        "ClientError404",
    }
