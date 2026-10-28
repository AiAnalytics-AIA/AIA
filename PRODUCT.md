# Product

<!-- impeccable:product-schema 1 -->

Written on 27 Oct 2026 from the repository (CLAUDE.md, ARCHITECTURE.md, `apps/web`, `.planning/`,
`prototypes/LOOK.md`), not from an interview. Lines marked *(inferred)* were read from code and copy,
not stated by the product owner; open decisions are listed at the end.

## Platform

web

## Users

- **Researchers** at a market and social research agency (Czech-speaking), who design and run
  studies for their clients and hand over reports. They work in long desk sessions at 1440 px and
  above; the product also serves 1100 px, 768 px drawers and 390 px phone sheets.
- **Owners and administrators** of the organization, who set roles, budgets, client rules, the
  methodology in force and who may approve what.
- **The Metodik** (a member carrying the methodology mark), who edits and activates methodology
  versions such as the Sociomap's.
- Every member has the same research permissions (one role, ADR 0019); approvals and
  administration are gated by role and by the person's own rights.

## Product Purpose

AIA lets a researcher take a client's question from a written brief to an approvable report:
brief, research design, questionnaire, audience, dimensions, sample, a run answered by AI
respondents drawn from a modelled Czech population, results, a sociomap (a map of how objects such
as brands relate in respondents' eyes), analysis modules and a DOCX/PDF report edited and approved
in place. An AI Research Lead (Ada by default) works beside every step: it reads the study, proposes
edits and paid jobs, and never changes anything without the person's yes. Success is a study a
researcher can defend: every number traceable to admitted evidence, every spend confirmed, every
modelled figure labelled.

## Positioning

AIA's respondents are modelled from a licensed Czech population panel with its own field policy,
and every number reaches a result only as an admitted claim (support, intervals, suppression,
modelled vs measured). The Lead proposes; people decide. *(inferred from ADRs 0016, 0024, 0026)*

## Operating Context

- Work is organized client-first: Klienti → a client's workspace (Přehled, Výzkumy, Simulace,
  Znalosti, Data, Profil) → a study → its eleven stages in six phases.
- Paid AI work is held against the client's and the study's budget; a start whose cost ceiling
  reaches the confirmation threshold asks first.
- Reports are DOCX and PDF, edited in an ONLYOFFICE editor AIA hosts, approved as the exact version
  read.
- Client knowledge (documents, datasets, sources, approved facts) is scoped to its client.

## Capabilities and Constraints

- Czech UI copy throughout; money in the Czech locale ("1 250,00 USD"); four money names
  (Rozpočet klienta, Rozpočet studie, Peněženka, Práh potvrzení).
- Unknown is never shown as zero or as good; suppressed values are named, never a number.
- No emoji in the interface.
- Evidence states: modelled, measured, suppressed, unknown; a Sociomap's approval comes from its
  register.
- Next.js 16, React 19, Tailwind 4; one design-token source (`apps/web/src/design/tokens.json`).

## Brand Commitments

- The approved look of 26 Oct 2026: `prototypes/LOOK.md`, the Settings prototype (v99) and the
  research-stage prototype (v73/v77) on core v3 (`prototypes/shared/aia-core.css`). The product
  owner: *"I am super happy with the design of the research steps, we need to aim to build out this
  exact UX design."*
- Indigo signal `#4b48ce` (dark `#828bea`); coral only for "needs you"; green only for "in force";
  no amber; radii 6/8/10, *"rounded but not complete pills"*; IBM Plex Sans/Mono, Source Serif 4 for
  top-level heroes only; Phosphor icons.
- The AIA mark (a 5 × 5 lattice) and the researcher's own Lead mark.

## Evidence on Hand

- Fictional development data only (`make ui-fixtures`, the develop seed). No customer names,
  testimonials or usage figures exist in the repository; none may be invented.

## Product Principles

1. The person decides; AI proposes and shows its cost first.
2. Unknown is never good, never zero.
3. Every number shows where it came from.
4. One look across Settings and the research stages.

## Accessibility & Inclusion

WCAG 2.2 AA: 4.5:1 text contrast in both themes, 24 px minimum targets (44 px on a phone), visible
focus, reduced motion honoured. *(from tokens.json usage notes and LOOK.md)*

## Open decisions

- Whether `/studies` (the pre-AIA pages) stays reachable. *(design-system v2, D3)*
- The fifteen look questions D1-D15 in the AIA Design System v2 artifact.
