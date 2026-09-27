# Sociomap

Respondent and object maps over immutable originals; view overrides and what-if are visible layers.

**The consumer provides:** `nodes` [`{id,label,x,y,role,cluster,moved?,whatif?}`], `edges` [`{a,b,w,crossBlock?}`], `clusters`, `selected`, `overrideBy`, `showOverrides`, `whatif`.

**Use:** Use it in the Sociomapa screen's three modes.

**Don't:** Dragging saves a view override; it never edits results. A what-if layer always carries the provisional band, in print too.
