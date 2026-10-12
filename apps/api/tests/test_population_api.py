"""``GET /population``: the registry, read-only (plan ``population-operations.md`` P2).

Any member reads it; nobody unauthenticated does. Each version says where it stands,
derived from the populations and their history (never stored): the STATIC reference,
LIVE now, superseded, or only registered. Nothing about the response can write.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from aia_core.domain.population import PopulationKind
from aia_core.domain.population.audience_catalogue import AUDIENCE_CATALOGUE_VERSION
from aia_core.domain.population.czech import CZ_SYNTHETIC_V17
from aia_core.domain.population.versions import (
    DatasetVersion,
    Population,
    PromotionRecord,
    dataset_version_id,
)
from aia_core.infrastructure.db import create_session_factory
from aia_core.infrastructure.population_repository import PopulationRegistryRepository
from aia_core.infrastructure.tables import (
    PopulationDatasetVersionRow,
    PopulationVersionAudienceCatalogueRow,
)
from fastapi import FastAPI
from sqlalchemy import update

DATASET = CZ_SYNTHETIC_V17.dataset_id
AT = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _version(label: str, parent: str | None, minutes: int) -> DatasetVersion:
    sha = _sha(label)
    return DatasetVersion(
        version_id=dataset_version_id(DATASET, sha),
        dataset_id=DATASET,
        label=label,
        content_sha256=sha,
        byte_size=100,
        row_count=6,
        column_count=4,
        contract_id=CZ_SYNTHETIC_V17.contract_id,
        dictionary_sha256=_sha("dictionary"),
        field_names_sha256=_sha("fields"),
        parent_version_id=parent,
        storage_location=f"panels/{label}.csv.gz",
        dictionary_location="dictionary.csv",
        provenance="fictional registry rows for this test",
        imported_at=AT + timedelta(minutes=minutes),
        imported_by="USR-operator",
    )


@pytest.fixture
def registry(app: FastAPI) -> dict[str, str]:
    """Four fictional versions: a root, STATIC, a superseded LIVE, LIVE now."""
    base = _version("v_BASE", None, 0)
    static = _version("v_1", base.version_id, 1)
    old = _version("v_4", static.version_id, 2)
    live = _version("v_5", old.version_id, 3)
    with create_session_factory(app.state.engine)() as session:
        repo = PopulationRegistryRepository(session)
        for v in (base, static, old, live):
            repo.insert_version(v, validation={})
        for pid, kind, version in (
            ("CZ_STATIC_REFERENCE", PopulationKind.STATIC, static),
            ("CZ_LIVE", PopulationKind.LIVE, old),
        ):
            repo.insert_population(
                Population(pid, DATASET, kind, version.version_id, AT, "USR-operator"),
                PromotionRecord(
                    f"PRM-{pid}", pid, None, version.version_id, "USR-operator", "establish", AT
                ),
            )
        repo.apply_promotion(
            Population(
                "CZ_LIVE", DATASET, PopulationKind.LIVE, live.version_id, AT, "USR-operator"
            ),
            PromotionRecord(
                "PRM-move", "CZ_LIVE", old.version_id, live.version_id, "USR-operator",
                "the newer version", AT + timedelta(minutes=5),
            ),
        )  # fmt: skip
        session.commit()
    return {"base": base.version_id, "static": static.version_id, "old": old.version_id,
            "live": live.version_id}  # fmt: skip


def test_an_empty_registry_reads_as_empty(lead: Any, api_prefix: str) -> None:
    body = lead.get(f"{api_prefix}/population").json()
    assert body["dataset_id"] == DATASET
    assert body["versions"] == [] and body["populations"] == [] and body["history"] == []


def test_every_version_says_where_it_stands(
    registry: dict[str, str], viewer: Any, api_prefix: str
) -> None:
    response = viewer.get(f"{api_prefix}/population")
    assert response.status_code == 200
    body = response.json()
    by_id = {v["version_id"]: v for v in body["versions"]}
    assert [v["label"] for v in body["versions"]] == ["v_BASE", "v_1", "v_4", "v_5"]
    assert {k: (by_id[v]["status"], by_id[v]["runtime_eligible"]) for k, v in registry.items()} == {
        "base": ("REGISTERED", False),
        "static": ("STATIC_REFERENCE", True),
        "old": ("SUPERSEDED", True),
        "live": ("LIVE_CURRENT", True),
    }
    assert by_id[registry["live"]]["parent_version_id"] == registry["old"]
    assert {p["population_id"]: p["current_version_id"] for p in body["populations"]} == {
        "CZ_STATIC_REFERENCE": registry["static"],
        "CZ_LIVE": registry["live"],
    }
    moves = [(h["from_version_id"], h["to_version_id"], h["reason"]) for h in body["history"]]
    assert (registry["old"], registry["live"], "the newer version") in moves


def test_any_member_reads_it_and_nobody_unauthenticated(
    registry: dict[str, str], outsider: Any, client: Any, api_prefix: str
) -> None:
    assert outsider.get(f"{api_prefix}/population").status_code == 200
    assert client.get(f"{api_prefix}/population").status_code == 401


def test_the_registry_offers_no_write(lead: Any, api_prefix: str) -> None:
    for method in ("post", "put", "patch", "delete"):
        assert getattr(lead, method)(f"{api_prefix}/population").status_code == 405


# ------------------------------------------------- a version's characteristics (P7c)

#: A fictional dictionary in the reference's layout: three fields of the Czech contract's
#: names, so the route's contract builds a policy over them. No respondent row anywhere.
FICTIONAL_DICTIONARY = (
    "field,block,source,evidence_status,production_grade,recommended_use,description,"
    "persona_eligible\n"
    "vek,population_anchor,Census 2021,POPULATION_ANCHOR,A,PERSONA_OR_ANALYSIS_WITH_SCOPE,"
    "Věk (fictional),yes\n"
    "is_student,core,fictional,CANONICAL_CORE,C,AUDIT_ONLY,Student (fictional),no\n"
    "vaha_strukturalni_2025,weight,fictional,NEW_WEIGHT,T,AUDIT_ONLY,Váha (fictional),no\n"
).encode()


@pytest.fixture
def characterised(app: FastAPI) -> dict[str, str]:
    """Two fictional versions: one keeping its dictionary, one imported before."""
    kept = replace(_version("v_kept", None, 0), dictionary_sha256=_sha_bytes(FICTIONAL_DICTIONARY))
    older = replace(_version("v_older", None, 1), dictionary_sha256=kept.dictionary_sha256)
    with create_session_factory(app.state.engine)() as session:
        repo = PopulationRegistryRepository(session)
        for v in (kept, older):
            repo.insert_version(v, validation={})
        repo.insert_dictionary(
            kept.version_id,
            sha256=kept.dictionary_sha256,
            content=FICTIONAL_DICTIONARY,
            recorded_at=AT,
            recorded_by="test",
        )
        session.commit()
    return {"kept": kept.version_id, "older": older.version_id}


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _characteristics(member: Any, api_prefix: str, version_id: str) -> Any:
    return member.get(f"{api_prefix}/population/versions/{version_id}/characteristics")


def test_a_version_says_what_it_is_made_of(
    characterised: dict[str, str], viewer: Any, api_prefix: str
) -> None:
    response = _characteristics(viewer, api_prefix, characterised["kept"])
    assert response.status_code == 200
    body = response.json()
    assert body["dictionary_kept"] is True and body["label"] == "v_kept"
    by_name = {f["field"]: f for f in body["fields"]}
    assert list(by_name)[:3] == ["vek", "is_student", "vaha_strukturalni_2025"]
    vek = {u["use"]: u for u in by_name["vek"]["uses"]}
    assert vek["AUDIENCE_FILTERING"]["allowed"] is True
    assert by_name["vek"]["description"] == "Věk (fictional)"
    assert by_name["vaha_strukturalni_2025"]["is_weight"] is True
    assert [w["role"] for w in body["weights"] if w["is_default"]] == ["default_current"]
    subpanels = {s["key"]: s for s in body["subpanels"]}
    assert len(subpanels) == 18
    assert (subpanels["young_18_29"]["usable"], subpanels["young_18_29"]["reason"]) == (True, None)
    assert (subpanels["students"]["usable"], subpanels["students"]["reason"]) == (
        False,
        "audit_only",
    )
    assert subpanels["employed"]["reason"] == "unknown_field"
    assert subpanels["young_18_29"]["measured_by_18_6_6"]["rows"] == 2785
    assert body["subpanels_measured_on"] == "17.1.2"


def test_a_version_without_its_dictionary_says_so_and_calls_nothing_usable(
    characterised: dict[str, str], viewer: Any, api_prefix: str
) -> None:
    body = _characteristics(viewer, api_prefix, characterised["older"]).json()
    assert body["dictionary_kept"] is False and body["fields"] == []
    assert {(s["usable"], s["reason"]) for s in body["subpanels"]} == {(None, None)}


def test_a_dictionary_that_does_not_match_its_pin_is_a_conflict(
    app: FastAPI, characterised: dict[str, str], viewer: Any, api_prefix: str
) -> None:
    from aia_core.infrastructure.tables import PopulationVersionDictionaryRow
    from sqlalchemy import update

    with create_session_factory(app.state.engine)() as session:
        session.execute(update(PopulationVersionDictionaryRow).values(content=b"field\nvek\n"))
        session.commit()
    response = _characteristics(viewer, api_prefix, characterised["kept"])
    assert response.status_code == 409
    assert response.json()["code"] == "population_dictionary_mismatch"


def test_an_unknown_version_is_404_and_nobody_unauthenticated_reads_one(
    characterised: dict[str, str], outsider: Any, client: Any, api_prefix: str
) -> None:
    assert _characteristics(outsider, api_prefix, "nope@sha256:00").status_code == 404
    assert _characteristics(outsider, api_prefix, characterised["kept"]).status_code == 200
    assert _characteristics(client, api_prefix, characterised["kept"]).status_code == 401


# --------------------------------------------------------------------------- owned children


@pytest.fixture
def children(app: FastAPI, world: Any) -> dict[str, str]:
    """A shared base with two owned children: ours (primary client) and another org's."""
    from aia_core.application.scope import AuthenticatedPrincipal, ScopeResolver
    from aia_core.domain.population import (
        MaterializedField,
        MaterializedKind,
        PopulationContractExtension,
        VersionOwner,
        owned_version_id,
    )
    from aia_core.infrastructure.scope_repository import ScopeRepository

    base = replace(_version("v_BASE", None, 0), dictionary_sha256=_sha_bytes(FICTIONAL_DICTIONARY))
    extension = PopulationContractExtension(
        base_contract_id=base.contract_id,
        base_field_names_sha256=base.field_names_sha256,
        base_dictionary_sha256=base.dictionary_sha256,
        fields=(
            MaterializedField(
                "pije_kavu_rano", MaterializedKind.BINARY, _sha("definition"), "method", "1"
            ),
        ),
    )
    with create_session_factory(app.state.engine)() as session:
        scope = ScopeRepository(session)
        org, owner = scope.create_organization(
            slug="elsewhere", name="Elsewhere", owner_email="owner@elsewhere.test", owner_name="O"
        )
        admin = ScopeResolver(session).organization_context(
            AuthenticatedPrincipal(user_id=owner.user_id, organization_id=org.organization_id)
        )
        their_client = scope.create_client(admin, slug="theirs", name="Their client")
        repo = PopulationRegistryRepository(session)
        repo.insert_version(base, validation={})
        repo.insert_dictionary(
            base.version_id,
            sha256=base.dictionary_sha256,
            content=FICTIONAL_DICTIONARY,
            recorded_at=AT,
            recorded_by="test",
        )
        repo.insert_extension(extension, recorded_at=AT, recorded_by="test")
        ids = {"base": base.version_id}
        for name, owner_of in (
            ("ours", VersionOwner(world.organization_id, world.client_id("primary"))),
            ("theirs", VersionOwner(org.organization_id, their_client.client_id)),
        ):
            sha = _sha(f"child {name}")
            child = replace(
                base,
                version_id=owned_version_id(DATASET, sha, owner_of),
                label="v_BASE+pije_kavu_rano",
                content_sha256=sha,
                column_count=base.column_count + 1,
                parent_version_id=base.version_id,
                imported_at=AT + timedelta(minutes=1),
                owner=owner_of,
                extension_sha256=extension.sha256,
            )
            repo.insert_version(child, validation={})
            ids[name] = child.version_id
        session.commit()
    ids["extension"] = extension.sha256
    return ids


