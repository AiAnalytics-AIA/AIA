"""A run's report opened in the editor: its lines, the line that opens and the session's key
(artifact-report RPT8c)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from aia_core.application.contextual_report import CONTEXT_REPORT_ARTIFACT_TYPE
from aia_core.application.report import INTERNAL_REPORT_ARTIFACT_TYPE
from aia_core.application.report_editor import LineNotFound, NotEditable, ReportEditor
from aia_core.application.research import research_artifacts
from aia_core.domain.report.editor import (
    EDIT_ARTIFACT_TYPES,
    KEY,
    SESSION_IDLE,
    CallbackAction,
    LineHead,
    SessionState,
    callback_action,
    default_line,
    document_key,
    reuse_session,
)
from aia_core.infrastructure.artifact_repository import Artifact
from aia_core.infrastructure.report_editor_repository import (
    ReportEditorRepository,
    session_by_key,
)
from aia_core.infrastructure.storage import InMemoryArtifactStore
from aia_core.infrastructure.study_design_repository import StudyDesignRepository

T0 = datetime(2026, 10, 23, 8, 0, tzinfo=UTC)
SHA = "a" * 64


# -- the rules ---------------------------------------------------------------


def test_a_key_names_the_line_the_version_and_the_session_within_onlyoffices_grammar() -> None:
    key = document_key("ART-0123456789abcdef", SHA, 3)
    assert key == f"ART-0123456789abcdef.{'a' * 40}.3" and KEY.fullmatch(key)
    assert document_key("ART-0123456789abcdef", SHA, 4) != key
    for bad in (("ART-1", "short", 1), ("ART-1", SHA, 0), ("ART 1", SHA, 1)):
        with pytest.raises(ValueError):
            document_key(*bad)


def test_every_onlyoffice_status_has_one_action_and_no_other_is_read() -> None:
    assert [callback_action(s) for s in (1, 2, 3, 4, 6, 7)] == [
        CallbackAction.OPEN,
        CallbackAction.STORE_AND_CLOSE,
        CallbackAction.LOG,
        CallbackAction.CLOSE,
        CallbackAction.STORE,
        CallbackAction.LOG,
    ]
    with pytest.raises(ValueError):
        callback_action(5)


def test_an_open_session_is_joined_until_a_day_passes_with_nothing_from_it() -> None:
    open_ = SessionState("k", 1, T0)
    assert reuse_session(open_, T0 + SESSION_IDLE - timedelta(seconds=1))
    assert not reuse_session(open_, T0 + SESSION_IDLE)
    assert not reuse_session(SessionState("k", 1, T0, closed_at=T0), T0)
    assert not reuse_session(None, T0)


def test_the_line_with_the_newest_version_opens_whatever_the_order_read() -> None:
    old = LineHead("ART-a", 4, "v4", T0)
    new = LineHead("ART-b", 1, "v1", T0 + timedelta(minutes=1))
    assert default_line([old, new]) == default_line([new, old]) == new
    assert default_line([]) is None


# -- the lines and sessions, stored ------------------------------------------


@pytest.fixture
def editor_world(session: Any, scoped: Any) -> Any:
    scope = scoped.scope()
    store = InMemoryArtifactStore()
    designs = StudyDesignRepository(session, scope)
    revision, _ = designs.submit_as_working_copy(
        content={"title": "Ranní nápoj", "n": 200}, source_stage="run"
    )
    project_id = designs.project_id()
    artifacts = research_artifacts(session, scope, store)

    def compose(run_id: str = "RUN-1", data: bytes = b"koncept", **meta: Any) -> Artifact:
        artifact, _ = artifacts.put(
            project_id=project_id,
            revision=revision.revision,
            stage_type="REPORT",
            artifact_type=meta.pop("artifact_type", INTERNAL_REPORT_ARTIFACT_TYPE),
            data=data,
            metadata={"run_id": run_id, "report_kind": "internal", **meta},
            reuse=False,
        )
        return artifact

    def save(line: str, koncept: int, data: bytes, at: datetime) -> str:
        """A later version of ``line``, as the callback's chunk will store one."""
        artifact, _ = artifacts.put(
            project_id=project_id,
            revision=revision.revision,
            stage_type="REPORT",
            artifact_type=EDIT_ARTIFACT_TYPES["internal"],
            data=data,
            metadata={"run_id": "RUN-1", "line_id": line, "koncept": koncept},
            reuse=False,
        )
        ReportEditorRepository(session, scope).add_version(
            artifact_id=artifact.artifact_id,
            line_id=line,
            koncept=koncept,
            run_id="RUN-1",
            variant="internal",
            deep_research_run_id=None,
            sha256=artifact.sha256,
            saved_at=at,
        )
        return artifact.artifact_id

    class World:
        pass

    world = World()
    world.session, world.scoped, world.scope = session, scoped, scope  # type: ignore[attr-defined]
    world.compose, world.save = compose, save  # type: ignore[attr-defined]
    world.store = store  # type: ignore[attr-defined]
    world.editor = ReportEditor(session, scope)  # type: ignore[attr-defined]
    return world


