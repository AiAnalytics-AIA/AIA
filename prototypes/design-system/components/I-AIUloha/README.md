# AI úloha: od návrhu k rozhodnutí

Every AI job (a Lead card, a design worker, Deep Research, AI proposals from a document) moves through one life, with one card and one set of words:

1. **Připraveno · čeká na vás**: coral, with the ceiling, "Teď ne" and the AI start with its amount.
2. **Běží**: orb and AgentStatus with Zastavit; the progress the job reports, never a guessed percentage.
3. **Čeká na rozpočet**: coral. It shows the need (`budget_need`) and the study's lift through SpendDialog.
4. **Hotovo · návrh čeká**: ChangeReview on the stage it changes, plus "Posoudit na Návrhu" from the card.
5. **Přijato / Zahozeno / Zastaralé**: the ledger's word. A stale proposal says what moved and offers "Navrhnout znovu".

The card, the tray, the palette and the overview bar show the same state.

**Fix today**
- AI proposals from a document poll every 2 s with their own words (`SourceProposals.tsx:60-81`). They should read this life.
- `agentJobState` already treats "waiting for budget" as waiting (`lib/research-agent-jobs.ts`); keep it.


*Source: the interaction inventories of 27. 10. 2026, read from `apps/web` at develop@dbaa7720 (client workspace, Settings, shared controls, the workbench and its eleven stages). The anchors are in each rule.*
