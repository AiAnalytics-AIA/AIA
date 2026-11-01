# Peníze (SpendDialog)

The one modal for money: a start, a retry, a budget lift or a Deep Research run whose cost reaches the study's threshold. It names the four sums by their names (Rozpočet klienta, Rozpočet studie, Peněženka, Práh potvrzení), the ceiling as "horní mez, ne odhad", and an unknown price in words, never zero. The action leads with its amount.

**Use** every money confirmation. Inside the Lead's chat the same facts sit on the Lead card and its AI button; the dialog is for starts outside the chat.

**Replaces** the ≥ 10 money confirmations that go through `AskDialog` text via `withBudget` (`ExecutionSteps.tsx:767`, `:1177`, `:1250` …). `ui/SpendDialog.tsx:60` exists and matches the frame but has no product importer; v2 puts it to work.
