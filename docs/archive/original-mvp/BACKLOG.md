> [!WARNING]
> **SUPERSEDED — NOT CURRENT REQUIREMENTS.**
>
> This document describes the *original* AIA MVP: a single-case workspace that
> produced a copy/paste correlation matrix for **manual** Sociomapping. That scope
> was superseded by the production rebuild brief, which replaces the AIA
> application with the full NPC Panel research and simulation product.
>
> It is retained for historical context only. Do not implement from it, cite it as
> a requirement, or treat it as a backlog.
>
> **Current authoritative documentation:**
> - Product scope — [`docs/product/`](../../product/)
> - Architecture — [`docs/architecture/`](../../architecture/)
> - Migration status — [`docs/migration/status.md`](../../migration/status.md)

---

# AIA Backlog (v0.1)

## Milestone: v0.1 (single-case, correlation paste pack)

### Must-have
- [ ] Login: password hash + session (no plaintext env)
- [ ] Single-case stepper UI (Intake → Variables → Upload → Stats → Exports → SOP)
- [ ] Variables table editor + validations
- [ ] Upload CSV/XLSX + preview + column list
- [ ] Mapping UI (variable → column) with auto-suggest + completeness checks
- [ ] Data quality summary (N, missing%, constant columns)
- [ ] Stats: Spearman default + Pearson option
- [ ] Export: matrix.xlsx + matrix.csv (headers = variable names)
- [ ] Export: dictionary.xlsx + dictionary.csv
- [ ] Export: stats-summary.txt (method, missing handling, warnings)
- [ ] Audit log for each run + parameters

### Nice-to-have
- [ ] Gate UI (Request approval / Approve / Reject with comments)
- [ ] Basic issue list (QA-lite): unmapped vars, high missing, constant cols
- [ ] Download bundle (zip) of exports

## Later
- Evidence Pack (RAG)
- Study Writer + QA agents
- Multi-case dashboard
- RBAC + per-client isolation
