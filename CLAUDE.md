# CLAUDE.md — standing instructions for AIA

Read this file, then [ARCHITECTURE.md](ARCHITECTURE.md), then
[AGENTS.md](AGENTS.md), before writing any code. Then run
`python tools/progress.py`: every plan's status, from its own front-matter (§4).

These rules are not advisory. They apply to every session, every branch and
every agent working in this repository.

---

## 0. The contract

You are working in someone else's long-lived codebase. Two things are true and
they order everything below.

1. **The repository is the memory.** Nothing you learn survives this session
   unless it lands in code, a test, one of the three documents above, or your
   feature's plan file and PR description (§1, §4). A
   decision explained only in chat is a decision that will be re-litigated in six
   weeks by someone with less context.
2. **Solid over fast.** When you hit a blocker, do not rush to clear only that
   blocker. Step back and ask what the right shape is. A fix that makes the next
   three fixes harder is a loss even when it ships today.

## 1. The document triad

| File | Owns | Rule |
|---|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Layering, boundaries, contracts, enforcement, anti-patterns, CI tiers | The authoritative spec. Read before any change that crosses a module boundary. |
| **CLAUDE.md** (this file) | The project map, the commands, the working rules | What exists, where, and how work is done here. |
| [AGENTS.md](AGENTS.md) | Framework-level gotchas — FastAPI, SQLAlchemy, Alembic, Pydantic, pytest, Next.js | Tool-agnostic. Anyone's agent can use it. |

For the MVP, `.planning/plans/mvp-master-plan.md` is the entry point beside the triad: it says
which plans are the MVP, in what order, who owns which surface and what must be switched on, and
its document map says which file owns which kind of question.

**Keeping them in sync is mandatory — through a docs PR, never inside a feature
PR.** When you add, rename or remove anything they describe — a module, a table,
a route, a job, a config key, a command — the document must change. The feature
PR does not make that edit. It writes the change under **Doc follow-up** in its
PR description, as exact text or a description precise enough to apply without
the author, and a separate, small, docs-only PR applies the follow-ups of one or
more merged feature PRs. The reviewer reads the Doc follow-up alongside the code
diff. **Stale docs are worse than no docs, because they are believed**, so open
the docs PR soon after the merge; until it lands, the merged PR's Doc follow-up
is the record.

**Shared files no feature PR edits:** `CLAUDE.md`, `ARCHITECTURE.md`,
`AGENTS.md`, `.planning/overview.md`, `.planning/open-items.md`,
`.planning/plans/README.md`, and the indexes and status narratives
(`docs/architecture/README.md`, `docs/architecture/adr/README.md`,
`docs/migration/status.md`). Every open PR was editing them, so each merge
conflicted with every other open PR (the hand-resolved file in 24 of the last 60
merges was the retired `PROGRESS.md`, 21 `open-items.md`, 18 `CLAUDE.md`, 16
`ARCHITECTURE.md`). Files that code or a test is checked against are **not**
shared docs and still change with the code: `parity-matrix.json`, the route and
UI function ledgers, the design tokens, and every generated file — a test fails
otherwise.

When you solve a non-obvious framework problem — a race, a silent truncation, a
config that behaves differently under test — record it immediately, with the
wrong version and the right version side by side, in your plan file and under
Doc follow-up; the docs PR carries it into `AGENTS.md`. That file exists because
the same three-hour debugging session was happening twice.

## 2. The map

