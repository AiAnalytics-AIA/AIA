"""The independent verifier: its closed contract and its prompt (plan § 8.4, chunk 12).

Plan ``deep-research-web-search.md`` § 5.2 and § 8.4. In the agent-directed mode every
candidate the brief could use is attacked by a verifier that sees none of the
investigator's reasoning: the claim, its quote, the quote's context in the source,
the measure of every number the claim states, what code established about the source
(its publisher, primary or secondary), and the other figures the same publisher was
captured giving. It tries to break the finding -- a wrong attribute, an overstated
generalisation, a newer figure, a different denominator, preliminary data -- and says
which attacks it tried.

It is an agent of its own (``aia.deep_research.independent_verifier``, prompt
:data:`VERIFIER_PROMPT_VERSION`, contract :data:`VERIFIER_CONTRACT_VERSION`) rather
than a second prompt version of the planned mode's verifier: it answers in another
contract, with a fourth verdict, ``superseded``, and a stored call names an agent id
and a prompt version that must say unambiguously what shape came back. The planned
mode's verifier, its contract and its prompt are unchanged.

What the verifier says is a proposal. Code decides (:mod:`.verification`): a
``superseded`` verdict stands only when it names a captured figure from the same
publisher that is itself verified and is not older by the measures; a proposed search
is a typed lead, sent later, if ever, through the gate like every other call.

Every field is required (``null`` where it may be empty), so the schema is
strict-compatible. The prompt is rendered from the enums it names.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "MAX_JUDGEMENTS",
    "VERIFIER_CONTRACT_VERSION",
    "VERIFIER_PROMPT_VERSION",
    "VERIFIER_TASK",
    "Attack",
    "ClaimJudgement",
    "ClaimVerdict",
    "Verification",
    "VerifierSearch",
]

#: The independent verifier's own prompt version.
VERIFIER_PROMPT_VERSION: Final = "1"

#: The independent verifier's output contract, :class:`Verification`.
VERIFIER_CONTRACT_VERSION: Final = "verification-2"

#: At most this many judgements in one answer (one per candidate of a batch).
MAX_JUDGEMENTS: Final = 40


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


_Id = Annotated[str, Field(min_length=1, max_length=100)]
_Line = Annotated[str, Field(min_length=1, max_length=300)]


class ClaimVerdict(StrEnum):
    """What the independent verifier says of one finding."""

    #: The quote and its context support the claim with every attribute of its measures.
    SUPPORTED = "supported"
    #: The claim says more than the quote: a part made a whole, a year made a trend.
    OVERSTATED = "overstated"
    #: The quote does not support the claim, or a measure is not the source's.
    UNSUPPORTED = "unsupported"
    #: A newer figure of the same measure from the same publisher was captured.
    SUPERSEDED = "superseded"


class Attack(StrEnum):
    """The ways a verifier tries to break a finding (plan § 8.4)."""

    WRONG_ATTRIBUTE = "wrong_attribute"
    OVERSTATED_GENERALISATION = "overstated_generalisation"
    NEWER_FIGURE = "newer_figure"
    DIFFERENT_DENOMINATOR = "different_denominator"
    PRELIMINARY_DATA = "preliminary_data"


class VerifierSearch(_Closed):
    """A search the verifier proposes for a newer or a primary figure. Code decides."""

    query: str = Field(min_length=3, max_length=200)
    #: The publisher the figure should come from, as the verifier names it, or null.
    publisher: str | None = Field(max_length=200)
    why: _Line


class ClaimJudgement(_Closed):
    """One finding judged: the verdict, the attacks tried, and why."""

    evidence_id: _Id
    verdict: ClaimVerdict
    attacks: list[Attack] = Field(max_length=len(Attack))
    #: For ``superseded``: the ``evidence_id`` of the newer figure, from ``related``.
    superseded_by: str | None = Field(max_length=100)
    search: VerifierSearch | None
    reason: str = Field(max_length=500)


class Verification(_Closed):
    """The independent verifier's answer for one batch."""

    judgements: list[ClaimJudgement] = Field(max_length=MAX_JUDGEMENTS)


def _values(enum: Iterable[StrEnum]) -> str:
    return ", ".join(f"'{m.value}'" for m in enum)


_V = ClaimVerdict

#: The verifier's task, after the common preamble (``agents.prompt_for``).
VERIFIER_TASK: Final = f"""Jsi nezávislý ověřovatel zjištění. Nevidíš úvahy výzkumníka, který
zjištění navrhl, a nepřebíráš jeho závěry: tvým úkolem je zjištění vyvrátit, pokud to jde.
U každého zjištění (items) dostaneš tvrzení (claim), doslovnou citaci (quote), okolí citace ve
zdroji (excerpt), míry čísel tvrzení (measures: value, unit, scale, period, geography,
population, denominator, measure_name, basis), vydavatele zdroje a to, zda ho aplikace
považuje za primární zdroj čísla (source), a další zachycené údaje téhož vydavatele
(related). Posuzuj jen podle dodaného textu, nikdy podle své paměti.
Zkus tyto útoky (attacks) a uveď, které jsi zkusil: {_values(Attack)}. Chybný atribut je
jiná jednotka, řád, období, území nebo populace, než uvádí zdroj; nepřiměřené zobecnění je
tvrzení o celku, trendu nebo všech lidech, když citace mluví o části, jednom roce nebo
domácnostech; jiný jmenovatel je podíl z jiného základu; předběžný údaj je údaj, který zdroj
sám označuje za předběžný nebo odhad.
Verdikty (verdict): '{_V.SUPPORTED.value}' -- citace a její okolí tvrzení plně podporují
včetně všech atributů měr; '{_V.OVERSTATED.value}' -- tvrzení říká víc, než citace
(zobecnění z části na celek, z jednoho období na vývoj, z domácností na osoby);
'{_V.UNSUPPORTED.value}' -- citace tvrzení nepodporuje nebo míra neodpovídá zdroji;
'{_V.SUPERSEDED.value}' -- mezi related je novější údaj téhož ukazatele od téhož vydavatele
(novější období, nebo konečný údaj místo předběžného); jeho evidence_id uveď do superseded_by.
Bez superseded_by z related aplikace verdikt '{_V.SUPERSEDED.value}' nepřijme; u ostatních
verdiktů je superseded_by null.
Chybí-li ti novější nebo primární údaj, který by zjištění potvrdil nebo vyvrátil, navrhni
hledání (search: query, publisher nebo null, why); jinak je search null. Hledání provede
aplikace, pokud vůbec, ne ty.
Pro každé zadané evidence_id vrať právě jeden posudek (judgements) se stručným důvodem
(reason)."""
