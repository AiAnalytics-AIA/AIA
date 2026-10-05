"""The AI respondent: its agent definition, prompt, output contract and answer handling.

The ``ai_runtime`` fieldwork source (ADR 0016 decision 4) in its pure part. The
division of labour is 18.6.6's (``dotaznik.py:106-356``), and it is the whole design:

* the **model** is shown one persona and a short block of questions and returns,
  per question, only what its contract permits -- a probability vector over the
  options or scale points, a set of chosen options, or a short open answer;
* **code** answers every fact the persona already has (:mod:`.respondent_facts`),
  refuses an individual fact it does not have, validates the model's output
  strictly, applies the response process (:mod:`.respondent_behavior`) and draws
  the final answer with a seeded generator;
* **nothing** the model returns is an id, a weight, a donor, a fact or a statistic:
  those come from the persona and from Aggregate, which reads only the dataset.

This module builds requests and reads answers. It never calls anything: the
fieldwork executor sends each request through ``GovernedModelGateway``.

**Personas are fictional here.** :func:`fictional_roster` invents respondents from
``random.Random(seed)``; their lineage is AIA's fictional fixture dataset, the one
determination that approves transmission (``licence_determinations``). A persona
from the population panel would derive from PIAAC, ISSP and the Czech panel, which
OI-61 leaves UNDETERMINED: the licence gate refuses it before any adapter, and this
PR builds no such persona.

Pure: stdlib and Pydantic.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, create_model

from .ai_contracts import AgentDefinition, Message, ModelRequest
from .ai_models import ModelCapability
from .fieldwork import (
    DATASET_VERSION,
    Answer,
    DataOrigin,
    FieldworkDataset,
    FieldworkRespondent,
    FieldworkSource,
)
from .licence import DataLineage
from .licence_determinations import SYNTHETIC_FIXTURE_DATASET
from .research_design import ResearchSpecification, SpecQuestion
from .residency import DataClass
from .respondent_behavior import (
    EDUCATION_ORDER,
    STYLES,
    ResponseQuestion,
    adjust_probabilities,
    assign_styles,
    draw_index,
)
from .respondent_facts import (
    FactStatus,
    UnansweredFact,
    classify_question,
    deterministic_answer,
)

__all__ = [
    "AGENT_ID",
    "AGENT_VERSION",
    "CONTRACT_VERSION",
    "GENERATOR",
    "MAX_BLOCK_ITEMS",
    "OPEN_TEXT_LIMIT",
    "PROMPT_ID",
    "PROMPT_SHA256",
    "PROMPT_VERSION",
    "ROSTER_VERSION",
    "SYSTEM_PROMPT",
    "Block",
    "Item",
    "Persona",
    "RespondentOutputInvalid",
    "RespondentPlan",
    "UnsupportedFact",
    "assemble_dataset",
    "block_contract",
    "build_request",
    "classify_material",
    "fictional_roster",
    "interpret_block",
    "plan_items",
    "plan_respondent",
    "respondent_agent",
]

AGENT_ID: Final = "aia.research.respondent"
AGENT_VERSION: Final = "1"
PROMPT_ID: Final = "aia.respondent.block"
PROMPT_VERSION: Final = "1"
CONTRACT_VERSION: Final = "aia-respondent-contract-1"
GENERATOR: Final = "aia-ai-respondent-1"
ROSTER_VERSION: Final = "aia-fictional-roster-1"

#: ``build_dotaznik_block_kw`` takes 2-8 questions per block; AIA takes 1-8 closed
#: items per block, and asks every open question alone, as the unit does.
MAX_BLOCK_ITEMS: Final = 8
#: ``_response_tool``'s open-answer limit.
OPEN_TEXT_LIMIT: Final = 600

#: The system prompt, from ``dotaznik.SYSTEM_DOT_BLOCK`` (18.6.6), reworded for AIA's
#: contract: fictional personas, one block, the submit tool. A change to this text is
#: a new PROMPT_VERSION; its SHA-256 is on every dataset built with it.
SYSTEM_PROMPT: Final = """Jsi respondent v sekvenčním výzkumu. Dostaneš profil JEDNOHO člověka, \
jeho dřívější odpovědi v tomto rozhovoru a krátký blok aktuálních otázek. Odpovídej jako \
tento člověk, nikoli jako průměrný Čech.

