# sociomapa-deterministic

**STATUS: PAUSED.** The core engine is merged and the methodology decision package is
in review. The session is paused until **the worker execution contract lands** or
**the withheld reference archive becomes available**. No new Sociomapping features
will be started to fill the time.

Cloud session. No local-machine dependency. All numbers below were measured here.

## Merged

**PR #13: the deterministic Sociomap core**, merged at `17eac55`, CI green.
`aia_core.domain.sociomap`, engine version `1.1.0`:
- a versioned `SociomapSpec` v2 and a deterministic `SociomapArtifact` v2;
- terrain, normaliser and object metrics moved out of the browser;
- the layout declared, never detected.

Reference fixtures F1–F9 are vendored and run in every CI job:
- **match:** F1, F2, F3, F5, F6, F7 and F9;
- **partial:** F8;
- **refused:** F4, meaning the legacy algorithm is refused rather than claimed.

**No R parity is claimed.**

## Open, awaiting review

**PR #20: the methodology sign-off package** (draft; CI not yet observed).
- `docs/architecture/sociomapa-methodology-decision.md` gives each of the four AIA declarations the reference evidence, the archive gap, the consequence, the real alternatives, legacy comparability, a labelled proposal and an ACCEPT / REPLACE / DEFER field.
- The engine doc's §13 rule separates computable from deliverable.
- A `layer_check` guard keeps `AIA_SOCIOMAP_V1` out of the application, infrastructure, API, worker and web layers. It was shown to fail on a probe import and pass without it.

## The one methodology decision preventing client use

**D6 / OI-16.** The methodology owner must ACCEPT, REPLACE or DEFER the four
declarations in `AIA_SOCIOMAP_V1` (`aia-sociomap-1`, spec fingerprint
`9d4dffea…c211`):

| # | Declaration | Proposal (needs owner approval) |
|---|---|---|
| 1 | dissimilarity `scale_top_minus_rating` | ACCEPT with conditions: label `aia-sociomap-1`, no legacy comparison, re-review when the archive arrives |
| 2 | layout `aia_rowcond_unfolding_v1` | ACCEPT with the same conditions, plus `stress_1` stated on every deliverable; the owner sets the maximum acceptable stress |
| 3 | map frame `max_abs_to_extent`, extent 45 | ACCEPT |
| 4 | missing relation `refuse` | ACCEPT as the default; the reference's 5.5 sentinel only by explicit per-study sign-off |

This blocks client use only. Computation is not blocked.

## External blockers (archive acquisition; reconstruction has stopped)

| Item | Needs |
|---|---|
| **OI-13**: legacy `python_weighted_unfolding` (F4) | `sociomap.py` from `REF-WITHHELD-REFERENCE-ARCHIVE` |
| **OI-14**: `baseObjectLayout66` (F8 positions) | `ui_app.html` from the same archive |
| **OI-15**: `REF-GAP-SOCIO-R-SMACOF` | the archive's R wrapper, plus a host with CRAN access. Cloud sessions install R 4.3.3, but CRAN is blocked there |

## For integration-architecture: cross-context requirement

Recorded as **OI-17** and in `sociomapa-deterministic-engine.md` §13:

1. The engine may compute any explicitly requested, supported `SociomapSpec`.
2. A Sociomap may become a client deliverable, export or client-role view **only
   if its `methodology_version` and `spec_fingerprint` are both approved** in the
   product/methodology policy. The registry and the gate that reads it are yours
   and product policy's. They must not live in the engine, or an artifact's
   numbers would depend on who signed what.
3. No API, worker or UI may silently substitute `AIA_SOCIOMAP_V1` or any other
   spec. A request without a spec is an error.

The gate must land before, or together with, the first path that can emit a
Sociomap to a client. No such path exists today.

## For platform-runtime

Sociomap work resumes on your **worker execution contract**. A 1,000-respondent
map takes about 3.3 s in pure Python, so it is a job, not a request. The first
job should take the spec as an explicit, fingerprinted input and store the
artifact through `ArtifactRepository.put_json`.
