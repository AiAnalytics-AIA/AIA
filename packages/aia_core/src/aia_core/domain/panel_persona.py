"""Panel personas: the respondents a run's sample names, as a model and the code see them.

Chunk 3e of ``plans/panel-grounded-respondents.md``. For each respondent of a
:class:`~.population.sampling.PanelSample`, a :class:`~.ai_respondent.Persona` built from the
row the sample drew, from the population the run's binding loaded, and the profile a model is
shown for each request (``persona_profile`` + ``persona_topics`` + ``persona_signals``).

What reaches the persona, and how:

* **every column through the field policy.** A column the profile, the facts or the styles read
  is used only when ``decide(column, PERSONA_CONSTRUCTION)`` allows it; a refused one is left
  out, never replaced, and the refusals are recorded (:meth:`PanelPersonas.provenance`).
* **the joint gate, as the certificate draws it.** The core fields (every dictionary block that
  is not a matched donor block) must be allowed jointly, and each matched block's fields within
  that block. Fields of different matched blocks are never presented as one person's: each
  catalog signal from a matched block carries the unit's own provenance ("statisticky
  přiřazený celý donor blok"), which is what v17's certificate permits
  (``core_same_person_joint``, ``specialist_block_internal_joint``,
  ``cross_block_same_person_joint: false``). A refusal refuses every persona
  (``persona_joint_refused``).
* **styles over the population.** 18.6.6 assigned response styles over its whole loaded panel
  (``pipeline.py:172-173``, ``styly.prirad_styly``) keyed by ``panel_row_id`` when there is no
  ``respondent_id``; :func:`~.respondent_behavior.assign_styles` is run over every row the same
  way, then read at the sampled rows.
* **facts by code.** The factual layer's fields the row holds (``respondent_facts``), as typed.

Refusals, each by name, never a narrower persona: ``persona_catalog_missing`` and
``persona_value_labels_missing`` (the companions the behavioural block reads),
``persona_compatibility_block_unported`` (a population carrying the ``P_*`` columns of 18.6.6's
older block, which is not ported), ``persona_age_out_of_scope`` (a row without an age or under 18:
the unit's panel dropped such rows before it sampled or styled, ``pipeline.py:149-152``, and AIA's
sample and styles would differ), ``persona_donor_missing``, ``persona_joint_refused``.

Pure: stdlib only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

from .ai_respondent import Block, Item, Persona, RespondentPlan, plan_respondent
from .licence_determinations import PANEL_DERIVED_DATASETS
from .persona_profile import PERSONA_MODE, PROFILE_VERSION, persona_text
from .persona_signals import (
    CATALOG_ASSET,
    VALUE_LABELS_ASSET,
    Signal,
    compatibility_columns,
    grounded_text,
    parse_catalog,
    parse_value_labels,
)
from .persona_topics import block_topics
from .population.audience import Typed, _typed, column_type
from .population.errors import PopulationError
from .population.policy import FieldUse
from .population.runtime import RuntimePopulation
from .population.sampling import DONOR_FIELD, PanelSample
from .research_design import ResearchSpecification
from .respondent_behavior import AIA_RESPONSE_V1, ResponseProcessSpec, assign_styles
from .respondent_facts import _DIRECT_PATTERNS

__all__ = [
    "MIN_AGE",
    "PANEL_PERSONA_VERSION",
    "PROFILE_COLUMNS",
    "PanelPersonas",
    "PersonaRefused",
    "panel_personas",
    "persona_allowlist",
]

PANEL_PERSONA_VERSION: Final = "aia-panel-persona-source-1"
#: ``Panel(df, min_vek=18)`` (``pipeline.py:147-152``).
MIN_AGE: Final = 18
ID_FIELD: Final = "panel_row_id"

#: Every column ``persona_profile`` reads (``pipeline.py:560-762``, ``dispozice.py:579-604``).
PROFILE_COLUMNS: Final = (
    "pohlavi",
    "vek",
    "vzdelani",
    "kraj",
    "prijem_osobni_mesicni",
    "prijem_cisty_mesicni",
    "prijem_definice",
    "prijem_pozice_0_1",
    "prijem_decile",
    "zamestnani_status",
    "is_student",
    "occupation_major",
    "velikost_domacnosti",
    "pocet_deti_celkem",
    "has_partner",
    "partner_cohabiting",
    "zdravi_sebehodnoceni",
    "kraj_kvalita_zivota_poradi",
    "brand_specific_background_ready",
    "F_rodinny_stav",
    "F_bydleni",
    "F_auto",
    "F_deti",
    "F_sam",
)
#: What ``styly.prirad_styly`` reads (``styly.py:66-73``).
STYLE_COLUMNS: Final = ("vek", "pohlavi", "vzdelani")
FACT_COLUMNS: Final = tuple(name for name, _ in _DIRECT_PATTERNS)
_MATCHED_ROLES: Final = frozenset({"MATCHED_DONOR_BLOCK", "MATCHED_WHOLE_BLOCK_CANONICAL"})


class PersonaRefused(PopulationError):
    """Panel personas cannot be built as 18.6.6 built them; ``reason`` names why."""

    reason = "persona_refused"


@dataclass(frozen=True, slots=True)
class PanelPersonas:
    """The personas of one sample, and what each request's profile is made from."""

    personas: tuple[Persona, ...]
    rows: Mapping[str, Mapping[str, Typed]] = field(repr=False)
    catalog: tuple[Signal, ...] = field(repr=False)
    labels: Mapping[str, Mapping[str, Any]] = field(repr=False)
    refused_fields: tuple[tuple[str, str], ...] = ()

    def profile(self, persona_id: str, topics: Sequence[str]) -> str:
        """The profile a model is shown for this respondent and these topics."""
        row = self.rows[persona_id]
        return persona_text(row, topics, grounded_text(row, topics, self.catalog, self.labels))

    def plan(self, spec: ResearchSpecification, persona: Persona) -> RespondentPlan:
        """``plan_respondent``, with each block's profile built from that block's topics,
        filtered to the study's selected dimensions (``persona_allowlist``) as 18.6.6 did."""
        base = plan_respondent(spec, persona)
        allowlist = persona_allowlist(spec)
        return RespondentPlan(
            persona=persona,
            facts=base.facts,
            blocks=base.blocks,
            profiles=tuple(
                self.profile(persona.persona_id, _topics(block, allowlist)) for block in base.blocks
            ),
        )

    def provenance(self) -> dict[str, Any]:
        """What a run records about how its personas were built."""
        return {
            "persona_source": PANEL_PERSONA_VERSION,
            "profile_version": PROFILE_VERSION,
            "persona_mode": PERSONA_MODE,
            "refused_fields": [{"field": f, "reason": r} for f, r in self.refused_fields],
            "catalog_signals": len(self.catalog),
        }


