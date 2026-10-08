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
3. **each object's alignment and connectedness** -- the audit's replacement
   of the classic score (F8), over the PRIMARY objects with UNKNOWN pairs left
   out; every object of a tracked set is PRIMARY until AIA has an object
   manager (chunk 1b). Stored beside the map; the map's height is still the
   preset's. Beside them, connectedness on 0-100 with a respondent-bootstrap
   interval and the order those intervals allow (audit F9, chunk 4a);
4. **the map** -- AIA's deterministic engine, ``compute_sociomap``, under the
   spec the run pinned when it was started (:class:`SociomapMethod`), with only the
   rating scale taken from the battery (a property of the data, recorded on the
   artifact). The module's preset is what a *new* run pins; a run executes the spec
   it pinned, whatever the preset has become since, and a run stored before methods
   were pinned is read as ``aia-sociomap-1`` (:data:`LEGACY_METHODS`), the method that
   computed it (plan ``sociomap-formula-corrections`` § 8.2, I0 and I4).

**Integration is not exposure.** The preset carries four AIA methodology
declarations that PROGRESS D6 has not approved, so every Sociomap this module
builds is ``INTERNAL_ONLY``: the Study's researchers may inspect it; no
client-facing surface, export or report may render it. :func:`require_client_facing`
is the one check such a surface calls, and it refuses while D6 is open.

