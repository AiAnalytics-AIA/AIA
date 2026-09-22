"""Where population bytes come from: one protocol, swappable by configuration.

The real panels are licensed-derived research data that must live in EU-resident
object storage (ADR 0008; AIA-reference ``open-decisions.md`` D1/D3). That store is
not chosen yet, and nothing in the loader should care which it is. The loader asks
a :class:`PopulationAssetSource` for the bytes at a registered location and then
verifies them against the registered SHA256 itself -- so a source is trusted to
*deliver* bytes, never to vouch for them.

Implementations here:

* :class:`FilesystemPopulationSource` -- a read-only directory, for an operator's
  local bootstrap and for tests. Locations are relative paths under its root.
* :class:`InMemoryPopulationSource` -- tests.

The EU object-store adapter is the clean seam this protocol exists for: it
implements ``read`` and nothing else changes. It is not written yet because the
bucket, its region and its access model are data-owner decisions.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from aia_core.domain.population import PopulationError

__all__ = [
    "FilesystemPopulationSource",
    "InMemoryPopulationSource",
    "PopulationAssetMissing",
    "PopulationAssetSource",
]


class PopulationAssetMissing(PopulationError):
    """No bytes at the requested location. Never answered with a substitute."""

    reason = "asset_missing"


@runtime_checkable
class PopulationAssetSource(Protocol):
    """Deliver the bytes stored at ``location``, or raise."""

    def read(self, location: str) -> bytes:
        """Return the bytes at ``location``; raise :class:`PopulationAssetMissing`."""
        ...


class InMemoryPopulationSource:
    """A dictionary of location -> bytes."""

    def __init__(self, objects: dict[str, bytes] | None = None) -> None:
        self._objects: dict[str, bytes] = dict(objects or {})

    def put(self, location: str, data: bytes) -> None:
        """Store ``data`` at ``location``, replacing whatever was there.

        Replacement is allowed on purpose: it is how a test simulates a swapped
        file, which the loader must then refuse by hash.
        """
        self._objects[location] = data

    def read(self, location: str) -> bytes:
        try:
            return self._objects[location]
        except KeyError:
            raise PopulationAssetMissing(f"no population asset at {location!r}") from None


class FilesystemPopulationSource:
    """Read-only access to files under one root directory."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()

    def read(self, location: str) -> bytes:
        candidate = (self._root / location).resolve()
        # A location is data from the registry; it may not climb out of the root.
        if not candidate.is_relative_to(self._root):
            raise PopulationAssetMissing(f"{location!r} is outside the population asset root")
        try:
            return candidate.read_bytes()
        except (FileNotFoundError, IsADirectoryError):
            raise PopulationAssetMissing(f"no population asset at {location!r}") from None
