"""The run's sample against 18.6.6's own ``draw_representative``, on its fallback path (2e).

``tests/fixtures/representative_draw/expected.json`` is what the unit's unmodified
``representative_sampling.draw_representative`` did on fictional rows with SciPy's MILP made to
fail, so it ran the largest-remainder fallback AIA ports (``tools/sampling_capture.py``).

Parity, as the plan's § 2a states it:

* targets, quota fields and quotas: EXACT, on cases whose winning and losing remainders lie
  further apart than the unit's ``1e-9`` tie-break noise (the fixture records the gap);
* raking and the audit, given the unit's own picks: the audit's rounded figures and the verdict
  EXACT, the raked weights to ``1e-12`` relative (NumPy sums pairwise, AIA with ``math.fsum``);
* the draw: by property, since the unit's stream is NumPy's PCG64 and AIA's ``random.Random``.
"""

from __future__ import annotations

import csv
import hashlib
import io
import itertools
import json
import math
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from aia_core.domain.population.audience import audience_mask, sanitize_filters
from aia_core.domain.population.sampling import (
    QUOTA_FIELDS,
    SAMPLER_VERSION,
    Draw,
    SamplingRefused,
    audit_composition,
    category_keys,
    joint_fields,
    judge,
    quantile,
    quotas,
    rake,
    representative_draw,
    targets,
    tolerances,
    usable_fields,
)

FIXTURES = Path(__file__).parent / "fixtures" / "representative_draw"
UNIT = Path(__file__).resolve().parents[3] / "legacy" / "npc-panel-18.6.6" / "app"
EXPECTED: dict[str, Any] = json.loads((FIXTURES / "expected.json").read_text("utf-8"))
_INPUTS: dict[str, Any] = json.loads((FIXTURES / "cases.json").read_text("utf-8"))
CASES: dict[str, dict[str, Any]] = {c["id"]: c for c in _INPUTS["draws"]}
RAKES: dict[str, dict[str, Any]] = {c["id"]: c for c in _INPUTS["rakes"]}
WEIGHT = "vaha_strukturalni_2025"
#: Remainders closer than this are decided by the unit's 1e-9 noise; none of the cases is.
TIE = 1e-6


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read() -> tuple[tuple[str, ...], dict[str, tuple[str | None, ...]], int]:
    reader = csv.reader(io.StringIO((FIXTURES / "rows.csv").read_text("utf-8")))
    header, *rows = list(reader)
    columns = {
        h: tuple(None if row[i] == "" else row[i] for row in rows) for i, h in enumerate(header)
    }
    return tuple(header), columns, len(rows)


HEADER, COLUMNS, ROWS = _read()


def _audience(filters: dict[str, Any]) -> tuple[int, ...]:
    clean, dropped = sanitize_filters(COLUMNS, filters)
    assert not dropped
    return audience_mask(COLUMNS, clean)


def _keys(audience: Sequence[int]) -> dict[str, tuple[str, ...]]:
    return {f: category_keys(f, [COLUMNS[f][i] for i in audience]) for f in QUOTA_FIELDS}


def _weights(audience: Sequence[int]) -> list[float]:
    return [max(float(COLUMNS[WEIGHT][i] or "nan"), 1e-12) for i in audience]


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-15)


def _drawn(case: dict[str, Any]) -> tuple[dict[str, tuple[str, ...]], list[float]]:
    """The unit's own sample, as AIA holds it: keys and base weights in sample order."""
    keys = {f: category_keys(f, [COLUMNS[f][i] for i in case["picks"]]) for f in QUOTA_FIELDS}
    return {f: keys[f] for f in case["targets"]}, [
        max(float(COLUMNS[WEIGHT][i] or "nan"), 1e-12) for i in case["picks"]
    ]


