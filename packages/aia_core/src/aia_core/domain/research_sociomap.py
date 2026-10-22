"""A research run's Sociomap: integrated, computed, and not exposed (ADR 0016 decision 6).

PR C chunk 6. For each tracked object set of the specification:

1. **the relation matrix** -- ported from the unit, ``sociomap.py``
   ``derive_relation_matrix``: object x object weighted Pearson correlation of the
   respondents' ratings, mapped onto 1-10 (``corr = -1 -> 1``, ``0 -> 5.5``,
   ``+1 -> 10``), fewer than five common ratings -> 5.5, diagonal 0; and each
   object's weighted mean rating. Weighted by ``_analysis_weight`` normalised to
   sum N, as the unit's ``project_engine._battery_dataset`` builds ``vaha``;
2. **each pair's status** -- the audit *NPC Sociomapa: faulty formulas in the
   code* (F3): the same correlation signed, the number of respondents who rated
   both objects, the Fisher-z interval and what the pair can be said to be
   (``UNKNOWN`` below ``n_min``, ``RELIABLE``, ``WEAK``). The unit's 5.5 stamp
   stays in step 1 only, because ``aia-sociomap-1`` is the unit's formula kept
   as a named comparison alternative; the status says where that matrix must
   not be read (plan ``sociomap-formula-corrections``, chunk 1a);
3. **the reference map** (only a run stored before the signed-off methodology pinned one;
   a new run pins ``aia-sociomap-5`` alone, so steps 1-3 are not computed) -- AIA's
   deterministic engine, ``compute_sociomap``, under the
   spec the run pinned when it was started (:class:`SociomapMethod`), with only the
   rating scale taken from the battery (a property of the data, recorded on the
   artifact). The module's preset is what a *new* run pins; a run executes the spec
   it pinned, whatever the preset has become since, and a run stored before methods
   were pinned is read as ``aia-sociomap-1`` (:data:`LEGACY_METHODS`), the method that
   computed it (plan ``sociomap-formula-corrections`` § 8.2, I0 and I4);
4. **the object maps** -- each pinned contract-3 method's map (:func:`compute_object_map`),
   stored under ``maps``: the relations over each person's own scale (audit F2), each
   object's alignment and connectedness over the PRIMARY objects (F8) and, with the
   worker's switch on, connectedness on 0-100 with its bootstrap interval (F9). The body
   holds them only there, once (plan ``mvp-workflow-assurance`` A3d).

**Integration is not exposure.** A map's status is the Sociomap register's for the
method, at the exact specification, that computed it (:mod:`.sociomap_register`,
complete-study-report B4). The drawn contract-2 map (``aia-sociomap-1``, whose four AIA
declarations PROGRESS D6 has not approved) is not in the register, so it is
``INTERNAL_ONLY``: the Study's researchers may inspect it; no client-facing surface, export
or report may render it. :func:`require_client_facing` is the one check such a surface
calls, and it refuses anything the register has not approved.

Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    ValidationError,
    model_serializer,
)

from .fieldwork import FieldworkDataset
from .methodology.expressions import ExpressionRefused, compile_formula
from .methodology.sociomap_formulas import SOCIOMAP_FORMULAS
from .pipeline import fingerprint
from .research_design import ResearchSpecification, SpecBattery, SpecQuestion
from .sociomap import (
    AIA_SOCIOMAP_V1,
    ObjectMapInputs,
    RatingItem,
    SociomapSpec,
    SociomapSpecV3,
    compute_object_map,
    compute_sociomap,
    read_spec,
    require_supported,
    spec_payload,
)
from .sociomap.metrics import (
    CONNECTEDNESS_QUANTILES,
)
from .sociomap.models import RatingsMatrix, RelationMatrix, SociomapInputs
from .sociomap.pairs import PairRelations, derive_pair_relations, derive_relation_matrix
from .sociomap.relations import AUDIT_PROVISIONAL_N_MIN
from .sociomap.slots import ENGINE_SLOTS, NO_SLOTS, Slots
from .sociomap.specification import AIA_SOCIOMAP_V5
from .sociomap_register import MethodologyStatus, method_status

__all__ = [
    "CONNECTEDNESS_RESAMPLES",
    "CONNECTEDNESS_SEED",
    "LEGACY_METHODS",
    "PAIR_CONFIDENCE",
    "RELATION_SOURCE",
    "SOCIOMAP_VERSION",
    "MethodologyStatus",
    "PairRelations",
    "SideTables",
    "SociomapMethod",
    "SociomapMethodsInvalid",
    "SociomapNotApproved",
    "battery_sociomap",
    "default_methods",
    "derive_pair_relations",
    "derive_relation_matrix",
    "is_retired",
    "methods_fingerprint",
    "object_map_inputs",
    "rating_universe",
    "read_methods",
    "require_client_facing",
    "research_sociomaps",
    "side_tables_for",
    "side_tables_of",
    "without_reference",
]

#: The version of this module's artifact body. ``2``: the relation block carries
#: every pair's signed correlation, rater count, interval and status (chunk 1a);
#: the executor fingerprints its input with it, so a run computed under ``1`` is
#: not reused as if it had them. ``3``: each set carries ``object_scores``, the
#: audit's alignment and connectedness (chunk 1b), so a body stored under ``2``
#: (without them) is not reused as if it had them. ``4``: each set carries
#: ``relation_rescaled``, every pair over each person's own 0-1 scale (audit F2,
#: chunk 2a), and ``object_scores`` read it instead of the raw correlation.
#: ``5``: each set carries ``connectedness_100``, the audit's F9 score with its
#: bootstrap interval and the ranking with ties (chunk 4a), so a body stored under
#: ``4`` (without them) is not reused as if it had them. ``6``: the body names the
#: methods the run pinned (``methods``) and each set's map is computed under the
#: pinned spec, not the module's preset (plan § 8.2, S1). ``7``: each set carries
#: ``maps``, the run's pinned contract-3 object maps by method id (``aia-sociomap-2``,
#: S2). ``8``: the rating universe holds the design's declared standalone rating items
#: (``relation_rescaled.rating_questions``) and the roles are the specification's
#: (``roles``; S3). ``9``: the side tables (``relation``, ``relation_rescaled``,
#: ``object_scores``) and K100 read n_min, confidence and the bootstrap from the run's
#: pinned object map, and say which (``side_tables``; plan ``methodology-tab`` S2b).
#: ``10``: the body keeps no second copy of what each pinned object map holds -- no
#: ``relation_rescaled``, ``object_scores`` or ``connectedness_100``, and no second K100
#: bootstrap (plan ``mvp-workflow-assurance`` A3d); a body stored under ``9`` keeps them.
#: Not the engine preset (``aia-sociomap-<n>``).
SOCIOMAP_VERSION: Final = "aia-research-sociomap-10"
RELATION_SOURCE: Final = "DERIVED_FROM_COMMON_RESPONDENT_RATINGS"
#: The audit's interval (F3): a 95 % Fisher-z interval decides RELIABLE. The side tables of
#: a run that pinned no object map; a run that pinned one reads its own (:class:`SideTables`).
PAIR_CONFIDENCE: Final = 0.95
#: Audit F9's B ("e.g. 500"): respondent bootstraps behind each K100 interval, for a run
#: that pinned no object map. Recorded on every body; never shrunk silently.
CONNECTEDNESS_RESAMPLES: Final = 500
#: The bootstrap's seed (OI-62's generator), for a run that pinned no object map, recorded
#: on every body: the same dataset gives the same intervals on any host.
CONNECTEDNESS_SEED: Final = 20261007


@dataclass(frozen=True, slots=True)
class SideTables:
    """What the body's ``relation`` pairs are computed with (plan ``methodology-tab`` S2b):
    the pair status's ``n_min`` and ``confidence``, read from the run's last pinned object
    map (``method``), so an edited methodology put in force moves them with the map, and that
    map's bootstrap, recorded beside them (the body computes no K100 of its own since A3d).
    The statuses keep reading the respondent count: that is the body's documented rule,
    whatever basis the map's own pairs read.

    A run that pinned no object map (``method`` ``None``) is computed with the values the
    code fixed before the pin carried them (:data:`LEGACY_SIDE_TABLES`).
    """

    method: str | None
    n_min: int
    confidence: float
    resamples: int
    seed: int
    quantiles: tuple[float, float]

    def to_payload(self) -> dict[str, Any]:
        """What the body records: where every value came from, and the values."""
        return {
            "method": self.method,
            "n_min": self.n_min,
            "confidence": self.confidence,
            "resamples": self.resamples,
            "seed": self.seed,
            "quantiles": list(self.quantiles),
        }


#: The side tables of a run that pinned no object map: the code's values before S2b.
LEGACY_SIDE_TABLES: Final = SideTables(
    method=None,
    n_min=AUDIT_PROVISIONAL_N_MIN,
    confidence=PAIR_CONFIDENCE,
    resamples=CONNECTEDNESS_RESAMPLES,
    seed=CONNECTEDNESS_SEED,
    quantiles=CONNECTEDNESS_QUANTILES,
)


def side_tables_for(object_maps: Sequence[SociomapSpecV3]) -> SideTables:
    """The side tables a run computes: the last pinned object map's, or the legacy ones."""
    if not object_maps:
        return LEGACY_SIDE_TABLES
    spec = object_maps[-1]
    declared = spec.connectedness.quantiles
    return SideTables(
        method=spec.methodology_version,
        n_min=spec.relation.n_min,
        confidence=spec.relation.confidence,
        resamples=spec.connectedness.resamples,
        seed=spec.connectedness.seed,
        quantiles=LEGACY_SIDE_TABLES.quantiles if declared is None else declared,
    )