```
apps/
  api/src/aia_api/          FastAPI. Validates, delegates, serialises.
    config.py               Typed settings + production guards; AIA_AI_RESEARCH_LEAD_ENABLED must be
                            stated in a deployed environment (unset: refused at start), research_lead_on (#561);
                            AIA_DATA_CLASS_GATES (`enforce` | `advisory`, default enforce, domain/deployment.py
                            DataClassGates): advisory makes every refusal made solely because of a data class a
                            recorded pass (residency.ClassAdvisory: the ledger row's note,
                            CallProvenance.class_advisories, the tool event, a step event); unclassified material is
                            judged as Class A; develop only (Compose), refused in staging, production and an unknown
                            AIA_ENV; EU residency, licences, budgets and scope still hold; Brave's search route takes
                            any class there (ToolRoute.any_class_when_advisory; ADR 0008, Amendment 2026-10-21, #594)
    dependencies.py         Composition root: engine, sessions, identity, scope; AudiencePopulation,
                            the population the audience routes read (CZECH_AUDIENCE in every
                            deployment; only the workbench installs another on app.state); RunPopulationDep,
                            the population a new run records (the Czech LIVE; the population double only under
                            AIA_POPULATION_DOUBLE, local and test, RQC10)
    identity/               IdentityProvider protocol: cognito, testing, development
    observability.py        Structured logging, request correlation, secret redaction
                            (aia_core.infrastructure.redaction); tags every error report with the
                            request id; a 500 is reported (AIA_ERROR_TRACKING_DSN, off when unset)
    routers/                health, projects, scope, runs (runs + artifacts under a project; never a
                            research_lead run, its events or artifacts),
                            workspace (clients, a client's workspace, its knowledge and proposals,
                            a study's frame and its working content in AIA, ADR 0015, ADR 0018;
                            GET /clients/{id}/memory/search: project memory, one client's studies;
                            POST /clients/{id}/memory/reuse: a new or empty study from a past design;
                            GET /studies/{id}/workspace/materials: each brief file and link at the current
                            revision with the data class its rule gives it (rule:design, Class B; null when no
                            rule names it), informational only (#586);
                            GET /clients/{id} carries the tabs' counts (archived studies out, the
                            knowledge counts null without VIEW_CLIENT_KNOWLEDGE) and the client's
                            effective self_approval_allowed / _source; each listed study its
                            knowledge counts (approved, proposed, rejected); the knowledge's
                            folders and labels (list, create, rename or recolour, delete), PUT
                            …/knowledge/placement, GET …/knowledge?folder=…|unfiled&label=…; the
                            overview's stale_items, unfiled_items and recent_changes; a SOURCE,
                            DOCUMENT or DATASET item names its client's source as
                            content.source_id (422 unknown_source for any other; a study's
                            proposal names none), and a proposal answers its source_id and, from AI,
                            its from_source (the document, run, quote and locator; #446); GET/PUT
                            /clients/{id}/profile (the profile, its contacts, its history),
                            POST /clients/{id}/contacts, PUT/DELETE …/contacts/{contact_id}; a knowledge decision
                            naming a revision for a new item is 422 no_revision_to_review, 409 knowledge_proposal_stale
                            details carry reviewed_revision, and revisions and proposals answer author, decision and
                            reviewed_revision (revisions also base_revision, evidence, sha256; lifecycle K3)),
                            client_sources (a client's sources, lifecycle K2: POST/GET
                            /clients/{id}/sources -- 201 when new, 200 with created: false for the
                            same bytes again -- GET …/{source_id} with its reading (a dataset's
                            columns in reading.dataset), GET …/{source_id}/original, always an
                            application/octet-stream attachment; POST …/{source_id}/reading reads a
                            source again with its format's current reader, OI-110; POST/GET …/{source_id}/proposals:
                            AI proposals from a document as the client's own work, one run per reading, asked again
                            only when no paid call is uncertain (restartable); a table refused by name, 422; #446;
                            PUT …/{source_id}/internal ({internal: bool}): mark a source "Interní dokument" or
                            unmark it, PROPOSE_CLIENT_KNOWLEDGE, audited; every source answers
                            internal: {by, at} | null),
                            session (AIA's own session + the gate in front of /app: any active
                            member, ADR 0018), research (a study's Design Revisions, readiness, runs, their steps and
                            artifacts (ADR 0016; GET …/research/runs lists each run with its steps, without
                            their attempt history: no start time, error or cost), the budget lift for a step
                            stopped at the study's cap, and POST …/runs/{id}/budget: the run's budget lift, every
                            step waiting for budget released as one decision (CR-3); GET …/research/limits: the
                            readiness limits in force, the valid n the web refuses outside of (RQC9);
                            POST …/runs/{id}/analysis/retry (a finished run's failed analysis modules
                            asked again over its own collected data) and GET …/analysis/retryable
                            (read from the outcomes as stored), each step's analysis_outcome,
                            readiness with the run's cost ceiling and the study's spend limit (and
                            question_outlook: every item's verdict before a run; research_trace: each
                            research question traced to its measures), and native
                            agent-jobs beneath each Study, with their event feed (…/agent-jobs/{id}/events?
                            since=; a step names the step_id its events carry), each job's proposal_state
                            and rebuild_of (?pending=true: only proposals still waiting), …/dismiss (a
                            ledger row) and …/rebuild (asked again on the newest revision); POST …/agent-jobs and …/rebuild take
                            confirm_cost_usd, and a new job whose reservation reaches the study's threshold is 409
                            cost_confirmation_required (LO15); GET …/design/source: where a reused design
                            came from; a run's reports: GET …/report, …/report/download,
                            …/report/pdf/download, …/report/context/download (stored, names its
                            artifact), …/report/client/download (a modelled run's client report;
                            409 client_report_refused otherwise), POST …/report/approve (a stored
                            report of the run, once), GET …/report/document (the internal draft's stored
                            document model, beside its DOCX: sections and blocks by their stored ids, the
                            ledger's printed text; 409 report_document_not_stored before RD5a),
                            GET …/report/client/document (the stored client report's, composing nothing; #584);
                            GET …/research/sociomap-register); readiness and start take
                            persona_source (readiness answers persona_sources: each offered or not, why, the default;
                            an unoffered one is 409 persona_source_unavailable, never swapped) and a run its selection
                            (what its design selected and what reached its respondents: dimensions and filters await
                            a population draw; dimensions_unmatched: ids that name no persona topic; #439, #447),
                            lead (the caller's Research Lead conversation in a study, ADR 0026:
                            GET/POST /studies/{id}/lead[/turns]; POST …/turns/{turn_id}/edits (accept
                            or dismiss under APPROVE_GATE, one transaction, ledger lead_edit);
                            POST …/turns/{turn_id}/request (an agent job behind the spend limit,
                            ledger lead_job_request); POST …/turns/{turn_id}/self-update (what would
                            reach every client, on the researcher's yes; ledger lead_self_update);
                            GET/POST /lead: the researcher's own Lead, read-only files and notes,
                            hatching; PUT /lead/preferences: auto_accept_text_edits, the caller's own,
                            audited; …/edits takes auto: true (422 auto_accept_off unless the caller's
                            preference is on; text edits only, any other refused not_a_text_edit;
                            409 stale_turn when the working copy moved under the turn; ledger
                            "auto": true); GET /studies/{id}/lead answers worker_ready (null unknown; false
                            with worker_reason from the caller's newest turn parked for the worker's
                            composition; never true until LO12b) and worker_ready_source;
                            POST …/turns/{turn_id}/request is 409 research_lead_disabled for a card the Lead's
                            model prepared while the Lead is off (Q42), stored edits staying decidable (#561);
                            a message that is exactly a typed start command (domain/lead_commands.py) is stored
                            as the person's command, Lead on or off, with no model turn, and
                            POST …/turns/{turn_id}/request starts it (ledger chat_start, the wallet when on);
                            GET /lead lists commands (#574); research.py's run_start_settings and
                            run_start_errors are shared with the Lead's typed run),
                            deep research (a Study's Deep Research
                            runs; Interpretation Research's start, POST …/deep-research/runs/
                            interpretation, over a result of the Study's own run; POST …/runs/{id}/
                            sources/{source_ref}/knowledge: "Ověřeno, přidat zdroj", a captured source
                            a person checked added as a SOURCE item from the sealed bundle, once per
                            client and URL or final URL (200 exists otherwise); a proposal where the
                            client or the Study has self-approval off; POST …/deep-research/quote: the
                            ceiling by kind, priced routes, missing live settings, threshold, budget,
                            start_verdict and whether a run would park (read-only); every new run stores
                            cost_ceiling_usd, threshold or not, #555), scope
                            (PUT /studies/{id}/spend-confirm sets the limit; any member creates a
                            client, its status stays the Admin's; PUT /studies/{id}/budget sends the study's
                            Lead turns parked at the cap whose hold now fits, lifted in the ledger under the person
                            who set it (Q39); a study's status change goes through application/wallet.py
                            set_study_status), wallet (GET/PUT /studies/{id}/wallet, Peněženka; off: available false,
                            409 wallet_disabled; 409 above_client_ceiling naming OWNER/ADMIN, above_study_budget),
                            settings (the read-only settings document: every control and how it is set;
                            the access group states membership_is_access and offers no grant;
                            ai_runtime, what powers AIA's model calls from code (the study Lead an
                            activity of its own, study_lead); ai_history, the
                            prototype's provider fields, readable and never offered),
                            methodology (the Metodika tab, ADR 0023: GET the catalogue, a module and
                            its versions, POST check and compare (any member); POST versions and PUT
                            activation (an organization OWNER or ADMIN)),
                            population (GET /population: the registry, read-only, any member;
                            status derived, never stored; GET /population/versions/{id}/
                            characteristics: a version's weights, blocks, fields and subpanels;
                            GET /population/audience-catalogue: LIVE's kept factor catalogue and the
                            18 subpanels as filters, reading no row; POST /population/audience-preview:
                            what filters select in LIVE and whether n can be drawn, and each filter alone
                            (per_filter, #580), counts only, 503 without AIA_POPULATION_ASSET_ROOT, the API's one population read;
                            an owned child listed and readable only within its organization, with its
                            materialized outcome: target beside achieved, target_met never presumed),
                            materialize (POST/GET /studies/{id}/population/materializations: a
                            client's dimension materialized from a study, refused by name (422), an
                            unresolvable LIVE 409; the study's runs and each child's outcome)
    schemas/                Request/response models + the one error contract
  web/                      Next.js 16 / React 19 / Tailwind 4. /login + /logout, the live /studies
                            pages, and /app: AIA, client-first (ADR 0015); no mock data. Nothing of
                            18.6.6: no hand-off, no skin, no call to the unit (ADR 0018)
    src/app/app/            AIA behind AIA's own gate (no switch): /app/clients (home),
                            clients/<client>/{research,simulations,knowledge,data,profile},
                            clients/<client>/research/<study>/<stage>, clients/<client>/memory/<study>
                            (a past research, read-only), intelligence, memory, settings, lead
                            (Můj Vedoucí: the researcher's Lead, its SOUL, USER and notes, read only;
                            they change only through chat; the toggle that accepts its text edits
                            automatically)
    src/app/classic/        The public page an old /classic link lands on: 18.6.6 is gone, the way in
    src/components/aia/     The client-first shell: AppShell (four global items, breadcrumbs, one
                            action, tabs; a `track` puts it in study mode: icon-only global
                            navigation, a one-row header, the title in the page), the client
                            workspace and its areas (clients/: StudyList, Výzkumy and Simulace as a
                            table with status filters and two orders; KnowledgeArea, the library:
                            views, folders, labels, kinds and the open item, opened on
                            ?view=review|unfiled|old, ?add=1 and ?item=<id> (one item opened),
                            read with useSearchParams; its
                            text form is Napsat znalost;
                            KnowledgeLibrary, its table, bulk bar and the open item with its
                            history, filing by menu and the search debounced (300 ms); KnowledgeOrganizers:
                            the library's folders and labels as rows: chosen by the row, renamed in place (F2,
                            double click, ⋯ menu), a label recoloured by its swatch, "+ Nová složka / Nový
                            štítek" rows; deleted at once with Vrátit (items read first, re-created and
                            refiled), or asked at the row when undo could not be whole; focus back on a
                            renamed row after the render that mounts it (#569, #596); ClientOverview, Přehled opening on Čeká na vás; ProfileArea,
                            the details, contacts, brands and competitors as ENTITY knowledge, the
                            self-approval rule and the history; SourceFile: SourcePicker, one file
                            kept as the client's source with its reading in words, and
                            SourceCard, a named file, what was read and the original, and the
                            "Interní dokument" toggle (what it does; who marked it, when); IntakeSheet:
                            Přidat podklady, the client's one way in for files, on every area via
                            IntakeButton or a drop anywhere on the client's page (ClientContext
                            holds intake / openIntake / added): each file kept and read at once,
                            its row in words; a table as Datová sada or Dokument with its personal
                            columns named, reading until they are in; pasted text; one knowledge
                            item per file, filed in folders and labels (filing finished on a
                            retry, never made twice); links and AI extraction say V AIA zatím
                            není), ResearchStudy
                            (a study's frame; its content loaded by the study's id), useResource
                            (404 = nothing here),
                            settings/ControlPanel (eight task-based tabs, searchable reference/audit/studies,
                            optional technical details and protected policy drafts; settings-guide.ts
                            explains each setting and its scope; every control from GET /settings, how each is set;
                            live forms over the admin routes with the signed-in token, lib/api.ts `admin`;
                            the one AI section: ai_runtime beside /config's switches, never "connected"),
                            settings/MethodologyPanel (the Metodika tab: searchable modules and grouped steps, formulas
                            as MathML via Temml, every value with its origin), MethodologyVersions (in
                            force, stored versions and what each changes, activation with a reason,
                            history; for an administrator the editor: one section at a time with original values,
                            draft replacement guards, fresh check/compare results and optional expert formula
                            slot, the domain's check at the field) and MethodologyComparison (an edit
                            beside what is in force on fictional panels or support cells); lib/methodology-edit.ts is
                            the editor's pure part,
                            FrontDoor (the Graphite frame of /login, /logout, /auth/callback; the
                            identity's cyan, `brand-apex`, is the signal there)
    src/components/ui/      The input standard's shared controls (input-interactions I1-I11): InlineText,
                            Stepper, ChoiceChips, InlineCreateRow, SwatchPicker, MenuButton, UndoToast (useUndo),
                            SpendDialog (the one modal for money: four kinds, four sums by name, the ceiling "horní
                            mez, ne odhad", unknown never zero); parts.tsx: their shared classes, SaveNote,
                            useDismiss, POPOVER_END, menuSide; InlineText autoOpen / onSettled, InlineCreateRow
                            adornment (#569). Their pure rules in src/lib/: number-input.ts (a bounded number read, never
                            clamped), name-input.ts (organizer_name / organizer_key at the row, length in code
                            points), roving.ts (arrow keys in a group), inline-edit.ts (isThenable), spend.ts
    src/i18n/cs.ts          The copy module; `money`: the four money names written once (Rozpočet klienta,
                            Rozpočet studie, Peněženka, Práh potvrzení; D-01), held to the server's by
                            tests/fixtures/money/vocabulary.json
    src/components/brand/   Wordmark and LatticeField: the identity inline, in currentColor + --signal;
                            ActivityOrb: the thinking-orbs package (MIT, plain canvas), shown only while
                            the API reports a step RUNNING, tinted --ai-ink when a model works on it and
                            --status-running when code does; aria-hidden beside the status it decorates.
                            64 px in a running step's panel and the job dialog, 32 px by default.
                            DotField: the front door's 144-dot field (lib/dot-field.ts, pure) on a
                            full-viewport canvas; on a sign-in the person started (lib/liftoff.ts)
                            25 primes fly into the mark at the launch film's frame-0 geometry
                            (lattice, checked by tools/film_frame0.py) and `aia:mark-formed` fires;
                            LaunchFilm then plays public/skin/brand/aia-liftoff.{webm,mp4}
                            full-screen on `brand-stage`, takes over on its first frame, and its
                            end is the way in
    src/components/workbench/  The research workbench (ADR 0026), the study screen behind
                            AIA_WEB_RESEARCH_WORKBENCH (read by /config; off by default, on in the
                            develop Compose file; the workbench serves at every width: the split from
                            1100 px, the Lead as a side drawer from 768 px and a full-screen sheet below (one
                            tree, D21); with the switch off the classic layout serves (#592); below 1100 px
                            the launcher (the rail, a bottom bar under 768 px) opens LeadPane as a modal
                            drawer or sheet: Tab kept inside, Escape back to the launcher; "@" and a turn's
                            focus step it aside (Zpět k Vedoucímu); the launcher's dot and name carry
                            lib/lead-availability.ts (#595); never an alternate AI start): the frame ported from the research-lead prototype
                            (workbench.css scoped under .wb over tokens.css; study header, phase
                            navigator, artifact header and bars) over AIA's own stage screens;
                            Split (the conversation / artifact split); Glyph / Icons; LeadPane (the
                            researcher's own Lead: hatching, greeting, messages queued while it works and
                            held for "Zkusit znovu", edits accepted or dismissed through …/edits, a
                            prepared job approved through …/request, a cross-client change on "Pamatovat
                            si"; a waiting change saved before a message goes, beforeMessage); with the
                            researcher's toggle on, a turn's text edits accepted through …/edits with
                            auto: true and shown "Přijato automaticky" with Vrátit (the replaced wording
                            written back as the person's own edit, once the copy holds the accept),
                            structure still waiting); SampleView (Vzorek, read only: links to where n,
                            dimensions and audience
                            are set); LeadCards.tsx (lib/lead-cards.ts): every design job and research run
                            as a card in the Lead's conversation (title, state pill, facts, actions, orb), the
                            prepared research run an approval card that starts through POST …/research/runs;
                            ResearchContext.leadOwnsAiStarts: in the workbench the stages show no AI start of
                            their own, Návrh's answers and comments save only and "Požádat Vedoucího"
                            (rehome/research/AskLead.tsx) asks the Lead (#550)
    src/lib/workbench-stages.ts  The eleven stages in six phases, each today's route (and on Výsledky
                            ResultsWorkspace's hash); a stage's tone is the lane's.
                            workbench-split.ts: the split's rules (28-62 %, 2 % per arrow, focus modes);
                            inspector-stack.ts: the item drawer's back stack, display state only;
                            guarded-navigation.ts: every way out of a stage is a link click, so a stage's
                            leave guard can stop it; lead.ts: the Lead's turns and closed output, the
                            pure part of its edit tools (isTextEdit, the server's is_text_edit), focus
                            targets to and from the stages' data-aia ids; applyLeadEdit mirrors the
                            server's apply_edit, held to it by tests/fixtures/edit_ops/cases.json (reason: the
                            server's refusal word); leadReasonWords (a turn parked on the budget, one replaced).
                            workbench-layout.ts: the workbench's layouts by width (split ≥ 1100 px, drawer
                            768-1099, sheet < 768), the drawer's states and the one Escape order (D21);
                            lead-availability.ts: the Lead's availability from GET /lead alone (ON / WAITING / OFF /
                            UNKNOWN; unknown never on) and its words.
                            workbench-artifacts.ts: the Lead's per-artifact contract for the screens
                            (domain/lead_artifacts.py's, held to the same fixture); aiaId(kind, id) / parseAiaId,
                            the one builder of data-aia="<kind>:<id>" (#563)
    src/components/rehome/  Primitives (token utilities only) and the research stages, re-homed
                            under the shell above
    src/research/           The research flow's logic ported from ui_app.html (parity-tested under
                            Node): model, the ten steps, the job panel's words, and the store that
                            loads and saves a study's working content in AIA (1.8 s save, visible
                            state, a stale save refused and said, ADR 0018); plan-edit.ts keeps direct human
                            proposal edits consistent in native research_plan and legacy analysis;
                            trace.ts: which research question each questionnaire item measures
                            (researchQuestionsOf, as the server reads them; the link read and toggled),
                            "Odpovídá na výzkumné otázky" on every question and tracked set in Dotazník;
                            comparisonOf / setComparison ("Jak výzkumné otázky zodpovíme" in Dotazník);
                            proposedTrace (a proposal's links, read on the inline review); coverageOf:
                            Dotazník's strip, the items a respondent answers and per stated research question
                            the items that declare they measure it; unknown until an item declares a link (the
                            server's linked), never a gap; QuestionnaireStrip.tsx draws it (#585);
                            proposal-items.ts: a stale_proposal refusal's conflicting items in Czech;
                            the store's reload (after an accept; reload(read, { since }) reads an
                            accepted revision in place, a change typed meanwhile kept, the copy in
                            conflict), conflict(current) (a copy that moved
                            while an accept was in flight), completed (a copy the template's defaults
                            completed on load) and submitWorkingDesign (saves such a copy, then submits
                            the revision it names); flush resolves only once the copy is saved, edits made
                            during the flight included: saves serialised, each from the revision the previous
                            returned; at most MAX_FLUSH_ROUNDS, then FlushIncomplete, the change kept pending
                            (#556, OI-182); the store keeps stable item ids behind
                            AIA_WEB_STABLE_ITEM_IDS (/config stableItemIds, off; item-ids.ts, the port of
                            domain/item_ids.py); persona.ts: the sample input refuses outside the server's range,
                            never clamps (IA-1); scale-labels.ts: a scale's range and labels, the server's
                            rule at the field (presets, readRange, rescaleLabels, endsOnly, describeEveryPoint,
                            labelProblem), ScaleEditor's pure part (#559); readers.ts: what reads each
                            questionnaire item downstream (Sběr dat, Výsledky, Sociomapa, Analýza, Zpráva) over
                            the working copy, by the compiler's and the Sociomap's rules, each cited; what an
                            item feeds once it compiles, never a verdict; QuestionnaireDependencies.tsx draws it
                            as Dotazník's Závislosti (#572); brief-materials.ts: the Brief's materials, signed only when
                            present (briefFingerprint), never an eligibility
    src/testing/legacy.ts   Parity harness: a function's effective binding, run in a Node vm (reads
                            the vendored ui_app.html: reference only, never product code)
    src/lib/app-routes.ts   Every /app URL, built in one place (stage slugs: `persona` is `dimensions`;
                            knowledgeItem: one item opened on Znalosti)
    src/lib/api.ts          The API client; a stored report's download (requestStored) reads
                            X-AIA-Artifact-Id / X-AIA-Review-State, so the report approved is the
                            one downloaded; deepResearch.designProposal, deepResearch.runs(studyId, limit?),
                            deepResearch.start(studyId, revisionId, confirmCostUsd?)
    src/components/rehome/research/  The stage frame (StudyFrame: client, study, rights):
                            StageTrack (every stage with its state, Průběh a stage of its own),
                            Inspector (InspectorProvider / InspectorSlot: a stage's readiness beside
                            it, then AI pomoc, then "Do spuštění zbývá"), save state, job panel, the
                            shared brief analysis (useAnalysis), one screen per stage; ProposalReview
                            (a design proposal reviewed inline, its changes listed; a questionnaire
                            proposal's research questions, their measures and answers, before it is
                            accepted; accepted on the server, then the working copy reloaded; "Zahodit"
                            and "Navrhnout znovu"); CompleteReport
                            (the report card on Výsledky: a part claimed only when the run's steps
                            made it; its origin part reads the run's origin kinds (fictional,
                            modelled, unknown, mixed; originWords), never a fixed "Modelovaná data";
                            the one place a run's report is downloaded -- internal or, for a
                            modelled run, client; DOCX or PDF -- and approved, the document approved
                            being the one downloaded); the internal report panel below shows its
                            provenance only; InterpretationResearch approves the report with
                            literature it downloaded and shows the bundle in full: numbered accepted
                            findings with their source class, the sources, gaps and rejected
                            findings with their claims and reasons, and the unapproved draft by
                            section, each finding naming the accepted findings it rests on, then
                            what the checker refused; VerifiedSourceButton (lib/verified-source.ts,
                            pure): "Ověřeno, přidat zdroj" beside a captured source on the Design
                            Research panel, the Interpretation Research findings and each research
                            question's design evidence, then what the server did (added, waiting
                            for approval, already there) with a link to the item; DesignResearchReview: a
                            completed Design Research run's proposal, reviewed on Dotazník, its ticked items
                            accepted through POST …/design-proposal/accept, then the working copy reloaded
                            (lib/design-research-review.ts its pure part: readProposal, acceptBody, refusalWords;
                            lib/api.ts deepResearch.acceptDesignProposal; #554); ScaleEditor: a scale's range
                            and labels on Dotazník (presets 1–5, 1–7, 0–10, 1–10 or Vlastní with two bounded
                            steppers, the two ends or a label on every point edited in place, labels the server
                            would leave out said, a range change that clears labels undone by "Vrátit"; a
                            tracked set its two ends only, OI-184; #559); AnalysisCoverage.tsx: Analýza's
                            research-question table and milestones (lib/analysis-coverage.ts, #575); FormattedText: a
                            model's long text as
                            paragraphs and lists (result-reading.ts textBlocks); ProposalEditor and PlanStep edit the research narrative
                            and whole comparable measurements with live previews, preserving existing
                            questionnaires (PlanStep tests: direct proposal editing); ExecutionSteps.tsx: Run, Progress, Results (ADR 0016);
                            the Run stage's "Na co běh odpoví" card (every item's verdict, worst first) and
                            its "Výzkumné otázky a jejich měření" card (each research question, its
                            measures by their wording, stale links); Progress follows the run an
                            action answers with (?run= rewritten, read again at once, the poll
                            restarted), so a retry's steps move on screen; Results' Data: measure
                            cards in questionnaire order, each read in words, a comparison per rated
                            set, each rated set as a table (mean, interval, band, Kish n; a suppressed object's
                            row says why, no number; #566, OI-190), #measure-<id> opens one; its analysis: Hlavní zjištění across
                            modules first, each finding with the numbers it cites linked to Data,
                            then every module's full text; the trace card shows, under each research question, what
                            the newest finished Design Research run found (design-evidence.ts); the Run stage's
                            "Kdo bude odpovídat" (the persona source, the default preselected, an unoffered one
                            disabled with its reason) and "Kdo odpovídal" on Progress and Results (the source pinned
                            beside the data's origin, the population, each selected dimension and filter applied or
                            not, unmatched dimensions named); the report card names what holds it back (reportHolds)
                            and links to Progress;
                            RunResults, one run's results from the StudyFrame alone (read-only when
                            canEdit is false). DesignSourceNote: on every stage of a reused study, its
                            source study and revision and the labels it carries.
                            ResultsWorkspace.tsx: accessible views of one frozen research run;
                            switching data, maps, analysis and report retains the camera/review choice,
                            changes no result and starts no additional run.
                            The audience step's factor editor, feasibility preview and built-in
                            subpanels come from AIA's population (the two /population audience
                            routes; without them the step says why); special panels, own audiences
                            and panel factors say "V AIA zatím není" where they are met.
                            The Run stage offers the study's client's materialized children
                            ("Populace běhu"; LIVE by default) and sends the one chosen
    src/lib/result-reading.ts  How a run's results read in words, pure: readMeasure (an order
                            only where 95 % intervals part, audit F9; a missing interval unknown,
                            never ordered), compareObjects (a set's objects on their scale, the top
                            and bottom groups, suppressed ones named; withheld: each object without a number,
                            with its reason, donors and Kish n), measureTarget / setTarget / objectTarget: the
                            Lead's focus ids on the Data view (#566), citedMeasure (an analysis
                            claim's evidence_ref resolved to its measure), textBlocks (a model's
                            long text as paragraphs and lists, every word kept), untitled (a measure
                            without stored wording titled in words, never by its id)
    src/lib/run-state.ts    runState(run): one research run's state (RUNNING, WAITING, NEEDS_REPAIR,
                            EVIDENCE_UNAVAILABLE, RESULTS_READY, REPORT_READY, CANCELLED; UNKNOWN for an
                            ended run read without its steps) with its reason in words, and
                            runDestination; the run list, Progress, Results, project memory and the stage
                            track (lane.ts runLane) read it
    src/lib/reason-words.ts  A stored code in words (codeWords, codedText, known; the code of one with
                            no words kept, inline or under details), a Deep Research step's name and
                            reason (deepStepLabel, stepProblem), coverageWords;
                            components/rehome/research/CodedWords.tsx
    src/lib/budget-line.ts  What remains of a study's budget beside what an action can cost (budgetLine,
                            withBudget: read as a confirmation asks; unknown never zero; open holds not
                            counted, said so), on every start, retry, analysis retry, Deep Research start
                            and budget lift; holdsNote: beside a lift, open holds are not in the remainder
    src/lib/report-status.ts  One rule for a run's internal report (reportStatus: NONE, COMPOSING,
                            NOT_MADE, FAILED, REFUSED, DRAFT, APPROVED, UNKNOWN; reviewStatus;
                            approvalRefusal), read by CompleteReport, the internal report panel, project
                            memory's runLabels and Interpretation Research
    src/lib/research-agent-jobs.ts  Native Study jobs: enqueue/follow; proposal review and reload
                            live in useResearchAgents.tsx. No classic provider probe. agentJobState: a job
                            waiting for budget waits, never a failure; the stage shows the study's lift for the same
                            job (CR-2)
    src/lib/research-execution.ts  How a run's state and results read: suppression hides numbers,
                            fictional data is labelled every time, the park is explained;
                            originKind / resultOriginKind: the API's three-way reading of an
                            origin (fictional, modelled, unknown -- never fieldwork), the one
                            every screen's label uses; needsRepair: an analysis step that
                            succeeded with its module stored BLOCKED ("Potřebuje opravu", never
                            "Hotovo"), which reportHolds names as holding the report; traceMeasures:
                            a research question's measures in words, a tracked set once (an unlisted
                            measure's id kept as code, never its text); respondentReceipt: the
                            pinned persona source beside the fieldwork data's origin, a mismatch named, never resolved
    src/lib/design-evidence.ts  What the newest finished Design Research run found per research
                            question (latestDesignRun, questionEvidence: findings, a gap or not studied, every rejection
                            by reason); external context for the design, never respondent evidence
    src/lib/analysis-coverage.ts  Analýza's research-question coverage, pure: coverage (each research
                            question of the run's frozen design with the research-questions module's answer, a
                            gap recorded at start, the findings citing the same measures; a BLOCKED module never
                            an answer; an unread design never a list), findingsOf, findingAnchor;
                            components/rehome/research/AnalysisCoverage.tsx the table and the milestones (#575)
    src/lib/material-class.ts  A Brief material's class in words (classLabel; unknown never C) and the
                            server's answer matched to an attachment (classOf); BriefStep's Podklady chip (#586)
    src/lib/source-proposals.ts  AI proposals from a client's document as the web follows them;
                            components/aia/clients/SourceProposals.tsx: "Navrhnout znalosti" on a document's item
                            (paid by the client, the budget lift, Ke schválení); the intake sheet's "Navrhnout znalosti
                            z textu" is live; Ke schválení shows an AI proposal's quote and locator
    src/lib/population.ts   How Společenská inteligence reads the population registry (summarize,
                            labelOf, shortSha); read-only. children / clientChildren / sharedVersions /
                            targetVerdict / outcomeValue: an organization's materialized children,
                            listed on their own with target beside achieved, unknown never met.
                            components/aia/PopulationCharacteristics.tsx:
                            a version's weights, blocks, the 18 subpanels and every field's uses
    src/lib/knowledge-library.ts  How the client's library reads its views: the year rule
                            (YEAR_MS, the API's STALE_AFTER), the 200-item cap (RESULT_CAP), selection,
                            nextLabelColour, undoable (#569); study-table.ts
                            the studies table's filters and orders
    src/lib/intake.ts       The intake sheet's pure part: rows, their words, items, placements
    src/lib/client-sources.ts  How a client's source reads on its knowledge: the kinds that take a
                            file (FILE_KINDS), sourceIdOf / withSource, the reading and its
                            locators in words (readingLine, locatorWords, reasonWords)
    src/lib/memory.ts       How project memory's search reads (sendable, ofKind, evidence);
                            runLabels (a past run's data, report, reach: unknown never good),
                            designSummary (what a past design says, as the search reads it),
                            sourceLabelWords. components/aia/MemorySearch.tsx: one client's search, on
                            Projektová paměť (a client chosen first) and on the client's Výzkumy;
                            components/aia/MemoryStudy.tsx: a past research read-only (revisions, the
                            chosen one's design, its runs with their labels, a run's results under a
                            frame that may not edit) and "Použít tento design"
    src/lib/activity-orb.ts  Which running step shows which orb, and whether it is AI (the steps
                            that hold a model caller): agent jobs, run steps, Deep Research steps; a
                            queued, waiting or finished step shows none; researchStepWork: whether a run's
                            step calls a model, at any status (unknown: null); the step tag on Průběh and
                            data-aia step:<node_key> (#567)
    src/lib/step-activity.ts  A run's events folded into words per step: only what an event says
                            (counts as reported, never a percentage; tokens a provider did not report
                            are unknown, never zero). components/rehome/research/useStepActivity.ts
                            reads the feed after its cursor every 1.5 s while a step runs, once more
                            when it stops; StepActivityPanel.tsx opens under a RUNNING step (64 px orb,
                            latest report, counts, elapsed, a polite live log) on Progress, the job
                            dialog, Deep Research and Interpretation Research
    src/lib/ai-runtime.ts   How Settings reads an AI activity: on in configuration, off and by which
                            switch, invalid (the worker will not start), unknown -- never verified
    src/lib/public-config.ts  Public config type, runtime switch vocabulary and class parser;
                            /config reads server values at request time, never credentials
    src/lib/error-tracking.ts  The browser's error reporter: started from /config's errorTracking
                            (AIA_WEB_ERROR_TRACKING_DSN; none, nothing is loaded), @sentry/browser
                            through error-tracking-sdk.ts by dynamic import, the same scrubbing as
                            the backend; components/errors/ (ErrorTracking, PageError) and the
                            app/global-error.tsx + app/app/error.tsx boundaries report a render crash
    src/research/lane.ts    Each stage's state from the study's working content and runs (no new
                            rule: Kontrola's server readiness stays the authority); proposal-diff.ts:
                            a proposal's changes against the working content (occurrenceKeys, the
                            server's occurrence_keys; held to it by proposal-diff.items.test.ts)
    src/lib/object-map-view.ts  The contract-3 object map read from its artifact: mapApproval (a map's
                            approval in the Sociomap register, by the method its run recorded; an
                            unread register is internal); ten display terraces
                            on the absolute 0-1 scale, mapLinks (the one link rule), pairDetail (UNKNOWN
                            with an r apart from an undefined r), mapFrame, screen-space label placement
    src/lib/object-map-3d.ts  terraceLayers (terraces cut from the stored mesh at the band thresholds) and
                            the framed orthographic camera; presentation only, no kernel or relation maths
                            (object-map-boundary.test.ts). ObjectMapTerrain.tsx draws 3D; ObjectMapView.tsx
                            is the approved design's workspace: top view first, 3D unmounts, relief,
                            rotation and opening choreography as display state, an internal PNG snapshot
    src/design/tokens.json  The design system's ONE source: colour, type, spacing, radius, motion
    scripts/build-tokens.mjs  tokens.json -> tokens.css, tokens-theme.css, fonts.css, tokens.ts,
                              and aia_core domain/report/print_tokens.py (the report's print register)
    scripts/check-design.mjs  Contrast, chart-palette and client-accent evidence, re-measured; § 4 the
                              object map's viz-terrace-1..10 ramp (adjacent and CVD ΔE floors) and the
                              contrast of its stage, labels, links, pins and fit badges
    public/skin/            Self-hosted fonts (OFL) and the identity, served at /skin/ (the name is
                            historical: the 18.6.6 skin that shared the path is gone, ADR 0018)
  worker/src/aia_worker/    The execution loop. Claims, heartbeats, records. Does no work itself.
    executor.py             StepExecutor / StepContext protocols, outcomes -- the seam
    worker.py               The loop: claim, execute, record; reconcile on an interval.
                            Refuses a one-connection engine (in-memory SQLite). Reports what broke a
                            run (error_tracking): a step left FAILED, one issue per step kind /
                            failure class / cause; an unclassified exception once, with its stack;
                            never a retry, park, gate, budget stop or cancellation
    context.py              Checkpoints, per-call metering, lease-fenced transactions
    heartbeat.py            Lease extension + cancellation carried back, one thread per attempt
    settings.py             Typed, validated settings from the environment
    registry.py             Loads executors from AIA_WORKER_EXECUTORS=module:factory; outside
                            AIA_ENV=local/test only an aia_executors module, refused before import
    testing.py              Scripted executor for the tests (and the multi-process suite)
  executors/src/aia_executors/  Step implementations the worker runs, registered by kind
    snapshot.py             develop_snapshot: a project revision as a JSON artifact (S3)
    registry.py             The composition root AIA_WORKER_EXECUTORS names; store + build;
                            population_store: the one store the materialize step and the panel
                            loader share; compose_registry(transport=, signer=, population=): production's
                            composition, which the acceptance and population-double workers reuse
    recorded_models.py      The recorded Converse wire the suites and the acceptance harness share:
                            respondent, analysis and Lead answers, recorded-<kind>-<n>; the eight design workers too
                            (DESIGN_ANSWERS, one fixed answer per contract, #570); unrecorded: client-source
                            extraction and the Deep Research agents; any other contract refused by name
    acceptance_recorded.py  The acceptance harness's worker: production's composition over the recorded
                            wire; local and test only; refuses Deep Research
    population_double.py    LOCAL AND TEST ONLY: the production registry with the panel loader
                            replaced by the population double's (RQC10); refused outside local and test, and no
                            deployment may name it (layer_check)
    research.py             The research steps: compile, preflight, fieldwork (parks without a
                            source), aggregate, sociomap; every artifact on the owned design project;
                            the sociomap step computes the run's pinned methods (none: legacy;
                            sociomap_method_invalid for a pin that does not verify) and is reused
                            only under the same engine version and pins
    research_agents.py     Native proposal executor: frozen design/context, StepModelCaller,
                            provenance artifact; no automatic write or retry
    research_lead.py        research_lead_turn: one STUDY_LEAD request and one repair over the
                            frozen context; applies only what stays in the turn's client, the rest
                            waits for the researcher; parks research_lead_unconfigured without
                            AIA_AI_RESEARCH_LEAD_ENABLED, …_MAX_OUTPUT_TOKENS, …_RESERVATION_USD;
                            the workbench's ScriptedLeadExecutor says it is scripted
    ai_fieldwork.py         The ai_runtime source: AI respondents, fictional or drawn from the run's
                            population as the run pinned (persona_source); class + lineage, gateway
                            preflight (a refusal parks), one request per respondent block, answers
                            drawn by code. population_loader: the run's recorded binding, v17 contract,
                            the ANALYSIS enricher, over the shared directory and, when configured,
                            the population store (a selected child; ai_runtime.panel_population_source);
                            a panel run on a worker without it parks
                            (panel_personas_unavailable); a sample or persona refusal fails by name;
                            answer_plans: the request, draw and ledger loop over given plans, which
                            produce and the validation's arms share; require_binding= fails a
                            different resolved binding before any request; Answered.details: each
                            draw's record; the run's design classified by rule (rule:design);
                            AIA_AI_SCALE_LABELS_IN_PROMPT (off): a scale question's labels in its item, and a
                            validation arm asks with them off
    client_source_proposals.py  The client_source_proposals step (lifecycle K2d): AI proposals
                            from a client's document as the client's own work, every request held against and charged
                            to the client's budget (AWAITING_BUDGET until lifted); each answered batch kept in
                            client_work_journal, so a resumed step never pays twice; AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED
                            (off, also off on develop), …_MAX_OUTPUT_TOKENS, …_RESERVATION_USD (at least two calls at the
                            request window); unset, it parks client_source_proposals_unconfigured; a
                            marked source's requests Class C, the mark read again before each request
                            (an unmark mid-run stops it, source_class_changed), each proposal recording
                            data_class and class_source
    analysis.py             research_analysis: one module per step over StepModelCaller; preflight
                            BLOCKED stored with 0 calls, turn checkpoints (a retry replays, never pays
                            twice), AnalysisConfig.from_settings; in the default registry: without
                            AIA_AI_ANALYSIS_ENABLED a module parks (analysis_unconfigured); the
                            model-backed module needs it and the AI runtime itself (AIA_AI_RUNTIME_ENABLED
                            and a valid provider configuration), else it parks too (registry.py).
                            Harness 2: a schema failure is stored per failed field, and the repair
                            turn shows the model its own refused answer (a truncated one: asked for
                            less); analysis_round: a person's retry is a new round, in every turn
                            key, and a model-BLOCKED outcome is not reused in a retry round; the
                            run's design classified by rule (rule:design)
    report.py               research_report: the internal draft from the eight analysis modules and
                            the run's chapters (report_chapters: maps, question tables, design,
                            respondents); never approved here; with AIA_REPORT_PDF_ENABLED (off by
                            default, on for develop) its PDF rendering beside it (research_internal_pdf,
                            infrastructure/report_pdf.py; a failed conversion fails nothing); stores its document
                            model as research_internal_document beside the DOCX under the same fingerprint (#584)
    sociomapping_report.py  The experimental Sociomapping's internal DOCX draft; always registered.
                            AIA_SOCIOMAPPING_EXPERIMENTAL_ENABLED decides only whether a newly started
                            run includes its step; turning it off does not stop a run that already has it
    ai_step.py              StepContext -> ExecutionContext: StepModelCaller (one reservation per
                            request, settled once) + StepCallJournal (fenced dispatch, unfenced ledger)
    ai_runtime.py           AIA_AI_* / AIA_BEDROCK_* settings (off by default, fail closed when on) and
                            the one gateway over ADR 0010's route; the only builder of the adapter.
                            AIA_AI_STEP_EVENTS (off by default): a research agent's and an analysis
                            module's model requests write ai_request_sent / ai_request_answered to
                            the run's feed (StepModelCaller(announce=): counts, cost, latency, never
                            text; two writes per request, ~1.3 ms measured).
                            STUDY_LEAD, the study Research Lead's turn (ADR 0026), is bound to the
                            Lead's own model when AIA_AI_RESEARCH_LEAD_MODEL_ID is set
                            (LeadModelSettings: a pinned EU profile, accepted as Bedrock lists it --
                            the current family's ids carry no ":N" -- and an alias ending "latest"
                            refused; its prices, limits and request profile from
                            AIA_AI_RESEARCH_LEAD_*, no defaults, a wrong key stops the worker by
                            name), a second policy entry on the same route pinned through
                            PinnedModels; else to the route's model. The Lead's reservation is
                            checked at that model's prices and window. Each …MODEL_ID is the model's
                            identity; the optional AIA_BEDROCK_INVOCATION_TARGET /
                            AIA_AI_RESEARCH_LEAD_INVOCATION_TARGET is the application inference profile ARN its
                            calls go through (domain/model_invocation.py; unset, the id itself)
    workbench.py            The ONLY composition with fictional fieldwork; refuses unless AIA_ENV is
                            local/test, and no deployment may name it (layer_check); with AIA_AI_ANALYSIS_ENABLED
                            its analysis modules are answered by RecordedModels behind the real gateway at zero
                            price (recorded_analysis, RECORDED_RUNTIME, never read from the environment), so a
                            fictional run reaches its internal draft locally (CHN7, #565); with
                            AIA_AI_RESEARCH_AGENTS_ENABLED the eight design workers answer the same way
                            (recorded_research_agent, one recorded proposal each), so a job's card, proposal and
                            stale refusal can be met locally (#597); with AIA_WORKBENCH_DEEP_RESEARCH_FIXTURES (set
                            by tools/ui_workbench/workbench.py to tools/ui_workbench/fixtures/deep_research/), also
                            the six Deep Research steps over deep_research_recorded's recorded web and
                            ScriptedDeepResearchModel, a wire that answers each agent from agents.json, reports
                            no tokens and says it is scripted (workbench-scripted-…, route workbench-scripted);
                            WorkbenchDesignClassifier classifies the run's design Class C, synthetic, as the
                            workbench's operator (#578)
    deep_research/          The six Deep Research steps (in the default registry; a run parks
                            without AIA_DEEP_RESEARCH_ENABLED): plan, investigate, merge, verify,
                            synthesize, publish; StepToolMeter (every tool call journaled, fenced,
                            before it leaves; a retry takes the journal over and never resends a
                            call left in flight; a priced call held against the study's budget and
                            settled once); deep_research_registry(runtime=None) parks.
                            investigate.py: a planned track's _PlannedLog stores every external
                            outcome (the search with its hits in order, each fetch, the round, the
                            answer) before the next call, so a released step continues and never
                            sends a call twice; a journaled call with no stored outcome is uncertain
      fan_out.py            AIA_DEEP_RESEARCH_FAN_OUT (off by default): every track that makes a call
                            in a step of its own, any worker (InvestigateTrackExecutor; its payload,
                            TrackStepPayload); the run's snapshot cache in the store
                            (StoredRunSnapshotCache); investigate joins them
    deep_research_runtime.py  AIA_DEEP_RESEARCH_ENABLED: needs research agents; the search route is
                            AIA_DEEP_RESEARCH_WEB_SEARCH = off | wikipedia | brave (unset: the old
                            AIA_DEEP_RESEARCH_WIKIPEDIA_ENABLED decides); off blocks every web track
                            and sends nothing. deep_research_live.py builds each: Czech and English Wikipedia
                            (fee-free, Class C only); brave (priced, NON_EU, Class C only) needs the
                            public fetch's contact, AIA_DEEP_RESEARCH_BRAVE_USD_PER_1000,
                            …_PRICES_AS_OF and …_BRAVE_API_KEY (a reference, never kept or logged).
                            AIA_DEEP_RESEARCH_COMMON_CRAWL (off by default) composes the Athena URL
                            index (us-east-1, priced at its scan cutoff) and the archive beside a
                            search route; every AIA_DEEP_RESEARCH_COMMON_CRAWL_* key required,
                            …_CRAWLS the ladder's. The runtime's sign_off_routes() names the priced
                            live routes; they run only under a pin recording the sign-off (ADR 0022).
                            AIA_DEEP_RESEARCH_FAN_OUT (off by default) needs
                            AIA_DEEP_RESEARCH_MODEL_CONCURRENCY: no default, 1-256, model requests in
                            flight across every worker on the route
    deep_research_recorded.py  The ONLY composition with recorded web retrieval; the workbench
                            composition alone composes it beside itself (local and test); refuses unless
                            AIA_ENV is local/test, and no deployment may name it (layer_check)
    materialize.py          population_materialize: a client's dimension made into its owned child
                            (PopulationRuntime.materialize_child); parks without a population store or
                            AIA_POPULATION_ASSET_ROOT (population_store_unconfigured)
    validation.py           holdout_sample (the confirmation's respondents, drawn once and recorded)
                            and holdout_arm (one model arm's replicate: the same sample drawn again,
                            the preregistered blocks with each block's exclusion, answered through
                            answer_plans with the preregistered model binding required, codes stored
                            beside their probabilities); both park without the AI runtime or the
                            panel path
    seed.py, smoke.py       Operator commands: idempotent develop seed; deployment proof
    legacy_workspace.py     Operator command: the one-off migration of Studies' content from a copy
                            of the 18.6.6 store (dry run unless --apply; ADR 0018 decision 2)
    population_ops.py       Operator command: status / import / attach / establish / promote over
                            PopulationRuntime, as a person AIA_POPULATION_OPERATORS names (user id
                            -> permissions; unset: nobody); bundles under AIA_POPULATION_ASSET_ROOT;
                            --all-companions reads each companion the contract declares by its id;
                            record-dictionary (acts as no one; run by the develop deploy) keeps a
                            version's verified dictionary with it; record-catalogue (the same) keeps
                            each population's current version's audience catalogue, which establish
                            and promote also keep for the version they move to

packages/aia_core/src/aia_core/
  domain/                   Pure. No I/O. stdlib + Pydantic, and numpy / scipy / numba for numerical
                            code (aia-sociomap-5, #504; pinned 2.5 / 1.18 / 0.68)
    ai_models.py            ModelCapability, catalog, ModelPolicy, ModelRegistry (fails closed);
                            RequestProfile (a model's request shape, declared in its catalog entry);
                            STUDY_LEAD (the study Lead), apart from RESEARCH_LEAD (Deep Research)
    ai_contracts.py         ModelRequest/Result, AIUsageEvent, 10-way error taxonomy,
                            structured-output validation, AgentDefinition, FallbackPolicy
    material_rules.py       The class a study's material takes by rule (the product owner, 2026-10-19;
                            ADR 0008 amendment): a design, the study's names and a researcher's
                            messages, focus labels and job instructions Class B; the Lead's files and
                            personal notes C; client notes, approved knowledge and a client's sources A;
                            a source a person marked "Interní dokument" C. classify_by_rule: an
                            operator's exact-bytes classification can only raise a rule (source
                            rule:<name> or operator); material no rule names still refuses
    ai_execution.py         ModelGateway + ExecutionContext: the step-executor contract
    ai_tools.py             ToolRegistry — scope never from model arguments
    approval_ledger.py      The approval ledger's closed set of subjects (ApprovalSubject: what each
                            subject_id names and who writes it; LANE_M3_SUBJECTS: wallet, lead_plan, plan_step,
                            chat_start, data_contract, map_snapshot, sociomap_unlock, admitted by migration
                            5054d4d610c2 before their writers)
    money.py                The four money amounts and their names (Rozpočet klienta, Rozpočet studie,
                            Peněženka, Práh potvrzení; D-01), the wallet ceiling, one precedence (budget, wallet,
                            threshold), the threshold's rule (threshold_verdict: ResearchRuns.start, agent jobs,
                            Deep Research, validation), the wallet's and one start's verdict per path (ADR 0028)
    wallet.py               The wallet's values: ChargeKind, CHARGE_AUTHORITIES, effective_cap (the least of
                            the cap, the client ceiling and the study budget), the two refusals (LO1)
    edit_ops.py             The working copy's edit vocabulary (ADR 0029 decision 1): 30 operations, 8
                            applied (the Lead's payloads and apply_edit, re-exported by research_lead) and 22
                            declared, refused op_not_available; ids, refusal words, touches (the field diff of
                            applying the edit), the Sociomap lock (locked_items, lock_refusal,
                            whole_copy_lock_refusal), the text-only marker; set_n held to the readiness limits
                            (sample_size_problem); one case file, tests/fixtures/edit_ops/cases.json
    lead_artifacts.py       The Lead's per-artifact contract, one row per stage (artifact kind, edits, closed
                            view operations, data-aia target kinds, card starts, inputs, hand-offs and their form,
                            report sections by composer Section id), held with the web's lib/workbench-artifacts.ts
                            to tests/fixtures/lead_artifacts/contract.json; REPORT_SECTIONS, each section's state
                            (filled / fixed text / missing) (#563)
    lead_commands.py        The composer's typed start commands, matched by code (LO5), pinned in
                            tests/fixtures/lead_commands/commands.json (#574)
    lead_workers.py         The worker contract (LO9a): LeadWorkerSpec, one row per worker the Lead may
                            call, every field required and checked at registration (WorkerRegistry); the eight
                            design workers are research_agents.WORKERS, held to
                            tests/fixtures/lead_workers/workers.json
    model_invocation.py     A model's identity (the eu. id) versus its invocation target (an application
                            inference profile ARN in the route's EU region, or the id itself; 5a)
    research_agents.py     Eight closed Research task contracts, prompt/harness versions,
                            bounded context and task-owned proposal mapping; the questionnaire
                            contract (harness 3) proposes each item's research_questions, a set's
                            output_type and each research question's comparison; proposal_result
                            keeps only links to stated research questions (dropped_links names the
                            rest); prompt_version_for: build/optimize at 3, the rest at 2;
                            proposal_state / ProposalState: pending, accepted, dismissed or
                            superseded, a projection of the ledger and rebuild_of; a design and a
                            nonempty instruction classified by rule (design_classification,
                            instruction_classification); prompt_class_source
    research_lead.py        The closed LeadOutput (reply, view, edits, request, follow, self_update),
                            lead_contract (numbers only from the context, sign included, exponents
                            refused), ground_edits, apply_edit, split_self_update, FOCUS_ID,
                            freeze_context (96 KB, oldest turns first), lead_request (STUDY_LEAD;
                            context_classification: each part's class by rule, material_rules);
                            TEXT_EDIT_OPS / is_text_edit (set_text of the title or problem summary,
                            list_replace of a hypothesis, question_edit of the text alone: what an
                            automatic accept may take); its edits are edit_ops's; set_n held to the
                            readiness limits frozen in design.readiness (harness aia-research-lead-2)
    deep_research/          Deep Research (ADR 0017, ADR 0021), pure; the engine is frozen after #166:
      contracts.py          subjects, tracks, snapshots, knowledge sources, evidence, quarantine and
                            stop reasons, the request a run is frozen to; harness 3: the request's
                            settings_method (the approved method digest) and method_identity() in
                            every cross-run reuse key
      settings.py           ADR 0022's catalogue, effective values, the run's pin (pin / read_pin,
                            verified by digest; no fallback); route_allowances / request_limits:
                            what the engine reads from it, never above the code's caps
      workflow.py           the deep_research graph: plan → investigate → merge → verify →
                            synthesize → publish (built from here by the service, not a template)
      integration.py        ADR 0021, around the engine: DeepResearchPurpose (DESIGN_RESEARCH /
                            INTERPRETATION_RESEARCH), ResearchTargetRef (closed: Design Revision,
                            question / battery-object result, analysis module, Sociomap battery,
                            object, object pair), FrozenLineage (artifacts pinned by id + SHA256),
                            DeepResearchRunSpec (its fingerprint keys the run; the engine request's
                            does not move), DeepResearchProvenance; neither purpose may write a
                            design or a deterministic artifact
      interpretation.py     an Interpretation Research run's mission: subjects built by code from
                            its target, the pinned specification and the Design Revision (no
                            respondent number), each with an interpretation:<KIND>:<entity> origin;
                            require_interpretation_mission, the enqueue boundary's check (chunk 30)
      tooling.py            the tool-cost contract: ToolRoute, reserve → dispatching → outcome;
                            needs_sign_off: a live route with a price
      legacy.py             18.6.6 research_context leakage screen + merge, EXACT (unit captures)
      grounding.py          a quote must be in a source the same track retrieved; numbers too
      sources.py            source class + score from declared tables; unknown scores lowest
      classification.py     a query's class: inherited from its context, never lowered by keywords
      web.py                what a fetch may reach: public http(s), every hop, every address
      knowledge_access.py   Client Knowledge frozen at enqueue, classed by kind, retrieved by code
      planning.py           subjects → tracks → fingerprints; presets (DR-5, proposed); stop rule
      agents.py             five agents: closed contracts, prompts from the enums, no tools
      merge.py              declared scores, dedupe, confirmation bonus, the verifier's verdicts
      synthesis.py          the brief: cite accepted evidence, write only its quotes' numbers
      bundle.py, quarantine.py  the sealed bundle; respondent context (re-screened against the
                            final questionnaire), design input, analysis context
      steps.py              what each step stores; reusable (by content) vs this run's own;
                            tally: what a run bought, a reused unit costing nothing
    ai_respondent.py        The AI respondent: agent aia.research.respondent, prompt v1, per-block strict
                            contract, fictional roster, facts by code, interpretation, the dataset;
                            dataset_origin: the origin derived from the personas (a mixed roster refused);
                            fieldwork_seed: the roster and draw seed from the specification;
                            scale_label_wording (PROVISIONAL, SCALE_LABEL_WORDING), sent only under
                            AIA_AI_SCALE_LABELS_IN_PROMPT; respondent_prompt_sha256: the prompt a respondent system
                            names, another one with the labels on
    support_forecast.py     A run's evidence support, forecast before launch from the roster fieldwork
                            will draw (fieldwork_seed + fictional_roster through donor_support and
                            reassess_support, under the support rules and aggregation formulas a start
                            would pin); unknown for a panel run, never good; the smallest sufficient n
                            searched within 40,000 respondents; readiness's support_forecast check
                            (WARN, never FAIL) for an ai_runtime run
    question_outlook.py     Before a run, every item a respondent will answer with one verdict
                            (ANSWERABLE / AT_RISK / UNKNOWN / UNANSWERABLE) and its reasons
                            (conditional, familiarity, fidelity_refused, open_ended, support_*;
                            support_analysis_excluded: shown on Results, not citable), by the rules
                            that decide after the run; unknown never answerable
    research_trace.py       Each research question (as research_questions_of reads it) traced to the
                            items that declare they measure it (research_questions on a question or a
                            tracked set, by text), as answerable as its best measure; unmeasured,
                            unlinked (unknown) and dangling links named; readiness's
                            research_question_coverage (WARN, never FAIL);
                            research_plan.research_question_comparisons (describe / rank_objects /
                            compare_segments / ab_test, by text) checked against the measures:
                            ranking needs a tracked set, A/B a concept-test set, segments
                            unavailable, unknown never answerable (comparisons_of)
    respondent_behavior.py  18.6.6 behavior.py + styly.py: response process, styles, the seeded draw
    respondent_facts.py     18.6.6 factual_layer.py: facts answered by code, unsupported facts refused
    persona_profile.py      A panel respondent's profile: 18.6.6's generate_persona_text in the mode it
                            ran (calibrated -> core, adaptive), first-person prose cut at 185 words (EXACT)
    persona_topics.py       A question's topics: odvod_temata and a block's union (EXACT);
                            block_topics(…, allowlist=): the study's selected dimensions as the persona topic allowlist
                            (18.6.6 dotaznik.py:943-945); DIMENSION_TOPICS: ekologie -> eko, komunikace -> osobnost (the
                            product owner, 2026-10-15; AIA's one deviation from the unit), dimension_topic
    persona_signals.py      The persona signal catalog's topic-matched signals: grounded_profile_text
                            (EXACT; a NaN-priority signal ranks last)
    panel_persona.py        A run's sample as personas: every column through
                            decide(PERSONA_CONSTRUCTION), the joint gate per dictionary block (core
                            jointly, each matched donor block within itself), styles over the whole
                            population, a profile per request block; refusals by name; persona_allowlist:
                            spec.selection.dimensions, each block's topics filtered to it
    panel_source.py         A run's panel respondents: panel_plans (the sample under the design's
                            audience filters, the personas, a plan per respondent, in that order);
                            respondent_system (ADR 0024 §4's components); pinned_components: every
                            component but the model binding; PanelPlans.provenance (with persona_topic_allowlist
                            when one applied);
                            joint_certificate_record (the population's certificate as a panel
                            dataset records it: text, SHA-256, the panel SHA-256)
    licence.py              Licence eligibility beside residency: DataLineage (no default),
                            LicencePolicy.authorise, LicenceDenied (ADR 0016 decision 5)
    licence_determinations.py  The determinations as data: panel sources APPROVED for
                            bedrock-eu-primary alone (OI-61, data owner 2026-10-12); CLIENT_KNOWLEDGE_DATASET
                            (unclassified-client-knowledge, a DATASET / ARTIFACT / FINDING knowledge item with no
                            recorded datasets) APPROVED for bedrock-eu-primary alone (the product owner as data
                            owner, 2026-10-21, /pmstatus Q60 (a); #582, OI-187)
    design.py               A Study's Design Revision: immutable content, provenance, the owner tag;
                            workspace_revision, the working revision it was made from, kept in its
                            reason as design:<stage>@w<n> (no column)
    design_items.py         A design's items (ADR 0026 decision 5): ItemKey, design_items, merge_items
                            (item by item, keeping the person's order), occurrence_keys (a repeated
                            key is <key>#2), brief_signature (= the web's briefFingerprint); shared
                            cases in tests/fixtures/design_items/cases.json (cases, merges), read by
                            proposal-diff.items.test.ts; plan-list items keyed by id; legacy_keys /
                            from_legacy_keys (keys a worker recorded before the ids, read as the ids they name)
    item_ids.py             Stable item ids beside the lists they name (WCE1): *_ids entries {id, bound},
                            derived for content stored before; section ids the compiler's; links follow a reword
                            (follow_rewords, settle_item_ids); apps/web/src/research/item-ids.ts its port, one case
                            file (tests/fixtures/item_ids/cases.json)
    design_fields.py        The D-06 field view: item (existence), each field, a question's section, and
                            order items
    brief_materials.py      The Brief's materials (proposed, client-data-in-analysis 8a): a client dataset
                            named by source, reading and intended contract; eligibility computed from accepted
                            contracts, never stored; none eligible before chunk 2
    design_reuse.py         A reused design's labels (derive_source_labels: the union over every run of
                            the source revision, never chosen) and its citation (DesignSource)
    brief_material_classes.py  Each entry of briefing.attachments with the class material_rules gives it
                            (DESIGN, B); an entry no rule names has none (#586)
    research_design.py      A revision -> ResearchSpecification (compile) + AIA's readiness rules;
                            the Sociomap's declarations (sociomap_rating on a scale question,
                            context_objects on a battery: SECONDARY), SpecSelection (the dimensions
                            and audience filters recorded, applied: false), sociomap_support (WARN
                            below n_min 30); a declaration not made is out of the fingerprint; a
                            question's or set's research_questions: the research questions it
                            measures, by text; a question whose id is a set item's id refused
                            (item_id_collision); selection_receipt: what a run records of its design's selection
                            (dimensions and filters await a population draw, an applied flag never true before the
                            code that applies it ran; dimensions_unmatched); COMPILER_VERSION
                            aia-research-compile-3 keeps the audience's description and builtin_subpanel when
                            given (CHN5, #587); -2 (scale labels): a scale's labels (popisky_skaly on a question,
                            scale_labels on a set) are the two ends or one per point, ≤ 60 characters, else left out
                            with a readiness WARN scale_labels_ignored, never stopping a compile; a non-integer end is
                            invalid_scale; SpecQuestion.scale_labels out of the fingerprint when none; a -1
                            specification read as stored; a set's told_ends (develop_ends) is develop's reading of
                            its ends, sent while the labels stay off the prompt; sample_size_problem: a valid n is a
                            whole number within the limits, never clamped (RQC9)
    run_cost.py             The most a run can cost: its model requests x the reservation per request
                            (fieldwork, analysis with its repairs); an upper bound; unknown, never zero
    fieldwork.py            FieldworkSource, FieldworkDataset, validate_dataset; DataOrigin (two
                            synthetic origins and MODELLED_AI_PANEL, ADR 0024), NON_EVIDENCE_ORIGINS,
                            CLIENT_ADMISSIBLE_ORIGINS (the allowlist every client-facing gate reads),
                            origin_kind (SIMULATED / MODELLED / UNKNOWN: the one reading every label
                            uses), MODELLED_DISCLOSURE, RESPONDENT_SYSTEM_METADATA (the dataset's
                            record of its respondent system) and JOINT_CERTIFICATE_METADATA (a panel
                            dataset's record of its population's CORE_JOINT_STATUS, which its evidence
                            is judged under); PersonaSource (fictional_roster | panel)
                            and persona_source_of (a run before the pin: the roster)
    sociomap_register.py    SOCIOMAP_REGISTER: which Sociomap method, at which exact spec fingerprint,
                            is approved (MethodologyStatus); a method absent is INTERNAL_ONLY, never
                            presumed; aia-sociomap-3 approved by the product owner 2026-10-13 (D6);
                            read whenever a map is read (recorded_statuses), never stored on a run
    synthetic_fieldwork.py  Fictional respondents from random.Random(seed), workbench and tests only
    research_aggregate.py   agreguj_otazku's reportable core + uncertainty.py, ported from the unit
                            (EXACT; bootstrap bounds from AIA's generator, OI-62, parity D5); RoundingSpec in
                            AggregationSpec (methodology V1b): the places a run stores, 18.6.6's 1 and 2 by default; the
                            aggregate carries a rounding block only when they differ; stored_decimals
    research_sociomap.py    The unit's relation matrix -> compute_sociomap; a map's status is the
                            Sociomap register's for its method (sociomap_register.py);
                            require_client_facing refuses anything it does not approve. Beside it each pair's signed r,
                            n, interval and status (contract 2); relation_rescaled (F2), object_scores (F8) and
                            K100 (only with AIA_SOCIOMAP_CONNECTEDNESS_INTERVAL_ENABLED) live only in each pinned
                            contract-3 map, never copied into the body (A3d, body version 10); rating_universe
                            (every set's items + the declared rating questions); SociomapMethod,
                            default_methods (aia-sociomap-1 + -3; a run that pinned -2 keeps it),
                            read_methods, LEGACY_METHODS: a run computes the methods it pinned;
                            each battery's contract-3 maps; SociomapMethod.formulas: the formulas a
                            stored methodology version replaces, compiled on read (slots()), absent
                            from the stored form when empty
    research.py             A run's phase in words (queued … cancelled), from the engine's state
    holdout/                The respondent system's holdout validation (panel-grounded-respondents 7),
                            pure: bank.py (the item bank: each held-out question's Czech wording and
                            options as fielded, the panel code of each option and the public document
                            and page it was read from; pinned by its canonical SHA-256; one of the
                            seven surveys the panel is built from; item_payload / read_item; repeated
                            option labels refused), eligibility.py (which items a
                            population can hold out: measured, every value an option, 80 % coverage,
                            300 effective donors over the donor behind the answer, nothing the
                            respondent is told; a core item scored only in the ages its survey asked),
                            leakage.py (what a block's respondents are not given, computed: the item,
                            its matched block, every persona field at |r| or Cramér's V >= 0.30, an
                            association that cannot be computed, signals on those or the item's
                            concept), preregistration.py (the seeded split: near-duplicates >= 0.70
                            dropped, 40 % of each domain to development; the hashed record of
                            everything that decides the verdict, P1-P8 included; a confirmation set
                            under 40 items / 5 domains of 4 refused; read_preregistration: a stored
                            record checked as written -- canonical bytes, the code's thresholds, the
                            system's fingerprint and population version, the blocks exactly the
                            confirmation set), arms.py (the model arms: A none,
                            B demographics, C core without catalog signals, D the production persona,
                            S D's profiles deranged; the block's exclusion applied in every arm, each
                            respondent keeping their own facts and styles; D unexcluded is today's
                            PanelPersonas.plan; blocks= asks the preregistered blocks), scoring.py (per item TVD, subgroup TVD, Brier on
                            core items, entropy gap; the P1-P8 verdict: P4 D beats A on TVD, P5 D
                            beats S on subgroups and Brier, one Holm family; a criterion that cannot
                            be evaluated fails), baselines.py (L0 the population marginal, L1 the
                            demographic cell without the respondent's own donor, backing off below
                            30 donors; neither decides the verdict), run.py (a confirmation run from
                            its preregistration: sample, arm x replicate, score; the items as fielded
                            in the preregistered blocks, a fact item refused; requests n x blocks x 5
                            x 3; the system checked but for the gateway's binding; sample_sha256,
                            arm_record / read_arm_record). Tests:
                            conftest.holdout_population, a session-scoped fictional factory, and
                            conftest.holdout_records, a hand-built bank and preregistration
    pipeline.py             Stage order, fingerprints, impact/invalidation rule
    population/             Dataset versions, STATIC/LIVE, lineage, promotion, import
                            contract + validation, weights, bindings, RuntimePopulation
      czech.py              The Czech v17 import contract (pinned by hash, not copied)
      policy.py             Field policy as code: what each field may be used for
      companions.py         Companion assets + the fail-closed joint certificate gate
      authority.py          Population-operator capability (establish / promote)
      runtime.py            RuntimePopulation, issued only by the loader; companion(asset_id): a
                            companion's bytes as the loader verified them at load; joint_certificate:
                            the certificate's verified bytes and the panel SHA-256 it was checked against
      subpanels.py          The 18 built-in subpanels adopted from 18.6.6 (pinned to
                            BUILTIN_SUBPANELS_v17.json), check_subpanel; the counts are 18.6.6's
      audience.py           The audience filter: 18.6.6's sanitize_filters + _mask (EXACT), the kind
                            from the column as pandas types it; subpanel_filters; select_audience over
                            a run's population, refusing where the unit dropped a filter
      audience_catalogue.py The factor catalogue: 18.6.6's catalog (EXACT, fixture catalogue.json),
                            each factor's AUDIENCE_FILTERING answer (catalogue_of), the research-only
                            factors not sent to the screen (for_the_screen)
      audience_preview.py   The audience step's preview: select_audience's counts, each filter's alone
                            (per_filter, #580), and draw_panel_sample's verdict at PREVIEW_SEED; counts only
      enrichment.py         The ANALYSIS view's seven runtime dimensions: 18.6.6's attach_derived
                            (EXACT); AudienceDimensionsEnricher, the view's Enricher (composed by
                            the worker's population_loader)
      sampling.py           A run's sample: the audience (audience.py), 18.6.6's largest-remainder
                            quotas over sex x age group x region (+ education from n 700), weighted
                            draw without replacement, raking and the audit; refusals by name;
                            PanelSample.provenance() is what a run records
      materialized.py       A materialized dimension (P4): the hash-pinned contract extension, the M3
                            field policy (modelled; never measured, never weighting),
                            check_child_version; a child is owned by one organization and never a
                            shared population's version (OwnedVersionNotShared); target_met within
                            TARGET_TOLERANCE (binary 0.005, scale 0.01), never presumed
      derivation.py         18.6.6's evidence derivation EXACT (npc-18.6.6-evidence-overlay v1);
                            refuses a dimension no predictor varies for (no_varying_predictor)
      definition.py         DimensionDefinition: the K5 contract as a type (kind, target with its
                            evidence anchor, predictors, missingness, range), hash-identified
      versions.py           owned_version_id: an owned child's id, its content qualified by an
                            owner digest
    project.py              Project, revisions, stage state
    providers.py            Provider policy, model roles, budget and error semantics; NATIVE_PROVIDERS
                            (Bedrock) -- the prototype's providers and policies are read from records only
    residency.py            EU residency, data classes, the fail-closed egress boundary
    scope.py                Organization/Client/Study vocabulary, permissions; one role (Researcher =
                            every permission, ADR 0019) and WORKER_PERMISSIONS, an explicit set that
                            withholds every approval; StudyKind (RESEARCH / SIMULATION);
                            ClientContext + ClientPermission
    deployment.py           AIA_ENV: local / test / develop / staging / production; what each allows
                            (deployed guards, fictional material), the one fictional-material rule the
                            API and the worker both ask; DataClassGates / data_class_gates_problem
                            (AIA_DATA_CLASS_GATES, enforce | advisory: advisory refused outside local, test and
                            develop; #594)
    workspace.py            A research Study's working content: ContentState (EMPTY … AWAITING_MIGRATION),
                            validation, lineage of content migrated from 18.6.6 (ADR 0018, OI-58);
                            edited_from_current: a save naming no revision is not stale over a working copy that is
                            still the bare template a server writer saved (OI-173)
    research_template.py    The research template a new study starts from (the unit's empty project)
    attachments.py          A brief attachment's record and the unit's rules (25 MB, the name, the excerpt)
    questionnaire_import.py The questionnaire template's rows -> sections, as the unit imported them
                            (its row rules and the normalize_project rules an import meets)
    workspace_migration.py  The 18.6.6 migration's rules: file references, the record rewrite, the
                            copy checked against the unit's own hashes, one-for-one validation, report
    knowledge.py            Client Knowledge: layers, kinds, proposals, revisions (ADR 0015);
                            folders and labels (organization, not knowledge: no model sees them, no
                            revision is written), STALE_AFTER (365 days), KnowledgeHealth;
                            source_ref: a file by reference (content.source_id, SOURCE /
                            DOCUMENT / DATASET only); ProposalDraft: an AI proposal's draft before it is filed;
                            typed revisions and decisions (lifecycle K3): KnowledgeAuthor, KnowledgeDecision,
                            reviewed_decision (the one approval rule: a named revision that is not current is stale
                            whatever the base), RevisionEvidence / evidence_of, revision_sha256 (canonical JSON);
                            UNKNOWN / null for a record from before
    knowledge_context.py    A study's chosen knowledge (lifecycle K4): KnowledgeSelection,
                            FrozenKnowledgeContext (CURRENT / SUPERSEDED entries, RETIRED omitted by name,
                            context_sha256, verify), StaleKnowledgeSelection
    client_profile.py       A client's profile on its record (short code, industry, market,
                            description) and its contacts; neither is knowledge, no model reads them
    client_sources.py       A client's sources (lifecycle K2): family by suffix (the owner's format
                            list of 2026-10-13), Locator, Segment, ReadingNote, SourceReading (READ /
                            PARTIAL / UNREADABLE / UNSUPPORTED / REFUSED, never more than happened),
                            display_name (the name as written); InternalMark (who and when a person
                            marked a source "Interní dokument")
    source_proposals.py     AI proposals from a client's document (lifecycle K2d): require_extractable
                            (documents only; dataset_not_extracted, no_text, nothing_read), batches bounded by
                            BATCH_MAX_BYTES (24,000), MAX_REQUESTS (42, else too_many_requests before any call),
                            request_window_tokens (the hold's window), proposal_request (FAST_EXTRACTION; Class A, or
                            C with internal= for a source marked "Interní dokument"), ground
                            (a quote literally in its segment; the segment's locator, never the model's)
    client_datasets.py      A dataset's preview (K2c): per column the header (row 1 when all text
                            over numbers or dates), kind, fill, distinct values (to 1,000) and five
                            samples; a column flagged personal (header, or a third of its values an
                            e-mail, Czech phone or birth number) has its samples masked; patterns
                            pinned in fixtures/client_datasets/personal.json
    project_memory.py       Project memory's match: every word, accent-folded, a four-letter stem;
                            DIMENSION_LABELS, the canonical dimension titles pinned to the web's
    workflow.py             Workflow DAG, job states, retry classification
    workflow_templates.py   The closed set of workflow types and their step graphs
    methodology/            The Metodika tab's model (ADR 0023), pure: catalogue.py (module, step,
                            group, preset; every step pinned to the function it describes; a step
                            says what it is for, the steps it reads and its audit point, and
                            feeds_of derives the steps that read it; ParameterEffect.CHANGES_STORED marks a field
                            that changes stored numbers, MethodModule.preview_title_cs titles a module's
                            preview), sociomap.py (the object map
                            in the order of its computation, stages S1-S7, each step citing its
                            audit point F1-F16) and
                            sociomap_reference.py (aia-sociomap-1, read-only); expressions.py (the
                            formula language: AST whitelist compiled to closures, no eval; LaTeX
                            written from the expression; slot properties checked on a grid);
                            sociomap_formulas.py (the 14 built-in formulas, bit-identical to the
                            engine; each says what the engine keeps around it, kept_cs, whatever
                            replaces it); aggregation_formulas.py (the aggregate's five
                            estimators, each with what the aggregate keeps around it, kept_cs);
                            versions.py (what a stored version may be: <base>+e<n>);
                            pins.py (the methodology in force -> a run's Sociomap pins;
                            COMPUTED_SLOTS); sociomap_check.py (an edit beside what is in force on
                            three fixed fictional panels, through the run's own pin)
    sociomap/               Sociomapping maths, pure Python: compute_sociomap -> artifact
      slots.py              The formula slots a methodology version replaces (ADR 0023): the ids the
                            engine reads; every engine function takes slots (default none: the code's
                            formula, bit for bit)
      specification.py      SociomapSpec v2 (contract 2, AIA_SOCIOMAP_V1) and SociomapSpecV3
                            (contract 3: AIA_SOCIOMAP_V2, the audit's object map; AIA_SOCIOMAP_V3,
                            the same under AIA's Q5-Q7 decisions: Kish-n pair evidence, the 0.10
                            effect floor, the envelope terrain at provisional sigma 0.25), no defaults,
                            require_supported each; read_spec / spec_payload read a stored spec by
                            the contract it names, never another
      relations.py          scale coercion, mutual projection, ipsatization   F1-F3; pair_status
                            (audit F3: UNKNOWN / RELIABLE / WEAK), person_minmax (F2),
                            coerce_declared_1_10 (F5: a declared matrix type, never detected);
                            kish_effective_n, meets_effect_floor (Q6: two gates, the floor beside
                            the status, never inside it)
      pairs.py              derive_pair_relations (signed r, n, interval, status; with a declared
                            policy, each pair's Kish n and meets_effect_floor) and the unit's
                            derive_relation_matrix
      layout.py             declared layout registry; aia_rowcond_unfolding_v1;
                            fit_smacof_objects (audit F6: objects on the fixed ruler, never rescaled)
      metrics.py            object metrics, T-score, normaliser               F5-F6; primary_scores
                            (audit F8, PRIMARY only, UNKNOWN pairs out); connectedness_100 and
                            rank_with_ties (F9: an order only where intervals part)
      terrain.py            respondent density / object weighted mean         F7-F8;
                            object_envelope (audit F12/F13: max of hills, each its own height; a
                            cell no hill reaches is null; nothing outside the engine computes one);
                            fit_frame (the framed grid) and EnvelopeParameters.axes() (the grid's x
                            and y about its centre; axis() is the offsets from the centre)
      signed_off_*.py       aia-sociomap-5 (AIA_SOCIOMAP_V5, #504): the methodology owner's signed-off
                            Sociomapa, ported as written (numpy/scipy/numba), not the default and
                            INTERNAL_ONLY until registered; earlier presets byte-identical.
                            signed_off_inputs (per-person centring, the unrelated baseline, pair
                            floors 10 / 5, Benjamini-Hochberg with the noise rule, the sparse design);
                            signed_off_layout (soft-rank Spearman with Coulomb, BB1, for 4-163
                            objects, Interval MDS above, choose_method; platform-dependent from ~12
                            objects); signed_off_credibility (split_half_agreement, map_uncertainty;
                            engine_v2._credibility); signed_off_respondents (place_respondents,
                            respondent_density; engine_v2._respondents); signed_off_segments
                            (respondent_slopes, map_decision, taste_segments, consensus_state,
                            segment_profiles, jittered_ratings; engine_v2._segments). Under -5 the
                            artifact records layout.method (no stress_1), heights.relative,
                            objects_not_placed, the framed_relative_envelope terrain, credibility,
                            respondents (placement, density) and segments; register rules
                            AIA-SIGNED-OFF-CREDIBILITY, -RESPONDENTS, -SEGMENTS; Metodika groups
                            "Věrohodnost mapy", "Respondenti a podpora mapy" and S7 (segments).
                            The web does not draw -5 yet (plan signed-off-sociomap-method)
      engine.py, models.py  the pipeline and the v2 artifact
      engine_v2.py, models_v3.py  compute_object_map -> SociomapArtifactV3 (MAPPED / NOT_MAPPABLE,
                            support); read_artifact reads either contract, refuses any other;
                            read_object_maps: the one reader of a battery's stored maps (contract 3,
                            each map's method equal to its key), for the report and its figures
      view.py               drag overrides, view terrain, scenarios (never write) F9;
                            align_to_reference (a view), stress_quality (the audit's label)
    report/                 The report as data: document model, components, templates (DOCX output)
      print_tokens.py       GENERATED from tokens.json: print colours, type scale in pt, page
      model.py              The document: metadata, sections, every block — numbers only as refs
      document_model.py     The report's document model as stored JSON (aia-report-document-1): composer
                            section ids, `<section>.<n>` block ids, each cited ref's printed text; no bytes
                            (report-delivery RD5a, #584)
      evidence.py           EvidenceLedger (built from AdmittedClaims only) and print grades;
                            modelled_panel: the refs that print "modelováno: AI respondenti z
                            populace" beside them (ADR 0024 §7)
      validation.py         Every rule a report must keep before it renders; fails closed
      numbers.py            Czech print formatting; never re-rounds; effective n rounds down
      copy.py               The report's own Czech vocabulary
      outline.py            Every printed number: chapters, appendices, headings, figures, cross-ref labels
      rendering.py          ReportRenderer protocol: the seam to the DOCX adapter
      templates.py          client / final / internal / documentation recipes; the client report
                            keeps the legacy client_report_v2 section order
    evidence/               What may be claimed — every gate fails closed
      field_policy.py       400-field dictionary as typed policy; FieldPolicyBook
      joint_status.py       CORE_JOINT_STATUS certificate, hash-bound; joint units
      claims.py             Permissible-claim policy: measured vs modelled, disclosures
      support.py            Kish effective n, SUPPRESS by default, intervals required
      metrics.py            The allowed analysis metrics, one unit each
      validation.py         Validation bound to system fingerprint; tier gate;
                            respondent_system_fingerprint (ADR 0024 §4) and lifts_internal_only (a
                            current holdout on it, nothing else)
      instrument.py         A Study's own items as evidence fields: -1 (simulated) and -2
                            (MODELLED_AI_PANEL), chosen by origin; -2 internal until a holdout lifts
                            it, or, for the client report alone, the owner's lift
      report_lift.py        MODELLED_CLIENT_REPORT_LIFT: the product owner's 2026-10-13 decision as
                            data (ADR 0024 §4 amendment): drops -2's INTERNAL_ONLY for the client
                            report only; only application/client_report.py passes it
      factual.py            Factual layer: panel facts are read, never invented
      admission.py          AdmittedClaim — the ONLY way a number enters a result
    analysis/               The eight analysis modules, drafts, prompts, results; native
                            evidence admits each number at the places its aggregate stored (stored_decimals)
    simulation/             Deterministic simulation core from a frozen WorldModel:
                            reference constants, reject-not-clip validation,
                            inoculation, scenarios, variants, frozen results
  application/
    model_gateway.py        GovernedModelGateway — the ONLY model call path (ADR 0005)
    errors.py               The infrastructure errors a router catches, re-exported (the same
                            classes), so a router need not import infrastructure (the ratchet
                            contract in pyproject.toml)
    scope.py                ScopeResolver — the ONLY issuer of a scope context,
                            including a worker's, issued only against a held lease,
                            and of a ClientContext (client_context, accessible_clients);
                            membership of the organization is the access, no grant is read
                            (ADR 0019), and an archived client's studies are not listed
    population.py           PopulationRuntime — the ONLY loader of population data; live_binding:
                            the binding a new run records (None until the population is
                            established; reads no panel); materialize_child: a client's dimension
                            derived over a shared base, written once to the population store and
                            registered as its owned child, never promoted; resolve_child: an owned
                            child, pinned, verified against its base at load; child_binding: a
                            selected child, the study's own client's only
    population_double.py    LOCAL AND TEST ONLY: the fictional population both processes compose for tier
                            A (AIA_POPULATION_DOUBLE), established through PopulationRuntime; refused outside local
                            and test
    wallet.py               StudyWallets behind AIA_STUDY_WALLET_ENABLED (off by default); set_study_status:
                            a study's status change, which closes its wallet when the study closes
    materialize.py          prepare_materialization: a dimension request checked from a study against
                            LIVE's kept policy (owner from the scope, base, definition);
                            start_materialization: a population_materialize run under the study's
                            population project (owner study_population); child_key, and the run's
                            key within the study; materialization_run / materialization_runs, found
                            only through the study; child_outcome: a child's dimension and what it
                            reached, from its stored extension and registration record
    validation.py           ValidationRuns.start: a confirmation run from the Study's stored
                            preregistration and its pinned bank; refuses a stale system, an unknown
                            or larger ceiling than preregistered, an unconfirmed spend, and a system
                            another Study has started confirming; validation_artifacts: the Study's
                            owned validation project
    population_authority.py PopulationAuthority — the ONLY issuer of an operator context
    population_characteristics.py  A version's weights, blocks, every field's dictionary facts and
                            per-use policy answers, the subpanels checked; from the kept
                            dictionary, re-hashed; reads no row
    audience_catalogue.py   LIVE's kept audience catalogue and the 18 subpanels as filters; reads
                            no row (PopulationRuntime.record_audience_catalogue keeps it)
    audience_preview.py     AudiencePreviewer: LIVE loaded once per process and version through
                            PopulationRuntime, then the domain preview
    project_memory.py       search_client_studies: one client's studies through ScopeResolver,
                            each under its own study context; latest Design Revision, else the
                            working draft, else the name
    design_reuse.py         reuse_design: a new or empty research study of the same client from a past
                            Design Revision (working content, first revision, citation, one transaction);
                            source_runs
    analysis.py             Runs one module: draft → gate → repair ≤2 → COMPLETED/BLOCKED
    analysis_results.py     A module's sources, preparation and stored outcome; reconstruct_run
                            re-judges every outcome under today's harness (refuses an older one);
                            stored_analysis reads them as stored, any harness, judging nothing;
                            retry_failed_modules: a finished run's model-blocked or failed modules
                            asked again as a new linked run over its frozen dataset (no fieldwork),
                            completed ones reused, the preflight's refusals not retried; an analysis retry
                            names the original's specification by id and SHA-256 (FrozenDataset.specification_*),
                            taken as stored by the compile step
    report.py               Main internal narrative from eight re-admitted analysis modules;
                            body prose keeps evidence refs and actual headings keep semantic styles;
                            the design chapter after the introduction, "Respondenti a výpočet" and the
                            per-question tables after the methodology, the questionnaire appendix
    report_chapters.py      report_chapters: the map, question, design and method chapters from the
                            run's verified sources (verified_map: the run's Sociomap, derived from its
                            dataset and specification); the worker's report and the report with
                            literature both take them from here
    report_tables.py        question_tables: every question's numbers as tables, each cell a claim
                            admitted question by question for the given surface (internal: a refused
                            question named with its reasons; client: left out and counted)
    report_design.py        compose_design_sections: the design the run executed (questions, sets,
                            sample, audience as stated) and its questionnaire as an appendix
    report_method.py        compose_method_section: who answered (by origin kind), the population
                            recorded and read, filters applied or not, the methods pinned;
                            unrecorded said so
    report_approval.py      approve_report: a person approves a run's stored report (internal, with
                            literature, or client) through ArtifactRepository.approve, once
    client_report.py        compose_client_report / stored_client_report: a modelled run's client
                            report: numbers admitted CLIENT_FACING under the owner's lift and the
                            run's recorded certificate, each labelled modelled with its scope;
                            approved maps only, as figures; the design and the questionnaire;
                            stored once as a draft (research_client_docx); its download stores the document
                            model as research_client_document beside the DOCX, client_report_document reads it
                            (#584); refused by name
                            (ClientReportRefused) for any other run
    contextual_report.py    Combined internal report over an explicitly selected completed interpretation
                            run: scoped ownership, bundle seal and exact frozen lineage; accepted source
                            claims, complete cited numeric context and explicit coverage limits. Generated
                            interpretation remains an unapproved UI draft outside the report; external L
                            citations stay outside respondent evidence. The same chapters as the
                            internal report (report_chapters); stored once per exact source set as
                            research_internal_docx_with_research (DRAFT_UNAPPROVED,
                            stored_contextual_report); the original run is unchanged.
                            See test_citation_valid_inapplicability_inference_is_not_published.
    report_maps.py          Map chapters from frozen object maps and supplied print snapshots, each
                            map with the Sociomap register's status; reading guide, fit/support and
                            signed relationship table; client=True: approved maps only, as figures
    client_work.py          The client's own work (client-budget): client_work_project, one
                            client_sources project per client held by uq_projects_client_work (migration b3d5f7a9c1e4);
                            lift_client_budget_wait compares under the client row's lock
    source_proposals.py     start_source_proposals: one run per reading as the client's own work,
                            a new one only after a failed or cancelled run or one stopped for recovery with nothing
                            uncertain (restartable); latest_source_proposals: the newest, with the step's own reason
    workflows.py            start_workflow: a run from a template, idempotent per revision
    proposal_accept.py      accept_into_working_copy: an AI proposal's accept (an agent job's, a Design
                            Research run's) in one transaction under the Study lock -- the item-level
                            stale rule (StaleProposal: design_moved, unknown_baseline, items_changed),
                            the merge into the working copy, the Design Revision naming that working
                            revision; the caller's ledger row commits with it
    lead_chat_start.py      approve_chat_start: a typed start command's quote, create, chat_start ledger row
                            and charge, in LO1's order (#574)
    research_lead.py        ResearchLead (state, post under the researcher's lock, decide_edits --
                            auto=: the researcher's standing choice, text edits only, refused whole
                            as stale_turn (LeadTurnStale) when the turn's frozen working revision is
                            not the current one --, approve_request, decide_self_update) and
                            LeadProfile (read, hatch, set_preferences); set_study_budget /
                            release_lead_budget_waits; a message written before the budget is set replaces a parked
                            turn, and a parked turn holds nothing
    verified_sources.py     add_verified_source: a captured source a person checked, from the run's
                            verified sealed bundle (the snapshot and the accepted finding citing it;
                            nothing from the browser), added to the Study's client's knowledge as a
                            SOURCE item through add_source_once, or filed as a proposal where
                            self-approval is off
    research.py             ResearchRuns: start/list/get/cancel/retry over a Design Revision,
                            found only through the Study; research_artifacts, the ONLY reader;
                            start/retry ask when the run's cost ceiling reaches the study's spend
                            limit, and record the yes (ADR 0019 gate 2); start pins the Sociomap
                            methods -- the organization's methodology in force (ADR 0023: a stored
                            version as aia-sociomap-3+e<n>, its digest in the run's identity) -- and
                            a retry keeps the original's; ResearchAgentJobs.accept: a
                            person applies an agent's proposal (APPROVE_GATE), recorded (gate 1);
                            start records the LIVE population binding, or the study's own client's
                            selected child (population_version_id, pinned), when it creates a run (a
                            found run keeps what it recorded, a retry the original's), and pins
                            its persona source (a panel run is its own identity and needs an
                            established population: PanelPopulationMissing); a retry keeps it.
                            retry_analysis: the same restart under every pin, its fieldwork step
                            given the original's dataset (FrozenDataset: artifact id + SHA-256,
                            verified by the step, never substituted). readiness(…, fieldwork_source=):
                            with ai_runtime, the support forecast under the support rules and
                            aggregation a start would pin; outlook(): the specification, readiness
                            and question outlook from one forecast (RunOutlook); readiness reads it
    deep_research_pricing.py  DeepResearchPricingSettings: the keys a Deep Research ceiling is priced from
                            (prices, budgets, search route, mode, study_prices), built by each composition root; a
                            start and a quote share one admission (DeepResearchRuns._admit; #555)
    deep_research.py        DeepResearchRuns: the run spec frozen at enqueue (ADR 0021):
                            freeze_design (the engine request: knowledge via for_study, client
                            terms) and freeze_interpretation (a result of this Study's own research
                            run, every artifact pinned and verified, never the latest);
                            start/get/runs/events/cancel/retry (a retry never re-chooses its
                            target); _enqueue, the one enqueue boundary, refuses a spec whose
                            request is not its own purpose's (an interpretation request holds only
                            its target's mission: interpretation_mission_mismatch); an
                            interpretation retry re-freezes the stored target, lineage_changed
                            when a pin moved; legacy runs read legacy-unversioned; the bundle
                            (seal verified), its snapshots and provenance only through the run.
                            The run's effective settings pinned at enqueue (ADR 0022: settings_pin
                            in its metadata and the plan step's input; run_settings reads it back
                            verified); cost_ceiling sized by the pinned allowances and limits;
                            LiveNotApproved (409 live_settings_unapproved, missing + routes) when a
                            priced route is composed and a live setting is not approved
    web_retrieval.py        RetrievalGate: the ONLY way a query or URL leaves -- classify, egress,
                            metering, reserve, journal the dispatch, call, journal the outcome
    develop_seed.py         The synthetic develop world, through the same paths the API uses
    workspace_migration.py  migrate_unit_workspaces: each waiting Study as a named person, through
                            ScopeResolver, in its own transaction; missing is not lost until said so
  infrastructure/
    report_pdf.py           LibreOfficePdf: a stored DOCX rendered as PDF (headless soffice, a private
                            profile per conversion, a timeout); AIA_REPORT_PDF_ENABLED (off by
                            default; on without soffice stops the worker)
    report_docx/            The report as DOCX (python-docx; the `report` extra, imported lazily)
      cover.py, assets/     Original Claude Design lockup/field SVGs in a cover-only header;
                            editable bottom-aligned cover text and preserved draft footer
      object_map_figure.py  Deterministic top/3D PNG snapshots from stored contract-3 points, heights
                            and finite terrain triangles; no layout or terrain recomputation
      embed.py              ECMA-376 obfuscated font embedding; deterministic keys
      styles.py             The Word style sheet, built from print_tokens (S = every style name)
      renderer.py           DocxRenderer.render(doc) -> bytes: validate, outline, write, finish;
                            deterministic bytes (fixed zip timestamps)
      layout.py             Sections (cover / front i, ii / body 1, 2 / appendix), running heads,
                            the draft footer, cover, document control, TOC fields
      blocks.py             One renderer per model block; no direct formatting
      tables.py             The data table: SEQ caption with base n, repeating header, suppressed
                            rows removed and counted, landscape sections
      charts.py, figures.py Charts from the ledger with the viz tokens (7 kinds, hatched modelled
                            series, direct labels); figures; the Sociomap gate (require_client_facing)
      dispatch.py           Which renderer draws which block
      marks.py, images.py   Evidence marks (one glyph per grade; unknown prints "?"), SVG + PNG
                            fallback images with alt text (asvg:svgBlip)
      plotting.py           Matplotlib for the report: vendored fonts, tokens, deterministic SVG/PNG
      context.py            RenderContext: the state of one render
      lint.py               lint_docx: no direct formatting, schema order kept
      ooxml.py, numbering.py, footnotes.py  Fields and bookmarks; lists; the footnotes part
      fonts/                Upstream TTFs, unmodified, with licences + SHA256SUMS
    tables.py               SQLAlchemy tables
    db.py                   Engine and session factory
    repositories.py         ProjectRepository (owner= in its isolation predicate)
    scope_repository.py     Organizations, clients, studies, budgets; studies in a client, by kind;
                            set_study_spend_confirm (the study's spend limit, audited); any member
                            creates a client (ADR 0019); the grant tables are dropped (chunk 6); client_budget(…,
                            for_update=) carries reserved_usd: the client's open holds that name no study
    study_design_repository.py  A Study's design project (owned: projects.owner) and its
                            Design Revisions; the ONLY writer of a Study's design (ADR 0016); a reused
                            design's citation (study_design_sources, insert-once: record_source, source);
                            submit / submit_if_current name the working revision, checked by hash
                            (design_not_from_workspace); submit_as_working_copy: a design the server
                            authored, saved as the working copy first
    holdout_repository.py   A validation Study's preregistration (holdout_preregistrations): kept once
                            as its canonical bytes, re-hashed and re-checked on every read; found only
                            through the Study; the Study's confirmation (holdout_confirmations), once
                            per respondent system in an organization, held by a unique constraint
    study_workspace_repository.py  A Study's working content in its owned working project
                            (projects.owner = study_workspace): load, save naming its base revision
                            (a stale one refused), history; the brief's attachments as artifacts of
                            that project; found only through the Study (ADR 0018); at_revision: one
                            stored working revision
    study_lead_repository.py  A researcher's Lead turns in a study (study_lead_turns), scoped in the query
    researcher_lead_repository.py  The researcher's Lead (researcher_leads), its revisions and notes; a
                            client note only within that client's study; set_preferences
                            (auto_accept_text_edits, default false, migration 57eaa96a5538)
    document_text.py        An attachment's text, read as the unit read it (pypdf, python-docx,
                            openpyxl: the `documents` extra), with the ZIP bounds the unit lacked;
                            a PDF's tables through pdfplumber, after pypdf, bounded
                            (`MAX_PDF_TABLES`, 20 s); check_zip_bounds(data, kind) before any
                            Office or OpenDocument ZIP is inflated; grid_from_rows, the one way a
                            reader outside it makes a bounded grid
    source_reading.py       read_source: a client source's bytes -> segments with locators, a pure
                            function: PDF by page and table row, DOCX and ODT by paragraph and table
                            row, PPTX by slide, TXT/MD by paragraph, DOC from its Word 97 piece table
                            (piece_text; olefile only opens the file; a DOC's cells are Word's
                            paragraphs, no row guessed); CSV, XLSX, XLS (xlrd) and ODS by sheet and
                            row, with the dataset preview, an ODS's repeats never materialized past
                            the grid bounds; an XML part declaring a DTD refused
    questionnaire_file.py   A questionnaire file's rows (the unit's CSV and stdlib XLSX readers) and
                            AIA's own template workbook
    unit_project_store.py   A COPY of the 18.6.6 project store, read mode=ro&immutable=1 (a live
                            database refused; the backup ZIP unpacked to scratch); files by base name
    client_knowledge_repository.py  The ONLY reader/writer of Client Knowledge: read inside a
                            resolved scope, changed by a person's write or an accepted proposal
                            (a new revision each time); also of its folders, labels and item filing
                            (no revision, no date moved, every change audited), health and
                            recent_revisions; an edit of an item is approved only against the
                            revision it was written from (base_revision), else
                            StaleKnowledgeProposal (409 knowledge_proposal_stale) unless the
                            reviewer names the current revision (reviewed_revision); propose_from_client_work: AI
                            proposals filed once per run, authored ai, the run named; add_source_once
                            (client row locked): a SOURCE item once per client and URL or final URL,
                            an active item or a pending proposal answering exists; proposals record author,
                            decision and reviewed_revision (migration a3c5e7f9b1d4), revisions read typed through
                            their proposal; select_for_study / unselect_for_study / selections / freeze_for_study
                            over client_knowledge_selections (migration b5d7f9a1c3e6), one exact revision per study
                            and item, audited CLIENT_KNOWLEDGE_SELECTED / _UNSELECTED
    client_profile_repository.py  The ONLY reader/writer of client_contacts and the profile columns
                            of clients; history read from the audit, never naming an e-mail
    client_source_repository.py  The ONLY reader/writer of client_sources and
                            client_source_occurrences: kept once per client and SHA-256, bytes and
                            reading under org/<org>/client/<client>/sources/<sha256>/, verified on
                            every read; reread: a newer reader's reading beside the first; reading_pin /
                            pinned_reading: the reading a client-work run pinned by SHA-256 (else SourceReadingChanged);
                            mark_internal: who and when on the row (internal_marked_by, internal_marked_at,
                            migration c7e9a1b3d5f2, the row locked), each change audited
                            (CLIENT_SOURCE_MARKED_INTERNAL / …_UNMARKED_INTERNAL); marked_internal
    client_work_journal.py  ClientWorkJournal: each answered request of the client's own work, kept
                            under the lease the moment it returns (client_work_journal, migration c5e7a9b1d3f6), keyed by
                            the client and a fingerprint of exactly what was sent; a resumed step replays it
    artifact_repository.py  Artifact rows, provenance, dependency edges, reuse; find_reusable is
                            newest first within a revision; put(reuse=False) stores beside an
                            artifact under the same fingerprint
    methodology_repository.py  The ONLY reader/writer of the methodology tables (ADR 0023):
                            immutable versions, validated by domain.methodology.versions; append-only
                            activations, newest wins, NULL the code's preset; any member reads,
                            require_administer writes, every change audited;
                            methodology_in_force_for_study, what a run start pins
    deep_research_settings_repository.py  The ONLY reader/writer of the Deep Research settings
                            tables (propose, approve, history); immutable study-test policy proposals and
                            append-only scoped approvals (tables.py:1669 @ db6db022), with catalogue,
                            expiry, fictional-client and USD 20 guards; settings_in_force_for_study,
                            what an enqueue pins (deep_research_settings_repository.py:208 @ db6db022)
    workflow_repository.py  Durable jobs, lease-fenced writes, cost reservations,
                            the population binding each run records; list_runs(key_prefix=), matched literally;
                            list_runs(steps=True): a page's steps in one more query, no attempts; WorkQueue --
                            the only cross-study surface (claim, recover, resume, refuse);
                            resume_budget_waits: a person lifts every AWAITING_BUDGET step of one run, one
                            row in the approval ledger (subject the run; each STEP_RESUMED names its decision_id;
                            the worker's scope cannot); ledger(subjects=): a study's ledger rows under its three
                            scope columns; record_spend_confirmation and
                            record_ai_proposal_acceptance (once per agent job): the same ledger;
                            record_chat_start (APPROVE_GATE, a typed start command's ledger row, #574);
                            reserve_tool_budget: a priced tool call's hold, the same check, fence
                            and recovery as a model call's
    study_wallet_repository.py  The ONLY reader/writer of study_wallets, study_wallet_raises and
                            study_wallet_charges (migration 60ccc9ff42cf, LO1): every amount compared under the
                            study row's FOR UPDATE; a charge is a run's ceiling, once, authorised by a chat_start or
                            plan_step ledger row; set_cap writes the wallet ledger row
    fan_out_coordination.py  ModelSlots (model requests in flight across processes, PostgreSQL
                            rows) and SharedHostPacer (per-host politeness shared by every worker)
    host_pacing.py          PacedTransport: every fetch waits its host's turn (local or shared pacer)
    population_repository.py  Population registry: versions, populations, history; each version's
                            dictionary bytes (population_version_dictionaries) and audience
                            catalogue (population_version_audience_catalogues), insert-once; an
                            owned child (P4c): versions(…, organization_id=) and visible_version
                            return shared versions plus only that organization's own, the import's
                            lookups see shared alone; extensions insert-once, re-hashed on read
                            (population_contract_extensions)
    population_store.py     Materialized children in EU S3: put_once (a conditional put; the same
                            bytes answer as written, other bytes refused), RoutingPopulationSource
                            (s3:// from the store, else the shared copy), AIA_POPULATION_STORE_BUCKET /
                            _REGION, both or neither
    population_parser.py    Text-preserving panel + dictionary parser (stdlib); write_panel, its
                            deterministic inverse
    population_source.py    PopulationAssetSource: filesystem / memory (EU store later)
    ai_usage_repository.py  Append-only AI usage ledger; uncertain-call resolution
    ai_call_journal.py      CallJournal over the workflow attempt + ledger
    archive_index.py        What RetrievalGate asks of a URL index and an archive fetcher (UrlIndex,
                            ArchiveRecordFetcher, IndexQueryFailed): protocols only, no wire;
                            common_crawl.py implements them
    http_transport.py       What every outbound HTTP adapter shares: certificate_refused,
                            CredentialSource, SigningUnavailable (model adapters and web routes alike; nothing outside
                            the executor compositions imports model_adapters, an import contract)
    model_adapters/         Anthropic / OpenAI / Claude Code / Bedrock adapters, transports, recorded
                            doubles; live_transport.py (urllib3, no retries), aws_signing.py (SigV4,
                            instance or container role only). Each model's request shape is declared
                            in its catalog entry (domain/ai_models.py RequestProfile: structured_output
                            forced_tool | auto_tool, thinking budget | adaptive, sampling, effort),
                            threaded into AdapterRequest. The Bedrock adapter sends an auto_tool model
                            toolChoice: auto with the gateway's answer-through-the-tool instruction,
                            never a thinking budget or temperature to a model that refuses them, and
                            only a configured effort as additionalModelRequestFields.output_config;
                            what a profile cannot carry is refused unsent. The other adapters refuse
                            any non-default profile. A ledger row's system_prompt_sha256 is the system
                            prompt as sent (with that instruction); input_fingerprint includes a
                            configured effort
    storage.py              ArtifactStore: S3 / filesystem / memory; s3_client(), the one AWS SDK
                            import site
    storage_settings.py     AIA_STORAGE_*: one typed definition for every composition root
    web_retrieval.py        WebFetcher (every hop and address checked, caps, HTML to a content-
                            addressed snapshot); search/fetch protocols; recorded doubles (they say
                            RECORDED and nothing else). The one live route is web_retrieval_live.py:
                            fee-free Czech/English Wikipedia, separately pinned IP/host, no proxy
    build_identity.py       AIA_BUILD_SHA: the commit a process runs; null, never a guess
    redaction.py            What never reaches a log, an error_json or an error report: secret keys
                            and value shapes (provider keys, bearer tokens, JWTs); one definition for
                            the API, the worker and the reporter (OI-23)
    error_tracking.py       The error reporter (GlitchTip, Sentry's protocol): the ONLY sentry_sdk
                            import site, from the `errors` extra; off without AIA_ERROR_TRACKING_DSN,
                            a malformed DSN refused at start; every event redacted, no bodies,
                            cookies, queries, locals, user or model input; no tracing

tests/acceptance/           MVP-ACCEPT-2 tier A over HTTP: the stack (the API and an acceptance_recorded
                            worker as processes), the declared bootstrap, allocation.json (the approved USD 25)
migrations/                 Alembic
deploy/docker/              python.Dockerfile (api + worker targets; the worker build arg AIA_WORKER_PDF
                            installs LibreOffice Writer, ~300 MB, on for develop; NUMBA_CACHE_DIR=/tmp/numba,
                            because numba writes its cache at import and the containers are read-only
                            but /tmp); apps/web/Dockerfile is the client
deploy/develop/             The develop host: Compose, Caddyfile, deploy/backup/restore/smoke, runbook.
                            AIA only: no unit image, service, volume, hostname, credential, data sync
                            or health check (ADR 0018 decision 5); the first deploy without the unit
                            stops its old container and keeps its volume (bin/lib.sh).
                            bin/image_retention.py: protected old release-image cleanup and disk
                            headroom before downloads; a host lock serializes deploys; successful
                            rollback history is recorded only after smoke. Runbook: Disk retention.
                            bin/sync-population.sh (by hand) puts the population's 19 files, listed
                            and pinned in population/v17.files, read-only under AIA_POPULATION_DIR;
                            bin/population.sh runs population_ops in a one-off worker container.
                            AIA's population, never the unit.
                            errors/: GlitchTip 6.2.6 and its own PostgreSQL, a Compose project of
                            its own (aia-errors) on AIA's internal network, at errors.<hostname>;
                            bin/errors.sh up / down / status / admin; bin/deploy.sh starts it after
                            AIA is healthy when aia_errors_enabled, never failing the deploy
deploy/reference/           The 18.6.6 unit beside the product, never part of it: Compose project
                            `aia-reference` on the unit's external volume, a basic-auth gate on the
                            host's loopback (127.0.0.1:8765), up/down/backup-state by hand;
                            .github/workflows/reference-unit.yml builds its image and bundle
  bin/backup-legacy-state.py The unit's SQLite databases copied WAL-safe (backup API), for the
                            migration's copy and backup-state.sh
infra/develop/              Terraform for the develop AWS resources (one root, no modules)
docs/architecture/          System design + the ADRs; ai-step-executor-contract.md;
                            research-journey.md (the research journey: stage owners, interfaces, acceptance)
docs/design/                Brand and UI direction; the design-system brief
design-system/              The AIA Design System artifact as a static reference package for design tools:
                            tokens (CSS + flat JSON), fonts, identity SVGs, status-map.md (from the domain
                            enums), three no-build HTML pages, the artifact verbatim. Not imported by apps/web,
                            whose token source stays apps/web/src/design/tokens.json
docs/migration/             Plan, status, legacy map, MVP acceptance test
  parity-matrix.json        THE parity tracker: 78 capabilities, gates, and MVP-ACCEPT-2's criteria
                            (mvp_acceptance); parity is information, no release blocker (MVP-21)
  legacy-route-ledger.json  The strangler's route ledger: 153 legacy routes, LEGACY/PORTING/PORTED/RETIRED
  interface-screens.json    Every classic screen (router routes + DEMO views) and its React rebuild state (ADR 0014)
  legacy-ui-functions.json  The 88 research functions of ui_app.html (+ recorded additions), hash-pinned
docs/product/               Authoritative product scope
docs/archive/original-mvp/  Superseded. NOT requirements.
tools/layer_check.sh        Layering enforcement
tools/exposure_check.sh     Reference-exposure enforcement (private-repo hygiene)
tools/sociomap_golden.py    Regenerates the Sociomap engine's own golden fixture
tools/film_frame0.py        Checks the launch film's frame 0 is the mark the handoff forms (stdlib
                            over ffmpeg; fails above 0.5 px)
tools/report_preview.py     A report as a reader sees it: DOCX -> PDF -> PNG via LibreOffice,
                            lint, greyscale, +35 % Czech stress (manual)
tools/parity_status.py      Parity verdict per capability, from JUnit XML; the acceptance verdict per
                            criterion from the acceptance step's JUnit, path parity beside it
tools/progress.py           Every plan's status from its front-matter; `--check` validates it
tools/master_check.py       The MVP master plan's register against the plan files: every plan#ID resolves,
                            every gap, interface and criterion has a chunk, every open core chunk a wave
                            (not in CI yet, mvp-master-plan MP14)
prototypes/research-lead-v2/  The canonical design reference for the workbench and all eleven artifact
                            bodies (MVPQ-01, 2026-10-20); research-lead-v3/text is supporting reference only
tools/legacy_oracle.py      Reach the running 18.6.6 unit: probe / record / compare (stdlib)
tools/aggregate_capture.py  Research fixtures from the unit's own functions: `cases`, `capture` (in
                            the unit's venv), `self` (AIA's pinned bounds)
tools/audience_capture.py  Audience-filter fixtures: fictional rows and cases (`inputs`), the unit's
                            own sanitize_filters / _mask / factor_map and catalog on them (`capture`,
                            with pandas)
tools/enrichment_capture.py  Enrichment fixtures: fictional rows (`inputs`), the unit's own
                            enrich_panel on them (`capture`, with pandas)
tools/sampling_capture.py   Sample fixtures: fictional rows and cases (`inputs`), the unit's own
                            draw_representative with the MILP made to fail, and _rake (`capture`)
tools/materialize_capture.py  Materialization fixtures: fictional rows and cases (`inputs`), the
                            unit's own materialize_evidence_dimension (`capture`, pandas + NumPy)
tools/persona_capture.py    Persona fixtures: fictional rows, questions, a fictional signal catalog
                            (`inputs`); the unit's own generate_persona_text, odvod_temata,
                            grounded_profile_text, _render and _compact_anchor (`capture`, with pandas
                            and SciPy)
tools/respondent_capture.py  Respondent behaviour fixtures from the unit's own behavior.py / styly.py
                            (`capture`, in an environment with NumPy, pandas and SciPy)
tools/attachment_text_capture.py  Attachment-text fixtures: fictional documents (`inputs`) and the
                            unit's own `_extract_text` on each (`capture`, with the unit's libraries)
tools/source_fixtures.py    Client-source reader fixtures: fictional text and one fictional export
                            LibreOffice converts into DOC, ODT, DOCX, PPTX, ODS, XLSX and XLS, and a
                            Czech CSV (`write [name …]`: only the named, their pins merged), pinned
                            in fixtures/client_sources/index.json (`verify`)
tools/questionnaire_import_capture.py  Import fixtures: fictional files (`inputs`), AIA's template
                            (`template`), the unit's own import on each (`capture`)
tools/deep_research_capture.py  Leakage-screen and merge fixtures from the unit's own
                            research_context.py (`capture`, `verify`; stdlib only)
tools/bootstrap_seed_sensitivity.py  The unit's bootstrap spread over seeds: the evidence for OI-62
tools/ui_functions.py       Extract ui_app.html's 737 functions verbatim; `effective` prints the binding
                            that runs (the last declaration or reassignment); check the UI ledger
tools/ui_function_runner.mjs, ui_function_capture.py
                            Run extracted functions under Node; capture U<nn> fixtures
tools/caddy_routes.py       CI's check of the adapted develop Caddyfile: one hostname, / -> /app/clients,
                            /app behind AIA's gate, no 18.6.6 document, no upstream but the API and the
                            web client, no panel gate
tools/develop_routing_proof.py, develop_routing_journey.mjs
                            Run the real Caddyfile locally in front of stand-ins; then a browser
tools/ui_workbench/         AIA on this machine, for UI work: the real API on SQLite with local
                            identity and the develop seed, `next dev`, a facade routed by the
                            Caddyfile, a worker with fictional fieldwork; nothing of the unit unless
                            `up --with-unit` runs it beside AIA as reference (scratch copy, fictional
                            panel, its own port, never behind the facade). Never parity. capture.mjs
                            screenshots every AIA screen, and the unit's when it runs;
                            fixture_project.py: fictional research projects; research_journey.mjs:
                            Run -> Results; workspace_journey.mjs: a study's content, file, import,
                            audience, dimensions; both fail on a request to a path the unit served;
                            analysis switched on and each fixture study given a $5 budget, so `make ui-research`
                            runs through to the internal draft (#565); design jobs answered from recordings
                            (#597); fixture_project.py's deep_research study (budget USD 1, its Design Research
                            run) and fixtures/deep_research/ (#578);
                            fictional_population.py: a population of the sampler's 3,000 fictional
                            rows under a contract of its own, established through PopulationRuntime
                            with its catalogue kept, installed as the stand-in's AudiencePopulation
                            (runs still record the Czech LIVE; `--no-audience-population` skips it);
                            audience_journey.mjs: the live audience step (catalogue filters, the
                            preview, subpanels) saved and read back
.planning/                  Progress, plans, open items
legacy/npc-panel-18.6.6/    The NPC Panel 18.6.6 product, extracted from the audited archive
                            by AIA-reference/tools/extract_legacy.py. Frozen: regenerated,
                            never edited. The baseline and parity oracle (ADR 0011).
```

