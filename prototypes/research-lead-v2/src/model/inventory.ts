// The prototype's deliverables as data: the in-app documentation view renders
// them and scripts/export-docs.mjs writes them to docs/*.md, so the scenario
// labels and inventories are identical in both places.

export const INSPECTED = {
  aia: { repo: 'AiAnalytics-AIA/AIA', branch: 'develop', commit: '50547cdc8d90a282af1d2e94bcd8e835df7178f9', date: '2026-10-18' },
  owu: { repo: 'open-webui/open-webui', branch: 'dev', commit: 'aa8ce52c7a3afbb164bc16a3b7c20e40ba6390ed', date: '2026-10-19 (dev head when inspected)' },
  canvas: 'https://claude.ai/artifact/KtMSDdqtTuoV53EjmU8mvT (V1 canvas, published earlier in this session)',
  exports: 'The four supplied exports (AIA Research Lead Workbench.html, …boundaries.html, …stages.html, …stages2.html) were not attached to this session and could not be found on disk. They were NOT inspected; V2 builds on the V1 canvas, which this session authored, and on the repository.',
};

export const HIERARCHY: { level: string; what: string; why: string }[] = [
  { level: '1 · Study header (52 px)', what: 'Client › Study, one-line state, synthetic-data chip, pending decisions (only when any), compact budget, research permissions, study menu.', why: 'Where the study stands in one line; everything detailed opens on request.' },
  { level: '2 · Stage navigator (40 px)', what: 'Eleven stages in six phases, one glyph each (shape + colour), current stage marked, "you" stages topped with an amber rule; Lifecycle overview opens the full picture and the dependency notes.', why: 'All stages one click away without a dense bottom rail; status visible without reading.' },
  { level: '3 · Conversation (left, 40 %)', what: 'One Research Lead thread for the Study: messages, single updating activity cards, decision cards, return summary, composer with queue and @ references.', why: 'Directs and explains; links to the artifact rather than repeating it.' },
  { level: '4 · Artifact (right, 60 %)', what: 'Title, state pill (working / proposed / accepted / frozen), the version line (content revision · study revision · run revision), at most one state bar, the purpose-built artifact.', why: 'The work happens here; proposals appear beside what they change.' },
  { level: '5 · Inspector (overlay on the artifact)', what: 'Sources, findings, claims, map objects and pairs, history, inputs/feeds/workers/commands, AI contract, Lead context, research envelope, budget, synthetic limitations. Back stack, Esc closes, focus returns.', why: 'Detail on demand without permanent side panels squeezing the map or document.' },
];

