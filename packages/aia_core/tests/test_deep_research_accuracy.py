"""Accuracy on a truth set: exact values, primary sources, cells, false acceptances, gaps.

Plan ``deep-research-web-search.md`` chunk 25. Every figure, publisher and host here
is FICTIONAL (the fixture's invented publishers on ``.example`` hosts, the year
2091). The bundles are sealed the way a run seals them.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from aia_core.domain.deep_research.accuracy import (
    AcquisitionGapRecord,
    AttributeCheck,
    BundleRefused,
    GroundingKind,
    Provenance,
    RunFinding,
    RunRecord,
    TargetStatus,
    ValueVerdict,
    accuracy_report,
    render_summary,
    run_from_bundle,
    score_run,
)
from aia_core.domain.deep_research.bundle import EvidenceBundle, TrackRecord, seal_bundle
from aia_core.domain.deep_research.contracts import (
    HARNESS_VERSION,
    BriefDigest,
    Channel,
    DeepResearchRequest,
    EvidenceItem,
    EvidenceType,
    FrozenKnowledge,
    Measure,
    RecommendedUse,
    ResearchSubject,
    RetrievalMode,
    SourceKind,
    StopReason,
    SubjectKind,
    TrackStatus,
    subject_key,
)
from aia_core.domain.deep_research.measures import claim_measures
from aia_core.domain.deep_research.merge import AcceptedEvidence, RespondentUse, ScoreRecord
from aia_core.domain.deep_research.truth_set import (
    TruthSet,
    TruthSetRefused,
    empty_pins,
    load_pins,
    load_truth_set,
)
from aia_core.domain.residency import DataClass

FIXTURES = Path(__file__).parent / "fixtures" / "deep_research_accuracy"
TRUTH: TruthSet = load_truth_set((FIXTURES / "fictional_truth_set.json").read_text("utf-8"))
PINS = load_pins((FIXTURES / "pins.json").read_text("utf-8"))
QUESTIONS = {f.fact_id: f.question for f in TRUTH.facts}
STAT = "https://statistika-fikce.example/tabulka"
KOMORA = "https://komora-fikce.example/zprava"
_ids = itertools.count(1)


def _subject(fact_id: str) -> ResearchSubject:
    text = QUESTIONS[fact_id]
    assert text is not None
    return ResearchSubject(
        key=subject_key(SubjectKind.QUESTION, text),
        kind=SubjectKind.QUESTION,
        text=text,
        origin="truth_set",
    )


SUBJECTS = {fact_id: _subject(fact_id) for fact_id in QUESTIONS}


def _finding(
    fact_id: str,
    claim: str,
    *,
    url: str | None = STAT,
    quote: str | None = None,
    measures: tuple[Measure, ...] = (),
    **fields: Any,
) -> RunFinding:
    """A finding as a run record states it; its measures read from the claim unless given."""
    return RunFinding.model_validate(
        {
            "evidence_id": f"EV-{next(_ids):016x}",
            "subject_key": SUBJECTS[fact_id].key,
            "claim": claim,
            "quote": quote or claim,
            "source_ref": "SNP-" + "0" * 24,
            "source_url": url,
            "measures": measures or claim_measures(claim),
            "measures_from": "stated" if measures else "read",
            "grounding": fields.pop("grounding", GroundingKind.TEXT),
            **fields,
        }
    )


def _run(*findings: RunFinding, preset: str = "DEEP", **fields: Any) -> RunRecord:
    return RunRecord.model_validate(
        {
            "kind": "deep_research_accuracy_run",
            "version": "aia-dr-accuracy-run-1",
            "run_id": fields.pop("run_id", f"run-{preset}"),
            "preset": preset,
            "origins": ("RECORDED_FIXTURE",),
            "fictional_client": True,
            "subjects": {s.key: s.text for s in SUBJECTS.values()},
            "findings": findings,
            "reports_provenance": fields.pop("reports_provenance", False),
            "reports_acquisition_gaps": fields.pop("reports_acquisition_gaps", False),
            **fields,
        }
    )


def _fact(run: RunRecord, fact_id: str) -> Any:
    score = score_run(TRUTH, run)
    return next(f for f in score.facts if f.fact_id == fact_id)


# --------------------------------------------------------------------------- one fact


def test_the_same_number_in_another_scale_is_exact() -> None:
    for claim in (
        "V roce 2091 vlastnilo fiktivní přístroj 450 tis. domácností v Česku.",
        "V roce 2091 vlastnilo fiktivní přístroj 450 000 domácností v Česku.",
    ):
        fact = _fact(_run(_finding("cons-01", claim)), "cons-01")
        assert fact.answered and fact.exact and not fact.false_acceptances, claim
        (judged,) = fact.measures
        assert judged.value is ValueVerdict.EXACT
        assert set(judged.attributes.values()) == {AttributeCheck.MATCH}


def test_a_dropped_scale_is_a_wrong_number_accepted() -> None:
    finding = _finding("cons-01", "V roce 2091 vlastnilo fiktivní přístroj 450 domácností v Česku.")
    fact = _fact(_run(finding), "cons-01")
    assert fact.answered and not fact.exact
    assert fact.false_acceptances == (finding.evidence_id,)
    assert fact.measures[0].value is ValueVerdict.WRONG


def test_a_wrong_unit_is_another_figure_not_an_answer() -> None:
    fact = _fact(
        _run(_finding("price-02", "Inflace v Česku v roce 2091 vzrostla o 2,5 p. b.")),
        "price-02",
    )
    (judged,) = fact.measures
    assert judged.attributes["unit"] is AttributeCheck.CONTRADICT
    assert not judged.answers and not fact.answered and not fact.exact
    assert fact.false_acceptances == () and fact.gap


def test_a_wrong_period_is_another_figure_not_an_answer() -> None:
    fact = _fact(_run(_finding("price-02", "Inflace v Česku v roce 2090 byla 3,1 %.")), "price-02")
    assert fact.measures[0].attributes["period"] is AttributeCheck.CONTRADICT
    assert not fact.answered and fact.false_acceptances == () and fact.gap


def test_an_unstated_period_answers_but_is_never_exact() -> None:
    right = _fact(_run(_finding("price-02", "Inflace v Česku byla 2,5 %.")), "price-02")
    assert right.answered and not right.exact and right.false_acceptances == ()
    assert right.measures[0].attributes["period"] is AttributeCheck.UNSTATED
    wrong = _finding("price-02", "Inflace v Česku byla 4,1 %.")
    fact = _fact(_run(wrong), "price-02")
    assert fact.false_acceptances == (wrong.evidence_id,)


def test_a_household_share_is_not_a_share_of_people() -> None:
    fact = _fact(
        _run(_finding("cons-02", "V roce 2091 kupovalo fiktivní nápoj 45 % lidí v Česku.")),
        "cons-02",
    )
    assert fact.measures[0].attributes["population"] is AttributeCheck.CONTRADICT
    assert not fact.answered and not fact.exact


def test_the_country_is_not_its_capital() -> None:
    fact = _fact(
        _run(_finding("pop-02", "Česko mělo k 31. 12. 2091 celkem 1,4 mil. obyvatel.")),
        "pop-02",
    )
    assert fact.measures[0].attributes["geography"] is AttributeCheck.CONTRADICT
    assert not fact.answered


def test_a_bare_number_names_no_figure_and_answers_nothing() -> None:
    # "k 31. 12." is read as two numbers; with no unit or population they answer nothing.
    fact = _fact(
        _run(_finding("pop-01", "Česko mělo k 31. 12. 2091 celkem 10 450 tis. obyvatel.")),
        "pop-01",
    )
    day, month, count = fact.measures
    assert (day.measure.value, month.measure.value) == (31.0, 12.0)
    assert day.attributes["population"] is AttributeCheck.UNSTATED
    assert not day.answers and not month.answers and not day.false_acceptance
    assert count.answers and count.exact and fact.false_acceptances == ()
    no_unit = _finding("price-02", "Inflace v Česku v roce 2091 byla 4,1.")
    assert not _fact(_run(no_unit), "price-02").answered


def test_a_coarser_rounding_is_neither_exact_nor_wrong() -> None:
    fact = _fact(
        _run(_finding("pop-01", "Česko mělo k 31. 12. 2091 celkem 10,5 mil. obyvatel.")),
        "pop-01",
    )
    assert fact.answered and not fact.exact and fact.false_acceptances == ()
    assert [m.value for m in fact.measures if m.answers] == [ValueVerdict.ROUNDED]
    same_precision = _finding("pop-01", "Česko mělo k 31. 12. 2091 celkem 10 460 tis. obyvatel.")
    assert _fact(_run(same_precision), "pop-01").false_acceptances == (same_precision.evidence_id,)


def test_a_stated_absolute_tolerance_is_honoured_and_no_further() -> None:
    near = _fact(
        _run(_finding("trade-01", "Vývoz fiktivního zboží z Česka v roce 2091 byl 1,22 mld. Kč.")),
        "trade-01",
    )
    assert near.exact
    far = _finding("trade-01", "Vývoz fiktivního zboží z Česka v roce 2091 byl 1,3 mld. Kč.")
    assert _fact(_run(far), "trade-01").false_acceptances == (far.evidence_id,)


def test_stated_measures_in_words_are_read_into_the_vocabulary() -> None:
    measure = Measure(value=42.5, unit="Kč", denominator="litr", period="2091", geography="Česko")
    fact = _fact(_run(_finding("price-01", "Litr stál 42,5 Kč.", measures=(measure,))), "price-01")
    assert fact.exact
    assert fact.measures[0].measure.unit == "CZK" and fact.measures[0].measure.denominator == "l"


def test_primary_is_decided_by_the_publisher_of_the_source_not_by_the_run() -> None:
    claim = "Česko mělo k 31. 12. 2091 celkem 10 450 tis. obyvatel."
    secondary = _run(
        _finding("pop-01", claim, url=KOMORA, provenance=Provenance.PRIMARY),
        reports_provenance=True,
    )
    fact = _fact(secondary, "pop-01")
    assert fact.exact and not fact.primary_used
    assert fact.measures[0].publisher == "register:fiktivni obchodni komora"
    assert fact.measures[0].run_provenance is Provenance.PRIMARY
    assert _fact(_run(_finding("pop-01", claim, url=STAT)), "pop-01").primary_used


def test_a_cell_grounded_answer_is_counted() -> None:
    claim = "Česko mělo k 31. 12. 2091 celkem 10 450 tis. obyvatel."
    cell = _finding(
        "pop-01", claim, grounding=GroundingKind.DATASET_CELL, cell_locator="OBY01!CZ/2091"
    )
    assert _fact(_run(cell), "pop-01").cell_grounded
    assert not _fact(_run(_finding("pop-01", claim)), "pop-01").cell_grounded


def test_a_finding_on_another_question_does_not_answer_this_one() -> None:
    # The right figure, filed under the Prague question: pop-01 stays unanswered.
    stray = _finding("pop-02", "Česko mělo k 31. 12. 2091 celkem 10 450 tis. obyvatel.")
    fact = _fact(_run(stray), "pop-01")
    assert fact.asked and not fact.answered and fact.gap and fact.measures == ()


def test_one_right_and_one_wrong_finding_is_exact_and_a_false_acceptance() -> None:
    right = _finding("price-02", "Inflace v Česku v roce 2091 byla 2,5 %.")
    wrong = _finding("price-02", "Inflace v Česku v roce 2091 byla 2,7 %.", url=KOMORA)
    fact = _fact(_run(right, wrong), "price-02")
    assert fact.exact and fact.false_acceptances == (wrong.evidence_id,)


# --------------------------------------------------------------------------- runs


def test_unasked_facts_count_against_accuracy() -> None:
    subjects = {SUBJECTS["pop-01"].key: SUBJECTS["pop-01"].text}
    run = RunRecord(
        kind="deep_research_accuracy_run",
        version="aia-dr-accuracy-run-1",
        run_id="r",
        preset="DEEP",
        origins=(),
        fictional_client=True,
        subjects=subjects,
        findings=(_finding("pop-01", "Česko mělo k 31. 12. 2091 celkem 10 450 tis. obyvatel."),),
        reports_provenance=False,
        reports_acquisition_gaps=False,
    )
    m = score_run(TRUTH, run).metrics
    assert (m.facts, m.asked, m.not_asked, m.exact, m.gaps) == (7, 1, 6, 1, 0)
    assert m.exact_accuracy == pytest.approx(1 / 7)
    assert m.primary_source_rate == 1.0 and m.cell_grounded_share == 0.0


def test_nothing_answered_leaves_the_rates_unmeasured() -> None:
    m = score_run(TRUTH, _run()).metrics
    assert m.answered == 0 and m.gaps == 7 and m.exact_accuracy == 0.0
    assert m.primary_source_rate is None and m.cell_grounded_share is None
    assert m.acquisition_gaps is None


def test_acquisition_gaps_are_counted_and_tied_to_their_publisher() -> None:
    run = _run(
        reports_acquisition_gaps=True,
        acquisition_gaps=(
            AcquisitionGapRecord(
                gap_id="AG-1", publisher="Fiktivní obchodní komora", title="Vývoz", reason="paywall"
            ),
            AcquisitionGapRecord(gap_id="AG-2", publisher=None, title="?", reason="robots"),
        ),
    )
    score = score_run(TRUTH, run)
    assert score.metrics.acquisition_gaps == 2
    by_id = {f.fact_id: f for f in score.facts}
    assert by_id["trade-01"].acquisition_gaps == ("AG-1",)
    assert by_id["pop-01"].acquisition_gaps == ()


def test_a_run_record_holds_together() -> None:
    finding = _finding("pop-01", "Česko mělo 10 450 tis. obyvatel.", provenance=Provenance.PRIMARY)
    with pytest.raises(ValidationError, match="reports none"):
        _run(finding)
    with pytest.raises(ValidationError, match="names its cell"):
        _finding("pop-01", "x 1 y", grounding=GroundingKind.DATASET_CELL)
    with pytest.raises(ValidationError, match="listed twice"):
        _run(finding, finding, reports_provenance=True)


# --------------------------------------------------------------------------- the bundle


def _request() -> DeepResearchRequest:
    return DeepResearchRequest(
        harness_version=HARNESS_VERSION,
        design_revision_id="REV-1",
        design_revision=1,
        preset="DEEP",
        channels=(Channel.WEB,),
        brief=BriefDigest(title="t", goal="g", decision_use="d", briefing=""),
        subjects=tuple(SUBJECTS.values()),
        questionnaire=(),
        knowledge=FrozenKnowledge(items=(), omitted_ids=(), retrieval_limit=200),
        client_terms=(),
    )


def _track(subject: ResearchSubject) -> TrackRecord:
    return TrackRecord(
        track_id="DRT-W-" + subject.key,
        subject_key=subject.key,
        channel=Channel.WEB,
        fingerprint="a" * 64,
        status=TrackStatus.COMPLETED,
        stop_reason=StopReason.SATURATED,
        detail="",
        reused=False,
        artifact_id="ART-1",
        retrieval_mode=RetrievalMode.RECORDED,
        queries=(),
        snapshot_ids=(),
        evidence_ids=(),
        quarantined_ids=(),
        model_requests=1,
        search_calls=1,
        fetches=1,
        credits=0,
        model_cost_usd=0.0,
        tool_cost_usd=0.0,
    )


def _accepted(fact_id: str, claim: str, *, quote: str | None = None, url: str = STAT) -> Any:
    subject = SUBJECTS[fact_id]
    item = EvidenceItem(
        evidence_id=f"EV-{next(_ids):016x}",
        track_id="DRT-W-" + subject.key,
        subject_key=subject.key,
        channel=Channel.WEB,
        source_kind=SourceKind.WEB_PAGE,
        source_ref="SNP-" + "1" * 24,
        source_url=url,
        source_title="t",
        claim=claim,
        quote=quote or claim,
        quote_span=(0, len(quote or claim)),
        evidence_type=EvidenceType.OFFICIAL_REPORT,
        source_date="2091-12-31",
        geography="CZ",
        population="",
        topics=(),
        data_class=DataClass.CLASS_C_INTERNAL,
        agent_outcome_overlap=False,
        agent_recommended_use=RecommendedUse.CONTEXT_ONLY,
        agent_source_quality=0.9,
    )
    return AcceptedEvidence(
        evidence=item,
        score=ScoreRecord(
            source_class="OFFICIAL_STATISTICS",
            base=0.95,
            age="recent",
            age_adjustment=0.0,
            score=0.95,
            geography="CZ",
            table_version="t",
        ),
        respondent_use=RespondentUse.ELIGIBLE,
        respondent_exclusion=None,
        merged_ids=(),
        confirmations=(),
        confidence=0.8,
        verifier_reason="ok",
    )


def _bundle(*accepted: AcceptedEvidence) -> EvidenceBundle:
    return seal_bundle(
        request=_request(),
        subjects=tuple(SUBJECTS.values()),
        versions={"harness": HARNESS_VERSION},
        tracks=tuple(_track(s) for s in SUBJECTS.values()),
        accepted=accepted,
        quarantined=(),
        snapshots=(),
        synthesis=None,
        fictional_client=True,
        counts={},
        spend_usd={},
    )


def test_a_sealed_bundle_becomes_a_run_record() -> None:
    cell_quote = "[OBY01!CZ/2091] Česko | 2091 | unit osoby = 10 450 tis. obyvatel"
    bundle = _bundle(
        _accepted(
            "pop-01", "Česko mělo k 31. 12. 2091 celkem 10 450 tis. obyvatel.", quote=cell_quote
        ),
        _accepted("price-02", "Inflace v Česku v roce 2091 byla 2,5 %."),
    )
    run = run_from_bundle(bundle)
    assert run.preset == "DEEP" and run.origins == ("RECORDED_FIXTURE",)
    assert not run.reports_provenance and not run.reports_acquisition_gaps
    by_subject = {f.subject_key: f for f in run.findings}
    pop = by_subject[SUBJECTS["pop-01"].key]
    assert pop.grounding is GroundingKind.DATASET_CELL and pop.cell_locator == "OBY01!CZ/2091"
    assert pop.measures_from == "read"
    assert by_subject[SUBJECTS["price-02"].key].grounding is GroundingKind.TEXT
    m = score_run(TRUTH, run).metrics
    assert (m.exact, m.cell_grounded_answered, m.acquisition_gaps) == (2, 1, None)


def test_a_tampered_bundle_is_refused() -> None:
    bundle = _bundle(_accepted("price-02", "Inflace v Česku v roce 2091 byla 2,5 %."))
    tampered = bundle.model_copy(update={"preset": "QUICK"})
    with pytest.raises(BundleRefused):
        run_from_bundle(tampered)


# --------------------------------------------------------------------------- the report


def _all_exact(preset: str) -> RunRecord:
    claims = {
        "pop-01": "Česko mělo k 31. 12. 2091 celkem 10 450 tis. obyvatel.",
        "pop-02": "Praha měla k 31. 12. 2091 celkem 1 400 tis. obyvatel.",
        "cons-01": "V roce 2091 vlastnilo fiktivní přístroj 450 tis. domácností v Česku.",
        "cons-02": "V roce 2091 kupovalo fiktivní nápoj 45 % domácností v Česku.",
        "price-01": "Litr fiktivního nápoje stál v Česku v roce 2091 průměrně 42,5 Kč za litr.",
        "price-02": "Inflace v Česku v roce 2091 byla 2,5 %.",
        "trade-01": "Vývoz fiktivního zboží z Česka v roce 2091 byl 1,2 mld. Kč.",
    }
    return _run(
        *(_finding(f, c, url=KOMORA if f == "trade-01" else STAT) for f, c in claims.items()),
        preset=preset,
    )


def test_every_fact_of_the_fixture_can_be_answered_exactly() -> None:
    m = score_run(TRUTH, _all_exact("DEEP")).metrics
    assert (m.exact, m.answered, m.false_acceptances, m.gaps) == (7, 7, 0, 0)
    assert m.primary_source_rate == 1.0


def test_the_report_pools_per_preset_and_checks_the_proposed_targets() -> None:
    standard = _run(
        _finding("price-02", "Inflace v Česku v roce 2091 byla 2,9 %."), preset="STANDARD"
    )
    report = accuracy_report(TRUTH, PINS, [_all_exact("DEEP"), standard], allow_unverified=True)
    assert set(report.presets) == {"DEEP", "STANDARD"}
    assert report.presets["DEEP"].exact_accuracy == 1.0
    assert report.presets["STANDARD"].false_acceptances == 1
    status = {(c.target_id, c.preset): c.status for c in report.targets}
    assert status == {
        ("zero-false-acceptances", "DEEP"): TargetStatus.PASS,
        ("zero-false-acceptances", "STANDARD"): TargetStatus.FAIL,
        ("exact-accuracy-deep", "DEEP"): TargetStatus.PASS,
    }
    assert report.targets_status == "proposed"
    summary = render_summary(report)
    assert "FALSE ACCEPTANCE run-STANDARD price-02" in summary
    assert "FICTIONAL" in summary and "[fail] zero false acceptances @ STANDARD" in summary


def test_two_runs_of_one_preset_are_pooled() -> None:
    a = _all_exact("DEEP").model_copy(update={"run_id": "a"})
    b = _run(preset="DEEP", run_id="b")
    report = accuracy_report(TRUTH, PINS, [a, b], allow_unverified=True)
    deep = report.presets["DEEP"]
    assert (deep.facts, deep.exact) == (14, 7)
    assert deep.exact_accuracy == 0.5
    status = {(c.target_id, c.preset): c.status for c in report.targets}
    assert status[("exact-accuracy-deep", "DEEP")] is TargetStatus.FAIL


def test_deep_not_run_is_not_measured_not_passed() -> None:
    report = accuracy_report(TRUTH, PINS, [_all_exact("STANDARD")], allow_unverified=True)
    deep = [c for c in report.targets if c.target_id == "exact-accuracy-deep"]
    assert [(c.status, c.measured) for c in deep] == [(TargetStatus.NOT_MEASURED, None)]


def test_the_report_refuses_before_scoring_an_unpinned_or_unverified_set() -> None:
    with pytest.raises(TruthSetRefused, match="not pinned"):
        accuracy_report(TRUTH, empty_pins(), [_all_exact("DEEP")], allow_unverified=True)
    with pytest.raises(TruthSetRefused, match="not verified"):
        accuracy_report(TRUTH, PINS, [_all_exact("DEEP")], allow_unverified=False)


def test_the_report_is_plain_json() -> None:
    report = accuracy_report(TRUTH, PINS, [_all_exact("DEEP")], allow_unverified=True)
    again = type(report).model_validate_json(report.model_dump_json())
    assert again == report
    assert report.truth_set.sha256 == TRUTH.sha256()