def test_a_first_open_starts_the_line_and_a_session_on_koncept_1(editor_world: Any) -> None:
    composed = editor_world.compose()
    opened = editor_world.editor.open(composed, run_id="RUN-1", variant="internal", now=T0)
    assert opened.line_id == composed.artifact_id and opened.started
    assert opened.version.koncept == 1 and opened.version.artifact_id == composed.artifact_id
    assert opened.session.document_key == document_key(composed.artifact_id, composed.sha256, 1)
    found = session_by_key(editor_world.session, opened.session.document_key)
    assert found is not None and found.study_id == editor_world.scope.study_id


def test_a_second_researcher_joins_the_open_session_under_the_same_key(editor_world: Any) -> None:
    composed = editor_world.compose()
    first = editor_world.editor.open(composed, run_id="RUN-1", variant="internal", now=T0)
    other = editor_world.scoped.scope(user="other_lead")
    later = T0 + timedelta(hours=1)
    second = ReportEditor(editor_world.session, other).open(
        composed, run_id="RUN-1", variant="internal", now=later
    )
    assert not second.started
    assert second.session.document_key == first.session.document_key
    assert set(second.session.users) == {editor_world.scope.actor_id, other.actor_id}


def test_after_a_close_the_next_session_opens_on_the_newest_version_with_a_new_key(
    editor_world: Any,
) -> None:
    composed = editor_world.compose()
    first = editor_world.editor.open(composed, run_id="RUN-1", variant="internal", now=T0)
    newest = editor_world.save(composed.artifact_id, 2, b"koncept 2", T0 + timedelta(minutes=5))
    repo = ReportEditorRepository(editor_world.session, editor_world.scope)
    repo.close(first.session.document_key, now=T0 + timedelta(minutes=6), reason="saved")
    second = editor_world.editor.open(
        composed, run_id="RUN-1", variant="internal", now=T0 + timedelta(minutes=7)
    )
    assert second.started and second.session.session_no == 2
    assert second.version.artifact_id == newest and second.version.koncept == 2
    assert second.session.document_key != first.session.document_key


def test_a_session_idle_for_a_day_is_closed_by_the_next_open(editor_world: Any) -> None:
    composed = editor_world.compose()
    first = editor_world.editor.open(composed, run_id="RUN-1", variant="internal", now=T0)
    second = editor_world.editor.open(
        composed, run_id="RUN-1", variant="internal", now=T0 + SESSION_IDLE
    )
    assert second.started and second.session.document_key != first.session.document_key
    repo = ReportEditorRepository(editor_world.session, editor_world.scope)
    closed = repo.session(first.session.document_key)
    assert closed is not None and closed.closed_reason == "idle"


def test_a_recompose_after_an_edit_starts_a_new_line_and_leaves_the_edited_one(
    editor_world: Any,
) -> None:
    """/pmstatus (a): a composition by code is a new line, koncept 1 the composer's; the
    edited line keeps its koncept N, and the newest version, by its stored time, opens."""
    first = editor_world.compose()
    editor_world.editor.open(first, run_id="RUN-1", variant="internal", now=T0)
    later = datetime.now(UTC) + timedelta(hours=1)  # saved after the recompose below
    edited = editor_world.save(first.artifact_id, 2, b"koncept 2", later)
    recomposed = editor_world.compose(data=b"recomposed")
    opened = editor_world.editor.open(recomposed, run_id="RUN-1", variant="internal", now=T0)
    assert opened.line_id == first.artifact_id and opened.version.artifact_id == edited
    heads = {h.line_id: h for h in editor_world.editor.lines(run_id="RUN-1", variant="internal")}
    assert heads[recomposed.artifact_id].koncept == 1
    assert heads[recomposed.artifact_id].version_id == recomposed.artifact_id
    assert heads[first.artifact_id].version_id == edited and heads[first.artifact_id].koncept == 2
    new = editor_world.editor.open(
        recomposed,
        run_id="RUN-1",
        variant="internal",
        line_id=recomposed.artifact_id,
        now=T0 + timedelta(minutes=1),
    )
    assert new.version.artifact_id == recomposed.artifact_id and new.started


def test_a_line_of_another_run_or_variant_is_not_found(editor_world: Any) -> None:
    composed = editor_world.compose()
    other = editor_world.compose(run_id="RUN-2")
    editor_world.editor.start_line(other, run_id="RUN-2", variant="internal")
    with pytest.raises(LineNotFound):
        editor_world.editor.open(
            composed, run_id="RUN-1", variant="internal", line_id=other.artifact_id, now=T0
        )


