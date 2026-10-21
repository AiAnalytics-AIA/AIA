# Cross-check of the three tracks #507 did not re-map: Evidence, Deep Research, Acceptance

Written 2026-10-20 for the scope freeze, against `develop @ 854c209`. Every code anchor is
`path:line @ 854c209` unless it says otherwise. `core/` = `packages/aia_core/src/aia_core/`,
`api/` = `apps/api/src/aia_api/`, `exec/` = `apps/executors/src/aia_executors/`, `web/` = `apps/web/src/`.

**What this is.** #507 (master plan §6.1 G47-G57) mapped four tracks from the code and compared
them with the plans; it said the Evidence, Deep Research and Acceptance tracks were never
re-mapped. This document does that with the same method:

1. **Map** each track from the code, one anchored line per link.
2. **Compare** the map with every plan: missing, contradicted, unowned, or in the wrong wave.
3. **Refute**: each candidate finding went to a second, independent reader told to disprove it
   against the code and every file under `.planning/`, `docs/architecture/` and `docs/migration/`,
   including G1-G57, I1-I26, §6.2, §11, the five traces and `codex-coordination.md`.

24 candidates reached the refute step (9 Evidence, 6 Deep Research, 9 Acceptance), after the
mappers had already dropped 35 more themselves (§5). None of the 24 was refuted whole; 13 were
narrowed. Three merges (the `-5` findings E1, A1 and A8; the two AC-09 findings E2 and A8; A7 into
A2 and A3) leave **21 findings**, proposed as gap rows G58-G78.

**Limits, stated plainly.** No pytest was run: this container has no venv, and `aia_core` does not
import. Each reproduction is a grep, `tools/master_check.py` or `tools/parity_status.py` (both
stdlib, both run), or a named test that a person with the environment can run. Findings that rest
on reading alone are marked **hypothesis** where they are one (CLAUDE.md §9). What SSM holds on
develop is unknown.

**The owner's decision of 2026-10-20 that the MVP ships `aia-sociomap-5`** (#504), relayed by the
coordinator, was applied to the Evidence and Acceptance tracks: every chunk, row and criterion that
still assumes `-3` is a finding. The decision itself is recorded nowhere in the repository yet
(`mvp-master-plan.md:126` still says "the MVP uses `aia-sociomap-3`").

---

## 1. Track 5: Evidence

### 1.1 Map

**How a number becomes an `AdmittedClaim`**
- Aggregate to evidence rows:
  - The aggregate's origin must equal the dataset's (`core/domain/analysis/native.py:486-490`).
  - The field book is built from the run's instrument only (`:493-500`), with the stored decimals (`:505-508`).
  - Each row is `MODELED` / `AGGREGATE` (`:340-357`, `:364-432`).
- A row is removed, keeping the reason, when:
  - its support is not reportable;
  - the unit's fidelity is REFUSE;
  - it has no estimate, or is off the stored places;
  - an estimate has no interval that contains it.
  (`native.py:322-339`, `_interval` `:286-296`.) This applies on every surface.
- Support: the unit's status, then `assess_support` under the run's pinned rule; the stricter wins, and unknown suppresses (`native.py:254-274`). SUPPRESS is the default (`core/domain/evidence/support.py:6, 172-191, 201-229`). SUPPRESS rows leave the table (`core/domain/evidence/admission.py:150-160`).
- Joint status comes only from the population certificate the run recorded, verified against the panel SHA. With none, nothing is client-facing (`native.py:513-518`).
- `_check_claim` gates, in order (`admission.py:221-295`). Admission is all or nothing (`:298-331`).
  1. Suppressed refs are refused.
  2. Unknown refs are refused.
  3. Client-facing: the origin must be in `CLIENT_ADMISSIBLE_ORIGINS`.
  4. Metric, unit and value must equal the row's.
  5. Client-facing: an estimate needs its interval.
  6. `evaluate_claim`: field policy, then joint structure (`core/domain/evidence/claims.py:186-206`, rules `:120-183`).
- `admit_numeric_claims` has exactly two callers: the analysis draft gate (`core/domain/analysis/draft.py:333`) and the report's question tables (`core/application/report_tables.py:140`).

**Field-policy authority**
- Production numbers are judged only against `instrument_policy_book` (`core/domain/evidence/instrument.py:323-364`), with fields `instrument:<qid>`. Its rules are `claim_rules_for` over AIA's own phrases (`field_policy.py:218-220`; `instrument.py:111-124`):
  - `-1`: `INTERNAL_ONLY` (`:182-187`).
  - `-2`: `MODELED_DISCLOSURE_ALWAYS` + `INTERNAL_ONLY` (`:188-193`). `INTERNAL_ONLY` is lifted only by a current holdout or by the owner's client-report lift (`:231-258`).
- The population contract's list (`RECOMMENDED_USE_POLICY`, `core/domain/population/policy.py:162`, read `:310-311`) is a second derivation. `FieldPolicyBook.from_dictionary_rows` / `from_policy_document` (`field_policy.py:400, 427`) have no non-test caller.
- RELIGION's only non-test mention is an audience field (`core/domain/population/audience.py:184`). Its refusal is tested on the dictionary book (`packages/aia_core/tests/test_evidence_gate_parity.py:493`, `test_evidence_joint_status.py:174`). No production evidence row cites a population field.

**Analysis modules**
- `MAX_REPAIRS = 2` (`core/application/analysis.py:64`). The outcome is COMPLETED or BLOCKED-with-violations (`:105-122, 142-219`).
- The input fingerprint includes the table, book, certificate, prompt template SHA, surface, method status, system fingerprint and `external_context` (`analysis.py:125-140`). `prepare_module` passes no external context (`core/application/analysis_results.py:549-578`; G33).
- The draft gate parses, admits, checks questions, then checks numbers-in-prose coverage (`draft.py:295-346`, `:254-282`). A finding with no `claim_ids` passes (`:116-118`; G32).
- Preflight blocks with 0 calls (`native.py:552-621`) on:
  - a client-facing synthetic or inadmissible origin;
  - `INTERNAL_ONLY`;
  - an uncertified joint status;
  - an empty table;
  - no research question.
- A read re-judges every outcome under today's harness (`analysis_results.py:771-849`). A stale module can be retried over the frozen dataset (`:722-756`).

**Report composition, validation, client report**
- The internal report needs all eight modules complete, over the same table, sources, questions, fingerprint and labels (`core/application/report.py:156-157, 312-343`).
- `core/domain/report/validation.py:182-319` checks:
  - ledger and classification;
  - identifiers;
  - the METHOD callout;
  - that refs are neither suppressed nor unknown;
  - client intervals;
  - audit blocks and internal terms;
  - one stress or fit caption per map;
  - that a client map is `CLIENT_FACING`.

  **Nothing checks a number written in prose against the ledger**: there is no `uncovered_numbers` caller under `domain/report` or `application/report*`.
- `compose_client_report` (`core/application/client_report.py:94-238`):
  - requires `EXPORT_DELIVERABLE`;
  - refuses a non-modelled origin (`:108-113`);
  - judges under `MODELLED_CLIENT_REPORT_LIFT` and the recorded certificate (`:114-123`);
  - draws approved maps only (`:162-164`);
  - prints design, method and appendix (`:207-215`);
  - **reads no analysis module**.
- `approve_report` approves any VALID report artifact of the run (`core/application/report_approval.py:34-36, 43-83`). The route answers `internal_only: True` for every type (`api/routers/research.py:2500-2506`). The wire states are `DRAFT_UNAPPROVED` / `APPROVED_INTERNAL` only (`core/domain/report/review.py:46-50`).
- Downloads serve the draft or the approved version (`research.py:2040-2066, 2395-2449`; G34).

