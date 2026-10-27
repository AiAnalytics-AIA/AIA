# Klávesnice

**Global**
- Ctrl/⌘ K: the palette.
- `?`: shortcut sheet.
- G then K / P / N: Klienti / Paměť / Nastavení.
- N: Nový výzkum.
- U: Přidat podklady.

None of these fire in a field.

**Inside a widget**
- Tab enters a group once. Arrows move inside it (roving tabindex).
- In a radio-like group, an arrow **moves**. Enter or Space **chooses** when the choice saves or spends.
- F2 renames. Enter saves. Ctrl+Enter saves a multi-line field.
- Esc restores, then closes, from the inside out: field → popover → drawer → page. Focus returns to the opener every time.

**Fix today**
- Arrows that save at once: Access roles, client status, self-approval (`AccessPanel.tsx:178,354,486`) and Deep Research in-row chips (`DeepResearchSettingsPanel.tsx:477`, each a new proposal version).
- No arrow keys in: the SectionMenu list, the Metodika preset radios (`MethodologyPanel.tsx:234`), the version tabs (`MethodologyVersions.tsx:183`), the study filter and kind chips.
- No Esc on: the mobile dock menu (`DockRail.tsx:121`), the open knowledge item (`KnowledgeLibrary.tsx:236`), contact and add forms.
- Focus does not move to the opened item panel.


**Fixed in PR #1022:** Ctrl/⌘ K palette on every page and in the workbench. ChoiceChips `saves` (Access roles, statuses, self-approval, posture, Deep Research chips). Still to do: arrows in SectionMenu, Metodika presets and tabs; Esc in the open item and the forms.

*Source: the interaction inventories of 27. 10. 2026, read from `apps/web` at develop@dbaa7720 (client workspace, Settings, shared controls, the workbench and its eleven stages). The anchors are in each rule.*
