---
status: in-progress
chunks:
  - "[x] K0. Audit current client knowledge intake, payloads, decisions and consumers at 67af44e"
  - "[x] K1. Draft the client knowledge structure, intake and acceptance contracts for review"
  - "[ ] K2. Deliver document, dataset and web intake through one source-to-reviewed-knowledge journey"
  - "[ ] K3. Implement typed knowledge revisions and decisions against the reviewed base revision"
  - "[ ] K4. Resolve a study's selected, eligible client knowledge into an immutable context snapshot"
  - "[ ] K5. Define and materialize executable dimensions through the existing population authority"
  - "[ ] K6. Implement correction, retirement, conflicts and dependent-study change visibility"
  - "[ ] K7. Prove all four consumers and reconcile the shared documentation after landing"
---
# Client knowledge that studies can use correctly

**Owner:** client knowledge / data-library product integration. **Started:** 2026-10-08.
**Baseline:** develop `67af44e5b9431d6293347b581fde7a34b95ed44c`.

User direction: rethink and improve the types of knowledge bases created for clients,
their structure, input methods and approval methods. This proposal supplies the missing
product and semantic contract. The user authorized publishing this proposal as a draft
on 2026-10-08; publication does not accept its product/methodology decisions or authorize
implementation, migration or deployment. The MVP still requires all four areas.

## Problem and observed evidence

The existing foundation has client scope, item identity, append-only revisions, proposals
and decisions. Those should be retained. But a category is not a contract for how an item
may be used.

Anchors below are at the baseline SHA:

| Current behavior | Evidence | Consequence |
| --- | --- | --- |
| Every knowledge kind shares a generic content/provenance dictionary | `domain/knowledge.py:121-182`; `routers/workspace.py:385-405` | SOURCE, FACT, DIMENSION and DATASET have no distinct, required payload semantics here |
| The client intake form sends kind, title and summary | `KnowledgeArea.tsx:127-161` | Choosing DOCUMENT does not upload its bytes; choosing DIMENSION does not define its measure |
| Review cards show title, summary, origin study and decision buttons | `KnowledgeArea.tsx:85-117` | A reviewer does not inspect the source span, payload, exact revision diff or intended computational use in this view |
| Client dimension catalogue takes item id and title | `apps/web/src/research/persona.ts:52-61` | An accepted dimension label can appear without an executable definition or values |
| Client additions are immediately accepted by default; study proposals wait | `workspace.py:825-837`; `client_knowledge_repository.py:395-441` | Preserve ADR 0019: distinguish the person's declaration from a system-generated extraction; do not introduce mandatory approval by another person |
| New study retrieval selects active client items | `client_knowledge_repository.py:125-180` | Content availability alone is not an explicit relevance, freshness and permitted-use decision |
| Pending edits store item identity but no reviewed base revision | `client_knowledge_repository.py:250-296, 353-387, 516-527` | An earlier proposal can replace a newer correction when accepted later (F-K1) |

Two disposable audit reproductions passed against the baseline, using existing fictional
core fixtures and SQLite. They assert observed gaps, not the desired behavior:
`test_a_pending_edit_can_replace_a_newer_accepted_correction` and
`test_a_dimension_can_be_accepted_with_no_definition_or_values`.
Probe and sanitized JUnit are published in `.planning/evidence/client-knowledge-review/`.
No production file or existing test was changed by the audit. PostgreSQL concurrency and
deployed behavior were not tested.

## Product structure — one client workspace, several views

The proposed client workspace answers: what do we know, where did it come from, when does
it apply, what can it be used for, and what changed? It is not a collection of independent
knowledge engines. Organize the same versioned items into these user-facing views:

| View | Typical contents | Default use |
| --- | --- | --- |
| Client context | Organization, products/services, terminology, business constraints, objectives | Design and briefing context; a goal is not an observed fact |
| Sources | Uploaded documents, presentations, notes, captured pages and imported data | Originals and extraction evidence; storage is not acceptance of every statement |
| Market and customer knowledge | Competitors, customer needs, qualitative themes, audience descriptions | Cited context with population, geography and time scope |
| Data and measures | Datasets, variable definitions, instruments and materialized dimension versions | Computation only after applicable validation and eligibility checks |
| Findings | Accepted observations, research findings, modelled findings and explicit hypotheses | Preserve the evidence category; acceptance never changes synthetic evidence to measurement |
| Decisions and assumptions | Chosen actions, scenario assumptions and why they were chosen | Inputs to design/scenarios, distinguished from empirical findings |
| History and use | Superseded revisions, studies that consumed them, saved outputs and decisions | Project memory and impact review; originals remain reconstructible |

