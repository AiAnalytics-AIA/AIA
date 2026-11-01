# Výběr (Select)

A button with a caret that opens a list: the button 32 px, radius 6; the list radius 10 with `shadow-overlay`, the chosen item marked with a check. Keyboard: arrows, Enter, Escape, type-ahead.

**Use** when the options are more than five or their labels are long (a category, a client, a member). Five or fewer short options: Segmented.

**Replaces** `rehome/ui.tsx:134` Select (native `<select>`, 36/14) and the menu half of `ui/MenuButton.tsx` keeps its role for actions. POPOVER in `ui/parts.tsx` is this list's frame.