class SociomapNotApproved(PermissionError):
    """A Sociomap reached a client-facing surface while its methodology is not approved."""


def require_client_facing(sociomap: dict[str, Any]) -> None:
    """The check every client-facing surface, export and report makes. Fails closed."""
    if sociomap.get("methodology_status") != MethodologyStatus.CLIENT_FACING.value:
        raise SociomapNotApproved(
            "this Sociomap is INTERNAL_ONLY: the Sociomap register does not approve its "
            "methodology for client use"
        )


class SociomapMethodsInvalid(ValueError):
    """A run's pinned methods cannot be read, or are not a set this module computes."""


class SociomapMethod(BaseModel):
    """One Sociomap method a run pinned when it was started: its id and its whole spec.

    The spec is stored, not its name: a run executes exactly the methodology it was
    started under, even after the module's preset changes. ``spec_fingerprint`` is the
    spec's own and is re-checked on every read, so an edited pin is refused rather than
    computed. The battery's rating scale is filled in at execution (a property of the
    data, recorded on the artifact), as it always was.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    method_id: str = Field(min_length=1, max_length=100)
    spec: dict[str, Any]
    spec_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    #: The formulas a stored methodology version replaces, by slot (ADR 0023, S4c): the
    #: engine computes each from its expression. Left out of the stored form when empty,
    #: so every pin made before it existed -- and every code preset -- stores, and so
    #: fingerprints, exactly as it did.
    formulas: dict[str, str] = Field(default_factory=dict)

    @model_serializer(mode="wrap")
    def _store(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        body: dict[str, Any] = handler(self)
        if not self.formulas:
            body.pop("formulas", None)
        return body

    @classmethod
    def of(
        cls, spec: SociomapSpec | SociomapSpecV3, formulas: Mapping[str, str] | None = None
    ) -> SociomapMethod:
        """The pin for ``spec``: its methodology version, its stored form, its fingerprint,
        and the formulas a stored version replaces (none for a code preset)."""
        return cls(
            method_id=spec.methodology_version,
            spec=spec_payload(spec),
            spec_fingerprint=spec.fingerprint(),
            formulas=dict(formulas or {}),
        )

    def slots(self) -> Slots:
        """The replaced formulas compiled for the engine; :data:`NO_SLOTS` for none.

        A formula is read only on an object map (contract 3) and only in a slot the engine
        computes; each is compiled again here, so a pin whose expression no longer compiles
        is refused by name (:class:`SociomapMethodsInvalid`), never computed as the code's.
        """
        if not self.formulas:
            return NO_SLOTS
        if self.spec.get("contract_version") != "3":
            raise SociomapMethodsInvalid(
                f"{self.method_id}: only an object map's formulas are replaceable"
            )
        builtin = {f.slot.id: f.slot for f in SOCIOMAP_FORMULAS}
        compiled: dict[str, Any] = {}
        for slot_id, text in sorted(self.formulas.items()):
            if slot_id not in ENGINE_SLOTS or slot_id not in builtin:
                raise SociomapMethodsInvalid(
                    f"{self.method_id}: the engine computes no formula slot {slot_id!r}"
                )
            try:
                compiled[slot_id] = compile_formula(builtin[slot_id], text)
            except ExpressionRefused as exc:
                raise SociomapMethodsInvalid(
                    f"{self.method_id}: formula {slot_id} does not compile: {exc}"
                ) from exc
        return compiled

    def resolve(self) -> SociomapSpec | SociomapSpecV3:
        """The pinned spec, verified against its fingerprint and its id, and computable.

        Raises :class:`SociomapMethodsInvalid` for a pin that does not read, does not hash
        to its fingerprint or names another method, and
        :class:`~.sociomap.specification.UnsupportedMethodology` for a spec this engine
        cannot compute: nothing substitutes another method.
        """
        try:
            spec = read_spec(self.spec)
        except (ValueError, ValidationError) as exc:
            raise SociomapMethodsInvalid(
                f"{self.method_id}: the pinned spec does not read: {exc}"
            ) from exc
        if spec.fingerprint() != self.spec_fingerprint:
            raise SociomapMethodsInvalid(
                f"{self.method_id}: the pinned spec does not match its recorded fingerprint"
            )
        if spec.methodology_version != self.method_id:
            raise SociomapMethodsInvalid(
                f"the pin names {self.method_id!r} but holds {spec.methodology_version!r}"
            )
        require_supported(spec)
        return spec


#: How a run stored before methods were pinned is read: ``aia-sociomap-1``, the preset
#: that computed every such run. Never back-filled onto the stored run.
LEGACY_METHODS: Final = (SociomapMethod.of(AIA_SOCIOMAP_V1),)


def default_methods() -> tuple[SociomapMethod, ...]:
    """What a new run pins: ``aia-sociomap-5``, the signed-off methodology, by its own name at
    its spec fingerprint, and nothing beside it -- no reference picture is computed any more.
    The Sociomap register approves it at that fingerprint. A run that pinned an earlier method
    keeps its pins and its data: a pin is never rewritten."""
    return (SociomapMethod.of(AIA_SOCIOMAP_V5),)


#: The earlier default's object map, which no new run computes. The old engine stays in the code,
#: so a run that pinned it still reads.
RETIRED_OBJECT_MAP: Final = "aia-sociomap-3"


def is_retired(methods: Sequence[SociomapMethod]) -> bool:
    """Whether a run's object map is exactly the earlier default's ``aia-sociomap-3``, or it
    pinned the reference map alone (a run stored before pins reads so): such a run is never
    computed again. A run of an edited version (``aia-sociomap-3+e2``, ``-5+e1``), which also
    pinned the reference map beside it, is not: :func:`without_reference` is what it computes."""
    if any(m.method_id == RETIRED_OBJECT_MAP for m in methods):
        return True
    return all(m.spec.get("contract_version") == "2" for m in methods)


def without_reference(methods: Sequence[SociomapMethod]) -> tuple[SociomapMethod, ...]:
    """A run's pins without the reference map (contract 2), which no new run computes: what a
    retry of a run of an edited version pins. Only for a set :func:`is_retired` lets through."""
    return tuple(m for m in methods if m.spec.get("contract_version") != "2")


def side_tables_of(methods: Sequence[SociomapMethod]) -> SideTables:
    """:func:`side_tables_for` over a run's pinned methods, each resolved (verified and
    computable) first: what the readiness warning and the side tables both read, so the two
    never disagree on a pair's ``n_min`` (plan ``methodology-tab`` S2c)."""
    specs = [m.resolve() for m in methods]
    return side_tables_for([s for s in specs if isinstance(s, SociomapSpecV3)])


