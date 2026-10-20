# ADR 0038 — The MVP's Sociomap method is `aia-sociomap-5`, and the only one: new runs pin it by its own name, it stays internal until the register approves it, the old methods leave every product path, and stored maps are never recomputed

**Status:** Proposed — 2026-10-20, recording the product owner's decision of the same day
(MVPQ-13: "the MVP ships `aia-sociomap-5`", #504, relayed by the coordinator). Not accepted until the
product owner says so; **every method question is the methodology owner's** and lives in the
methodology packet (`.planning/mvp-methodology-packet.md`, #510, MQ-01 to MQ-24), not here. **Builds
on** [ADR 0023](0023-methodology-is-data-the-methodologist-owns.md) (a run pins the methodology in
force; versions are immutable) and the Sociomap register (`domain/sociomap_register.py`; D6 is the
precedent). **Changes** what a new run pins, what Metodika has in force and offers, who may edit
methodology, and what a product path does with a map of an older method. **Leaves unchanged** every
stored run's artifacts and pins (never rewritten, recomputed or deleted), and the old engine and its
golden fixtures as tested reference.
**Date:** 2026-10-20. **Amended 2026-10-20** with the product owner's recorded answers D-13, D-14 and
Q1 to Q4 (`.planning/evidence/scope-freeze/answers-2026-10-20.md`, #523 @ `ee21982`): `-5` the only
method, the old methods out of every product path, the Metodik mark. Still Proposed.
**Plan:** [signed-off-sociomap-method](../../../.planning/plans/signed-off-sociomap-method.md);
packet E-1 to E-9

## Context

`aia-sociomap-5` is the methodology owner's signed-off method, merged as a preset with #504
(`AIA_SOCIOMAP_V5`, `packages/aia_core/src/aia_core/domain/sociomap/specification.py:1553 @ 86ec0cd`).
It differs from `-3` in its pair evidence, its layout (soft-rank Spearman with Coulomb repulsion,
BB1, to 163 objects), its relative heights, and in that it computes a respondent map and taste
segments (packet, MVPQ-13's table). Four facts of the code frame the decision:

- **No run pins `-5` today.** A new run pins `-1` and `-3` (`default_methods`,
  `domain/research_sociomap.py:323-330 @ 86ec0cd`). Metodika has `-3` in force and offers `-5` as a
  preset (`domain/methodology/sociomap.py:2007-2014 @ 86ec0cd`), but putting a preset in force goes
  through a stored version, and a version pins its spec under its own name `<base>+e<n>`
  (`domain/methodology/versions.py:71-75`, `domain/methodology/pins.py:84-95 @ 86ec0cd`).
- **The register matches an exact name and fingerprint**, and refuses any method whose formulas a
  version replaced (`approval_of`, `domain/sociomap_register.py:72-86 @ 86ec0cd`). So an entry for
  `aia-sociomap-5` would approve no run AIA can start (packet E-1).
- **BB1 is not bit-identical across platforms.** Its compiled kernel's last bits differ between
  platforms (`domain/sociomap/layout.py:155-162 @ 86ec0cd`); from 12 objects on, two platforms can give
  different, equally good maps under the same library versions (packet MQ-04).
- **The domain imports numerical libraries for `-5`.** numpy, scipy and numba are pinned to the
  versions its evidence was produced with (`packages/aia_core/pyproject.toml:14-20 @ 86ec0cd`), an
  exception to the domain's stdlib-and-Pydantic rule that `ARCHITECTURE.md` §2 row 1 now records
  (#508; `ARCHITECTURE.md:50 @ 86ec0cd`).

## Decision

### 1. A new run pins `aia-sociomap-5` exactly, by its own name

The code's preset becomes `-5`: with no methodology version in force, `default_methods()` pins
`SociomapMethod.of(AIA_SOCIOMAP_V5)`, under the name `aia-sociomap-5` and its spec fingerprint, so a
register entry for that name and fingerprint matches every run that computed it. Metodika's in force
becomes `aia-sociomap-5`. An **activation of a preset as it stands** (no field and no formula changed)
pins the preset's own name, never `+e<n>`; `+e<n>` is kept for a version that changes something, which
is a different method and needs its own register entry (`sociomap_register.py:8-11`). The run's
identity carries the method's name and fingerprint, as today, so a run started under `-5` and one
started under `-5+e1` never share artifacts.

**`-5` is the only method of a new run** (the product owner, 2026-10-20, D-13: "i would like to
completely refresh and essentially make aia 5 the only version for now i want to get rid of any
functionality of the old ones. maps are drawn according to the current 5"). `default_methods()`
returns `-5` alone; `aia-sociomap-1` is no longer pinned beside it, and no run computes a second
method. Metodika offers `-5` as its one preset. The switch merges when it is built, with the web's
`-5` drawing (packet E-3) in the same wave, so a new run is never left with an old picture (Q1).

**Only the methodologist edits methodology** (D-14: "only the mathematician can edit the
methodology"; Q4). A "Metodik" member mark, granted by an organization OWNER and held by
A. Bahbouh, gates storing and activating a methodology version; `require_administer` alone no longer
suffices (ADR 0023's interim rule). An edited version is `-5+e<n>`, internal until its own entry.

### 2. Internal until the register approves it

`-5` has no register entry, so every `-5` map is `INTERNAL_ONLY` and `require_client_facing` refuses
it by name. Researchers see it, labelled internal. An entry is added only by the methodology owner's
recorded decision at `-5`'s exact spec fingerprint, with its Czech reader note, as D6 approved `-3` on
2026-10-13. What the entry covers (the object map alone, or the respondent map and segments too) is
packet MQ-01. Until it exists, no client deliverable carries a `-5` map, and the report-delivery gates
and AC-09's client snapshots wait for it.

### 3. Older methods leave every product path; stored runs keep what they computed

`aia-sociomap-1` to `-4` are removed from every product path: the default pins, Metodika's presets,
the web's map drawing, the report's map chapters and the snapshot approval (the product owner,
2026-10-20, Q3). The old engine code and its golden fixtures F1-F11 stay, as reference behind
tests, never reached by a product request.

A run stored under an older method keeps its pins and its stored artifacts, byte for byte: nothing
is back-filled, re-labelled, recomputed or deleted. What a person sees of it is its data (results,
aggregates, analysis) with, in place of its map, *"Mapa ze starší metody; spusťte běh znovu"* (Q2).
A retry keeps the original's pins (as `ResearchRuns.retry` does today), so retrying such a run would
recompute an older method; a retry of an older-method run is refused by name and a new run is
started instead. A study that wants maps of an older run's data starts a new run under `-5`.

### 4. The stored map is the record; the production image is the reference

A `-5` map is computed once, by the worker that runs the step, and stored with the run. Every later
reader (Results, the report, a snapshot, the Lead's results context, a retry that reuses the step)
reads the stored map; nothing re-derives it for display or delivery. The worker image is the
reference platform: its numpy, scipy and numba versions, read at run time, are recorded beside the
map as part of its provenance, and the production image's map is the canonical one. A map computed
anywhere else (a laptop, another image) is a check, compared by statuses and decisions, never by
coordinates, and never stored as the run's. Where the report today re-derives the run's map from its
dataset and specification (`verified_map`, `application/report_chapters.py:66 @ 86ec0cd`), for `-5` it
verifies the stored map's hash and recorded inputs instead (packet E-7). Whether a different,
equally good map from another platform matters to the method is MQ-04, the methodology owner's.

### 5. The numerical exception is bounded

The domain may import numpy, scipy and numba for `-5`'s numerical code only, under
`domain/sociomap/`, pinned to the versions above; no I/O either way. The earlier presets stay pure
Python and byte-identical. The worker's read-only containers set `NUMBA_CACHE_DIR` to a writable
path (packet E-6). A version bump of any of the three is a change to the reference platform, made in
its own PR with the parity tests' result stated.

## Alternatives considered

- **Pin `-1` beside `-5` until the web draws `-5`** (the decision list's recommendation). Rejected by
  the owner (D-13): `-5` is the only method.
- **Keep showing a stored older-method map, labelled.** Rejected by the owner (Q2, Q3): the old
  methods leave every product path.
- **Keep `-3` and add `-5`'s respondent and segment maps beside it.** Rejected in the packet: `-5`
  places respondents against its own object positions, so a hybrid would draw people on a map they
  were not placed on.
- **Reach `-5` only through a Metodika version.** The pin would be `aia-sociomap-5+e<n>`, which no
  entry for `-5` approves (E-1).
- **Make the register match a base name for an unchanged version.** It would weaken the rule that an
  entry approves exactly one method at one fingerprint; naming the unchanged preset by its own name
  keeps the rule as it is.
- **Recompute every map on read.** Under BB1, a different platform could print a different picture
  of the same run.

## Consequences

- New runs compute the method the owner chose; until the methodology owner's entry exists, none of
  their maps reaches a client.
- The web, the report and Metodika must learn `-5` (packet E-3 to E-5: no drawing, Stress-1 in the
  map chapter where `-5` has none, a comparison without credibility or segments). Each is a chunk.
- Runtime is unmeasured at large n (E-9).
- Older runs lose their map on screen: a study that needs one runs again under `-5`, at the cost of
  a new fieldwork run unless the run's data is reused (not decided here).
- `ARCHITECTURE.md:508 @ 86ec0cd` still says the domain imports nothing beyond stdlib and Pydantic;
  it disagrees with row 1 and needs the same exception (Doc follow-up).

## What enforces it

- Tests: a new run with no version in force pins `aia-sociomap-5` alone, at its fingerprint;
  `default_methods()` returns one method; a stored `-1` or `-3` run reads its data and shows the
  older-method message in place of its map, with its artifacts unchanged; no product route draws,
  reports or approves a map of an older method; a retry of an older-method run is refused by name;
  storing or activating a methodology version without the Metodik mark is refused; activating the
  `-5` preset unchanged pins the same name and fingerprint; a version that changes one field pins
  `-5+e<n>` and matches no `-5` entry; a `-5` map is refused client-facing with no entry; the report verifies a stored `-5` map
  by hash and never recomputes it; the recorded library versions are present on every `-5` map.
- `make layer_check`: numpy, scipy and numba are imported only under `domain/sociomap/` within the
  domain (a new rule).
- The Sociomap golden fixtures F1–F9 stay byte-identical and keep running, as reference tests of the old engine no product path reaches.

## Unblocks

Packet E-1 and E-2 (the pin and Metodika's in force), then E-3 to E-7; `segment-maps-and-drilldown`
and `sociomap-formula-corrections` re-aimed at `-5` (E-8); gate I-2 internally; AC-09 and AC-13 once
the methodology owner's entry exists.

## Open for Nigel

Answered by the product owner on 2026-10-20 (`answers-2026-10-20.md`, #523 @ `ee21982`), and
written into decisions 1 and 3:

1. ~~Does a new run still pin `-1` beside `-5`?~~ No: `-5` is the only method; maps are drawn from
   `-5` (D-13). The switch merges when built, with the `-5` drawing (Q1).
- Who edits methodology: the Metodik mark (D-14, Q4). What a stored older run shows (Q2) and the old
  code's fate (Q3).

Still open:

1. **Client reports already approved under `-3`.** D6 approved `-3` for client reports on
   2026-10-13, and a delivered client report may carry a `-3` map. Q3 removes `-3` from every product
   path: does an already approved and delivered report stay downloadable as it was approved, or is
   it withdrawn with the method?
2. **Retrying an older-method run.** This ADR refuses it (a retry keeps its pins, so it would
   recompute a removed method) and points to a new run; confirm.
3. **The method questions** (MQ-01 the entry and its scope, MQ-04 the platform, MQ-06 the runtime and
   the rest) are the methodology owner's, in the packet (#510).
