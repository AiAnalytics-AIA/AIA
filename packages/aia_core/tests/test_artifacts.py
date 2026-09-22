"""Tests for artifact storage, provenance, reuse and integrity.

Two things are being protected here:

* **Money.** Artifact reuse is what stops an edit to a late stage re-running the
  expensive early ones. A regression costs real provider spend on every save.
* **Truth.** An artifact is a research output. Serving content that may have been
  altered, or a metadata row pointing at a missing object, would present a
  corrupted result as a finding.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.domain.providers import Provider
from aia_core.domain.scope import ScopeDenied, SeparationOfDutiesViolation
from aia_core.infrastructure.artifact_repository import (
    ArtifactNotFound,
    ArtifactRepository,
    ArtifactStatus,
)
from aia_core.infrastructure.repositories import ProjectRepository
from aia_core.infrastructure.storage import (
    FilesystemArtifactStore,
    InMemoryArtifactStore,
    IntegrityError,
    ObjectNotFound,
    StorageError,
    build_storage_key,
    sha256_bytes,
)

FINGERPRINT = "a" * 64
OTHER_FINGERPRINT = "b" * 64


@pytest.fixture
def store() -> InMemoryArtifactStore:
    return InMemoryArtifactStore()


@pytest.fixture
def project(session: Session, scoped: Any) -> Any:
    """A project in the primary study, created by a LEAD."""
    repo = ProjectRepository(session, scoped.scope(user="lead", study="primary"))
    created, _ = repo.create(title="Artifact host", content={"goal": "g"})
    return created


@pytest.fixture
def artifacts(session: Session, scoped: Any, store: InMemoryArtifactStore) -> ArtifactRepository:
    return ArtifactRepository(session, scoped.scope(user="lead", study="primary"), store)


# --------------------------------------------------------------------------- #
# Storage keys
# --------------------------------------------------------------------------- #


def test_storage_key_orders_scope_outermost_first() -> None:
    """The prefix must allow per-client prefix operations.

    Bucket policies, lifecycle rules, per-client metering and "delete everything
    for this client" are all prefix operations. Putting the project first would
    make the last one a full-bucket scan.
    """
    key = build_storage_key(
        organization_id="ORG-1",
        client_id="CLI-1",
        study_id="STU-1",
        project_id="PRJ-1",
        revision=3,
        stage_type="ANALYSIS",
        artifact_id="ART-1",
    )
    assert key == "org/ORG-1/client/CLI-1/study/STU-1/proj/PRJ-1/rev/3/ANALYSIS/ART-1"
    assert key.startswith("org/ORG-1/client/CLI-1/")


@pytest.mark.parametrize(
    "component",
    ["", "has/slash", "../escape"],
)
def test_storage_key_rejects_unsafe_components(component: str) -> None:
    """A key component containing a separator could escape a tenant prefix."""
    with pytest.raises(StorageError):
        build_storage_key(
            organization_id=component,
            client_id="CLI-1",
            study_id="STU-1",
            project_id="PRJ-1",
            revision=1,
            stage_type="BRIEF",
            artifact_id="ART-1",
        )


@pytest.mark.parametrize(
    "key",
    [
        "",
        "/absolute",
        "org/../../etc/passwd",
        "org//double",
        "org/ORG-1/../../escape",
        "a" * 2000,
        "org/ORG 1/key",
    ],
)
def test_stores_reject_unsafe_keys(key: str, store: InMemoryArtifactStore) -> None:
    """Keys also arrive from the database, so they are validated on every use."""
    with pytest.raises(StorageError):
        store.put(key, b"x")
    with pytest.raises(StorageError):
        store.get(key)


def test_filesystem_store_refuses_to_escape_its_root(tmp_path: Any) -> None:
    """A second barrier behind key validation."""
    fs = FilesystemArtifactStore(tmp_path / "artifacts")
    with pytest.raises(StorageError):
        fs.put("../outside", b"x")
    assert not (tmp_path / "outside").exists()


# --------------------------------------------------------------------------- #
# Store semantics, identical across backends
# --------------------------------------------------------------------------- #


@pytest.fixture(params=["memory", "filesystem"])
def any_store(request: Any, tmp_path: Any) -> Any:
    """Each backend, so they are held to the same contract."""
    if request.param == "memory":
        return InMemoryArtifactStore()
    return FilesystemArtifactStore(tmp_path / "store")


def test_round_trip(any_store: Any) -> None:
    """Bytes come back exactly, with the right hash and size."""
    data = b'{"finding": "v\xc3\xbdsledek"}'
    stored = any_store.put("org/O/client/C/study/S/proj/P/rev/1/BRIEF/ART-1", data)

    assert stored.sha256 == sha256_bytes(data)
    assert stored.size_bytes == len(data)
    assert any_store.get(stored.key) == data
    assert any_store.exists(stored.key)


def test_missing_object_raises_rather_than_returning_empty(any_store: Any) -> None:
    """An empty analysis must never be mistaken for a missing one."""
    with pytest.raises(ObjectNotFound):
        any_store.get("org/O/client/C/study/S/proj/P/rev/1/BRIEF/ART-missing")
    assert not any_store.exists("org/O/client/C/study/S/proj/P/rev/1/BRIEF/ART-missing")


def test_hash_verification_detects_tampering(any_store: Any) -> None:
    """A changed object is refused, not served."""
    key = "org/O/client/C/study/S/proj/P/rev/1/BRIEF/ART-1"
    any_store.put(key, b"original")

    with pytest.raises(IntegrityError):
        any_store.get(key, expected_sha256=sha256_bytes(b"different"))

    # The correct hash still reads fine.
    assert any_store.get(key, expected_sha256=sha256_bytes(b"original")) == b"original"


def test_put_is_idempotent_for_identical_content(any_store: Any) -> None:
    """A duplicate queue delivery re-running a step must not be an error."""
    key = "org/O/client/C/study/S/proj/P/rev/1/BRIEF/ART-1"
    first = any_store.put(key, b"payload")
    second = any_store.put(key, b"payload")

    assert first.sha256 == second.sha256
    assert any_store.get(key) == b"payload"


def test_delete_is_idempotent(any_store: Any) -> None:
    """Deleting a missing object is not an error, so a reaper can be simple."""
    key = "org/O/client/C/study/S/proj/P/rev/1/BRIEF/ART-1"
    any_store.put(key, b"x")
    any_store.delete(key)
    any_store.delete(key)
    assert not any_store.exists(key)


def test_streaming_read(any_store: Any) -> None:
    """Large artifacts can be streamed rather than buffered."""
    key = "org/O/client/C/study/S/proj/P/rev/1/BRIEF/ART-1"
    any_store.put(key, b"0123456789")
    with any_store.open(key) as stream:
        assert stream.read() == b"0123456789"


def test_local_stores_issue_no_download_url(any_store: Any) -> None:
    """A local path must never be handed to a client."""
    key = "org/O/client/C/study/S/proj/P/rev/1/BRIEF/ART-1"
    any_store.put(key, b"x")
    assert any_store.presigned_url(key) is None


def test_filesystem_writes_are_atomic(tmp_path: Any) -> None:
    """No temporary file is left behind, so a reader never sees a partial write."""
    fs = FilesystemArtifactStore(tmp_path / "store")
    fs.put("org/O/client/C/study/S/proj/P/rev/1/BRIEF/ART-1", b"payload")

    leftovers = [p.name for p in (tmp_path / "store").rglob("*") if ".tmp" in p.name]
    assert leftovers == []


# --------------------------------------------------------------------------- #
# The repository: provenance
# --------------------------------------------------------------------------- #


def test_put_records_full_provenance(artifacts: ArtifactRepository, project: Any) -> None:
    """Every artifact can answer what produced it, from what, and how."""
    artifact, created = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="DEEP_RESEARCH",
        artifact_type="EVIDENCE_PACK",
        payload={"sources": ["a", "b"]},
        input_fingerprint=FINGERPRINT,
        provider=Provider.CLAUDE_CODE,
        model="sonnet",
        prompt_version="deep-research-v3",
        runtime_version="18.6.6",
        produced_by_job_id="JOB-1",
        metadata={"source_count": 2},
    )

    assert created
    assert artifact.provider is Provider.CLAUDE_CODE
    assert artifact.model == "sonnet"
    assert artifact.prompt_version == "deep-research-v3"
    assert artifact.runtime_version == "18.6.6"
    assert artifact.produced_by_job_id == "JOB-1"
    assert artifact.input_fingerprint == FINGERPRINT
    assert artifact.metadata["source_count"] == 2
    assert artifact.status is ArtifactStatus.VALID
    assert len(artifact.sha256) == 64


def test_artifact_is_associated_with_its_revision(
    artifacts: ArtifactRepository, project: Any
) -> None:
    """Artifacts belong to a revision, so history stays inspectable."""
    artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="BRIEF",
        artifact_type="COMPILED_BRIEF",
        payload={"v": 1},
    )
    artifacts.put_json(
        project_id=project.project_id,
        revision=2,
        stage_type="BRIEF",
        artifact_type="COMPILED_BRIEF",
        payload={"v": 2},
    )

    rev1 = artifacts.list_for_stage(project_id=project.project_id, revision=1, stage_type="BRIEF")
    rev2 = artifacts.list_for_stage(project_id=project.project_id, revision=2, stage_type="BRIEF")

    assert len(rev1) == 1 and len(rev2) == 1
    assert artifacts.read_json(rev1[0].artifact_id) == {"v": 1}
    assert artifacts.read_json(rev2[0].artifact_id) == {"v": 2}


def test_storage_key_embeds_the_scope(
    artifacts: ArtifactRepository, project: Any, scoped: Any
) -> None:
    """The object lands under its client and study prefix."""
    artifact, _ = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="BRIEF",
        artifact_type="COMPILED_BRIEF",
        payload={},
    )
    assert scoped.clients["primary"].client_id in artifact.storage_key
    assert scoped.studies["primary"].study_id in artifact.storage_key


def test_dependencies_form_an_evidence_trace(artifacts: ArtifactRepository, project: Any) -> None:
    """'Which evidence did this rest on' must be a query, not an investigation."""
    evidence, _ = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="DEEP_RESEARCH",
        artifact_type="EVIDENCE_PACK",
        payload={"sources": ["s1"]},
    )
    analysis, _ = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="ANALYSIS",
        artifact_type="ANALYSIS_SEGMENTS",
        payload={"segments": []},
        depends_on=[evidence.artifact_id],
    )

    traced = artifacts.dependencies(analysis.artifact_id)
    assert [a.artifact_id for a in traced] == [evidence.artifact_id]
    assert artifacts.dependencies(evidence.artifact_id) == []


def test_dependency_outside_scope_is_refused(
    session: Session, scoped: Any, store: InMemoryArtifactStore
) -> None:
    """An evidence chain cannot reference another client's artifact."""
    primary_scope = scoped.scope(user="lead", study="primary")
    other_scope = scoped.scope(user="other_lead", study="other_client")

    other_project, _ = ProjectRepository(session, other_scope).create(title="Theirs")
    other_artifacts = ArtifactRepository(session, other_scope, store)
    foreign, _ = other_artifacts.put_json(
        project_id=other_project.project_id,
        revision=1,
        stage_type="BRIEF",
        artifact_type="COMPILED_BRIEF",
        payload={"secret": True},
    )

    mine, _ = ProjectRepository(session, primary_scope).create(title="Mine")
    my_artifacts = ArtifactRepository(session, primary_scope, store)

    with pytest.raises(ArtifactNotFound):
        my_artifacts.put_json(
            project_id=mine.project_id,
            revision=1,
            stage_type="ANALYSIS",
            artifact_type="ANALYSIS_SEGMENTS",
            payload={},
            depends_on=[foreign.artifact_id],
        )