ALL = sorted(c["id"] for c in EXPECTED["cases"])
QUOTA_CASES = sorted(c["id"] for c in EXPECTED["cases"] if "quotas" in c and "picks" in c)
#: The unit gave a full cell a seat and refused the sample (representative_sampling.py:124, :153).
FULL_CELL_CASES = sorted(
    c["id"] for c in EXPECTED["cases"] if "nemá dost respondentů" in c.get("refused", "")
)
BY_ID = {c["id"]: c for c in EXPECTED["cases"]}
for _case in EXPECTED["cases"]:  # the JSON's keys are sorted; raking's order is the unit's
    if "targets" in _case:
        _case["targets"] = {f: _case["targets"][f] for f in _case["target_fields"]}


def test_the_fixture_is_pinned_to_its_inputs_and_the_unit_sources() -> None:
    assert _sha((FIXTURES / "rows.csv").read_bytes()) == EXPECTED["rows_sha256"]
    assert _sha((FIXTURES / "cases.json").read_bytes()) == EXPECTED["cases_sha256"]
    for name, sha in EXPECTED["unit_sources"].items():
        assert _sha((UNIT / name).read_bytes()) == sha, f"{name} changed; re-capture"


@pytest.mark.parametrize("case_id", ALL)
def test_the_audience_is_the_units(case_id: str) -> None:
    audience = _audience(CASES[case_id]["filters"])
    expected = BY_ID[case_id]
    assert len(audience) == expected["audience_n"]
    assert _sha(",".join(map(str, audience)).encode("ascii")) == expected["audience_sha256"]


@pytest.mark.parametrize("case_id", QUOTA_CASES)
def test_targets_and_quota_fields_are_the_units(case_id: str) -> None:
    expected = BY_ID[case_id]
    audience = _audience(CASES[case_id]["filters"])
    keys, weights = _keys(audience), _weights(audience)
    fields = usable_fields(keys, QUOTA_FIELDS)
    assert list(fields) == list(expected["targets"])
    assert list(joint_fields(fields, CASES[case_id]["n"])) == expected["quota_fields"]
    produced = targets(keys, weights, fields)
    assert {f: list(t) for f, t in produced.items()} == {
        f: list(t) for f, t in expected["targets"].items()
    }  # the same categories, in the unit's sorted order
    for f, shares in expected["targets"].items():
        for category, share in shares.items():
            assert _close(produced[f][category], share), (f, category)


@pytest.mark.parametrize("case_id", QUOTA_CASES)
def test_quotas_are_the_units_largest_remainder(case_id: str) -> None:
    expected = BY_ID[case_id]
    assert expected["remainder_gap"] > TIE, "a near tie: the unit's noise decides, not the rule"
    audience = _audience(CASES[case_id]["filters"])
    keys, weights = _keys(audience), _weights(audience)
    joint = expected["quota_fields"]
    cells = ["¦".join(keys[f][i] for f in joint) for i in range(len(audience))]
    for seed in (0, 1, 2):  # the noise only breaks ties; with none, any seed agrees
        assert (
            quotas(cells, weights, CASES[case_id]["n"], random.Random(seed)) == (expected["quotas"])
        )


@pytest.mark.parametrize("case_id", QUOTA_CASES)
def test_the_units_picks_fill_its_quotas(case_id: str) -> None:
    """A check on the fixture itself: every cell got exactly its quota, no row twice."""
    expected = BY_ID[case_id]
    picks = expected["picks"]
    assert len(set(picks)) == len(picks) == CASES[case_id]["n"]
    keys = {f: category_keys(f, [COLUMNS[f][i] for i in picks]) for f in QUOTA_FIELDS}
    cells = Counter(
        "¦".join(keys[f][i] for f in expected["quota_fields"]) for i in range(len(picks))
    )
    assert {c: k for c, k in expected["quotas"].items() if k} == dict(cells)


