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

# AIA Roadmap (MVP)

## v0.1 — Single-case workspace
1) Login
2) Intake (form)
3) Variable table + mapping to dataset columns (wide format)
4) Upload CSV/XLSX + preview + basic data quality report
5) Stats: correlation compute (Spearman default; Pearson option)
6) Exports:
   - matrix.xlsx / matrix.csv
   - dictionary.xlsx / dictionary.csv
   - stats-summary.txt
7) Manual Sociomapping checklist

## Later
- Evidence pack (RAG)
- QA reviewer view
- Multi-case dashboard
