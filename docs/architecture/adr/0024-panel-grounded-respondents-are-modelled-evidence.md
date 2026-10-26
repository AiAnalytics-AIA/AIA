# ADR 0024 — Panel-grounded AI respondents are modelled evidence: their own origin, admitted only as modelled, client-facing only once validated

**Status:** Proposed — develop (2026-10-12). Plan:
[panel-grounded-respondents](../../../.planning/plans/panel-grounded-respondents.md), chunk 1.
**Builds on** [ADR 0016](0016-research-execution-and-model-transmission.md) (research runs, the
`ai_runtime` source, decision 5's licence gate), the evidence gates (`domain/evidence/`), and
the population contract ([population.md](../population.md)). **Answers, for one origin,** the
part of decision ANL-1 (`.planning/overview.md`) that asks *whether any instrument evidence may
ever be client-facing, and on what origin*. **Leaves open** D6 (the Sociomap) and ANL-1 for every
other origin.
**Owner decision, 2026-10-25** (ADR-0020-0024 (b), the audit page, relayed by coordinator 3): the owner will review ADRs 0020 to
0024 one by one. His note, verbatim: "i want to review them, Create a document that includes all the
questions, how they're connected in AIA, and the inputs and outputs. Include an example when
explaining complex topics. do it for each individually." The status is unchanged until he does.

**Date:** 2026-10-12

## Context

AIA's AI respondents are invented. `fictional_roster` draws sex, age, education and region
uniformly from a seeded generator, with weight 1.0 and an invented donor
(`domain/ai_respondent.py:255 @ ea5210e`). Their datasets are `SYNTHETIC_AI_FICTIONAL`, and every
synthetic origin is in `NON_EVIDENCE_ORIGINS` (`domain/fieldwork.py:66`). Nothing they say reaches
a client.

18.6.6 drew its respondents from the population panel instead: PPS sampling without replacement
on the calibrated weight (`legacy/npc-panel-18.6.6/app/pipeline.py:240`), and a persona built from
the sampled row (`pipeline.py:528`). AIA could not port that while OI-61 left the panel's licence
undetermined. On 2026-10-12 the data owner made two decisions:

1. The panel's sources may reach `bedrock-eu-primary`, and only that route. This is recorded in
   `licence_determinations.py @ a7616ef` (PR #289), and OI-61 is closed.
2. Answers from panel-grounded respondents are **modelled evidence**: admissible, but never as
   measurement.

Today three refusals stand between any research answer and a client, independently:

- **The origin gate.** `admit_numeric_claims` blocks a client-facing claim whose row's origin is in
  `NON_EVIDENCE_ORIGINS` (`domain/evidence/admission.py:244`), and native analysis preflight does
  the same (`domain/analysis/native.py:508`).
- **The instrument policy.** `aia-instrument-evidence-1` declares a study's own items
  `NEVER_MEASURED_FACT`, `AGGREGATE_ONLY`, `PERSON_VALUE_MODELED` and `INTERNAL_ONLY`. It refuses
  any origin other than the simulated ones, including none
  (`domain/evidence/instrument.py:1-40,80`).
- **The joint certificate.** A run with no `CORE_JOINT_STATUS` certificate admits no client claim
  (`native.py:524`).

A grounded respondent is still a model answering *as* a synthetic person, and the panel itself is
synthetic: rows built from PIAAC, ISSP and Czech survey donors. What grounding adds is real
structure: who is sampled, in what proportion, with which attributes jointly. What it does not add
is an observation of anyone's opinion. Evidence must say exactly that.

## Decision

### 1. A new origin, stamped from facts: `DataOrigin.MODELLED_AI_PANEL`

- A dataset carries `MODELLED_AI_PANEL` only when every respondent was built from a row sampled
  from the run's own recorded `PopulationBinding`, read through `PopulationRuntime.load_for_run`.
  Each persona's lineage is that binding's datasets, and its donor is the row's `core_donor_id`.
- Mixed rosters are refused, not labelled. So is a binding the run did not record, and so is a
  persona whose fields were not each allowed by
  `RuntimePopulation.decide(field, FieldUse.PERSONA_CONSTRUCTION)` and, combined, by
  `decide_joint`.
- No caller chooses an origin. `assemble_dataset` derives it from the personas, as it derives
  `SYNTHETIC_AI_FICTIONAL` today.
- `MODELLED_AI_PANEL` is **not** in `NON_EVIDENCE_ORIGINS`. It is also not "observed": no origin
  in AIA is observed fieldwork, and none is introduced here.

### 2. The origin gate becomes an allowlist

- A client-facing claim is admitted only from an origin in `CLIENT_ADMISSIBLE_ORIGINS`, which this
  ADR sets to `{MODELLED_AI_PANEL}`.
- Every other origin, including `None` and any origin added later, is refused client-facing until
  someone decides otherwise.
- Today's gate is a denylist. `row.data_origin in NON_EVIDENCE_ORIGINS` is false for `None` and for
  any new origin, so it lets both through. That fail-open is harmless only because the instrument
  policy refuses them first.
- `NON_EVIDENCE_ORIGINS` stays, for labelling ("simulated respondents"). It no longer decides
  admission.

### 3. A second instrument policy for this origin, `aia-instrument-evidence-2`

| Rule | `-1` (simulated origins) | `-2` (`MODELLED_AI_PANEL`) |
|---|---|---|
| A measured fact (`NEVER_MEASURED_FACT`, provenance `MODELLED`) | never | **never** |
| Aggregate only (`AGGREGATE_ONLY`, `PERSON_VALUE_MODELED`) | yes | **yes** |
| Client-facing | never (`INTERNAL_ONLY`) | **only as `ClaimBasis.MODELED`, at `AGGREGATE` or `SEGMENT` level, with `Disclosure.MODELED_VALUE` and `SCOPE`, and only under §4** |
| Uses | internal analysis | internal analysis, client-facing modelled claims |

- `-1` is unchanged for the origins it covers.
- An individual-level claim is refused on every surface ("respondent R00042 said…" is a model's
  output, not a person's answer).
- A measured claim is refused on every surface, internal included. This keeps the rule
  `claims.py` states: an internal analysis that calls a modelled prior a measurement is the error
  that later reaches a client.

### 4. Client-facing needs a current validation, bound to the respondent system

A modelled claim reaches a client only while
`effective_validation_status(state, system_fingerprint(...))` reports a validation earned on the
**current** respondent system (`domain/evidence/validation.py:87,115`). The fingerprint's
components are:

- the respondent prompt's SHA-256;
- the persona builder and persona mode;
- the sampler version;
- the population version the binding names;
- the model binding (provider, model, route);
- the response-process version.

Any change to these makes the validation stale, and the claim internal again. What earns the
validation is the plan's chunk 7: persona ablation (none / demographics / full) and a holdout
against marginals the population knows. Its thresholds are a methodology decision, recorded with
the result and not here. Until a validation exists, every `MODELLED_AI_PANEL` claim is internal,
under `-2`'s other rules.

The tier gate still applies on top (`evaluate_tier`): segment breakdowns need a tier that permits
`demographic_breakdown` or `segmentation`.

**Amendment, 2026-10-13: the client report ahead of the validation.** The product owner decided
(in session, recorded in
[complete-study-report](../../../.planning/plans/complete-study-report.md), "B5 owner
decisions") that modelled numbers may enter the **client report only** before a validation
exists. It is a recorded exception to this section, not a change of its rule:

- It is data, `MODELLED_CLIENT_REPORT_LIFT` (`domain/evidence/report_lift.py`): who decided,
  when, the surface (`CLIENT_REPORT`), and the note every client report prints. Only the client
  composer (`application/client_report.py`) passes it, and it drops `INTERNAL_ONLY` from a
  modelled run's `-2` items, for a run that recorded its respondent system, and nothing else.
  The lift's id is part of the instrument declaration's identity.
- Every other rule stands: support and suppression, the interval a client estimate needs, the
  modelled disclosure on every number, the refusal of any predictive-validity claim, and the
  population's joint certificate, which a panel run now records beside its dataset
  (`JOINT_CERTIFICATE_METADATA`) and its evidence is judged under.
- Client-facing **analysis** (the eight modules' prose) never passes the lift and still waits
  for the validation this section describes.

Revoking it is removing that record; the chunk-7 validation, once earned, supersedes it.

**Amendment, 2026-10-22: the client report's checks warn.** Since 2026-10-22 (the product owner:
"lets get rid of these strict gates", "Relax RD0 too", "Warnings for all of it"; report-delivery
RD0, #879), the client report's checks (`drill_down_content`, `unadmitted_number`,
`ledger_not_client_facing`, `gate_unrecorded`, and the Interní dokument check once RD11 cites a
client source) warn in the approval dialog, are named by where they are, and are recorded on the
approval's ledger row (`approval_decisions.warnings`); none refuses
(`packages/aia_core/src/aia_core/domain/report/client_gate.py:32-36 @ 5d5ed250`;
`application/report_approval.py:151-170 @ 5d5ed250`; `infrastructure/tables.py:2010 @ 5d5ed250`).
What composition admits is unchanged (only `CLIENT_FACING` claims); the researcher approves past
what the checks name, on record.

### 5. Support counts donors, not respondents

- Grounded respondents are drawn from synthetic rows that share survey donors. Support is the
  unique `core_donor_id`s behind a value, under the thresholds already ported
  (`domain/evidence/support.py`: `min_layer_donors` 25, Kish `n_guard` 25, indicative under 50,
  `SUPPRESS` by default).
- Intervals are the donor-clustered bootstrap already in `research_aggregate.py`.
- Weights are the weight role the binding names. There is no default weight, and no fallback.
- A sample of 1,000 respondents built on 40 donors is reported as 40-donor evidence.

### 6. What does not change

- **The Sociomap** is `INTERNAL_ONLY` while D6 is open, whatever the origin
  (`research_sociomapping.py:359`).
- **The joint certificate** is required client-facing, as today.
- **Respondent facts the panel holds** are answered by code (`respondent_facts.py`). A fact the
  panel does not hold is still refused, never invented by the model.
- **Residency.** A client's questionnaire is Class A, and only a route approved for Class A
  carries it.
- **Deep Research** is never an input to fieldwork or to the canonical Sociomap (ADR 0021).

### 7. How it reads, everywhere

Every surface that shows a `MODELLED_AI_PANEL` number says it is modelled, every time:

- results;
- analysis;
- the report;
- exports.

The Czech wording is "modelováno: AI respondenti z populace". "Respondents said", "measured" and
"survey found" are never used. The report prints the disclosure beside the number, not in a
footnote, along with the validation's date and fingerprint.

## Consequences

- AIA can say something to a client from AI respondents for the first time, and only something
  stated as modelled, aggregated, donor-supported and validated on the exact system that produced
  it.
- Every change to the prompt, the persona builder or the model makes client claims internal again
  until revalidated. That is deliberate, and it is a cost: model upgrades need a validation run
  before client use.
- `-1` and the fictional roster are untouched, so existing runs read exactly as before.
- Cost per respondent rises with the persona's length. The plan's chunk 5 measures it before the
  source is switched on (`AIA_AI_PANEL_PERSONAS_ENABLED`, off by default).

## Alternatives considered

- **Keep panel answers non-evidence, like the fictional roster.** This is the safest option, but
  it is not what the owner decided, and it would leave the panel's structure unused for anything a
  client sees.
- **Treat them as measured, like a survey.** Rejected. A model's answer is not an observation,
  and `claims.py`'s first rule forbids presenting a modelled figure as a measurement.
- **Admit without validation, with the disclosure only.** Rejected. A disclosure says *what* a
  number is, not *whether it tracks reality*. 18.6.6 itself held persona conditioning to a
  measured ablation (`persona_ablation.py`) and validity to a holdout certificate.

## Open

- **Legal's confirmation of OI-61.** The basis recorded is the owner's determination alone.
- **The validation thresholds** for §4: methodology owner, with chunk 7's result.
- **The client-report lift** (§4 amendment): to be retired once a validation on the current
  respondent system is recorded.
- **ANL-1 for every other origin**, and D6, remain as they are.