**"Interní dokument" and provenance**
- The mark lives on the source row (`core/domain/material_rules.py:20, 102-105`). The frozen Deep Research `KnowledgeSource` has no mark field and is classed by kind (`core/domain/deep_research/contracts.py:206-225`; `knowledge_access.py:56-59, 76-89`). The report with literature prints "znalosti klienta" sources (`core/application/contextual_report.py:134-143`). No report code reads the mark.
- An evidence row's canonical form carries no origin, population or model (`admission.py:115-140`). The run-level record does exist:
  - the dataset's `respondent_system` (`core/domain/panel_source.py:112-155`);
  - the binding's weight role (`:64-74`);
  - the report's `depends_on` (`exec/report.py:122-160`).

**The Sociomap register and `aia-sociomap-5`**
- The register holds one entry, `aia-sociomap-3` (`core/domain/sociomap_register.py:51-69`). A version with formulas never matches (`:72-86`), and absence means `INTERNAL_ONLY`.
- A new run pins `-1` + `-3` (`core/domain/research_sociomap.py:323-330`). Its docstring still calls `-3` "INTERNAL_ONLY while D6 is open", which is stale since 2026-10-13.
- An organization's version is pinned as `<base>+e<n>` (`core/domain/methodology/pins.py:84-95`, `versions.py:71-75`). The code says of `-5`: "Not pinned by default and not in the register" (`core/domain/sociomap/specification.py:1550-1553`).
- The report reads part of `-5`: credibility and a fit caption with no Stress-1 (`core/application/report_maps.py:68-101, 243-250`). It reads no respondents or segments.
- The figure draws nodes at `heights.values` over a relative terrain (`core/infrastructure/report_docx/object_map_figure.py:39, 64-77, 85-86, 100-104`).

### 1.2 Surviving findings

**E1. The MVP's Sociomap method is outside the master plan, and nothing pins or approves it** (merged with A1, A8 part b; proposed G58)
- *Claim.* A new run pins `-1` + `-3`, and unedited `-5` cannot be pinned. `-5` has no register entry, so any `-5` map (only reachable as `-5+e<n>`) is `INTERNAL_ONLY`. The plan that owns `-5` puts "making `-5` the default" out of its scope, and is not in the master register.
- *Anchors.*
  - Code: `core/domain/research_sociomap.py:323-330`; `core/domain/methodology/pins.py:84-95`; `versions.py:71-75`; `core/domain/sociomap/specification.py:1550-1553`; `core/domain/sociomap_register.py:51-69`.
  - Plans: `.planning/plans/signed-off-sociomap-method.md:41-44, :92` (chunks 0-7 all `[x]`, status `in-progress`); `mvp-master-plan.md:126`.
- *Reproduction.* `python3 tools/master_check.py` → `plan signed-off-sociomap-method (in-progress) is not in §3`. `grep -n 'method_id="' packages/aia_core/src/aia_core/domain/sociomap_register.py` → only `aia-sociomap-3`.
- *Consequence.* The acceptance study's maps come from `-3`, the method the MVP does not ship. A `-5` version activated on Metodika gives a client report with no maps (`client_report.py:197-202`), so AC-13's approved snapshots cannot hold one.
- *Smallest fix.*
  - (a) `default_methods()` pins `-1` + `-5`, and a run that pinned `-3` keeps it.
  - (b) The methodology owner's register entry for `aia-sociomap-5` at its spec fingerprint.
  - (c) The plan is added to master §3.1, and §3.2:126 is corrected.
- *Test.* `test_a_new_run_pins_aia_sociomap_5`: `metadata.sociomap_methods` names `-5`, and a retry of an older run keeps `-3`. `method_status("aia-sociomap-5", AIA_SOCIOMAP_V5.fingerprint())` is `CLIENT_FACING`. A `-5` run's client report has a map chapter.
- *Owner.* New chunk `signed-off-sociomap-method#8` (S2 + the methodology owner).
- *Wave.* W0 for the register row (the check fails today). W1 for the pin and the entry, before E13 freezes method selection.

**E2. AC-09's respondent and segment maps are scheduled on the `-3` route, which `-5` replaces** (merged with A8 part c; G59)
- *Claim.* AC-09 is built by `sociomap-formula-corrections#3` (F10 ideal-point placement, blocked on §11.4 item 12) and by `segment-maps-and-drilldown#2` ("the existing contract-3 engine per segment"). But `-5` already stores a respondent map and taste segments in the same artifact (`core/domain/sociomap/models_v3.py:424-557`, under `respondents` / `respondents.segments`). The "reconcile with #504" notes (`segment-maps-and-drilldown.md:55, :111`; `mvp-cohesion.md:716`; `mvp-master-plan.md:574`) changed no chunk or row. These are still `-3`-shaped:
  - the AC-09 row (`mvp-master-plan.md:156`);
  - E14 (`mvp-execution-contracts.md:37`);
  - segment-maps' "What exists" and chunk 2 (`segment-maps-and-drilldown.md:44-47, 57-59`);
  - E29 (2d, the `-2` preset);
  - E31 (4c, row-conditional unfolding);
  - E30's "carries Stress-1" (a wording problem only: `report_maps.py:243-250` already handles a `-5` map with no Stress-1).
