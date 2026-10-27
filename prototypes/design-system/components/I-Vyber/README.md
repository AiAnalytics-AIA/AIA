# Výběr a hromadné akce

Rows have a checkbox, plus "Vybrat vše zobrazené" in the header. Shift-click selects a range.

When anything is selected, a bulk bar replaces the toolbar. It shows:
- "Vybráno: n";
- the actions as menus (Přesunout do složky, Přidat štítek, Odebrat štítek);
- "Zrušit výběr" (Esc).

Each bulk action ends with a toast naming what it did ("3 znalosti přesunuty do Brand 2025") and Vrátit. Today it reloads silently with no undo (`KnowledgeLibrary.tsx:260-288`).


*Source: the interaction inventories of 27. 10. 2026, read from `apps/web` at develop@dbaa7720 (client workspace, Settings, shared controls, the workbench and its eleven stages). The anchors are in each rule.*
