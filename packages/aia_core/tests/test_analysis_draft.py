"""The draft check and the result type: no number reaches a result unadmitted."""

from __future__ import annotations

from typing import Any

import pytest

from aia_core.domain.analysis import (
    AnalysisModuleId,
    AnalysisModuleResult,
    Finding,
    UnbackedResult,
    check_analysis_draft,
    module_spec,
    numbers_in,
    repair_prompt,
    result_from_check,
    uncovered_numbers,
)
from aia_core.domain.analysis.draft import InvalidStructuredOutput, number_spans
from aia_core.domain.evidence import (
    METHOD_STATUS_PENDING,
    ClaimLevel,
    ClaimSurface,
    EvidenceTable,
    Interval,
    ViolationCode,
)

CLIENT = ClaimSurface.CLIENT_FACING
QUESTIONS = ("Jaký je zájem o nabídku?", "Liší se zájem podle věku?")


# --- numbers in prose -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "numbers"),
    [
        ("Podíl je 42,5 %.", ((42.5, 1),)),
        ("share 42.5% of 600", ((42.5, 1), (600.0, 0))),
        ("celkem 1 200 respondentů", ((1200.0, 0),)),
        ("nbsp\u00a0grouped 12\u00a0345", ((12345.0, 0),)),
        ("lidé 18\u201329 let", ((18.0, 0), (29.0, 0))),
        ("identifiers q1, E12 and vote_2021 are not numbers", ()),
        ("v roce 2025.", ((2025.0, 0),)),
        ("no digits at all", ()),
    ],
)
def test_numbers_in(text: str, numbers: tuple[tuple[float, int], ...]) -> None:
    assert numbers_in(text) == numbers


def test_number_spans_read_as_numbers_in_and_say_where() -> None:
    text = "Tržby 1 200 Kč, podíl 12,5 % (2025)."
    spans = number_spans(text)
    assert tuple((v, d) for v, d, _, _ in spans) == numbers_in(text)
    assert [text[a:b] for _, _, a, b in spans] == ["1 200", "12,5", "2025"]


def test_rounding_shown_in_prose_is_allowed_and_no_more() -> None:
    assert uncovered_numbers("zhruba 42 %", [42.4], []) == ()
    assert uncovered_numbers("42,4 %", [42.46], []) == (42.4,)
    assert uncovered_numbers("43 %", [42.4], []) == (43.0,)


def test_a_number_from_a_cited_name_cannot_be_reused_as_a_figure() -> None:
    """Review finding: citing ``age 18-29`` must not license an invented "29%"."""
    assert uncovered_numbers("Interest is 29%", [42.5], ["age 18-29"]) == (29.0,)
    assert uncovered_numbers("Zájem je 18 %.", [42.5], ["vek 18-29"]) == (18.0,)


@pytest.mark.parametrize(
    ("text", "label"),
    [
        ("mezi 18\u201329 lety 51 %", "vek 18-29"),
        ("mezi 18-29 lety 51 %", "vek 18\u201329"),
        ("ve věku 18 až 29 let 51 %", "vek 18-29"),
        ("aged 18 to 29: 51 %", "vek 18-29"),
        ("lidé 65+ 51 %", "vek 65+"),
        ("mladší <30 let 51 %", "vek <30"),
    ],
)
def test_a_cited_range_or_bound_is_a_name(text: str, label: str) -> None:
    assert uncovered_numbers(text, [51.0], [label]) == ()


def test_a_bare_number_in_a_label_licenses_nothing() -> None:
    assert uncovered_numbers("Kohorta 2021 má 51 %.", [51.0], ["kohorta 2021"]) == (2021.0,)


def test_a_different_range_is_not_the_cited_name() -> None:
    assert uncovered_numbers("mezi 18\u201330 lety 51 %", [51.0], ["vek 18-29"]) == (18.0, 30.0)


def test_numbers_in_a_cited_name_are_not_claims() -> None:
    assert uncovered_numbers("Mezi 18\u201329 lety je to 51 %", [51.0], ["vek 18-29"]) == ()
    assert uncovered_numbers("Mezi 30\u201344 lety je to 51 %", [51.0], ["vek 18-29"]) == (
        30.0,
        44.0,
    )


