# Vrátit, nebo potvrdit

Pick exactly one per action, by this rule:

| Akce | Jak |
|---|---|
| Can be undone fully (rename, refile, label, role, contact, status, a Lead edit) | Acts at once. UndoToast "Vrátit" for **8 s**, paused on hover or focus. One offer at a time, the newest. |
| Cannot be undone, or reaches outside AIA (delete for good, public research, deactivation that seals the Lead) | ConfirmDialog. Focus on the safe button. Esc cancels. The verb is on the button ("Smazat natrvalo"). A typed name only for the client delete. |
| Spends money | SpendDialog (next rule). Never a ConfirmDialog. |
| Leaves unsaved work | InlineConfirm at the place ("Zahodit úpravy a přepnout" / "Pokračovat v úpravách"). **Esc = keep.** |

**Fix today**
- No undo: contact remove (`ProfileArea.tsx:261`), knowledge approve/reject (`KnowledgeArea.tsx:117`), bulk filing (`KnowledgeLibrary.tsx:278`), label × (`:409`), client status and archiving (`AccessPanel.tsx:486`), "Obnovit", "Nikdy" (`StudiesPanel.tsx:110`), and intake row remove or closing a filled sheet (`IntakeSheet.tsx:188,500`).
- InlineConfirm has no Esc (`rehome/step.tsx:342`).
- Prompt activation uses an inline panel where every other activation uses ConfirmDialog (`SystemPromptsPanel.tsx:663`).


**Fixed in PR #1022:** Vrátit for a removed contact and a client status change. Still to do: approve/reject, bulk filing, label ×, intake rows, InlineConfirm's Esc, prompt activation.

*Source: the interaction inventories of 27. 10. 2026, read from `apps/web` at develop@dbaa7720 (client workspace, Settings, shared controls, the workbench and its eleven stages). The anchors are in each rule.*