@pytest.mark.parametrize("variant", ["client", "context"])
def test_the_client_report_and_a_mismatched_draft_do_not_open(
    editor_world: Any, variant: str
) -> None:
    composed = editor_world.compose()
    with pytest.raises(NotEditable):
        editor_world.editor.open(composed, run_id="RUN-1", variant=variant, now=T0)
    with pytest.raises(NotEditable):
        editor_world.editor.open(composed, run_id="RUN-2", variant="internal", now=T0)


def test_the_report_with_literature_opens_as_a_line_of_its_own(editor_world: Any) -> None:
    composed = editor_world.compose(
        artifact_type=CONTEXT_REPORT_ARTIFACT_TYPE, deep_research_run_id="DR-1"
    )
    opened = editor_world.editor.open(
        composed, run_id="RUN-1", variant="context", deep_research_run_id="DR-1", now=T0
    )
    assert opened.version.variant == "context" and opened.version.deep_research_run_id == "DR-1"
    assert editor_world.editor.lines(run_id="RUN-1", variant="internal") == []


def test_another_studys_lines_are_not_read(editor_world: Any) -> None:
    composed = editor_world.compose()
    opened = editor_world.editor.open(composed, run_id="RUN-1", variant="internal", now=T0)
    elsewhere = ReportEditorRepository(
        editor_world.session, editor_world.scoped.scope(study="sibling")
    )
    assert elsewhere.versions(composed.artifact_id) == []
    assert elsewhere.session(opened.session.document_key) is None


def test_a_lines_rows_go_with_its_artifacts(editor_world: Any) -> None:
    """A deleted client's run artifacts take their lines and sessions with them (the rows
    cascade from ``project_artifacts``), so client deletion needs nothing of its own here."""
    from sqlalchemy import delete, func, select

    from aia_core.infrastructure.tables import (
        ProjectArtifactRow,
        ReportEditorSessionRow,
        ReportEditorVersionRow,
    )

    composed = editor_world.compose()
    editor_world.editor.open(composed, run_id="RUN-1", variant="internal", now=T0)
    editor_world.session.execute(
        delete(ProjectArtifactRow).where(ProjectArtifactRow.artifact_id == composed.artifact_id)
    )
    for table in (ReportEditorVersionRow, ReportEditorSessionRow):
        assert editor_world.session.scalar(select(func.count()).select_from(table)) == 0


def test_a_save_not_stored_is_noted_on_the_session_and_cleared_by_the_next(
    editor_world: Any,
) -> None:
    composed = editor_world.compose()
    opened = editor_world.editor.open(composed, run_id="RUN-1", variant="internal", now=T0)
    repo = ReportEditorRepository(editor_world.session, editor_world.scope)
    key = opened.session.document_key
    repo.note_problem(key, now=T0, problem="document_server_restarted")
    noted = repo.session(key)
    assert noted is not None and noted.last_problem == "document_server_restarted"
    assert noted.last_problem_at == T0
    repo.note_problem(key, now=T0, problem=None)
    cleared = repo.session(key)
    assert cleared is not None and cleared.last_problem is None and cleared.last_problem_at is None