def methods_fingerprint(methods: Sequence[SociomapMethod]) -> str:
    """One identity for a pinned set, in its order."""
    return fingerprint([m.model_dump(mode="json") for m in methods])


def read_methods(value: Any) -> tuple[SociomapMethod, ...]:
    """A run's pinned methods from its stored form; ``None`` (a run stored before pins) is
    :data:`LEGACY_METHODS`.

    The set must be one this module computes: at least one method, no id twice, at most one
    spec of contract 2, whose map is the set's ``sociomap`` (the reference picture a run stored
    before the signed-off methodology; a new run pins none), and any number of contract-3
    object maps, stored under ``maps``. Raises :class:`SociomapMethodsInvalid`.
    """
    if value is None:
        return LEGACY_METHODS
    if not isinstance(value, list | tuple) or not value:
        raise SociomapMethodsInvalid("a run pins at least one Sociomap method")
    try:
        methods = tuple(SociomapMethod.model_validate(v) for v in value)
    except ValidationError as exc:
        raise SociomapMethodsInvalid(f"a pinned method does not read: {exc}") from exc
    ids = [m.method_id for m in methods]
    if len(set(ids)) != len(ids):
        raise SociomapMethodsInvalid(f"a method is pinned twice: {ids}")
    unknown = [m.method_id for m in methods if m.spec.get("contract_version") not in ("2", "3")]
    if unknown:
        raise SociomapMethodsInvalid(f"methods of a contract this module does not read: {unknown}")
    contract_2 = [m for m in methods if m.spec.get("contract_version") == "2"]
    if len(contract_2) > 1:
        raise SociomapMethodsInvalid(
            "at most one contract-2 method draws a set's reference map; pinned "
            f"{[m.method_id for m in contract_2]}"
        )
    return methods


