---
status: planned
chunks:
  - "[ ] RPD0. The processing record for named natural persons taken from public registers: purpose, legal basis (legitimate interest), the balancing-test template, retention, recipients; written with the legal counsel the owner names, before any such field reaches a study"
  - "[ ] RPD1. Which register fields name a natural person (ARES statutory bodies, the commercial register's officers and owners, sole traders), as data in the source register (public-data-routes PDR0); those fields withheld until RPD2 passes"
  - "[ ] RPD2. The balancing test as an approval-ledger subject (a migration admits it to ApprovalSubject before its writer): per client and source, recorded by a person, read before a withheld field is released to a study"
  - "[ ] RPD3. Art. 14 notices: where a notice is owed, its record; where an exemption applies, the reason recorded; both on the approval ledger"
  - "[ ] RPD4. Retention and erasure of register-derived personal data through study-data-lifecycle's delete path, with the horizons RPD0 sets"
  - "[ ] RPD5. Minimisation: a field naming a person never sent to a model unless RPD0's record allows that use, Class A by rule (material_rules), masked on screen as client_datasets masks personal columns"
---
# Personal data from public registers

Written 2026-11-02 under [ADR 0046](../../docs/architecture/adr/0046-business-decisions-pivot.md)
decision 7. The research found Czech registers lawful to build on (C2-C3), with GDPR binding for named
natural persons: the Czech DPA fined a register copier CZK 500,000
([`../evidence/pivot-research-2026-11-02.md`](../evidence/pivot-research-2026-11-02.md), C2). The
approval ledger gains the records (§ Keep, extend, replace: "Approval ledger: Extend").

**Owner:** S3, with the legal counsel the owner names (RPD0). Proposed; the session that takes it
reviews this plan first.
