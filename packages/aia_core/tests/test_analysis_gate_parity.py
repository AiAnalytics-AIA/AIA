"""The analysis evidence gate against the unit's own ``evidence_validator.py`` (M17).

The unit's module is stdlib-only, so it is imported here straight from the frozen tree
(read, never edited), as ``test_respondent_facts.py`` does with ``factual_layer.py``.
Both gates judge the same drafts over the same numbers: the aggregate AIA computes is
the unit's ``vysledky`` (``domain/research_aggregate.py`` ports ``agreguj_otazku``), so
``{"vysledky": aggregate["questions"]}`` is exactly what the unit's validator indexed,
and AIA's native evidence is built from the same aggregate.

Each case says what the unit decided and what AIA decides, and why they may differ:

``EXACT``
    The same decision.
``INTENTIONAL_DIFFERENCE``
    AIA refuses what the unit admitted, for a stated reason. AIA is never looser here.
``DECISION_OWED``
    AIA admits what the unit refused. Nobody has decided that, so it is not called
    intentional: the case names the decision it waits on (the plan's ANL-4), and the
    test pins today's behaviour so that deciding it changes a test on purpose.

Battery objects are left out: the unit's validator indexed only the Sociomap's map
metrics for a battery (``battery:<id>``), which AIA does not treat as evidence (D6).
"""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Literal

import pytest

from aia_core.domain.analysis import AnalysisModuleId, check_analysis_draft, module_spec
from aia_core.domain.analysis.native import NativeEvidence, native_evidence
from aia_core.domain.evidence import ClaimSurface, ViolationCode
from aia_core.domain.research_aggregate import aggregate_dataset
from aia_core.domain.research_design import compile_design
from aia_core.domain.synthetic_fieldwork import synthetic_dataset

UNIT = Path(__file__).resolve().parents[3] / "legacy" / "npc-panel-18.6.6" / "app"
#: evidence_validator.py as compared; a regenerated unit that changes it fails here first.
UNIT_SHA = "a82b893f35d67eefa89a498decddb95b062f7cb86af23f3f8b3b29174e43a304"

DESIGN: dict[str, Any] = {
    "title": "Ranní nápoj",
    "n": 200,
    "sections": [
        {
            "type": "questions",
            "questions": [
                {"id": "q1", "text": "Jak často pijete kávu?", "typ": "skala", "skala": [1, 5]},
                {
                    "id": "q2",
                    "text": "Co si ráno koupíte?",
                    "typ": "vyber",
                    "kategorie": ["Kávu", "Čaj", "Nic"],
                },
                {
                    "id": "q5",
                    "text": "Kolik byste zaplatil za šálek kávy?",
                    "typ": "vyber",
                    "kategorie": ["Málo", "Středně", "Hodně"],
                },
            ],
        }
    ],
}


@pytest.fixture(scope="module")
def unit() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "unit_evidence_validator", UNIT / "evidence_validator.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[spec.name]
        raise
    return module


@dataclass(frozen=True)
class Evidence:
    native: NativeEvidence
    summary: dict[str, Any]


@pytest.fixture(scope="module")
def evidence() -> Evidence:
    spec, problems = compile_design(DESIGN)
    assert spec is not None, problems
    dataset = synthetic_dataset(spec, seed=20260816)
    aggregate = aggregate_dataset(spec, dataset)
    native = native_evidence(spec, aggregate, dataset_sha256="d" * 64, origin=dataset.origin)
    return Evidence(native=native, summary={"vysledky": aggregate["questions"]})


def test_the_unit_source_is_the_one_compared() -> None:
    digest = hashlib.sha256((UNIT / "evidence_validator.py").read_bytes()).hexdigest()
    assert digest == UNIT_SHA


def test_both_gates_read_the_same_numbers(unit: ModuleType, evidence: Evidence) -> None:
    """Every share, mean, top-two-box and effective n AIA can cite is the unit's value."""
    index = unit.build_evidence_index(evidence.summary)
    compared = 0
    for ref, row in evidence.native.table.rows.items():
        qid, _, _ = ref.partition(".")
        metric = str(row.metric)
        if metric == "n":
            continue  # the aggregate states n_platnych; the unit's index read an absent "n"
        assert unit.resolve_metric(index, qid, metric) == row.value, ref
        compared += 1
    assert compared >= 6


# --------------------------------------------------------------------------- #
# the decision table
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Claim:
    qid: str  #: the unit's evidence_ref: a question
    metric: str  #: the unit's spelling: pct:<answer>, mean, top2box_pct, effective_n
    ref: str  #: AIA's evidence_ref: one row
    #: added to the evidence's value; a claim on a number neither gate holds states 40.8
    delta: float = 0.0
    as_text: bool = False


