"""The population operator command (plan ``population-operations.md`` P1).

Over a fictional bundle written to disk -- six invented rows, a dictionary, a contract
pinning both -- through the real filesystem source, registry and authority: a named
operator imports, establishes and promotes; the history records them by verified user
id; and every refusal (no such person, a person the configuration does not name, a
permission they do not hold, a stale expected version, a malformed key) writes nothing.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
from pathlib import Path
from typing import Any

import pytest
from aia_core.domain.population import (
    KnownVersion,
    PopulationImportContract,
    WeightScheme,
    content_sha256,
    field_names_fingerprint,
)
from aia_core.infrastructure.population_repository import PopulationRegistryRepository
from aia_core.infrastructure.population_source import FilesystemPopulationSource
from aia_executors.population_ops import (
    ASSET_ROOT_KEY,
    OPERATORS_KEY,
    OperatorConfigError,
    main,
    operator_config,
    run,
)
from sqlalchemy.orm import Session, sessionmaker

FIELDS = ("row_id", "vek", "segment", "w_main")
LABELS = ("f1_BASE", "f1_1", "f1_4", "f1_5")
BOTH = ("POPULATION_ESTABLISH", "POPULATION_PROMOTE")


def _rows(suffix: str) -> list[dict[str, str]]:
    """Six fictional respondents; only the segment differs between versions."""
    ages = ("34", "71", "", "18", "45", "100")
    weights = ("1.5", "0.5", "2.0", "1.0", "3.25", "0.75")
    return [
        {"row_id": f"R{i}", "vek": age, "segment": f"s{suffix}", "w_main": w}
        for i, (age, w) in enumerate(zip(ages, weights, strict=True), start=1)
    ]


def _gzip_csv(rows: list[dict[str, str]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(FIELDS)
    for row in rows:
        writer.writerow([row[f] for f in FIELDS])
    return gzip.compress(buffer.getvalue().encode("utf-8"), mtime=0)


def _dictionary() -> bytes:
    policy = {
        "row_id": ("provenance", "PROVENANCE_OR_CORE", "T", "AUDIT_ONLY", "no"),
        "vek": (
            "population_anchor",
            "POPULATION_ANCHOR",
            "A",
            "PERSONA_OR_ANALYSIS_WITH_SCOPE",
            "yes",
        ),
        "segment": ("core", "CANONICAL_CORE", "C", "HISTORICAL_OR_EXPLORATORY", "yes"),
        "w_main": ("weight", "NEW_WEIGHT", "T", "AUDIT_ONLY", "no"),
    }
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(
        [
            "field",
            "block",
            "source",
            "evidence_status",
            "production_grade",
            "recommended_use",
            "description",
            "persona_eligible",
        ]
    )
    for name in FIELDS:
        block, status, grade, use, persona = policy[name]
        writer.writerow([name, block, "fictional", status, grade, use, name, persona])
    return buffer.getvalue().encode("utf-8")


@pytest.fixture
def bundle(tmp_path: Path) -> tuple[PopulationImportContract, FilesystemPopulationSource]:
    """A fictional contract and its three versions, on disk under ``tmp_path``."""
    panels = {label: _gzip_csv(_rows(label[-1])) for label in LABELS}
    dictionary = _dictionary()
    (tmp_path / "panels").mkdir()
    for label, data in panels.items():
        (tmp_path / "panels" / f"{label}.csv.gz").write_bytes(data)
    (tmp_path / "dictionary.csv").write_bytes(dictionary)
    contract = PopulationImportContract(
        contract_id="fictional_population/v1",
        dataset_id="fictional_population",
        field_count=len(FIELDS),
        field_names_sha256=field_names_fingerprint(FIELDS),
        dictionary_sha256=content_sha256(dictionary),
        primary_key="row_id",
        expected_rows=6,
        weight_schemes=(WeightScheme("main", "w_main", expected_total=9.0, tolerance=1e-9),),
        default_weight_role="main",
        known_versions=(
            KnownVersion("f1_BASE", content_sha256(panels["f1_BASE"]), len(panels["f1_BASE"])),
            KnownVersion("f1_1", content_sha256(panels["f1_1"]), len(panels["f1_1"]), "f1_BASE"),
            KnownVersion("f1_4", content_sha256(panels["f1_4"]), len(panels["f1_4"]), "f1_1"),
            KnownVersion("f1_5", content_sha256(panels["f1_5"]), len(panels["f1_5"]), "f1_4"),
        ),
        static_reference_label="f1_1",
        enrichment_fields=(),
    )
    return contract, FilesystemPopulationSource(tmp_path)


class Ops:
    """Runs the command as the tests' operator configuration names."""

    def __init__(self, world: Any, bundle: Any, operators: dict[str, list[str]]) -> None:
        self.sessions: sessionmaker[Session] = world.sessions
        self.contract, self.source = bundle
        self.config = operator_config({OPERATORS_KEY: json.dumps(operators)})

    def __call__(self, *argv: str) -> tuple[int, Any, str]:
        out, err = io.StringIO(), io.StringIO()
        code = run(
            argv,
            sessions=self.sessions,
            config=self.config,
            source=self.source,
            contract=self.contract,
            out=out,
            err=err,
        )
        return code, json.loads(out.getvalue()) if code == 0 else None, err.getvalue()

    def import_all(self, actor: str) -> dict[str, str]:
        ids = {}
        for label in LABELS:
            parent = {"f1_1": "f1_BASE", "f1_4": "f1_1", "f1_5": "f1_4"}.get(label)
            argv = [
                "import",
                "--as",
                actor,
                "--label",
                label,
                "--panel",
                f"panels/{label}.csv.gz",
                "--dictionary",
                "dictionary.csv",
                "--provenance",
                "fictional test bundle",
            ]
            if parent:
                argv += ["--parent", ids[parent]]
            code, result, err = self(*argv)
            assert code == 0, err
            ids[label] = result["version_id"]
        return ids

    def establish(self, actor: str, ids: dict[str, str]) -> None:
        """STATIC on f1_1 (the contract's reference), then LIVE on f1_4."""
        for population, kind, label in (
            ("FIC_STATIC", "STATIC", "f1_1"),
            ("FIC_LIVE", "LIVE", "f1_4"),
        ):
            code, _, err = self(
                "establish", "--as", actor, "--population", population, "--kind", kind,
                "--version", ids[label], "--reason", f"first {kind}",
            )  # fmt: skip
            assert code == 0, err

    def live_version(self, population: str = "FIC_LIVE") -> str | None:
        with self.sessions() as session:
            found = PopulationRegistryRepository(session).population(population)
            return found.current_version_id if found else None


