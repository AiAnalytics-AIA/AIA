# Úprava na místě (InlineEdit)

A value edited where it is read (`ui/InlineText.tsx` in the product). At rest it is the text with a 1 px dashed `border-strong` underline; on hover, `signal-tint`; while editing, a 2 px `signal` underline on the tint.

**Behaviour (the same as the product, try it in the preview):**
- **Opening:** a click, Enter or F2 on the value opens a field holding the text, all of it selected.
- **Saving:** Enter or leaving the field saves, then "Uloženo" shows for 3 s (`SAVED_MS`). Nothing changed, nothing is said.
- **Restoring:** Esc puts the old text back.
- **Emptying:** an emptied value goes back to its placeholder.
- **Refusing:** a refused value stays open at the field with the reason in fault colour, the text kept. It is never clamped and never silently dropped.
- **Read only:** no mark and no hover.

**Use** for names, wordings and short values in tables and lists (a member's name, a research objective, a folder). A placeholder says what is missing, in `ink-faint`: mark the empty value `.inplace[data-empty]`. Never mark it with the class `ph`: `.ph` is the Phosphor icon class, and it would draw the value as a filled icon-sized box.

**The consumer provides** the value, a save handler that can refuse, and an undo where the change is consequential (Vrátit, 8 s).

**Replaces** `ui/InlineText.tsx:21` at rest (no mark today; a dotted underline and pencil only on hover) with the contract's always-visible dashed mark. `selectable` (Návrh's narrative, Q68) stays.