@pytest.mark.parametrize("case_id", QUOTA_CASES)
def test_raking_the_units_picks_gives_the_units_weights(case_id: str) -> None:
    expected = BY_ID[case_id]
    keys, base = _drawn(expected)
    assert base == expected["base_weights"]
    raked = rake(keys, expected["targets"], base)
    assert len(raked) == len(expected["analysis_weights"])
    for got, want in zip(raked, expected["analysis_weights"], strict=True):
        assert math.isclose(got, want, rel_tol=1e-12), (got, want)


@pytest.mark.parametrize("case_id", QUOTA_CASES)
def test_the_audit_of_the_units_sample_is_the_units(case_id: str) -> None:
    expected = BY_ID[case_id]
    keys, _ = _drawn(expected)
    raw = audit_composition(keys, expected["targets"])
    weighted = audit_composition(keys, expected["targets"], expected["analysis_weights"])
    assert raw.as_json() == expected["raw"]
    assert weighted.as_json() == expected["weighted"]


@pytest.mark.parametrize("case_id", QUOTA_CASES)
def test_the_verdict_is_the_units(case_id: str) -> None:
    """PASS, PASS_WEIGHTED, or the refusal the unit raised, on the unit's own sample."""
    expected = BY_ID[case_id]
    keys, base = _drawn(expected)
    n = CASES[case_id]["n"]
    raked = tuple(expected["analysis_weights"])
    draw = Draw(
        picks=tuple(range(n)),
        base_weights=tuple(base),
        analysis_weights=raked,
        fields=tuple(expected["targets"]),
        quota_fields=tuple(expected["quota_fields"]),
        quotas=expected["quotas"],
        targets=expected["targets"],
        raw=audit_composition(keys, expected["targets"]),
        weighted=audit_composition(keys, expected["targets"], raked),
    )
    if "refused" in expected:
        with pytest.raises(SamplingRefused) as refused:
            judge(draw, n)
        assert refused.value.reason == "sampling_unrepresentative"
        return
    status, warn = judge(draw, n)
    verdict = expected["verdict"]
    assert status == verdict["status"]
    assert warn == verdict["raw_selection_warning"]
    raw_tol, weighted_tol = tolerances(n)
    assert round(raw_tol, 3) == verdict["raw_tolerance_pp"]
    assert weighted_tol == verdict["weighted_tolerance_pp"]
    ess = math.fsum(raked) ** 2 / math.fsum(w * w for w in raked)
    assert round(ess, 3) == verdict["effective_n"]
    assert round(min(raked), 4) == verdict["weight_min"]
    assert round(max(raked), 4) == verdict["weight_max"]


@pytest.mark.parametrize("case_id", sorted(RAKES))
def test_raking_where_the_cap_binds_is_the_units(case_id: str) -> None:
    """The cap is 8 x the maximum at 20 rows or fewer, 8 x the 99th percentile above."""
    case = RAKES[case_id]
    goal = {f: dict(shares) for f, shares in case["targets"]}
    raked = rake(case["columns"], goal, case["base"])
    expected = {r["id"]: r["weights"] for r in EXPECTED["rakes"]}[case_id]
    for got, want in zip(raked, expected, strict=True):
        assert math.isclose(got, want, rel_tol=1e-12), (got, want)


def test_a_field_with_one_value_and_gaps_is_not_a_quota_field() -> None:
    """``nunique(dropna=True) > 1``: a missing cell is not a second value."""
    from aia_core.domain.population.sampling import MISSING

    assert usable_fields({"pohlavi": ("muž", MISSING, "muž")}, QUOTA_FIELDS) == ()
    assert usable_fields({"pohlavi": ("muž", "žena")}, QUOTA_FIELDS) == ("pohlavi",)


def test_with_no_usable_quota_field_the_weight_is_the_base_over_its_mean() -> None:
    """``representative_sampling.py:136-137``: no quota, no raking."""
    expected = BY_ID["D09_no_quota_field"]
    audience = _audience(CASES["D09_no_quota_field"]["filters"])
    assert usable_fields(_keys(audience), QUOTA_FIELDS) == ()
    base = expected["base_weights"]
    mean = math.fsum(base) / len(base)
    for got, want in zip((b / mean for b in base), expected["analysis_weights"], strict=True):
        assert math.isclose(got, want, rel_tol=1e-12)
    assert expected["verdict"]["status"] == "PASS"