def persona_allowlist(spec: ResearchSpecification) -> tuple[str, ...]:
    """The study's selected dimensions as the run's persona topic allowlist (18.6.6
    ``research_project.py:440``): ``persona_dimensions.approved``, as the specification
    recorded it; empty filters nothing."""
    return spec.selection.dimensions if spec.selection is not None else ()


def _topics(block: Block, allowlist: Sequence[str] = ()) -> list[str]:
    return block_topics([_item_text(item) for item in block.items], allowlist)


def _item_text(item: Item) -> tuple[str, Sequence[str]]:
    return item.text, item.labels


def _refuse(message: str, reason: str) -> PersonaRefused:
    return PersonaRefused(message, reason=reason)


def _companion(population: RuntimePopulation, asset: str, reason: str) -> bytes:
    try:
        return population.companion(asset)
    except PopulationError as exc:
        raise _refuse(f"the persona needs the companion {asset}: {exc}", reason) from exc


def _gate_joint(population: RuntimePopulation, columns: Sequence[str]) -> None:
    """Core fields jointly; each matched donor block's fields within that block."""
    matched = population.joint_status.matched_blocks
    groups: dict[str, list[str]] = {}
    for name in columns:
        entry = population.field_policy.entry(name)
        block = entry.block if entry is not None and entry.block else "runtime-derived"
        groups.setdefault(block if block in matched else "core", []).append(name)
    for group, names in sorted(groups.items()):
        decision = population.decide_joint(names, client_facing=False)
        if not decision.allowed:
            raise _refuse(
                f"the field policy does not allow the persona's {group} fields jointly: "
                f"{decision.reason}",
                "persona_joint_refused",
            )