# --------------------------------------------------------------------------- #
# The repository: reuse
# --------------------------------------------------------------------------- #


def test_matching_fingerprint_reuses_instead_of_storing(
    artifacts: ArtifactRepository, project: Any, store: InMemoryArtifactStore
) -> None:
    """The money-saving path: no upload, no new row, no AI call."""
    first, created_first = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="DEEP_RESEARCH",
        artifact_type="EVIDENCE_PACK",
        payload={"sources": ["a"]},
        input_fingerprint=FINGERPRINT,
    )
    assert created_first
    keys_after_first = len(store.keys)

    second, created_second = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="DEEP_RESEARCH",
        artifact_type="EVIDENCE_PACK",
        payload={"sources": ["totally different"]},
        input_fingerprint=FINGERPRINT,
    )

    assert not created_second
    assert second.artifact_id == first.artifact_id
    assert len(store.keys) == keys_after_first, "nothing should have been uploaded"


def test_reuse_crosses_revisions(artifacts: ArtifactRepository, project: Any) -> None:
    """This is the whole point of the durability model.

    Editing a late stage creates a new revision; the early stages' artifacts live
    on the previous one and must still be found.
    """
    original, _ = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="DEEP_RESEARCH",
        artifact_type="EVIDENCE_PACK",
        payload={"sources": ["a"]},
        input_fingerprint=FINGERPRINT,
    )

    found = artifacts.find_reusable(
        project_id=project.project_id,
        stage_type="DEEP_RESEARCH",
        artifact_type="EVIDENCE_PACK",
        input_fingerprint=FINGERPRINT,
    )
    assert found is not None
    assert found.artifact_id == original.artifact_id
    assert found.revision == 1