- *Reproduction.* `grep -n "sociomap-formula-corrections#3" .planning/plans/mvp-master-plan.md .planning/mvp-execution-contracts.md` → the AC-09 row and E14.
- *Consequence.* Two respondent maps and two segmentations under different methods. Or W2 waits on an F10 threshold the MVP no longer needs.
- *Smallest fix.* `segment-maps-and-drilldown#0` records the disposition. Respondents and segments are treated differently:
  - **Respondent map.** It is `-5`'s stored `respondents`. `sociomap-formula-corrections#3` becomes POST, or gets a stated reason.
  - **Segments.** Defined segments stay the default (MVP-17, `segment-maps-and-drilldown.md:28`; MVPQ-03, the sampler's descriptors, `mvp-cohesion.md:716`; chunks 1-2). Chunk 2 keeps its scope and computes each defined segment's map under the pinned `-5` method rather than "the existing contract-3 engine". `-5`'s `respondents.segments` (taste clusters) is a candidate for chunk 3's clustering *option*, and the methodology owner decides it under chunk 0. It is never a replacement for the defined segments. (Corrected after review, 2026-10-20: the first version re-scoped chunks 2 and 3 to consume `-5` outright.)
  - **Register and contracts.** The AC-09 row and E14, E29, E30 and E31 are rewritten.
- *Test.* An AC-09 acceptance case asserts three things:
  - the map artifact's `respondents.status == "computed"` under the pinned `-5` method;
  - each defined segment's map is computed from the sampler's descriptors;
  - any clustered segments are labelled "found by clustering".
- *Owner.* `segment-maps-and-drilldown#0`, plus the master §3.4 AC-09 row.
- *Wave.* W1 (E13), before any W2 numerical work.

**E3. The report's map figure misdraws a `-5` map, and no chunk owns the fix** (G60)
- *Claim.* For a `-5` map, the DOCX figure is wrong in three ways:
  - Nodes and surface are on different scales. The terrain is built from relative heights (`object_map_figure.py:39`; `core/domain/sociomap/engine_v2.py:374-395`, `framed_relative_envelope`), but the nodes are placed at `heights.values` on a 0-1 axis (`object_map_figure.py:64-77, 85-86`).
  - The caption "Mezery: bez povrchu" is fixed (`:100-104`).
  - `objects_not_placed` are dropped silently.

  `-5`'s own plan records this only as a "Web follow-up" (`signed-off-sociomap-method.md:131-146`). `segment-maps-and-drilldown#9` and `report-delivery#RD4` do not name it.
- *Reproduction.* **Hypothesis** for the visual effect: rendering needs scipy. The scale mismatch is read directly from `:39` against `:64-77`.
- *Consequence.* An approved map snapshot in either report misdraws the signed-off method and leaves out objects without saying so.
- *Smallest fix.* Under `framed_relative_envelope`, draw nodes at `heights.relative`, take the caption from the terrain method, and list `objects_not_placed`.
- *Test.* In `test_report_map_snapshots.py`, for a `-5` artifact:
  - node z equals `heights.relative`;
  - no "Mezery" caption;
  - a not-placed object is named.
- *Owner.* New chunk `signed-off-sociomap-method#9`. The respondent and segment views stay with `segment-maps-and-drilldown#9`, which must name `-5`'s fields.
- *Wave.* W2, before E15 (`report-delivery#RD4`).

**E4. AC-08's "one field-policy authority" and "RELIGION refused" are missing from AC-08's row, and chunk 5's test cannot hold** (narrowed; G61)
- *Claim.* The §3.4 AC-08 row (`mvp-master-plan.md:155`) maps neither `evidence-integrity#5` (one authority) nor `segment-maps-and-drilldown#10`, which carries the RELIGION test (`segment-maps-and-drilldown.md:113`). Chunk 5's test is "every field admitted client-facing is allowed by `RECOMMENDED_USE_POLICY`" (`evidence-integrity.md:70-72`). It cannot pass for any production claim: every one is an `instrument:<qid>` field under AIA's own phrases, and `policy.py:310-311` reports those as "not a known phrase". Trace-3 found the second half, and no G or §6.2 row carries it.
- *Reproduction.* `grep -n "evidence-integrity#5\|segment-maps-and-drilldown#10" .planning/plans/mvp-master-plan.md` → no hit on line 155.
- *Consequence.* AC-08 could be ticked with no authority work. Or chunk 5 fails against the client report's own numbers.
- *Smallest fix.* Restate chunk 5 as "one authority per evidence source": the instrument policy for study items, the population list for population fields cited by segment claims. Then add `evidence-integrity#5` and `segment-maps-and-drilldown#10` to AC-08's row.
- *Test.* A SEGMENT claim over a RELIGION field is refused client-facing through the production book. Every client-report claim resolves through exactly one declared authority.
- *Owner.* `evidence-integrity#5`.
- *Wave.* W0 for the restatement. The test lands with `segment-maps-and-drilldown#10` (W2).

**E5. `evidence-integrity#1` is W0 in two documents and W3 in the execution contracts, after its own consumer** (G62)
- *Claim.* Three placements disagree:
  - "Chunks 1 and 5 are W0" (`evidence-integrity.md:108`), and the development plan's W0 agrees (`mvp-development-plan.md:147`).
  - E20, which holds `evidence-integrity#1`, is **W3** and needs E32 (`mvp-execution-contracts.md:43`).
  - E32, which holds `evidence-integrity#9a` (the "no supported finding" diagnostic), is **W1** (`:54`).

  So 9a's meaning of "supported" is built before the rule that defines it. `master_check.py` does not detect a chunk in a later wave than its consumer.
- *Reproduction.* `grep -n "evidence-integrity#1\`\|evidence-integrity#9a" .planning/mvp-execution-contracts.md`.
- *Consequence.* I-1's "empty-module diagnostic stored" can pass while counting a finding with no `claim_ids` as supported.
- *Smallest fix.* Move `evidence-integrity#1` from E20 into E32, or into a W0 row. Keep 9b in E20.
- *Test.* A `master_check.py` rule: no chunk in two predecessor rows, and none later than a row that needs it.
- *Owner.* `mvp-execution-contracts.md`, through the coordinator's freeze PR. The tooling rule goes to `mvp-master-plan#MP8`.
- *Wave.* W0.

**E6. RD0's "no number without an admitted claim" never says which numbers are results** (G63)
- *Claim.* Report validation has no check of numbers in prose (`validation.py:69-91, 182-319`). The client report's fixed text carries numbers that are design or method facts, and RD0 (`report-delivery.md:32-33`) exempts none of them:
  - "vždy s 95% intervalem" (`client_report.py:194`);
  - "Návrh počítal s {n} respondenty" (`core/application/report_design.py:141`);
  - the scale ends (`:122-124`);
  - the filter bounds (`:62-68`).

  No plan or decision defines the classes, including MVPQ-09 (`mvp-owner-decisions.md:188-196`).
- *Reproduction.* `grep -rn "uncovered_numbers" packages/aia_core/src/aia_core/domain/report packages/aia_core/src/aia_core/application/report*.py packages/aia_core/src/aia_core/application/client_report.py` → no hit.
- *Consequence.* A literal gate refuses every client report. A loose one ("refs resolve") is what validation already does, and it misses an invented number in a template or in RD6's wording.
- *Smallest fix.* RD0 defines result numbers, which must be ledger refs, and design or method facts, which are typed blocks fed from the specification and exempt. The validator runs `uncovered_numbers` over every other prose run.
- *Test.* "62 % preferuje službu A" without a ref is refused by name, and the composed library-study client report passes.
- *Owner.* `report-delivery#RD0`.
- *Wave.* W2.

**E7. The "Interní dokument" gate has nothing to read** (G64)
- *Claim.* The mark cannot reach either report:
  - AC-13 applies the gate to both reports (`docs/migration/mvp-acceptance.md:88`), but RD0's test covers only the client report, which cites no source (`client_report.py:206-214`).
  - The report with literature prints client-knowledge sources (`contextual_report.py:134-143`).
  - The frozen `KnowledgeSource` has no mark and is classed by kind, so a DOCUMENT is Class A (`contracts.py:206-225`; `knowledge_access.py:56-59, 76-89`), while a marked source is C by rule (`material_rules.py:102-105`).
  - No report code reads the mark.
- *Reproduction.* `grep -rn -i "internal_mark\|marked_internal" packages/aia_core/src/aia_core/application/report*.py packages/aia_core/src/aia_core/application/contextual_report.py packages/aia_core/src/aia_core/domain/deep_research/` → no hit.
- *Consequence.* The gate passes vacuously on the client report. A knowledge item resting on a source the client team marked internal can be printed in an approved report with literature.
- *Smallest fix.* Freeze the mark at enqueue: `source_internal` on `KnowledgeSource`, which is a bundle-contract change and needs ADR 0021's defect note. RD0 then checks both deliverables, and AC-13 says which reports it means.
- *Test.* An Interpretation run whose accepted finding cites a marked source: the deliverable is refused by name, and an unmark after enqueue does not change the frozen answer.
- *Owner.* `report-delivery#RD0`, plus `client-knowledge-lifecycle#K8` for the freeze.
- *Wave.* W1 for the freeze (E09). W2 for RD0.

**E8. AC-15's per-number provenance trace has no chunk** (narrowed; G65)
- *Claim.* AC-15's first clause is that every number traces to fingerprints, provider, model, prompt version, population version, weight identity and data contract. The §3.4 row (`mvp-master-plan.md:162`) lists spend chunks only. The data is spread across `respondent_system`, the binding, the module records and `depends_on`, but no chunk defines or tests the walk from a printed ref to them. `mvp-acceptance-harness#5` would wire AC-15 generically, without the walk.
- *Reproduction.* `grep -n "provenance" .planning/plans/develop-spend-attribution.md .planning/plans/mvp-acceptance-harness.md .planning/plans/report-delivery.md` → nothing about per-number provenance.
- *Consequence.* AC-15 cannot be observed to pass. Or it is passed on spend alone.
- *Smallest fix.* A harness provenance reader: for one report, every ledger ref resolves through `depends_on` to the model binding, prompt pin, population version and weight role. Add it to the AC-15 row.
- *Test.* For each `cited_refs(document)` of both reports, the walk returns non-null fields; any null fails the criterion.
- *Owner.* New chunk `mvp-acceptance-harness#16`.
- *Wave.* W3, after `system-prompts-settings#7`.

**E9. Approving a client report is answered on the wire as an internal approval** (narrowed to the API; G66)
- *Claim.* The approve route returns `internal_only: true` for every artifact type (`api/routers/research.py:2500-2506`), while `report_approval.py:35` admits the client type. There is one vocabulary, `DRAFT_UNAPPROVED` / `APPROVED_INTERNAL` (`review.py:46-50`), and `web/lib/api.ts:1119, 1163, 1176, 1308` type `internal_only: true` as a literal. The web card itself already says "Schváleno k předání klientovi" (`CompleteReport.tsx:306-310, 438`; `cs.ts:2757-2758, 2866`), so the UI half is refuted. Trace-3 found this; G34 and RD2/RD3 do not carry it.
- *Reproduction.* `grep -n '"internal_only": True' apps/api/src/aia_api/routers/research.py`.
- *Consequence.* Any reader other than that card cannot tell a client release from an internal approval: RD2's ledger reader, project memory's labels, the Lead's context.
- *Smallest fix.* The approve response and the review state carry the report's kind. `internal_only` is false for `research_client_docx`.
- *Test.* An API test: approving a client report returns `internal_only: false` and a client review state.
- *Owner.* `report-delivery#RD3`; RD2's reader states the kind.
- *Wave.* W2.

---

## 2. Track 6: Deep Research

### 2.1 Map

**Routes and composition**
- Switches: `AIA_DEEP_RESEARCH_ENABLED`, `_FAN_OUT`, `_CONNECTORS`, `_WEB_SEARCH`, `_COMMON_CRAWL` (`exec/deep_research_runtime.py:185-199`). `WEB_SEARCH` is strictly `off|wikipedia|brave` (`:318-330`).
- Dependencies between switches:
  - `AIA_DEEP_RESEARCH_LEAD` needs `AIA_DEEP_RESEARCH_AGENT_DIRECTED`, or the worker refuses to start (`:459-461`).
  - Connectors need the public-fetch contact (`:455-458`).
- Routes (`exec/deep_research_live.py`):

  | Route | Anchor | Notes |
  |---|---|---|
  | Wikipedia | `:142` | |
  | Public fetch | `:161` | |
  | Brave | `:201` | NON_EU (`:224`) |
  | Common Crawl index and archive | `:255` | Athena NON_EU (`:279`) |
  | Connectors | `:312-357` | route `connector-<name>` (`:393`) |
  | Procurement | `:364-366, 384-385` | unavailable, and naming it stops the worker |

  Each free route is approved for Class C only (`:104-116`).
- The composed routes go into the plan artifact's `web_retrieval` identity (`exec/deep_research/runtime.py:177-194`, written at `exec/deep_research/plan.py:334`). Priced routes are listed by `sign_off_routes` (`runtime.py:196-205`).
- Compose: every Deep Research key is off or empty for both the API and the worker (`deploy/develop/docker-compose.yml:167-181, 263-290`).

**Ladder** (agent-directed mode only)
- Ladders run for an investigator's leads (`exec/deep_research/agent_directed.py:461-528`).
- A connector is reached only when a lead names a dataset (`core/domain/deep_research/acquisition.py:374`).
- The archive is rung 9 alone, under a permit (`acquisition.py:26-27, 128`), given only for a dead, moved or changed page (`core/domain/deep_research/archive.py:159-188`).

**Classification and posture**
- The plan step classifies the whole design from the operator's exact-bytes record (`plan.py:163-174`). With no record, it returns `Failed(RUNTIME_UNAVAILABLE, egress_unclassified_material)`.
- Web tracks are gated by the design's class (`plan.py:262-268`; `core/application/web_retrieval.py:618`). Queries are classified at `web_retrieval.py:788, 882, 1177, 1275, 1365`.
- `clients.data_posture` does not exist yet (G37, chunk 53).

**ADR 0022**
- The settings are pinned in run metadata and the plan input at enqueue (`core/application/deep_research.py:617-619, 658-690`), with the test-policy receipt (`:620, :659`).
- Enqueue refuses `LiveNotApproved` when the API's prices name a paid route (`:624-631`). The worker re-checks the pin and returns `Failed(RUNTIME_UNAVAILABLE, live_settings_unapproved)` (`plan.py:123-137`).
- The test-policy path covers fictional clients only, up to USD 20 (`core/infrastructure/deep_research_settings_repository.py:238-244, 437-467`). Organization approvals apply to any client (`:622-698`).

**What a refusal does**
- `RUNTIME_UNAVAILABLE` parks the step as `WAITING_PROVIDER` / `ai_runtime_unavailable`, with no attempt consumed (`core/domain/workflow.py:601-607`).
- Nothing resumes it on a timer (`:790-798`).
- A waiting run is not retryable (`core/domain/research.py:56-65`).

**Retry**
- A Design Research retry freezes afresh and re-pins (`application/deep_research.py:705-773`).
- An Interpretation retry re-freezes the stored target and requires the same lineage (`:735-761`).

**Budget**
- `cost_ceiling` is computed only with a spend limit (`application/deep_research.py:250-272, 632-651`), at the API's env prices (`api/routers/deep_research.py:292-338`).
- A tool call is held as `payee=tool:<route_id>` (`core/infrastructure/workflow_repository.py:1184-1206`) and settled into `attempt.actual_cost_usd` (`:1332-1370`).
- The per-call journal (`ToolUsageEvent` with `route_id`, `core/domain/deep_research/tooling.py:150-175`) is stored as run events, not as `ai_usage_events` (I20).

**Two purposes**
- Design Research:
  - Subjects are research questions, tracked objects and ENTITY knowledge (`core/domain/deep_research/planning.py:226-281`); `SubjectKind` is QUESTION, OBJECT or CROSS (`contracts.py:138-144`).
  - One EVIDENCE or GAP item per subject (`design_proposals.py:155-171`); an accept writes `design_research` only.
- Interpretation Research: `freeze_interpretation` and `start_interpretation` (`application/deep_research.py:382, 538`). Both purposes pass the mission check at the one enqueue (`:606`).

**Findings out**
- Into the report: only the report with literature, from an Interpretation run (`core/application/contextual_report.py:985`).
- Into knowledge: "Ověřeno, přidat zdroj" through `add_source_once`, or a proposal where self-approval is off (`core/application/verified_sources.py:47-127`).
- The run's sources as a dataset: not built (chunks 33-37, open; chunk 36's inventories are marked by the lead, `deep-research-web-search.md:975, 984`).

