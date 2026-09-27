# Button

Action buttons: primary (signal), secondary (bordered), quiet, danger; comfortable or compact.

**The consumer provides:** `variant`, `compact`, `icon`, `kbd` (a shortcut hint), `onClick`, children for the label.

**Use:** Keep one primary action per surface. In ParkAndAsk no action is primary-by-default in focus.

**Don't:** Never render a disabled button for a permission the viewer lacks — omit it. Never use amber for a button.
