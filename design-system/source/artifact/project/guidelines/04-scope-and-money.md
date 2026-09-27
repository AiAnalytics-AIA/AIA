# Scope, confidentiality and money

## Persistent scope chrome

`ScopeBar` is the first thing on every screen, and it is sticky at `z-scope`. Nothing may cover it. It carries:

- a 4px band in the client's accent,
- the client monogram (two letters on the accent),
- *Client / Study*, the `StudyStatus` chip, the revision, and your effective role.

States:

| Surface | Band | Crumb | Extra |
|---|---|---|---|
| Inside a study | `client-N` | Client / Study | — |
| Across clients (Portfolio, Data Library, Admin) | hatched `scope-above` ink | "Napříč klienty" + what the screen spans | Each row carries its own monogram |
| Delivered, archived or cancelled | `client-N` | Client / Study | A "Pouze ke čtení · Předáno 12. 6. 2025" plate; edit actions are absent |
| Park-and-ask dialog | its own band, `client-N` | Client / Study inside the dialog | A spending decision always shows whose budget it spends |

## Client accents

Six accents (`client-1…6`), low in chroma and spread in hue and lightness. They are used **only** in the scope band and the monogram, never in a plot area and never in a status.

Measured separation (OKLab ΔE × 100, both themes; see *Accessibility*):

- to every status, UI and categorical token: **≥ 7.6** (light) and **≥ 7.7** (dark),
- to each other: **≥ 13.3** (light) and **≥ 12.9** (dark),
- the hues exclude the amber band (55–100°) and the signal/slate band (228–262°) outright.

**Derivation.** The brief asked for an accent derived from the client identifier. A pure hash is deterministic but collides early: FNV-1a mod 6 over this system's five fixture clients already puts two on the same accent (`cl_salvia` and `cl_tecka` both → 4). The design therefore uses a **persisted slot**. It is assigned once, least-used first, when the client is created, and it never changes afterwards. That keeps it deterministic, since it is stored with the client and identical on every screen. The hash (`clientAccentIndex`) is only a fallback for a client created before the slot existed. With more than six clients some accents repeat, so the accent is a *second* channel: the client name and monogram are always present, and they are the primary identification.

## Permissions: absent, not disabled

A viewer's screen is not a researcher's screen with dead buttons. An action the viewer cannot take is **absent**. The exception is an action whose presence is itself information. There it is shown with who *can* do it — "Výdaj nad rozpočet schvaluje vedoucí studie · Požádat". A resource you have no grant on is "Studie nenalezena", with the same copy whether it exists or not (the backend returns 404, not 403).

## Money

- **`BudgetMeter`** has four quantities, and three of them are not a progress bar: *utraceno* (solid `budget-spent`), *nejisté* (`SETTLED_UNCERTAIN`, hatched `budget-uncertain`, counted as spent and shown in red even when it is 0,84 USD), *rezervováno* (hatched `budget-reserved`) and *zbývá* (the empty track). Each segment has a key with its exact amount, and a 2px gap separates the segments.
- **`ParkAndAsk`** states what will be spent, on what, with which model role and provider, against which study's budget, what is left afterwards, and exactly what happens if you decline. Focus opens on the heading, not on "Schválit", and both actions have equal weight. Without `APPROVE_BUDGET` the approve action is replaced by "Požádat vedoucí studie".
- **`UsageLedger`** is immutable, dense, sortable, exportable to CSV, and attributable to a step and a model role. A reservation still in flight shows its output tokens and amount as *chybí*. A subscription call shows `0,00 USD` with a note that it is covered by the subscription, not free.
- **`ProviderChoice`**: when a provider cannot serve, the default is to wait (at no cost, resuming by itself). Switching is shown only where `ProviderPolicy` is `CLAUDE_CODE_THEN_API`. It is labelled as paid and as changing provenance, and it is written to the audit trail. It is never offered as a cheaper convenience.
- **`RecoveryDecision`** offers three explicit choices. "Spustit znovu" says it may charge twice. There is no automatic retry.
- Currency is always written out (`USD`, `CZK`). Money uses `num` with two decimals, and four in the ledger.
