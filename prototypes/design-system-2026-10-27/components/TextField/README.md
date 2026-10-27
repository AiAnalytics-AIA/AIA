# Pole (TextField)

A text input, textarea or search field: 32 px high, radius 6, 1 px `border-strong`, 13 px text, a label above in `.lbl` (12/500 muted).

**Use** for typed values that are saved by a button or by the store's autosave. For a value edited where it is read, use InlineEdit; for a bounded number, Stepper; for a choice, Segmented or Select.

**The consumer provides** a visible label (never a placeholder in its place), the value, and the error in words under the field (`status-fault` on `status-fault-wash`, the field's own rule, checked as typed).

**Rules** a refused value is said at the field and never clamped; a field that can't be edited says who can ("Mění jen vlastník nebo správce.").

**Replaces** `rehome/ui.tsx:139` TextInput and `:143` TextArea (36/14 → 32/13), the 13 native `<input>`s screens draw themselves. *Open question D2: the v73 boards draw inputs at about 36/14; LOOK.md says 32/13. Recommended: LOOK wins.*
