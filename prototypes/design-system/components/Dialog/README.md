# Dialog

560 px, radius 10, padding 24, `shadow-overlay` over a 10 % ink scrim. Title says the action as a question; the body says what changes and what stays; buttons right: quiet cancel, then the action. An irreversible delete asks you to type the name.

**Use** only for a consequential decision that is not money (money: SpendDialog). Everything else confirms in place with undo (Toast).

**Replaces** `rehome/ui.tsx:155/173` AskDialog (prompt and confirm kinds → one ConfirmDialog with an optional field), the six `<dialog>` frames (three copies of the same class), research's `.sdlg` (520 → 560, padding 20 → 24).
