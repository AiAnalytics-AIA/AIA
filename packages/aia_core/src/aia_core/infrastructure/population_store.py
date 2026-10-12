"""The population store: materialized children in EU S3 (population-operations P4d1).

A materialized child (P4, M1) is its base's panel plus the added columns, owned by one
organization (M5). Its bytes cannot live beside the shared versions: those are a read-only
copy the develop host syncs (``deploy/develop/bin/sync-population.sh``), and nothing in AIA
writes there. The owner chose S3 (2026-10-12). This module is that store and nothing more:

* :class:`S3PopulationStore` writes an object **once**. ``put_once`` sends a conditional put
  (``If-None-Match: *``), so a second writer cannot replace the first; an object already at
  the key with the same SHA256 is the same child (a retried step), and one with other bytes
  is refused (:class:`PopulationStoreConflict`), never overwritten. It reads only through
  ``read``, which the loader verifies against the registered hash as it does every source.
* :class:`RoutingPopulationSource` is the one :class:`PopulationAssetSource` a loader is
  given: an ``s3://`` location reads from the store, any other from the shared source, so a
  shared version reads exactly as it did.
* :class:`PopulationStoreSettings` reads ``AIA_POPULATION_STORE_BUCKET`` and
  ``AIA_POPULATION_STORE_REGION``: both set, or neither (no store); one alone does not start.

Credentials are never read here: ``boto3`` resolves the instance role, as the artifact store
does (``storage_settings.py``). The client is built on first use by ``storage.s3_client``, the one
place the AWS SDK is imported.
"""

from __future__ import annotations

import hashlib
import re
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final

from aia_core.domain.population import PopulationError

from .population_source import PopulationAssetMissing, PopulationAssetSource
from .storage import s3_client

__all__ = [
    "MATERIALIZED_PREFIX",
    "PopulationStoreConflict",
    "PopulationStoreError",
    "PopulationStoreSettings",
    "RoutingPopulationSource",
    "S3PopulationStore",
]

#: Every object the store writes is under this prefix; the instance role may write nowhere else.
MATERIALIZED_PREFIX: Final = "materialized"

BUCKET_KEY: Final = "AIA_POPULATION_STORE_BUCKET"
REGION_KEY: Final = "AIA_POPULATION_STORE_REGION"

_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]*(/[a-z0-9][a-z0-9._-]*)*$")
_SCHEME = "s3://"


class PopulationStoreError(PopulationError):
    """The store could not do what was asked; nothing was substituted."""

    reason = "population_store_error"


class PopulationStoreConflict(PopulationStoreError):
    """Other bytes are already at the key. A child is written once and never replaced."""

    reason = "population_store_conflict"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _error_code(exc: BaseException) -> str:
    """The S3 error code of a botocore ``ClientError``, matched structurally."""
    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return ""
    error = response.get("Error")
    return str(error.get("Code", "")) if isinstance(error, Mapping) else ""


_MISSING: Final = frozenset({"NoSuchKey", "404", "NotFound"})
# 412 when the key exists; 409 when a concurrent conditional write to it is in flight.
_EXISTS: Final = frozenset({"PreconditionFailed", "412", "ConditionalRequestConflict", "409"})


class S3PopulationStore:
    """Materialized children in one bucket, under :data:`MATERIALIZED_PREFIX`."""

    def __init__(self, bucket: str, *, region_name: str, client: Any = None) -> None:
        if not bucket or not region_name:
            raise PopulationStoreError("the population store names its bucket and its region")
        self._bucket = bucket
        self._region_name = region_name
        self._client = client
        self._lock = threading.Lock()

    @property
    def bucket(self) -> str:
        return self._bucket

    def _s3(self) -> Any:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = s3_client(region_name=self._region_name)
        return self._client

    def location(self, key: str) -> str:
        """The registered location of ``key``: ``s3://<bucket>/materialized/<key>``."""
        return f"{_SCHEME}{self._bucket}/{self._object_key(key)}"

    def _object_key(self, key: str) -> str:
        if not _KEY.match(key) or ".." in key.split("/"):
            raise PopulationStoreError(f"not a population store key: {key!r}")
        return f"{MATERIALIZED_PREFIX}/{key}"

    def _key_of(self, location: str) -> str:
        """The object key a location names; refused unless it is this store's own."""
        prefix = f"{_SCHEME}{self._bucket}/{MATERIALIZED_PREFIX}/"
        if not location.startswith(prefix):
            raise PopulationAssetMissing(f"{location} is not in this population store")
        return self._object_key(location[len(prefix) :])

    def put_once(self, key: str, data: bytes) -> str:
        """Write ``data`` at ``key`` unless something is already there; return its location.

        The same bytes already at the key answer as written (a retried step). Other bytes are
        :class:`PopulationStoreConflict`: the object is never replaced.
        """
        if not data:
            raise PopulationStoreError("a population object is never empty")
        object_key = self._object_key(key)
        digest = _sha256(data)
        try:
            self._s3().put_object(
                Bucket=self._bucket,
                Key=object_key,
                Body=data,
                IfNoneMatch="*",
                ContentType="application/gzip",
                Metadata={"sha256": digest},
                ServerSideEncryption="AES256",
            )
        except Exception as exc:
            if _error_code(exc) not in _EXISTS:
                raise PopulationStoreError(f"could not write {object_key}") from exc
            existing = self._get(object_key)
            if _sha256(existing) != digest:
                raise PopulationStoreConflict(
                    f"{object_key} already holds other bytes; a child is never replaced"
                ) from None
        return self.location(key)

    def read(self, location: str) -> bytes:
        """The bytes at a location this store wrote; :class:`PopulationAssetMissing` if none."""
        return self._get(self._key_of(location))

    def _get(self, object_key: str) -> bytes:
        try:
            response = self._s3().get_object(Bucket=self._bucket, Key=object_key)
            body: bytes = response["Body"].read()
        except Exception as exc:
            if _error_code(exc) in _MISSING:
                raise PopulationAssetMissing(f"no population object at {object_key}") from exc
            raise PopulationStoreError(f"could not read {object_key}") from exc
        return body


class RoutingPopulationSource:
    """The loader's one source: ``s3://`` from the store, anything else from the shared one."""

    def __init__(
        self, shared: PopulationAssetSource, store: S3PopulationStore | None = None
    ) -> None:
        self._shared = shared
        self._store = store

    def read(self, location: str) -> bytes:
        if location.startswith(_SCHEME):
            if self._store is None:
                raise PopulationAssetMissing(
                    f"{location} is in the population store, and none is configured"
                )
            return self._store.read(location)
        return self._shared.read(location)


@dataclass(frozen=True, slots=True)
class PopulationStoreSettings:
    """Where the population store is: one bucket in one region."""

    bucket: str
    region: str

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> PopulationStoreSettings | None:
        """Both keys, or neither (no store). One alone is a configuration error."""
        bucket = (env.get(BUCKET_KEY) or "").strip()
        region = (env.get(REGION_KEY) or "").strip()
        if not bucket and not region:
            return None
        if not bucket or not region:
            raise PopulationStoreError(
                f"{BUCKET_KEY} and {REGION_KEY} are set together, or not at all"
            )
        return cls(bucket=bucket, region=region)

    def build(self, *, client: Any = None) -> S3PopulationStore:
        return S3PopulationStore(self.bucket, region_name=self.region, client=client)
