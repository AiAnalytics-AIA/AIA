"""The MVP's activation profile (mvp-master-plan MP6): each row READY or NOT_READY, with its
reason, from the configuration alone. No row composes a wire or makes a call."""

from __future__ import annotations

import socket
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from aia_executors.activation import POPULATION_CONTRACT, PROFILE, Readiness, judge

#: What bin/sync-population.sh lands on the develop host, by base name.
SYNC_LIST = Path(__file__).resolve().parents[3] / "deploy" / "develop" / "population" / "v17.files"

#: A fictional contract small enough to write: one companion and one panel version.
FICTIONAL_CONTRACT = SimpleNamespace(
    contract_id="fictional/v1",
    companions=(SimpleNamespace(asset_id="COMPANION.csv", byte_size=9),),
    known_versions=(SimpleNamespace(label="v1_0", byte_size=7),),
)

_AI_ROWS = (
    "ai_runtime",
    "route_classes",
    "research_agents",
    "study_lead",
    "population_personas",
    "analysis",
    "client_source_proposals",
)

#: A runtime with every MVP switch on, shaped like develop's Parameter Store (test prices).
ON: dict[str, str] = {
    "AIA_ENV": "develop",
    "AIA_AI_RUNTIME_ENABLED": "true",
    "AIA_AI_ROUTE_ID": "bedrock-eu-primary",
    "AIA_BEDROCK_REGION": "eu-central-1",
    "AIA_BEDROCK_MODEL_ID": "eu.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "AIA_AI_POLICY_VERSION": "aia-model-policy-test-1",
    "AIA_BEDROCK_INPUT_USD_PER_MTOK": "3",
    "AIA_BEDROCK_OUTPUT_USD_PER_MTOK": "15",
    "AIA_BEDROCK_MAX_OUTPUT_TOKENS": "8192",
    "AIA_BEDROCK_CONTEXT_WINDOW_TOKENS": "200000",
    "AIA_AI_ROUTE_EU_PROCESSING_APPROVED": "true",
    "AIA_AI_ROUTE_EXCLUDED_FROM_TRAINING": "true",
    "AIA_AI_ROUTE_APPROVED_FOR": (
        "CLASS_A_CLIENT_CONFIDENTIAL,CLASS_B_DERIVED_CLIENT,CLASS_C_INTERNAL"
    ),
    "AIA_AI_ROUTE_RETENTION_DAYS": "0",
    "AIA_AI_FIELDWORK_MAX_OUTPUT_TOKENS": "1024",
    "AIA_AI_FIELDWORK_RESERVATION_USD": "0.25",
    "AIA_AI_RESEARCH_AGENTS_ENABLED": "true",
    "AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS": "4096",
    "AIA_AI_RESEARCH_RESERVATION_USD": "2",
    "AIA_AI_RESEARCH_LEAD_ENABLED": "true",
    "AIA_AI_RESEARCH_LEAD_MAX_OUTPUT_TOKENS": "1500",
    "AIA_AI_RESEARCH_LEAD_RESERVATION_USD": "1.02",
    "AIA_AI_ANALYSIS_ENABLED": "true",
    "AIA_AI_ANALYSIS_MAX_OUTPUT_TOKENS": "4096",
    "AIA_AI_ANALYSIS_RESERVATION_USD": "2",
    "AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED": "true",
    "AIA_AI_CLIENT_SOURCE_MAX_OUTPUT_TOKENS": "2048",
    "AIA_AI_CLIENT_SOURCE_RESERVATION_USD": "1",
    "AIA_AI_POPULATION_PERSONAS_ENABLED": "true",
    "AIA_DEEP_RESEARCH_ENABLED": "true",
    "AIA_DEEP_RESEARCH_WEB_SEARCH": "brave",
    "AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000": "5",
    "AIA_DEEP_RESEARCH_BRAVE_PRICES_AS_OF": "2026-10-01",
    "AIA_DEEP_RESEARCH_BRAVE_API_KEY": "brave-secret-value",
    "AIA_DEEP_RESEARCH_CONNECTORS": "wayback",
    "AIA_DEEP_RESEARCH_COMMON_CRAWL": "true",
    "AIA_DEEP_RESEARCH_AGENT_DIRECTED": "true",
    "AIA_DEEP_RESEARCH_LEAD": "true",
    "AIA_REPORT_PDF_ENABLED": "true",
    "AIA_ERROR_TRACKING_DSN": "https://publickey@errors.example.test/1",
}