Pravidla:
- Otázky řeš přesně v uvedeném pořadí. Odpověď na pozdější otázku nesmí zpětně změnit \
odpověď na dřívější otázku.
- Používej jen informace v profilu a v předchozích odpovědích; nevymýšlej další životní \
fakta ani populační distribuce.
- Pravděpodobnosti popisují nejistotu TOHOTO respondenta, ne celé populace. Nevybírej \
finální možnost: odpověď vylosuje runtime.
- Řádek „Jak odpovídá v dotaznících“ popisuje styl odpovídání, ne názory.
- U otevřené otázky piš krátkou mluvenou češtinou.
- Vrať přesně jeden strukturovaný objekt s odpovědí pro každé ID otázky, nic dalšího.

Výsledek odešli pouze přes nástroj pro odeslání odpovědi."""

PROMPT_SHA256: Final = hashlib.sha256(SYSTEM_PROMPT.encode("utf-8")).hexdigest()


class UnsupportedFact(ValueError):
    """A question asks for an individual fact no persona carries. Fieldwork refuses."""


class RespondentOutputInvalid(ValueError):
    """The model's answer passed the schema but not the deterministic checks."""


# --------------------------------------------------------------------------- #
# Personas
# --------------------------------------------------------------------------- #


class Persona(BaseModel):
    """One respondent as the model is shown it, and as the dataset records it.

    ``facts`` are the respondent's own attributes, answered by code. ``lineage`` names
    the datasets the persona was computed from -- what the licence gate reads.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    persona_id: str
    donor_id: str
    weight: float = Field(gt=0)
    facts: dict[str, str | int]
    style: dict[str, float]
    lineage: frozenset[str]
    fictional: bool

    def profile(self) -> str:
        """The profile text shown to the model: its facts and response style."""
        f = self.facts
        lines = [
            "FIKTIVNÍ RESPONDENT: smyšlená persona pro test, ne skutečný člověk.",
            f"Pohlaví: {f.get('pohlavi', 'neuvedeno')}; věk: {f.get('vek', 'neuvedeno')}; "
            f"vzdělání: {f.get('vzdelani', 'neuvedeno')}; kraj: {f.get('kraj', 'neuvedeno')}.",
        ]
        described = describe_style(self.style)
        if described:
            lines.append(f"Jak odpovídá v dotaznících: {described}.")
        return "\n".join(lines)


#: ``styly.POPISY``: (high, low) wording per style, shown only when pronounced.
_STYLE_WORDS: Final[dict[str, tuple[str, str]]] = {
    "souhlasny_sklon": (
        "má sklon souhlasit s tím, co mu tazatel nabídne, i když o tom moc nepřemýšlí",
        "nenechá se zatlačit do souhlasu, spíš odmítá",
    ),
    "vyhranenost": (
        "volí krajní hodnoty škál, málokdy střed",
        "drží se středu škál, krajní hodnoty nepoužívá",
    ),
    "ochota_priznat_nevim": (
        "když něco neví, klidně to řekne",
        "nerad přiznává, že něco neví — radši si názor dotvoří na místě",
    ),
    "sdilnost": (
        "u otevřených otázek mluví, rozvede to",
        "u otevřených otázek odbude odpověď pár slovy",
    ),
    "satisficing": (
        "u delších dotazníků má sklon odpovídat úsporně a méně promýšlet každou položku",
        "i delší dotazník vyplňuje soustředěně",
    ),
    "social_desirability_sensitivity": (
        "u citlivých témat hlídá, jak jeho odpověď působí",
        "u citlivých témat se méně řídí tím, co zní společensky žádoucí",
    ),
}


def describe_style(style: Mapping[str, float], threshold: float = 0.7) -> str:
    """``styly.popis_stylu``: only the pronounced sides of a style, joined by '; '."""
    parts: list[str] = []
    for name in STYLES:
        value = float(style.get(name, 0.0))
        if value >= threshold:
            parts.append(_STYLE_WORDS[name][0])
        elif value <= -threshold:
            parts.append(_STYLE_WORDS[name][1])
    return "; ".join(parts)


_REGIONS: Final = (
    "Hlavní město Praha",
    "Středočeský kraj",
    "Jihočeský kraj",
    "Plzeňský kraj",
    "Karlovarský kraj",
    "Ústecký kraj",
    "Liberecký kraj",
    "Královéhradecký kraj",
    "Pardubický kraj",
    "Kraj Vysočina",
    "Jihomoravský kraj",
    "Olomoucký kraj",
    "Zlínský kraj",
    "Moravskoslezský kraj",
)


def fictional_roster(n: int, *, seed: int) -> tuple[Persona, ...]:
    """``n`` invented respondents, the same for the same ``(n, seed)`` on any host.

    Attributes are drawn uniformly from ``random.Random(seed)``: they are not a
    sample of any population, and a map drawn from their answers is not a finding.
    Styles are ``styly.prirad_styly``'s over this roster.
    """
    if n < 1:
        raise ValueError("a roster needs at least one respondent")
    rng = random.Random(seed)
    education = tuple(EDUCATION_ORDER)
    rows: list[dict[str, Any]] = []
    for i in range(n):
        rows.append(
            {
                "respondent_id": f"FIC-R{i + 1:05d}",
                "pohlavi": rng.choice(("muž", "žena")),
                "vek": rng.randint(18, 89),
                "vzdelani": rng.choice(education),
                "kraj": rng.choice(_REGIONS),
            }
        )
    donors = max(3, n // 3)
    styles = assign_styles(rows)
    return tuple(
        Persona(
            persona_id=row["respondent_id"],
            donor_id=f"FIC-D{rng.randrange(donors) + 1:04d}",
            weight=1.0,
            facts={k: row[k] for k in ("pohlavi", "vek", "vzdelani", "kraj")},
            style={k: round(v, 6) for k, v in style.items()},
            lineage=frozenset({SYNTHETIC_FIXTURE_DATASET}),
            fictional=True,
        )
        for row, style in zip(rows, styles, strict=True)
    )


def classify_material(
    personas: Sequence[Persona], *, client_declared_fictional: bool
) -> tuple[DataClass, DataLineage]:
    """The data class and lineage of every request built for these personas.

    Class C only when *nothing* in the request is client material: every persona is
    invented **and** the operator has declared the Study's client fictional (so its
    questionnaire is not a client's design). Anything else is Class A -- a client's
    study design is client-confidential (ADR 0008) -- and is refused by any route not
    approved for it. Unknown is never scored as internal.
    """
    lineage = DataLineage(frozenset().union(*(p.lineage for p in personas)))
    internal = client_declared_fictional and bool(personas) and all(p.fictional for p in personas)
    return (
        DataClass.CLASS_C_INTERNAL if internal else DataClass.CLASS_A_CLIENT_CONFIDENTIAL,
        lineage,
    )


# --------------------------------------------------------------------------- #
# Items and blocks
# --------------------------------------------------------------------------- #

ItemKind = Literal["choice", "scale", "multi", "open"]


@dataclass(frozen=True, slots=True)
class Item:
    """One thing a respondent answers: a question, or one object of a battery."""

    item_id: str
    kind: ItemKind
    text: str
    labels: tuple[str, ...] = ()
    scale: tuple[int, int] | None = None
    allow_dont_know: bool = False
    scale_labels: tuple[str, str] | None = None
    question: SpecQuestion | None = None

    @property
    def width(self) -> int:
        """How many probabilities (``choice``/``scale``) or options (``multi``)."""
        if self.kind == "scale":
            assert self.scale is not None
            return self.scale[1] - self.scale[0] + 1 + (1 if self.allow_dont_know else 0)
        return len(self.labels)

    def response_question(self) -> ResponseQuestion:
        return ResponseQuestion(
            typ="skala" if self.kind == "scale" else "vyber",
            labels=self.labels,
            scale=self.scale,
            allow_dont_know=self.allow_dont_know,
        )


def plan_items(spec: ResearchSpecification) -> tuple[Item, ...]:
    """Every item of the questionnaire, in order: questions, then each battery's objects."""
    items: list[Item] = []
    for q in spec.questions:
        if q.typ == "vyber":
            items.append(
                Item(
                    q.id, "choice", q.text, q.options, allow_dont_know=q.allow_dont_know, question=q
                )
            )
        elif q.typ == "multi":
            items.append(Item(q.id, "multi", q.text, q.options, question=q))
        elif q.typ == "skala":
            items.append(
                Item(
                    q.id,
                    "scale",
                    q.text,
                    scale=q.scale,
                    allow_dont_know=q.allow_dont_know,
                    question=q,
                )
            )
        else:
            items.append(Item(q.id, "open", q.text, question=q))
    for b in spec.batteries:
        for o in b.objects:
            items.append(
                Item(
                    b.question_id(o),
                    "scale",
                    b.question_template.replace("{object}", o.label),
                    scale=b.scale,
                    scale_labels=b.scale_labels,
                )
            )
    return tuple(items)


