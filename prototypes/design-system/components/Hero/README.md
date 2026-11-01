# Hrdina stránky (Hero)

Top-level pages only (UI-1): Nastavení, Můj Vedoucí, Klienti, a client's workspace, Společenská inteligence, Projektová paměť. As core v4.3 draws it: the eyebrow in `signal` with who may change it as chips on the same row, the serif title 28/34, a lede (14/20 muted, 68ch at most), then 3–5 figures in a row beneath (36 px apart, label over value, the figure that waits on you in `status-you-ink`), a hairline under the hero (padding 6 / 12 px, 22 px below). Inside a study the compact stage header is used instead.

**Built** `components/aia/Hero.tsx` (PBA4); v2 moves its hard-coded sizes to the tokens `hero-title`, `lede`, `eyebrow`, `figure`.

**Replaces** the plain 28/36 header on the study entry (`ResearchStudy.tsx:26`), the simulation frame (`SimulationFrame.tsx:25`) and a past research (`MemoryStudy.tsx:46`) → the compact header, since they are inside a study.