Views may overlap and filter by topic, entity, study and time. They do not create copies.
Keep shared platform intelligence, this client's knowledge and a study's frozen context
separate as ADR 0015 requires. Organization-wide access is not permission to automatically
copy one client's findings into another client's context. No silent shared publication.

## Typed knowledge and relationships

Reuse existing ids, scopes, repository authority and revision history. Define versioned
payloads incrementally inside the existing knowledge subsystem, rather than building a
parallel graph/vector database or using free-form JSON as an executable contract.

| Record | Required meaning |
| --- | --- |
| Source revision | Immutable original/capture, byte hash, capture/import time, source publication date when known, origin and existing data classification; storage and extraction references |
| Evidence reference | Exact source revision plus page/section/quote or sheet/cell/row locator; preserve the span used by extraction and its interpretation limits |
| Knowledge assertion | Statement, assertion class, supporting/contradicting evidence, subject/entities, applicable geography/population/time, author/derivation; distinguish observation, person-declared claim, hypothesis and modelled result |
| Dataset revision | Data artifact, schema, row/field identities, source lineage, units/codes, missingness and quality results; respondent weighting and joint-claim constraints where applicable |
| Dimension definition | Stable id and version, construct, unit/scale/categories, valid range, missingness, operational definition, source variables/derivation, permitted roles and validation status |
| Dimension materialization | Definition version plus actual values, compatible population binding, coverage, donor/weight lineage and validation evidence; a definition alone has no respondent values |
| Audience definition | Versioned predicates over eligible, versioned fields; resolve eligible counts before use; description and executable predicate are distinct |
| Reusable artifact | Existing artifact id/hash and producing run, evidence/method/population identities, accepted reuse purposes and limitations |
| Decision/assumption | What was chosen or hypothesized, rationale, owner, applicable scope/time and related evidence; never disguise a decision as a measurement |

Relationship types include supported-by, contradicts, derived-from, defines, materialized-as,
supersedes and consumed-by. Use exact revisions, not a pointer to whichever item is current.
Existing artifact dependencies, knowledge revisions and admission policies remain their
authorities; typed relationships must bridge them rather than duplicate their decisions.

Keep three questions separate: processing succeeded; a person accepted this interpretation;
the intended use is eligible. Avoid one universal APPROVED flag implying all three. Formal
eligibility stays with the existing population/evidence rules, not with a knowledge UI.

## Input methods and one consistent intake journey

Proposed minimum input families: direct writing/pasting; supported document upload; URL capture
and Deep Research import; tabular dataset import; reuse from an existing study/artifact.
Format support must be explicit. An unsupported file or acquisition route has a named outcome;
it must not quietly produce a title-only knowledge card.

**User confirmation, 2026-10-08: all three families are integral.** Document/presentation/note
intake, spreadsheet/survey/dataset intake and URL/external-research intake are all required
in this design and its acceptance; there is no documents-only acceptance milestone counted
as completion. Specify concrete supported formats before implementation, and treat parser,
dataset mapping and web acquisition as bounded adapters to the same journey:

1. Select client and add material. Show what was stored, its origin and processing state.
2. Persist the original/capture as an immutable source revision. Deduplicate by content identity
   within scope while retaining import occurrence metadata. Never claim a successful parse
   when only upload succeeded. Follow the existing attachment, retrieval and paid-call boundaries.
3. Extract readable content or a schema preview with stable locators. Report partial extraction,
   unreadable pages, missing columns and unsupported formats. Preserve originals.
4. Propose knowledge: assertions, terms/entities, findings or dataset mappings. System output
   stays a proposal, even if triggered by a person clicking Upload.
5. Review exact proposals beside their evidence and intended uses. Accept selected items, edit
   explicitly, reject, or leave pending. Detect duplicate/conflicting assertions without silently
   picking a winner. A batch accept names the exact displayed proposal ids and versions.
6. Show accepted items, remaining gaps and where each item can be used. Each later stage has
   its own applicable validation; source acceptance never automatically creates population values.

Direct human-authored context follows ADR 0019 and can be saved immediately, labelled as the
person's declaration. Storing a pasted assertion does not certify that it was measured.
Human editing of a system-generated proposal records the derivation and the explicit accept;
it does not erase the original proposal/evidence.

## Acceptance actions and review interface