# --- the draft check ---------------------------------------------------------------------------


@pytest.fixture
def table(evidence_row: Any) -> EvidenceTable:
    return EvidenceTable.build(
        [
            evidence_row("E1", value=42.5, cell="total"),
            evidence_row(
                "E2",
                value=51.0,
                cell="vek 18-29",
                interval=Interval(45.2, 56.8, 0.95),
                fields=("vek",),
                level=ClaimLevel.SEGMENT,
            ),
            evidence_row("E3", metric="n", value=600.0, decimals=0, interval=None, cell="total"),
        ]
    )


def draft(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "module": "research_questions",
        "summary": "Zájem projevuje 42,5 % populace, mezi 18\u201329 lety 51 %.",
        "research_question_answers": [
            {
                "question": QUESTIONS[0],
                "answer": "Zájem má 42,5 % dospělých (n = 600).",
                "claim_ids": ["c1", "c3"],
            },
            {
                "question": QUESTIONS[1],
                "answer": "Ano, ve věku 18\u201329 je zájem 51 %.",
                "claim_ids": ["c2"],
            },
        ],
        "key_findings": [{"text": "Mladší skupina je nad průměrem: 51 %.", "claim_ids": ["c2"]}],
        "numeric_claims": [
            {"claim_id": "c1", "evidence_ref": "E1", "metric": "top2box_pct", "value": 42.5,
             "unit": "%"},
            {"claim_id": "c2", "evidence_ref": "E2", "metric": "top2box_pct", "value": 51.0,
             "unit": "%"},
            {"claim_id": "c3", "evidence_ref": "E3", "metric": "n", "value": 600.0,
             "unit": "respondents"},
        ],
    }  # fmt: skip
    body.update(overrides)
    return body


@pytest.fixture
def check(field_book: Any, joint_status: Any, table: EvidenceTable) -> Any:
    def run(raw: object, module: str = "research_questions") -> Any:
        return check_analysis_draft(
            raw,
            module_spec(module),
            table,
            book=field_book,
            joint_status=joint_status,
            surface=CLIENT,
            research_questions=QUESTIONS,
        )

    return run


def test_a_disciplined_draft_passes(check: Any) -> None:
    result = check(draft())
    assert result.decision.allowed, result.decision.violations
    assert [c.claim_id for c in result.admission.admitted] == ["c1", "c2", "c3"]


def test_metric_label_wording_does_not_license_an_uncited_count(check: Any) -> None:
    """Live repair exhausted on 'top-2'; natural wording needs no invented claim."""
    raw = draft(key_findings=[{"text": "Top-2: 42,5 %.", "claim_ids": ["c1"]}])
    assert check(raw).decision.codes == {ViolationCode.UNCITED_NUMBER}
    raw["key_findings"][0]["text"] = "Podíl nejvyšších hodnocení je 42,5 %."
    assert check(raw).decision.allowed
    raw["key_findings"][0]["text"] = "Podíl nejvyšších hodnocení je 2 %."
    assert check(raw).decision.codes == {ViolationCode.UNCITED_NUMBER}


def test_a_figure_from_external_context_is_refused_like_any_uncited_number(check: Any) -> None:
    """evidence-integrity 7: a module is shown Deep Research findings as context; a figure it
    copies from them into a draft cites no row of the run's evidence, so the gate refuses it."""
    raw = draft(summary="Podle zdroje trh vzrostl o 12,5 %; zájem projevuje 42,5 % populace.")
    assert check(raw).decision.codes == {ViolationCode.UNCITED_NUMBER}


@pytest.mark.parametrize(
    "raw",
    [
        "not an object",
        {"module": "research_questions"},
        {**draft(), "method_status": "externally validated"},
        {**draft(), "numeric_claims": [{"claim_id": "c1", "evidence_ref": "E1", "metric": "mean",
                                        "value": "42.5", "unit": "%"}]},
        {**draft(), "numeric_claims": [{"claim_id": "c1", "evidence_ref": "E1", "metric": "mean",
                                        "value": float("nan"), "unit": "%"}]},
    ],
)  # fmt: skip
def test_schema_violations_are_refused(check: Any, raw: object) -> None:
    result = check(raw)
    assert result.decision.codes == {ViolationCode.SCHEMA_INVALID}
    assert result.admission is None