def panel_personas(
    population: RuntimePopulation,
    sample: PanelSample,
    *,
    response: ResponseProcessSpec = AIA_RESPONSE_V1,
) -> PanelPersonas:
    """The personas of ``sample``, drawn from ``population`` -- or a refusal by name."""
    fields = set(population.fields)
    unported = compatibility_columns(population.fields)
    if unported:
        raise _refuse(
            f"the population carries {len(unported)} P_* columns of 18.6.6's compatibility "
            f"block, which is not ported (e.g. {unported[0]})",
            "persona_compatibility_block_unported",
        )
    catalog = parse_catalog(_companion(population, CATALOG_ASSET, "persona_catalog_missing"))
    labels = parse_value_labels(
        _companion(population, VALUE_LABELS_ASSET, "persona_value_labels_missing")
    )
    if DONOR_FIELD not in fields:
        raise _refuse("the population has no donor column", "persona_donor_missing")

    wanted: list[str] = list(dict.fromkeys((*PROFILE_COLUMNS, *STYLE_COLUMNS, *FACT_COLUMNS)))
    for signal in catalog:
        wanted.append(signal.column)
        if signal.evidence_role in _MATCHED_ROLES:
            wanted.append(f"_donor_{signal.block or 'blok'}_quality")
    allowed: list[str] = []
    refused: list[tuple[str, str]] = []
    for name in dict.fromkeys(wanted):
        if name not in fields:
            continue
        decision = population.decide(name, FieldUse.PERSONA_CONSTRUCTION)
        if decision.allowed:
            allowed.append(name)
        else:
            refused.append((name, decision.reason))
    _gate_joint(population, allowed)

    kinds = {name: column_type(name, population.column(name)) for name in allowed}

    def typed(name: str, index: int) -> Typed:
        return _typed(population.column(name)[index], kinds[name])

    ages = population.column("vek") if "vek" in fields else None
    if ages is None:
        raise _refuse("the population has no age column", "persona_age_out_of_scope")
    age_kind = column_type("vek", ages)
    out_of_scope = 0
    for cell in ages:
        age = _typed(cell, age_kind)
        if not isinstance(age, (int, float)) or isinstance(age, bool) or not age >= MIN_AGE:
            out_of_scope += 1
    if out_of_scope:
        raise _refuse(
            f"{out_of_scope} rows have no age or are under {MIN_AGE}; 18.6.6 dropped them before "
            "it sampled and styled, so its sample and styles would differ",
            "persona_age_out_of_scope",
        )

    ids = population.column(ID_FIELD) if ID_FIELD in fields else None
    style_rows = [
        {
            "respondent_id": str(ids[i]) if ids is not None else str(i),
            **{name: typed(name, i) for name in STYLE_COLUMNS if name in kinds},
        }
        for i in range(population.row_count)
    ]
    styles = assign_styles(style_rows, response)

    donors = population.column(DONOR_FIELD)
    personas: list[Persona] = []
    rows: dict[str, dict[str, Typed]] = {}
    for respondent in sample.respondents:
        i = respondent.row
        donor = donors[i]
        if donor is None:
            raise _refuse(f"row {i} has no donor", "persona_donor_missing")
        persona_id = str(ids[i]) if ids is not None else f"ROW-{i}"
        row = {name: typed(name, i) for name in allowed}
        rows[persona_id] = row
        facts = {
            name: value for name in FACT_COLUMNS if name in row and (value := row[name]) is not None
        }
        personas.append(
            Persona(
                persona_id=persona_id,
                donor_id=donor,
                weight=respondent.analysis_weight,
                facts=facts,
                style={k: round(v, 6) for k, v in styles[i].items()},
                lineage=frozenset(PANEL_DERIVED_DATASETS),
                fictional=False,
            )
        )
    return PanelPersonas(
        personas=tuple(personas),
        rows=rows,
        catalog=catalog,
        labels=labels,
        refused_fields=tuple(refused),
    )
