# AI: jiskrový okraj (spark edge)

AI has no colour of its own (the owner, 27 Oct 2026: the iris violet is gone). AI is graphite and a cool neutral, and it is marked by:

- **the spark edge**: a 1 px conic gradient in the identity's light: `spark-1` cyan (brand-apex, deepened for light grounds), `spark-2` sky, `spark-3` an ice glint;
- **the sparkle** (Phosphor `sparkle`) in `spark-1`, or in `spark-3` on the graphite fill.

**When it moves**
- At rest the edge is still: an AI-authored block (a proposal waiting for a decision, the job panel), the secondary AI action, an AI chip.
- On hover and focus of an AI action, the light turns once every 2.4 s (`duration-spark`), with a soft cyan glow.
- While a model works (`aria-busy="true"`, `.ai-spark--working`, a running Lead card), it keeps turning; the activity orb takes `spark-1`.
- Under reduced motion the edge stays and the turn stops.

**Where it lives**
- Product: one definition, `apps/web/src/app/globals.css` (`.ai-spark`, `.ai-spark--solid`, `.ai-spark--wash`, `.ai-spark--working`, `.ai-sparkle`); `AiButton` in `components/rehome/ui.tsx` uses it, and so do ProposalReview, DesignResearchReview, ResearchAssistance and JobPanel.
- Prototypes: core v4.2's AI layer (`.btn.ai`, `.chip.ai`, `.note.ai`, `.agent`, `.lc.ai`, `.lc.run`).

**Never**
- A fill of spark colour, a status, or decoration. Text in an AI block is ink.
- `spark-3` alone as a line: it is the glint only.
- Within ΔE 14 of needs-you: `check-design.mjs` measures spark-1 and spark-2 against `status-you`.