def _methodology_status(
    spec: SociomapSpec | SociomapSpecV3, slots: Slots = NO_SLOTS
) -> MethodologyStatus:
    """The register's status for the spec a run pinned (complete-study-report B4). PROGRESS
    D6's global switch is gone: what is approved is a method at its exact specification. A
    method whose formulas a version replaced is never approved by its base's entry."""
    if slots:
        return MethodologyStatus.INTERNAL_ONLY
    return method_status(spec.methodology_version, spec.fingerprint())


def _rating(value: Any) -> float | None:
    return float(value) if isinstance(value, int) and not isinstance(value, bool) else None


def rating_universe(
    rated_with: Sequence[SpecBattery], rating_questions: Sequence[SpecQuestion]
) -> list[tuple[str, int, int]]:
    """The specification's rating items, each with its declared scale: every object of every
    tracked set, then every standalone scale question the design declared a rating item
    (plan § 8.2, S3). Nothing enters by its type: an undeclared numeric question is a
    descriptor, never a rating."""
    universe: list[tuple[str, int, int]] = []
    for b in rated_with:
        low, high = b.scale
        if not high > low:
            raise ValueError(f"battery {b.id!r} declares an empty scale {b.scale!r}")
        universe.extend((b.question_id(obj), low, high) for obj in b.objects)
    for q in rating_questions:
        if not q.rating_item or q.scale is None:
            raise ValueError(f"{q.id} is not a declared scale rating item")
        universe.append((q.id, q.scale[0], q.scale[1]))
    return universe