**Stack:** Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic,
PostgreSQL 16, Next.js 16, TypeScript, Tailwind 4.
**Target:** AWS. The `develop` environment is one EC2 host under Docker Compose
with S3, Cognito, ECR, SSM and Bedrock used for real
([ADR 0009](docs/architecture/adr/0009-single-host-develop-environment.md));
production compute is undecided (ECS Fargate expected, with RDS). Terraform,
GitHub Actions with OIDC. No Kubernetes, no Redis, no SQS
([ADR 0002](docs/architecture/adr/0002-postgresql-authoritative-store.md)).

**Model calls.** Nothing calls a provider except through
`GovernedModelGateway.invoke`; `make layer_check` forbids a provider SDK or gateway
library anywhere in the core or API. Domain code names a `ModelCapability` and a
`DataClass`, never a model.

**Routes.** Every project route is study-scoped:
`/api/v1/studies/{study_id}/projects/…`. A project route outside a study prefix
fails the build — that would mean scope had stopped being carried in the path.

**The legacy prototype's archive is not in this repository.** The raw tree
lives at `../npc-panel-reference`, reached through `AIA_LEGACY_REFERENCE`, and is
used by the parity suites. What *is* here, since ADR 0011, is the extracted
**product unit** at `legacy/npc-panel-18.6.6/`: the 924 code and configuration
files of 18.6.6, byte-identical to the archive, with their licence-bound data
kept in EU object storage and hydrated at container start. It is frozen and
regenerated by `AIA-reference/tools/extract_legacy.py`; never edit a file under
`legacy/npc-panel-18.6.6/app/` by hand. It is the behavioural baseline every port
is checked against, and runs for that alone: from `deploy/reference/` beside the
develop host's product, on the host's loopback behind a basic-auth gate, started by
hand (ADR 0018 decision 5). The product deployment has no unit in it and needs none.