@pytest.mark.parametrize("values", [[1.0], [3.0, 1.0], [5.0, 1.0, 9.0, 2.0], list(range(101))])
def test_quantile_is_numpys_linear(values: list[float]) -> None:
    """Spot values computed with ``numpy.quantile(values, 0.99)`` (numpy 2.x)."""
    expected = {1: 1.0, 2: 2.98, 4: 8.879999999999999, 101: 99.0}[len(values)]
    assert quantile(values, 0.99) == expected


# --------------------------------------------------------------------------- #
# The draw: properties
# --------------------------------------------------------------------------- #


def _draw(case_id: str, seed: int) -> tuple[Draw, tuple[int, ...]]:
    audience = _audience(CASES[case_id]["filters"])
    return (
        representative_draw(
            _keys(audience), _weights(audience), CASES[case_id]["n"], random.Random(seed)
        ),
        audience,
    )


@pytest.mark.parametrize("case_id", QUOTA_CASES)
def test_aias_draw_fills_the_units_quotas_with_distinct_rows(case_id: str) -> None:
    draw, audience = _draw(case_id, 7)
    expected = BY_ID[case_id]
    assert draw.quotas == expected["quotas"]
    assert len(set(draw.picks)) == len(draw.picks) == CASES[case_id]["n"]
    keys = _keys(audience)
    cells = Counter("¦".join(keys[f][p] for f in draw.quota_fields) for p in draw.picks)
    assert {c: k for c, k in draw.quotas.items() if k} == dict(cells)
    assert math.isclose(math.fsum(draw.analysis_weights) / len(draw.picks), 1.0, rel_tol=1e-9)


def test_the_fixture_holds_full_cell_cases() -> None:
    assert FULL_CELL_CASES == ["D15_whole_audience", "D16_near_whole_audience"]


@pytest.mark.parametrize("case_id", FULL_CELL_CASES)
def test_where_the_unit_overfilled_a_cell_aia_keeps_every_quota_within_its_rows(
    case_id: str,
) -> None:
    """The deliberate difference: the unit's noise gave a full cell a seat, and it refused."""
    expected = BY_ID[case_id]
    audience = _audience(CASES[case_id]["filters"])
    keys = _keys(audience)
    rows = Counter(
        "¦".join(keys[f][i] for f in expected["quota_fields"]) for i in range(len(audience))
    )
    assert any(k > rows[c] for c, k in expected["quotas"].items())  # the unit's overfilled cell
    draw, _ = _draw(case_id, 3)
    assert all(k <= rows[c] for c, k in draw.quotas.items())
    assert sum(draw.quotas.values()) == len(set(draw.picks)) == CASES[case_id]["n"]


def test_the_tolerances_are_the_units_boundaries() -> None:
    """``representative_sampling.py:164-167``: refused above the weighted tolerance, a raw
    deviation above its own tolerance only warns."""
    base = BY_ID["D02_n200"]
    keys, _ = _drawn(base)
    raked = tuple(base["analysis_weights"])

    def judged(raw_pp: float, weighted_pp: float) -> tuple[str, bool]:
        raw = audit_composition(keys, base["targets"])
        weighted = audit_composition(keys, base["targets"], raked)
        draw = Draw(
            picks=tuple(range(200)),
            base_weights=raked,
            analysis_weights=raked,
            fields=tuple(base["targets"]),
            quota_fields=tuple(base["quota_fields"]),
            quotas=base["quotas"],
            targets=base["targets"],
            raw=replace(raw, max_abs_pp=raw_pp),
            weighted=replace(weighted, max_abs_pp=weighted_pp),
        )
        return judge(draw, 200)

    assert tolerances(200) == (0.5, 0.5)
    assert judged(0.5, 0.5) == ("PASS", False)
    assert judged(0.501, 0.5) == ("PASS_WEIGHTED", True)
    with pytest.raises(SamplingRefused):
        judged(0.5, 0.501)
    assert tolerances(1000) == (0.5, 0.25)


