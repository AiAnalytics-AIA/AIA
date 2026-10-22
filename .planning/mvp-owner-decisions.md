# MVP owner decision packet

2026-10-20. MVPQ-01, MVPQ-02, MVPQ-04, MVPQ-07, MVPQ-08 and MVPQ-11 are SETTLED by the product owner below. MVPQ-03, MVPQ-05, MVPQ-06 and MVPQ-09 have their product-owner parts ANSWERED; their methodology or quality parts, and MVPQ-10 and MVPQ-12, remain OPEN until the named owner answers. The coding feature's scope is settled; its methodology specification and admission rules still require the methodology owner's approval. A session,
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
Workbench 15 and 17–22 follow V2; MP12 still checks and records any necessary differences
from the existing domain decisions. This question is answered, not an implementation
completion. Do not ask it again.

## MVPQ-02 — Assumptions and open-answer coding: SETTLED, 2026-10-20

**Product owner answer:** “Both.” Tracked assumptions and qualitative coding of open
answers are required at first release. This closes the feature-scope question; do
not offer either as optional/post-MVP or re-ask whether it is included.

**Required planning/implementation:** assumptions are stable, editable, traceable
items with status, supporting evidence and human-approved updates, connected to
the design/coverage/Lead context and working-copy vocabulary. Coding has a real
producer: stored, versioned per-answer assignments over the frozen run's open
answers, with deterministic theme counts and traceable examples. Connect the
result to Analysis, Report, claim admission and exact input fingerprints. A
prototype panel or generated prose is not a coded result.

**MVPQ-02b — OPEN coding-method prerequisite:** the codebook/rules, permitted labels
and multi-label semantics, denominator/missing-answer treatment, review/acceptance
and scientific admission. Approval of the feature does not choose those rules.
Answer-ready form: [`mvp-methodology-packet.md`](mvp-methodology-packet.md) MQ-14.
Name this methodology-owner prerequisite as MVPQ-02b in the coding chunk and gate;
do not reopen the settled scope. Deterministic counts are computed from the same
frozen reviewed per-answer assignment artifact and its version, dataset and codebook;
a model or a human recoding the same text may legitimately produce different
assignments. Changed assignments invalidate dependent counts/analysis/report,
while the original answers remain frozen. If this creates an additional worker/prompt, update the
registry, price/pins, harness and acceptance statements explicitly alongside the
eleven baseline workers. Stable ids and unrelated manual editing can proceed.

The researcher's private return summary remains existing LO7 work; it is not
removed or made conditional on the new assumptions feature.

## MVPQ-03 — What defines a segment and what may drill-down expose?: PRODUCT PART ANSWERED, 2026-10-20

Answer-ready form: [`mvp-methodology-packet.md`](mvp-methodology-packet.md) MQ-02, MQ-03 and MQ-11 – MQ-13.

**Product owner answer:** defined segments start from the sampler's stored descriptors
(the recommendation below); the internal drill-down shows **stored attributes and answers
only**, never the generated persona profile prose. **Still open (methodology owner):** the
permitted combinations, minimum support and suppression, how accepted own dimensions take
part, the clustering method and its register approval. The methodology owner's open PR #504
(`aia-sociomap-5`, `.planning/plans/signed-off-sociomap-method.md` on its branch) already
carries a respondent map and clustered taste segments; `segment-maps-and-drilldown` and
`sociomap-formula-corrections#3` are not yet reconciled with it.


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

## MVPQ-04 — No supported finding: SETTLED, 2026-10-20

**Product owner answer:** “Block the report until resolved.” If an analysis module
has no supported finding, report composition/approval/export stays blocked until
that gap is resolved under the actual evidence/method contract. A structured
“no finding, reason and coverage gap” is useful diagnostic output and cannot
satisfy the gate. Do not invent a finding, admit unsupported prose, silently drop
a required module or count an unavailable module as complete to unblock a report.

Apply this to evidence-integrity 1, its module completion contract, the report
composer/delivery gates and the acceptance harness/MD/JSON together. The existing
all-eight-modules rule remains; this answer is not permission to bypass it with a
coverage note. Preserve same-data analysis retry and frozen numeric outputs. No
implementation checkbox is completed by this answer.