def object_map_inputs(
    battery: SpecBattery,
    dataset: FieldworkDataset,
    rated_with: Sequence[SpecBattery],
    weights: Sequence[float],
    *,
    rating_questions: Sequence[SpecQuestion],
) -> ObjectMapInputs:
    """``battery``'s family over the specification's rating universe, as the object map reads
    it: every rating item (:func:`rating_universe`) with its declared scale (audit F1, F2),
    the raw ratings, the weights the relations are weighted by, and each object's role as
    the specification declares it (:meth:`~.research_design.SpecBattery.object_roles`).
    """
    if not any(b.id == battery.id for b in rated_with):
        raise ValueError(f"battery {battery.id!r} is not among the sets it is rated with")
    items = [
        RatingItem(item_id=qid, scale_min=float(low), scale_max=float(high))
        for qid, low, high in rating_universe(rated_with, rating_questions)
    ]
    return ObjectMapInputs(
        respondent_ids=tuple(r.respondent_id for r in dataset.respondents),
        donor_ids=tuple(r.donor_id for r in dataset.respondents),
        items=tuple(items),
        values=tuple(
            tuple(_rating(r.answers.get(i.item_id)) for i in items) for r in dataset.respondents
        ),
        weights=tuple(weights),
        object_ids=tuple(o.id for o in battery.objects),
        object_items=tuple(battery.question_id(o) for o in battery.objects),
        roles=battery.object_roles(),
    )


