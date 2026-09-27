# ProviderChoice

An explicit choice when a provider cannot serve: wait (free) or switch (paid, changes provenance).

**The consumer provides:** `provider`, `reason`, `resumeAt`, `policy` (ProviderPolicy), `alternative`, `alternativeCost`.

**Use:** Show it on a run parked in WAITING_PROVIDER.

**Don't:** Offer the switch only when policy is CLAUDE_CODE_THEN_API. Never present a cheaper or different provider as a convenience.
