---
status: planned
chunks:
  - "[ ] RD0. Define the "evidence audit" and the "legal source-use gate" as testable checks (the owner states what each checks)"
  - "[ ] RD1. The client report PDF: extend `RENDERABLE_REPORTS`, the PDF is approved with its DOCX"
  - "[ ] RD2. A reader for the approval ledger: "approved by whom, when" for a report and a snapshot"
  - "[ ] RD3. The Approve and Export panel: what is approved and by whom; exports after approval; the slot in the Report artifact"
  - "[ ] RD4. The map snapshot: an approvable object rendered server-side from the stored map and camera parameters, never browser bytes; one ledger shape"
  - "[ ] RD5. Report draft revisions: a separate draft counter, tracked changes per paragraph; a report edit never reopens fieldwork"
  - "[ ] RD6. The accept destinations for the report writer, the map interpreter and the straight-liner flags: an artifact type, the composer input and its fingerprint"
  - "[ ] RD7. A sentence-level claim check: a sentence that claims a comparison with no admitted claim is flagged"
  - "[ ] RD8. The producer of a client report is the run that composed it, not whoever first downloaded it"
---
# Report delivery: approval, export and the map snapshot

What makes a report deliverable: the approvals, the export panel, the client PDF, the snapshot and the worker accept paths. Written 2026-10-19 from `.planning/evidence/mvp-master-traces/trace-3-evidence.md`.

**Owner: S3.** Takes the gap rows G34, G35 (accept paths), G16 (accept destinations) and interfaces I12, I13, I14 of `mvp-master-plan.md` §6.1 and serves AC-13, AC-08 and gate I-3.
Every chunk below is **open**; a chunk is built from this file, not from the master plan.

## Decisions this plan carries (settled by the owner; not re-asked)

- Separate approvals for the internal report, the client report and each map snapshot; DOCX and PDF become available only after approval (F17).
- No unconditional second person: whether the producer may approve follows the client's existing self-approval setting (F17, withdrawn 2026-10-19).
- AC-13 stands as written: the client report is **DOCX and PDF**, passes the evidence audit and the legal source-use gate, carries only approved maps and labelled modelled and client-reported numbers and no analysis prose. Dropping the PDF or weakening a gate is a scope override and needs the owner's explicit yes.

## Chunks

**RD0. Define the "evidence audit" and the "legal source-use gate" as testable checks (the owner states what each checks)**  
Both are NOT_STARTED in the parity matrix with no plan. The checks are the owner's to define; this chunk records them and builds them. Not replaced by a weaker check without the owner's override.

**RD1. The client report PDF: extend `RENDERABLE_REPORTS`, the PDF is approved with its DOCX**  
The client report is DOCX only today (`report_variants.py:78`).

**RD2. A reader for the approval ledger: "approved by whom, when" for a report and a snapshot**  


**RD3. The Approve and Export panel: what is approved and by whom; exports after approval; the slot in the Report artifact**  
S1 hosts the slot (`research-lead-workbench` 21), same wave. Tests: approvals name the exact artifact fingerprint; a stale-version download is refused; both self-approval settings; an unauthorised download is refused. Today drafts download freely and approval follows the download (`research.py:2395-2449`); the panel makes the client export follow approval. Interfaces I12.

**RD4. The map snapshot: an approvable object rendered server-side from the stored map and camera parameters, never browser bytes; one ledger shape**  
The existing approval writes subject `artifact` (`artifact_repository.py:568`) and M3 names `map_snapshot`; one is chosen and the other removed. S2 supplies the deterministic figure function. Interfaces I13.

**RD5. Report draft revisions: a separate draft counter, tracked changes per paragraph; a report edit never reopens fieldwork**  
The prototype's D6. The counter against ADR 0016's revision semantics is an owner clarification below.

**RD6. The accept destinations for the report writer, the map interpreter and the straight-liner flags: an artifact type, the composer input and its fingerprint**  
S3 defines the type, S1 writes the worker against it (`lead-orchestration#LO9`). Interfaces I14.

**RD7. A sentence-level claim check: a sentence that claims a comparison with no admitted claim is flagged**  
The prototype shows it (scenario M); the evidence validation checks numbers only. A new rule; the owner confirms its strictness.

**RD8. The producer of a client report is the run that composed it, not whoever first downloaded it**  
With self-approval off, the reviewer who opens it first cannot approve it today ◇.

## Open: owner clarifications

- What the evidence audit and the legal source-use gate check (RD0).
- Whether the report draft counter is separate from the Design Revision (proposed: yes, the prototype's D6).