## MVPQ-05 — Client-data evidence policy: PRODUCT PART ANSWERED, 2026-10-20

Answer-ready form: [`mvp-methodology-packet.md`](mvp-methodology-packet.md) MQ-16 – MQ-18.

**Product owner answer:** the human-accepted data contract **alone** compiles into the
dataset's evidence policy: a column the contract names used and not personal is admissible
as client-reported, with no AIA-maintained field list in between. The visible label is
**"z dat klienta"** beside each client number; the source and the period are disclosed once
(a footnote or the methods chapter), not on every line. **Still open (methodology owner):**
the benchmark interval when supports differ, and whether a client survey may ever ground AI
respondents.


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

## MVPQ-06 — Required reach, evaluation quality and allowance: PRODUCT PART ANSWERED, 2026-10-20

**Product owner answer:** Common Crawl stays required for I-R. The product owner owns
evaluations 25, 26 and 39 and their thresholds. Their allowance is **USD 50**, separate from
the USD 25 representative tier-B study, with costs estimated from the configured ceilings
before any paid run. **Still open:** the representative tasks, metrics and measured
thresholds themselves. No paid work is authorized by recording this.


**Product owner plus research-quality owner.** Evaluation thresholds and allowance
still need answers; the required reach is recorded alongside them:

- Common Crawl remains required for I-R under the recorded scope; this does not
  need reconfirmation. Removing or delaying it would require an explicit owner
  override, not a successful smoke or an engineering scheduling choice.
- Who owns evaluations 25/26/39, which representative tasks/metrics are required,
  and what measured thresholds must pass before final live run 27?
- What is the approved evaluation/comparison allowance, separately from the USD 25
  representative tier-B study? No paid work is authorized by this packet.

**Recommendation:** preserve broad reach and the current archive requirement;
decide thresholds on the recorded evaluation protocol, with costs estimated from
the configured ceilings before an allowance is chosen. Blocks final research
evaluation/live gates; independent implementation and zero-cost tests can continue.
Keep n=300 and USD25 acceptance inputs until the owner explicitly changes them.

## MVPQ-07 — Residual deletion retention and accounting facts: SETTLED, 2026-10-20

**Product owner answer:** after a person deletes a client or study, its content may remain
in backups and object versions for **at most 30 days** (RDS's 14-day recovery window lies
inside that), and a durable deletion journal is replayed after any restore before traffic is
served. **Content-free usage and audit rows** (date, model, tokens, USD, ids; no text, no
client name) are kept so spend still reconciles, readable by an organisation OWNER or ADMIN
only.


**Product owner/data owner.** After a person deletes a client/study, state the
maximum residual lifetime in backups and object versions. Which non-content
usage/audit facts may remain so spend still reconciles? Who may read them?

**Recommendation:** approve explicit horizons rather than inheriting 14/30-day
infrastructure defaults. The engineering invariant is that a restore replays a
durable deletion journal before serving traffic; deleted content must not reappear.
Blocks SDL0, deletion FK M12, destructive lifecycle configuration and final release.
Schema/inventory/runbook proposals and disposable-data test design can continue.

## MVPQ-08 — Client Knowledge extraction outside a study: SETTLED, 2026-10-20

**Product owner answer:** yes. Source extraction stays a client-level job in Client
Knowledge, under its client budget, approval, isolation and audit, recorded as an explicit
exception to AC-02.


**Product owner.** Confirm the scope exception: source extraction can remain a
client-level job in Client Knowledge, charged to its client budget, while study-stage
AI starts use the Lead's approved authority path.

**Recommendation:** retain the existing client-level workflow with its own approval,
budget, isolation and audit; do not create a fake study. Blocks LO13's final acceptance
wording and K8's paid-source entry semantics; it does not grant arbitrary study starts.

## MVPQ-09 — Exact report evidence and source-use checks: PRODUCT PART ANSWERED, 2026-10-20

