# Peníze: jedno okno, čtyři jména

Any action that can spend money opens **SpendDialog** before it acts. That covers:
- a paid start, retry or analysis retry;
- Deep Research;
- a budget lift;
- AI proposals from a document;
- raising a budget, a wallet or a ceiling.

**The dialog shows**
- the ceiling, "horní mez, ne odhad";
- what remains of the budget it is held against, "I při nejvyšší ceně zbude…";
- the four money names, written once (Rozpočet klienta, Rozpočet studie, Peněženka, Práh potvrzení);
- unknown as "neznámá", never 0,00.

The start button carries the amount (`btn ai` + `.amt`).

**Fix today**
- SpendDialog exists and is used nowhere (`ui/SpendDialog.tsx`). The workbench asks through AskDialog.
- AI proposals from a document start with no confirmation (`SourceProposals.tsx:134`, `IntakeSheet.tsx:378`).
- A budget is typed into `type=number` (`ProfileArea.tsx:403`) or free text (`SourceProposals.tsx:125`), where an invalid value is silently ignored.
- Budget Steppers save on every arrow press (`StudiesPanel.tsx:91`): commit on Enter or blur instead.


**Fixed in PR #1022:** `confirmSpend`. SpendDialog for every paid start and retry in the research flow, for agent jobs at the threshold and for the Lead's run start; Czech amounts. Stepper `deferred` saves a budget, ceiling or proposal once. Still to do: AI proposals from a document, the Profile budget field.

*Source: the interaction inventories of 27. 10. 2026, read from `apps/web` at develop@dbaa7720 (client workspace, Settings, shared controls, the workbench and its eleven stages). The anchors are in each rule.*
