# Research stages build spec, 27 Oct 2026

How the approved research-stages prototype maps onto develop: per stage, what the prototype shows, what develop has
today, the build chunks and the backend gaps. Copied from the claude.ai artifact "Research Stages Build Spec"
(version `1793061661-5e96`), which the owner's other account cannot open.

- `spec/00-overview.md`: scope, what is already built, the biggest gaps, owner decisions B1–B6 and the 27 Oct
  decisions, the owner questions and the suggested order.
- `spec/navrh.md`: Zadání, Návrh, Dotazník.
- `spec/vzorek.md`: Cílová skupina, Dimenze, Vzorek.
- `spec/sber-vysledky.md`: Sběr dat (Kontrola, Průběh), the respondent disc, Výsledky.
- `spec/sociomapa-analyza-zprava.md`: Sociomapa, Analýza, Zpráva, the report editor's theme.
- `spec/lead.md`: the Lead pane, the "+" menu, every card type, streaming, files in the chat.
- `index.html`: the reader page. Served over HTTP, it loads each `spec/*.md`; opened as a file, the browser refuses
  the fetch, so read the Markdown directly.

## How current it is

- **A snapshot:** written against develop `bd0d1ad6` (26 Oct) and prototype v78. Every code claim carries its
  `file:line @ bd0d1ad6` anchor, so a stale one is visibly stale.
- **The prototype has moved on:** it is now Výzkumné kroky v95 (the canvas files one folder up, `../`).
- **The plans own scheduling:** where a chunk here became a plan chunk, the plan file in `.planning/plans/` is the
  record of its status; this spec is not updated as chunks land.