**The develop site is AIA, client-first** (ADR 0015). `/` answers 302
`/app/clients`; the hierarchy is Clients → client workspace (Přehled, Výzkumy,
Simulace, Znalosti, Data, Profil) → study → stages, and the global navigation has four
items: Klienti, Společenská inteligence, Projektová paměť, Nastavení. Research
and simulation are both `Study` records, told apart by `Study.kind`. The 18.6.6
interface is not part of the product (ADR 0018 decision 4): no page hands off to
it, `/classic` is AIA's public page saying so, and what AIA does not have yet says
so where a person meets it (`docs/migration/interface-screens.json`: every classic
screen REBUILT, REBUILDING, SUPERSEDED or NOT_IN_AIA with where AIA says it). `/app`
sits behind AIA's own gate, `forward_auth` to `GET /api/v1/session/gate` (ADR 0018):
any active member of the organization with an AIA session; what they see inside is
decided per call by the API (user → organization membership; ADR 0019: no client or
study grant is read). No legacy setting touches it. The product hostname serves nothing of the unit (ADR 0018
decision 5): its old paths are the web client's 404, the panel's gate is gone with
it, and `tools/caddy_routes.py` fails a Caddyfile that routes anywhere but the API
and the web client. The one other name, `errors.<hostname>`, is GlitchTip's, and reaches
GlitchTip alone (`deploy/develop/README.md` § Error tracking).