def test_different_fingerprint_does_not_reuse(artifacts: ArtifactRepository, project: Any) -> None:
    """Changed inputs must produce new work."""
    first, _ = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="DEEP_RESEARCH",
        artifact_type="EVIDENCE_PACK",
        payload={"v": 1},
        input_fingerprint=FINGERPRINT,
    )
    second, created = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="DEEP_RESEARCH",
        artifact_type="EVIDENCE_PACK",
        payload={"v": 2},
        input_fingerprint=OTHER_FINGERPRINT,
    )

    assert created
    assert second.artifact_id != first.artifact_id


def test_blank_fingerprint_never_reuses(artifacts: ArtifactRepository, project: Any) -> None:
    """A stage whose fingerprint could not be computed must recompute.

    Otherwise every such stage would collide on the empty string and reuse an
    unrelated artifact.
    """
    first, _ = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="BRIEF",
        artifact_type="COMPILED_BRIEF",
        payload={"v": 1},
        input_fingerprint="",
    )
    second, created = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="BRIEF",
        artifact_type="COMPILED_BRIEF",
        payload={"v": 2},
        input_fingerprint="",
    )

    assert created
    assert second.artifact_id != first.artifact_id
    assert (
        artifacts.find_reusable(
            project_id=project.project_id,
            stage_type="BRIEF",
            artifact_type="COMPILED_BRIEF",
            input_fingerprint="",
        )
        is None
    )


