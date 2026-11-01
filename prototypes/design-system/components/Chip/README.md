# Štítek (Chip)

A 24 px label, radius 6, 12/500: who sets a value, a data class, a version state, a filter that can be picked. Status chips use StatusGlyph's pill.

**Tones** `op` (set by the deployment operator, slate), `inapp` (set in the app, signal tint), `code` (fixed in code, dashed), `you`, `bad`, `good` (ink on strong border), `live` (in force, green), `world`, `ai`. `pick` chips toggle and show `signal` when chosen; they are for several choices, never a menu of one.

**Replaces** workbench.css `.chip` (r11 pill), `MethodologyRegister.tsx:13` RegisterChip (`rounded-[11px]`), `KnowledgeLibrary.tsx:70` LabelChip (`rounded-pill`, 20 h), `rehome/step.tsx:261` ChipInput's inner chips (r8), the 20 `min-h-[22px]` chips, and the local "V AIA zatím není" chips (`AccessPanel.tsx:98`, `DataPanel.tsx:50`, `AudienceStep.tsx:97`) → one `chip code` "V AIA zatím není".