def test_the_registry_lists_our_child_and_never_another_organizations(
    children: dict[str, str], world: Any, viewer: Any, api_prefix: str
) -> None:
    body = viewer.get(f"{api_prefix}/population").json()
    by_id = {v["version_id"]: v for v in body["versions"]}
    assert set(by_id) == {children["base"], children["ours"]}
    ours = by_id[children["ours"]]
    assert ours["owner_client_id"] == world.client_id("primary")
    assert ours["extension_sha256"] == children["extension"]
    assert ours["parent_version_id"] == children["base"]
    assert by_id[children["base"]]["owner_client_id"] is None
    assert by_id[children["base"]]["extension_sha256"] is None


def test_a_childs_characteristics_are_its_organizations_and_404_to_any_other(
    children: dict[str, str], viewer: Any, outsider: Any, api_prefix: str
) -> None:
    response = _characteristics(viewer, api_prefix, children["ours"])
    assert response.status_code == 200
    body = response.json()
    assert body["dictionary_kept"] is True  # its base's dictionary, re-hashed
    added = {f["field"]: f for f in body["fields"]}["pije_kavu_rano"]
    assert added["materialized"] is True and added["block"] == "materialized"
    uses = {u["use"]: u["allowed"] for u in added["uses"]}
    assert uses["PERSONA_CONSTRUCTION"] and not uses["CLIENT_MEASURED_CLAIM"]
    assert not uses["WEIGHTING"]
    # Every member of our organization reads it (ADR 0019); another organization never does.
    assert _characteristics(outsider, api_prefix, children["ours"]).status_code == 200
    theirs = _characteristics(viewer, api_prefix, children["theirs"])
    assert theirs.status_code == 404 and theirs.json()["code"] == "not_found"