def test_reuse_is_scoped_to_stage_and_type(artifacts: ArtifactRepository, project: Any) -> None:
    """The same fingerprint on a different stage or type must not match."""
    artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="DEEP_RESEARCH",
        artifact_type="EVIDENCE_PACK",
        payload={},
        input_fingerprint=FINGERPRINT,
    )

    assert (
        artifacts.find_reusable(
            project_id=project.project_id,
            stage_type="ANALYSIS",
            artifact_type="EVIDENCE_PACK",
            input_fingerprint=FINGERPRINT,
        )
        is None
    )
    assert (
        artifacts.find_reusable(
            project_id=project.project_id,
            stage_type="DEEP_RESEARCH",
            artifact_type="SOMETHING_ELSE",
            input_fingerprint=FINGERPRINT,
        )
        is None
    )


def test_invalidated_artifact_is_not_reused(artifacts: ArtifactRepository, project: Any) -> None:
    """Only a VALID artifact may satisfy a reuse check."""
    artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="DEEP_RESEARCH",
        artifact_type="EVIDENCE_PACK",
        payload={},
        input_fingerprint=FINGERPRINT,
    )
    assert (
        artifacts.invalidate_stage(
            project_id=project.project_id, revision=1, stage_type="DEEP_RESEARCH"
        )
        == 1
    )

    assert (
        artifacts.find_reusable(
            project_id=project.project_id,
            stage_type="DEEP_RESEARCH",
            artifact_type="EVIDENCE_PACK",
            input_fingerprint=FINGERPRINT,
        )
        is None
    )


