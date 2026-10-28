# Přehled studie (StudyOverview)

A study's home page, new in v4. Before it, a study opened on a stage and the whole was readable only by walking eleven stages. It has five parts:
1. **Header**: title, one-sentence goal and decision from the Brief, and two actions: continue where you are, or go to the run.
2. **Numbers**: step, waiting count, runs, the last run's respondents, budget, and what changed since the last run.
3. **Kde studie stojí**: all 11 stages in their 6 phases. Each row shows its status glyph and word, its one-line state, and "změněno od běhu n" where the working copy reopened it (`lib/working-impact.ts`).
4. **Čeká na vás**, **Do běhu n** (readiness checks) and **Peníze**: the four money names, unknown never zero.
5. **Co se ve studii stalo**: the last six ledger and edit-log events, with person or Lead, each linked to its stage.

**On the canvas** as `Overview.dc.html` on Výzkumné kroky; the study header's "Přehled studie" opens it.

**Backend** today's routes cover it: research runs, readiness on the working revision, impact, the study's spend, the operation log. The event list needs the operation log read as a feed; that is NO BACKEND today.