export type CapState = 'implemented' | 'simulated' | 'proposed' | 'unavailable';
export const CAPABILITIES: { capability: string; product: string; v2: string; state: CapState }[] = [
  { capability: 'Brief: objectives, decisions, context, materials, assumptions', product: 'Zadání stage (brief)', v2: 'Brief artifact; materials show data class', state: 'simulated' },
  { capability: 'Brief file intake', product: 'Přidat podklady / workspace attachments', v2: 'Composer attach menu + note in Brief', state: 'simulated' },
  { capability: 'Research questions + coverage (research_trace)', product: 'Plán + Dotazník "Odpovídá na výzkumné otázky"', v2: 'Design: coverage chain per RQ (decision → report)', state: 'simulated' },
  { capability: 'Comparison per RQ (compare_segments)', product: 'research_trace: segments unavailable', v2: 'RQ3 shown as gap; Segmenty module BLOCKED', state: 'unavailable' },
  { capability: 'Questionnaire editor: blocks, routing, formats, tracked sets', product: 'Dotazník stage', v2: 'Questionnaire artifact; inline edit, move, remove, @ reference', state: 'simulated' },
  { capability: 'Protected Sociomap inputs', product: 'sociomap_rating / tracked set declarations', v2: 'Set 1 and Q19 locked with reason; Lead refuses to propose changes', state: 'simulated' },
  { capability: 'Questionnaire optimisation (agent job)', product: 'aia.research.questionnaire_optimize via ResearchAgentJobs', v2: 'Worker activity → proposal with coverage gained/lost/kept', state: 'simulated' },
  { capability: 'Proposal review / accept (APPROVE_GATE)', product: 'ProposalReview, ResearchAgentJobs.accept', v2: 'Proposal bar + inline changes; accept only by a person; stale refused', state: 'simulated' },
  { capability: 'Audience filters + preview (counts only)', product: '/population/audience-preview', v2: 'Audience filters table with counts', state: 'simulated' },
  { capability: 'Audience assumptions + evidence', product: 'not in product (Deep Research proposes design input)', v2: 'Evidence attached to assumptions as a proposal', state: 'proposed' },
  { capability: 'Dimensions with persona topics; unmatched named', product: 'Dimenze stage; dimensions_unmatched', v2: 'Dimensions artifact', state: 'simulated' },
  { capability: 'Sample size, quotas, support forecast, readiness', product: 'Dimenze (size) + Kontrola (readiness, outlook)', v2: 'Sample artifact lists every prerequisite', state: 'simulated' },
  { capability: 'Persona source choice', product: 'Run stage "Kdo bude odpovídat"', v2: 'Sample §4 (panel shown not offered)', state: 'simulated' },
  { capability: 'Run start / cancel / retry; spend confirmation', product: 'ResearchRuns, ADR 0019 gate 2', v2: 'Fieldwork artifact + decision card; no extra confirm under limit', state: 'simulated' },
  { capability: 'Provider wait / park, AWAITING_BUDGET, budget lift', product: 'worker park, resume_budget_wait', v2: 'Fieldwork states + decision card', state: 'simulated' },
  { capability: 'Constant responders flagged, not replaced', product: 'not in product', v2: 'Decision card: keep / flag; replace disabled', state: 'proposed' },
  { capability: 'Results: means 1–10, shares, intervals, Kish n, suppression', product: 'Výsledky · Data (readMeasure, compareObjects)', v2: 'Results artifact; order only where intervals part', state: 'simulated' },
  { capability: 'Sociomap: frozen map, pairs, fit, register status', product: 'Výsledky · Sociomapy (ObjectMapView)', v2: 'Sociomap artifact; pair/object inspector; four-way distinction', state: 'simulated' },
  { capability: 'Sociomap display filters', product: 'view state in ObjectMapView', v2: 'Hide weak / labels / relief, visible filter bar', state: 'simulated' },
  { capability: 'Methodology change', product: 'Settings → Metodika (ADR 0023)', v2: 'Refused in place; routed to versioned methodology', state: 'unavailable' },
  { capability: 'Deep Research (DESIGN / INTERPRETATION)', product: 'DeepResearchRuns, RetrievalGate, ADR 0021/0022', v2: 'Lead requests; AIA validates purpose, class, route, budget', state: 'simulated' },
  { capability: 'Analysis modules + evidence gate', product: 'research_analysis, AdmittedClaim', v2: 'Analysis artifact: coverage, registers, blocked claims, modules', state: 'simulated' },
  { capability: 'Analysis retry round', product: 'POST …/analysis/retry', v2: 'Failed module → new round over frozen data', state: 'simulated' },
  { capability: 'Open-answer qualitative coding', product: 'not in product', v2: 'Proposal of themes with examples; counts from stored classification', state: 'proposed' },
  { capability: 'Internal report draft + approval', product: 'research_report, approve_report', v2: 'Report document; tracked changes; approve by a person', state: 'simulated' },
  { capability: 'Semantic report edits (bounded worker)', product: 'not in product', v2: 'Less technical / emphasis / overstate check as proposals', state: 'proposed' },
  { capability: 'Client report for a fictional run', product: 'client_report_refused', v2: 'Refused with reason', state: 'unavailable' },
  { capability: 'One persistent Research Lead conversation per Study', product: 'not in product (agent jobs per task)', v2: 'Left pane; return summary; history', state: 'proposed' },
  { capability: 'AI Interaction Contract per artifact', product: 'not in product', v2: 'Inspector → Kontrakt AI; data-aia identifiers', state: 'proposed' },
];