@dataclass(frozen=True)
class Finding:
    #: ``{0}``, ``{1}`` ... are the claims' values as prose writes them (decimal comma)
    text: str
    claims: tuple[Claim, ...] = ()
    #: the unit's evidence_refs; by default the questions the claims cite
    refs: tuple[str, ...] | None = None


Parity = Literal["EXACT", "INTENTIONAL_DIFFERENCE", "DECISION_OWED"]


@dataclass(frozen=True)
class Case:
    case_id: str
    source: str
    parity: Parity
    findings: tuple[Finding, ...]
    unit_passes: bool
    aia_allows: bool
    aia_codes: frozenset[ViolationCode] = frozenset()
    why: str = ""


KAVU = Claim("q2", "pct:Kávu", "q2.pct.1")
ONE = Finding("Kávu si ráno koupí {0} % fiktivních respondentů.", (KAVU,))

CASES: tuple[Case, ...] = (
    Case("copied-exactly", "evidence_validator.py:28-38", "EXACT", (ONE,), True, True),
    Case(
        "mean-and-top-two-box", "evidence_validator.py:14-16", "EXACT",
        (
            Finding(
                "Průměr je {0} a {1} % volí dva nejvyšší body.",
                (Claim("q1", "mean", "q1.mean"), Claim("q1", "top2box_pct", "q1.top2box")),
            ),
        ),
        True, True,
    ),
    Case(
        "value-off-the-table", "evidence_validator.py:34-37", "EXACT",
        (Finding("Kávu si koupí {0} %.", (Claim("q2", "pct:Kávu", "q2.pct.1", delta=4.0),)),),
        False, False, frozenset({ViolationCode.VALUE_MISMATCH}),
    ),
    Case(
        "unknown-question", "evidence_validator.py:31", "EXACT",
        (Finding("Kávu si koupí {0} %.", (Claim("q9", "pct:Kávu", "q9.pct.1"),)),),
        False, False, frozenset({ViolationCode.EVIDENCE_REF_UNKNOWN}),
    ),
    Case(
        "unknown-answer", "evidence_validator.py:32", "EXACT",
        (Finding("Džus si koupí {0} %.", (Claim("q2", "pct:Džus", "q2.pct.9"),)),),
        False, False, frozenset({ViolationCode.EVIDENCE_REF_UNKNOWN}),
    ),
    Case(
        "metric-outside-the-set", "evidence_validator.py:32; M17 allowed metrics", "EXACT",
        (Finding("Medián je {0}.", (Claim("q1", "median", "q1.median"),)),),
        False, False, frozenset({ViolationCode.EVIDENCE_REF_UNKNOWN}),
    ),
    Case(
        "within-the-units-tolerance", "evidence_validator.py:28 (tolerance .051)",
        "INTENTIONAL_DIFFERENCE",
        (Finding("Kávu si koupí {0} %.", (Claim("q2", "pct:Kávu", "q2.pct.1", delta=0.03),)),),
        True, False, frozenset({ViolationCode.VALUE_MISMATCH}),
        why="a value is copied exactly (M17's own prompt rule); the unit let 0.051 through",
    ),
    Case(
        "uncited-number-in-prose", "evidence_validator.py:39-60 (prose never read)",
        "INTENTIONAL_DIFFERENCE",
        (Finding("Kávu pije 55 % fiktivních respondentů.", (KAVU,)),),
        True, False, frozenset({ViolationCode.UNCITED_NUMBER}),
        why="every number in prose must be a cited claim's; the unit stated that only in "
        "its prompt and never checked the text",
    ),
    Case(
        "value-as-text", "evidence_validator.py:5-7 (_num coerces)", "INTENTIONAL_DIFFERENCE",
        (Finding("Kávu si koupí {0} %.", (Claim("q2", "pct:Kávu", "q2.pct.1", as_text=True),)),),
        True, False, frozenset({ViolationCode.SCHEMA_INVALID}),
        why="a claim's value is a number, never text coerced into one",
    ),
    Case(
        "refused-by-fidelity", "fidelity.py:22-70 (REFUSE); evidence_validator indexes it",
        "INTENTIONAL_DIFFERENCE",
        (Finding("Málo by zaplatilo {0} %.", (Claim("q5", "pct:Málo", "q5.pct.1"),)),),
        True, False, frozenset({ViolationCode.EVIDENCE_SUPPRESSED}),
        why="the unit rated absolute willingness to pay REFUSE and still indexed it; AIA "
        "removes the question's rows, keeping why",
    ),
    Case(
        "finding-without-evidence", "evidence_validator.py:47 (coverage >= .95)",
        "DECISION_OWED",
        (ONE, Finding("Fiktivní respondenti preferují kávu.", refs=())),
        False, True,
        why="ANL-4: the unit required 95 % of findings to cite evidence; AIA requires every "
        "number to be cited, and a finding without one to cite nothing",
    ),
    Case(
        "no-finding-at-all", "evidence_validator.py:48 (bool(findings))", "DECISION_OWED",
        (), False, True,
        why="ANL-4: the unit refused an analysis with no finding; an AIA module may be its "
        "summary alone",
    ),
)  # fmt: skip