def test_two_first_opens_of_a_new_line_meet_in_one_session(
    editor_world: Any, engine: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two researchers open a freshly composed report at once. The first is held after it
    started the line, holding its lock; the second must wait for it, then join its session,
    never insert koncept 1 again (an IntegrityError, a 500).

    PostgreSQL only: the guard is a row lock, which SQLite does not take (it serialises
    writers instead)."""
    import threading
    import time

    from sqlalchemy import func, select

    from aia_core.infrastructure.db import create_session_factory
    from aia_core.infrastructure.tables import ReportEditorSessionRow

    if engine.dialect.name != "postgresql":
        pytest.skip("row locks are PostgreSQL's; SQLite serialises writers")
    composed = editor_world.compose()
    editor_world.session.commit()
    first_in, first_go = threading.Event(), threading.Event()
    real = ReportEditorRepository.add_version

    def held(self: ReportEditorRepository, **kw: Any) -> Any:
        added = real(self, **kw)
        if not first_in.is_set():  # the first opener: started the line, now held
            first_in.set()
            assert first_go.wait(30)
        return added

    monkeypatch.setattr(ReportEditorRepository, "add_version", held)
    factory = create_session_factory(engine)
    keys: list[str] = []
    errors: list[BaseException] = []

    def open_(user: str) -> None:
        try:
            with factory() as own:
                scope = editor_world.scoped.scope(user=user)
                opened = ReportEditor(own, scope).open(
                    composed, run_id="RUN-1", variant="internal", now=T0
                )
                own.commit()
                keys.append(opened.session.document_key)
        except BaseException as exc:  # reported below, never swallowed
            errors.append(exc)

    a = threading.Thread(target=open_, args=("lead",))
    a.start()
    assert first_in.wait(30)
    b = threading.Thread(target=open_, args=("other_lead",))
    b.start()
    time.sleep(1.0)  # room for the second to race ahead if nothing held it
    first_go.set()
    a.join(30)
    b.join(30)
    assert not errors, errors
    assert len(keys) == 2 and keys[0] == keys[1]
    editor_world.session.expire_all()
    open_rows = editor_world.session.scalar(
        select(func.count())
        .select_from(ReportEditorSessionRow)
        .where(ReportEditorSessionRow.closed_at.is_(None))
    )
    assert open_rows == 1


def _docx(value: str) -> bytes:
    import io
    import zipfile

    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    body = (
        f'<w:document xmlns:w="{w}"><w:body><w:p><w:sdt><w:sdtPr><w:tag w:val="trust_total"/>'
        f"</w:sdtPr><w:sdtContent><w:r><w:t>{value}</w:t></w:r></w:sdtContent></w:sdt></w:p>"
        "</w:body></w:document>"
    )
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        z.writestr(zipfile.ZipInfo("word/document.xml", (2026, 10, 23, 0, 0, 0)), body)
    return out.getvalue()


def test_two_saves_of_one_line_at_once_take_the_next_two_koncepts(
    editor_world: Any, engine: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two force-saves of one session arrive together. The first is held after it stored its
    koncept, holding the line; the second must wait for it and store the next one, never number
    the same koncept (uq_report_editor_versions_koncept, a 500).

    PostgreSQL only: the guard is a row lock, which SQLite does not take."""
    import threading
    import time

    from aia_core.application.report_editor_saves import store_save
    from aia_core.infrastructure.db import create_session_factory

    if engine.dialect.name != "postgresql":
        pytest.skip("row locks are PostgreSQL's; SQLite serialises writers")
    origin = "https://docs.aia.example.test"
    files = {f"{origin}/cache/files/{n}.docx": _docx(f"{n} %") for n in (50, 60)}
    composed = editor_world.compose(data=_docx("42 %"))
    opened = editor_world.editor.open(composed, run_id="RUN-1", variant="internal", now=T0)
    editor_world.session.commit()
    first_in, first_go = threading.Event(), threading.Event()
    real = ReportEditorRepository.add_version

    def held(self: ReportEditorRepository, **kw: Any) -> Any:
        added = real(self, **kw)
        if not first_in.is_set():
            first_in.set()
            assert first_go.wait(30)
        return added

    monkeypatch.setattr(ReportEditorRepository, "add_version", held)
    factory = create_session_factory(engine)
    koncepts: list[int] = []
    errors: list[BaseException] = []

    def save(url: str) -> None:
        try:
            with factory() as own:
                scope = editor_world.scoped.scope()
                stored = store_save(
                    own,
                    scope,
                    editor_world.store,
                    opened.session,
                    url=url,
                    origin=origin,
                    fetcher=files.__getitem__,
                    authors=[scope.actor_id],
                    now=T0,
                )
                own.commit()
                koncepts.append(stored.version.koncept)
        except BaseException as exc:  # reported below, never swallowed
            errors.append(exc)

    one, two = list(files)
    a = threading.Thread(target=save, args=(one,))
    a.start()
    assert first_in.wait(30)
    b = threading.Thread(target=save, args=(two,))
    b.start()
    time.sleep(1.0)  # room for the second to race ahead if nothing held it
    first_go.set()
    a.join(30)
    b.join(30)
    assert not errors, errors
    assert sorted(koncepts) == [2, 3]


def test_approved_edits_are_read_from_the_approved_rows_alone(editor_world: Any) -> None:
    """Whatever the length of a line's history, the run's approved edits are one query over
    the approved rows: unapproved autosaves are never read one by one."""
    composed = editor_world.compose()
    line = editor_world.editor.open(composed, run_id="RUN-1", variant="internal", now=T0).line_id
    saved = [
        editor_world.save(line, n, f"save {n}".encode(), T0 + timedelta(minutes=n))
        for n in range(2, 7)
    ]
    repo = ReportEditorRepository(editor_world.session, editor_world.scope)
    assert repo.approved_edits(run_id="RUN-1", variant="internal", deep_research_run_id=None) == []
    artifacts = research_artifacts(editor_world.session, editor_world.scope, editor_world.store)
    artifacts.approve(saved[2])
    found = repo.approved_edits(run_id="RUN-1", variant="internal", deep_research_run_id=None)
    assert [v.artifact_id for v in found] == [saved[2]]
    assert repo.approved_edits(run_id="RUN-1", variant="context", deep_research_run_id=None) == []
