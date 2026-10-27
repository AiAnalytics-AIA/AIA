# Načítání, prázdno, chyba

Every container has four states, drawn in its own frame so the layout does not jump:
- **Načítání**: skeleton bars at real size, after 300 ms (none for faster reads), in a polite live region. Never a blank, and never only "Načítám…" in plain text.
- **Prázdno**: one sentence that says what is missing, plus one action ("Zatím žádné výstupy." + "Spustit výzkum").
- **Neznámé**: "neznámé" / "nezjištěno" with why on hover and focus, never 0 and never good.
- **Chyba**: one Czech sentence saying what failed and who fixes it, plus "Zkusit znovu". The request id goes under "Technické údaje".

**Never shown to a person**: an API's English `message`, "HTTP 409 · code", a user id, a run id, `e3`, OPEN / CLASSIFIED, or a raw stage code.

**Fix today**
- `e.message` reaches the screen in the client workspace (`states.tsx:36`, `ClientContext.tsx:100`, `KnowledgeArea.tsx:70`, `IntakeSheet.tsx:212`, `MemoryStudy.tsx:200`).
- `describeError` prints "HTTP {status} · {code}" across Settings (`settings/errors.ts:7`).
- Raw ids show at `SourceFile.tsx:221`, `AuditPanel.tsx:53` and `DataPanel.tsx:100`.
- ClientRules renders nothing while loading (`ClientRules.tsx:50`).


**Fixed in PR #1022:** `errorWords` / `errorText`: Czech by status, technical detail labelled; the page loader folds it under Technické údaje. Still to do: raw ids and codes outside errors (OPEN / CLASSIFIED, user and run ids, `e3`).

*Source: the interaction inventories of 27. 10. 2026, read from `apps/web` at develop@dbaa7720 (client workspace, Settings, shared controls, the workbench and its eleven stages). The anchors are in each rule.*