export const INTERACTIONS: { action: string; path: 'GUI' | 'Typed command' | 'Lookup' | 'Worker' | 'Deterministic engine' | 'Deep Research' | 'Human decision'; detail: string }[] = [
  { action: 'Open a stage, focus an element, select a map object, open the inspector', path: 'GUI', detail: 'visual.open / select / inspect: never changes research content' },
  { action: 'Apply a display filter on the Sociomap', path: 'GUI', detail: 'visual.filter, logged; artifact unchanged' },
  { action: 'Edit an element by hand', path: 'Typed command', detail: 'working.edit → autosaved working copy; Lead notices' },
  { action: 'Accept a working copy as a revision', path: 'Human decision', detail: 'working.accept (UI only); downstream reopens after a run' },
  { action: 'Lead reads the questionnaire / pair / state', path: 'Lookup', detail: 'read-only card; no cost' },
  { action: 'Optimise the questionnaire; rebuild a stale proposal', path: 'Worker', detail: 'bounded agent job → proposal with baseRev' },
  { action: 'Accept / reject a proposal', path: 'Human decision', detail: 'proposal.accept refuses non-human callers and stale bases' },
  { action: 'Check readiness / coverage', path: 'Deterministic engine', detail: 'readiness, research_trace, outlook' },
  { action: 'Start a run', path: 'Human decision', detail: 'decision card → run.start; spend confirmation only at the limit' },
  { action: 'Aggregate, Sociomap', path: 'Deterministic engine', detail: 'no model; frozen artifacts' },
  { action: 'Analysis modules, report composition', path: 'Worker', detail: 'aia.analysis.module, report per section; evidence gate decides' },
  { action: 'Verify assumptions, contextualise a map pair', path: 'Deep Research', detail: 'request → AIA validates; within envelope no repeat confirmation' },
  { action: 'Budget lift, report approval, keep/flag respondents', path: 'Human decision', detail: 'commands refuse the Lead' },
  { action: 'Change Sociomap methodology', path: 'Typed command', detail: 'refused here; Settings → Metodika (administrator), new run' },
];

export const DONORS: { pattern: string; source: string; adaptation: string; cls: string }[] = [
  { pattern: 'Resizable split with pointer capture, keyboard, persisted width', source: 'src/lib/components/common/ResizableSidePanel.svelte:55-137 (10 px arrows, storageKey), used at chat/ChatControls.svelte:319-327', adaptation: 'Percent split, 2 % arrow steps, Home/Enter reset, double-click reset (AIA addition), never overwritten by focus modes', cls: 'Interaction pattern only · candidate for AIA-native implementation' },
  { pattern: 'Stick to bottom only while at bottom; return-to-latest', source: 'chat/Chat.svelte:5192-5198 (5 px threshold), 3043-3094; chat/MessageInput.svelte:1786-1810 (button above composer)', adaptation: '24 px threshold; button names the unread count', cls: 'Interaction pattern only · candidate for AIA-native implementation' },
  { pattern: 'Load older messages on demand', source: 'chat/Messages.svelte:61, 70-86, 504-517; common/Loader.svelte:10-33 (8 at a time, scroll position kept)', adaptation: 'Explicit "Načíst starší" button, 40 at a time', cls: 'Interaction pattern only' },
  { pattern: 'Queued follow-ups while a response runs', source: 'chat/MessageInput.svelte:231, 1910-1972; chat/Chat.svelte:3117-3121', adaptation: 'Queue above composer: send now (stops current), edit, remove; one at a time, not concatenated', cls: 'Interaction pattern only · candidate for AIA-native implementation' },
  { pattern: 'Escape stops; ArrowUp on empty edits last; IME guard', source: 'chat/MessageInput.svelte:721-727, 2219-2236; stopResponse at chat/Chat.svelte:4488', adaptation: 'Same keys; Stop notes "nothing accepted for you"', cls: 'Interaction pattern only' },
  { pattern: 'Hover/focus-revealed message actions, visible on last', source: 'src/app.css:69-74 (.hover-reveal), chat/Messages/ResponseMessage.svelte action bar', adaptation: 'Copy, why (context), edit; focus-within keeps keyboard access', cls: 'Interaction pattern only' },
  { pattern: 'Collapsible tool activity', source: 'common/ToolCallDisplay.svelte (385 lines), common/Collapsible.svelte', adaptation: 'Activity card typed by actor (worker, research, compute, lookup, decision); one card updated in place', cls: 'Interaction pattern only · candidate for AIA-native implementation' },
  { pattern: 'Grouping consecutive details blocks', source: 'ConsecutiveDetailsGroup in chat/Messages/Markdown/MarkdownTokens.svelte', adaptation: 'Consecutive completed activity collapses to "N dokončené činnosti"', cls: 'Interaction pattern only' },
  { pattern: 'Citations pill and source modal', source: 'chat/Messages/Citations.svelte (249 lines)', adaptation: 'Source chips open the inspector with class, grade, admission, provenance', cls: 'Visual pattern only' },
  { pattern: 'Follow-up suggestions', source: 'chat/Messages/ResponseMessage/FollowUps.svelte', adaptation: 'Follow-ups under the latest Lead answer only', cls: 'Interaction pattern only' },
  { pattern: 'Streaming caret', source: 'ResponseMessage.svelte animate-cursor-pulse', adaptation: 'Caret while streaming; respects reduced motion', cls: 'Visual pattern only' },
  { pattern: 'Artifact "Version x of y"', source: 'chat/Artifacts.svelte:139-168', adaptation: 'Replaced by AIA revision semantics: content / study / run revision', cls: 'Do not carry into production (AIA revisions differ)' },
  { pattern: 'Sibling (branch) navigation x/y', source: 'chat/Messages/ResponseMessage.svelte:155-160, 968-999', adaptation: 'Not used: one canonical conversation; history is revision-aware instead', cls: 'Do not carry into production' },
  { pattern: 'Width modes (widescreen)', source: 'chat/Messages/Message.svelte:67-69; common/InterfaceSettings.svelte:913-929', adaptation: 'Focus modes are an AIA addition; Open WebUI has none', cls: 'Interaction pattern only' },
  { pattern: 'Code', source: '—', adaptation: 'No Open WebUI source was copied; all components are new React code over AIA tokens', cls: 'No prototype code reuse' },
];