**How a run names its routes**
- The composed routes are in the plan artifact only.
- The used routes are in raw event payloads only (`GET …/events`, `api/routers/deep_research.py:678-702`).
- `GET …/runs/{id}` (`:218-242`) and `DeepResearchProvenance` (`core/domain/deep_research/integration.py:431-448`) carry no route.
- Coverage groups by `ToolKind` and drops `route_id` (`core/domain/deep_research/coverage.py:42-56, 102-125`).

### 2.2 Surviving findings

**D1. No response names the routes a run used** (G67)
- *Claim.* Chunk 51's test, I-R and AC-11 all require the run's record to name each route used:
  - chunk 51: "`GET …/deep-research/runs/{id}` names each route it used" (`deep-research-web-search.md:1645-1646`);
  - I-R: `mvp-development-plan.md:162-164`;
  - AC-11: `mvp-acceptance.md:92`.

  The run response and provenance carry none, and coverage drops `route_id`. The routes are recorded only in raw `/events` payloads and in the plan artifact, which is not a reader-shaped record. Reused tracks' calls sit in another run's journal (`coverage.py:14-16`). Chunk 47 (coverage, `[x]`) is by tool kind only; LO12b and chunk 52 cover the deployment's composition, not a run's.
- *Reproduction.* `grep -n "route" apps/api/src/aia_api/routers/deep_research.py | sed -n '/class DeepResearchRun/,/actual_cost/p'` → no route field. `grep -rn route_id apps/web/src` → nothing.
- *Consequence.* The I-R record cannot say which connector was probed live, or whether search was Brave or Wikipedia, without parsing event payloads.
- *Smallest fix.* A `by_route` breakdown in `CoverageLedger` (route id → sent, succeeded, refused), plus `composed_routes` read from the plan artifact. A reused track counts under its original run.
- *Test.* A recorded run through `public-web-fetch`, one connector and the Wayback lookup: `GET …/coverage` lists exactly those route ids, with counts.
- *Owner.* New chunk `deep-research-web-search#51a`. It cannot be 51 itself, which is an activation chunk in E05.
- *Wave.* W1 (E12).

