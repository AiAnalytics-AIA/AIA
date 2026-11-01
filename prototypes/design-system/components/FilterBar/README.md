# Filtr jako tokeny (FilterBar)

One bar holds every active filter as a removable token ("Stav: Rozpracované ×", "Štítek: Brand ×"), followed by free text. It replaces rows of aria-pressed chips beside chip groups: `StudyList.tsx:67`, `KnowledgeArea.tsx:500`, `AuditPanel.tsx:91`, `ControlPanel.tsx:822`.

**Keyboard**
- Backspace in the empty field removes the last token.
- ↓ opens the suggestions.
- Enter adds a suggestion.
- Esc clears the text.

**Search**: 300 ms debounce everywhere, never instant on one list and debounced on the next.
