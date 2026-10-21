---
status: done
chunks:
  - "[x] 1. The switch: AIA_DATA_CLASS_GATES=enforce|advisory in domain/deployment.py, read by the API, the worker and the executors; refused in staging, production and an unknown environment"
  - "[x] 2. Egress and the model gateway: a class-only refusal (unclassified material, a route not approved for the class) passes in advisory and is recorded on every ledger row of the call and in its provenance"
  - "[x] 3. The Research Lead, the research agents and validation: an unknown class reaches the gateway in advisory instead of an assertion or a park"
  - "[x] 4. The retrieval gate and Brave: a class-only refusal passes in advisory; Brave's search takes a query of any class there; each pass on the DISPATCHED tool event"
  - "[x] 5. Deep Research's design classification (OI-129): an unclassified design takes the design rule's class in advisory, recorded on the plan step's event"
  - "[x] 6. develop runs advisory: Compose, the deploy workflow, and the Compose test"
---
# Develop: data class gates advisory

**Status:** done · **Drafted:** 2026-10-21 · **Branch:** `feature/develop-class-advisory`
from `develop` @ `b3b55817`

## Decision (the product owner, Nigel Blount, 2026-10-21)

In this session, in his own words: "build the develop-only class-advisory switch, including Brave
for any class". It follows his /pmstatus answers: Q65, "i dont want any gates stopping based on
the classification we are going for full functionality right now", and Q66 (a), "Develop only:
classes are shown and recorded, never block; EU residency and licences still hold", with "dont
limit the brave search capabilities either".

So: one switch, `AIA_DATA_CLASS_GATES=enforce|advisory`, default `enforce`. On `advisory`, every
gate that refuses **solely because of a data class** records a warning and lets the call
proceed. `advisory` is set only by develop's Compose file; staging, production and an unknown
`AIA_ENV` refuse to start with it. Brave's search is the one stated exception to EU residency, for
search queries only: in advisory it takes a query of any class.

## What advisory means, exactly

- **The class is still computed** everywhere it is today, by the same rules
  (`domain/material_rules.py`, `domain/deep_research/classification.py`), and shown and stored
  wherever it is today.
- **A class-only refusal becomes a recorded pass.** The record (`ClassAdvisory`,
  `domain/residency.py`) names the gate, the refusal enforce mode would have made, the class
  (`unclassified` when none), and `advisory=true`. It is written where the refusal would have
  been: the note of every AI usage ledger row of the call and the call's provenance
  (`CallProvenance.class_advisories`); the note of the retrieval gate's `DISPATCHED` tool event;
  a step event for the two refusals made by an executor before any call (Deep Research's plan,
  validation's arms).
- **Unclassified material is judged as Class A** for every residency check that still holds:
  unknown is never scored as the permissive answer (CLAUDE.md § 8). The ledger row's
  `data_class` is that judged class, and its note says it was unclassified.
- **Still enforced, in both modes:** EU residency for model calls (EU processing, training
  exclusion, bounded retention for A and B, `residency.py:239-256`); the licence gate; the lineage
  `unclassified-client-knowledge` (a licence refusal, not a class one); budgets, reservations and
  the study's spend limit; scope; the route/provider match; tool metering; ADR 0022's live sign-off
  (`plan.py:122-136`); every fetch, dataset, archive and Common Crawl route's residency (only the
  search route of Brave is exempt). A class-only refusal on a route whose residency still refuses
  stays a refusal, with the residency reason.

## The gates found (anchors @ `b3b55817`)

| # | Gate | Anchor | Class-only? | In advisory |
|---|---|---|---|---|
| G1 | Egress: unclassified material | `packages/aia_core/src/aia_core/domain/residency.py:223-228` | yes | passes, judged as A, recorded |
| G2 | Egress: route not approved for the class | `domain/residency.py:233-237` | yes | passes, recorded |
| G3 | Egress: A/B need EU processing, training exclusion, retention | `domain/residency.py:239-256` | no: EU residency | **enforced** (Brave search excepted, G9) |
| G4 | Model gateway's egress (every model call: fieldwork, analysis, agents, Lead, Deep Research, client source proposals, triage) | `packages/aia_core/src/aia_core/application/model_gateway.py:342-350` (`_lane`), preflight `:251` | via G1/G2 | passes, on every ledger row's note and in `CallProvenance` |
| G5 | ModelPolicy / ModelRegistry | `domain/ai_models.py` (no `DataClass` anywhere: `grep -n DataClass domain/ai_models.py` is empty) | none | nothing to change |
| G6 | The Research Lead: an unknown part of its context (`context_classification`, `lead_request`) | `domain/research_lead.py:808-814`; executor's park `apps/executors/src/aia_executors/research_lead.py:189-198` and assertion `:201` | yes (G1) | the request reaches the gateway; the class recorded is the gateway's |
| G7 | Research agents: an undeclared stored prompt (`prompt_data_class`) | `domain/research_agents.py:609-621, 681-688`; executor `apps/executors/src/aia_executors/research_agents.py:240-247` and assertions `:256-260` | yes (G1) | the same as G6 |
| G8 | Retrieval gate: route class approval, `class_a_query`, `class_a_url` | `packages/aia_core/src/aia_core/application/web_retrieval.py:608-632, 796-799, 896-898, 1186-1189, 1290-1292, 1400-1405` | yes | passes where residency allows, recorded on the `DISPATCHED` event |
| G9 | Brave's search route: Class C only, outside the EU | `apps/executors/src/aia_executors/deep_research_live.py:104-116, 223-228` | yes, and residency | the route declares `any_class_when_advisory`: any class, recorded (the stated exception) |
| G10 | Deep Research parks an unclassified design (OI-129) | `apps/executors/src/aia_executors/deep_research/plan.py:163-175` | yes | the design rule's class (B) when no operator classified it, on a step event |
| G11 | Validation's arms park unclassified material | `apps/executors/src/aia_executors/validation.py:267-271` | yes | sent judged as Class A, on a step event and the arm's artifact |
| G12 | Licence gate | `domain/licence.py`, `domain/licence_determinations.py`; `model_gateway.py:370-375` | no | **enforced** |
| G13 | Budget, reservation, spend limit | `model_gateway.py:399-416, 488-501`; `web_retrieval.py:614-615` | no | **enforced** |
| G14 | Scope | `residency.py:216-221`; `web_retrieval.py:546-549` | no | **enforced** |
| G15 | Deep Research's priced live routes need ADR 0022's sign-off | `deep_research/plan.py:122-136` | no | **enforced** |