**A research study's working content lives in AIA** (ADR 0018, OI-58). The stages load
and save it through `/api/v1/studies/{study_id}/workspace/content`; it is the Study's
owned working project (`projects.owner = study_workspace`), found only through the
Study's `study_workspaces` row, whose `content_state` names where it stands. A save
names the revision it was edited from and a stale one is refused (409), never
applied over a newer one; a save naming no revision is not stale over a copy that is still the
bare template a server writer saved, and the Lead's turn names that template revision
(`edited_from_current`, OI-173). A study bound to 18.6.6 before ADR 0018 is
`AWAITING_MIGRATION` -- not editable -- until the explicit migration of its 18.6.6
content (`aia_executors.legacy_workspace`, ADR 0018 decision 2) brings it over from a
*copy* of the unit's store, as a named person through their own access; nothing reads
the running unit. `unit_project_id` is lineage only, and nothing finds a study by it. The files a
brief carries are artifacts of the same working project, in AIA's storage
(`/workspace/attachments`), served only through the Study as `application/octet-stream`;
the brief keeps their records, never a URL. A questionnaire file is read in AIA
(`/workspace/questionnaire-import`) and only its sections come back; the stage saves them.

**Client Knowledge is scoped before it is read.** `ClientKnowledgeRepository`
takes a `ClientContext` or `StudyContext` and queries by that client; there is
no global pool filtered afterwards. What a person writes in the client workspace is
knowledge at once; a study proposes and a person accepts (the proposer too, unless
self-approval is turned off), and either writes a new revision with provenance; knowledge
the AI wrote stays a proposal until a person accepts it. An approval never applies an edit
written from an older revision unless the reviewer names the current one (F-K1, OI-111). A source
Deep Research captured and a person checked is that person's write ("Ověřeno, přidat zdroj"),
once per client and address. Nothing changes knowledge otherwise. A study's chosen knowledge is a
person's choice of exact revisions, frozen for its consumers (K4; the consumers move in K4b behind a
switch). `make layer_check` keeps the rows inside the
repository.