@dataclass(frozen=True)
class Stated:
    claim: Claim
    value: Any


def _stated(case: Case, unit: ModuleType, evidence: Evidence) -> list[tuple[Finding, list[Stated]]]:
    """Each finding with the value each of its claims states, from the evidence itself."""
    index = unit.build_evidence_index(evidence.summary)
    out = []
    for f in case.findings:
        stated = []
        for c in f.claims:
            base = unit.resolve_metric(index, c.qid, c.metric)
            value = round((40.8 if base is None else base) + c.delta, 6)
            stated.append(Stated(c, str(value) if c.as_text else value))
        out.append((f, stated))
    return out


def _prose(f: Finding, stated: list[Stated]) -> str:
    return f.text.format(*(f"{float(s.value):g}".replace(".", ",") for s in stated))


def _unit_analysis(resolved: list[tuple[Finding, list[Stated]]]) -> dict[str, Any]:
    return {
        "key_findings": [
            {
                "text": _prose(f, stated),
                "evidence_refs": list(f.refs if f.refs is not None else {c.qid for c in f.claims}),
                "numeric_claims": [
                    {"evidence_ref": s.claim.qid, "metric": s.claim.metric, "value": s.value}
                    for s in stated
                ],
            }
            for f, stated in resolved
        ]
    }


def _aia_draft(resolved: list[tuple[Finding, list[Stated]]], evidence: Evidence) -> dict[str, Any]:
    rows = evidence.native.table.rows
    claims: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for f, stated in resolved:
        ids = []
        for s in stated:
            claim_id = f"c{len(claims) + 1}"
            row = rows.get(s.claim.ref)
            claims.append(
                {
                    "claim_id": claim_id,
                    "evidence_ref": s.claim.ref,
                    "metric": str(row.metric) if row else s.claim.metric,
                    "value": s.value,
                    "unit": row.unit.value if row else "%",
                }
            )
            ids.append(claim_id)
        findings.append({"text": _prose(f, stated), "claim_ids": ids})
    return {
        "module": AnalysisModuleId.EXECUTIVE.value,
        "summary": "Shrnutí fiktivních odpovědí.",
        "key_findings": findings,
        "numeric_claims": claims,
    }


@pytest.mark.parametrize("case", CASES, ids=[c.case_id for c in CASES])
def test_the_decision_against_the_units(case: Case, unit: ModuleType, evidence: Evidence) -> None:
    resolved = _stated(case, unit, evidence)
    unit_result = unit.validate_analysis(_unit_analysis(resolved), evidence.summary)
    assert unit_result["passed"] is case.unit_passes, (case.source, unit_result["issues"])
    check = check_analysis_draft(
        _aia_draft(resolved, evidence),
        module_spec(AnalysisModuleId.EXECUTIVE),
        evidence.native.table,
        book=evidence.native.book,
        joint_status=evidence.native.joint_status,
        surface=ClaimSurface.INTERNAL,
        research_questions=(),
    )
    assert check.decision.allowed is case.aia_allows, check.decision.violations
    assert case.aia_codes <= check.decision.codes, check.decision.violations


def test_every_case_is_labelled_by_what_it_shows() -> None:
    assert len({c.case_id for c in CASES}) == len(CASES)
    for case in CASES:
        assert case.source
        assert case.aia_allows == (not case.aia_codes), case.case_id
        if case.parity == "EXACT":
            assert case.unit_passes == case.aia_allows, case.case_id
        elif case.parity == "INTENTIONAL_DIFFERENCE":
            assert case.unit_passes and not case.aia_allows and case.why, case.case_id
        else:
            assert not case.unit_passes and case.aia_allows, case.case_id
            assert case.why.startswith("ANL-"), "a looser decision names what it waits on"


def test_aia_admits_nothing_the_unit_refused_but_what_waits_on_a_decision() -> None:
    looser = [c.case_id for c in CASES if c.aia_allows and not c.unit_passes]
    assert looser == [c.case_id for c in CASES if c.parity == "DECISION_OWED"]