Paths not listed that send a model material (`ai_fieldwork.py:443-457`, `analysis.py`,
`client_source_proposals.py:205-255`, `deep_research/_shared.py:300`,
`application/deep_research_triage.py:294`) always compute a class and are judged by G4 only.

## Chunks

1. **The switch.** `DataClassGates` and `data_class_gates_problem` in `domain/deployment.py`, one
   rule for both processes (AGENTS.md § Pydantic settings, the 2026-10-02 outage). The API's
   `Settings.data_class_gates`, refused by `validate_for_production` in staging and production;
   `WorkerSettings.data_class_gates`; `AIRuntimeSettings.data_class_gates`, which the
   compositions hand to the gateway and Deep Research's config.
2. **Egress and the gateway.** `evaluate_egress(class_gates=)` and `EgressDecision.advisories`;
   `GovernedModelGateway(class_gates=)`; every ledger row of a call carries the advisory in its
   note, and `CallProvenance.class_advisories` the same.
3. **Lead, agents, validation.** Record the gateway's class and advisories in their provenance
   instead of asserting the request's; validation sends an unclassified specification to the
   gateway in advisory.
4. **Retrieval gate and Brave.** `RetrievalGate(class_gates=)`; `ToolRoute.any_class_when_advisory`
   (a search route only), set by `brave_retrieval` alone.
5. **OI-129.** The plan step's design class in advisory.
6. **develop.** `AIA_DATA_CLASS_GATES: advisory` in Compose's shared environment, the deploy
   workflow's check, and `test_develop_host_configuration.py`.

## Trade-off

On develop the data class no longer stops anything: a design, a Lead turn or a prompt nobody
classified is sent (judged as Class A for residency), and Brave, outside the EU, may receive a
search query written from client material. Every such pass is recorded, never silent; the
switch cannot start in staging or production.

## What landed, and its tests