def test_the_sample_is_shuffled_out_of_its_cells_order() -> None:
    """``representative_sampling.py:158``: cells are drawn in key order, then shuffled."""
    draw, audience = _draw("D02_n200", 3)
    keys = _keys(audience)
    sequence = ["¦".join(keys[f][p] for f in draw.quota_fields) for p in draw.picks]
    runs = 1 + sum(a != b for a, b in itertools.pairwise(sequence))
    assert runs > 2 * len({c for c, k in draw.quotas.items() if k})


def test_the_same_seed_draws_the_same_sample_and_another_seed_does_not() -> None:
    first, _ = _draw("D02_n200", 3)
    again, _ = _draw("D02_n200", 3)
    other, _ = _draw("D02_n200", 4)
    assert first == again
    assert first.picks != other.picks
    assert first.quotas == other.quotas


def test_the_draw_within_a_cell_follows_the_weights() -> None:
    """Successive weighted picks: over many seeds a heavy row is drawn far more often."""
    from aia_core.domain.population.sampling import _weighted_without_replacement

    hits = Counter[int]()
    for seed in range(2000):
        hits.update(
            _weighted_without_replacement([0, 1, 2], [8.0, 1.0, 1.0], 1, random.Random(seed))
        )
    assert hits[0] > 1400 and hits[1] < 300 and hits[2] < 300
    assert sorted(
        _weighted_without_replacement([0, 1, 2], [1e-12, 1e-12, 5.0], 3, random.Random(1))
    ) == [0, 1, 2]


def test_a_zero_weight_row_is_drawn_only_when_its_cell_needs_it() -> None:
    from aia_core.domain.population.sampling import _weighted_without_replacement

    for seed in range(200):
        assert 0 not in _weighted_without_replacement(
            [0, 1, 2], [1e-12, 1.0, 1.0], 2, random.Random(seed)
        )


# --------------------------------------------------------------------------- #
# draw_panel_sample over a population the canonical loader issued
# --------------------------------------------------------------------------- #


class _NoEnrichment:
    enricher_id = "test-no-enrichment/v1"

    def derive(self, panel: Any) -> dict[str, tuple[str | None, ...]]:
        return {}


