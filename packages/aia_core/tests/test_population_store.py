"""The population store: a child written once to S3, read back by the loader (P4d1).

Over a stand-in S3 client that keeps S3's own rules for what these calls depend on: a
conditional put (``IfNoneMatch="*"``) fails with ``PreconditionFailed`` when the key exists,
and a missing key is ``NoSuchKey``. The errors are shaped as botocore's are (``.response``),
so the store matches them as it would the real client's. No network.
"""

from __future__ import annotations

import io
from typing import Any

import pytest

from aia_core.infrastructure.population_source import (
    InMemoryPopulationSource,
    PopulationAssetMissing,
)
from aia_core.infrastructure.population_store import (
    PopulationStoreConflict,
    PopulationStoreError,
    PopulationStoreSettings,
    RoutingPopulationSource,
    S3PopulationStore,
)

BUCKET = "aia-develop-population-000000000000"


class FakeClientError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.response = {"Error": {"Code": code}}


class FakeS3:
    """The calls the store makes, with S3's semantics for each."""

    def __init__(self, *, fail_with: str | None = None) -> None:
        self.objects: dict[tuple[str, str], dict[str, Any]] = {}
        self.puts: list[dict[str, Any]] = []
        self._fail_with = fail_with

    def put_object(self, **kw: Any) -> dict[str, Any]:
        self.puts.append(kw)
        if self._fail_with:
            raise FakeClientError(self._fail_with)
        key = (kw["Bucket"], kw["Key"])
        if kw.get("IfNoneMatch") == "*" and key in self.objects:
            raise FakeClientError("PreconditionFailed")
        self.objects[key] = kw
        return {}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:  # noqa: N803 - boto3's names
        if (Bucket, Key) not in self.objects:
            raise FakeClientError("NoSuchKey")
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)]["Body"])}


def store(client: FakeS3) -> S3PopulationStore:
    return S3PopulationStore(BUCKET, region_name="eu-central-1", client=client)


def test_a_child_is_written_once_encrypted_under_its_prefix_and_reads_back() -> None:
    s3 = FakeS3()
    location = store(s3).put_once("cz/child-1.csv.gz", b"panel bytes")
    assert location == f"s3://{BUCKET}/materialized/cz/child-1.csv.gz"
    put = s3.puts[0]
    assert put["Key"] == "materialized/cz/child-1.csv.gz"
    assert put["IfNoneMatch"] == "*" and put["ServerSideEncryption"] == "AES256"
    assert put["Metadata"]["sha256"] == (
        "5ae28589eaa7c939d9cafd27aab744e5972322f18d195085b66197ad00b270d6"
    )
    assert store(s3).read(location) == b"panel bytes"


def test_the_same_bytes_again_are_the_same_child_and_other_bytes_are_never_written() -> None:
    s3 = FakeS3()
    first = store(s3).put_once("child.csv.gz", b"panel bytes")
    assert store(s3).put_once("child.csv.gz", b"panel bytes") == first  # a retried step
    with pytest.raises(PopulationStoreConflict):
        store(s3).put_once("child.csv.gz", b"other bytes")
    assert store(s3).read(first) == b"panel bytes"  # never replaced


def test_a_key_outside_the_store_or_a_location_of_another_bucket_is_refused() -> None:
    s3 = FakeS3()
    for key in ("../escape", "/abs", "Upper.csv", "a//b", ""):
        with pytest.raises(PopulationStoreError):
            store(s3).put_once(key, b"x")
    assert s3.puts == []
    with pytest.raises(PopulationAssetMissing):
        store(s3).read("s3://another-bucket/materialized/child.csv.gz")
    with pytest.raises(PopulationAssetMissing):
        store(s3).read(f"s3://{BUCKET}/elsewhere/child.csv.gz")
    with pytest.raises(PopulationStoreError, match="never empty"):
        store(s3).put_once("empty.csv.gz", b"")


def test_a_missing_object_is_missing_and_any_other_failure_is_an_error() -> None:
    with pytest.raises(PopulationAssetMissing):
        store(FakeS3()).read(f"s3://{BUCKET}/materialized/none.csv.gz")
    with pytest.raises(PopulationStoreError, match="could not write") as failed:
        store(FakeS3(fail_with="AccessDenied")).put_once("child.csv.gz", b"x")
    assert not isinstance(failed.value, PopulationStoreConflict)


def test_the_loaders_source_reads_a_shared_version_as_before_and_a_child_from_the_store() -> None:
    s3 = FakeS3()
    location = store(s3).put_once("child.csv.gz", b"child")
    shared = InMemoryPopulationSource({"panels/v1.csv.gz": b"shared"})
    source = RoutingPopulationSource(shared, store(s3))
    assert source.read("panels/v1.csv.gz") == b"shared"
    assert source.read(location) == b"child"
    without = RoutingPopulationSource(shared)
    with pytest.raises(PopulationAssetMissing, match="none is configured"):
        without.read(location)


def test_the_settings_are_both_keys_or_neither() -> None:
    assert PopulationStoreSettings.from_env({}) is None
    settings = PopulationStoreSettings.from_env(
        {"AIA_POPULATION_STORE_BUCKET": BUCKET, "AIA_POPULATION_STORE_REGION": "eu-central-1"}
    )
    assert settings == PopulationStoreSettings(BUCKET, "eu-central-1")
    for half in ({"AIA_POPULATION_STORE_BUCKET": BUCKET}, {"AIA_POPULATION_STORE_REGION": "x"}):
        with pytest.raises(PopulationStoreError, match="together"):
            PopulationStoreSettings.from_env(half)
