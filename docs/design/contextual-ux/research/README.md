# AIA Research · contextual AI assistance (R1)

Variant: `ui_kits/aia-develop/contextual-ux/Research Context.dc.html`
Baseline: `ui_kits/aia-develop/AIA Develop.dc.html` (synced to `develop` @ `33959ec3022b`). The baseline is unchanged.

Fictional prototype data only. All AI calls are simulated; use the Tweaks `aiScenario` (complete / delay / refusal / failure) and `role` (editor / viewer) to see each state.

## Foundation preserved
- Tokens: light and dark token blocks copied verbatim from the baseline (from `tokens.css` / `tokens-theme.css`).
- Fonts: IBM Plex Sans / Mono, Source Serif 4 (self-hosted, `fonts/`, OFL).
- Brand: `assets/aia-mark-on-graphite.svg`.
- Stage editors 2–6, Progress, Sociomap and Sociomapping are verbatim copies of the baseline components (`AIA Develop *.dc.html`). Stage 1 (Zadání) markup and logic are spliced from the baseline shell.
- The three advice actions, which stages offer them, their labels and their behaviour follow `ResearchScreen.tsx`, `useResearchAgents.tsx`, `AgentProposalDialog.tsx` and `research-agent-jobs.ts`. The variant adds no new agents.
- Data-origin banners, pinned run methodology, response-process deviation, intervals, suppression and the internal-only Sociomap notice are kept.

## Change manifest
1. **AI help moved from the footer bar to the stage heading.** A compact AI-accent card next to `h1` shows one primary action, at most two secondary actions, stage-specific question suggestions (prefill only) and the visible context/scope.
2. **AI panel.** It is a nonmodal side panel at ≥1024px, so the workspace and maps stay usable, and a keyboard-accessible dialog below that. It contains: action switch, "Co AI uvidí", question field (critique has a fixed instruction), job status, answer, and "Uložené návrhy AI".
3. **Truthful job states.** saving → running (real elapsed time, no percent or ETA) → done. Also waiting (explicit resume of the same job), failed (refresh only, no resubmit), refused (nothing sent or billed), cancel confirm, cancelling, cancelled, and read-only. One job at a time, and nothing repeats automatically.
4. **Persistence.** The brief draft, typed questions, saved answers, panel state and stage are kept in localStorage. Stage editors stay mounted after the first visit, so their drafts survive navigation.
5. **Results reorganised** into Zjištění / Důkazy / Limity / Další krok.
   - Each finding sits beside two separate blocks: approved client knowledge (with an answer_memory ask that prefills an editable question) and the existing Deep Research interpretation (read-only, cited).
   - The read-only legend/method aside sits beside the Sociomap controls. It states that map values are not sent to AI automatically.
   - Review notes save with immediate feedback. Exports show "request accepted" until the file is ready, with no fake progress.
6. **Accessibility.**
   - Targets are ≥44px.
   - `:focus-visible` outline.
   - Focus moves to the stage title on navigation and into the panel on open.
   - Escape closes the panel and returns focus to the control that opened it.
   - Tab is trapped in the dialog.
   - Reduced motion is respected, and both light and dark themes work.

## Files
- `design-contract.json`: hierarchy, tokens, actions, states, accessibility, responsive rules.
- `component-layouts.html`: reusable markup and styles for the card, panel, job states, finding row and legend aside.
- `research-context-r1.zip`: the variant folder (DCs, support runtime, fonts, logo, map data).

## File manifest
New files:
- `contextual-ux/Research Context.dc.html`: shell, stage heading + AI card, AI panel, job states, Zadání stage (spliced from the baseline).
- `contextual-ux/Research Context Results.dc.html`: results organised as Zjištění / Důkazy / Limity / Další krok.

Copied unchanged from `ui_kits/aia-develop/`:
- Stage and map components: `AIA Develop Plan`, `Questionnaire`, `Audience`, `Dimensions`, `Run`, `Progress`, `Sociomap`, `Sociomapping` (`.dc.html`).
- `support.js` and `object-map.json`.

Foundation assets, copied unchanged:
- `contextual-ux/fonts/` (from `/fonts`).
- `contextual-ux/assets/aia-mark-on-graphite.svg` (from `/assets/logos`).

Exports:
- `design-contract.json`
- `README.md`
- `component-layouts.html`: loads `/styles.css`, so it uses the foundation tokens unchanged (AI accent `--ai #a3319a` / `--ai-ink #8a2783`, dark `--ai #e07ad6`), with a light/dark toggle.

Fixed after review:
- `component-layouts.html` had preview colour overrides that replaced the AI accent with an invented purple. They are removed, and all colours now come from the foundation.

Unchanged: `ui_kits/aia-develop/*` baseline, `/tokens`, `/fonts`, `/assets`, `/components`.

## Open for review
- Answers and knowledge items are illustrative. The real content comes from the agent results.
- Sidebar navigation is static in this variant (research lane only).
- **Next: Settings → Metodika.** The latest methodology supports multiple editable modules. The version editor must cover every editable module, not only the object map. The current baseline Settings restricts it to the object map and will be corrected in that pass.