@dataclass(frozen=True, slots=True)
class Block:
    """The items one call asks, in questionnaire order."""

    index: int
    items: tuple[Item, ...]


@dataclass(frozen=True, slots=True)
class RespondentPlan:
    """What code answers for a persona, and what the model is asked, block by block."""

    persona: Persona
    facts: dict[str, Answer] = field(default_factory=dict)
    blocks: tuple[Block, ...] = ()


def plan_respondent(spec: ResearchSpecification, persona: Persona) -> RespondentPlan:
    """Split the questionnaire into facts (code) and blocks (model). Refuses a lacking fact."""
    fields = set(persona.facts)
    facts: dict[str, Answer] = {}
    asked: list[Item] = []
    for item in plan_items(spec):
        if item.question is not None:
            fact = classify_question(item.question, fields)
            if fact.status is FactStatus.UNSUPPORTED:
                raise UnsupportedFact(f"{item.item_id}: {fact.reason}")
            if fact.status is FactStatus.DIRECT:
                try:
                    facts[item.item_id] = deterministic_answer(item.question, persona.facts, fact)
                except UnansweredFact as exc:
                    raise UnsupportedFact(str(exc)) from exc
                continue
        asked.append(item)

    return RespondentPlan(persona=persona, facts=facts, blocks=split_blocks(asked))