**A research run executes a Design Revision** (ADR 0016). The browser submits the
design it shows; the revision is immutable and belongs to the Study's owned design
project, which no generic project route can see. Runs are found only through the
Study and their artifacts only through the run. Fieldwork for an `ai_runtime` run is
answered by AI respondents (`aia_executors.ai_fieldwork`) only when the worker's AI
runtime is configured and the gateway's gates pass; otherwise it **parks**
(`ai_runtime_unavailable`, the refusing gate named). Its personas are fictional and
its datasets say so (`SYNTHETIC_AI_FICTIONAL`); the fixture's invented respondents
exist only in `aia_executors.workbench` and tests (`SYNTHETIC_FIXTURE`). The model
returns one respondent's probabilities; code answers facts and draws the answer.
What a run sends a model takes its class from `domain/material_rules.py` (a design is Class B by
rule, an operator only raising it; ADR 0008, Amendment 2026-10-19), not from an operator's hash
alone, so a route approved for Class C alone refuses it. On develop
(`AIA_DATA_CLASS_GATES=advisory`) a class-only refusal is a recorded pass.
Panel-derived data may reach only `bedrock-eu-primary` (OI-61, determined by the data
owner 2026-10-12, `licence_determinations.py`); the licence gate stays beside residency
and refuses it on any other route. Unrecorded client knowledge may likewise reach only
`bedrock-eu-primary` (/pmstatus Q60, 2026-10-21). A run pins its persona source at start
(`AIA_AI_POPULATION_PERSONAS_ENABLED`, off by default, in the API and the worker, offers the panel
and makes it the default; a person chooses per run on the Run stage, "Kdo bude odpovídat"): a panel run's
respondents are drawn from the population it recorded and its dataset is `MODELLED_AI_PANEL`; a
worker without the path parks it, never answering with the roster instead
([`panel-grounded-respondents.md`](.planning/plans/panel-grounded-respondents.md)).
A Sociomap's status is the Sociomap register's for the exact method, at its spec fingerprint, that
computed it (`domain/sociomap_register.py`): `aia-sociomap-3` is approved (the product owner,
2026-10-13, D6); `aia-sociomap-1` and anything not registered is `INTERNAL_ONLY`. A study may set a spend limit; a start whose cost
ceiling reaches it needs the person's confirmation, recorded in the approval ledger
(ADR 0019 gate 2).

