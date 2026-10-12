---
status: in-progress
chunks:
  - "[x] 0. Record the OI-61 determination: PIAAC, ISSP and the Czech panel APPROVED for bedrock-eu-primary"
  - "[ ] 1. ADR: panel-grounded AI respondents are modelled evidence, never measured"
  - "[ ] 2. Sample: PPS without replacement from the run's recorded population, audience filters, parity with 18.6.6"
  - "[ ] 3. Persona: facts and the structured profile from the sampled row, every field through decide(PERSONA_CONSTRUCTION)"
  - "[ ] 4. Origin: MODELLED_AI_PANEL through dataset, analysis, Sociomap and report, MODELED basis with disclosure"
  - "[ ] 5. Executor: the panel source behind AIA_AI_PANEL_PERSONAS_ENABLED (off by default), cost measured"
  - "[ ] 6. Screens: audience and subpanels live where they say 'V AIA zatím není'; modelled labelling"
  - "[ ] 7. Validation: persona ablation and a holdout against known marginals before any client-facing claim"
---
# Panel-grounded AI respondents

## Why

Today an AI respondent inherits nothing from the population. `fictional_roster`
(`packages/aia_core/src/aia_core/domain/ai_respondent.py:255 @ 5d545eb`) draws sex,
age (18-89), education and region **uniformly** from `random.Random(seed)`, weight 1.0,
an invented donor. Only the six response styles depend on those attributes
(`respondent_behavior.py:66`, `_LINKS`; `assign_styles` :275). A run records the LIVE
population binding at creation, but no step reads it (CLAUDE.md § population).

18.6.6 drew respondents from the panel: PPS without replacement, probability
proportional to `vaha_kalibrovana`, audience filters through the one canonical mask
(`legacy/npc-panel-18.6.6/app/pipeline.py:240`, `sample_representative`), and built
each persona from the row in a structured "survey format" with only the most
pronounced traits (`pipeline.py:528`, `generate_persona_text`; `dispozice.py:494,579`).

The blocker was OI-61. On 2026-10-12 the owner determined that licensing is not a
problem (decisions below).

## Decisions (owner, 2026-10-12, in session)

1. **Licence.** PIAAC, ISSP and `czech_population_panel` may be sent to a model
   provider. Basis: owner determination. Route: **`bedrock-eu-primary` only**
   (ADR 0010; `deploy/develop/env.example:51`), not `ANY_APPROVED_ROUTE`. A future
   route needs its own determination.
2. **Evidence status.** Answers of panel-grounded respondents are **modelled
   evidence**: admissible only as `ClaimBasis.MODELED` with the `MODELED_VALUE`
   disclosure (`domain/evidence/claims.py:67-100`), never `MEASURED`. That makes
   this a new origin outside `NON_EVIDENCE_ORIGINS` (`domain/fieldwork.py:50-68`)
   and needs an ADR before code (chunk 1).

## Chunks

**0. Determination.** Replace the three UNDETERMINED records in
`domain/licence_determinations.py` with APPROVED, `decided_by` the owner,
`decided_on=2026-10-12`, the basis above, `approved_routes={"bedrock-eu-primary"}`.
Tests: the gate passes panel lineage on that route and refuses it on any other
(`test_licence_gate.py`). Residency still applies unchanged: a client study's
material stays Class A.
*Open:* OI-61's text asks for legal's confirmation beside the data owner; the owner's
determination is recorded as the basis, and the docs PR closes OI-61 citing it.

*Landed:* `licence_determinations.py` records the three datasets APPROVED for
`PANEL_APPROVED_ROUTE = "bedrock-eu-primary"`
(`test_licence_gate.py::test_each_panel_derived_dataset_reaches_the_eu_bedrock_route_and_no_other`).
Over any other route the gateway now refuses panel lineage as
`licence_not_approved_for_route`, no longer `licence_undetermined`
(`test_model_gateway.py::test_licence_is_a_second_gate_refused_before_dispatch`). The
fieldwork step fails `persona_source_unsupported` before anything is reserved or sent
when a persona is not fictional, until chunk 5 gives it a panel source
(`test_ai_fieldwork.py::test_panel_derived_personas_fail_before_any_call_while_no_panel_source_exists`;
see Findings).