def _population(session: Session, kit: Any, *, header: Sequence[str] = HEADER) -> Any:
    """``rows.csv`` as a population version, loaded as the ANALYSIS view a run binds."""
    gzip_csv, joint_certificate_json = kit.gzip_csv, kit.joint_certificate_json
    policy_dictionary_csv = kit.policy_dictionary_csv

    from aia_core.application.population import PopulationRuntime
    from aia_core.domain.population import (
        CompanionKind,
        CompanionSpec,
        KnownVersion,
        PopulationImportContract,
        PopulationKind,
        PopulationSelector,
        PopulationView,
        WeightScheme,
        content_sha256,
        field_names_fingerprint,
    )
    from aia_core.infrastructure.population_source import InMemoryPopulationSource

    fields = tuple(header)
    base = [
        dict(zip(HEADER, (COLUMNS[h][i] or "" for h in HEADER), strict=True)) for i in range(ROWS)
    ]
    rows = {
        label: [{**r, "panel_row_id": f"{r['panel_row_id']}-{label}"} for r in base]
        for label in ("v1_BASE", "v1_1", "v1_4")
    }
    panels = {label: gzip_csv(fields, r) for label, r in rows.items()}
    policy = {
        "panel_row_id": ("provenance", "PROVENANCE_OR_CORE", "T", "AUDIT_ONLY", "no"),
        "core_donor_id": ("provenance", "PROVENANCE_OR_CORE", "T", "AUDIT_ONLY", "no"),
        WEIGHT: ("weight", "NEW_WEIGHT", "T", "AUDIT_ONLY", "no"),
    }
    dictionary = policy_dictionary_csv(fields, policy)
    certificate = joint_certificate_json(content_sha256(panels["v1_4"]))
    total = math.fsum(float(c or 0) for c in COLUMNS[WEIGHT])
    contract = PopulationImportContract(
        contract_id="sampling_population/v1",
        dataset_id="sampling_population",
        field_count=len(fields),
        field_names_sha256=field_names_fingerprint(fields),
        dictionary_sha256=content_sha256(dictionary),
        primary_key="panel_row_id",
        expected_rows=ROWS,
        weight_schemes=(
            WeightScheme("default_current", WEIGHT, expected_total=total, tolerance=1e-6),
        ),
        default_weight_role="default_current",
        known_versions=(
            KnownVersion("v1_BASE", content_sha256(panels["v1_BASE"]), len(panels["v1_BASE"])),
            KnownVersion("v1_1", content_sha256(panels["v1_1"]), len(panels["v1_1"]), "v1_BASE"),
            KnownVersion("v1_4", content_sha256(panels["v1_4"]), len(panels["v1_4"]), "v1_1"),
        ),
        static_reference_label="v1_1",
        enrichment_fields=(),
    )
    contract = replace(
        contract,
        companions=(
            CompanionSpec(
                asset_id="CORE_JOINT_STATUS.json",
                kind=CompanionKind.CORE_JOINT_STATUS,
                sha256=content_sha256(certificate),
                byte_size=len(certificate),
                fmt="json",
            ),
        ),
        joint_certified_labels=frozenset({"v1_4"}),
    )
    source = InMemoryPopulationSource({"dictionary.csv": dictionary})
    for label, data in panels.items():
        source.put(f"panels/{label}.csv.gz", data)
        source.put(f"companions/{label}/CORE_JOINT_STATUS.json", certificate)
    rt = PopulationRuntime(session, contract=contract, source=source, enricher=_NoEnrichment())

    def load(label: str) -> Any:
        return rt.import_version(
            label=label,
            panel_location=f"panels/{label}.csv.gz",
            dictionary_location="dictionary.csv",
            provenance="fictional sampling rows",
            imported_by="importer",
            companion_locations={
                "CORE_JOINT_STATUS.json": f"companions/{label}/CORE_JOINT_STATUS.json"
            },
        )

    load("v1_BASE")
    anchor = load("v1_1")
    rt.establish(
        population_id="SAMPLING_STATIC",
        kind=PopulationKind.STATIC,
        version_id=anchor.version_id,
        operator=kit.operator,
        reason="the reproducibility anchor",
    )
    version = load("v1_4")
    rt.establish(
        population_id="SAMPLING_LIVE",
        kind=PopulationKind.LIVE,
        version_id=version.version_id,
        operator=kit.operator,
        reason="the sampler's test population",
    )
    binding = rt.resolve(
        PopulationSelector.population("SAMPLING_LIVE"), view=PopulationView.ANALYSIS
    )
    return rt.load(binding)


