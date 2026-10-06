"""Deep Research: research tracks over Client Knowledge and the web, grounded in captured sources.

ADR 0017 and ``.planning/plans/deep-research.md``. The package is the method, and it
is pure:

* :mod:`.contracts` -- subjects, tracks, snapshots, evidence, quarantine and stop
  reasons, the request a run is frozen to;
* :mod:`.workflow` -- the ``deep_research`` step graph (defined, not registered);
* :mod:`.tooling` -- the cost contract for search and fetch;
* :mod:`.legacy` -- the 18.6.6 leakage screen and merge, ported exactly;
* :mod:`.grounding` -- a quote must be in the source it cites;
* :mod:`.sources` -- source classes, tiers and scores from declared tables;
* :mod:`.reputation` -- the reputation register: publishers, names, hosts, tiers (proposed);
* :mod:`.classification` -- a query's data class, inherited and never lowered;
* :mod:`.web` -- what a fetch may reach, on every hop;
* :mod:`.knowledge_access` -- Client Knowledge frozen at enqueue, retrieved by code;
* :mod:`.planning` -- subjects, tracks and their fingerprints, depth, stopping;
* :mod:`.agents` -- the five agents' contracts, prompts and requests;
* :mod:`.merge` -- scoring, dedupe, confirmation and the verifier's verdicts;
* :mod:`.synthesis` -- the brief, and what of it may be published;
* :mod:`.bundle` -- the sealed evidence bundle;
* :mod:`.steps` -- what each step of a run stores, and the gate each refusal names;
* :mod:`.quarantine` -- what leaves the bundle for respondents, design and analysis.
* :mod:`.filters` -- the funnel's Filter stage: exact and near duplicates, language,
  relevance (defined, not wired).
* :mod:`.verifier` -- the agent-directed mode's independent verifier: contract, prompt;
* :mod:`.triangulation` -- publishers, independence after near-duplicate collapse,
  conflicts and resolve-track requests;
* :mod:`.tracing` -- primary or secondary, traced, and the leads to primary sources;
* :mod:`.verification` -- the independent verifier's verdicts decided by code,
  supersession, and the review an agent-directed verify step records.

Pure: stdlib and Pydantic only.
"""