# ------------------------------------------- the audience catalogue (panel-grounded 6b)

#: A catalogue as ``population_ops record-catalogue`` keeps it: fictional counts, one
#: research-only factor the screen is not sent.
FICTIONAL_CATALOGUE: dict[str, Any] = {
    "catalogue_version": AUDIENCE_CATALOGUE_VERSION,
    "categories": [
        {"id": "demography", "label": "Demografie a životní fáze", "description": "d",
         "count": 2, "filterable_count": 2},
        {"id": "research_only", "label": "Research-only / citlivé", "description": "r",
         "count": 1, "filterable_count": 0},
    ],
    "factors": [
        {"id": "vek", "column": "vek", "label": "Věk", "category": "demography",
         "category_label": "Demografie a životní fáze", "kind": "numeric",
         "status": "PANEL_EXISTING", "filterable": True, "sensitive": False,
         "source": "Panel v17", "non_null": 6, "min": 18.0, "max": 89.0, "p10": 20.5,
         "p90": 80.0, "policy_allowed": True, "policy_reason": "allowed"},
        {"id": "pohlavi", "column": "pohlavi", "label": "Pohlaví", "category": "demography",
         "category_label": "Demografie a životní fáze", "kind": "category",
         "status": "PANEL_EXISTING", "filterable": True, "sensitive": False,
         "source": "Panel v17", "non_null": 6,
         "values": [{"value": "žena", "count": 4}, {"value": "muž", "count": 2}],
         "policy_allowed": False, "policy_reason": "unknown_field"},
        {"id": "PHQ9_2022", "column": "PHQ9_2022", "label": "PHQ9",
         "category": "research_only", "category_label": "Research-only / citlivé",
         "kind": "numeric", "status": "PANEL_EXISTING_RESEARCH_ONLY", "filterable": False,
         "sensitive": True, "source": "Research-only panel signal", "non_null": 6,
         "min": 0.0, "max": 27.0, "p10": 1.0, "p90": 20.0, "policy_allowed": False,
         "policy_reason": "unknown_field"},
    ],
    "filterable_count": 2,
    "factor_count": 3,
    "logic": "OR uvnitř jedné dimenze, AND mezi dimenzemi",
}  # fmt: skip