def split_blocks(asked: Sequence[Item]) -> tuple[Block, ...]:
    """The calls that ask these items: closed ones together up to a limit, each open one alone."""
    blocks: list[Block] = []
    closed: list[Item] = []

    def flush() -> None:
        if closed:
            blocks.append(Block(len(blocks), tuple(closed)))
            closed.clear()

    for item in asked:
        if item.kind == "open":
            flush()
            blocks.append(Block(len(blocks), (item,)))
            continue
        closed.append(item)
        if len(closed) == MAX_BLOCK_ITEMS:
            flush()
    flush()
    return tuple(blocks)


def max_blocks_per_respondent(spec: ResearchSpecification) -> int:
    """The most calls one respondent can need: every item asked, none answered by code.

    Which items code answers from a persona's facts differs by persona, and answering one only
    removes it, so asking them all is an upper bound that holds for every persona.
    """
    return len(split_blocks(plan_items(spec)))


# --------------------------------------------------------------------------- #
# The output contract and the agent
# --------------------------------------------------------------------------- #

_CLOSED: Final = ConfigDict(extra="forbid", frozen=True)
_Probability = Annotated[float, Field(ge=0.0, le=1.0)]


def _probabilities_model(width: int) -> type[BaseModel]:
    return create_model(
        f"Probabilities{width}",
        __config__=_CLOSED,
        probabilities=(
            Annotated[list[_Probability], Field(min_length=width, max_length=width)],
            ...,
        ),
    )


def _selection_model(width: int) -> type[BaseModel]:
    return create_model(
        f"Selection{width}",
        __config__=_CLOSED,
        selected=(
            Annotated[list[Annotated[int, Field(ge=1, le=width)]], Field(max_length=width)],
            ...,
        ),
    )