def test_a_run_sample_records_its_rows_donors_weights_and_provenance(
    session: Session, population_kit: Any
) -> None:
    from aia_core.domain.population.sampling import draw_panel_sample

    population = _population(session, population_kit)
    sample = draw_panel_sample(population, {"vek": {"min": 60, "max": 89}}, 150, 20)
    audience = _audience({"vek": {"min": 60, "max": 89}})
    assert len(sample.respondents) == 150
    assert [r.order for r in sample.respondents] == list(range(150))
    assert {r.row for r in sample.respondents} <= set(audience)
    assert len({r.row for r in sample.respondents}) == 150
    for r in sample.respondents:
        assert r.donor == COLUMNS["core_donor_id"][r.row]
        assert r.base_weight == max(float(COLUMNS[WEIGHT][r.row] or 0), 1e-12)
    audit = sample.audit
    assert audit.population_n == len(audience) and audit.sample_n == 150
    assert audit.fields == ("pohlavi", "vek_skupina", "kraj", "vzdelani", "zamestnani_status")
    assert audit.quota_fields == ("pohlavi", "vek_skupina", "kraj")
    assert audit.selection_method == "largest_remainder"
    assert audit.status in ("PASS", "PASS_WEIGHTED")
    assert audit.audience_donors == len({COLUMNS["core_donor_id"][i] for i in audience})
    assert audit.sample_donors == len({r.donor for r in sample.respondents})
    record = sample.provenance()
    assert record["sampler_version"] == SAMPLER_VERSION
    assert record["filters"] == {"vek": {"min": 60.0, "max": 89.0}}
    assert record["seed"] == 20
    assert record["version_id"] == population.binding.version_id
    assert record["content_sha256"] == population.binding.content_sha256
    json.dumps(record)  # recordable as it stands
    assert draw_panel_sample(population, {"vek": {"min": 60, "max": 89}}, 150, 20) == sample


@pytest.mark.parametrize(
    ("filters", "n", "reason"),
    [
        ({"vek": "abc"}, 10, "sampling_filter_invalid"),
        ({"vek": {"min": 101, "max": 120}}, 10, "sampling_empty"),
        ({"kraj": "Karlovarský kraj"}, 5000, "sampling_n_exceeds_support"),
        ({}, 0, "sampling_n_invalid"),
        ({}, 20, "sampling_unrepresentative"),
        # The one row this selects has weight 0: the unit would weight it 1.0.
        (
            {
                "pohlavi": "muž",
                "kraj": "Hlavní město Praha",
                "vzdelani": "VOŠ/VŠ",
                "vek": {"min": 70, "max": 70},
            },
            1,
            "sampling_no_weight",
        ),
    ],
)
def test_a_sample_that_cannot_be_drawn_as_asked_is_refused_by_name(
    session: Session, population_kit: Any, filters: dict[str, Any], n: int, reason: str
) -> None:
    from aia_core.domain.population import PopulationError
    from aia_core.domain.population.sampling import draw_panel_sample

    population = _population(session, population_kit)
    with pytest.raises(PopulationError) as refused:
        draw_panel_sample(population, filters, n, 13)
    assert refused.value.reason == reason


def test_a_population_without_a_quota_field_is_refused_not_skipped(
    session: Session, population_kit: Any
) -> None:
    from aia_core.domain.population.sampling import draw_panel_sample

    population = _population(
        session, population_kit, header=tuple(h for h in HEADER if h != "zamestnani_status")
    )
    with pytest.raises(SamplingRefused) as refused:
        draw_panel_sample(population, {}, 50, 1)
    assert refused.value.reason == "sampling_field_unknown"
    assert "zamestnani_status" in str(refused.value)


def test_a_zero_weight_row_keeps_the_units_floor_when_it_is_drawn(
    session: Session, population_kit: Any
) -> None:
    """``pipeline.py:278`` clips the weight at 1e-12: a zero-weight row is drawn last, not never."""
    from aia_core.domain.population.sampling import draw_panel_sample

    population = _population(session, population_kit)
    zero = next(i for i, w in enumerate(COLUMNS[WEIGHT]) if float(w or 0) == 0.0)
    region = COLUMNS["kraj"][zero]
    audience = _audience({"kraj": region})
    sample = draw_panel_sample(population, {"kraj": region}, len(audience), 5)
    drawn = {r.row: r for r in sample.respondents}
    assert set(drawn) == set(audience)  # every row: the audience is the sample
    assert drawn[zero].base_weight == 1e-12
    assert sample.audit.weighted is not None and sample.audit.weighted.max_abs_pp == 0.0