Answer-ready form: [`mvp-methodology-packet.md`](mvp-methodology-packet.md) MQ-19 and MQ-20.

**Product owner answer:** a **minimal deterministic gate** before a client deliverable can be
approved, not the full enumerated audit: no source marked "Interní dokument", no drill-down
content, and no number without an admitted claim. There is **no separate legal-rights review
step** in the MVP; the reviewer approves the exact version (F17, unchanged). An unsupported
qualitative or comparison claim (RD7) **blocks approval**, and the refusal names the
sentence. AC-13's wording ("evidence audit and the legal source-use gate") changes to this
gate. **Still open (methodology owner):** any scientific check beyond admitted support.


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

Answer-ready form: [`mvp-methodology-packet.md`](mvp-methodology-packet.md) MQ-15.

**Methodology owner.** For the settled feature “replace as a new linked run,”
specify redraw/exclusion, retained-respondent answer reuse, weight recalibration,
effective n, support/quotas and conditions that refuse replacement. How is the
replacement rule pinned and reported so the two runs can be compared honestly?

**Recommendation:** preserve the original run and paid answers of unchanged
respondents; do not silently renormalize weights or approve a numerical replacement
policy. Blocks RQC5's executable replacement behavior and its ADR; lineage/storage
and refusal contracts can be prepared. This does not reopen whether replacement is MVP.

## MVPQ-11 — Narrow-screen Lead access: SETTLED, 2026-10-20

**Product owner answer:** “Keep the Lead accessible through a compact drawer or
stacked layout.” Workbench 26 must retain usable Lead access on narrow screens;
implementation may choose a compact drawer or stacked view consistent with the
canonical V2 workspace. This supersedes the recommendation to remove study AI
below 1100 px and does not authorize fallback manual AI-start buttons.

Every supported study layout uses the same revision-bound human authority,
approved-plan, budget/wallet and LO15 server-confirmation paths. The responsive
container does not add authority, weaken privacy or alter deterministic results.
Test 1099/1100 px, smaller supported widths, keyboard/focus/Escape and return to
the targeted artifact, stale cards and direct HTTP starts. On switch-off/rollback,
make actual availability explicit; retain compact Lead access when its backend
is enabled, and keep a genuinely disabled backend disabled. Do not bypass a kill
switch or restore alternate AI starts to disguise unavailable Lead execution.

This settles the product behavior; the exact responsive composition is an
engineering/design choice, not another owner question. The separately open
client-level extraction exception is still MVPQ-08.

**2026-10-21, the owner's answers Q40-Q43** (on the PM status page, relayed by the coordinator;
plan `research-lead-workbench` D21, D22, #551). The narrow-screen Lead is a side drawer at
768-1099 px and a full-screen sheet under 768 px, one element tree (chunks 26a-26f). Q41: the classic
study frame and `AIA_WEB_RESEARCH_WORKBENCH` are retired (27c). Q42: a card approved after the Lead is
switched off is refused, 409 `research_lead_disabled`; stored text edits can still be accepted or
dismissed (27b). Q43: with the Lead off, LO5's typed start commands still work, matched by code
(27a, 27b). The research run keeps Spuštění's own Start button and also appears as a card in the
Lead's chat ("i want this to appear in the lead researches chat too"; D15, 26f). Q40: spend is shown
per researcher (`develop-spend-attribution#7`), delivered by #583 (merged as `e78dfa8b`, 2026-10-21):
Settings → Studie a rozpočty "Útrata podle výzkumníka", every member for OWNER/ADMIN, a researcher
their own; a charge booked to the budget lifter, else the one start approver, else the starter,
else nobody, never a guess (Q67 (a) below; OI-193, OI-194).

