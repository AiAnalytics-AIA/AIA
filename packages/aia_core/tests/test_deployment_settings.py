"""Build identity and storage settings: the two things every deployed process reads.

A wrong non-null revision, or a store that quietly falls back to memory in a
deployment, is exactly the class of defect ARCHITECTURE.md A5 describes, so each
refusal here has a test naming what it must not become.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from aia_core.infrastructure.build_identity import BuildIdentity, parse_build_sha
from aia_core.infrastructure.storage import (
    FilesystemArtifactStore,
    InMemoryArtifactStore,
    S3ArtifactStore,
)
from aia_core.infrastructure.storage_settings import StorageSettings, build_artifact_store

# --------------------------------------------------------------------------- #
# Build identity
# --------------------------------------------------------------------------- #


def test_a_full_and_an_abbreviated_sha_are_accepted_and_lowercased() -> None:
    assert parse_build_sha("A15BE650937aacaa821db783c7eff6b9ab40cbe9") == (
        "a15be650937aacaa821db783c7eff6b9ab40cbe9"
    )
    assert parse_build_sha("a15be65") == "a15be65"


def test_a_blank_sha_is_none_not_a_placeholder() -> None:
    assert parse_build_sha(None) is None
    assert parse_build_sha("   ") is None
    assert BuildIdentity.from_env({}).sha is None
    assert BuildIdentity.from_env({}).as_record() == {"sha": None, "built_at": None}


@pytest.mark.parametrize("raw", ["develop", "latest", "abc12", "g" * 8, "a15be65 dirty"])
def test_a_malformed_sha_is_refused_rather_than_recorded(raw: str) -> None:
    with pytest.raises(ValueError, match="AIA_BUILD_SHA"):
        parse_build_sha(raw)


def test_identity_is_read_from_the_environment() -> None:
    identity = BuildIdentity.from_env(
        {"AIA_BUILD_SHA": "a15be650937aacaa", "AIA_BUILD_TIME": "2026-09-23T01:00:00Z"}
    )
    assert identity.sha == "a15be650937aacaa"
    assert identity.short_sha == "a15be650937a"
    assert identity.built_at == "2026-09-23T01:00:00Z"


# --------------------------------------------------------------------------- #
# Storage settings
# --------------------------------------------------------------------------- #


def test_default_backend_is_memory() -> None:
    settings = StorageSettings.from_env({})
    assert settings.backend == "memory"
    assert isinstance(build_artifact_store(settings), InMemoryArtifactStore)


def test_filesystem_backend_uses_the_configured_root(tmp_path: Path) -> None:
    settings = StorageSettings.from_env(
        {"AIA_STORAGE_BACKEND": "filesystem", "AIA_STORAGE_ROOT": str(tmp_path / "artifacts")}
    )
    store = build_artifact_store(settings)
    assert isinstance(store, FilesystemArtifactStore)
    store.put("org/a/client/b/study/c/proj/d/rev/1/X/ART-1", b"hello")
    assert (tmp_path / "artifacts").is_dir()


def test_s3_backend_is_built_without_touching_the_aws_sdk() -> None:
    """The client is created on first use, so a misconfigured region or missing
    credentials surface at the first read, not at boot -- and the domain tests
    never load boto3."""
    settings = StorageSettings.from_env(
        {
            "AIA_STORAGE_BACKEND": "S3",
            "AIA_STORAGE_BUCKET": "aia-develop-artifacts",
            "AIA_STORAGE_REGION": "eu-central-1",
            "AIA_STORAGE_PREFIX": "develop",
            "AIA_STORAGE_KMS_KEY_ID": "arn:aws:kms:eu-central-1:1:key/k",
        }
    )
    store = build_artifact_store(settings)
    assert isinstance(store, S3ArtifactStore)
    assert store._client is None
    assert store._prefix == "develop"
    assert store._encryption_args() == {
        "ServerSideEncryption": "aws:kms",
        "SSEKMSKeyId": "arn:aws:kms:eu-central-1:1:key/k",
    }


def test_s3_requires_a_bucket() -> None:
    with pytest.raises(ValueError, match="AIA_STORAGE_BUCKET is required"):
        StorageSettings.from_env({"AIA_STORAGE_BACKEND": "s3"})


def test_an_unknown_backend_is_refused() -> None:
    with pytest.raises(ValueError, match="AIA_STORAGE_BACKEND must be one of"):
        StorageSettings.from_env({"AIA_STORAGE_BACKEND": "minio"})


def test_a_deployment_accepts_only_s3_itself() -> None:
    assert StorageSettings(backend="memory").deployment_problems() == [
        "AIA_STORAGE_BACKEND must be 's3' in a deployed environment, not 'memory'"
    ]
    assert (
        StorageSettings(backend="filesystem")
        .deployment_problems()[0]
        .startswith("AIA_STORAGE_BACKEND must be 's3'")
    )
    problems = StorageSettings(
        backend="s3", bucket="b", endpoint_url="http://minio:9000"
    ).deployment_problems()
    assert any("AIA_STORAGE_REGION is required" in p for p in problems)
    assert any("AIA_STORAGE_ENDPOINT must not be set" in p for p in problems)
    assert (
        StorageSettings(backend="s3", bucket="b", region="eu-central-1").deployment_problems() == []
    )
