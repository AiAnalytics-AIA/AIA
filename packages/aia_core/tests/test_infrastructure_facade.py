"""The infrastructure package re-exports nothing from ``tables``.

The import contract "the application reaches the tables only through a
repository" (pyproject.toml) sees a direct import edge only. Were the package
to re-export a row, ``from aia_core.infrastructure import StudyRow`` would be
an edge to the package, the contract would stay green, and a use case could
select over the table anyway. Rows are imported from ``infrastructure.tables``
by name, where the contract sees them.
"""

from __future__ import annotations

import aia_core.infrastructure as infrastructure


def test_the_package_re_exports_no_table_object() -> None:
    leaked = sorted(
        name
        for name in dir(infrastructure)
        if getattr(getattr(infrastructure, name), "__module__", None)
        == "aia_core.infrastructure.tables"
    )
    assert leaked == []


def test_every_exported_name_exists_and_is_not_a_table_object() -> None:
    for name in infrastructure.__all__:
        value = getattr(infrastructure, name)
        assert getattr(value, "__module__", None) != "aia_core.infrastructure.tables", name