**D2. A run refused for class or approval parks, with a Resume that only parks it again** (narrowed; G68)
- *Claim.* Both refusals park the run, and the plans disagree on what should happen:
  - `egress_unclassified_material` (`plan.py:166-174`) and `live_settings_unapproved` (`:127-137`) are both returned as `RUNTIME_UNAVAILABLE`, which parks as `WAITING_PROVIDER` / `ai_runtime_unavailable` (`workflow.py:601-607`).
  - The run-level park panel offers "Pokračovat v běhu" (`web/components/rehome/research/DeepResearchWaits.tsx:26-41`; `cs.ts:2721-2723`). It can only park again, because the pin is frozen at enqueue, and a waiting run cannot be retried.
  - Chunk 53 says "fails whole" (`deep-research-web-search.md:1679-1681`), and its own test two lines later says "still parks" (`:1683-1684`). AC-11 says "refused whole"; I-R and `mvp-cohesion.md:66` say "parks".
- *Narrowed.*
  - The step shows the real cause: the API carries `error.message` (`routers/deep_research.py:501-503`) and the web shows it first (`web/lib/research-execution.ts:135`).
  - `live_settings_unapproved` reaches the worker only when enqueue's check is skipped: no prices, or an API/worker mismatch. The frequent case is the classification refusal.
  - Trace 5 B2 saw the contradiction but read the code as failing (`trace-5-deepresearch-data-infra.md:68-69, 267`). No G row carries it.
  - **Hypothesis**: a new start after an approval may return the same parked run, because the idempotency key is the spec fingerprint (`application/deep_research.py:621-625`).
- *Reproduction.* `pytest apps/executors/tests/test_deep_research_journey.py -k priced_live_route` (not run here): the plan step ends `WAITING_PROVIDER` / `ai_runtime_unavailable`, not `FAILED`.
- *Consequence.* AC-11's negative case ("refused whole") cannot be asserted as written. A researcher is offered a Resume that silently re-parks, and the run stays non-terminal until cancelled.
- *Smallest fix.* Choose one behaviour:
  - a terminal failure class, so the run is `FAILED` and retryable under fresh pins; or
  - a distinct `waiting_reason` that `resume_runtime_parks` does not match, worded by its cause.

  Then settle chunk 53 and AC-11 on it.
- *Test.* Two journeys, one with no classification and one with an unapproved pin. Each run is `FAILED`, or waits with a reason other than `ai_runtime_unavailable`. `POST …/resume` is refused, and after approval a start or retry runs.
- *Owner.* `deep-research-web-search#53`. The words go to `lead-orchestration#LO12a`.
- *Wave.* W1 (E12).

**D3. From W1 to W4, Deep Research has either no way in or a manual start AC-02 forbids** (narrowed; G69)
- *Claim.* `research-lead-workbench#26` removes "the manual AI starts … in every layout" in W1 (`research-lead-workbench.md:30`; E26, `mvp-execution-contracts.md:49`). D15 requires each removal to come "with the Lead able to call that stage's worker" (`:121-129`). The Lead's Deep Research cards are #23, in W4 (`:27`; E22). No LO chunk defines a Deep Research plan step or chat start: `lead-orchestration.md` names Deep Research only as an envelope charge and in LO4's remark. Yet I22 (`mvp-master-plan.md:222`) presumes one, and I-R (W1), E27 (W2) and E28 (W3) need runs.
- *Narrowed.* LO2 keeps a Run-stage button (`lead-orchestration.md:47-48`). The plans never say whether the Deep Research start buttons count as manual AI starts; that ambiguity is the defect.
  - Corrected anchors: Design Research start `web/components/rehome/research/DeepResearchPanel.tsx:91, 97` (`:108`, `:113` are retry); Interpretation start `InterpretationResearch.tsx:103, 108`.
