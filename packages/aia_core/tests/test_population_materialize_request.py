"""Asking for a materialized dimension: the definition, the checks, the frozen request (P4d2).

The definition is checked alone (its contract); the service then checks it against the base
version LIVE points at, over the fictional population in ``conftest.py``, from a study scope.
Nothing is enqueued here: the template, executor and enqueue land together in P4d3.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.application.materialize import (
    MaterializationRefused,
    prepare_materialization,
)
from aia_core.application.population import PopulationRuntime
from aia_core.application.population_characteristics import shared_version_policy
from aia_core.domain.population import MaterializedKind, PopulationKind
from aia_core.domain.population.definition import (
    DEFINITION_CONTRACT,
    DefinitionRefused,
    DimensionDefinition,
    EvidenceAnchor,
    MissingnessRule,
    PredictorSpec,
)
from aia_core.domain.population.policy import FieldUse
from aia_core.domain.scope import ScopeDenied

EVIDENCE = EvidenceAnchor(knowledge_item_id="KNW-fictional", revision=2, span="34 % ráno")


def definition(**change: Any) -> DimensionDefinition:
    fields: dict[str, Any] = {
        "dimension_id": "pije_kavu_rano",
        "version": 1,
        "construct": "morning coffee",
        "label": "Pije kávu ráno",
        "kind": MaterializedKind.BINARY,
        "target": 0.34,
        "evidence": EVIDENCE,
        "predictors": (PredictorSpec("vek"),),
        "missingness": MissingnessRule.PREDICTOR_MEAN,
        "range": (0.0, 1.0),
    }
    fields.update(change)
    return DimensionDefinition(**fields)


# --------------------------------------------------------------------------- the definition


def test_a_definition_is_identified_by_its_content_and_reads_back() -> None:
    d = definition()
    assert d.sha256 == definition().sha256
    assert DimensionDefinition.from_payload(d.payload()) == d
    assert d.payload()["contract"] == DEFINITION_CONTRACT
    assert definition(target=0.35).sha256 != d.sha256
    spec = d.evidence_spec()
    assert (spec.kind, spec.target, spec.predictors[0].column) == (
        MaterializedKind.BINARY,
        0.34,
        "vek",
    )


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"dimension_id": "Pije Kávu"}, "dimension_id_invalid"),
        ({"version": 0}, "version_invalid"),
        ({"label": " "}, "unnamed"),
        ({"target": 1.0}, "target_out_of_range"),
        ({"kind": MaterializedKind.SCALE_1_10, "target": 11.0, "range": (1.0, 10.0)},
         "target_out_of_range"),
        ({"predictors": ()}, "no_predictor"),
        ({"predictors": (PredictorSpec("vek"), PredictorSpec("vek"))}, "predictor_repeated"),
        ({"range": (1.0, 10.0)}, "range_invalid"),
    ],
)  # fmt: skip
def test_a_definition_that_misses_the_contract_is_refused_by_name(
    change: dict[str, Any], reason: str
) -> None:
    with pytest.raises(DefinitionRefused) as refused:
        definition(**change)
    assert refused.value.reason == reason


def test_its_parts_refuse_what_they_cannot_say() -> None:
    with pytest.raises(DefinitionRefused, match="span"):
        EvidenceAnchor(knowledge_item_id="KNW-x", revision=1, span="")
    with pytest.raises(DefinitionRefused) as zero:
        PredictorSpec("vek", strength=0)  # 18.6.6 read 0 as 1; a typed definition may not
    assert zero.value.reason == "strength_invalid"
    with pytest.raises(DefinitionRefused) as other:
        DimensionDefinition.from_payload({**definition().payload(), "contract": "other/v9"})
    assert other.value.reason == "contract"
    with pytest.raises(DefinitionRefused) as broken:
        DimensionDefinition.from_payload({**definition().payload(), "evidence": {}})
    assert broken.value.reason == "malformed"


# --------------------------------------------------------------------------- the service


@pytest.fixture
def live(session: Session, synthetic_population: Any) -> dict[str, Any]:
    """The fictional population imported, its dictionary kept, STATIC and LIVE established."""
    from aia_core.application.population_authority import (
        PopulationAuthority,
        PopulationOperatorConfig,
    )
    from aia_core.application.scope import AuthenticatedPrincipal

    operator = PopulationAuthority(
        PopulationOperatorConfig.from_names(
            {"owner": ("POPULATION_ESTABLISH", "POPULATION_PROMOTE")}
        )
    ).operator_context(AuthenticatedPrincipal(user_id="owner", organization_id="platform"))
    pop = synthetic_population
    runtime = PopulationRuntime(session, contract=pop.contract, source=pop.source)
    versions = {
        label: runtime.import_version(
            label=label,
            panel_location=pop.location(label),
            dictionary_location=pop.dictionary_location,
            provenance="fictional test bundle",
            imported_by="importer",
        )
        for label in ("v1_BASE", "v1_1", "v1_4")
    }
    runtime.establish(
        population_id="SYN_STATIC",
        kind=PopulationKind.STATIC,
        version_id=versions["v1_1"].version_id,
        operator=operator,
        reason="anchor",
    )
    runtime.establish(
        population_id="SYN_LIVE",
        kind=PopulationKind.LIVE,
        version_id=versions["v1_4"].version_id,
        operator=operator,
        reason="runtime",
    )
    kept = shared_version_policy(session, contract=pop.contract, version=versions["v1_4"])
    assert kept is not None
    dictionary, policy = kept
    allowed = [
        f for f in dictionary.fields if policy.decide(f, FieldUse.PERSONA_CONSTRUCTION).allowed
    ]
    refused = [
        f for f in dictionary.fields if not policy.decide(f, FieldUse.PERSONA_CONSTRUCTION).allowed
    ]
    return {"pop": pop, "live": versions["v1_4"], "allowed": allowed, "refused": refused}


def prepare(session: Session, scope: Any, live: dict[str, Any], d: DimensionDefinition) -> Any:
    return prepare_materialization(
        session,
        scope,
        definition=d,
        contract=live["pop"].contract,
        population_id="SYN_LIVE",
    )


def test_a_request_is_frozen_to_the_studys_owner_lives_base_and_the_definition(
    session: Session, scoped: Any, live: dict[str, Any]
) -> None:
    scope = scoped.scope()
    d = definition(predictors=(PredictorSpec(live["allowed"][0]),))
    request = prepare(session, scope, live, d)
    assert (request.owner.organization_id, request.owner.client_id) == (
        scope.organization_id,
        scope.client_id,
    )
    assert request.study_id == scope.study_id
    assert request.base.version_id == live["live"].version_id
    step = request.step_input()
    assert step["definition_sha256"] == d.sha256
    assert step["base_version_id"] == live["live"].version_id
    assert DimensionDefinition.from_payload(step["definition"]) == d
    # One child per owner, base and definition -- from any of the client's studies -- and
    # one run per study: a run's key is unique across studies but found within one.
    sibling = prepare(session, scoped.scope(study="sibling"), live, d)
    assert sibling.child_key == request.child_key
    assert sibling.idempotency_key != request.idempotency_key
    assert request.study_id in request.idempotency_key
    other_client = prepare(session, scoped.scope(user="other_lead", study="other_client"), live, d)
    assert other_client.child_key != request.child_key
    changed = prepare(session, scope, live, replace(d, target=0.4))
    assert changed.child_key != request.child_key


def test_a_predictor_the_base_lacks_or_may_not_build_a_persona_is_refused(
    session: Session, scoped: Any, live: dict[str, Any]
) -> None:
    scope = scoped.scope()
    with pytest.raises(MaterializationRefused) as unknown:
        prepare(session, scope, live, definition(predictors=(PredictorSpec("no_such_field"),)))
    assert unknown.value.reason == "predictor_unknown"
    assert live["refused"], "the fictional dictionary has an audit-only field"
    with pytest.raises(MaterializationRefused) as audit:
        prepare(session, scope, live, definition(predictors=(PredictorSpec(live["refused"][0]),)))
    assert audit.value.reason == "predictor_not_permitted"


def test_a_name_the_base_already_has_is_refused(
    session: Session, scoped: Any, live: dict[str, Any]
) -> None:
    taken = live["allowed"][0]
    with pytest.raises(MaterializationRefused) as refused:
        prepare(
            session,
            scoped.scope(),
            live,
            definition(dimension_id=taken, predictors=(PredictorSpec(live["allowed"][-1]),)),
        )
    assert refused.value.reason == "name_taken"


def test_without_live_there_is_no_base_and_without_rights_nothing_is_checked(
    session: Session, scoped: Any, synthetic_population: Any
) -> None:
    with pytest.raises(MaterializationRefused) as no_live:
        prepare_materialization(
            session,
            scoped.scope(),
            definition=definition(),
            contract=synthetic_population.contract,
            population_id="SYN_LIVE",
        )
    assert no_live.value.reason == "population_not_established"
    scope = scoped.scope()
    closed = replace(scope, permissions=frozenset())
    with pytest.raises(ScopeDenied):
        prepare_materialization(
            session,
            closed,
            definition=definition(),
            contract=synthetic_population.contract,
            population_id="SYN_LIVE",
        )