@pytest.fixture
def on(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Every switch on, over a fictional population that holds every file its contract pins."""
    monkeypatch.setattr("aia_executors.activation.POPULATION_CONTRACT", FICTIONAL_CONTRACT)
    population = tmp_path / "population"
    population.mkdir()
    (population / "COMPANION.csv").write_bytes(b"a,b\n1,2\n\n")
    (population / "PANEL_v1_0.csv.gz").write_bytes(b"\x1f\x8b0000\n")
    return {**ON, "AIA_POPULATION_ASSET_ROOT": str(population)}


@pytest.fixture
def soffice(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A LibreOffice that answers ``--version``, as the converter asks at start, whether or not
    the host has one (CI does not)."""
    stand_in = tmp_path / "bin" / "soffice"
    stand_in.parent.mkdir()
    stand_in.write_text("#!/bin/sh\necho 'LibreOffice 0.0 (test stand-in)'\n")
    stand_in.chmod(0o755)
    monkeypatch.setattr("aia_core.infrastructure.report_pdf.shutil.which", lambda _: str(stand_in))


def _rows(env: dict[str, str]) -> dict[str, Readiness]:
    return {row.key: readiness for row, readiness in judge(env)}


def test_every_row_is_judged_once_in_the_profiles_order() -> None:
    keys = [row.key for row in PROFILE]
    assert len(keys) == len(set(keys))
    assert [row.key for row, _ in judge({})] == keys


def test_with_nothing_set_every_row_is_not_ready_and_names_its_switch() -> None:
    rows = _rows({"AIA_ENV": "develop"})
    assert not any(r.ready for r in rows.values())
    for key in _AI_ROWS:
        assert rows[key].reason == "AIA_AI_RUNTIME_ENABLED is not true"
    assert rows["deep_research"].reason == "AIA_DEEP_RESEARCH_ENABLED is not true"
    assert rows["report_pdf"].reason == "AIA_REPORT_PDF_ENABLED is not true"
    assert rows["lead_plans"].reason.startswith("not built yet (lead-orchestration#LO3")
    assert rows["run_qc"].reason.startswith("not built yet (run-qc-and-checkpoint#RQC2")
    assert rows["population_assets"].reason == "AIA_POPULATION_ASSET_ROOT is not set"


def test_every_switch_on_reads_ready_but_the_two_not_built(
    on: dict[str, str], soffice: None
) -> None:
    rows = _rows(on)
    assert {k for k, r in rows.items() if not r.ready} == {"lead_plans", "run_qc"}
    assert rows["route_classes"].reason == "A, B and C approved, retention 0 days"
    assert rows["study_lead"].reason.startswith("turns answer on the route's eu.anthropic")


def test_a_refused_runtime_is_not_ready_with_the_workers_own_words(on: dict[str, str]) -> None:
    rows = _rows({**on, "AIA_BEDROCK_REGION": "us-east-1"})
    for key in _AI_ROWS:
        assert not rows[key].ready
        assert "AIA_BEDROCK_REGION='us-east-1' is not an EU region" in rows[key].reason


def test_a_route_other_than_the_panels_takes_ai_but_not_the_panel(on: dict[str, str]) -> None:
    rows = _rows({**on, "AIA_AI_ROUTE_ID": "bedrock-eu-other"})
    assert rows["ai_runtime"].ready
    assert rows["population_personas"] == Readiness(
        False, "AIA_AI_ROUTE_ID is bedrock-eu-other; panel data may reach bedrock-eu-primary"
    )


def test_a_route_for_class_c_alone_names_every_gap(on: dict[str, str]) -> None:
    env = {**on, "AIA_AI_ROUTE_APPROVED_FOR": "CLASS_C_INTERNAL"}
    del env["AIA_AI_ROUTE_RETENTION_DAYS"]
    assert _rows(env)["route_classes"] == Readiness(
        False,
        "not approved for CLASS_A_CLIENT_CONFIDENTIAL; not approved for CLASS_B_DERIVED_CLIENT; "
        "AIA_AI_ROUTE_RETENTION_DAYS is unspecified",
    )


def test_a_route_for_class_c_alone_parks_every_row_whose_material_it_refuses(
    on: dict[str, str],
) -> None:
    """§2.2, G3/G4: a design is Class B, approved knowledge and panel personas Class A; a route
    for C alone parks each of these, and each row says which class and what parks."""
    rows = _rows({**on, "AIA_AI_ROUTE_APPROVED_FOR": "CLASS_C_INTERNAL"})
    a_and_b = "the route refuses CLASS_A_CLIENT_CONFIDENTIAL, CLASS_B_DERIVED_CLIENT"
    assert rows["research_agents"] == Readiness(False, f"{a_and_b}: every design job parks")
    assert rows["study_lead"] == Readiness(False, f"{a_and_b}: every turn parks")
    assert rows["analysis"] == Readiness(False, f"{a_and_b}: a modelled run's analysis parks")
    assert rows["population_personas"] == Readiness(
        False, "the route refuses CLASS_A_CLIENT_CONFIDENTIAL: every panel run parks"
    )
    assert rows["client_source_proposals"] == Readiness(
        False, "the route refuses CLASS_A_CLIENT_CONFIDENTIAL: every proposal run parks"
    )
    assert rows["ai_runtime"].ready


def test_under_advisory_gates_a_refused_class_passes_and_the_row_says_so(
    on: dict[str, str],
) -> None:
    """Develop (plan develop-class-advisory): a class-only refusal is a recorded pass."""
    rows = _rows(
        {**on, "AIA_AI_ROUTE_APPROVED_FOR": "CLASS_C_INTERNAL", "AIA_DATA_CLASS_GATES": "advisory"}
    )
    for key in ("research_agents", "study_lead", "analysis", "population_personas"):
        assert rows[key].ready and rows[key].reason.endswith("pass only as advisory (develop)")
    assert not rows["route_classes"].ready  # the approval itself is still not recorded


def test_panel_personas_without_the_population_on_disk_are_not_ready(
    on: dict[str, str], tmp_path: Path
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    rows = _rows({**on, "AIA_POPULATION_ASSET_ROOT": str(empty)})
    assert not rows["population_personas"].ready and not rows["population_assets"].ready
    assert rows["population_assets"].reason == (
        f"{empty} lacks 2 file(s) fictional/v1 pins, among them COMPANION.csv, the v1_0 panel "
        "(bin/sync-population.sh)"
    )


def test_a_placeholder_or_a_truncated_panel_is_not_the_population(on: dict[str, str]) -> None:
    """Codex on #1050: a directory that is not empty is not yet a population. A file the
    contract does not name, or the panel at another size, reads NOT_READY."""
    root = Path(on["AIA_POPULATION_ASSET_ROOT"])
    (root / "PANEL_v1_0.csv.gz").write_bytes(b"\x1f\x8b")
    (root / "placeholder").write_text("x", encoding="utf-8")
    rows = _rows(on)
    assert not rows["population_assets"].ready
    assert "the v1_0 panel" in rows["population_assets"].reason
    assert not rows["population_personas"].ready


def test_the_panels_the_profile_looks_for_are_the_ones_the_sync_lands() -> None:
    """The real contract's panels, by their label and size, are the files
    bin/sync-population.sh lands (test_population_carry_over holds the companions)."""
    landed = {}
    for line in SYNC_LIST.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            _, size, _, path = line.split()
            landed[path.rsplit("/", 1)[-1]] = int(size)
    for version in POPULATION_CONTRACT.known_versions:
        found = [n for n, s in landed.items() if n.endswith(f"_{version.label}.csv.gz")]
        assert found and landed[found[0]] == version.byte_size, version.label
    for companion in POPULATION_CONTRACT.companions:
        assert landed[companion.asset_id] == companion.byte_size


def test_the_lead_on_without_its_keys_parks_every_turn(on: dict[str, str]) -> None:
    env = {k: v for k, v in on.items() if not k.startswith("AIA_AI_RESEARCH_LEAD_R")}
    assert _rows(env)["study_lead"] == Readiness(
        False,
        "AIA_AI_RESEARCH_LEAD_MAX_OUTPUT_TOKENS or _RESERVATION_USD unset: every turn parks",
    )


def test_deep_research_needs_research_agents_and_a_priced_brave(on: dict[str, str]) -> None:
    rows = _rows({**on, "AIA_AI_RESEARCH_AGENTS_ENABLED": "false"})
    assert rows["deep_research"] == Readiness(
        False, "AIA_DEEP_RESEARCH_ENABLED needs AIA_AI_RESEARCH_AGENTS_ENABLED"
    )
    keyless = {k: v for k, v in on.items() if k != "AIA_DEEP_RESEARCH_BRAVE_API_KEY"}
    assert _rows(keyless)["deep_research"] == Readiness(
        False, "AIA_DEEP_RESEARCH_WEB_SEARCH=brave needs AIA_DEEP_RESEARCH_BRAVE_API_KEY"
    )


def test_deep_research_without_connectors_or_common_crawl_is_not_ready(on: dict[str, str]) -> None:
    """Codex on #1050: Deep Research on with a priced Brave composes no connector and no archive
    when none is listed and Common Crawl is off; each says so on a row of its own."""
    rows = _rows({**on, "AIA_DEEP_RESEARCH_CONNECTORS": "", "AIA_DEEP_RESEARCH_COMMON_CRAWL": ""})
    assert rows["deep_research"].ready
    assert rows["deep_research_connectors"] == Readiness(
        False, "AIA_DEEP_RESEARCH_CONNECTORS lists none"
    )
    assert rows["deep_research_common_crawl"] == Readiness(
        False, "AIA_DEEP_RESEARCH_COMMON_CRAWL is not true"
    )


def test_deep_research_needs_brave_and_its_lead_needs_agent_directed_mode(
    on: dict[str, str],
) -> None:
    rows = _rows({**on, "AIA_DEEP_RESEARCH_WEB_SEARCH": "wikipedia"})
    assert rows["deep_research"] == Readiness(
        False, "AIA_DEEP_RESEARCH_WEB_SEARCH is wikipedia, not brave"
    )
    rows = _rows({**on, "AIA_DEEP_RESEARCH_AGENT_DIRECTED": "false", "AIA_DEEP_RESEARCH_LEAD": ""})
    assert rows["deep_research_agent_directed"].reason == (
        "AIA_DEEP_RESEARCH_AGENT_DIRECTED is not true"
    )
    assert rows["deep_research_lead"].reason == "AIA_DEEP_RESEARCH_LEAD is not true"
    rows = _rows({**on, "AIA_DEEP_RESEARCH_LEAD": "maybe"})
    assert rows["deep_research_lead"] == Readiness(
        False, "AIA_DEEP_RESEARCH_LEAD='maybe' is not true or false"
    )


def test_report_pdfs_on_without_libreoffice_are_not_ready(
    on: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("aia_core.infrastructure.report_pdf.shutil.which", lambda _: None)
    assert _rows(on)["report_pdf"] == Readiness(
        False, "AIA_REPORT_PDF_ENABLED is on and soffice is not installed"
    )


def test_a_directory_that_cannot_be_read_is_not_ready_never_a_failed_smoke(
    on: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def refused(_: str) -> Any:
        raise PermissionError(13, "Permission denied", "/srv/population/v17")

    monkeypatch.setattr("aia_executors.activation.os.scandir", refused)
    rows = _rows(on)
    assert rows["population_assets"] == Readiness(
        False, "[Errno 13] Permission denied: '/srv/population/v17'"
    )
    assert not rows["population_personas"].ready


def test_no_reason_carries_a_secret_value(on: dict[str, str], soffice: None) -> None:
    reasons = " ".join(r.reason for r in _rows(on).values())
    assert "publickey" not in reasons and "brave-secret-value" not in reasons


def test_no_row_opens_a_connection(
    on: dict[str, str], soffice: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """E05: composition readiness makes no call. Any socket connection fails this test."""

    def refuse(*_: Any, **__: Any) -> None:
        raise AssertionError("an activation row opened a connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    assert len(judge(on)) == len(PROFILE)