# --------------------------------------------------------------------------- #
# A sample's quota cells, and the support a start would see (run-qc-and-checkpoint RQC6a)
# --------------------------------------------------------------------------- #


#: The cases where the unit drew a sample and AIA's own draw passes too. D11's five respondents
#: are drawn by AIA's generator, not the unit's, and refused as unrepresentative; its quotas are
#: held by test_quotas_are_the_units_largest_remainder.
DRAWN_CASES = [c for c in QUOTA_CASES if "verdict" in BY_ID[c] and c != "D11_n5"]


@pytest.mark.parametrize("case_id", DRAWN_CASES)
def test_a_samples_quota_cells_are_the_units_largest_remainder(
    case_id: str, session: Session, population_kit: Any
) -> None:
    from aia_core.domain.population.sampling import draw_panel_sample

    expected, case = BY_ID[case_id], CASES[case_id]
    population = _population(session, population_kit)
    sample = draw_panel_sample(population, case["filters"], case["n"], case["seed"])
    assert sample.audit.quota_fields == tuple(expected["quota_fields"])
    assert {"¦".join(c.values): c.n for c in sample.quota_cells} == expected["quotas"]
    assert sum(c.n for c in sample.quota_cells) == case["n"]
    # Each cell holds exactly the respondents drawn into it.
    drawn: dict[tuple[str, ...], int] = {}
    for r in sample.respondents:
        cell = tuple(category_keys(f, [COLUMNS[f][r.row]])[0] for f in sample.audit.quota_fields)
        drawn[cell] = drawn.get(cell, 0) + 1
    assert {c.values: c.n for c in sample.quota_cells if c.n} == drawn
    # What a run records is unchanged.
    assert "quota_cells" not in sample.provenance()


def test_a_panel_forecast_reads_the_sample_a_start_would_draw(
    session: Session, population_kit: Any
) -> None:
    from dataclasses import replace as replaced

    from aia_core.domain.evidence import SupportStatus
    from aia_core.domain.evidence.support import AIA_SUPPORT_V1
    from aia_core.domain.fieldwork import PersonaSource
    from aia_core.domain.population.sampling import draw_panel_sample
    from aia_core.domain.research_aggregate import donor_support
    from aia_core.domain.research_design import compile_design
    from aia_core.domain.support_forecast import forecast_support

    spec, problems = compile_design(
        {
            "title": "Fiktivní nápoj",
            "n": 150,
            "sections": [
                {
                    "type": "questions",
                    "questions": [{"id": "q1", "text": "Jak?", "typ": "skala", "skala": [1, 5]}],
                }
            ],
        }
    )
    assert spec is not None, problems
    population = _population(session, population_kit)
    sample = draw_panel_sample(population, {"vek": {"min": 60, "max": 89}}, 150, 20)
    panel = PersonaSource.PANEL
    forecast = forecast_support(spec, support=AIA_SUPPORT_V1, persona_source=panel, sample=sample)
    cell = donor_support(
        [str(r.donor) for r in sample.respondents],
        [r.analysis_weight for r in sample.respondents],
        rule=AIA_SUPPORT_V1.results,
    )
    assert forecast.known and forecast.respondents == 150
    assert forecast.donors == cell["n_unique_layer_donors"] == sample.audit.sample_donors
    assert forecast.results is SupportStatus(str(cell["support_status"]))
    assert forecast.reportable_n is None

    # Unknown, never good: no sample, a sample of another size, a respondent without a donor.
    no_donor = replaced(
        sample,
        respondents=(replaced(sample.respondents[0], donor=None), *sample.respondents[1:]),
    )
    for other in (None, replaced(sample, respondents=sample.respondents[:149]), no_donor):
        missing = forecast_support(spec, support=AIA_SUPPORT_V1, persona_source=panel, sample=other)
        assert not missing.known and missing.results is None and missing.analysis is None