def battery_sociomap(
    battery: SpecBattery,
    dataset: FieldworkDataset,
    *,
    rated_with: Sequence[SpecBattery],
    connectedness_interval: bool,
    map_spec: SociomapSpec | None,
    object_maps: Sequence[SociomapSpecV3 | tuple[SociomapSpecV3, Slots]],
    rating_questions: Sequence[SpecQuestion],
    runtime: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """One tracked set's relation matrix and its Sociomap, as an internal artifact body.

    ``rated_with`` are every tracked set of the specification and ``rating_questions`` its
    declared standalone rating items: together the rating universe each respondent's own
    scale is read over (audit F2: all the items they rated, not only this family).
    ``map_spec`` is the run's pinned contract-2 spec; only its rating scale is replaced,
    by the battery's. ``None`` (a run that pinned none, as every new run) computes no reference
    picture: the body has no ``sociomap`` or ``preset``, and its status is the last object
    map's. ``object_maps`` are its pinned contract-3 specs, each with the
    formulas its version replaces (a bare spec replaces none): each is computed over the
    same rating universe and stored under ``maps`` by method id. ``runtime`` is what the
    worker records of its numerical libraries beside each signed-off map
    (:func:`~.sociomap.engine_v2.compute_object_map`).
    """
    object_ids = [o.id for o in battery.objects]
    qids = [battery.question_id(o) for o in battery.objects]
    raw = [r.weight for r in dataset.respondents]
    total = sum(raw) or 1.0
    weights = [w * (len(raw) / total) for w in raw]  # project_engine.py:34-35, "vaha"
    ratings: list[list[float | None]] = [
        [_rating(r.answers.get(q)) for q in qids] for r in dataset.respondents
    ]
    pinned_maps = [m if isinstance(m, tuple) else (m, NO_SLOTS) for m in object_maps]
    roles = battery.object_roles()
    # Each pinned object map holds the relations over each person's own scale (audit F2),
    # the object scores (F8) and K100 (F9). The body keeps no second copy of them (A3d):
    # nothing read it, and its K100 paid a second bootstrap beside the map's.
    maps = {
        spec_v3.methodology_version: compute_object_map(
            object_map_inputs(
                battery, dataset, rated_with, weights, rating_questions=rating_questions
            ),
            spec_v3,
            connectedness_interval=connectedness_interval,
            slots=slots,
            runtime=runtime,
        )
        for spec_v3, slots in pinned_maps
    }

    low, high = battery.scale
    common = {
        "battery_id": battery.id,
        "title": battery.title,
        "family": battery.family,
        "objects": [{"id": o.id, "label": o.label} for o in battery.objects],
    }
    if map_spec is None:
        if not pinned_maps:
            raise SociomapMethodsInvalid("a run pins at least one Sociomap method")
        # Nothing beside the pinned maps: the unit's relation matrix and its side tables went
        # with the reference picture they were kept for; each map holds its own pairs.
        status_spec, status_slots = pinned_maps[-1]
        return {
            **common,
            "methodology_status": _methodology_status(status_spec, status_slots).value,
            "rating_scale": [low, high],
            "roles": {"declared": battery.roles_declared, "by_object": roles},
            "maps": {method_id: a.to_payload() for method_id, a in maps.items()},
        }
    side = side_tables_for([spec_v3 for spec_v3, _ in pinned_maps])
    relation, scores = derive_relation_matrix(ratings, weights)
    pairs = derive_pair_relations(ratings, weights, n_min=side.n_min, confidence=side.confidence)
    spec = map_spec.model_copy(
        update={
            "ratings": map_spec.ratings.model_copy(
                update={"rating_scale_min": float(low), "rating_scale_max": float(high)}
            )
        }
    )
    inputs = SociomapInputs(
        ratings=RatingsMatrix(
            respondent_ids=tuple(r.respondent_id for r in dataset.respondents),
            object_ids=tuple(object_ids),
            values=tuple(tuple(row) for row in ratings),
        ),
        object_relation=RelationMatrix(
            entity_ids=tuple(object_ids), values=tuple(tuple(row) for row in relation)
        ),
    )
    artifact = compute_sociomap(inputs, spec)
    return {
        **common,
        "methodology_status": _methodology_status(map_spec).value,
        "methodology_decision": "PROGRESS D6: the four AIA Sociomap declarations, open",
        "preset": map_spec.methodology_version,
        "rating_scale": [low, high],
        "side_tables": side.to_payload(),
        "relation": _relation_block(relation, scores, pairs),
        "roles": {"declared": battery.roles_declared, "by_object": roles},
        "sociomap": artifact.model_dump(mode="json"),
        "maps": {method_id: a.to_payload() for method_id, a in maps.items()},
    }


def _relation_block(
    relation: list[list[float]], scores: list[float | None], pairs: PairRelations
) -> dict[str, Any]:
    """The body's relation pairs: the unit's 1-10 matrix and each pair's audited status."""
    return {
        "source": RELATION_SOURCE,
        "ported_from": "legacy/npc-panel-18.6.6/app/sociomap.py derive_relation_matrix",
        "matrix": relation,
        "matrix_caveat": (
            "the unit's 1-10 strength, kept for aia-sociomap-1: a pair below five raters "
            "is stamped 5.5 and r = 0 reads as a medium relation (audit F3, F4); read "
            "status before matrix"
        ),
        "scores": scores,
        **pairs.model_dump(mode="json"),
        "status_counts": pairs.counts(),
        "status_rule": (
            "audit F3: UNKNOWN below n_min common raters or without a correlation; "
            "RELIABLE when the Fisher-z interval at confidence excludes 0; WEAK otherwise. "
            "n_min and the confidence are side_tables': the run's last pinned object map's, "
            "or, with none pinned, the audit's provisional n_min (pending its Q6) and 0.95"
        ),
    }


def research_sociomaps(
    spec: ResearchSpecification,
    dataset: FieldworkDataset,
    *,
    methods: Sequence[SociomapMethod],
    connectedness_interval: bool,
    runtime: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Every tracked set's Sociomap. A specification without one has none, and says so.

    ``methods`` are the run's pinned methods (:func:`read_methods`); each is resolved --
    verified and checked computable -- before any number, so a pin this engine cannot
    compute fails here by name. ``connectedness_interval`` is the worker's kill switch for
    the F9 bootstrap, passed by name to each object map: off, each map records that it was
    not computed. ``runtime`` is the worker's numerical libraries, recorded with each
    signed-off map. The result's ``methodology_status`` is the reference map's when the run
    pinned one, else the last object map's (a new run's ``aia-sociomap-5``).
    """
    pinned = read_methods([m.model_dump(mode="json") for m in methods])
    resolved = [(m.resolve(), m.slots()) for m in pinned]
    map_spec = next((s for s, _ in resolved if isinstance(s, SociomapSpec)), None)
    object_maps = [(s, slots) for s, slots in resolved if isinstance(s, SociomapSpecV3)]
    if map_spec is not None:
        status = _methodology_status(map_spec)
    else:
        last_spec, last_slots = object_maps[-1]
        status = _methodology_status(last_spec, last_slots)
    return {
        "sociomap_version": SOCIOMAP_VERSION,
        "methods": [
            {
                "method_id": m.method_id,
                "spec_fingerprint": m.spec_fingerprint,
                # What an edited version replaced, beside the map it shaped (ADR 0023).
                **({"formulas": dict(m.formulas)} if m.formulas else {}),
            }
            for m in pinned
        ],
        "methodology_status": status.value,
        "data_origin": dataset.origin.value if dataset.origin else None,
        "batteries": [
            battery_sociomap(
                b,
                dataset,
                rated_with=spec.batteries,
                connectedness_interval=connectedness_interval,
                map_spec=map_spec,
                object_maps=object_maps,
                rating_questions=spec.rating_questions(),
                runtime=runtime,
            )
            for b in spec.batteries
        ],
        "note": None if spec.batteries else "Návrh nemá sledovanou sadu; Sociomapa nevznikla.",
    }