def test_reuse_check_detects_a_missing_object(
    artifacts: ArtifactRepository, project: Any, store: InMemoryArtifactStore
) -> None:
    """A row claiming an object exists must be verified before trusting it.

    Otherwise an expensive recomputation would be skipped on the strength of a
    row pointing at nothing, and the stage would be declared complete.
    """
    artifact, _ = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="DEEP_RESEARCH",
        artifact_type="EVIDENCE_PACK",
        payload={},
        input_fingerprint=FINGERPRINT,
    )
    store.delete(artifact.storage_key)

    assert (
        artifacts.find_reusable(
            project_id=project.project_id,
            stage_type="DEEP_RESEARCH",
            artifact_type="EVIDENCE_PACK",
            input_fingerprint=FINGERPRINT,
        )
        is None
    )
    assert artifacts.get(artifact.artifact_id).status is ArtifactStatus.CORRUPT


def test_canonical_json_makes_equal_payloads_deduplicate(
    artifacts: ArtifactRepository, project: Any
) -> None:
    """Key order must not defeat content hashing."""
    a, _ = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="BRIEF",
        artifact_type="COMPILED_BRIEF",
        payload={"x": 1, "y": 2},
    )
    b, _ = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="BRIEF",
        artifact_type="COMPILED_BRIEF",
        payload={"y": 2, "x": 1},
    )
    assert a.sha256 == b.sha256


# --------------------------------------------------------------------------- #
# Integrity on read
# --------------------------------------------------------------------------- #


def test_corrupted_content_is_refused_and_flagged(
    artifacts: ArtifactRepository, project: Any, store: InMemoryArtifactStore
) -> None:
    """Serving altered content as a research finding is worse than failing."""
    artifact, _ = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="ANALYSIS",
        artifact_type="ANALYSIS_SEGMENTS",
        payload={"segments": ["real"]},
    )

    store.put(artifact.storage_key, b'{"segments": ["tampered"]}')

    with pytest.raises(IntegrityError):
        artifacts.read(artifact.artifact_id)
    assert artifacts.get(artifact.artifact_id).status is ArtifactStatus.CORRUPT


def test_missing_object_on_read_is_flagged(
    artifacts: ArtifactRepository, project: Any, store: InMemoryArtifactStore
) -> None:
    """A vanished object marks the artifact corrupt rather than returning nothing."""
    artifact, _ = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="BRIEF",
        artifact_type="COMPILED_BRIEF",
        payload={},
    )
    store.delete(artifact.storage_key)

    with pytest.raises(ObjectNotFound):
        artifacts.read(artifact.artifact_id)
    assert artifacts.get(artifact.artifact_id).status is ArtifactStatus.CORRUPT


def test_verify_all_reports_corruption(
    artifacts: ArtifactRepository, project: Any, store: InMemoryArtifactStore
) -> None:
    """An operator integrity sweep distinguishes healthy from corrupt."""
    good, _ = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="BRIEF",
        artifact_type="COMPILED_BRIEF",
        payload={"ok": True},
    )
    bad, _ = artifacts.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="ANALYSIS",
        artifact_type="ANALYSIS_SEGMENTS",
        payload={"ok": True},
    )
    store.put(bad.storage_key, b"tampered")

    result = artifacts.verify_all(project_id=project.project_id)
    assert result["valid"] == [good.artifact_id]
    assert result["corrupt"] == [bad.artifact_id]


# --------------------------------------------------------------------------- #
# Scope and permissions
# --------------------------------------------------------------------------- #


def test_artifact_repository_requires_a_study_context(
    session: Session, store: InMemoryArtifactStore
) -> None:
    """Unscoped artifact access is not constructible."""
    for bogus in (None, "ORG-1", {"study_id": "STU-1"}):
        with pytest.raises(TypeError, match="requires a StudyContext"):
            ArtifactRepository(session, bogus, store)  # type: ignore[arg-type]


