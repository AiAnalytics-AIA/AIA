"""The owner's lift of modelled evidence into the client report (complete-study-report B5b).

ADR 0024 §4 keeps a modelled number (``MODELLED_AI_PANEL``, instrument policy ``-2``)
``INTERNAL_ONLY`` until a holdout validation of the respondent system lifts it. None has run.
The owner decided on 2026-10-13 to admit modelled numbers to the **client report** before it
does, every one labelled as modelled. This is that decision as data: a named, dated record a
reader can find and a change can revoke, never a default and never a flag a caller sets.

What it lifts, and only that: ``INTERNAL_ONLY`` on the ``-2`` items of a modelled run that
recorded its respondent system, when the client report's composer judges them. Nothing else
moves. Support and its suppression, the interval a client estimate needs, the population's
joint certificate (B5a), the modelled disclosure on every number and the refusal of any
predictive-validity claim all still apply; simulated respondents are never evidence; and the
client-facing analysis modules, which never pass the lift, stay blocked until a holdout.
"""

from __future__ import annotations

from datetime import date
from typing import Final

from pydantic import BaseModel, ConfigDict, Field


class ModelledReportLift(BaseModel):
    """One owner decision admitting modelled numbers to one surface."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lift_id: str = Field(min_length=1)
    surface: str = Field(min_length=1)
    decided_by: str = Field(min_length=1)
    decided_on: date
    #: Where the decision is recorded, for the reader who asks why.
    record: str = Field(min_length=1)
    #: Printed in every report it admits numbers to: what the lift is and is not.
    reader_note: str = Field(min_length=1)


MODELLED_CLIENT_REPORT_LIFT: Final = ModelledReportLift(
    lift_id="owner-2026-10-13-modelled-client-report",
    surface="CLIENT_REPORT",
    decided_by="vlastník produktu",
    decided_on=date(2026, 10, 13),
    record=(
        ".planning/plans/complete-study-report.md, B5 owner decisions (2026-10-13): modelled "
        "data in the client report only, ahead of the holdout validation (ADR 0024 §4)"
    ),
    reader_note=(
        "Čísla v této zprávě jsou modelovaná: odpovídali AI respondenti sestavení z populace, "
        "nikoli skuteční lidé. Vlastník produktu 13. 10. 2026 rozhodl zařadit je do klientské "
        "zprávy dříve, než systém respondentů projde ověřením na skutečných odpovědích. "
        "Zpráva proto netvrdí, že modelované odpovědi předpovídají chování lidí."
    ),
)