export const BOUNDARY: { capability: string; read: string; propose: string; operate: string; invoke: string; prohibited: string }[] = [
  { capability: 'Brief, Design, Questionnaire, Audience, Dimensions', read: 'accepted revision + working copy', propose: 'element ops as a proposal', operate: 'open, focus, select', invoke: 'bounded specialist workers', prohibited: 'accept a proposal; accept a working copy; edit protected items; change methodology' },
  { capability: 'Sample / readiness', read: 'readiness, outlook, forecast', propose: '—', operate: 'open readiness item', invoke: 'readiness check (deterministic)', prohibited: 'override a FAIL; start a run' },
  { capability: 'Fieldwork', read: 'run, steps, cost, quality', propose: 'decision card', operate: 'open', invoke: '—', prohibited: 'start, cancel for you, lift budget, replace respondents' },
  { capability: 'Results, Sociomap', read: 'frozen artifacts', propose: 'interpretation (labelled)', operate: 'select, inspect, view filter', invoke: 'INTERPRETATION_RESEARCH within envelope', prohibited: 'change numbers, pairs, layout, thresholds; feed external evidence into computation' },
  { capability: 'Analysis', read: 'modules, admitted claims, blocked claims', propose: 'coding themes (proposed capability)', operate: 'open finding / claim', invoke: 'analysis worker within run', prohibited: 'admit a claim; approve its own findings; write numbers not admitted' },
  { capability: 'Report', read: 'draft, refs, review state', propose: 'tracked changes per section', operate: 'focus section', invoke: 'section composer, claim check', prohibited: 'approve; produce a client report for a fictional run' },
  { capability: 'Deep Research', read: 'envelope, runs, bundles', propose: 'evidence annotations', operate: 'open envelope', invoke: 'request → AIA validates', prohibited: 'set scope, class, route or budget by its arguments; paraphrase confidential or respondent data into public search' },
  { capability: 'Models', read: '—', propose: '—', operate: '—', invoke: 'only through GovernedModelGateway (bedrock-eu-primary)', prohibited: 'choose a provider; call a model directly' },
];

