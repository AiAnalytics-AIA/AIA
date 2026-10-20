---
status: planned
chunks:
  - "[ ] AOC0. The assumptions contract: the engineering fields, actors and human-review workflow of an assumption (a stable id, a statement, links, a status that may be UNTESTED, who may set each); an evidence-backed status takes its meaning from the existing evidence policy and the ADR of AOC2, with no new scientific method"
  - "[ ] AOC1. The assumption design item (W1): a kind in the shared edit vocabulary with a stable id, a statement, links to the research question or measure that tests it, a status and its evidence; UNTESTED tracking works at once; any status change is a person's accepted proposal; an evidence-backed status needs its support (AOC2)"
  - "[ ] AOC2. Assumption evidence from Deep Research (W2): the ADR and deterministic admission rule ADR 0026 decision 4 requires, then a Design Research proposal may attach cited findings to an assumption, accepted by a person, never changing a status itself"
  - "[ ] AOC3. Assumption consumers (W3): the Design artifact lists and edits them, the Lead's context carries them, the analysis payload carries them with their links as context, and the report states each with its status and its admitted or cited support"
  - "[ ] AOC4. The open-answer coding method (MVPQ-02b): the codebook and rules, who defines them, the unit and permitted labels per answer (multi-label semantics), versioning, the denominator and missing-answer treatment, review and acceptance, quality and agreement measures, support and suppression of small codes, what a model may do, and what is reproducible; the methodology owner writes it, the owner approves it"
  - "[ ] AOC5. Coding storage and determinism (W2): a per-answer classification artifact beside the dataset, versioned and frozen once reviewed (answer, code, codebook version, assignment version, who or what coded it, reviewer, an example link), a coding node in the run with an impact root so a codebook change reruns coding and analysis but never fieldwork, a pure counts function over one frozen assignment version, and retry that never replays paid classification"
  - "[ ] AOC6. Coding as admitted claims (W3): the counts enter results only through `admit_numeric_claims` with effective-n suppression and intervals, answer text sent to a model has a `MaterialRule` and lineage, and raw text is never called admitted evidence"
  - "[ ] AOC7. The coder, only if AOC4 lets a model propose codes (W3): one more worker row beyond the eleven (binding, price, editable and pinned prompt, accept destination = the coding review), its codes proposals a person reviews; if AOC4 says no model, this chunk is closed with that reason"
  - "[ ] AOC8. Coding consumers (W3): Results shows codes and counts per open question with support and suppression, a named analysis module takes the coded counts as input (or its contract is amended explicitly), and the report has a chapter for them"
  - "[ ] AOC9. The acceptance journey and its refusals (W5): an assumption tracked as UNTESTED, evidence attached, an evidence-backed status set by a person with its support and shown in the report; open answers coded, counts admitted, shown in Results and the report; an evidence-backed status without support refused, counts never produced from prose, a changed assignment legitimately changing counts under a new assignment version, a codebook change leaving fieldwork untouched"
---
# Tracked assumptions and open-answer coding

The owner decided on 2026-10-20 (`MVPQ-02`): **both tracked assumptions and open-answer coding are required at first release.** That is a decision about scope, not about method. Assumptions need an engineering contract and the existing evidence policy, not a new scientific method; **the coding method (how an answer is coded and counted) is the methodology owner's and stays open (`MVPQ-02b`)** until approved. Neither feature is a checkbox inferred from the V2 prototype's panels: each needs a producer, a stored form, a consumer in Analysis and Report, and a refusal path.

**Owner: S1** for the assumption item and its artifact (AOC1, AOC3), **S2** for evidence and coding (AOC0, AOC2, AOC4-AOC8), **S3** for the report chapters (`report-delivery#RD9`, `report-delivery#RD10`) and the journey (AOC9). Serves AC-03, AC-08, AC-13 and gates I-1, I-3, I-5. Every chunk below is **open**; a chunk is built from this file, not from the master plan.

## Decisions this plan carries (settled by the owner; not re-asked)

- Both features are in the first release (`MVPQ-02`, 2026-10-20).
- Status changes and any update to an assumption are human-approved: a model or a Deep Research run proposes, a person accepts (ADR 0026, gate 1).
- Deep Research evidence is external context, never respondent evidence (ADR 0021): it can sit beside an assumption as a cited source, it cannot by itself mark one supported.
- Counts of coded answers are numbers, so they reach a result only as admitted claims (CLAUDE.md, "Evidence is a capability").

## Facts the plan rests on

- The AI respondent already returns "a short open answer" and a dataset may hold open text (`domain/ai_respondent.py:8`, `domain/fieldwork.py:256`); the outlook treats an open-ended item as AT_RISK (`domain/question_outlook.py:154`). The producer of the raw answers exists; the coding is what is missing.
- ADR 0026 decision 4 lists open-answer coding and audience-assumption evidence among the prototype's four "proposed" capabilities and gives them no command until each has its own ADR and a deterministic admission rule. The ADRs of AOC2 and AOC4 are therefore the first step of each, not a late chore (`mvp-master-plan.md` MP5).
- A design item has a stable id only after `working-copy-edit-ops#WCE1`; the vocabulary is `working-copy-edit-ops#WCE0`. AOC1 extends both and does not wait on a decision about the kind itself, only on the status values.

## Chunks

**AOC0. The assumptions contract**  
Engineering, not a new scientific method: the fields of an assumption (a stable id, a statement, links to a research question or measure, a status, evidence); the actors (any member proposes, a person with the accept permission decides); the human-review workflow; the statuses, including an explicit **UNTESTED** (and unverified) that needs no support, because tracking what is not yet known is the core use. Only an evidence-backed assertion (supported or contradicted) needs support, and what counts is already fixed by the evidence policy: admitted claims for respondent evidence, cited Deep Research findings as external context, never respondent evidence. The ADR of AOC2 records the admission rule for attaching evidence. This is not an owner or methodology question; no status is ever derived by code from prose.