**1. ADR.** Panel-grounded respondents as modelled evidence. It covers: what an
analysis may claim from them (aggregate and segment, MODELED, disclosed); what it may
not (MEASURED, individual-level facts the model produced); how support and Kish n
read for a sample drawn from a synthetic population; the interaction with D6 (Sociomap
`INTERNAL_ONLY`); report wording.

**2. Sample.** Port `sample_representative` to the domain: PPS without replacement on
the weight role the binding names, refusal (not duplication) when n exceeds support,
the audience mask shared by preview and fieldwork. Reads rows only through
`PopulationRuntime.load_for_run` (`application/population.py:494`). Seeded from the
spec fingerprint as today (`ai_fieldwork.py:93`). Parity fixtures captured from the
unit's own function (`tools/aggregate_capture.py` pattern).

**3. Persona.** Port `generate_persona_text` (persona modes, top-k traits,
structured format). Every field shown or used asks
`RuntimePopulation.decide(field, FieldUse.PERSONA_CONSTRUCTION)` and, combined,
`decide_joint`. The fact layer reads the row's columns: a question the panel answers
becomes DIRECT (answered by code) instead of UNSUPPORTED. Styles from
`assign_styles` over the real rows. Real weights and donor ids. Parity fixtures.

**4. Origin.** `DataOrigin.MODELLED_AI_PANEL`; dataset, analysis harness
(`analysis/harness.py:141`, `analysis/native.py:491`), Sociomap labelling
(`research_sociomapping.py:359`) and report read it as modelled, never synthetic
fiction and never measured.

**5. Executor.** `ai_fieldwork` takes a persona source per run: fictional roster or
panel. Behind `AIA_AI_PANEL_PERSONAS_ENABLED`, off by default and in test. The
profile is longer than four facts: measure input tokens and cost per respondent and
state them in the commit body. The run's provenance names the source, binding,
roster or sample version and the persona mode.
Code comments that still give OI-61 as the reason fieldwork is fictional change with it:
`domain/ai_respondent.py:19-24`, `application/research.py:176,216`,
`apps/api/src/aia_api/routers/research.py:187`, `apps/web/src/lib/research-execution.ts:98`
(all @ `ea5210e`); after OI-61 the reason is that no panel persona source exists.

**6. Screens.** Audience filters and the 18 subpanels become live where they now say
"V AIA zatím není"; results say "modelováno" every time.

**7. Validation.** Port the unit's persona ablation (`persona_ablation.py`: arms
none / demographics / full, TVD per question) and add a holdout: questions whose
population marginals are known (ISSP items in the panel), asked of panel-grounded
respondents, compared. No client-facing claim until the holdout result is recorded.

## Findings

- **Opening the licence gate alone would have made a non-fictional persona cost money
  before failing.** With chunk 0's records and no guard, a non-fictional persona on
  `bedrock-eu-primary` passed preflight; every respondent's blocks were sent and paid
  for, and only then `assemble_dataset` refused the dataset
  (`domain/ai_respondent.py:682 @ 5d545eb`), so the attempt ended `UNKNOWN`. No
  production path built such a persona, since `fictional_roster` is the only source.
  Reproduction: remove the guard and run
  `test_ai_fieldwork.py -k panel`; it fails with `FailureClass.UNKNOWN`. Fix: the
  pre-call guard in `ai_fieldwork.py` (chunk 0). Chunk 5 replaces it with the panel
  source.

## Doc follow-up

- `CLAUDE.md` § research run: "Panel-derived data reaches no model provider until OI-61
  records a licence determination" → panel-derived data may reach `bedrock-eu-primary`
  (OI-61 determined 2026-10-12, owner); fictional and panel persona sources.
- `.planning/open-items.md` OI-61: resolved, citing chunk 0's commit.
- `ARCHITECTURE.md` / evidence: the new origin and its MODELED-only admission.
