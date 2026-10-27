# Hrdina stránky (Hero)

Top-level pages only (UI-1): Nastavení, Můj Vedoucí, Klienti, a client's workspace, Společenská inteligence, Projektová paměť. An eyebrow in `signal`, the serif title 40/46, a lede (16/24 muted, 62ch), who may change it as chips, then 3–5 figures. Inside a study the compact stage header is used instead.

**Built** `components/aia/Hero.tsx` (PBA4); v2 moves its hard-coded sizes to the tokens `hero-title`, `lede`, `eyebrow`, `figure`.

**Replaces** the plain 28/36 header on the study entry (`ResearchStudy.tsx:26`), the simulation frame (`SimulationFrame.tsx:25`) and a past research (`MemoryStudy.tsx:46`) → the compact header, since they are inside a study.
