# MVP owner decision packet

2026-10-20. MVPQ-01 is SETTLED by the product owner below. The other questions remain OPEN until the named owner answers. A session,
question widget or usage limit ending is not an answer. Recommendations below
are proposals, not approvals. The master plan §11.4 is the index; the settled
decisions remain in §11.1 and the cohesion register.

Use ids MVPQ-01–MVPQ-12 when answering; subparts may be answered separately. Each answer
is recorded in the cohesion register with date, owner, affected chunks, ADR and
acceptance changes; then the master and every affected child are updated together.
If a newer recorded decision already answers an item, cite it and close the item
without asking again. Do not tick implementation because a decision is answered.

## MVPQ-01 — Canonical prototype: SETTLED, 2026-10-20

**Product owner decision:** “the one in the browser is the correct one,” after viewing
the V2 and V3 Questionnaire designs. The browser displayed the Czech **AIA Vedoucí výzkumu /
Research Lead V2** clickable build (`prototypes/research-lead-v2`, source baseline
`9b50963f`; supplied export *AIA Vedoucí výzkumu.html*).

**Disposition:** V2 is the canonical visual and interaction reference for the complete
workspace **and all eleven artifact bodies**. Retain its top stage navigator, Lead on the
left, artifact on the right, compact headers/state bars and contextual details.
V3 is supporting capability/design reference only; do not replace V2 layouts with V3
screens or import V3-only controls automatically. The earlier recommendation to use
V3 artifact bodies by default is superseded.

Existing explicit methodology, private-Lead, budget, approval and real-data decisions
still govern. Prototype mock text/data do not approve conflicting domain behavior.
Workbench 15 and 17–22 follow V2; M12 still checks and records any necessary differences
from the existing domain decisions. This question is answered, not an implementation
completion. Do not ask it again.

## MVPQ-02 — Are assumptions and open-answer coding new MVP features?

**Product owner, methodology owner for coding.** Please decide separately:

- Are tracked assumptions required as editable, traceable design items at first release?
- Is qualitative coding of open answers required at first release, or is displaying
  the stored open answers sufficient until a separately approved coding method exists?

**Recommendation:** a small explicit assumptions contract if required; treat coding
as an explicit scope/methodology decision, never infer it from a prototype panel.
The researcher's private return summary follows LO7's existing context/change-feed
work; it is not a request to drop that agreed behavior. Existing stable item ids
and the rest of WCE1 do not wait for a decision about adding an assumption item kind.
Blocks only those new item/processing contracts, not all manual editing.

## MVPQ-03 — What defines a segment and what may drill-down expose?

**Product owner plus methodology owner.** Name the permitted stored descriptors
and combinations; distinguish persona topics from real materialized variables.
How do accepted own dimensions participate? Confirm minimum support/suppression,
clustering method/parameters and method-register approval. Should internal drill-down
show only stored attributes/answers, or also generated profile prose, labelled modelled?

**Recommendation:** start from eligible sampler descriptors actually stored with
lineage, and make an own-dimension consumer explicit; do not invent support or
clustering thresholds. Blocks segment 0/0a/1–4 and affected Sociomap I0/I3;
type/storage proposals and explicit-unavailable UI can proceed. Drill-down remains
internal and never exported regardless of this answer.

## MVPQ-04 — What happens when a module finds no supported finding?

**Product owner, with evidence-policy review.** May a module return a structured
“no supported finding, reason and coverage gap” and let the report proceed,
or must that module block the report?

**Recommendation:** allow the explicit gap result, without an invented finding or
admitted claim. Every actual finding still needs admitted support. Blocks the
final evidence-integrity 1/composer behavior; validators and refusal tests can proceed.
This does not authorize an unsupported hypothesis to print as an accepted finding.

## MVPQ-05 — Client-data evidence policy

**Product owner and methodology owner.** Decide these parts of ADR 0027 together:

- Does the human-accepted data contract (use, unit, period, source/rights and named
  non-personal columns) compile into the policy for that dataset?
- Which benchmark interval/comparison is valid when client and modelled supports differ?
- May client survey answers ever ground AI respondents, or must they remain a separate
  comparison source? This requires the methodology owner's explicit rule.
- Confirm the visible client-reported label and required period/source disclosure.

**Recommendation:** policy per evidence source from its accepted contract; keep
client-reported and modelled results distinct. No guessed statistical rule or grounding
permission. Blocks client-data 0–9 runtime/admission and evidence-integrity 8's final
policy. Chunk 8a's proposed Brief/signature contract can proceed without admitting data.

## MVPQ-06 — Required reach, evaluation quality and allowance

**Product owner plus research-quality owner.** Three separate answers are needed:

- Does Common Crawl remain required for I-R? It is currently required. Removing or
  delaying it is an explicit change to the gate, not something a smoke can imply.
- Who owns evaluations 25/26/39, which representative tasks/metrics are required,
  and what measured thresholds must pass before final live run 27?
- What is the approved evaluation/comparison allowance, separately from the USD 25
  representative tier-B study? No paid work is authorized by this packet.