Pure: no I/O.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Any, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .fieldwork import FieldworkDataset
from .pipeline import fingerprint
from .research_design import ResearchSpecification, SpecBattery, SpecQuestion
from .sociomap import (
    AIA_SOCIOMAP_V1,
    AIA_SOCIOMAP_V2,
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
from .sociomap.metrics import connectedness_100, primary_scores, rank_with_ties
from .sociomap.models import RatingsMatrix, RelationMatrix, SociomapInputs
from .sociomap.pairs import PairRelations, derive_pair_relations, derive_relation_matrix
from .sociomap.relations import AUDIT_PROVISIONAL_N_MIN, PairStatus, person_minmax

__all__ = [
    "CONNECTEDNESS_NOT_COMPUTED",
    "CONNECTEDNESS_RESAMPLES",
    "CONNECTEDNESS_SEED",
    "D6_OPEN",
    "LEGACY_METHODS",
    "PAIR_CONFIDENCE",
    "RELATION_SOURCE",
    "RESCALE_RULE",
    "SOCIOMAP_VERSION",
    "MethodologyStatus",
    "PairRelations",
    "SociomapMethod",
    "SociomapMethodsInvalid",
    "SociomapNotApproved",
    "battery_sociomap",
    "default_methods",
    "derive_pair_relations",
    "derive_relation_matrix",
    "methods_fingerprint",
    "object_map_inputs",
    "rating_universe",
    "read_methods",
    "require_client_facing",
    "rescaled_battery_ratings",
    "research_sociomaps",
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
#: (``roles``; S3). Not the engine preset (``aia-sociomap-<n>``).
SOCIOMAP_VERSION: Final = "aia-research-sociomap-8"
#: How ``relation_rescaled`` was made, recorded on every body.
RESCALE_RULE: Final = (
    "audit F2: each rating on its item's declared 0-1 scale (audit F1, eq. 3), then each "
    "respondent's own min-max over every declared rating item of the specification they "
    "rated, straight-liners excluded, then the weighted Pearson correlation as the unit "
    "computes it; the weighting is AIA's reading where the audit is silent (register AUDIT-F2)"
)
RELATION_SOURCE: Final = "DERIVED_FROM_COMMON_RESPONDENT_RATINGS"
#: The audit's interval (F3): a 95 % Fisher-z interval decides RELIABLE.
PAIR_CONFIDENCE: Final = 0.95
#: Audit F9's B ("e.g. 500"): respondent bootstraps behind each K100 interval.
#: Declared here by name and recorded on every body; never shrunk silently.
CONNECTEDNESS_RESAMPLES: Final = 500
#: The bootstrap's seed (OI-62's generator), recorded on every body: the same
#: dataset gives the same intervals on any host.
CONNECTEDNESS_SEED: Final = 20261007

#: PROGRESS D6: the four AIA Sociomap declarations await the methodology owner.
#: Flipping this is a methodology decision recorded in PROGRESS, never a fix.
D6_OPEN: Final = True


class MethodologyStatus(StrEnum):
    #: The Study's researchers may look at it; nobody else, nowhere else.
    INTERNAL_ONLY = "INTERNAL_ONLY"
    #: D6 approved: a client-facing surface may render it.
    CLIENT_FACING = "CLIENT_FACING"


class SociomapNotApproved(PermissionError):
    """A Sociomap reached a client-facing surface while its methodology is not approved."""


def require_client_facing(sociomap: dict[str, Any]) -> None:
    """The check every client-facing surface, export and report makes. Fails closed."""
    if sociomap.get("methodology_status") != MethodologyStatus.CLIENT_FACING.value:
        raise SociomapNotApproved(
            "this Sociomap is INTERNAL_ONLY: its methodology (PROGRESS D6) is not approved "
            "for client use"
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

    @classmethod
    def of(cls, spec: SociomapSpec | SociomapSpecV3) -> SociomapMethod:
        """The pin for ``spec``: its methodology version, its stored form, its fingerprint."""
        return cls(
            method_id=spec.methodology_version,
            spec=spec_payload(spec),
            spec_fingerprint=spec.fingerprint(),
        )

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
    """What a new run pins: ``aia-sociomap-1``, the shipped picture until chunk 5 draws
    another, and ``aia-sociomap-2``, the audit's object map, computed beside it. Both are
    ``INTERNAL_ONLY`` while D6 is open."""
    return (*LEGACY_METHODS, SociomapMethod.of(AIA_SOCIOMAP_V2))


def methods_fingerprint(methods: Sequence[SociomapMethod]) -> str:
    """One identity for a pinned set, in its order."""
    return fingerprint([m.model_dump(mode="json") for m in methods])


def read_methods(value: Any) -> tuple[SociomapMethod, ...]:
    """A run's pinned methods from its stored form; ``None`` (a run stored before pins) is
    :data:`LEGACY_METHODS`.

    The set must be one this module computes: at least one method, no id twice, exactly
    one spec of contract 2, whose map is the set's ``sociomap`` (the picture the Results
    and the report draw until chunk 5), and any number of contract-3 object maps, stored
    beside it under ``maps``. Raises :class:`SociomapMethodsInvalid`.
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
    if len(contract_2) != 1:
        raise SociomapMethodsInvalid(
            "exactly one contract-2 method draws a set's map until chunk 5; pinned "
            f"{[m.method_id for m in contract_2]}"
        )
    return methods


def _methodology_status() -> MethodologyStatus:
    return MethodologyStatus.INTERNAL_ONLY if D6_OPEN else MethodologyStatus.CLIENT_FACING


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


def rescaled_battery_ratings(
    battery: SpecBattery,
    dataset: FieldworkDataset,
    rated_with: Sequence[SpecBattery],
    *,
    rating_questions: Sequence[SpecQuestion],
) -> tuple[list[list[float | None]], list[str]]:
    """``battery``'s ratings on each respondent's own 0-1 scale (audit F2), and who has none.

    Every rating item of the specification (:func:`rating_universe`: the sets in
    ``rated_with`` and the declared ``rating_questions``) is first put on its own declared
    0-1 scale, so items with different ends compare; each respondent's lowest is then 0
    and highest 1 over all of them (:func:`~.sociomap.relations.person_minmax`), and
    ``battery``'s columns are returned. A respondent whose rated items all share one value
    is excluded: their row is all ``None`` and their id is listed.
    """
    if not any(b.id == battery.id for b in rated_with):
        raise ValueError(f"battery {battery.id!r} is not among the sets it is rated with")
    columns = rating_universe(rated_with, rating_questions)
    mine = {battery.question_id(o) for o in battery.objects}
    own = [c for c, (qid, _, _) in enumerate(columns) if qid in mine]
    rows: list[list[float | None]] = []
    for r in dataset.respondents:
        row: list[float | None] = []
        for qid, low, high in columns:
            value = _rating(r.answers.get(qid))
            row.append(None if value is None else (value - low) / (high - low))
        rows.append(row)
    scaled = person_minmax(rows)
    ids = [dataset.respondents[k].respondent_id for k in scaled.excluded]
    return [[scaled.values[k][c] for c in own] for k in range(len(rows))], ids


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


#: What the body says where the bootstrap was not asked for (the worker's kill switch,
#: ``AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED``): not computed, never a 0 or a guess.
CONNECTEDNESS_NOT_COMPUTED: Final = {
    "status": "not_computed",
    "reason": (
        "the respondent bootstrap (audit F9) is off in this deployment: about 90 s per "
        "1,500 x 22 set at B = 500; AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED turns it on"
    ),
}


def battery_sociomap(
    battery: SpecBattery,
    dataset: FieldworkDataset,
    *,
    rated_with: Sequence[SpecBattery],
    connectedness_interval: bool,
    map_spec: SociomapSpec,
    object_maps: Sequence[SociomapSpecV3],
    rating_questions: Sequence[SpecQuestion],
) -> dict[str, Any]:
    """One tracked set's relation matrix and its Sociomap, as an internal artifact body.

    ``rated_with`` are every tracked set of the specification and ``rating_questions`` its
    declared standalone rating items: together the rating universe each respondent's own
    scale is read over (audit F2: all the items they rated, not only this family).
    ``map_spec`` is the run's pinned contract-2 spec; only its rating scale is replaced,
    by the battery's. ``object_maps`` are its pinned contract-3 specs: each is
    computed over the same rating universe and stored under ``maps`` by method id.
    """
    object_ids = [o.id for o in battery.objects]
    qids = [battery.question_id(o) for o in battery.objects]
    raw = [r.weight for r in dataset.respondents]
    total = sum(raw) or 1.0
    weights = [w * (len(raw) / total) for w in raw]  # project_engine.py:34-35, "vaha"
    ratings: list[list[float | None]] = [
        [_rating(r.answers.get(q)) for q in qids] for r in dataset.respondents
    ]
    relation, scores = derive_relation_matrix(ratings, weights)
    pairs = derive_pair_relations(
        ratings, weights, n_min=AUDIT_PROVISIONAL_N_MIN, confidence=PAIR_CONFIDENCE
    )
    rescaled, not_rescaled = rescaled_battery_ratings(
        battery, dataset, rated_with, rating_questions=rating_questions
    )
    roles = battery.object_roles()
    rescaled_pairs = derive_pair_relations(
        rescaled, weights, n_min=AUDIT_PROVISIONAL_N_MIN, confidence=PAIR_CONFIDENCE
    )
    # Each object's role as the specification declares it (``context_objects``; none
    # declared: every object PRIMARY, and the body says the roles were not declared). The
    # scores read the relation after the rating habit is removed (audit F8 reads r~, F2).
    object_scores = primary_scores(object_ids, rescaled_pairs.r, rescaled_pairs.status, roles)

    def correlate(
        multiplicities: Sequence[int],
    ) -> tuple[tuple[tuple[float | None, ...], ...], tuple[tuple[PairStatus | None, ...], ...]]:
        # A resample: each respondent's rescaled row taken as many times as drawn,
        # as a weight multiple (the weighted Pearson of duplicated rows). The rows
        # are rescaled once: each person's min-max is their own (F2).
        drawn = derive_pair_relations(
            rescaled,
            [k * w for k, w in zip(multiplicities, weights, strict=True)],
            n_min=AUDIT_PROVISIONAL_N_MIN,
            confidence=PAIR_CONFIDENCE,
        )
        return drawn.r, drawn.status

    maps = {
        spec_v3.methodology_version: compute_object_map(
            object_map_inputs(
                battery, dataset, rated_with, weights, rating_questions=rating_questions
            ),
            spec_v3,
            connectedness_interval=connectedness_interval,
        )
        for spec_v3 in object_maps
    }
    # K100 is computed once: an object map whose bootstrap is this body's -- the same
    # universe, rows, weights, roles, n_min, confidence, B and seed -- already
    # holds it, so it is copied rather than paid for twice (about 90 s per large set).
    same_bootstrap = next(
        (
            a
            for a in maps.values()
            if a.connectedness_100.get("status") == "computed"
            and a.spec.connectedness.resamples == CONNECTEDNESS_RESAMPLES
            and a.spec.connectedness.seed == CONNECTEDNESS_SEED
            and a.spec.relation.n_min == AUDIT_PROVISIONAL_N_MIN
            and a.spec.relation.confidence == PAIR_CONFIDENCE
            and a.roles == roles
        ),
        None,
    )
    connectedness: dict[str, Any] = dict(CONNECTEDNESS_NOT_COMPUTED)
    if connectedness_interval and same_bootstrap is not None:
        connectedness = dict(same_bootstrap.connectedness_100)
    elif connectedness_interval:
        k100 = connectedness_100(
            object_ids,
            roles,
            correlate,
            respondents=len(rescaled),
            resamples=CONNECTEDNESS_RESAMPLES,
            seed=CONNECTEDNESS_SEED,
        )
        connectedness = {
            "status": "computed",
            **k100.to_payload(),
            "ranking": rank_with_ties(k100.intervals()).to_payload(),
        }

    low, high = battery.scale
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
        "battery_id": battery.id,
        "title": battery.title,
        "family": battery.family,
        "objects": [{"id": o.id, "label": o.label} for o in battery.objects],
        "methodology_status": _methodology_status().value,
        "methodology_decision": "PROGRESS D6: the four AIA Sociomap declarations, open",
        "preset": map_spec.methodology_version,
        "rating_scale": [low, high],
        "relation": {
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
                "n_min is the audit's provisional value, pending its Q6"
            ),
        },
        "relation_rescaled": {
            "rule": RESCALE_RULE,
            "rated_with": [b.id for b in rated_with],
            "rating_questions": [q.id for q in rating_questions],
            "excluded_respondents": not_rescaled,
            **rescaled_pairs.model_dump(mode="json"),
            # Audit F4: how strong, whichever its direction, beside the signed r~.
            "abs_r": [[None if v is None else abs(v) for v in row] for row in rescaled_pairs.r],
            "status_counts": rescaled_pairs.counts(),
        },
        "roles": {"declared": battery.roles_declared, "by_object": roles},
        "object_scores": object_scores.to_payload(),
        "connectedness_100": connectedness,
        "sociomap": artifact.model_dump(mode="json"),
        "maps": {method_id: a.to_payload() for method_id, a in maps.items()},
    }


def research_sociomaps(
    spec: ResearchSpecification,
    dataset: FieldworkDataset,
    *,
    methods: Sequence[SociomapMethod],
    connectedness_interval: bool,
) -> dict[str, Any]:
    """Every tracked set's Sociomap. A specification without one has none, and says so.

    ``methods`` are the run's pinned methods (:func:`read_methods`); each is resolved --
    verified and checked computable -- before any number, so a pin this engine cannot
    compute fails here by name. ``connectedness_interval`` is the worker's kill switch for
    the F9 bootstrap, passed by name: off, each set records
    :data:`CONNECTEDNESS_NOT_COMPUTED` instead.
    """
    pinned = read_methods([m.model_dump(mode="json") for m in methods])
    resolved = [m.resolve() for m in pinned]
    map_spec = next(s for s in resolved if isinstance(s, SociomapSpec))
    object_maps = [s for s in resolved if isinstance(s, SociomapSpecV3)]
    return {
        "sociomap_version": SOCIOMAP_VERSION,
        "methods": [
            {"method_id": m.method_id, "spec_fingerprint": m.spec_fingerprint} for m in pinned
        ],
        "methodology_status": _methodology_status().value,
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
            )
            for b in spec.batteries
        ],
        "note": None if spec.batteries else "Návrh nemá sledovanou sadu; Sociomapa nevznikla.",
    }
