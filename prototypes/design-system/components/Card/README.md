# Karta a sekce (Card, StageSection)

Raised, 1 px `border`, radius 8, no shadow. Inside a study a stage's body is numbered sections (`.sec`): a header with the number in mono, a 15/20 title and a caption on the right, because their order is real. R16's tonal layering stays: sections are sheets, items in them are wells one tone down.

**Use** Card for a self-contained block on Settings and client pages; Section for a stage's parts. Don't nest cards; a well inside a well goes back up to the sheet.

**Replaces** `states.tsx:13` CARD (p-5 → 16) and its five private copies, SampleView's own `Sec`, `rehome/step.tsx:120` ActionDock (a bordered card → an action bar on `surface` with a top border), `live/ui.tsx:9` Panel (r12 + shadow).