OWNER = "owner@art-chain.io"
LEAD = "lead@art-chain.io"


def test_an_operator_imports_establishes_and_promotes_and_the_history_names_them(
    world: Any, bundle: Any
) -> None:
    ops = Ops(world, bundle, {world.owner_id: list(BOTH)})
    code, empty, _ = ops("status")
    assert code == 0 and empty["versions"] == [] and empty["populations"] == []

    ids = ops.import_all(OWNER)
    ops.establish(OWNER, ids)
    assert ops.live_version() == ids["f1_4"]

    code, promoted, err = ops(
        "promote", "--as", OWNER, "--population", "FIC_LIVE", "--to", ids["f1_5"],
        "--expected", ids["f1_4"], "--reason", "the newer version",
    )  # fmt: skip
    assert code == 0, err
    assert promoted["current_version_id"] == ids["f1_5"]

    code, status, _ = ops("status")
    assert [v["label"] for v in status["versions"]] == list(LABELS)
    assert {v["imported_by"] for v in status["versions"]} == {world.owner_id}
    assert sorted(status["populations"], key=lambda p: p["population_id"]) == [
        {"population_id": "FIC_LIVE", "kind": "LIVE", "current_version_id": ids["f1_5"]},
        {"population_id": "FIC_STATIC", "kind": "STATIC", "current_version_id": ids["f1_1"]},
    ]
    history = sorted(
        (h["population_id"], h["from_version_id"] or "", h["to_version_id"], h["actor_id"])
        for h in status["history"]
    )
    assert history == sorted(
        [
            ("FIC_STATIC", "", ids["f1_1"], world.owner_id),
            ("FIC_LIVE", "", ids["f1_4"], world.owner_id),
            ("FIC_LIVE", ids["f1_4"], ids["f1_5"], world.owner_id),
        ]
    )


def test_nobody_operates_until_the_configuration_names_them(world: Any, bundle: Any) -> None:
    ops = Ops(world, bundle, {})
    code, _, err = ops(
        "import", "--as", OWNER, "--label", "f1_BASE", "--panel", "panels/f1_BASE.csv.gz",
        "--dictionary", "dictionary.csv", "--provenance", "fictional",
    )  # fmt: skip
    assert code == 2 and "not a configured population operator" in err
    code, status, _ = ops("status")
    assert status["versions"] == []


