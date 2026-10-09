"""The agent-directed brief's synthesizer: its closed contract and its prompt (plan § 8.8).

Plan ``deep-research-web-search.md`` § 8.8, chunk 13. In the agent-directed mode the
brief is written per research objective from accepted findings only, and carries what
code established about them: each finding's measures, source, tier, primary or
secondary and **confidence computed by code** (:mod:`.confidence`), the conflicts with
both sides and their cause, the gaps and the acquisition gaps (:mod:`.gaps`). Code
builds every one of those parts; the synthesizer writes only prose around them: an
answer per subject citing evidence ids, a note on each conflict, the limitations and a
summary. :mod:`.brief` then checks every number the prose states against the quotes
and measures of the findings it cites, asks for one repair, and refuses what still
fails.

It is an agent of its own (``aia.deep_research.brief_synthesizer``, prompt
:data:`BRIEF_PROMPT_VERSION`, contract :data:`BRIEF_CONTRACT_VERSION`) rather than a
second prompt version of the planned mode's synthesizer: it answers in another
contract, and a stored call names an agent id and a prompt version that must say
unambiguously what shape came back. The planned mode's synthesizer, its contract and
its prompt are unchanged.

The contract has no confidence, score or quality field: the model rates nothing.
Every field is required, so the schema is strict-compatible.

Pure: stdlib and Pydantic only.
"""

from __future__ import annotations

from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "BRIEF_CONTRACT_VERSION",
    "BRIEF_PROMPT_VERSION",
    "BRIEF_TASK",
    "BriefAnswerDraft",
    "BriefProposal",
    "ConflictNoteDraft",
]

#: The brief synthesizer's own prompt version.
BRIEF_PROMPT_VERSION: Final = "2"

#: The brief synthesizer's output contract, :class:`BriefProposal`.
BRIEF_CONTRACT_VERSION: Final = "brief-1"


class _Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


_Id = Annotated[str, Field(min_length=1, max_length=100)]
_Line = Annotated[str, Field(min_length=1, max_length=300)]


class BriefAnswerDraft(_Closed):
    """The answer to one research objective, citing the findings it rests on."""

    subject_key: _Id
    text: str = Field(min_length=1, max_length=1500)
    evidence_ids: list[_Id] = Field(min_length=1, max_length=10)


class ConflictNoteDraft(_Closed):
    """A note on one conflict code found: what the two values are and why they may differ."""

    conflict_id: _Id
    text: str = Field(min_length=1, max_length=800)


class BriefProposal(_Closed):
    """The brief's prose. Findings, conflicts, gaps and confidence are code's, not here."""

    summary: str = Field(min_length=1, max_length=3000)
    answers: list[BriefAnswerDraft] = Field(max_length=40)
    conflict_notes: list[ConflictNoteDraft] = Field(max_length=20)
    limitations: list[_Line] = Field(max_length=10)


def _text_bound(contract: type[BaseModel], field: str) -> int:
    """Use the same character ceiling that validates the response."""
    return int(contract.model_json_schema()["properties"][field]["maxLength"])


#: The task, after the common preamble (``agents.prompt_for``).
BRIEF_TASK: Final = f"""Z přijatých zjištění napiš českou výzkumnou zprávu, po jednotlivých
výzkumných cílech (subjects). Dostaneš zjištění (findings) s citací, mírami čísel, vydavatelem,
úrovní zdroje (T1 nejvyšší), tím, zda jde o primární zdroj čísla, a jistotou, kterou spočítala
aplikace (high, medium, low); dále rozpory (conflicts) s oběma stranami a jejich pravděpodobnou
příčinou, mezery (gaps) a zdroje, které se nepodařilo získat (acquisition_gaps).
Do answers napiš ke každému subjektu, k němuž existují zjištění, odpověď (text) a uveď
evidence_ids zjištění, o která se opírá. Každé číslo v textu musí být v citaci nebo v míře
některého uvedeného zjištění, opsané tak, jak ho zdroj uvádí; jiné číslo nepiš, ani rok, ani
počet. Údaj ze sekundárního zdroje označ jako převzatý; u údaje s nízkou jistotou to řekni slovy.
Jistotu nikdy nevyjadřuj číslem a nehodnoť ji sám: spočítala ji aplikace.
Do conflict_notes napiš ke každému rozporu (conflict_id) krátkou poznámku: obě hodnoty a
jejich vydavatele a pravděpodobnou příčinu. Hodnoty nikdy neprůměruj a nevybírej mezi nimi bez
důvodu, který uvádějí míry. Smí obsahovat jen čísla obou stran rozporu.
Do limitations napiš omezení zprávy bez čísel. Mezery a nedostupné zdroje sestaví aplikace
sama; neopakuj je. summary smí použít jen čísla ze zjištění, která citují tvoje answers.
Externí údaje nejsou výsledky panelu ani výzkumu klienta a nesmíš je tak podat.
Pokud dostaneš problems k předchozí verzi (previous), oprav právě je: číslo, které v citovaném
zjištění není, odstraň nebo doplň citaci zjištění, které ho obsahuje.

REDAKČNÍ POSTUP: vyber hlavní podloženou odpověď ke každému cíli, připoj její
nejdůležitější rozsah a omezení, potom odstraň opakování. Neopisuj zjištění po jednom
ani pracovní historii hledání. Rozliš nabídku služby, její využití a hodnocení;
žádný z těchto ukazatelů automaticky neodpovídá na ostatní. Pokud evidence cíl
nezodpoví, neschovávej to za související fakta. Odpověď bez přijaté evidence
nevytvářej; mezeru sestaví aplikace. U rozporu zachovej obě strany a vysvětli
rozdílnou definici jen pokud je doložena. Doporučení nad rámec evidence vynech.

DÉLKA JE SOUČÁST KONTRAKTU: answers[].text má tvrdý strop
{_text_bound(BriefAnswerDraft, "text")} znaků včetně mezer; míř nejvýše na 1100.
Summary má strop {_text_bound(BriefProposal, "summary")} znaků; míř na 2200.
Conflict_notes[].text má strop {_text_bound(ConflictNoteDraft, "text")} znaků;
míř na 600. Každá limitations položka má strop
{BriefProposal.model_json_schema()["properties"]["limitations"]["items"]["maxLength"]}
znaků; míř na 220.
Zkracuj myšlenky a počet vět před odesláním; nečekej, že aplikace delší text zkrátí.
Vrať pouze summary, answers, conflict_notes, limitations. Seznamy jsou vždy pole,
prázdné pole je []; answer má subject_key, text a evidence_ids přijatých zjištění.
Nepřidávej sources, confidence, gaps ani další klíče. Při opravě vrať celý výsledek
s opravou všech problémů včetně typů a délky, ne patch ani vysvětlení opravy."""