export const DECISIONS: { id: string; decision: string; why: string }[] = [
  { id: 'D1', decision: 'Local Vite + React app, published as a single-file HTML artifact', why: 'The brief requires real-browser verification at fixed widths; a local app is Playwright-checkable and the same build is shareable. React matches apps/web; tokens are imported from apps/web/src/app/tokens.css, not copied.' },
  { id: 'D2', decision: 'Navigator as a 40 px phase-grouped row under the header', why: 'Keeps all eleven stages reachable in one click; phase labels hide below 1500 px container width so the row never wraps.' },
  { id: 'D3', decision: 'Inspector overlays the artifact (420 px), not a third column', why: 'The map and the report keep their width; Esc / back / close are predictable; focus returns to the opener.' },
  { id: 'D4', decision: 'Artifact focus collapses chat to a 64 px rail; conversation focus is a temporary 68 %', why: 'Neither mode writes the saved split, so a person returns exactly to their 40/60 (or chosen) layout.' },
  { id: 'D5', decision: 'State bars only, never metadata strips', why: 'A proposal (or stale proposal), your working copy, or the frozen-run notice appears only when it applies; inputs, feeds, workers and provenance moved to the inspector.' },
  { id: 'D6', decision: 'Design stages advance the Design Revision; the report advances its own draft number', why: 'Report wording is not a design change; a report edit must not reopen fieldwork.' },
  { id: 'D7', decision: 'Proposal acceptance refuses non-human callers in the command itself', why: 'The UI button and a typed Lead request take the same path; the rule lives in one place.' },
  { id: 'D8', decision: 'Deep Research validated per derived query', why: 'A query derived from class-A material is refused for public search even inside an approved envelope.' },
  { id: 'D9', decision: 'Sample is its own stage, mapped to product Dimenze (size) + Kontrola (readiness)', why: 'The brief\'s 11-stage order; recorded as a conflict with the product\'s 8-stage StageTrack.' },
  { id: 'D10', decision: 'Czech interface, terms in src/model/terms.ts', why: 'Matches AIA; one place for localisation.' },
];

export const CONFLICTS: { topic: string; finding: string; used: string }[] = [
  { topic: 'Stage count', finding: 'apps/web StageTrack has 8 stages (sample size inside Dimenze; Results holds Data, Sociomapy, AI analýza, Zpráva). The brief asks for 11.', used: '11 visible stages; mapping recorded in terms.ts (product field) and the capability inventory.' },
  { topic: 'Sociomap meaning', finding: 'Earlier prototype copy said objects near each other are "rated alike". aia-sociomap-3 distance is co-movement of per-person min-max rescaled ratings; height is the mean.', used: 'The method\'s meaning; "height is never closeness".' },
  { topic: 'Sociomap status', finding: 'Some docs say INTERNAL_ONLY for all methods; the register approves aia-sociomap-3 client-facing (2026-10-13).', used: 'Register status; this run is fictional so internal anyway.' },
  { topic: 'Analysis modules', finding: 'analysis.md lists module ids; domain/analysis/modules.py has executive … limitations.', used: 'The code\'s eight module names.' },
  { topic: 'Open answers', finding: 'No qualitative coding exists in the product.', used: 'Shown as a proposed capability; counts only from stored classification.' },
  { topic: 'Respondent replacement', finding: 'Not in the product; methodological meaning undetermined.', used: 'Disabled alternative labelled proposed.' },
  { topic: 'Audience assumptions + evidence', finding: 'The product has no assumptions object; Deep Research proposes design input.', used: 'Proposed capability over a real purpose (DESIGN_RESEARCH).' },
  { topic: 'Four exports', finding: 'Not available to this session.', used: 'Not inspected; stated as a limitation.' },
];

export const GAPS: string[] = [
  'A persistent per-Study Lead conversation needs storage, retention and summarisation rules; the product has agent jobs per task, not a conversation.',
  'The AI Interaction Contract needs stable semantic identifiers in apps/web (data-aia) and a server-side command registry; both are explorations here.',
  'Assumption objects in Audience, qualitative coding, semantic report edits and respondent replacement are not in the product; each needs its own design and methodology decision.',
  'compare_segments is unavailable; RQ3 and the Segmenty module stay blocked until it exists.',
  'Report proposal kinds (presentation vs design) and draft numbering need a product decision against ADR 0016 revision semantics.',
  'The Lead\'s cost per turn (context size, calls) is unmeasured; a kill switch and budget line are needed before it runs on the hot path.',
  'Accessibility was checked in Chromium only, keyboard and focus by script and by eye; no screen-reader pass was made.',
  'The four supplied exports were not inspected.',
];
