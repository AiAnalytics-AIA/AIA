"""Common Crawl's URL index: the one statement code writes, the rows it reads, a scan's price.

Pure: no network, no Athena. The rows are fictional.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from aia_core.domain.deep_research.common_crawl import (
    INDEX_COLUMNS,
    MAX_INDEX_ROWS,
    MAX_WARC_RECORD_BYTES,
    AthenaPricing,
    IndexQueryInvalid,
    IndexRowInvalid,
    IndexTable,
    IndexTarget,
    UrlIndexQuery,
    archive_url,
    build_index_sql,
    parse_index_rows,
)

TABLE = IndexTable(database="ccindex", table="ccindex")
CRAWL = "CC-MAIN-2024-10"
FILE = f"crawl-data/{CRAWL}/segments/1700000000000.10/warc/CC-MAIN-20240101-00001.warc.gz"


def _query(**overrides: object) -> UrlIndexQuery:
    values: dict[str, object] = {
        "target": IndexTarget.URL,
        "value": "https://stats.example/zprava/2023",
        "crawls": (CRAWL,),
        "limit": 5,
    }
    values.update(overrides)
    return UrlIndexQuery(**values)  # type: ignore[arg-type]


def test_an_exact_url_query_constrains_its_partitions_and_reads_only_the_index_columns() -> None:
    sql = build_index_sql(_query(), TABLE)
    assert sql == (
        "SELECT " + ", ".join(INDEX_COLUMNS) + "\n"
        'FROM "ccindex"."ccindex"\n'
        "WHERE crawl IN ('CC-MAIN-2024-10')\n"
        "  AND subset = 'warc'\n"
        "  AND url = 'https://stats.example/zprava/2023'\n"
        "  AND fetch_status IN (200)\n"
        "ORDER BY fetch_time DESC\n"
        "LIMIT 5"
    )


def test_a_host_query_with_a_prefix_media_types_and_a_window() -> None:
    sql = build_index_sql(
        _query(
            target=IndexTarget.HOST,
            value="www.stats.example",
            path_prefix="/publikace/",
            mime_types=("text/html",),
            statuses=(200, 301),
            captured_from=date(2023, 1, 1),
            captured_to=date(2023, 12, 31),
            crawls=(CRAWL, "CC-MAIN-2023-50"),
        ),
        TABLE,
    )
    assert "url_host_name = 'www.stats.example'" in sql
    assert "substr(url_path, 1, 11) = '/publikace/'" in sql
    assert "content_mime_type IN ('text/html')" in sql
    assert "fetch_status IN (200, 301)" in sql
    assert "fetch_time >= TIMESTAMP '2023-01-01 00:00:00'" in sql
    assert "fetch_time <= TIMESTAMP '2023-12-31 23:59:59'" in sql
    assert "crawl IN ('CC-MAIN-2024-10', 'CC-MAIN-2023-50')" in sql
    domain = build_index_sql(_query(target=IndexTarget.DOMAIN, value="stats.example"), TABLE)
    assert "url_host_registered_domain = 'stats.example'" in domain


@pytest.mark.parametrize(
    "overrides",
    [
        {"value": "https://stats.example/a' OR '1'='1"},
        {"value": "https://stats.example/a\\b"},
        {"value": "https://stats.example/a b"},
        {"value": "https://stats.example/a#part"},
        {"value": "http://10.0.0.1/a"},
        {"value": "file:///etc/passwd"},
        {"target": IndexTarget.HOST, "value": "stats.example'--"},
        {"target": IndexTarget.HOST, "value": "Stats.Example"},
        {"target": IndexTarget.HOST, "value": "stats.example", "path_prefix": "/a'"},
        {"target": IndexTarget.HOST, "value": "stats.example", "path_prefix": "no-slash"},
        {"path_prefix": "/a"},
        {"crawls": ()},
        {"crawls": ("CC-MAIN-2024-10'",)},
        {"crawls": (CRAWL, CRAWL)},
        {"crawls": tuple(f"CC-MAIN-2024-{n:02d}" for n in range(1, 8))},
        {"limit": 0},
        {"limit": MAX_INDEX_ROWS + 1},
        {"statuses": ()},
        {"statuses": (99,)},
        {"statuses": (True,)},
        {"mime_types": ("text/html'",)},
        {"captured_from": date(2024, 2, 1), "captured_to": date(2024, 1, 1)},
    ],
)
def test_a_value_code_would_not_write_is_refused_before_any_sql(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(IndexQueryInvalid):
        build_index_sql(_query(**overrides), TABLE)


def test_the_table_names_are_plain_identifiers() -> None:
    with pytest.raises(IndexQueryInvalid):
        IndexTable(database="ccindex", table='ccindex" --')
    with pytest.raises(IndexQueryInvalid):
        IndexTable(database="CCIndex", table="ccindex")


def _row(**overrides: str | None) -> list[str | None]:
    values: dict[str, str | None] = {
        "url": "https://stats.example/zprava/2023",
        "fetch_time": "2024-02-21 10:11:12.000",
        "fetch_status": "200",
        "content_mime_type": "text/html",
        "content_digest": "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567",
        "warc_filename": FILE,
        "warc_record_offset": "123456",
        "warc_record_length": "2048",
        "crawl": CRAWL,
    }
    values.update(overrides)
    return [values[c] for c in INDEX_COLUMNS]


def test_rows_are_read_by_column_name_into_typed_captures() -> None:
    columns = list(reversed(INDEX_COLUMNS))
    (row,) = parse_index_rows(columns, [list(reversed(_row()))])
    assert row.url == "https://stats.example/zprava/2023"
    assert row.captured_at == datetime(2024, 2, 21, 10, 11, 12, tzinfo=UTC)
    assert (row.status, row.mime_type, row.crawl) == (200, "text/html", CRAWL)
    assert (row.warc_record_offset, row.warc_record_length) == (123456, 2048)
    assert archive_url(row) == f"https://data.commoncrawl.org/{FILE}"


@pytest.mark.parametrize(
    "overrides",
    [
        {"warc_filename": "crawl-data/CC-MAIN-2024-10/../../secrets.warc.gz"},
        {"warc_filename": "crawl-data/CC-MAIN-2023-50/segments/x/warc/a.warc.gz"},
        {"warc_filename": "https://elsewhere.example/a.warc.gz"},
        {"warc_record_length": "0"},
        {"warc_record_length": str(MAX_WARC_RECORD_BYTES + 1)},
        {"warc_record_offset": "-1"},
        {"fetch_time": "yesterday"},
        {"fetch_status": "OK"},
        {"url": "http://192.168.0.1/admin"},
        {"url": None},
        {"crawl": "latest"},
    ],
)
def test_a_row_of_another_shape_is_refused(overrides: dict[str, str | None]) -> None:
    with pytest.raises(IndexRowInvalid):
        parse_index_rows(INDEX_COLUMNS, [_row(**overrides)])


def test_a_result_missing_a_column_or_of_another_width_is_refused_whole() -> None:
    with pytest.raises(IndexRowInvalid, match="lacks"):
        parse_index_rows(INDEX_COLUMNS[:-1], [_row()[:-1]])
    with pytest.raises(IndexRowInvalid, match="width"):
        parse_index_rows(INDEX_COLUMNS, [_row(), _row()[:-1]])


def test_a_scan_is_billed_from_the_bytes_scanned_with_the_configured_minimum_and_increment() -> (
    None
):
    pricing = AthenaPricing(
        usd_per_tb_scanned=5.0, minimum_billed_bytes=10_000_000, billing_increment_bytes=1_000_000
    )
    assert pricing.billed_bytes(0) == 10_000_000
    assert pricing.billed_bytes(10_000_001) == 11_000_000
    assert pricing.billed_bytes(2_500_000_000) == 2_500_000_000
    assert pricing.cost_usd(2_500_000_000) == pytest.approx(0.0125)
    assert pricing.cost_usd(1) == pytest.approx(0.00005)
    with pytest.raises(ValueError):
        pricing.billed_bytes(-1)


@pytest.mark.parametrize(
    ("price", "minimum", "increment"),
    [(0.0, 0, 1), (float("nan"), 0, 1), (5.0, -1, 1), (5.0, 0, 0)],
)
def test_a_price_is_configured_and_never_zero(price: float, minimum: int, increment: int) -> None:
    with pytest.raises(ValueError):
        AthenaPricing(
            usd_per_tb_scanned=price,
            minimum_billed_bytes=minimum,
            billing_increment_bytes=increment,
        )