def test_artifacts_are_invisible_across_clients(
    session: Session, scoped: Any, store: InMemoryArtifactStore
) -> None:
    """An artifact is never addressable by id alone."""
    primary_scope = scoped.scope(user="lead", study="primary")
    project, _ = ProjectRepository(session, primary_scope).create(title="Mine")
    artifact, _ = ArtifactRepository(session, primary_scope, store).put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="BRIEF",
        artifact_type="COMPILED_BRIEF",
        payload={"secret": "client confidential"},
    )

    other = ArtifactRepository(
        session, scoped.scope(user="other_lead", study="other_client"), store
    )
    with pytest.raises(ArtifactNotFound):
        other.get(artifact.artifact_id)
    with pytest.raises(ArtifactNotFound):
        other.read(artifact.artifact_id)
    with pytest.raises(ArtifactNotFound):
        other.dependencies(artifact.artifact_id)


def test_reviewer_cannot_write_artifacts(
    session: Session, scoped: Any, store: InMemoryArtifactStore, project: Any
) -> None:
    """Writing an artifact is doing the work, which a reviewer does not do."""
    reviewer = ArtifactRepository(session, scoped.scope(user="reviewer", study="primary"), store)
    with pytest.raises(ScopeDenied) as exc:
        reviewer.put_json(
            project_id=project.project_id,
            revision=1,
            stage_type="BRIEF",
            artifact_type="COMPILED_BRIEF",
            payload={},
        )
    assert exc.value.reason == "insufficient_role"


def test_researcher_cannot_sign_off_their_own_artifact(
    session: Session, scoped: Any, store: InMemoryArtifactStore, project: Any
) -> None:
    """The human gate is meaningless if the author can clear it."""
    researcher = ArtifactRepository(
        session, scoped.scope(user="researcher", study="primary"), store
    )
    artifact, _ = researcher.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="REPORT",
        artifact_type="CLIENT_REPORT",
        payload={"draft": True},
    )

    with pytest.raises(ScopeDenied):
        researcher.approve(artifact.artifact_id)

    reviewer = ArtifactRepository(session, scoped.scope(user="reviewer", study="primary"), store)
    assert reviewer.approve(artifact.artifact_id).is_approved


def test_download_url_requires_export_authority(
    session: Session, scoped: Any, store: InMemoryArtifactStore, project: Any
) -> None:
    """Handing out a URL is handing out the content, so it is gated like export."""
    researcher = ArtifactRepository(
        session, scoped.scope(user="researcher", study="primary"), store
    )
    artifact, _ = researcher.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="REPORT",
        artifact_type="CLIENT_REPORT",
        payload={},
    )
    # In-memory issues no URL, but the permission check must still have run.
    assert researcher.download_url(artifact.artifact_id) is None

    viewer = ArtifactRepository(session, scoped.scope(user="viewer", study="primary"), store)
    with pytest.raises(ScopeDenied):
        viewer.download_url(artifact.artifact_id)


# --------------------------------------------------------------------------- #
# Freeze and delete
# --------------------------------------------------------------------------- #


def test_frozen_artifact_survives_stage_invalidation(
    session: Session, scoped: Any, store: InMemoryArtifactStore, project: Any
) -> None:
    """A deliverable a client has seen is not invalidated by a later edit."""
    lead = ArtifactRepository(session, scoped.scope(user="lead", study="primary"), store)
    frozen, _ = lead.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="REPORT",
        artifact_type="CLIENT_REPORT",
        payload={"delivered": True},
    )
    live, _ = lead.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="REPORT",
        artifact_type="DRAFT_REPORT",
        payload={"draft": True},
    )
    lead.freeze(frozen.artifact_id)

    invalidated = lead.invalidate_stage(
        project_id=project.project_id, revision=1, stage_type="REPORT"
    )

    assert invalidated == 1
    assert lead.get(frozen.artifact_id).status is ArtifactStatus.VALID
    assert lead.get(live.artifact_id).status is ArtifactStatus.INVALIDATED


def test_frozen_artifact_cannot_be_deleted(
    session: Session, scoped: Any, store: InMemoryArtifactStore, project: Any
) -> None:
    """Delivered work must not disappear."""
    lead = ArtifactRepository(session, scoped.scope(user="lead", study="primary"), store)
    artifact, _ = lead.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="REPORT",
        artifact_type="CLIENT_REPORT",
        payload={},
    )
    lead.freeze(artifact.artifact_id)

    with pytest.raises(ScopeDenied) as exc:
        lead.delete(artifact.artifact_id)
    assert exc.value.reason == "artifact_frozen"