**The population is resolved once per run.** Research and simulation code gets
population data only from `PopulationRuntime.load_for_run`, which reads the
`PopulationBinding` the run recorded at creation. There is no other loader, no
default weight and no fallback version; `make layer_check` enforces the loader.
Before using a field, a consumer asks `RuntimePopulation.decide(field, use)` and,
before combining fields, `decide_joint(...)` — never the dictionary directly. The
contract is [docs/architecture/population.md](docs/architecture/population.md).
A research run records the LIVE binding at creation (owner, 2026-10-10); only a run that
pinned the panel persona source reads it (fieldwork), and the run says whether its respondents
came from it (`read_by_fieldwork`). On develop,
STATIC is `v17_1_2` and LIVE is `v17_4_0`, imported from 18.6.6 on 2026-10-11.

**Sociomapping golden fixtures are.** F1–F9 are synthetic inputs with the
reference's recorded outputs, vendored under
`packages/aia_core/tests/fixtures/sociomap/` and pinned by SHA256 in its
`index.json`. They run in every CI job. Never edit one to make a test pass.

**A Deep Research finding is a quote in a captured source, or it is nothing** (ADR 0017,
[deep-research.md](docs/architecture/deep-research.md)). Code picks the subjects and tracks,
sends every query and fetch, and grounds every quote in a content-addressed snapshot of the same
track; models only propose. A query's data class is inherited from what it was written from and
never lowered by keywords; a design's class is an operator's exact-bytes classification, never
the design rule, so a run on an edited design parks until an operator classifies it (the product
owner, 2026-10-19, OI-129) — on develop, under advisory gates, it takes the design rule's class
instead (ADR 0008, Amendment 2026-10-21). A captured source becomes Client Knowledge only by a person's click,
"Ověřeno, přidat zdroj" (`application/verified_sources.py`). The 18.6.6 leakage rule is kept exactly and bars a finding from
respondent context, which is re-screened against the final questionnaire. It runs through the
worker as six steps whose every unit is an artifact with a fingerprint, so a later pass buys only
what changed. Its executors are in the worker's default registry and its route in the API, but a
run parks unless `AIA_DEEP_RESEARCH_ENABLED` composes a runtime; the live search routes are
fee-free Czech/English Wikipedia and priced Brave (`AIA_DEEP_RESEARCH_WEB_SEARCH`, Class C), with Common
Crawl's priced index and fee-free archive beside them (`AIA_DEEP_RESEARCH_COMMON_CRAWL`). A priced
call is held against the study's budget before it leaves, and a priced route runs only once its
organization has approved every setting live needs on Settings → Deep Research (ADR 0022). With
no search route the production-shaped composition blocks every web track and sends nothing, and
recorded web retrieval
exists only in `aia_executors.deep_research_recorded` (local and test). Tracks fan out across
workers behind `AIA_DEEP_RESEARCH_FAN_OUT` (off by default), which needs
`AIA_DEEP_RESEARCH_MODEL_CONCURRENCY` (no default, 1-256).

**Deep Research serves two checkpoints, never research truth** (ADR 0021). `DESIGN_RESEARCH`
runs before the methodology freeze and may only *propose*; a person turns a proposal into a new
Design Revision. `INTERPRETATION_RESEARCH` runs over immutable results and has no mutation
authority over respondent data, aggregates, analysis or the canonical Sociomap. Interpretation Research may read the frozen canonical Sociomap. Deep Research and external evidence are never inputs to the canonical Sociomap calculation. Every new run
carries its purpose, a typed target and a frozen lineage (exact artifacts, by SHA256) in an
envelope around the unchanged engine request and sealed bundle; a pre-ADR run reads
`legacy-unversioned`. The engine (retrieval, ladder, investigators, lead, fan-out, recovery,
verification, grounding, confidence, the bundle) is frozen: change it only on a defect or
evaluation finding. Deep Research helps decide what to measure; respondents determine what we
observed; deterministic analysis and Sociomapping determine the computed structure; Deep Research
may then help interpret it. External research never manufactures respondent evidence and never
rewrites deterministic research truth.

**Evidence is a capability, like scope.** A number reaches an analysis result only
as an `AdmittedClaim`, minted only by `admit_numeric_claims` after field policy,
joint structure, support, interval and tier have all passed. Prompts state the
rules; they never enforce them. A modelled number (`MODELLED_AI_PANEL`) reaches a client
only in the client report (`application/client_report.py`): admitted `CLIENT_FACING` under
the owner's recorded lift (`MODELLED_CLIENT_REPORT_LIFT`, ADR 0024 §4 amendment) and the
population certificate its run recorded, labelled modelled; client-facing analysis prose
still waits for a holdout validation.

**The unit is the oracle, and its functions are fixtures.** The strangler plan
([`.planning/plans/legacy-strangler.md`](.planning/plans/legacy-strangler.md))
replaces one capability at a time, compared with the running unit (`deploy/reference`),
reached only through `tools/legacy_oracle.py` and `AIA_LEGACY_REFERENCE_URL`. The 88 research
functions of `ui_app.html` are ported *from the JavaScript*: a fixture is captured
first by running the extracted function under Node
(`packages/aia_core/tests/fixtures/legacy_ui/`, `U<nn>_<function>`), pinned to the
function's source hash, and the port is compared with it. The two ledgers in
`docs/migration/legacy-route-ledger.json` and `legacy-ui-functions.json` are the
state; the plan is the order.

**The golden fixtures need no archive.** F1–F9 are vendored, byte for byte,
under `packages/aia_core/tests/fixtures/sociomap/`; F10–F11 are read from a
checkout of the private `AiAnalytics-AIA/AIA-reference` at `../aia-reference` or
`AIA_REFERENCE_REPO`. Every fixture is pinned by SHA256 in
`docs/migration/parity-matrix.json`. When a capability lands, its fixture gate
lands with it — `test_parity_matrix.py` fails an `IMPLEMENTED` capability with an
ungated fixture.

## 3. Commands