def _keep_catalogue(app: FastAPI, version_id: str, catalogue: dict[str, Any]) -> None:
    content = json.dumps(catalogue, ensure_ascii=False, sort_keys=True)
    with create_session_factory(app.state.engine)() as session:
        PopulationRegistryRepository(session).insert_audience_catalogue(
            version_id,
            catalogue_version=AUDIENCE_CATALOGUE_VERSION,
            sha256=_sha(content),
            content=content,
            recorded_at=AT,
            recorded_by="test",
        )
        session.commit()


def _keep_dictionary(app: FastAPI, version_id: str) -> None:
    with create_session_factory(app.state.engine)() as session:
        repo = PopulationRegistryRepository(session)
        session.execute(
            update(PopulationDatasetVersionRow)
            .where(PopulationDatasetVersionRow.version_id == version_id)
            .values(dictionary_sha256=_sha_bytes(FICTIONAL_DICTIONARY))
        )
        repo.insert_dictionary(
            version_id,
            sha256=_sha_bytes(FICTIONAL_DICTIONARY),
            content=FICTIONAL_DICTIONARY,
            recorded_at=AT,
            recorded_by="test",
        )
        session.commit()


def test_the_audience_catalogue_is_lives_kept_one_without_what_is_not_drawn(
    app: FastAPI, registry: dict[str, str], viewer: Any, api_prefix: str
) -> None:
    _keep_dictionary(app, registry["live"])
    _keep_catalogue(app, registry["live"], FICTIONAL_CATALOGUE)
    # A catalogue kept for a version LIVE has left is not the one served.
    _keep_catalogue(app, registry["old"], {**FICTIONAL_CATALOGUE, "factors": []})
    response = viewer.get(f"{api_prefix}/population/audience-catalogue")
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["version_id"], body["version_label"]) == (registry["live"], "v_5")
    assert [f["id"] for f in body["factors"]] == ["vek", "pohlavi"]  # research-only not sent
    assert [c["id"] for c in body["categories"]] == ["demography", "research_only"]
    assert body["factor_count"] == 3
    pohlavi = body["factors"][1]
    assert pohlavi["values"] == [{"value": "žena", "count": 4}, {"value": "muž", "count": 2}]
    assert (pohlavi["policy_allowed"], pohlavi["policy_reason"]) == (False, "unknown_field")
    subpanels = {s["key"]: s for s in body["subpanels"]}
    assert len(subpanels) == 18
    young = subpanels["young_18_29"]
    assert young["filters"] == {"vek": [18, 29]} and young["usable"] is True
    assert young["measured_by_18_6_6"]["rows"] == 2785
    assert subpanels["students"]["filters"] == {"is_student": 1}
    assert subpanels["students"]["usable"] is False


