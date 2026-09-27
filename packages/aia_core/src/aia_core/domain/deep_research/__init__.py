"""Deep Research: research tracks over Client Knowledge and the web, grounded in captured sources.

ADR 0017 and ``.planning/plans/deep-research.md``. The package is the method, and it
is pure:

* :mod:`.contracts` -- subjects, tracks, snapshots, evidence, quarantine and stop
  reasons, the request a run is frozen to;
* :mod:`.workflow` -- the ``deep_research`` step graph (defined, not registered);
* :mod:`.tooling` -- the cost contract for search and fetch.

Pure: stdlib and Pydantic only.
"""
