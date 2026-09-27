# StageRail

The thirteen-stage lifecycle rail and a project's primary navigation.

**The consumer provides:** `lifecycle` (`research` · `simulation`), `stages` (13 × `{status, note?}` from the server, in pipeline order), `current`, `narrow`, `summary`, `onSelect`.

**Use:** Use it at the top of every project screen. `narrow` is for laptops.

**Don't:** Never compute a stage's status in the client. Never hide the glyph; in narrow mode it carries the state alone.