def test_no_live_population_or_no_kept_catalogue_says_which(
    app: FastAPI, lead: Any, api_prefix: str, registry_or_none: dict[str, str] | None
) -> None:
    url = f"{api_prefix}/population/audience-catalogue"
    if registry_or_none is None:
        response = lead.get(url)
        assert response.status_code == 404
        assert response.json()["code"] == "population_not_established"
    else:
        response = lead.get(url)
        assert response.status_code == 404
        assert response.json()["code"] == "audience_catalogue_missing"
        assert "record-catalogue" in response.json()["message"]


@pytest.fixture(params=["empty", "established"])
def registry_or_none(request: Any) -> dict[str, str] | None:
    return None if request.param == "empty" else request.getfixturevalue("registry")


def test_a_kept_catalogue_that_does_not_hash_is_a_conflict(
    app: FastAPI, registry: dict[str, str], viewer: Any, client: Any, api_prefix: str
) -> None:
    _keep_catalogue(app, registry["live"], FICTIONAL_CATALOGUE)
    with create_session_factory(app.state.engine)() as session:
        session.execute(update(PopulationVersionAudienceCatalogueRow).values(content="{}"))
        session.commit()
    response = viewer.get(f"{api_prefix}/population/audience-catalogue")
    assert response.status_code == 409
    assert response.json()["code"] == "audience_catalogue_mismatch"
    assert client.get(f"{api_prefix}/population/audience-catalogue").status_code == 401


# ------------------------------------------------ the audience preview (panel-grounded 6c)


@pytest.fixture
def counted(app: FastAPI, fictional_live: Any) -> Any:
    """A fictional LIVE in the API's database, and the API's previewer over it."""
    app.state.audience_previewer = fictional_live.previewer()
    return fictional_live


def test_the_preview_counts_the_audience_and_asks_the_sampler(
    counted: Any, viewer: Any, api_prefix: str
) -> None:
    url = f"{api_prefix}/population/audience-preview"
    response = viewer.post(url, json={"filters": {"vek": {"min": 30, "max": 59}}, "n": 200})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["population_rows"] == counted.rows
    assert 0 < body["selected_rows"] < counted.rows and body["selected_donors"] > 0
    assert body["filters_applied"] == {"vek": {"min": 30.0, "max": 59.0}}
    assert body["audience"]["ok"] is True and body["sample"]["ok"] is True
    assert body["version_label"] == "v1_4"
    # What the response holds is counts and verdicts: no row, no respondent value.
    assert set(body) == {
        "version_id", "version_label", "population_rows", "selected_rows", "selected_donors",
        "filters_applied", "audience", "n", "sample", "seed",
    }  # fmt: skip

    small = viewer.post(url, json={"filters": {}, "n": 8}).json()
    assert small["sample"]["reason"] == "sampling_unrepresentative"  # OI-99, said first
    refused = viewer.post(url, json={"filters": {"neexistuje": 1}}).json()
    assert refused["audience"]["reason"] == "sampling_filter_invalid"
    assert viewer.post(url, json={"n": 0}).status_code == 422
    # A boolean is not a sample size, whatever lax coercion would make of it (AGENTS.md).
    for flag in (True, False):
        assert viewer.post(url, json={"n": flag}).status_code == 422


