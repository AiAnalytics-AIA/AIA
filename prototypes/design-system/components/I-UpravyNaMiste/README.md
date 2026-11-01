# Úpravy na místě a vytváření v řádku

Edit a value where it is read (InlineText): click, Enter, F2 or Space opens it. Enter or blur saves. Esc restores. A selectable value waits 300 ms for a second click, so its words can be selected.

Create in the list (InlineCreateRow): "+ Nová složka". Enter creates and opens the next row. Esc or an empty field cancels. A refusal stays at the row in words ("„Brand“ už existuje.").

**Selects never act on change.** A select chooses; a button acts. A select that acts on change breaks I3: `IntakeSheet.tsx:347`, `MethodologyVersions.tsx:617`, `AccessPanel.tsx:389`.

**Reorder**: a drag handle plus Alt+↑ / Alt+↓ on every ordered list. That covers questions, sections, objectives and research questions. Today nothing in the questionnaire can be reordered.


*Source: the interaction inventories of 27. 10. 2026, read from `apps/web` at develop@dbaa7720 (client workspace, Settings, shared controls, the workbench and its eleven stages). The anchors are in each rule.*
