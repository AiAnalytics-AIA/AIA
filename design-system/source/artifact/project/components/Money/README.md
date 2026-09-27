# Money

A monetary amount with its currency, in Czech formatting.

**The consumer provides:** `value` (number or null), `currency` (default `USD`), `digits` (2 by default, 4 in the ledger).

**Use:** Use it for every amount: budgets, reservations, ledger rows, estimates.

**Don't:** Never render a bare number for money. `null` renders “chybí”, never 0,00.