def test_a_gateway_schema_failure_is_refused_once_per_failed_path(check: Any) -> None:
    failed = InvalidStructuredOutput(
        (
            "numeric_claims.0.value: Input should be a valid number",
            "confidence: Extra inputs are not permitted",
            "output is not a single JSON object",
        ),
        rejected_output='{"value": "42.5"}',
    )
    result = check(failed)
    assert result.admission is None
    assert [(v.code, v.subject, v.detail) for v in result.decision.violations] == [
        (ViolationCode.SCHEMA_INVALID, "numeric_claims.0.value", "Input should be a valid number"),
        (ViolationCode.SCHEMA_INVALID, "confidence", "Extra inputs are not permitted"),
        (ViolationCode.SCHEMA_INVALID, "draft", "output is not a single JSON object"),
    ]
    assert all("42.5" not in v.detail for v in result.decision.violations)


def test_a_long_schema_failure_keeps_twenty_paths_and_counts_the_rest(check: Any) -> None:
    failed = InvalidStructuredOutput(tuple(f"f{i}: Field required" for i in range(23)))
    subjects = [v.subject for v in check(failed).decision.violations]
    assert subjects[:20] == [f"f{i}" for i in range(20)] and subjects[20] == "draft"
    assert "and 3 more" in check(failed).decision.violations[20].detail


def test_a_model_cannot_stamp_its_own_method_status(check: Any) -> None:
    result = check({**draft(), "method_status": "validated"})
    assert "method_status" in result.decision.violations[0].subject


def test_wrong_module_is_refused(check: Any) -> None:
    assert ViolationCode.MODULE_MISMATCH in check(draft(), module="executive").decision.codes


def test_uncited_number_in_a_finding_is_refused(check: Any) -> None:
    raw = draft(key_findings=[{"text": "Zájem vzrostl o 7 bodů.", "claim_ids": ["c2"]}])
    result = check(raw)
    assert result.decision.codes == {ViolationCode.UNCITED_NUMBER}
    assert result.decision.violations[0].subject == "key_findings[0]"


def test_a_key_finding_that_cites_no_claim_is_refused_and_named(check: Any) -> None:
    """MVP-23: every key finding cites admitted evidence, even one that states no number."""
    raw = draft(
        key_findings=[
            {"text": "Mladší skupina je nad průměrem: 51 %.", "claim_ids": ["c2"]},
            {"text": "Mladší lidé o nápoj stojí víc.", "claim_ids": []},
        ]
    )
    result = check(raw)
    assert result.decision.codes == {ViolationCode.FINDING_UNCITED}
    (violation,) = result.decision.violations
    assert violation.subject == "key_findings[1]"
    # The repair turn names the finding, so the model knows which one to cite or drop.
    assert "key_findings[1]" in repair_prompt(result.decision.violations)


def test_a_finding_citing_only_an_unknown_claim_is_refused_as_dangling(check: Any) -> None:
    raw = draft(key_findings=[{"text": "Mladší lidé o nápoj stojí víc.", "claim_ids": ["c9"]}])
    assert check(raw).decision.codes == {ViolationCode.DANGLING_CLAIM_REF}


def test_a_draft_with_no_key_finding_is_left_to_the_diagnostic(check: Any) -> None:
    """A module of its summary alone is not refused here: evidence-integrity 9a diagnoses it."""
    assert check(draft(key_findings=[])).decision.allowed


def test_a_number_must_be_cited_by_the_item_that_uses_it(check: Any) -> None:
    raw = draft(key_findings=[{"text": "Celkem 42,5 %.", "claim_ids": ["c2"]}])
    assert check(raw).decision.codes == {ViolationCode.UNCITED_NUMBER}


def test_a_year_written_in_passing_is_an_uncited_number(check: Any) -> None:
    raw = draft(summary="V roce 2025 projevuje zájem 42,5 % populace.")
    assert check(raw).decision.codes == {ViolationCode.UNCITED_NUMBER}