- *Reproduction.* `grep -n -i "deep research" .planning/plans/lead-orchestration.md` → no start defined.
- *Consequence.* Either AC-02 is broken in W1-W3, or the Deep Research evidence those waves need (I-R, evaluations 25, 26, 39) comes from direct API calls that no journey covers.
- *Smallest fix.* Either a new `lead-orchestration#LO5a` (Deep Research starts as a plan-step kind and a typed chat start, using chunk 55's ceiling), or #26 states the two Deep Research starts survive as a labelled exception until #23.
- *Test.* At 1440 and 390 px after #26, Deep Research is startable through the Lead or through a button marked as the recorded exception. Not both, not neither.
- *Owner.* `research-lead-workbench#26` amended, or new `lead-orchestration#LO5a`.
- *Wave.* W1 (E26 with E12).

**D4. The archive route that I-R and AC-11 require is reached only by chance** (G70)
- *Claim.* The archive is required: I-R is BLOCKED without it (`mvp-execution-contracts.md:35, 154`; `mvp-master-plan.md:460`; `mvp-owner-decisions.md:147`). But it is asked only for a dead, moved or changed page, at rung 9, in agent-directed mode (`archive.py:159-188`; `acquisition.py:26-28, 128`). The plan says the same ("for a dead or moved page only", `deep-research-web-search.md:354, 638-640`). No plan makes the acceptance run meet such a page. Chunk 54's probe sits outside a run, which I-R's wording ("named in the run's record") does not accept.
- *Reproduction.* **Hypothesis** for the live case. The rule itself: `decide_archive_use` refuses `live_has_quote`.
- *Consequence.* Tier B passes or blocks I-R depending on whether some cited page happened to change, and re-running to get archive evidence spends the USD 25 allocation.
- *Smallest fix.* Either an acceptance subject whose cited primary source is a known dead URL, or a recorded archive probe that I-R is reworded to accept.
- *Test.* A harness check that the archive evidence cites a probe record, or a run whose journal shows `archive_lookup` / `archive_fetch` dispatched.
- *Owner.* `deep-research-web-search#54` and `mvp-acceptance-harness#11`.
- *Wave.* W0 (E05) for the probe; W5 (E25) for the record.

**D5. AC-11's dataset clause is missing from its register row and needs a switch no MVP document names** (narrowed; G71)
- *Claim.* "The run's sources are kept as a dataset" is built by chunks 33-37, which are scheduled (E27, `mvp-execution-contracts.md:50`), but the §3.4 AC-11 row (`mvp-master-plan.md:158`) lists none of them. Chunk 36's inventories are marked by the lead (`deep-research-web-search.md:975`). The lead exists only with `AIA_DEEP_RESEARCH_LEAD=true` plus agent-directed mode (`deep_research_runtime.py:444, 459-461, 539-540, 553`), which defaults to false (`docker-compose.yml:103, 181, 267`). §4 names agent-directed mode only (`mvp-master-plan.md:178-180`). Trace 5 §6 (`:166`) marked the clause PARTIAL; the switch and the row omission are new.
- *Reproduction.* `grep -rn "DEEP_RESEARCH_LEAD" .planning/mvp-*.md .planning/plans/mvp-*.md` → nothing.
- *Consequence.* An activation done by the matrix (agent-directed on, the lead off) never produces the dataset, so AC-11 fails at tier B for a reason no row names.
- *Smallest fix.* An activation row for `aia_deep_research_lead` (needs agent-directed mode; evidence: the plan records `versions.lead`), and `deep-research-web-search#36`, `#37` added to the AC-11 row. Or chunk 36 allows marking without the lead.
- *Test.* The MP6 smoke reports the lead row READY or NOT_READY.
- *Owner.* `mvp-master-plan#MP6` and the §3.4 row.
- *Wave.* W0 (MP6); the dataset itself is W2 (E27).

**D6. AOC2 names no producer for an assumption's Deep Research findings** (narrowed; G72)
- *Claim.* AOC2 lets "a Design Research proposal … add the attachment" (`assumptions-and-open-answer-coding.md:6, 42-43`). But a subject is only QUESTION, OBJECT or CROSS (`contracts.py:138-144`; `planning.py:226-281`), with one proposal item per subject (`design_proposals.py:155-171`). AOC2 says neither where an assumption's findings come from nor whether the frozen engine changes (ADR 0021 decision 7). G44 and E33 do not specify the producer.
- *Narrowed.* No engine change is needed. AOC1 links each assumption to a research question, and a QUESTION subject records its `research_questions[i]` origin (`ProposalItem.subject_origin`, `design_proposals.py:169`), so an assumption can inherit its linked question's findings.
- *Reproduction.* `grep -rn -i "assumption" packages/aia_core/src/aia_core/domain/deep_research/planning.py packages/aia_core/src/aia_core/domain/deep_research/contracts.py` → nothing.
- *Consequence.* AOC2's test ("an attachment with no quote is refused") has nothing real to refuse. G44's Deep Research evidence is met only by hand.
- *Smallest fix.* AOC2 states its producer: an assumption inherits its linked research question's EVIDENCE items, with no engine change.
- *Test.* With one assumption linked to RQ1, a Design Research proposal offers an attachment citing RQ1's finding. An unlinked assumption is offered nothing.
- *Owner.* `assumptions-and-open-answer-coding#AOC2`.
- *Wave.* W2 (E33).

---

## 3. Track 7: Acceptance

### 3.1 Map: each criterion against what the code demonstrates today

| AC | Demonstrated today | Not demonstrable | §1 input over HTTP |
|---|---|---|---|
| AC-01 | Identity seam (`apps/executors/tests/test_product_acceptance.py:129-136`); another **organization** gets 404 (`apps/api/tests/test_project_memory_api.py:91`, `packages/aia_core/tests/test_scope_isolation.py`) | Another **client's** user in the same organization reaches the study by design (`test_scope_isolation.py:209`, `core/application/scope.py:244-247`, ADR 0019): A2 | Client `POST /clients` (`api/routers/scope.py:311`); study with `budget_usd` (`:410, :429`); member (`:583`). **No route creates the organization or its owner** (A5) |
| AC-02 | Lead routes (`api/routers/lead.py:350-440`); edits through `…/edits`; confirmation on `ResearchRuns.start` (`core/application/research.py:716-745`) | Manual AI starts remain (G39, G55); envelope, plan card and typed start (G12); the eleven artifacts | n/a |
| AC-03 | Agent jobs and proposal accept (`core/application/proposal_accept.py`); prompt slots (`api/routers/system_prompts.py:250-292`) | Eleven worker contracts, analysis pins (G57), assumptions (G44) | n/a |
| AC-04 | Ceiling and confirmation (`research.py:716-745`); `AWAITING_BUDGET` park and lift (`core/infrastructure/workflow_repository.py:2193-2304`) | Envelope (LO0/LO1); server threshold on agent jobs (G39) | `PUT /studies/{id}/budget` (`scope.py:481`), `…/spend-confirm` (`:503`) |
| AC-05 | One loader (`core/application/population.py:671`); missing weight fails (`test_population_contract.py:482`) | No tier-A population double (RQC10); **weight identity not served** (A9) | LIVE is operator-only (`population_ops`) |
| AC-06 | No double charge on a kill (`apps/worker/tests/test_worker_processes.py:284, 328`); RECOVERY_REQUIRED (`test_ai_fieldwork.py:695, 1041`); analysis retry reuses the frozen dataset (`research.py:865-895`) | Per-respondent checkpoint (G26, RQC0) | n/a |
| AC-07 | `core/domain/pipeline.py:462 impact_preview`, used only by the generic project route | Working-revision impact (G22, WCE7) | n/a |
| AC-08 | `AdmittedClaim`, suppression, intervals | G31, G32, G45, G46; E4 | n/a |
| AC-09 | Contract-3 object map; register approves `-3` only | `-5` not pinned or registered (E1); segment maps (G30); figures (G54); E2, E3 | n/a |
| AC-10 | Sources (`POST /clients/{id}/sources`); materialize routes (`api/routers/materialize.py:215-278`) | Web page (K2e); data contract (G51, G52); a child consumed (G28) | Document and dataset yes; web page no (K2e) |
| AC-11 | Recorded journey (`apps/executors/tests/test_deep_research_journey.py`); "Ověřeno, přidat zdroj"; Interpretation start | Posture (G37); live routes; D1-D5 | Posture cannot be set (G37) |
| AC-12 | Memory search and reuse, cross-client 404 (`test_project_memory_api.py:65-109`, `test_project_memory_reuse_api.py:76`) | (none: demonstrable) | Past study creatable (`test_product_acceptance.py:207-226`) |
| AC-13 | Internal DOCX and PDF; client DOCX (`research.py:2396`); approve once (`:2462`) | Client PDF, approval before download (G34); E6, E7, E9 | Study self-approval off: `PUT /self-approval` (`scope.py:541-567`), OWNER or ADMIN only |
| AC-14 | `ModelRegistry` fails closed (`core/domain/ai_models.py:18-20, 686`); methodology pins on the run (`research.py:749-780`) | **No edition file exists**; deployment configuration not on the run (A3) | n/a |
| AC-15 | Usage ledger, reservations | Tool spend (G9); per-number provenance (E8); weight (A9) | n/a |

### 3.2 Harness infrastructure

- `tests/acceptance/` does not exist, and `parity-matrix.json` `mvp_acceptance.test` is `null`.
- `acceptance` is not a registered marker under `--strict-markers` (`pyproject.toml:279-288`; G10). G10 cites `:276-282`, which is a stale anchor.
- No CI step collects the tree: the collect-only pass and every pytest step name the four app trees only (`.github/workflows/ci.yml:200, 208-251`).
- `test_parity_matrix.py` asserts that parity blocks nothing and that the criteria's capabilities are the `mvp_path`. Nothing compares the matrix's statements with `mvp-acceptance.md`.
- `tools/parity_status.py:375-378` prints `MVP-ACCEPT-2: NOT_RUNNABLE -- 53 of 53 capabilities on the path are not release-ready` (run at 854c209). A4 is about this line.
- `test_product_acceptance.py` builds its world through `ScopeRepository` (`apps/executors/tests/conftest.py:110-146`) and drains the worker in-process with `run_once()` (`test_product_acceptance.py:194-198`). A5 is about this.

### 3.3 Surviving findings

**A2. AC-01's "another client's user gets 404" contradicts ADR 0019, the decision it cites** (narrowed to AC-01; G73)
- *Claim.* Under ADR 0019, membership of the organization is the access. A "client's user" does not exist, and every member reaches every client's study (`core/application/scope.py:244-247`; `packages/aia_core/tests/test_scope_isolation.py:209 test_every_member_reaches_every_clients_study`). The 404 holds only for another organization.
- *Narrowed.* The AC-12 half is refuted: project memory search is per client and tested (`apps/api/tests/test_project_memory_api.py:85`, `test_project_memory_reuse_api.py:76`).
- *Anchors.* `docs/migration/mvp-acceptance.md:82`; `docs/migration/parity-matrix.json:3961-3966`.
- *Reproduction.* `pytest packages/aia_core/tests/test_scope_isolation.py::test_every_member_reaches_every_clients_study` (passes by design; not run here).
- *Consequence.* The harness author either writes an AC-01 test that fails against ADR 0019 or silently tests something else.
- *Smallest fix.* AC-01 reads "a user of another organization gets 404, not 403, on every study route", changed in both files.
- *Test.* AC-01's acceptance case, written as reworded.
- *Owner.* `mvp-acceptance-harness#14`, whose reconcile list (AC-02, 11, 13, 15) omits AC-01.
- *Wave.* W0 (E01).

**A3. AC-14 has no subject: AIA has no edition file, and nothing records the deployment configuration on a run** (narrowed; G74)
- *Claim.* `config.edition` is NOT_STARTED with no implementation and no gates (`parity-matrix.json:1230-1263`). `edition_config.py` was "replaced by typed config" by design (`docs/migration/module-inventory.md:321`). The run records methodology-type configuration (`research.py:749-780`), but not the AI runtime, the model binding or the switches; `config.environment` says so (`parity-matrix.json:1265-1298`). The builders (MP6, harness#5) build neither, and harness#5 calls AC-14 an "existing path" (`mvp-acceptance-harness.md:75`). LO12b's composition record is not stored per run (`lead-orchestration.md:90-91`).
- *Reproduction.* `python3 -c "import json;print(json.load(open('docs/migration/parity-matrix.json'))['capabilities']['config.edition']['implementation_state'])"` → `NOT_STARTED`.
- *Consequence.* Harness#5's first batch cannot wire AC-14. It would be wired against an undefined artifact or quietly narrowed.
- *Smallest fix.* Reword AC-14 to a referent that exists: typed settings, plus the composition digest stored on each run. Add a chunk that records that digest.
- *Test.* Over HTTP, `GET …/research/runs/{id}` carries the composition digest, and a worker on malformed settings exits non-zero by name.
- *Owner.* `mvp-acceptance-harness#14` (wording) and a new `lead-orchestration#LO12c` (the per-run record).
- *Wave.* W0 for the wording; W1 for LO12c, after LO12b.

**A4. `parity_status.py` ties the acceptance verdict to parity readiness and can never report PASS or FAIL** (G75)
- *Claim.* The verdict is `NOT_RUNNABLE` while any of the 53 on-path capabilities is not PASS + IMPLEMENTED, and `NOT_EXECUTED` otherwise (`tools/parity_status.py:297, 375-378`; pinned by `packages/aia_core/tests/test_parity_status_tool.py:339`). It never reads the acceptance test's JUnit, so parity still gates the acceptance line, against MVP-21 (`mvp-acceptance.md:20-22`). Three on-path capabilities can never become ready as declared: `config.edition`, `artifacts.registration`, and `project.memory` (`parity-matrix.json:2573`, NOT_STARTED with no gates, although `core/application/project_memory.py` and its API tests exist). Harness#8 changes only the exit code (`mvp-acceptance-harness.md:95-114`).
- *Reproduction.* `python3 tools/parity_status.py | tail -1` (run here).
- *Consequence.* The record's "parity report as information" line (harness#6) contradicts the record's own PASS lines for ever.
- *Narrowed after review (2026-10-20).* `mvp-acceptance-harness#3` already owns the acceptance step's JUnit (`--junit-xml … -o junit_family=xunit1`, "which `parity_status.py` reads", `mvp-acceptance-harness.md:6, 68-70`). What no chunk says is that `parity_status.py` must *compute MVP-ACCEPT-2's verdict* from that JUnit. Today it reads JUnit only for capability gates, and the acceptance verdict is still `NOT_RUNNABLE`/`NOT_EXECUTED` by construction. So this is an added acceptance line on harness#3, not a new chunk.
- *Smallest fix.* Compute the acceptance verdict from the acceptance JUnit and report path parity beside it, never in it. Correct the `project.memory` row.
- *Test.* In `test_parity_status_tool.py`, a passing acceptance JUnit gives PASS while the path capabilities stay NOT_RUNNABLE.
- *Owner.* `mvp-acceptance-harness#3` (an added test line; it already owns the JUnit). No new chunk.
- *Wave.* W0 (E01).

**A5. The representative study cannot be provisioned over HTTP, and the fixture the harness says to extend is a back door** (G76)
- *Claim.* §2 forbids touching repositories (`mvp-acceptance.md:46-58`), yet:
  - The organization and its OWNER are created only by `ScopeRepository.create_organization` (`core/infrastructure/scope_repository.py:103`), whose only non-test caller is `core/application/develop_seed.py:229`. There is no `/organizations` route.
  - Self-approval needs the OWNER or an ADMIN (`api/routers/scope.py:541-560`).
  - The fixture harness#3 says to extend (`mvp-acceptance-harness.md:41-43, 62-64`) provisions through the repository and drains the worker in-process (`apps/executors/tests/conftest.py:110-146`; `test_product_acceptance.py:194-198`).

  No plan decides the bootstrap.
- *Reproduction.* `grep -rn "create_organization(" --include=*.py apps packages/aia_core/src | grep -v /tests/` → two hits, neither a route.
- *Consequence.* The record cannot tell setup from test, and the process topology is not production's.
- *Smallest fix.* Harness#3 declares an operator bootstrap (`aia_executors.seed`), named in the record, with everything after it over HTTP and the worker as a subprocess (as `apps/worker/tests/test_worker_processes.py` runs it).
- *Test.* An import-linter contract: `tests/acceptance` imports nothing from `aia_core.infrastructure` or `aia_core.application`.
- *Owner.* `mvp-acceptance-harness#3`.
- *Wave.* W0.

**A6. No plan says which clauses tier A proves for criteria that name live things** (narrowed; G77)
- *Claim.* §9 and I-5 require every criterion green in tier A (`mvp-master-plan.md:441-446`; `mvp-execution-contracts.md:158`). The tier table (`mvp-acceptance.md:62-67`) and RQC10 already project the providers and AC-05 onto doubles. What is unowned:
  - a written tier-A version of each criterion;
  - a record kept per tier (harness#6 is "one line per criterion", `mvp-acceptance-harness.md:9`);
  - AC-15's "agrees with the develop-tagged AWS cost record", which has no tier-A meaning.
- *Reproduction.* **Hypothesis** from reading; there is no test to run.
- *Consequence.* "No partial acceptance" (`mvp-acceptance.md:106`) leaves I-5 two wrong outcomes for AC-15: tier A never passes, or a FAIL is recorded as PASS.
- *Smallest fix.* Each criterion carries its tier-A and tier-B projection in both acceptance files, and the record is per criterion per tier.
- *Test.* `test_parity_matrix` asserts that every `mvp_acceptance` criterion carries `tier_a` and `tier_b`.
- *Owner.* `mvp-acceptance-harness#6` and `#14`.
- *Wave.* W0 for the wording; W5 for the record.

**A7. Folded into A2 and A3.** Harness chunk 5's front matter still says "the built ones first (AC-01, 06, 07, 12, 14)" (`mvp-acceptance-harness.md:8`). That contradicts its own body (`:75`), I-0 (`mvp-execution-contracts.md:152`), A2 and A3; only AC-12 has an existing path. The fix is chunk text, listed in the PR body's proposed edits.

**A9. Weight identity, required by AC-05 and AC-15, is not observable over HTTP** (narrowed; G78)
- *Claim.* The weight is recorded but not served:
  - The run's population note (`core/application/research.py:375-388`) has no weight.
  - A panel run's fieldwork provenance records `weight_role` (`core/domain/panel_source.py:64-74`, embedded by `exec/ai_fieldwork.py:461-475`), in the payload of the `research_fieldwork_dataset` artifact (`exec/research.py:445-450`). That payload is not served by either route:
    - The run's artifact route never inlines that type, "whatever its size" (`api/routers/research.py:154-156, 1634-1638`).
    - The generic project artifact route (`api/routers/runs.py:342-375`) cannot see a research artifact at all: the design project is owned, and only `research_artifacts` reaches it (`core/application/research.py:148-157`).
    - `ArtifactResponse` has no provenance field (`api/schemas/runs.py:108-135`).
    - No route reads that artifact type otherwise (`grep -rn research_fieldwork_dataset apps/api/src` → only the `_NEVER_INLINED` line).

    (Checked against review, 2026-10-20.)
  - `weight_column` exists only on the binding row (`core/domain/population/binding.py:108-109`).
  - The report prints the version label only (`core/application/report_method.py:463-468`).

  No plan owns this.
- *Reproduction.* `grep -rn "weight_column\|weight_role" apps/api/src` → nothing.
- *Consequence.* AC-05's "weight identity in provenance" and AC-15's trace can be observed only through a back door.
- *Smallest fix.* `weight_role` and `weight_column` go into `_population_note` and the "Respondenti a výpočet" section.
- *Test.* Over HTTP on the double, `GET …/research/runs/{id}` gives `metadata.population.weight_column == "vaha_strukturalni_2025"`.
- *Owner.* New chunk `run-qc-and-checkpoint#RQC12`, beside RQC10.
- *Wave.* W1.

---

## 4. Stale statements found on the way (fix the document, not the code)

| Statement | Where | What is true |
|---|---|---|
| "the MVP uses `aia-sociomap-3`" | `mvp-master-plan.md:126` | the owner chose `-5` on 2026-10-20 (E1) |
| #504 "open" | `mvp-owner-decisions.md:69-71` | merged as `18d59ea` |
| Chunk 5's front matter: "the built ones first (AC-01, 06, 07, 12, 14)" | `mvp-acceptance-harness.md:8` | only AC-12 (A7) |
| `pyproject.toml:276-282` | G10 | now `:279-288` |
| `sociomapping.core`: `-3` "INTERNAL_ONLY while D6 is open" | `parity-matrix.json:3485` | approved 2026-10-13. The same stale sentence is in the docstring at `core/domain/research_sociomap.py:323-329`; that one is code and goes with E1's chunk |
| `project.memory` NOT_STARTED with no gates | `parity-matrix.json:2573` | built and tested (A4) |
| Trace 5 B2 reads the refusal as "Failed" | `trace-5-deepresearch-data-infra.md:68-69` | `RUNTIME_UNAVAILABLE` parks (D2) |
| E30 "the map figure carries Stress-1" | `mvp-execution-contracts.md` E30 | `-5` computes no Stress-1, and `report_maps.py:243-250` already handles that (E2) |

## 5. Refuted (one line each)

**Evidence**
- External context never reaching the modules → G33.
- Results reading raw aggregates → G31.
- No client PDF, ungated downloads, no approval reader, the downloader as producer → G34, RD1-RD3, RD8.
- A finding with no claim ids passing → G32.
- The client export escaping MVPQ-04 → `evidence-integrity#9b` names it.
- Every past run's analysis unreadable after a change → PC3 retry (`analysis_results.py:722-756`).
- Internal estimates admitted without an interval → removed on every surface (`native.py:322-339`).
- A `-5` map failing validation for lack of Stress-1 → a fit caption is set (`report_maps.py:245-249`).
- An approved client report replaced by a later composition → the newest approved version is served (`client_report.py:241-262`).
- Panel runs carrying no weight → `analysis_weight` (`panel_persona.py:291`); only a docstring is stale.
- `-5` not computable at all → a Metodika preset (`methodology/sociomap.py:2012`).
- The `-5` reconciliation unrecorded → recorded as open (MVPQ-03); kept only as E2.

**Deep Research**
- "Full design" in AC-11 meaning the content read → it means the classification of an edited design (`mvp-cohesion.md:34, 55-70`).
- Tool spend mixed into `actual_cost_usd` → I20, G9.
- Track reuse ignoring posture; retry re-freezing posture → trace 5.
- No ceiling without a spend limit → by design (I4, G11).
- Live approval only for fictional clients → only the test-policy path (`deep_research_settings_repository.py:238-244`).
- The posture column and setter → G37.
- Connectors only in agent-directed mode → §4 row.
- The Lead cannot start Deep Research → `research-lead-workbench#23`; only the wave conflict survives, as D3.
- Interpretation run unbudgeted → G38.
- A verified source bypassing the `source_id` rule → SOURCE items go through `add_source_once` by design.
- "Chunks 33-37 have no builder" → E27 schedules them; D5 keeps only the register row and the switch.

**Acceptance**
- The marker and the CI collection → G10, harness#3/#9.
- Study self-approval or `budget_usd` not settable over HTTP → `scope.py:541-567`, `:429`, `:481`.
- Web page intake → K2e.
- Population double → RQC10.
- Client PDF and second person → G34, §6.2.
- Posture setter → G37.
- Interpretation budget → G38.
- AC-06 and AC-07 claimed built → §6.2 and harness#5's body.
- Matrix and document wording differences → refinements; the matrix is authoritative (`mvp-acceptance.md:77`).
- Browser evidence before harness#10 → W1-W4 extend chunk 10.
- The scripted-provider import → left to chunk 3.
- AC-12's "another client's studies cannot be found" → true and tested (A2, narrowed).
- The web omitting `-5` from `OBJECT_MAP_METHODS` → `readObjectMap` falls back (`object-map-view.ts:115-123`); this matters only for preference beside `-3`.