**2026-10-21, the owner's answers Q50, Q52, Q54, Q56 and Q58** (on the PM status page, relayed by the
coordinator; the artifact plans, #560). Q50 (b): in the `-5` drawing only the two state issues are
fixed: a selection carries over between Objekty and Respondenti, and full screen with Top vztahy
shows only the selected object's links. The camera snap (whether the 2D view keeps the 3D rotation)
and the dropped or overlapping labels go to the methodology owner (A. Bahbouh). Q52 (a): Výsledky shows up to five example raw
open answers per question, internal only, labelled as data and not admitted evidence, never
exported. Q54 (b): the persona source is chosen on Spuštění and read-only on Vzorek. Q56 (b): the
report narrative's first draft is written by code, then the Lead proposes tracked changes. Q58 (b):
**one document**, "The literature should be woven into the body of the report": literature stays
labelled as external sources (L), never respondent evidence (ADR 0021 unchanged in substance), and
the separate report with literature is retired for new reports; stored ones stay downloadable. This
may need a note in ADR 0021 and `contextual_report.py`'s description. Q57 was MVPQ-04 already (no new
decision). Q51, Q53 and Q55 were answered later (below).

**2026-10-21 14:40 UTC, the owner's answer Q59 (a)** (relayed by the coordinator): "The lead
researcher can see all the files in a client's knowledge base." Every Lead turn carries an index of
the study's client's knowledge: every item and source file, with its name, kind, status, folder and
summary. The Lead opens any file's text by id on demand; code fetches it, scoped to that client, and
the Lead cites it by locator. Pending proposals are marked unapproved, sources marked "Interní
dokument" are included and marked, and rejected items are left out. The plan,
`lead-client-knowledge.md`, comes in its own PR.

**2026-10-21, the owner's answers Q60-Q65** (on the PM status page, relayed by the coordinator).
Q60 (a), 14:51 UTC, as data owner: client knowledge in the lineage `unclassified-client-knowledge` is
licensed for `bedrock-eu-primary` only, beside the panel's OI-61 rule (`lead-client-knowledge#LK0`,
its own fix PR); it ends the refusal of every Lead turn for a client with an approved dataset,
artifact or finding (OI-142). Q61 (b), against the coordinator's recommendation: folder and label
names never reach a model; the Lead's index carries item names and kinds only. Q62 (a): a dataset
the Lead opens is read as its preview only, personal columns masked, never its rows (LK5). Q63 (a),
15:15: the nine typed start commands in #574 stay as proposed. Q64 (a), 15:17: Claude reviews stand
in for Codex until its credits reset (17:42 Prague time). Q65 (a), 15:18: brief attachments stay
Class B, shown for awareness; "i dont want any gates stopping based on the classification, we are
going for full functionality right now." Q66 (a), 15:20 UTC: **on develop only**, data classes are
shown and recorded but never block; EU residency and the licence determinations still hold. The
owner's note, "dont limit the brave search capabilities either": on develop, Brave may receive search
queries of any class, the one stated exception to EU residency, and for search queries only. In the
coordinator's session at about 15:22 UTC he said "build the develop-only class-advisory switch,
including Brave for any class"; the PR is `feature/develop-class-advisory`. Production keeps the
class rules (ADR 0008, ADR 0032 §4). Q67, who pays after a budget lift, is open. The read round inside a Lead turn (ADR 0042, Proposed) is
the coordinator's decision within Q59; the experimental Sociomapping draft is named only in CHN1's
section manifest (the coordinator, #579). Q51, Q53, Q55 and Q67 are answered below.

**2026-10-21, the owner's answers Q51, Q53, Q55 and Q67** (on the PM status page, relayed by the
coordinator with their stored wording). Q51 "Tracked sets: allow a word on every scale point?", (b),
14:32: "Keep sets to two end words until 3b3 (Aram's wording rule)"; #559 gives a single scale
question a word on every point, and a set stays two-ended because the server reads a set's first two
labels as its ends (`SpecBattery.told_ends`, OI-184). Q53 "Dotazník: who sets the questionnaire
length limit?", (a), 20:16: "A declared rule per study type, set by Aram on Metodika". Q55 "What
sections does the MVP draft report have?", (b), 14:33: "Today's report with gaps closed, plus
RD9/RD10, plus literature when chosen, in today's order", with his note "ensure we are not missing
anything". Q67 "Per-researcher spend: who pays after a budget lift?", (a), 20:12: "Whoever lifts the
budget pays for what runs after the lift" (built in #583). Still open on the PM status page: Q68
(comments on Návrh; the coordinator recommends (b)) and Q69 (the Lead's study notes in the draft
report; the coordinator recommends (a), left out).