def test_a_cited_rows_label_does_not_back_an_invented_figure(check: Any) -> None:
    """Review finding, end to end: c2 cites ``vek 18-29`` at 51 %, not a 29 % share."""
    raw = draft(key_findings=[{"text": "Zájem má 29 %.", "claim_ids": ["c2"]}])
    result = check(raw)
    assert result.decision.codes == {ViolationCode.UNCITED_NUMBER}
    assert "29" in result.decision.violations[0].detail


def test_dangling_claim_reference_is_refused(check: Any) -> None:
    raw = draft(key_findings=[{"text": "Mladší: 51 %.", "claim_ids": ["c2", "c9"]}])
    assert check(raw).decision.codes == {ViolationCode.DANGLING_CLAIM_REF}


def test_every_question_must_be_answered_and_none_invented(check: Any) -> None:
    answers = draft()["research_question_answers"]
    missing = check(draft(research_question_answers=answers[:1]))
    assert missing.decision.codes == {ViolationCode.RESEARCH_QUESTION_UNANSWERED}
    invented = check(
        draft(
            research_question_answers=[
                *answers,
                {"question": "Kdo vyhraje volby?", "answer": "Nelze říci.", "claim_ids": []},
            ]
        )
    )
    assert invented.decision.codes == {ViolationCode.RESEARCH_QUESTION_UNKNOWN}


def test_a_forged_claim_fails_the_whole_draft(check: Any) -> None:
    claims = draft()["numeric_claims"]
    claims[0] = {**claims[0], "value": 45.0}
    result = check(draft(numeric_claims=claims))
    assert ViolationCode.VALUE_MISMATCH in result.decision.codes
    assert result.admission is not None and result.admission.admitted == ()


# --- the result type -------------------------------------------------------------------------


def _result(check: Any) -> AnalysisModuleResult:
    return result_from_check(
        check(draft()),
        module_id=AnalysisModuleId.RESEARCH_QUESTIONS,
        surface=CLIENT,
        method_status=METHOD_STATUS_PENDING,
        input_fingerprint="f" * 64,
        research_questions=QUESTIONS,
    )


def test_passing_check_becomes_a_result(check: Any) -> None:
    result = _result(check)
    assert [c.claim_id for c in result.claims] == ["c1", "c2", "c3"]
    assert result.method_status == METHOD_STATUS_PENDING
    assert result.indicative_claims == ()


def test_failing_check_never_becomes_a_result(check: Any) -> None:
    with pytest.raises(UnbackedResult, match="UNCITED_NUMBER"):
        result_from_check(
            check(draft(summary="Zájem má 99 %.")),
            module_id=AnalysisModuleId.RESEARCH_QUESTIONS,
            surface=CLIENT,
            method_status=METHOD_STATUS_PENDING,
            input_fingerprint="f" * 64,
            research_questions=QUESTIONS,
        )


def test_a_result_built_by_hand_still_refuses_unbacked_prose(check: Any) -> None:
    good = _result(check)
    fields = {name: getattr(good, name) for name in AnalysisModuleResult.__dataclass_fields__}
    with pytest.raises(UnbackedResult, match="no admitted claim backs"):
        AnalysisModuleResult(**{**fields, "key_findings": (Finding("Zájem má 77 %.", ("c1",)),)})
    with pytest.raises(UnbackedResult, match="cites no admitted claim"):
        AnalysisModuleResult(**{**fields, "key_findings": (Finding("Mladší o nápoj stojí.", ()),)})
    with pytest.raises(UnbackedResult, match="not admitted"):
        AnalysisModuleResult(**{**fields, "key_findings": (Finding("51 %", ("c7",)),)})
    with pytest.raises(UnbackedResult, match="only admitted claims"):
        AnalysisModuleResult(**{**fields, "claims": ("c1",)})
    with pytest.raises(UnbackedResult, match="method status"):
        AnalysisModuleResult(**{**fields, "method_status": "validated by the model"})
    with pytest.raises(UnbackedResult, match="surface"):
        AnalysisModuleResult(**{**fields, "surface": ClaimSurface.INTERNAL})
