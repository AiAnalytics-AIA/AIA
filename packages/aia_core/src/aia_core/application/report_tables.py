"""Every question's numbers as tables in the internal report (complete-study-report B1a).

The analysis modules cite the rows they chose; a reader of the complete report also needs
every question's answers. Those rows are already in the run's evidence table
(``native_evidence``: one row per option share, scale mean and top-2-box). Nothing here
computes a number: each row is cited back through ``admit_numeric_claims`` -- the only way a
number becomes printable -- and the table holds refs into the report's ledger, so the
renderer applies suppression, intervals and print grades as everywhere else.

Admission is all or nothing per call, so it runs once per question: a question the gate
refuses is named, with the gate's reasons, and the other questions keep their tables.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from aia_core.application.analysis_results import RunAnalysis
from aia_core.domain.analysis import AnalysisModuleId
from aia_core.domain.evidence import (
    AdmittedClaim,
    ClaimSurface,
    EvidenceTable,
    FieldPolicyBook,
    JointStatus,
)
from aia_core.domain.evidence.admission import NumericClaim, admit_numeric_claims
from aia_core.domain.evidence.instrument import InstrumentItem
from aia_core.domain.report.model import (
    Align,
    Block,
    Callout,
    CalloutKind,
    Column,
    NumberCell,
    Paragraph,
    Section,
    Table,
    TableRow,
    TextCell,
    text,
)

#: The suffixes ``native_evidence`` gives a question's rows, in the order a table prints them
#: (the estimates, then the counts behind them), and how a table names a row that was
#: suppressed and left only its ref.
_ROW_ORDER = ("pct.", "mean", "top2box", "n", "effective_n")
_SUFFIX_LABEL = {
    "mean": "průměr",
    "top2box": "podíl dvou nejvyšších bodů",
    "n": "platné odpovědi",
    "effective_n": "efektivní n",
}


@dataclass(frozen=True, slots=True)
class QuestionTables:
    """The chapter of question tables and the claims its cells stand on."""

    sections: tuple[Section, ...]
    claims: tuple[AdmittedClaim, ...]
    #: Questions whose numbers the gate refused, with its reasons.
    refused: tuple[tuple[str, tuple[str, ...]], ...] = ()


def _order(ref: str, question_id: str) -> tuple[int, int]:
    """Option shares in the questionnaire's order, the mean, the top-2-box, then the counts."""
    suffix = ref.removeprefix(f"{question_id}.")
    if suffix.startswith("pct."):
        return (0, int(suffix.removeprefix("pct.")))
    return (_ROW_ORDER.index(suffix) if suffix in _ROW_ORDER else len(_ROW_ORDER), 0)


def _label(ref: str, question_id: str, detail: str | None) -> str:
    if detail:
        return detail
    suffix = ref.removeprefix(f"{question_id}.")
    if suffix.startswith("pct."):
        return f"odpověď {suffix.removeprefix('pct.')}"
    return _SUFFIX_LABEL.get(suffix, suffix)


def compose_question_tables(
    run: RunAnalysis, items: Sequence[InstrumentItem], *, source: str
) -> QuestionTables:
    """One table per question in ``items`` order, over the run's own evidence table.

    ``items`` are the questions the run's specification asked (``native_items``): their order
    and wording. A question with no row and no suppressed ref in the table has no table.
    """
    executive = run.modules.get(AnalysisModuleId.EXECUTIVE)
    if executive is None:
        raise ValueError("the run's analysis has no executive module to read its evidence from")
    inputs = executive.inputs
    return question_tables(
        inputs.table,
        items,
        book=inputs.book,
        joint_status=inputs.joint_status,
        source=source,
        surface=ClaimSurface.INTERNAL,
    )


def question_tables(
    table: EvidenceTable,
    items: Sequence[InstrumentItem],
    *,
    book: FieldPolicyBook,
    joint_status: JointStatus,
    source: str,
    surface: ClaimSurface,
) -> QuestionTables:
    """The question tables over ``table``, every cell admitted for ``surface``.

    Internal, a question the gate refuses is named with the gate's reasons. Client-facing, it
    is left out and the chapter says only how many were: the reasons are internal terms.
    """
    known = set(table.rows) | set(table.suppressed)

    blocks: list[Block] = [
        Paragraph(
            text(
                "Tato kapitola uvádí výsledky každé otázky dotazníku a každého hodnoceného "
                "objektu: podíly odpovědí, u škál průměr a podíl dvou nejvyšších bodů, vždy "
                "s 95% intervalem. Hodnoty s nedostatečnou oporou se neuvádějí; tabulka "
                "pod sebou říká, kolik jich vynechala."
            )
        )
    ]
    claims: list[AdmittedClaim] = []
    refused: list[tuple[str, tuple[str, ...]]] = []
    for index, item in enumerate(items, start=1):
        qid = item.question_id
        refs = sorted((r for r in known if r.startswith(f"{qid}.")), key=lambda r: _order(r, qid))
        if not refs:
            continue
        kept = [r for r in refs if r in table.rows]
        admission = admit_numeric_claims(
            [
                NumericClaim(
                    claim_id=f"tab:{ref}",
                    evidence_ref=ref,
                    metric=str(table.rows[ref].metric),
                    value=table.rows[ref].value,
                    unit=table.rows[ref].unit.value,
                )
                for ref in kept
            ],
            table,
            book=book,
            joint_status=joint_status,
            surface=surface,
        )
        if kept and not admission.decision.allowed:
            reasons = tuple(f"{v.code}: {v.detail}" for v in admission.decision.violations)
            refused.append((qid, reasons))
            if surface is ClaimSurface.CLIENT_FACING:
                continue
            blocks.append(
                Callout(
                    CalloutKind.LIMITATION,
                    text(
                        f"Otázku „{item.text}“ zpráva neuvádí: její čísla neprošla kontrolou "
                        f"evidence ({'; '.join(reasons)})."
                    ),
                )
            )
            continue
        claims.extend(admission.admitted)
        rows = []
        for ref in refs:
            row = table.rows.get(ref)
            detail = row.cell.split(" | ", 1)[1] if row is not None and " | " in row.cell else None
            rows.append(TableRow((TextCell(_label(ref, qid, detail)), NumberCell(ref, True))))
        blocks.append(
            Table(
                id=f"tab-question-{index}",
                title=item.text,
                columns=(
                    Column("Ukazatel", width_weight=3),
                    Column("Hodnota (95% interval)", align=Align.RIGHT, width_weight=2),
                ),
                rows=tuple(rows),
                source=source,
                base_ref=kept[0] if kept else None,
            )
        )
    if surface is ClaimSurface.CLIENT_FACING and refused:
        blocks.append(
            Callout(
                CalloutKind.LIMITATION,
                text(
                    f"Výsledky {len(refused)} otázek zpráva neuvádí: jejich čísla nesplnila "
                    "pravidla, za nichž lze modelovaná čísla předat klientovi."
                ),
            )
        )
    section = Section("Výsledky jednotlivých otázek", tuple(blocks), id="ch-questions")
    return QuestionTables((section,), tuple(claims), tuple(refused))
