---
status: planned
chunks:
  - "[ ] PDR0. The data source register as data: each source's legal status, cost, rate limit, licence, retention, and whether a field names a natural person, from the pivot research's § Data source register; read by RetrievalGate, never by a model"
  - "[ ] PDR1. SDMX: Eurostat and the ECB Data Portal as one route family; the model proposes a query key, code fetches, every admitted value byte-equal to the API's response; recorded doubles and golden responses pinned by hash"
  - "[ ] PDR2. ČNB: the daily fixing and ARAD series, within ČNB's limit on automated access"
  - "[ ] PDR3. GLEIF: entity and ownership matching (its licence confirmed first)"
  - "[ ] PDR4. EU TED: procurement notices and awards"
  - "[ ] PDR5. ISVZ open data live: isvz-notice-1 from recorded to a live route; NEN data behind its login never collected, refused by name"
  - "[ ] PDR6. ARES extended (firm counts by NACE, counterparty checks) and the commercial register's open data (dataor.justice.cz); fields that name a natural person wait for register-personal-data RPD1-RPD2"
  - "[ ] PDR7. Sbírka listin financial statements: PDF and XHTML read with located segments (client_sources' readers), both Czech P&L layouts, every extracted value reviewed by a person before use; the review's cost measured, which decides PDR10"
  - "[ ] PDR8. VIES: a one-off VAT validation, the answer never stored or retransmitted"
  - "[ ] PDR9. ČÚZK REST API-KN after registration (the owner registers), parcels as a high-value dataset; the paid WSDP outputs priced on the tool-cost ledger"
  - "[ ] PDR10. Commercial structured data (Merk, Cribis, MagnusWeb, Orbis, Creditinfo): the owner's buy-or-build decision from PDR7's measured cost; nothing contracted by this plan"
---
# Public data routes: Czech and EU registers and statistics

Written 2026-11-02 under [ADR 0046](../../docs/architecture/adr/0046-business-decisions-pivot.md)
decisions 6 and 7. The source register is the research's § Data source register and sections C1-C3
([`../evidence/pivot-research-2026-11-02.md`](../evidence/pivot-research-2026-11-02.md)).

**What exists.** These connectors are built and registered:
- `ares-subject-1`;
- `csu-datastat-1`;
- `eurostat-statistics-1`;
- `nkod-sparql-1`;
- `isvz-notice-1`, which records only.

They are in `docs/architecture/deep-research-connectors.md`. None has a live probe (@ 57c133a). There
is no connector for ČNB, ECB, TED, GLEIF, VIES or Sbírka listin.

**Rules.**
- Every route runs through `RetrievalGate`, under the gate additions of `deep-research-v2#DRV0`.
- A route's values reach a model input only as typed inputs a person accepted (`deep-research-v2#DRV3`).
- A priced route runs only under ADR 0022's sign-off.

**Owner:** S2. Proposed; the session that takes it reviews this plan first.
