# BudgetMeter

A study budget: spent, uncertain (SETTLED_UNCERTAIN), reserved and remaining, each with an exact amount.

**The consumer provides:** `limit`, `spent`, `uncertain`, `reserved`, `currency`.

**Use:** Use it on the study overview and the cost screen.

**Don't:** Never merge uncertain into spent silently or round it away. It is shown separately and in the fault colour, even at 0,84 USD.