| Gate | Advisory now | Test |
|---|---|---|
| G1, G2 egress | recorded pass (`EgressDecision.advisories`) | `packages/aia_core/tests/test_class_advisory.py::test_advisory_judges_unclassified_material_as_class_a_and_records_both_refusals`, `::test_advisory_passes_a_class_the_route_is_not_approved_for_and_records_it`; enforce `::test_enforce_refuses_a_class_only_egress_as_it_always_has` |
| G3 residency | **enforced** | `::test_advisory_still_enforces_eu_residency_and_needs_a_route` |
| G4 gateway | recorded pass, every ledger row's note, `CallProvenance.class_advisories` | `::test_the_gateway_under_advisory_sends_unclassified_material_and_writes_it_on_every_row`; enforce `::test_the_gateway_under_enforce_refuses_and_sends_nothing` |
| G6 Lead | recorded pass, `class_advisory` in the turn's provenance | `apps/executors/tests/test_research_lead_executor.py::test_under_advisory_class_gates_an_unclassified_turn_is_answered_and_says_so`, `::test_under_advisory_class_gates_a_class_a_turn_rides_a_route_approved_for_b_and_c`; enforce unchanged (`::test_unclassified_material_parks_the_turn_before_any_call`) |
| G7 agents | recorded pass, `class_advisory` in the job's provenance | `apps/executors/tests/test_research_agent_executor.py::test_under_advisory_class_gates_an_undeclared_version_is_sent_and_says_so`; enforce unchanged |
| G8 retrieval | recorded pass on the `DISPATCHED` event where residency allows | `test_class_advisory.py::test_the_retrieval_gate_under_advisory_sends_it_and_records_the_refusal_it_lifted`, `::test_the_retrieval_gate_under_advisory_still_enforces_residency_off_the_brave_route` |
| G9 Brave | any class, recorded | `test_class_advisory.py::test_brave_under_advisory_takes_a_query_of_any_class_and_records_it`; enforce `::test_brave_under_enforce_refuses_any_class_but_c`; composed `apps/executors/tests/test_deep_research_class_advisory.py::test_brave_composed_declares_the_exception_and_takes_any_class_only_under_advisory` |
| G10 OI-129 | design rule's class (B), on the plan step's event | `test_deep_research_class_advisory.py::test_under_advisory_an_unclassified_design_takes_the_design_rule_and_says_so`; enforce `::test_under_enforce_an_unclassified_design_parks_the_run_and_sends_nothing` |
| G11 validation | sent as Class A, on a step event and the artifact | `apps/executors/tests/test_validation_executors.py::test_under_advisory_class_gates_an_unclassified_questionnaire_is_sent_and_says_so` |
| G12 licence | **enforced** | `test_class_advisory.py::test_the_gateway_under_advisory_still_enforces_residency_and_licence` |
| G13 budget, metering | **enforced** | `::test_the_gateway_under_advisory_still_needs_a_reservation_for_a_metered_call`, `::test_brave_under_advisory_is_still_metered_against_the_study` |
| G14 scope | **enforced** | `::test_advisory_still_needs_an_issued_scope` |
| The switch | staging, production, unknown refuse | `test_class_advisory.py::test_advisory_is_refused_in_staging_production_and_an_unknown_environment`; `apps/api/tests/test_config_and_security.py::test_staging_and_production_refuse_advisory_data_class_gates`; `apps/worker/tests/test_worker_settings.py::test_a_worker_outside_local_test_and_develop_refuses_advisory_gates`; `apps/executors/tests/test_develop_host_configuration.py::test_advisory_gates_under_staging_are_refused_by_both` |
| develop | advisory in both processes, fixed in Compose, checked by the deploy | `test_develop_host_configuration.py::test_develop_runs_its_data_class_gates_advisory_in_the_api_and_the_worker`, `::test_the_develop_deploy_workflow_checks_the_gates_are_advisory` |

**Decisions made in the code, for the docs PR to carry:**

- **Unclassified is judged as Class A**, never as the permissive answer; the ledger row's
  `data_class` is A and its note says `class=unclassified`. Validation's arm, which builds its
  requests itself, sends an unclassified specification as Class A in the same way, and its
  artifact carries `class_advisory` beside that class. (Widening `ai_respondent.build_request`
  to take `None` was tried and dropped: it moved the Metodika step pin of `response/request`,
  `test_methodology.py::test_every_step_pin_matches_the_function_it_describes`.)
- **"A Class A query never leaves" is a class rule**, so under advisory it is lifted like the
  others: a Class A query can leave over a route whose residency allows A (an EU-approved route;
  none of today's live web routes) and over Brave's search (the stated exception). The retrieval
  gate reports the refusal that still holds when residency refuses (`egress_residency_violation`
  instead of `egress_route_not_approved_for_class`), so the reason a person reads is the true one.
- **Wikipedia's routes and the public fetch keep refusing client material under advisory**:
  they are not EU-approved, and the owner's exception names Brave's search alone. On develop,
  Deep Research with `AIA_DEEP_RESEARCH_WEB_SEARCH=wikipedia` on a Class B design still blocks its
  web tracks (`SEARCH_ROUTE_REFUSED`, `egress_residency_violation`); with `brave` it runs.
- **OI-129 under advisory** applies the design rule only when no operator classified the design;
  an operator's classification (the synthetic fixtures' Class C) is kept as before, so enforce's
  behaviour and every recorded fixture are unchanged.

**Deliberately not done:** the Settings document (`GET /api/v1/settings`) does not list
`AIA_DATA_CLASS_GATES` yet: it would need the web's guide and Czech labels
(`apps/web/src/components/aia/settings/settings-guide.ts`, `apps/web/src/i18n/cs.ts`), a web
change outside this plan. The worker logs the mode at start (`aia_worker/worker.py`, "worker
started").

## Findings

None.

## Doc follow-up

- **CLAUDE.md** § The map, under `domain/deployment.py`'s neighbours and `config.py`: "AIA_ENV …;
  `AIA_DATA_CLASS_GATES` (`enforce` | `advisory`, default enforce): advisory makes every refusal
  made solely because of a data class a recorded pass (`ClassAdvisory`: ledger note, provenance,
  the tool event, a step event); develop only, refused in staging and production; EU residency,
  licences, budgets and scope still hold; Brave's search takes any class there." And in the
  paragraph "A research run executes a Design Revision", after the class sentence: "On develop
  (`AIA_DATA_CLASS_GATES=advisory`) a class-only refusal is a recorded pass."
- **ADR 0008 amendment** (2026-10-21): the owner's develop-only advisory mode, what it relaxes
  (G1, G2, G8, G9 search only, G10, G11), what it never does (G3, G12-G15), where each pass is
  recorded, and that unclassified material is judged as Class A.
- **open-items.md OI-129**: on develop, decided and implemented as advisory (this plan, chunk 5):
  an unclassified design takes the design rule's class; still open for staging and production.