| Action | What the person is deciding | What does not follow automatically |
| --- | --- | --- |
| Add source / save authored context | Store material or record the person's statement | Truth of every sentence, AI transmission eligibility or computational usability |
| Accept extracted knowledge | Accept the displayed interpretation and scope for client context | Measured evidence, executable dimension, population promotion or deliverable approval |
| Validate a data mapping / dimension | Confirm definition and processing; existing domain checks determine eligible roles | Invented respondent values or permission for every statistical claim |
| Use in this study | Select exact eligible revisions for a declared purpose | Changing a completed run or accepting all future client knowledge |
| Promote a population revision | Explicitly select the validated new revision through PopulationAuthority | Promotion when a dimension is selected |
| Release a deliverable | Existing client-facing deliverable contract and release gate, once implemented | Knowledge acceptance substituting for report release |

Do not add extra Reviewer/Lead roles or mandatory peer approval: ADR 0019's two roles and
persisted independent-review override remain. A person's permission to accept and an item's
eligibility for a scientific use are separate decisions.

Each proposal review shows the source excerpt/data preview, proposed payload, scope/time,
origin (person / extraction / study / modelled result), supporting and conflicting sources,
current-versus-proposed diff, reviewed base revision and the requested use. Buttons describe
the action: Save context, Accept selected findings, Define measure, Use in study. Avoid an
unqualified Approve label that could mean all of these things.

## Consumption across the four MVP areas

**Research:** freeze a selected context manifest with item revisions, evidence hashes, use
roles and eligibility decisions at enqueue. Trace where context reached the actual request.
Missing materialization must remain explicit; no fictional roster substitution.

**Sociomapping:** consume declared ratings and eligible materialized descriptors through the
existing study-input contract. Context prose is not a numeric coordinate, rating or respondent
value. This plan supplies I0/I1/I3 in sociomap-formula-corrections, and changes no canonical math.

**Simulation:** bind an approved scenario and world model to eligible definition/value versions
and the existing population runtime. Specify units, bounds and allowed shifts before connecting
free-form scenarios to computation. PanelSchema currently names numeric/categorical fields but
not ranges (`domain/simulation/world_model.py:65-95`); scenario.py explicitly records that ranges
are unavailable (`:20-23`). Do not silently clip or invent a new methodology.

**Project memory:** retrieve accepted reusable items with original scope, source, method and
evidence category. Reuse proposes exact revisions for a new study and requires explicit accept.
Synthetic/modelled findings cannot return as independent measured evidence in their descendants.
Enforce the existing Deep Research leakage and evidence discipline rather than bypassing them.

## Corrections and lifecycle

An edit appends a revision. A proposal revising an item records the exact base revision/hash;
accept checks it atomically. If the item changed, return a conflict and show a rebase/diff before
accepting again. Approval must never silently replace a newer correction (F-K1).

Distinguish superseded, disputed, retired and unavailable-for-new-use knowledge from physical
deletion. Record why and who changed its availability. Current searches/selection stop offering
ineligible revisions; a frozen historical run keeps its consumed snapshot and a visible status
notice where appropriate. Do not retroactively rewrite an approved report or simulation.

Show dependent studies/artifacts and which are historical, in progress or candidates for reuse.
Propose new work when changed knowledge matters; do not automatically trigger paid reruns.
Distinguish a source correction from changing an interpretation, dimension definition or view.
Deletion/retention follows existing artifact and client-data policy, with explicit dispositions
for originals still referenced by historical outputs; no invented blanket forever-retention.

## Implementation slices and proof

K2 delivers the source-backed intake/review product path for each of the three required input
families, including document/presentation/note extraction, tabular schema/mapping preview, and
captured web/Deep Research evidence. Individual adapters may land in bounded implementation
slices, but K2 is not complete until all three paths pass connected acceptance.
K3 adds typed revisions and stale-decision checks to that path; its final typed contracts must
be written before implementation. These slices may be assembled together if their contracts
require it. Keep parsing/extraction in the worker, rules in domain/application and UI rendering.

K4 extends existing research context freezing instead of introducing a second context loader.
K5 owns knowledge-to-dimension definitions/materialization, delegates population loading and
promotion to existing authority, and coordinates feature-plan I0/I1/I3. K6 proves corrections
and reuse decisions. K7 consumes the four-area journey in mvp-workflow-assurance A4 rather than
inventing another release gate. Each bounded slice uses existing storage, jobs and provenance.

