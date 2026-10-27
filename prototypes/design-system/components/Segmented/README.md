# Přepínač možností (Segmented)

Every option menu is built this way: square cells divided by borders inside one 6-radius frame, the chosen cell filled with `signal`. 32 px (small 28). It is a radio group: arrows move, the label names the group.

**Use** for 2–5 short, exclusive options: a period, a view, a role, a theme. More or longer: Select. Several may be chosen: pick Chips.

**Rule** "no menu should be a row of pill buttons ever". Tabs that change the page are Tabs (Settings' `.subtabs`), not this.

**Replaces** `ui/ChoiceChips.tsx` default look for single choices (→ `look="segmented"` everywhere), `rehome/step.tsx:217` Segmented (iOS-style track), workbench.css `.seg`, and 9 pill rows: `StudyList.tsx:67`, `KnowledgeArea.tsx:500`, `AuditPanel.tsx:91`, `ControlPanel.tsx:822`, `ObjectMapView.tsx:306` and `:332`, `PlanStep.tsx:315`, `BriefStep.tsx:346`, `:409`.