def _open_model() -> type[BaseModel]:
    return create_model(
        "OpenAnswer",
        __config__=_CLOSED,
        text=(Annotated[str, Field(min_length=1, max_length=OPEN_TEXT_LIMIT)], ...),
    )


def block_contract(block: Block) -> type[BaseModel]:
    """The strict output contract for one block (``CONTRACT_VERSION``).

    One required property per asked item, keyed by the item id and nothing else: an
    unasked id, a missing one, a probability vector of the wrong length or outside
    0..1, or an option number out of range fails validation in the gateway, which
    allows the agent one repair and ledgers it as its own call.
    """
    fields: dict[str, Any] = {}
    for n, item in enumerate(block.items):
        if item.kind in ("choice", "scale"):
            model = _probabilities_model(item.width)
        elif item.kind == "multi":
            model = _selection_model(item.width)
        else:
            model = _open_model()
        fields[f"item_{n}"] = (model, Field(alias=item.item_id))
    return create_model("RespondentBlock", __config__=_CLOSED, **fields)


def respondent_agent(block: Block, *, max_output_tokens: int) -> AgentDefinition:
    """The agent for one block: its identity is fixed; its contract is the block's."""
    return AgentDefinition(
        agent_id=AGENT_ID,
        version=AGENT_VERSION,
        capability=ModelCapability.SIMULATION,
        prompt_id=PROMPT_ID,
        prompt_version=PROMPT_VERSION,
        output_contract=block_contract(block),
        max_output_tokens=max_output_tokens,
        schema_repair_attempts=1,
    )


# --------------------------------------------------------------------------- #
# The request
# --------------------------------------------------------------------------- #


def _instruction(item: Item) -> str:
    if item.kind == "choice":
        options = "\n".join(f"  {i + 1}. {label}" for i, label in enumerate(item.labels))
        return (
            f"Možnosti:\n{options}\nVrať {item.width} pravděpodobností ve stejném pořadí "
            "jako možnosti (pole probabilities); runtime je normalizuje a odpověď vylosuje."
        )
    if item.kind == "scale":
        assert item.scale is not None
        low, high = item.scale
        ends = (
            f" ({low} = {item.scale_labels[0]}, {high} = {item.scale_labels[1]})"
            if item.scale_labels
            else ""
        )
        tail = " a poslední pro „nevím“" if item.allow_dont_know else ""
        return (
            f"Škála {low} až {high}{ends}. Vrať pravděpodobnosti pro hodnoty {low} až {high}"
            f"{tail} ve vzestupném pořadí ({item.width} čísel, pole probabilities)."
        )
    if item.kind == "multi":
        options = "\n".join(f"  {i + 1}. {label}" for i, label in enumerate(item.labels))
        return f"Možnosti:\n{options}\nVrať čísla všech možností, které by zvolil (pole selected)."
    return f"Odpověz krátce vlastními slovy, nejvýše {OPEN_TEXT_LIMIT} znaků (pole text)."


def _history(answers: Mapping[str, Answer], items: Mapping[str, Item]) -> str:
    if not answers:
        return "(žádné)"
    lines = []
    for item_id, answer in answers.items():
        text = items[item_id].text if item_id in items else item_id
        shown = (
            "nevím"
            if answer is None
            else (", ".join(answer) if isinstance(answer, list) else answer)
        )
        lines.append(f"- {text} → {shown}")
    return "\n".join(lines)


def build_request(
    plan: RespondentPlan,
    block: Block,
    answers_so_far: Mapping[str, Answer],
    *,
    items_by_id: Mapping[str, Item],
    policy_version: str,
    data_class: DataClass,
    lineage: DataLineage,
    max_output_tokens: int,
) -> ModelRequest:
    """One respondent's request for one block. Scope is never in it; class and lineage are."""
    sections = [
        f"OTÁZKA {pos}/{len(block.items)} (ID {item.item_id})\n{item.text}\n{_instruction(item)}"
        for pos, item in enumerate(block.items, 1)
    ]
    content = (
        "PROFIL RESPONDENTA:\n"
        + plan.persona.profile()
        + "\n\nPŘEDCHOZÍ ODPOVĚDI V TOMTO ROZHOVORU:\n"
        + _history(answers_so_far, items_by_id)
        + "\n\n"
        + "\n\n".join(sections)
    )
    return ModelRequest(
        agent=respondent_agent(block, max_output_tokens=max_output_tokens),
        policy_version=policy_version,
        data_classification=data_class,
        data_lineage=lineage,
        system=SYSTEM_PROMPT,
        messages=(Message(role="user", content=content),),
        temperature=0.0,
    )