Required connected acceptance fixture: add fictional client documents/notes, a small dataset
and captured web/Deep Research sources; extract source-backed proposals from all three input
families; accept selected knowledge; define/validate a dimension; use
its eligible values in a frozen study; produce stored map/analysis artifacts; reuse an accepted
finding in a new study and run a scenario over the same bound baseline. Correct one source,
then show affected consumers while preserving the original results. The all-four path is a
future acceptance requirement, not code claimed to exist today.

Required failure cases include partial parse, duplicate source, contradictory findings, unknown
dimension definition, missing values, unavailable extraction runtime, wrong-client source,
stale proposal acceptance, retired source, synthetic-evidence reuse and interrupted processing.
Observe actual context reaching fieldwork; do not prove wiring merely by changing a hash.
Browser/API/worker/PostgreSQL/store acceptance and bounded deployment remain separate evidence.

No vector service or additional agent framework is selected by this plan. Start with typed
records, locators and scoped retrieval over existing infrastructure; add indexing only when a
representative retrieval task demonstrates the need. Migration must preserve existing ids and
generic historical records without inventing source spans or validated dimensions for them.

## Findings

**F-K1 — A pending item revision can replace a newer accepted correction.**
1. Claim: approval does not test whether the item changed after the proposal was created.
2. Anchor: `client_knowledge_repository.py:250-296, 353-387, 516-527 @ 67af44e`; ProposalCreate
   and DecisionRequest in `routers/workspace.py:385-405` carry no reviewed base revision.
3. Reproduction: create a FACT at revision 1; queue a study proposal editing it; save a newer
   human correction at revision 2; approve the earlier proposal. It succeeds at revision 3 and
   the earlier text becomes current. The two earlier revisions remain in history.
4. Consequence: a validly authorized acceptance can unintentionally undo a newer correction;
   revision history alone does not provide conflict protection.
5. Smallest fix: pin base revision/hash on a revising proposal and compare under the existing
   item lock before changing current content; return a named stale-proposal conflict.
6. Test: disposable `test_a_pending_edit_can_replace_a_newer_accepted_correction` reproduces
   current behavior. Implementation must add an ordinary regression expecting refusal and a
   separate explicit rebase/accept case, with a PostgreSQL contention case where required.

**F-K2 — Knowledge classification is being used as a dimension catalogue entry.**
1. Claim: a title-only DIMENSION can be accepted and offered as a selectable client dimension.
2. Anchor: `KnowledgeArea.tsx:127-161`, `domain/knowledge.py:121-138`, `clientDimensions` in
   `apps/web/src/research/persona.ts:52-61 @ 67af44e`.
3. Reproduction: add DIMENSION with title only; study retrieval returns it with empty content;
   the catalogue adapter exposes every DIMENSION by item id and title.
4. Consequence: the UI can suggest a usable measure without a definition or materialization.
   Fieldwork currently declares selection unapplied, so this is not a claim of silent numeric use.
5. Smallest fix: separate dimension definition from materialization/use eligibility; display
   draft/non-executable definitions honestly and allow computational selection only when resolved.
6. Test: disposable `test_a_dimension_can_be_accepted_with_no_definition_or_values` pins the
   current behavior; connected acceptance must refuse execution with an unresolved definition.

## Doc follow-up

After each slice lands, update CLAUDE's knowledge modules/routes and input/review surfaces;
ARCHITECTURE's knowledge consumption and revision-conflict boundary; client-first/data-model/
artifact documentation where the implemented contracts change; open-items with F-K1/F-K2 and
their actual dispositions. Record exact edits in each PR; no shared file is edited here.
Reconcile old MVP-ACCEPT-1 and its machine-readable criteria with the owner's all-four scope
and ADR 0019, preserving existing checks rather than dropping inconvenient requirements.
Do not mark this plan's proposal as an approved product decision in those documents.

## Decisions still open

- Concrete supported formats within all three required input families. Their inclusion is
  confirmed by the user; the remaining question is format support, not whether to defer a family.
- Representative client/study example for review of the proposed structure and use roles.
- Where individual dimensions may be materialized, with licensed/data/methodology restrictions
  resolved through their existing owners rather than by a generic knowledge accept.
- Correction and retirement user wording and the exact dependent-study notice contract.
- Scientific eligibility remains with canonical methodology and current evidence contracts;
  accepting this product structure cannot approve a new scientific rule.

## Review outcome

Draft prepared for authorized publication with code anchors and two reproduced gaps.
The publication base is develop `4d8f07d934e88a9d15b9da47c78c42a1b01ca019` (PR 194's
documentation follow-up); the audited runtime code remains the baseline above.
No production redesign, migration, independent review or client acceptance has occurred.