## MVPQ-12 — Canonical Sociomap questions still requiring sign-off

Answer-ready form: [`mvp-methodology-packet.md`](mvp-methodology-packet.md) MQ-04 – MQ-10; under MVPQ-13 (below) `aia-sociomap-5` settles Q5-Q7, the kernel widths and respondent placement (the packet's MQ-05 record), and only what `-5` leaves open is asked.

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

## MVPQ-13 — The MVP ships `aia-sociomap-5`: SETTLED, 2026-10-20

**Product owner answer** (Nigel Blount, 2026-10-20, relayed by the coordinator): the MVP's Sociomap
is the methodology owner's signed-off `aia-sociomap-5` (#504), not `aia-sociomap-3`. **One canonical
source:** where `-5` decides a point, its answer is the MVP's; the formula audit written for `-3`
(`sociomap-formula-corrections`) stands only where `-5` is silent, and the methodology owner is never
asked to re-confirm his own method. **The hybrid is rejected** (`-3` object maps with `-5` respondent
and segment maps): `-5` places respondents and finds segments against its own object positions, so
`-5` respondents on a `-3` map would sit on a map they were not placed on. Runs that pinned `-3` keep
it and its approval. What `-5` needs before a map reaches a client (the register entry, MQ-01) and
everything else it leaves open are in [`mvp-methodology-packet.md`](mvp-methodology-packet.md)
(#510); D-13 and ADR 0038 carry it as the only method of new runs.

## From the cross-check: X1, X8, X10: SETTLED, 2026-10-20

**Product owner answers** (recorded in `mvp-cohesion.md`, master plan G48, G53, G55): build segment
evidence (`segment-maps-and-drilldown#10`); build questionnaire routing end to end
(`working-copy-edit-ops#WCE13`, `run-qc-and-checkpoint#RQC11`, `evidence-integrity#10`); remove
Settings' draft-prompt test (`system-prompts-settings#14`). Not asked again.

## Operator facts are a separate checklist

Production hostname/callbacks, RDS sizing, quotas, model tiers/prices, Brave plan
and terms, retention evidence, secrets and measured Lead turn cost are not answered
by these product questions. MP6/MP7 and PE5 record the actual operator evidence;
unknown stays NOT_READY. No credential, provider sign-off, paid allowance or
deployment is implied by this document.


## Work that can begin while answers remain open

This is a planning handoff, not authorization for paid work, infrastructure changes
or release. The execution graph is the scheduling authority; engineering sequencing
within preserved scope is not another product question.

| Order | Independent work / predecessor | Concrete reviewable output |
|---|---|---|
| W0 E01 | No open owner decision | Acceptance collection/marker, shared recorded doubles and synchronized MD/JSON criteria; deliberately omitted coverage fails CI |
| W0 E02 | No open owner decision | Money/issued-authority and complete edit-vocabulary contracts, ledger subjects and negative fixtures; structural auto-accept remains off by default |
| W0 E03 | After E02 | LO9a worker rows; LO15 server start/rebuild confirmation check; spend-attribution 5a identity/invocation compatibility. Direct requests cannot evade confirmation |
| W0 E04 | After E01 | RQC9 single n authority, RQC10 HTTP population double and proposed client-material signature contract 8a; no client evidence admitted by attachment |
| W0 E05, no-call part | After E01 | Composition-readiness inventory and typed NOT_READY reasons; live probes still require actual operator readiness and approved allowance |

Next integration work consumes these contracts with recorded providers. A missing
methodology answer blocks only the affected numerical/admission behavior; a missing
budget blocks live calls. Unrelated contract, storage, UI and refusal preparation
continues. No elapsed session, expired question widget, draft PR or green test can
supply an unanswered owner/methodology decision. Record actual answers once using
MVPQ ids, update the affected child/acceptance contracts together, and retain every
other open item until its named owner answers.