# --------------------------------------------------------------------------- #
# Reading the answer
# --------------------------------------------------------------------------- #


def item_seed(seed: int, persona_id: str, item_id: str) -> int:
    """The draw's seed for one respondent and item: stable, and independent per item."""
    digest = hashlib.sha256(f"{seed}:{persona_id}:{item_id}".encode()).hexdigest()
    return int(digest[:16], 16)


def interpret_block(
    block: Block,
    output: BaseModel,
    persona: Persona,
    *,
    seed: int,
) -> tuple[dict[str, Answer], dict[str, dict[str, Any]]]:
    """The model's validated output -> final answers, drawn by code. And what was done.

    Raises :class:`RespondentOutputInvalid` for an answer the schema could not refuse:
    a probability vector with no mass. There is no repair here and no blank answer:
    the attempt fails and says which item.
    """
    # The contract class is rebuilt per request, so compare its fields, not its type.
    if set(type(output).model_fields) != {f"item_{n}" for n in range(len(block.items))}:
        raise RespondentOutputInvalid("the output is not this block's contract")
    answers: dict[str, Answer] = {}
    meta: dict[str, dict[str, Any]] = {}
    for n, item in enumerate(block.items):
        part = getattr(output, f"item_{n}")
        if item.kind in ("choice", "scale"):
            raw = list(part.probabilities)
            try:
                probs, behavior = adjust_probabilities(raw, item.response_question(), persona.style)
            except ValueError as exc:
                raise RespondentOutputInvalid(f"{item.item_id}: {exc}") from exc
            index = draw_index(probs, item_seed(seed, persona.persona_id, item.item_id))
            if item.kind == "choice":
                answers[item.item_id] = item.labels[index]
            else:
                assert item.scale is not None
                points = item.scale[1] - item.scale[0] + 1
                answers[item.item_id] = None if index >= points else item.scale[0] + index
            meta[item.item_id] = {
                "raw_probabilities": raw,
                "probabilities": [round(p, 6) for p in probs],
                "behavior": list(behavior.applied),
                "behavior_l1": behavior.l1_shift,
            }
        elif item.kind == "multi":
            chosen = list(dict.fromkeys(item.labels[i - 1] for i in part.selected))
            # dotaznik._parse_response: an empty selection is no answer, not "none".
            answers[item.item_id] = chosen or None
            meta[item.item_id] = {"selected": list(part.selected)}
        else:
            answers[item.item_id] = str(part.text).strip()[:OPEN_TEXT_LIMIT] or None
            meta[item.item_id] = {"open": True}
    return answers, meta


def assemble_dataset(
    spec: ResearchSpecification,
    respondents: Sequence[tuple[Persona, Mapping[str, Answer]]],
    *,
    seed: int,
) -> FieldworkDataset:
    """The fieldwork dataset: ids, weights and donors from the personas, answers drawn."""
    origin = DataOrigin.SYNTHETIC_AI_FICTIONAL if all(p.fictional for p, _ in respondents) else None
    if origin is None:
        # No persona source other than the fictional roster exists; one that did
        # would need its own origin decided, not a default.
        raise ValueError("only fictional personas are supported by this generator")
    return FieldworkDataset(
        dataset_version=DATASET_VERSION,
        source=FieldworkSource.AI_RUNTIME,
        origin=origin,
        spec_fingerprint=spec.fingerprint(),
        seed=seed,
        generator=GENERATOR,
        respondents=tuple(
            FieldworkRespondent(
                respondent_id=persona.persona_id,
                donor_id=persona.donor_id,
                weight=persona.weight,
                answers=dict(answers),
            )
            for persona, answers in respondents
        ),
    )
