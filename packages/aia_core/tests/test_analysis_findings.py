"""A person's review of a run's key findings, as rules (artifact-analysis ANL11, spec szz/A7)."""

from __future__ import annotations

from datetime import UTC, datetime

from aia_core.domain.analysis.modules import AnalysisModuleId
from aia_core.domain.analysis.review import (
    MAX_WORDING,
    FindingDecision,
    FindingKey,
    review_comment,
    reviews_of,
    wording_problem,
)
from aia_core.domain.approval_ledger import ApprovalSubject, LedgerEntry

RUN = "RUN-0123456789abcdef"
EXEC0 = FindingKey(AnalysisModuleId.EXECUTIVE, 0)
SHOWN = {AnalysisModuleId.EXECUTIVE: "ART-exec", AnalysisModuleId.OBJECTS: "ART-objects"}


def _entry(
    n: int,
    decision: str,
    key: FindingKey = EXEC0,
    *,
    wording: str | None = None,
    run: str = RUN,
    subject: ApprovalSubject = ApprovalSubject.ANALYSIS_FINDING,
    artifact: str | None = None,
) -> LedgerEntry:
    return LedgerEntry(
        decision_id=n,
        subject=subject,
        subject_id=key.subject_id(run),
        run_id=run,
        decision=decision,
        approver_user_id=f"user-{n}",
        self_approved=False,
        comment=review_comment(artifact or SHOWN[key.module], wording),
        created_at=datetime(2026, 10, 26, 12, n, tzinfo=UTC),
    )


def test_a_finding_s_subject_names_its_run_module_and_place_and_reads_back() -> None:
    assert EXEC0.subject_id(RUN) == "RUN-0123456789abcdef:executive:0"
    assert FindingKey.of_subject("RUN-0123456789abcdef:research_questions:12") == FindingKey(
        AnalysisModuleId.RESEARCH_QUESTIONS, 12
    )
    for malformed in (f"{RUN}:nonsense:0", f"{RUN}:executive:-1", f"{RUN}:executive", RUN):
        assert FindingKey.of_subject(malformed) is None


def test_the_newest_decision_wins_and_an_undo_takes_the_finding_back_to_undecided() -> None:
    objects1 = FindingKey(AnalysisModuleId.OBJECTS, 1)
    entries = [
        _entry(1, "accepted"),
        _entry(2, "edited", wording="Čaj vede."),
        _entry(3, "dropped", objects1),
        _entry(4, "undone", objects1),
    ]
    reviews = reviews_of(reversed(entries), SHOWN)  # read in any order, decided by decision id
    assert set(reviews) == {EXEC0}
    edited = reviews[EXEC0]
    assert (edited.decision, edited.wording, edited.decided_by) == (
        FindingDecision.EDITED,
        "Čaj vede.",
        "user-2",
    )
    # An accept after an edit drops the edited wording: the finding stands as the model wrote it.
    later = reviews_of([*entries, _entry(5, "accepted")], SHOWN)[EXEC0]
    assert (later.decision, later.wording) == (FindingDecision.ACCEPTED, None)


def test_an_undecided_finding_is_absent_never_accepted() -> None:
    assert reviews_of([], SHOWN) == {}
    assert reviews_of([_entry(1, "accepted"), _entry(2, "undone")], SHOWN) == {}
    assert reviews_of([_entry(1, "accepted", subject=ApprovalSubject.ARTIFACT)], SHOWN) == {}


def test_a_decision_holds_on_the_outcome_it_was_made_on_and_on_nothing_else() -> None:
    """An analysis retry reuses a module's outcome: a decision made on the first run holds on the
    retry. A module whose outcome was replaced is not reviewed, whatever run the row names."""
    retry = "RUN-ffffffffffffffff"
    reused = reviews_of([_entry(1, "dropped", run=RUN)], SHOWN)
    assert reused[EXEC0].decision is FindingDecision.DROPPED
    assert reviews_of([_entry(1, "dropped", run=retry, artifact="ART-old")], SHOWN) == {}
    assert reviews_of([_entry(1, "accepted")], {}) == {}


def test_an_edit_may_change_words_never_numbers() -> None:
    original = "Čaj volí 38,4 % lidí ve věku 18-29 let."
    cited = [38.4]
    names = ["q2: Čaj, věk 50-64", original]
    assert (
        wording_problem("Čaj si vybírá 38,4 % mladých (18-29).", cited_values=cited, names=names)
        is None
    )
    # A number no cited claim backs is named, so the person sees which one.
    assert wording_problem("Čaj volí 45 % lidí.", cited_values=cited, names=names) == (45.0,)
    # A range a cited claim's cell writes is allowed, as the gate allows it in a model's draft.
    assert wording_problem("Ve věku 50-64 vede čaj.", cited_values=cited, names=names) is None
    # The original's range stays allowed; a range neither writes does not.
    assert wording_problem("Mladí (30-39) volí čaj.", cited_values=cited, names=names) == (
        30.0,
        39.0,
    )
    assert wording_problem("   ", cited_values=cited, names=names) == "empty"
    assert wording_problem("a" * (MAX_WORDING + 1), cited_values=cited, names=names) == ("too_long")