**AOC1. The assumption design item (W1)**  
A kind in `domain/design_items.py` and the edit vocabulary (`working-copy-edit-ops#WCE0`): `assumption_add`, `assumption_edit`, `assumption_link`, `assumption_set_status`, each a proposal accepted by a person through the shared per-change accept (`WCE6`); the statement's text edit is a text edit, a status change is structural and never automatic unless a stage's structural auto-accept is on (`WCE11`). Readiness lists UNTESTED assumptions as a warning. UNTESTED tracking and the id, statement, links and human-review workflow need no ADR; an evidence-backed status waits for AOC2's admission rule. One fixture for Python and TypeScript. Test: two members edit different assumptions and both survive; a status change without a person's accept is refused; an UNTESTED assumption with no evidence is accepted and tracked; a locked item refuses.

**AOC2. Assumption evidence from Deep Research (W2)**  
First the ADR and the deterministic admission rule (ADR 0026 decision 4): a finding attaches to an assumption by its id, quote, source and run, never by a model's word. A Design Research proposal may add the attachment; accepting it is a person's act; it never changes the status. Test: an attachment with no quote in a captured source is refused; a rejected finding is not attachable.

**AOC3. Assumption consumers (W3)**  
`research-lead-workbench#18` shows and edits the assumptions; `lead-orchestration#LO7` adds them to the Lead's design layer; the analysis payload carries each with its links as context (`evidence-integrity#7` shares the context path); the report states each with its status and its support, via `report-delivery#RD9`. Test: the report prints no status that has no accepted decision and no support it does not hold.

**AOC4. The open-answer coding method (`MVPQ-02b`)**  
Specifies: the codebook and rules and who defines them (a person, or a model proposing and a person approving); the unit (one answer, one or several codes, multi-label semantics); the label set and its versioning; the denominator and the treatment of missing answers; review and acceptance; quality and agreement measures; the support rules for small codes (suppression, effective n); what a model may do (propose codes, never final); reproducibility (the same answers and the same codebook version give the same counts); what an AI-respondent answer means as evidence for these counts (modelled, internal until the validation lifts it). First the ADR and admission rule ADR 0026 decision 4 requires. Blocks AOC5 runtime, AOC6, AOC7.

**AOC5. Coding storage and determinism (W2)**  
A run-derived artifact beside the dataset: answer id, code, codebook version, **assignment version**, coder kind (person or model with its model and prompt pin), reviewer, time, and a link back to the answer as the traceable example. It never overwrites a respondent answer. Once reviewed, an assignment version is frozen; recoding (by a person or a model) writes a **new** assignment version, and changed assignments may legitimately change counts. Determinism is over the same frozen reviewed assignment version, the same dataset and the same codebook version: the counts function is pure and gives the same counts and fingerprint. The method, prompt, model and assignment identity are pinned, so a retry or reuse never replays paid classification and never edits a frozen answer. A coding node in the run (`run-qc-and-checkpoint#RQC2`'s pattern: template node, step kind, registry, switch, run-key identity) with an impact root: a codebook change reruns coding and analysis, never fieldwork. Test: the same frozen assignment version gives the same counts; a new assignment version may change them and says so; a retry replays no classification call; fieldwork is untouched.

**AOC6. Coding as admitted claims (W3)**  
Counts reach a result only through `admit_numeric_claims` with effective-n suppression and intervals; a small code is suppressed, not shown. Answer text sent to a model has a `MaterialRule` and lineage (`run-qc-and-checkpoint#RQC3`'s run-derived class). Test: a count with too small a base is suppressed from the response; no count exists without a claim; raw text is not marked admitted.

**AOC7. The coder, only if AOC4 lets a model propose codes (W3)**  
A twelfth worker row (the eleven are the baseline of AC-03): binding, price, an editable and pinned prompt (`system-prompts-settings#7`, `#13`), an accept destination that is the coding review. It is routed through the Lead and the same server gates as every worker (`lead-orchestration#LO15`). If AOC4 forbids a model coder, this chunk is closed with that reason and AC-03's baseline stays eleven. Never counted as present because an existing slot "could" do it.

**AOC8. Coding consumers (W3)**  
Results shows the codes and counts per open question with their support and suppression, and traceable example answers by answer id (labelled modelled for AI respondents) (`research-lead-workbench#20`/`#21`); a named analysis module takes the coded counts as input, or the module contract is amended explicitly (an eighth-module change is a scope item, not a quiet edit); the report chapter is `report-delivery#RD10`. An unavailable result is typed unavailable, never guessed.

**AOC9. The acceptance journey and its refusals (W5)**  
`mvp-acceptance-harness#15`: an assumption tracked as UNTESTED, evidence attached, an evidence-backed status set by a person with its support and printed in the report; open answers coded, counts admitted and shown in Results and the report. Refusals: an evidence-backed status without admitted or cited support (UNTESTED is allowed), counts never produced from prose, a codebook change that leaves fieldwork untouched, a model coder that cannot accept its own codes; a changed assignment version may change counts and says so.

## Open: owner and methodology

- `MVPQ-02b`: the open-answer coding method (AOC4), the methodology owner's, approved by the owner. Until approved, the contracts and refusal tests proceed and no count is produced. There is no owner question for assumptions: their contract is engineering and their evidence rule is the existing evidence policy plus AOC2's ADR.