def test_a_person_aia_does_not_know_is_refused_before_anything_is_read(
    world: Any, bundle: Any
) -> None:
    ops = Ops(world, bundle, {world.owner_id: list(BOTH)})
    code, _, err = ops(
        "establish", "--as", "nobody@example.org", "--population", "FIC_LIVE", "--kind", "LIVE",
        "--version", "v", "--reason", "r",
    )  # fmt: skip
    assert code == 2 and "no active AIA user" in err


def test_an_operator_without_the_permission_cannot_move_live(world: Any, bundle: Any) -> None:
    ops = Ops(
        world,
        bundle,
        {world.owner_id: list(BOTH), world.lead_id: ["POPULATION_ESTABLISH"]},
    )
    ids = ops.import_all(OWNER)
    ops.establish(OWNER, ids)
    code, _, err = ops(
        "promote", "--as", LEAD, "--population", "FIC_LIVE", "--to", ids["f1_5"],
        "--expected", ids["f1_4"], "--reason", "not theirs to move",
    )  # fmt: skip
    assert code == 3 and "POPULATION_PROMOTE" in err
    assert ops.live_version() == ids["f1_4"]


def test_a_promotion_naming_a_stale_version_is_refused_and_live_does_not_move(
    world: Any, bundle: Any
) -> None:
    ops = Ops(world, bundle, {world.owner_id: list(BOTH)})
    ids = ops.import_all(OWNER)
    ops.establish(OWNER, ids)
    code, _, err = ops(
        "promote", "--as", OWNER, "--population", "FIC_LIVE", "--to", ids["f1_5"],
        "--expected", ids["f1_1"], "--reason", "a stale view",
    )  # fmt: skip
    assert code == 3 and err.startswith("PromotionConflict")
    assert ops.live_version() == ids["f1_4"]


def test_a_bundle_the_contract_refuses_registers_nothing(world: Any, bundle: Any) -> None:
    ops = Ops(world, bundle, {world.owner_id: list(BOTH)})
    code, _, err = ops(
        "import", "--as", OWNER, "--label", "f1_BASE", "--panel", "panels/f1_4.csv.gz",
        "--dictionary", "dictionary.csv", "--provenance", "the wrong bytes for this label",
    )  # fmt: skip
    assert code == 3 and "ImportRejected" in err
    assert ops("status")[1]["versions"] == []


def test_a_malformed_companion_is_refused_before_the_bundle_is_read(
    world: Any, bundle: Any
) -> None:
    ops = Ops(world, bundle, {world.owner_id: list(BOTH)})
    code, _, err = ops(
        "import", "--as", OWNER, "--label", "f1_BASE", "--panel", "panels/f1_BASE.csv.gz",
        "--dictionary", "dictionary.csv", "--provenance", "p", "--companion", "no-equals",
    )  # fmt: skip
    assert code == 2 and "ASSET_ID=LOCATION" in err


# ------------------------------------------------------------------ the key


def test_an_unset_or_blank_key_names_nobody() -> None:
    assert operator_config({}).operators == {}
    assert operator_config({OPERATORS_KEY: "  "}).operators == {}


def test_the_key_reads_user_ids_and_their_permissions() -> None:
    config = operator_config({OPERATORS_KEY: json.dumps({"u-1": ["POPULATION_PROMOTE"]})})
    assert {k: {p.value for p in v} for k, v in config.operators.items()} == {
        "u-1": {"POPULATION_PROMOTE"}
    }


@pytest.mark.parametrize(
    ("value", "names"),
    [
        ("{not json", "is not JSON"),
        ('["u-1"]', "must be an object"),
        ('{"u-1": "POPULATION_PROMOTE"}', "needs a list"),
        ('{"u-1": ["POPULATION_DELETE"]}', "names POPULATION_DELETE"),
        ('{"": ["POPULATION_PROMOTE"]}', "needs a user id"),
    ],
)
def test_a_key_that_does_not_read_stops_the_command_naming_it(value: str, names: str) -> None:
    with pytest.raises(OperatorConfigError, match=names) as refused:
        operator_config({OPERATORS_KEY: value})
    assert OPERATORS_KEY in str(refused.value)


def test_main_refuses_without_an_asset_root_or_with_a_bad_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv(ASSET_ROOT_KEY, raising=False)
    monkeypatch.delenv(OPERATORS_KEY, raising=False)
    assert main(["status"]) == 2
    assert ASSET_ROOT_KEY in capsys.readouterr().err
    monkeypatch.setenv(OPERATORS_KEY, "{not json")
    assert main(["status"]) == 2
    assert OPERATORS_KEY in capsys.readouterr().err
