# Ukládání: jeden stav, všude stejně

Every value saved where it is edited shows the same three states in a SaveNote, a polite live region beside the field:
1. **Ukládám…** while the request is open.
2. **Uloženo** for **3 s**, then it fades. It never stays forever.
3. **Neuloženo – Zkusit znovu** stays until it is retried or reverted, with the value kept in the field.

**Applies to** InlineText, Stepper, ChoiceChips that save, Switch, SwatchPicker, toggles, and the store's autosave ("Uloženo 9:14" in the stage header).

**Fix today**
- Stepper never shows "Uloženo" (`ui/Stepper.tsx:158-169`).
- `useSave` "Uloženo" never clears (`settings/AccessPanel.tsx:38-61`).
- Profile's "Uloženo" stays until the next edit (`ProfileArea.tsx:38-91`).
- No SaveNote at all on: self-approval (`ProfileArea.tsx:304`), the swatch recolour (`KnowledgeOrganizers.tsx:210`), "Interní dokument" (`SourceFile.tsx:193`), data posture → CLASSIFIED (`ClientRules.tsx:73`).


**Fixed in PR #1022:** one `SAVED_MS` (3 s) for InlineText, Stepper and Access's save note. The Stepper now says Uloženo; Access's note clears.

*Source: the interaction inventories of 27. 10. 2026, read from `apps/web` at develop@dbaa7720 (client workspace, Settings, shared controls, the workbench and its eleven stages). The anchors are in each rule.*