**Recommendation:** preserve broad reach and the current archive requirement;
decide thresholds on the recorded evaluation protocol, with costs estimated from
the configured ceilings before an allowance is chosen. Blocks final research
evaluation/live gates; independent implementation and zero-cost tests can continue.
Keep n=300 and USD25 acceptance inputs until the owner explicitly changes them.

## MVPQ-07 — Residual deletion retention and accounting facts

**Product owner/data owner.** After a person deletes a client/study, state the
maximum residual lifetime in backups and object versions. Which non-content
usage/audit facts may remain so spend still reconciles? Who may read them?

**Recommendation:** approve explicit horizons rather than inheriting 14/30-day
infrastructure defaults. The engineering invariant is that a restore replays a
durable deletion journal before serving traffic; deleted content must not reappear.
Blocks SDL0, deletion FK M12, destructive lifecycle configuration and final release.
Schema/inventory/runbook proposals and disposable-data test design can continue.

## MVPQ-08 — Client Knowledge extraction outside a study

**Product owner.** Confirm the scope exception: source extraction can remain a
client-level job in Client Knowledge, charged to its client budget, while study-stage
AI starts use the Lead's approved authority path.

**Recommendation:** retain the existing client-level workflow with its own approval,
budget, isolation and audit; do not create a fake study. Blocks LO13's final acceptance
wording and K8's paid-source entry semantics; it does not grant arbitrary study starts.

## MVPQ-09 — Exact report evidence and source-use checks

**Product owner/data owner, methodology owner for scientific checks.** Confirm the
enumerated checks behind “evidence audit” and “legal source-use gate”: admitted
support for every finding/number, traceable source/period/quote, permitted origin
and source use, licensed panel lineage, registered method/snapshot and no internal-only
or drill-down content. Which additional checks or refusal reasons are required?
Also state whether RD7's unsupported qualitative/comparison claim is a blocking
refusal or a flagged draft needing correction before approval.

**Recommendation:** make the checks deterministic where possible and explicitly
identify human review; a source-class check alone is not a legal-rights determination.
Report and snapshot approvals stay separate, and deliverables require approval of
their exact version before download (F17). Those are settled. Client PDF stays in
scope. Blocks RD0/RD1/RD3/RD7's final gate policy, not renderer/component preparation.

## MVPQ-10 — Replacement weights and support

**Methodology owner.** For the settled feature “replace as a new linked run,”
specify redraw/exclusion, retained-respondent answer reuse, weight recalibration,
effective n, support/quotas and conditions that refuse replacement. How is the
replacement rule pinned and reported so the two runs can be compared honestly?

**Recommendation:** preserve the original run and paid answers of unchanged
respondents; do not silently renormalize weights or approve a numerical replacement
policy. Blocks RQC5's executable replacement behavior and its ADR; lineage/storage
and refusal contracts can be prepared. This does not reopen whether replacement is MVP.

## MVPQ-11 — AI access in the narrow or switch-off layout

**Product owner.** Which layout rule should workbench 26 implement?

| Option | Behavior | Consequence |
|---|---|---|
| A, current recommendation in master | Remove manual AI starts everywhere; show why the Lead needs the wider workbench | Literal MVP-8; narrow/switch-off fallback loses study-stage AI |
| B, explicit exception | Fallback keeps manual starts with the same server confirmation/budget checks | Usable fallback but an exception to “every study AI action through the Lead” |
| C, proposed alternative | Retain Lead access as a compact drawer or stacked view and route every study AI start through it | Preserves authority and access; adds responsive design work and requires explicit agreement on fallback behavior |

No option removes the LO15 server check. Test 1099/1100 px, switch-off entry,
keyboard/focus and direct HTTP starts. Contract/confirmation work can proceed
while this layout choice is open; do not block LO15 on a viewport decision.

## MVPQ-12 — Canonical Sociomap questions still requiring sign-off

**Methodology owner/audit author, coordinated by product owner.** Use the existing
`sociomap-formula-corrections` §4/§4a decision sheets; do not create competing formulas.

- Q5: does proximity mean relative co-movement, absolute similarity, or geometry
  from co-movement with absolute level shown separately?
- Q6: approve the pairwise evidence policy: minimum support, raw versus effective n,
  uncertainty criterion and separate practical-effect threshold, including weights.
- Q7: approve the default terrain-height meaning and how alternatives are labelled.
- Specify fixed-ruler object/respondent kernel widths, F10 misfit threshold and
  F16/R-adapter disposition and validation expectations where still unresolved.

**Recommendation:** retain F1–F16 as the canonical baseline and identify provisional
parameters explicitly. Completed code/fixtures do not close an unresolved methodology
decision. Blocks 0b and the affected spec/map/report/client-approval behavior;
unaffected infrastructure/contracts can proceed. Engineering chooses how to meet
an approved R seam and measured tolerance, not a different scientific method.

## Operator facts are a separate checklist

Production hostname/callbacks, RDS sizing, quotas, model tiers/prices, Brave plan
and terms, retention evidence, secrets and measured Lead turn cost are not answered
by these product questions. M6/M7 and PE5 record the actual operator evidence;
unknown stays NOT_READY. No credential, provider sign-off, paid allowance or
deployment is implied by this document.