| Purpose | Command |
|---|---|
| One-time setup | `make setup` (needs `python3.12`: the venv is built with the version in `.python-version`, the one CI runs) |
| **Python version** | `make python-version` (also before `make typecheck`): fails unless the venv's Python is `.python-version`'s and ci.yml's `PYTHON_VERSION` agrees. A venv on another minor version: `rm -rf .venv && make deps` |
| Start Postgres / MinIO | `make services` |
| Migrate | `make migrate` |
| New migration | `make migration m="add jobs"` |
| Run everything | `make dev` |
| Run one worker | `make dev-worker` (needs `DATABASE_URL`; the real executors, over `AIA_STORAGE_*`) |
| Seed the synthetic develop world | `make seed-develop` (needs `DATABASE_URL`, `AIA_SEED_OWNER_EMAIL`; idempotent) |
| Operate the population | `python -m aia_executors.population_ops <import\|attach\|establish\|promote> --as <email> …` (needs `DATABASE_URL`, `AIA_POPULATION_ASSET_ROOT`, `AIA_POPULATION_OPERATORS`); `status`, `record-dictionary` and `record-catalogue [--version]` act as no one and take no `--as` (no `AIA_POPULATION_OPERATORS`) |
| **Error tracking on develop** | `bin/errors.sh up \| down \| status \| admin <email>`; GlitchTip at `https://errors.<hostname>`; turning it on: `deploy/develop/README.md` § Error tracking |
| **The population on develop** | `bin/sync-population.sh`, then `bin/population.sh import … --all-companions` / `establish` (`deploy/develop/README.md` § The population) |
| **Migrate 18.6.6 content** | `python -m aia_executors.legacy_workspace --store <copy> --attachments <copy> --as <email> [--apply] [--recover-missing]` (needs `DATABASE_URL`, `AIA_STORAGE_*`; dry run by default; runbook `deploy/develop/README.md` § Migrating 18.6.6 content) |
| Tests | `make test` (core + API + worker + executors) |
| Worker tests | `make test-worker` (the multi-process suite needs a PostgreSQL `DATABASE_URL`) |
| Executor tests | `make test-executors` (the snapshot step under the real worker loop; seed; smoke module) |
| **MVP acceptance, tier A** | `make test-acceptance` (needs `AIA_ACCEPTANCE_DATABASE_URL`, a PostgreSQL database it may migrate and seed): `tests/acceptance` starts the API and a worker (`aia_executors.acceptance_recorded`) as processes after the declared bootstrap and drives them over HTTP; recorded models, nothing paid |
| Deploy `develop` | Merge to `develop`; [`deploy/develop/README.md`](deploy/develop/README.md) is the runbook. Live at <https://aia-develop.art-chain.io/> |
| **Deployment disk / image dry-run** | On the host, `python3 bin/image_retention.py preflight --registry <deployment-registry> --state-file /opt/aia/develop/.deploy-state/successful-releases.json --protect <current-sha> --protect <incoming-sha>`: no deletion unless `--apply`; the full deploy applies retention under its host lock before pulling. See [`Disk retention`](deploy/develop/README.md#disk-retention) for safeguards, initialization and refusal recovery. |
| Parity vs prototype | `make test-parity` (needs `AIA_LEGACY_REFERENCE`; population parity needs `AIA_REFERENCE_REPO`) |
| Golden-fixture pins and F10/F11 | `make test-golden` (needs the reference repository) |
| **Parity vs the running unit** | `make test-oracle` (needs `AIA_LEGACY_REFERENCE_URL` + `_USER` / `_PASSWORD`; skips cleanly without) |
| Capture UI function fixtures | `python tools/ui_function_capture.py capture` (needs Node); `verify` re-runs and compares |
| **Plan status** | `python tools/progress.py`; `--check` validates every plan's front-matter |
| **MVP register** | `python tools/master_check.py` (the master plan against every plan file and `mvp-execution-contracts.md`) |
| **Report PDFs** | The worker renders each report's PDF with `AIA_REPORT_PDF_ENABLED=true`, in an image built with `AIA_WORKER_PDF=true` (both on for develop: `.github/workflows/deploy-develop.yml`, `deploy/develop/docker-compose.yml`); on without `soffice` the worker stops at start |
| **Report preview** | `make report-preview` — the four sample reports as pages, in colour, greyscale and +35 % stress (needs `libreoffice-writer`, `poppler-utils`) |
| **Parity verdicts** | `make parity-status` — `PASS` / `FAIL` / `NOT_EXECUTED` / `NOT_RUNNABLE` per capability |
| Lint | `make lint` (ruff, one configuration: the root `pyproject.toml`; `packages/aia_core` and `apps/api` extend it) |
| Format | `make format` |
| Types | `make typecheck` (mypy `--strict --no-incremental` + `tsc --noEmit`; ~45 s, the check CI runs; a stale incremental cache reports errors CI does not, `AGENTS.md` § mypy) |
| Web tests | `make test-web` (Vitest, pure functions) |
| **Design tokens** | `make web_design` — generated files match `tokens.json`; contrast, palette and accent evidence holds. Change a token: edit `tokens.json`, then `npm run tokens` |
| **UI workbench** | `make ui-workbench` → <http://127.0.0.1:8780/workbench/sign-in>: AIA alone, nothing of 18.6.6; `make ui-workbench-reference`: the same with the unit at `:8767` as reference (its first run installs the unit's requirements into `tmp/ui-workbench/venv`); `make ui-workbench-status`, `make ui-workbench-down`. The API runs on the repo's env (`make setup`) |
| **Develop routing, run** | `sudo python3 tools/develop_routing_proof.py --keep`, then `node tools/develop_routing_journey.mjs` (disposable machine: Caddy on 80/443, `/etc/hosts` names; see the script) |
| Workbench research fixtures | `make ui-fixtures` (workbench running): fictional projects, prints their `/app` links |
| **A research run, end to end** | `make ui-research` (workbench + fixtures): Run → Progress → Results in a browser, on fictional fieldwork |
| **AIA with 18.6.6 absent** | `make ui-workbench` (no unit; its old paths are the web client's 404), `make ui-fixtures`, `make ui-research`, `make ui-workspace` (brief file, template import, audience, dimensions; a 1–10 scale with a label on every point, read back after a reload); both journeys fail on a request to a path the unit served |
| **The live audience step, in a browser** | `make ui-audience` (after `make ui-workbench` + `make ui-fixtures`; Playwright + Chromium): `audience_journey.mjs` on the workbench's fictional population: catalogue filters saved as chosen (an empty bound left out, OI-50) and read back after a reload, the preview's count and verdict, a subpanel saved as its filter and a refused one disabled; fails on a request to a path the unit served |
| **The 18.6.6 reference unit** | On the develop host, by hand: `deploy/reference/bin/up.sh <sha>`, `down.sh`, `backup-state.sh <sha> <label>` ([`deploy/reference/README.md`](deploy/reference/README.md)); the oracle through an SSM port forward to `127.0.0.1:8765` |
| Research fixtures from the unit | `python tools/aggregate_capture.py cases` / `self` (repo env), `capture` (the unit's venv) |
| Audience-filter fixtures from the unit | `python tools/audience_capture.py inputs` (repo env), `capture` (a venv with pandas) |
| Enrichment, sample, persona and materialization fixtures from the unit | `python tools/enrichment_capture.py inputs` / `sampling_capture.py inputs` / `persona_capture.py inputs` / `materialize_capture.py inputs` (repo env), `capture` (a venv with pandas and NumPy; persona also SciPy); a re-capture must be byte-identical |
| Deep Research leakage fixtures | `python tools/deep_research_capture.py capture` / `verify` (repo env: the unit module needs only the stdlib) |
| **Deep Research, end to end (recorded)** | `pytest apps/executors/tests/test_deep_research_journey.py` — the real worker, gateway and gate over recorded exchanges: two passes, measured counts, every failure mode; nothing leaves the process |
| **See every screen** | `make ui-capture` (workbench running; needs Playwright + Chromium): every AIA screen, and, with `make ui-workbench-reference`, the unit's router routes and DEMO views as shipped, 1440/1024 → `tmp/ui-workbench/shots/<time>/index.html` + `report.json` (errors, overflow, off-palette colours) |
| **Research UX regression** | After `make ui-fixtures` + `make ui-research`, `node tools/ui_workbench/ux_journey.mjs` (needs Playwright + Chromium): 17 AIA routes at 1440/1024/768/390, result sections, keyboard/hash navigation, client search and preserved 3D camera; real local APIs, fictional fieldwork, no paid calls; evidence → `tmp/ui-workbench/ux-journey/` |
| **Proposal and prompt UX acceptance** | After `make ui-fixtures`, `node tools/ui_workbench/proposal_prompt_journey.mjs` (Playwright + Chromium): real local save/reload, rejected-save retry, unfinished-edit guards, native proposals without legacy analysis, downstream design equality, prompt save/activation/reset and four responsive widths. Local fictional identity only; asserts zero paid jobs. `--facade` and `--out` override the local URL/evidence directory; `AIA_CHROMIUM` selects an installed browser. |
| **The research workbench, in a browser** | After `make ui-workbench` (with `AIA_WEB_RESEARCH_WORKBENCH=true`) + `make ui-fixtures`, `node tools/ui_workbench/workbench_journey.mjs` (Playwright + Chromium): the workbench at 1440, 1280 and 1100 px and the classic layout at 1024, no page overflow, the eleven stages in six phases, the separator by keyboard, the focus modes, the stage navigation (Výsledky's views by hash); zero paid jobs. `--facade` and `--out` as for the other journeys |
| **The Research Lead, in a browser** | After `make ui-workbench` (with `AIA_WEB_RESEARCH_WORKBENCH=true`) + `make ui-fixtures`, `node tools/ui_workbench/lead_journey.mjs`: the scripted Lead (no model): hatch, greeting, message, an edit accepted through the gate, a job left unapproved, the cross-client note held until accepted, the note on Můj Vedoucí; automatic text edits turned on there, a text edit accepted when its turn finishes and marked automatic, Vrátit; zero paid jobs. Passes once per workbench: rerun it on `python tools/ui_workbench/workbench.py up --fresh` (OI-133) |
| **The Lead's cards, in a browser** | On a fresh workbench (`python tools/ui_workbench/workbench.py up --fresh`) with `AIA_WEB_RESEARCH_WORKBENCH=true`, `node tools/ui_workbench/lead_cards_journey.mjs`: every design job and research run as a card in the Lead's conversation, the prepared research run an approval card (#550) |
| **Dotazník's dependencies, in a browser** | After `make ui-workbench` (with `AIA_WEB_RESEARCH_WORKBENCH=true`) + `make ui-fixtures`, `node tools/ui_workbench/questionnaire_journey.mjs`: Dotazník's Závislosti at 1440/1100/768/390 px; zero paid jobs (#572) |
| **Deep Research in a browser, nothing paid** | After `make ui-workbench` + `make ui-fixtures`, `node tools/ui_workbench/deep_research_journey.mjs` (Playwright + Chromium; `--facade`, `--out`, `--db`, `AIA_CHROMIUM`): a Design Research run on the workbench's recorded web and scripted agents, its sealed bundle, zero paid calls (#578) |
| **The client intake sheet, in a browser** | `make ui-intake` (after `make ui-workbench` + `make ui-fixtures`; Playwright + Chromium): files kept and read, a table named, one item per file, a drop on the page, the sheet open within 400 ms |
| **Client workspace acceptance** | After `make ui-workbench` + `make ui-fixtures`, `node tools/ui_workbench/client_journey.mjs` (Playwright + Chromium; `AIA_CHROMIUM` selects the browser): six client areas at four widths without overflow; fictional knowledge added, filed, labelled, edited and removed; the profile saved and read back after a reload; a contact added and removed with no e-mail in the history; zero paid jobs. After a migration that adds columns, start the workbench with `python tools/ui_workbench/workbench.py up --fresh` |
| **Settings UX acceptance** | After `make ui-workbench`, `node tools/ui_workbench/settings_journey.mjs` (Playwright + Chromium): all eight tabs at 1440/1024/768/390; real local member/budget persistence, policy proposal/approval/withdrawal, methodology validation/compare/refused-save retry/separate activation, protected drafts and expanded technical details. Fictional local identity only, zero paid jobs. `--facade`, `--out` and `AIA_CHROMIUM` configure the local URL, evidence directory and browser. |
| **The Metodika tab, every module** | `make ui-methodology` (after `make ui-workbench` + `make ui-fixtures`; Playwright + Chromium): every module's steps and links, one edit compared, stored and activated per editable module, a run that pins them; every module restored afterwards. `--facade`, `--out` and `AIA_CHROMIUM` as for the settings journey |
| **Layering** | `make layer_check`: the grep rules (`tools/layer_check.sh`) and `lint-imports` (the import contracts, `[tool.importlinter]` in the root `pyproject.toml`) |
| **Reference exposure** | `make exposure_check` |
| Everything CI runs | `make check` |
| Docs-only pull request | A PR changing only `.planning/`, `docs/architecture/adr/`, `CLAUDE.md`, `AGENTS.md` or `ARCHITECTURE.md` runs `Documentation checks` instead of the suites; the path list is the `changes` job in `.github/workflows/ci.yml` |
| **The pre-commit sequence** | `make verify` |
| OpenAPI document | `make openapi` |

There is no compile step in Python. `make typecheck` is this project's
warnings-are-errors gate: `mypy --strict` with `warn_unreachable`, plus
`tsc --noEmit` for the client. mypy runs over all three Python source trees in
one invocation, because `aia_core` ships no `py.typed` (`AGENTS.md` § mypy).

## 4. Planning — `.planning/`

Progress and design live in the repository, not in the chat log.

```
.planning/
├── overview.md        roadmap, decisions (ids `PROGRESS D<n>`), parity status, history
├── mvp-*.md           the MVP: consolidation, cohesion (findings F1-F19 and the decision register),
│                      the owner decision packet, target architecture, development plan (gates, waves,
│                      sessions) and execution contracts (the dependency graph, every chunk's wave)
├── evidence/          read-only traces and reviews the MVP plans cite
├── plans/             one file per feature, broken into chunks; its status on top
│   └── done/          plans archived before 2026-09-28; nothing new moves here
└── open-items.md      the live defect and question register
```

A feature's status lives in **its own plan file**, as front-matter at the top:

```markdown
---
status: in-progress        # planned | in-progress | done
chunks:
  - "[x] 1. Security audits on a weekly schedule"
  - "[ ] 2. Fold the parity jobs into backend"
---
# <feature>
```

- **At the start of every session, run `python tools/progress.py`** before any
  work: one table of every plan's status and next chunk, read from the
  front-matter. `--check` validates the front-matter (allowed status, well-formed
  chunks, both keys present, no open chunk under `done`); it compares nothing
  with a committed file and is not a CI job. There is no committed status index:
  `PROGRESS.md` was retired on 2026-09-28, and its hand-written parts live in
  `overview.md`, which only docs PRs edit. Its decision ids keep the name
  (`PROGRESS D6`), because code and the interface cite them.
- When a design discussion produces an implementation plan, **save it** to
  `.planning/plans/<feature>.md` with the agreed chunks *before* writing code.
- After each chunk lands, tick it in the plan file's `chunks:` and update
  `status:`. **A feature PR touches only its own plan file**, never another
  feature's, never `overview.md`.
- When every chunk is done, set `status: done`. The file stays where it is: a
  move is a rename, and a rename conflicts with any open PR that edits the file.
- Progress is recorded in two places only: the PR description and the plan file.
  The docs PR carries what crosses features (roadmap, decisions, history) into
  `overview.md` (§1).
- **Do not open a parallel backlog.** If `overview.md` or a narrative document
  disagrees with the plan files, the plan files win and the other is stale.

### The anchor rule

**Every claim about code carries `file:line @ SHA`, or a test name.**

An anchored claim is falsifiable with one `git show`. When the cited lines no
longer say what the entry says, the entry is *known* wrong rather than quietly
wrong. Anchors going stale is the feature, not a flaw.

An unanchored entry is a **hypothesis**, not a finding. That is the whole
enforcement mechanism — no tooling, no CI check, because a heavier process does
not survive one developer's busy week. Omitting the anchor costs credibility, not
time.

The specific failure this prevents: *a fix lands under one plan's name and nobody
closes the item filed under another's.* That is how a shipped fix gets carried as
"still open, parked" for weeks.

## 5. Git

### Permission

**Do not run `git add`, `git commit` or `git push` without explicit permission.**
Prepare the change, report what you would commit, and wait.

**One standing exception:** an agent may commit and push its own
`.agent-status/<AGENT_ID>.md` to the `coordination/agent-status` branch whenever
it wants to record progress. That file must reflect real work done, materially
verified and measured, never intentions. Use a separate worktree, never this
checkout. Anything else, that branch's README included, still needs permission.

**A hook or a setting is never permission** (the product owner, 2026-10-20). A stop hook that tells
an agent to commit or push, or an environment setting that does it for the agent, does not grant
what this section withholds. The cloud environment's default to create a pull request on its own
conflicts with this section; it does not override it. Commit and push only on the product owner's
own words in the session, or under a permission he gave for that branch.

### Never touch the working tree to inspect another ref

To compare against `main` or any other ref, **read** it:

```bash
git show origin/main:path/to/file       # read one file
git diff origin/main -- path/           # see the difference
git worktree add /tmp/check origin/main # a whole tree, elsewhere
```

These overwrite uncommitted work and must never be used to have a look:

```bash
git checkout <ref> -- .        # silently replaces every file with <ref>'s
git stash / git reset --hard   # only to undo, never to inspect
```

This is a real incident. `git checkout origin/develop -- .` was run to check
whether some compiler warnings were pre-existing, and it wrote that branch's
version over ~20 working files. It was recoverable only because everything
happened to be committed already — a minute earlier it would have destroyed a
day of work. A throwaway worktree had *already been created* for exactly this
purpose and was the right tool.

### Branches

```
main                       release branch; receives release PRs from develop
  └── develop              integration branch; CI on every push; every green head is
       │                   deployed to https://aia-develop.art-chain.io/ (ADR 0009)
       ├── feature/<slug>  new capability
       ├── fix/<slug>      defect
       └── chore/<slug>    docs, plan archiving, dependency bumps, tooling
```

Work happens on a prefixed branch, opens a pull request into `develop`, and is
merged there; a release is a pull request from `develop` into `main`. **Never
commit directly to `main` or `develop`.** The recommended protection for both,
and who has to configure it, is in
[`infra/develop/README.md` § Human actions](infra/develop/README.md#human-actions).
OI-3 recorded the condition for a second branch: a deployed environment to
protect a release from. That condition is met by `develop`.

**Branch from a fresh `develop`, every time:** `git fetch origin develop`, then
`git checkout -b <prefix>/<slug> origin/develop` -- never from a local `develop`,
which can be any age. CI tests a pull request merged with the current `develop`, so
a branch cut from a stale one is tested against code it never ran: a branch begun
322 commits behind went red on rules it had never seen (#433, 2026-10-15). Before
pushing a long-lived branch, fetch and merge `origin/develop` again.

### Commit messages

Subject: **imperative mood, plain English, describes the change's effect** — not
the files touched, not a ticket number, **not a `type(scope):` prefix**.

```
Verify the first screen on the turn, the rest in the background
Stop marking a listing analysed before it has anywhere to be
Tell "nothing nearby" apart from "we never looked"
Drop the unreachable email-normalisation fallback
```

Commits before this file landed use Conventional Commit prefixes. They are not
rewritten; the style changes going forward.

Body: **why, not what.** The diff already says what. A good body answers:

1. What was wrong, and how it showed up to a user or an operator.
2. Why the obvious fix is not the fix.
3. What this costs — the trade-off you accepted, stated plainly.
4. What you measured, with numbers, if the change is about performance, cost or
   volume.

Hard rules:

- **One logical change per commit.** Do not bundle unrelated changes.
- **Each commit builds and passes tests on its own.** A bisect that lands on a
  broken commit wastes the next person's afternoon.
- Author: the person whose account the work comes from, never another person's
  name: `nigelblount <nigelblount@art-chain.io>`, or
  `Aram Bahbouh <aram.bahbouh@art-chain.io>` for work from Aram's account.
  Agent-assisted commits keep the `Co-Authored-By:` and `Claude-Session:`
  trailers, consistent with all existing history.

### Pull requests

- The PR body is the commit body, widened: the problem, the approach, the
  trade-off, what you measured, and what you deliberately did not do.
- Every PR is green on the blocking checks in
  [ARCHITECTURE.md §8](ARCHITECTURE.md#8-ci-tiers) before review is requested.
- **Never skip, disable, quarantine or loosen a test to get green.** A failing
  test is a finding. If it is genuinely flaky, fix the cause (§7) or document it
  — do not delete the signal.

## 6. Work style

- **Chew only what you can chew.** Break every plan into small, digestible chunks
  *before* execution begins. Never attempt the whole thing at once. If a chunk
  feels large, split it again.
- Execute one chunk at a time. Confirm it builds and its tests pass before
  starting the next.
- **Commit per aspect.** When one aspect is finished — schema + logic + tests —
  commit. Never carry uncommitted work across aspects.
- Finish the whole task. If part of the scope turns out to be blocked, complete
  everything else and say explicitly what you left and why. Scaling the work down
  is the human's call, not yours.

## 7. Tests

Coverage expectations by layer are in
[ARCHITECTURE.md §7](ARCHITECTURE.md#7-testing-contract). Operationally:

### Run long suites in the background

```bash
make test > tmp/suite.txt 2>&1 &     # then keep working
grep -E "passed|failed" tmp/suite.txt # collect later
```

The exception is when the test run **is** the task — debugging one failure,
iterating on one file. Then run it in the foreground and watch it. Single files
are fast and stay in the foreground.

### Flakes are defects, and they have one usual cause

- **The shared cause is almost always parallel tests mutating global state** —
  application config, a shared cache key, an environment variable. The durable
  fix is marking the *mutating* test non-parallel, not a retry and not a sleep.
- Any test whose setup mutates global config must be non-parallel.
- Tests that write to a shared cache clear the key in **both** setup and teardown.
- **Size timing assertions generously.** A wait tuned to a fast dev machine fails
  on CI and buys no signal. If the assertion is about *ordering*, give the budget
  room rather than optimising the thing being measured.
- Do not chase a documented flake; do not re-run a suite hoping for green either.

### Known flakes

Add an entry here the moment one is confirmed, in this shape:

```
- `packages/aia_core/tests/test_x.py::test_y` — symptom: …
  Confirmation: passes when run alone. Cause: … Fix or waiver: …
```

- `apps/web` jsdom component tests (MethodologyVersions, MethodologyPanel, QuestionnaireStep,
  ResearchScreen, IntakeSheet, AudienceStep, BriefStep, ExecutionSteps, FieldOriginPanel,
  ObjectMapView, SystemPromptsPanel) — symptom: "Test timed out in 5000ms", or a findBy*
  that finds nothing after ~1 s, only while the host is loaded.
  Confirmation: passes when run alone. Cause: CPU starvation against idle-sized budgets
  (vitest 5 s per test, testing-library 1 s per lookup); no shared state. Fix or waiver:
  testTimeout 30 s (apps/web/vitest.config.mts), asyncUtilTimeout 10 s
  (apps/web/vitest.setup.ts); vi.waitFor keeps 1 s and names its size where it needs more
  (#536, OI-134).

Mocks live at interface boundaries — external services are mocked through their
protocol, always. Real HTTP only in explicitly manual or integration runs; if a
test needs a real request, stand up a local stub rather than hitting a third
party.

## 8. Correctness habits

The expensive class of bug, with the sweep that finds each, is catalogued as
anti-patterns A1–A10 in
[ARCHITECTURE.md §6](ARCHITECTURE.md#6-anti-patterns--do-not-do-these). The two
worth carrying in your head:

- **Never stamp a guess — prefer null.** A wrong non-null value overwrites good
  data that an earlier pass stored, where null would have left it alone.
- **Never score *unknown* as *good*.** Coalescing a missing value to a
  neutral-looking default silently rewards the absence of data.

**New behaviour on the hot path ships behind a kill switch**, off in test, with
its cost measured before it merges. State the burst size, the latency and the
money in the commit body.

## 9. A finding is only actionable with all six

When reporting a defect — to a human, in your plan file, or into
`.planning/open-items.md`:

1. The claim, in one sentence.
2. The anchor: `file:line @ SHA`.
3. A reproduction that fits one command or one test.
4. The user-visible consequence.
5. The smallest fix.
6. The test that would have caught it.

Missing the reproduction makes it a **hypothesis**, and it is labelled as one.
Hypotheses are reproduced or deleted; they are never budgeted for.

A feature PR records a new finding in its plan file under **Findings** and lists
it under Doc follow-up; a fix that closes an existing OI says so there too. The
docs PR moves findings into `open-items.md` and gives them their OI numbers.
Numbers are allocated only there, so two open PRs never take the same one.

## 10. Before you say a task is done

```bash
make typecheck     # mypy --strict; this project's warnings-are-errors gate
make layer_check
make exposure_check
ruff format --check packages/aia_core apps/api migrations
make test
make web_design    # token drift + design evidence
make test-web
```

or `make verify`, which runs exactly that sequence.

- [ ] No shared file from §1 is edited on this feature branch; anything they
      describe that moved is written under Doc follow-up in the PR description.
- [ ] The plan file's front-matter reflects the chunk that just landed.
- [ ] Every new public function has tests; every new job and event has a test file.
- [ ] No test was skipped, disabled or loosened to get green.
- [ ] Nothing was committed or pushed without permission.
- [ ] You can state the trade-off this change accepted in one sentence.

If the change touches domain logic, also run the parity suite locally against a
reference checkout — **CI cannot run it**, and a green CI is not evidence that
parity holds.

After finishing a whole plan, produce a **layer-by-layer review map**: every
changed and new file grouped by architectural layer, with its test files beside
it, walked through in layer order.

## 11. Reporting

Report outcomes faithfully. If tests fail, say so and paste the output. If you
skipped a step, say which and why. If you are unsure whether something works, say
that instead of "should work". When something is done and verified, say so
plainly without hedging.

Do not narrate options you are not going to take, and do not re-explain a
decision that has already been made.

## Native Research agents (2026-09-27)

[research-agents.md](docs/architecture/research-agents.md) describes contracts,
context, acceptance and activation. Fieldwork activation does not activate design
jobs. The additional worker keys are `AIA_AI_RESEARCH_AGENTS_ENABLED`,
`AIA_AI_RESEARCH_MAX_OUTPUT_TOKENS` and `AIA_AI_RESEARCH_RESERVATION_USD`; the
reservation covers primary plus one schema repair. The study Research Lead's own model takes the
`AIA_AI_RESEARCH_LEAD_MODEL_*` keys and their prices and limits
([`deploy/develop/README.md` § The Research Lead's own model](deploy/develop/README.md#the-research-leads-own-model)). Analysis/report execution and
owned web retrieval remain in the complete-workflow plan, not delivered by the
proposal executor. Do not describe model recollection as web research. The Lead's own web lookup
("Hledat na webu", `lead-orchestration#LO20`, [ADR 0040](docs/architecture/adr/0040-the-leads-web-lookup.md),
accepted 2026-10-20; not built yet) is a governed retrieval path through `RetrievalGate`, never model recollection.