def test_delete_removes_row_and_object(
    session: Session, scoped: Any, store: InMemoryArtifactStore, project: Any
) -> None:
    """Both halves go, and the row goes first."""
    lead = ArtifactRepository(session, scoped.scope(user="lead", study="primary"), store)
    artifact, _ = lead.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="BRIEF",
        artifact_type="COMPILED_BRIEF",
        payload={},
    )
    key = artifact.storage_key

    lead.delete(artifact.artifact_id)

    assert not store.exists(key)
    with pytest.raises(ArtifactNotFound):
        lead.get(artifact.artifact_id)


# --------------------------------------------------------------------------- #
# Separation of duties -- a permanent invariant
# --------------------------------------------------------------------------- #


def test_regression_producer_cannot_approve_their_own_artifact(
    session: Session, scoped: Any, store: InMemoryArtifactStore, project: Any
) -> None:
    """**producer_user_id != approving_user_id. Never relax this.**

    A role check alone is insufficient: a LEAD holds both EDIT_STUDY and
    SIGN_OFF_DELIVERABLE, so without this invariant one person could author a
    deliverable and then clear its own review gate by switching hats.

    The methodology's human review gate requires *independence*, not merely a
    permission. This test exists forever.
    """
    lead_scope = scoped.scope(user="lead", study="primary")
    lead = ArtifactRepository(session, lead_scope, store)

    artifact, _ = lead.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="REPORT",
        artifact_type="CLIENT_REPORT",
        payload={"draft": True},
    )
    assert artifact.produced_by_user_id == lead_scope.actor_id

    with pytest.raises(SeparationOfDutiesViolation) as exc:
        lead.approve(artifact.artifact_id)
    assert exc.value.reason == "separation_of_duties"
    assert lead.get(artifact.artifact_id).is_approved is False


def test_a_different_person_with_sign_off_authority_can_approve(
    session: Session, scoped: Any, store: InMemoryArtifactStore, project: Any
) -> None:
    """Independence satisfied: a reviewer who did not author it may approve."""
    researcher = ArtifactRepository(
        session, scoped.scope(user="researcher", study="primary"), store
    )
    artifact, _ = researcher.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="REPORT",
        artifact_type="CLIENT_REPORT",
        payload={"draft": True},
    )

    reviewer = ArtifactRepository(session, scoped.scope(user="reviewer", study="primary"), store)
    assert reviewer.approve(artifact.artifact_id).is_approved is True


def test_producer_is_taken_from_scope_not_from_an_argument(
    session: Session, scoped: Any, store: InMemoryArtifactStore, project: Any
) -> None:
    """The producer cannot be spoofed to defeat the independence check.

    ``produced_by_user_id`` comes from the authorised scope. A caller -- or an AI
    tool -- cannot claim someone else produced the work in order to approve it
    themselves.
    """
    lead_scope = scoped.scope(user="lead", study="primary")
    lead = ArtifactRepository(session, lead_scope, store)

    with pytest.raises(TypeError):
        lead.put_json(  # type: ignore[call-arg]
            project_id=project.project_id,
            revision=1,
            stage_type="REPORT",
            artifact_type="CLIENT_REPORT",
            payload={},
            produced_by_user_id="USR-someone-else",
        )


def test_an_artifact_with_no_recorded_producer_can_still_be_approved(
    session: Session, scoped: Any, store: InMemoryArtifactStore, project: Any
) -> None:
    """Unknown provenance does not block approval, but it is visible.

    A gate with no recorded producer predates provenance; blocking it would
    strand existing work. The check is only as strong as the provenance feeding
    it, which is why every write records a producer.
    """
    from aia_core.infrastructure.tables import ProjectArtifactRow

    lead_scope = scoped.scope(user="lead", study="primary")
    lead = ArtifactRepository(session, lead_scope, store)
    artifact, _ = lead.put_json(
        project_id=project.project_id,
        revision=1,
        stage_type="REPORT",
        artifact_type="CLIENT_REPORT",
        payload={},
    )

    row = session.get(ProjectArtifactRow, artifact.artifact_id)
    assert row is not None
    row.produced_by_user_id = None
    session.flush()

    assert lead.approve(artifact.artifact_id).is_approved is True