def test_the_preview_loads_live_once_per_version(
    counted: Any, viewer: Any, api_prefix: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aia_core.application import audience_preview as module

    loads = 0
    real = module.PopulationRuntime.load

    def counting(self: Any, binding: Any) -> Any:
        nonlocal loads
        loads += 1
        return real(self, binding)

    monkeypatch.setattr(module.PopulationRuntime, "load", counting)
    url = f"{api_prefix}/population/audience-preview"
    for _ in range(3):
        assert viewer.post(url, json={"filters": {}}).status_code == 200
    assert loads == 1


def test_without_an_asset_root_there_is_no_preview(
    app: FastAPI, viewer: Any, api_prefix: str
) -> None:
    url = f"{api_prefix}/population/audience-preview"
    app.state.audience_previewer = None
    unavailable = viewer.post(url, json={"filters": {}})
    assert unavailable.status_code == 503
    assert unavailable.json()["code"] == "audience_preview_unavailable"


def test_a_preview_over_no_live_population_is_404_and_needs_a_member(
    app: FastAPI, viewer: Any, client: Any, api_prefix: str
) -> None:
    from aia_core.application.audience_preview import AudiencePreviewer
    from aia_core.domain.population.enrichment import AudienceDimensionsEnricher
    from aia_core.infrastructure.population_source import InMemoryPopulationSource

    app.state.audience_previewer = AudiencePreviewer(
        contract=CZ_SYNTHETIC_V17,
        source=InMemoryPopulationSource({}),
        enricher=AudienceDimensionsEnricher(),
        population_id="CZ_LIVE",
    )
    url = f"{api_prefix}/population/audience-preview"
    missing = viewer.post(url, json={"filters": {}})
    assert missing.status_code == 404 and missing.json()["code"] == "population_not_established"
    assert client.post(url, json={"filters": {}}).status_code == 401


def test_a_population_that_will_not_load_is_unavailable_not_an_error(
    counted: Any, viewer: Any, api_prefix: str
) -> None:
    counted.source.put("panels/v1_4.csv.gz", b"not the version")
    response = viewer.post(f"{api_prefix}/population/audience-preview", json={"filters": {}})
    assert response.status_code == 503
    assert response.json()["code"] == "population_unavailable"


def test_the_audience_routes_read_the_population_the_composition_names(
    app: FastAPI, fictional_live: Any, viewer: Any, api_prefix: str
) -> None:
    """Every deployment names the Czech LIVE; the UI workbench names a fictional one, the
    only way fictional rows reach these routes (panel-grounded-respondents 6f)."""
    from aia_api.dependencies import CZECH_AUDIENCE, AudiencePopulation

    assert CZECH_AUDIENCE.population_id == "CZ_LIVE"
    url = f"{api_prefix}/population/audience-catalogue"
    assert viewer.get(url).json()["code"] == "population_not_established"  # no Czech LIVE here

    with create_session_factory(app.state.engine)() as session:
        rt = fictional_live.runtime(session)
        live = PopulationRegistryRepository(session).population(fictional_live.live_id)
        assert live is not None
        version_id = live.current_version_id
        rt.record_audience_catalogue(version_id, recorded_by="test")
        session.commit()
    app.state.audience_population = AudiencePopulation(
        contract=fictional_live.contract, population_id=fictional_live.live_id
    )
    body = viewer.get(url).json()
    assert body["version_id"] == version_id and body["version_label"] == "v1_4"
    assert "vek" in [f["id"] for f in body["factors"]]


def test_a_previewer_already_installed_survives_the_servers_startup(
    app: FastAPI, fictional_live: Any
) -> None:
    """The workbench installs its previewer, then the server's startup runs again; the 6f
    journey found it reset to none (a 503)."""
    from aia_api.dependencies import init_app_state

    installed = fictional_live.previewer()
    app.state.audience_previewer = installed
    kept = {k: getattr(app.state, k) for k in ("engine", "session_factory", "artifact_store")}
    app.state.engine = None  # as after the setup client's shutdown
    try:
        init_app_state(app, app.state.settings)
        assert app.state.audience_previewer is installed
    finally:
        app.state.engine.dispose()
        for name, value in kept.items():
            setattr(app.state, name, value)
