# Client pages and Settings: what the MVP plan changes

Written 2026-10-20 for the scope freeze, at the owner's request. The owner's attention so far has been on
the research side. This note looks at the two areas he has seen less of: the **client workspace** and
**Nastavení (Settings)**.

**Base and conventions**
- Every claim is against `origin/develop` @ `854c209`.
- A code claim carries `path:line @ 854c209`. Plan claims carry `plan:line`, read at the same SHA.
- Anything not checked against the code is marked **hypothesis** (CLAUDE.md §9).
- "Wave" is the wave `.planning/mvp-execution-contracts.md` gives the chunk (W0 to W5). A chunk that file does not list is marked **no wave**.

**Terminology** (owner, 2026-10-20): the plans' spending **envelope** is now the **wallet**, in Czech
**Peněženka**. This note uses "wallet"; plan quotes keep "envelope".

**Decision** (owner, 2026-10-20, relayed by the coordinator): the MVP ships **`aia-sociomap-5`** (#504), not `-3`. See §5.

**How it was checked**
- The local UI workbench was run on fictional data with no paid calls: `make setup`, `make ui-workbench`, `make ui-fixtures`, `make ui-capture`.
- `make ui-capture` failed on this machine. See finding F-1 in §8. The screens were captured through a temporary local copy of the script, deleted afterwards.
- Eight screenshots are kept under [`shots/`](shots/). The client in them is the workbench's "Horizont Mobility (fiktivní)".
- The code and the plans were read by five read-only agents. Their key anchors were re-opened before they were written here.

---

## 1. For Nigel: what you will notice

**Client pages.**
- Most of the client workspace stays as it is today: Přehled, Výzkumy, Znalosti with its review queue, the intake sheet and Profil.
- Three new things land on it, and the plan has not yet decided where each one goes:
  - **the client's data posture** (OPEN or CLASSIFIED): it decides whether Deep Research may search the web freely for this client;
  - **the client's wallet ceiling**: the most any study wallet for this client may hold;
  - **the data contract** that makes a client's dataset usable in an analysis.
- The plans build the database columns and routes for all three. **None of them builds the screen.** Two plans also disagree on whether posture and ceiling belong on Profil or in Settings.
- The **Data tab** is promised two incompatible futures:
  - the old client-workspace plan says "use in a study: not in AIA yet";
  - the client-data plan builds exactly that use.
- The client-workspace plan's own remaining chunks (C6 to C9: the review queue redesign, the Data tab, retire/restore) are in **no wave at all**. Yet the W1 gate requires them to pass in a browser.
- **There is still no way to delete a client, a source or a knowledge item, and no plan puts a delete button anywhere.** Only the deletion *service* is planned (W4).
- Simulace stays a dead end. It is out of the MVP, but "Nová simulace" still creates a study that can do nothing.

**Settings.**
- The visible changes are small:
  - the **"Vyzkoušet" (test this draft prompt) button goes**, because it is a paid AI start outside the Lead (W1);
  - **Deep Research gains a "Reach" panel**: which search routes are live, approved or refused, and why (W1);
  - **AI běh starts showing what the worker actually loaded**, instead of the web server's own copy of the switches (W1);
  - the **analysis prompts become editable**, and three or four new worker prompts appear (W3).
- **Metodika is formally "after the MVP"**, but it still changes:
  - shipping `aia-sociomap-5` means `-5` must become the method in force and be approved in the Sociomap register;
  - its new steps ("Věrohodnost mapy", "Respondenti a podpora mapy", segments) then become the default view;
  - an edit must start from `-5`, not `-4` as the editor does today;
  - every engine chunk in W2 has to re-pin Metodika steps in the same PR.
- **Settings stays read-only for AI configuration.** Switches stay with the operator (SSM).
- The money words need settling before the first migration:
  - "Strop rozpočtu" on Settings already means the study budget;
  - "Peněženka" is in no plan file;
  - the database names are about to be fixed as `study_envelopes` and `clients.envelope_ceiling_usd`.
- **Můj Vedoucí** (your Lead's page) gets the switch for structural auto-accept and your Lead's file history. The plans have not decided whether the auto-accept switch lives there or in each artifact's header.

---

## 2. Decisions Nigel needs to make

Each comes with a one-line example of what the answer looks like.

| # | Decision | Example answer |
|---|---|---|
| N1 | **Where the client's data posture (OPEN/CLASSIFIED) is set and shown.** #53 says Profil (`deep-research-web-search.md:1662-1665`). I15 says Settings (`mvp-master-plan.md:215`). | "On the client's Profil, in the Pravidla card next to self-approval; admins only." |
| N2 | **Where the wallet ceiling is set**, and **who approves a raise above it, on which screen**. LO1 needs "an approver above it" (`lead-orchestration.md:45-46`); no screen exists. | "Profil → Pravidla, admins only; a raise above the ceiling shows in Přehled → Čeká na vás for an admin." |
| N3 | **The Czech names of the four money numbers.** The client budget (`clients.budget_usd`), the study budget (`budget_usd`, today "Strop rozpočtu"), the study wallet (Peněženka), and the confirmation threshold (`spend_confirm_usd`). F16 is still open (`mvp-cohesion.md:505-506`). Also: rename the schema to `wallet` before M3/M4? | "Rozpočet klienta / Rozpočet studie / Peněženka / Práh potvrzení; the tables become `study_wallets*` and `clients.wallet_ceiling_usd`." |
| N4 | **Where a client dataset's data contract is accepted**: the Data tab (client-workspace C8) or the study's Brief drawer (F19, `mvp-cohesion.md:541-543`). Plus who may accept it: `APPROVE_GATE` or `PROPOSE_CLIENT_KNOWLEDGE` (`client-data-in-analysis.md:101-104`). | "In the Brief drawer when a study first uses it; the Data tab shows the contract read-only; any researcher may accept." |
| N5 | **Fold client-workspace C6 to C9 now** (master plan MP3), so each screen has one owner and a wave. | "Yes: C6→K2f/K3, C8→client-data-in-analysis 2/2a/3, C9→K6, C7 closed as superseded by the client budget." |
| N6 | **Delete in the MVP UI.** Who may delete a client, a source and a knowledge item, and from where. Today there is no route or button for any of them. | "Admins delete a client from Settings → Přístup with a typed confirmation; a researcher removes a source from its card; knowledge is retired, never deleted." |
| N7 | **Where structural auto-accept is switched on**: Můj Vedoucí, or each artifact's header (WCE11, `working-copy-edit-ops.md:111`). | "Můj Vedoucí, one switch per stage, off by default." |
| N8 | **Does removing the draft test also remove the server path?** `POST …/agent-jobs` still accepts `prompt_version` (`apps/api/src/aia_api/routers/research.py:2588-2595 @ 854c209`), so a paid start outside the Lead stays reachable over HTTP. | "Remove the parameter too; no exception to AC-02." |
| N9 | **`aia-sociomap-5` in force.** Two parts. **(a)** Approve `-5` in the Sociomap register at its fingerprint (client-facing). **(b)** Make it the code's default, so every organization starts on it. The alternative is that each organization stores and activates a copy, which would be `-5+e1` and therefore internal-only. | "Register `-5` as approved; the code default becomes `-1` + `-5`; `-3` stays readable on old runs." |
| N10 | **What a methodologist's edit of `-5` means for clients.** Any stored edit (`aia-sociomap-5+e1`) is `INTERNAL_ONLY` until registered (`packages/aia_core/src/aia_core/domain/sociomap_register.py:9-11 @ 854c209`). | "Edits are allowed but internal until the method owner registers them; Metodika says so before activation." |
| N11 | **Simulace in the MVP shell.** Hide "Nová simulace" and the Simulace tab, or keep the "V AIA zatím není" frame. | "Hide the tab and the button until simulation-studio lands." |
| N12 | **Settings as the home for admin-only things no plan places**: Lead admin read and handover (LO11), the OWNER/ADMIN view of kept usage and audit rows (MVPQ-07), and the client delete (N6). | "A new Settings tab 'Správa dat' for delete and kept rows; Lead handover under Přístup." |

---

## 3. Client pages

A shorthand for the code paths:
- `W` = `apps/web/src/`
- `C` = `W/components/aia/clients/`
- `API` = `apps/api/src/aia_api/routers/`
- `cs` = `W/i18n/cs.ts`

**The frame shared by every area**
- `ClientProvider` loads `GET /clients/{id}` once (`C/ClientContext.tsx:63-73`, `API/workspace.py:860-888`).
- Six tabs with counts (`C/ClientContext.tsx:105-116`). Actions: Přidat podklady / Nový výzkum / Nová simulace (`:132-140`). A drop anywhere opens intake (`:142-160`).
- Every member is a Researcher with every client permission (`packages/aia_core/src/aia_core/domain/scope.py:246-248 @ 854c209`), so no permission check hides anything today.

### 3.1 Klienti (`/app/clients`)
- **Today:**
  - Cards for each non-archived client, showing active work and the last change (`C/ClientDirectory.tsx:25-112`).
  - **Nový klient** is open to any member (`API/workspace.py:808-827`).
  - The search label "Hledat klienta nebo studii" is hard-coded, not in i18n (`C/ClientDirectory.tsx:86-92`).
- **Under the plan:** no chunk.
- **Gap:** if posture becomes per client (N1), the list is the natural place to see which clients are OPEN. Nothing plans that. (Hypothesis that it is wanted.)

### 3.2 Přehled
- **Today:** five sections (`C/ClientOverview.tsx:33-205`, `API/workspace.py:1084-1164`):
  - Čeká na vás: knowledge proposals and studies `IN_REVIEW`
  - Aktivní práce
  - Poslední změny znalostí
  - Nejnovější výstupy, which shows the raw `artifact_type` code (`C/ClientOverview.tsx:196`)
  - Kontext klienta, whose counts omit DATASET (`:57-62`)
- **Under the plan:**

  | Chunk | Wave | Change |
  |---|---|---|
  | `client-knowledge-lifecycle#K6` | W3 | Dependent-study change visibility (`client-knowledge-lifecycle.md:23`). Where it shows is not stated (hypothesis: Přehled or the open item). |

- **Gaps:**
  - A wallet raise above the client ceiling needs an approver (LO1). No queue for it is planned; Čeká na vás is the obvious place (N2).
  - `report-delivery#RD3` makes exports follow approval (`report-delivery.md:41-42`). Whether Nejnovější výstupy links to draft downloads that will then be refused is a hypothesis.

### 3.3 Výzkumy
- **Today:**
  - A table with filters Aktuální / Rozpracované / Ke kontrole / Předané / Archiv, two orders, and "Přineslo do znalostí" (`C/StudyList.tsx:56-127`).
  - The project-memory search sits above it (`:142-148`).
- **Under the plan:**

  | Chunk | Wave | Change |
  |---|---|---|
  | `working-copy-edit-ops#WCE2` | W1 | Design reuse, started from this tab's search, becomes a recorded whole-copy write. |

- **Gap:**
  - A new study's budget defaults to 0 (`productization-coherence.md:836`).
  - LO1 adds a wallet but no line says whether **Nový výzkum** asks for a wallet or a budget, or where.

### 3.4 Simulace
- **Today:**
  - The list works, but a simulation study opens `SimulationFrame`: "Postup simulace ve třinácti fázích v AIA zatím není…" (`W/components/aia/SimulationFrame.tsx:15-44`, `cs:504-505`).
  - **Nová simulace** creates a study that can do nothing and cannot be removed (`C/ClientContext.tsx:136-138`).
- **Under the plan:** none. `simulation-studio` is POST (`mvp-master-plan.md:127`).
- **Gap:** the dead end stays (productization finding F107, `productization-coherence.md:779`). See N11.

### 3.5 Znalosti and the review queue
- **Today:** the library (`C/KnowledgeArea.tsx:255-550`, `C/KnowledgeLibrary.tsx:77-447`):
  - views, folders, labels, kinds, bulk filing, the open item with revisions and stale-edit refusal;
  - **Ke schválení** (`C/KnowledgeArea.tsx:47-144`), where an AI proposal shows its quote and locator.
- **Under the plan:**

  | Chunk | Wave | Change |
  |---|---|---|
  | `client-workspace#C6` | **no wave** | Queue grouped by source; diff; editable folder and labels; action-named buttons (`client-workspace.md:313-324`). |
  | `client-knowledge-lifecycle#K2f` | W1 | Review payload with the evidence and "the paying study" beside each proposal (`client-knowledge-lifecycle.md:566-579`). |
  | `client-knowledge-lifecycle#K3` | W1 | Typed revisions and decisions against the reviewed base. |
  | `client-knowledge-lifecycle#K4` | W1 | A study's chosen knowledge frozen into a snapshot ("use in this study"). |
  | `client-knowledge-lifecycle#K8` | W1 | One meaning for Deep Research evidence entering knowledge. A document item's **text** becomes visible to Deep Research. MVPQ-08 keeps client-level extraction here. |
  | `client-knowledge-lifecycle#K5` | W2 | Own dimensions. The study chip links to this queue (`mvp-cohesion.md:544-545`). |
  | `deep-research-web-search#37` | W2 | A Deep Research dataset arrives here as a DATASET proposal. |
  | `client-workspace#C9` | **no wave** | Vyřadit / Vrátit do použití. |
  | `client-knowledge-lifecycle#K6` | W3 | Correction, retirement, conflicts. |
  | `lead-orchestration#LO12a` | W0 | A route-class refusal on source proposals says who fixes it. |

- **Conflicts:**
  - C6 against K2f and K3, and C9 against K6: two plans own one screen (`mvp-master-plan.md:117`). C6 does not list K5's dimension proposals or #37's DATASET proposals among what it shows (hypothesis).
  - K2 (W1) is "complete when [C6, C7, C8] pass the same journey in a browser" (`client-knowledge-lifecycle.md:577-578`). But `mvp-execution-contracts.md` has **no `client-workspace` row at all** (`grep -c client-workspace` = 0). **The W1 gate depends on chunks with no wave.**
  - The 200-item cap with no batch decision (finding F094, `productization-coherence.md:766`) is assigned to C6, which has no wave.
- **Stale code:** `?add=1` is still handled at `C/KnowledgeArea.tsx:271,278-279`, but nothing links to it.

### 3.6 Data tab
- **Today** (`C/DataArea.tsx:17-65`):
  - A list of DATASET and ARTIFACT knowledge items (`packages/aia_core/src/aia_core/domain/knowledge.py:201 @ 854c209`); the tab count counts DATASET only (`API/workspace.py:881`).
  - Rows **cannot be opened**: no columns, no file. The columns are visible only through Znalosti.
  - A "Sdílená data AIA" card.
  - **It says nothing about using a dataset in a study, and no study reads a dataset's rows.** An approved DATASET item does reach design-agent and Lead context as knowledge (`packages/aia_core/src/aia_core/domain/research_agents.py:689-690 @ 854c209`). That only the item's fields, not its rows, reach the model is a hypothesis.
  - See [`shots/client-data.png`](shots/client-data.png).
- **Under the plan:**

  | Chunk | Wave | Change |
  |---|---|---|
  | `client-workspace#C8` | **no wave** | Datasets table; per-column meaning; personal columns must be *Vypustit*; licence; **"Použití ve studii: V AIA zatím není"** (`client-workspace.md:420-431`, read at 854c209). |
  | `client-data-in-analysis#8a` | W0 | Uploaded datasets stay ineligible until a contract is accepted. |
  | `client-data-in-analysis#2`, `#2a` | W3 | The data contract (type, accept route, ledger row) and a quality report shown before accept. Migration **M8**: `client_data_contracts`, `client_dataset_copies`. |
  | `client-data-in-analysis#3`, `#3a`, `#3b` | W3 | Allowlist analysis copy, full-grid reader, accessor. |
  | `client-data-in-analysis#8` | W3 | Brief materials pick a dataset. |

- **Conflicts:**
  - C8 against client-data-in-analysis, F19 and ADR 0027. They disagree on three points:
    - where the contract is accepted: the Data tab, or the Brief drawer (`mvp-cohesion.md:541-543`);
    - which columns are kept: a blocklist ("drop the flagged column") or an allowlist the person classifies (`client-data-in-analysis.md:61-71`);
    - whether a dataset can be used in a study: "not in AIA yet", or built.

    The master plan names this as its own example of "two plans owning one surface" (`mvp-master-plan.md:71-73`). It is still unresolved because MP3 is open.
  - C8's "licence" is not the contract's `use_rights` (`mvp-target-architecture.md:215`).
- **Gaps:**
  - No chunk owns the contract and quality-report **UI**. The workbench Brief chunk 18 says only "Stable classified materials" (`research-lead-workbench.md:175`). See N4.
  - A client's materialized children (K5) are shown nowhere on the client (`productization-coherence.md:782`, F110).
  - Hypothesis, for K8 to decide: a DATASET that Deep Research proposes from a study carries no `content.source_id`, so no contract could attach to it.

### 3.7 Profil
- **Today** (`C/ProfileArea.tsx:414-460`; see [`shots/client-profile.png`](shots/client-profile.png)):
  - Základní údaje
  - Značky a konkurenti, stored as ENTITY knowledge
  - Kontakty
  - The Klient card: "Stav klienta mění správce organizace v Nastavení…" (`cs:75`)
  - **Rozpočet klienta** (`:347-412`): Rozpočet / Utraceno / Rezervováno / Zbývá; "Rozpočet není nastaven: práce AI na klientovi počká…". It is set by anyone with `MANAGE_CLIENT_BUDGET`, which is every researcher.
  - **Pravidla → Vlastní schvalování znalostí** (`:280-319`): admin-only. It can set only true or false, never "inherit", and `self_approval_source` is never shown.
- **Under the plan:**

  | Chunk | Wave | Change |
  |---|---|---|
  | `deep-research-web-search#53` + migration M10 | W1 | `clients.data_posture` CLASSIFIED (default) or OPEN; `PUT /clients/{id}/data-posture`, OWNER/ADMIN, audited, "shown on the client's profile" (`deep-research-web-search.md:1662-1665`). |
  | `lead-orchestration#LO1` + migration M4 | W1 | `clients.envelope_ceiling_usd` (`lead-orchestration.md:5,45`); route `GET/PUT /organization/clients/{id}/envelope-ceiling`, OWNER/ADMIN (`mvp-target-architecture.md:279`). |
  | `client-budget#CB5` | W1 | Proof only; no screen change. |
  | `two-roles-human-ai-gates#5b.4` via `report-delivery#RD2`-`RD4` | W2 | The client's self-approval switch now also governs client-report and map-snapshot approval. |

- **Conflicts:**
  - **Posture and ceiling have three possible homes:** Profil (#53; `mvp-master-plan.md:185`), Settings (I15, `mvp-master-plan.md:215`), and "Settings is read-only and stays so" (`lead-orchestration.md:91`). See N1 and N2.
  - **Permissions split on one card stack:** posture and ceiling are OWNER/ADMIN, while the client budget beside them is any researcher's (`client-budget.md:62`).
- **Gaps:**
  - No chunk builds the ceiling's setter **UI**, its audit display or its test.
  - The design artifact shows the ceiling as "Strop klienta pro peněženku · 60,00 USD · nastavuje vlastník organizace". It shows posture as "Postoj klienta OPEN nastavil vlastník organizace 2. 10." on the study's Deep Research card. Both appear only from inside the study (artifact screens `plan` and `dimensions`).
  - Hypothesis: competitors recorded here become client terms that stop Deep Research searching for them (`productization-coherence.md:763`, F091). How that meets an OPEN posture is not addressed.

### 3.8 Intake sheet: Přidat podklady
- **Today** (`C/IntakeSheet.tsx:68-505`):
  - Files, pasted text, Datová sada or Dokument for a table, personal-column warnings, filing.
  - **Vložit odkaz** is disabled: "Odkaz: v AIA zatím není" (`cs:323-324`).
  - "Navrhnout znalosti z textu": "…platí rozpočet klienta. Tabulky zatím ne." (`cs:363-364`).
  - On develop every proposal run parks, because `AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED=false` (`deploy/develop/docker-compose.yml:254 @ 854c209`).
- **Under the plan:**

  | Chunk | Wave | Change |
  |---|---|---|
  | `client-knowledge-lifecycle#K2e` | W1 | Link capture "beneath the chosen study"; Deep Research import from a same-client study run (`client-knowledge-lifecycle.md:559-565`). |
  | `client-workspace#C7` | **no wave** | "The paying study for AI extraction" (`client-workspace.md:406-418`). |
  | `lead-orchestration#LO12a` | W0 | Refusal copy names who fixes a route-class refusal. |

  Activation: the operator sets `aia_ai_client_source_proposals_enabled`, and the AI route must be widened to Classes A, B and C (`mvp-master-plan.md:172,177`).
- **Conflicts:**
  - C7 and decision D1 ("a study pays", "No client budget", `client-workspace.md:75,495`) are superseded by the built client budget (`client-budget.md:17-22`). C7 is stale.
  - K2e starts study-paid work from a client page. That fits neither MVPQ-08's exception (client-level extraction only, `mvp-owner-decisions.md:175-177`) nor "every AI action through the Lead". Hypothesis: a fee-free link fetch is not an "AI action".

### 3.9 Sources and "Interní dokument"
- **Today:**
  - `SourceCard` shows the reading, **Stáhnout originál**, and "Navrhnout znalosti" for a readable document (`C/SourceFile.tsx:95-157`).
  - The **Interní dokument** toggle shows who marked it and when (`:160-212`, `API/client_sources.py:407`).
  - API routes with no web caller: the source list (`API/client_sources.py:295`) and the re-read (`:378`).
  - No delete. The string "Odebrat soubor" (`cs:386`) is defined and unused.
- **Under the plan:**

  | Chunk | Wave | Change |
  |---|---|---|
  | `report-delivery#RD0` | W2 or W3 | Blocks approval of a deliverable that cites an "Interní dokument" source (MVPQ-09). |
  | `client-knowledge-lifecycle#K8` | W1 | Document text becomes visible to Deep Research. |

- **Conflicts:**
  - RD0's wave: "RD0-RD4 are W2" (`report-delivery.md:75`) against row E20 putting RD0 in W3 (`mvp-execution-contracts.md:43`).
  - Hypothesis: under an OPEN posture, queries drop to Class C and may reach Brave with names included (`deep-research-web-search.md:1672-1675`). Once K8 lets document text shape queries, only the OPEN flag guards client text going to a priced public search. No chunk states that consequence on the client's page.
- **Gap:** what happens to an approved deliverable when a cited source is marked internal afterwards (hypothesis).

### 3.10 Project memory
- **Today:**
  - `MemorySearch` (`W/components/aia/MemorySearch.tsx:25-104`).
  - `MemoryStudy`: read-only revisions, runs with labels, results with `canEdit:false`, and "Použít tento design" → `POST /clients/{id}/memory/reuse` (`W/components/aia/MemoryStudy.tsx:40-353`).
- **Under the plan:**

  | Chunk | Wave | Change |
  |---|---|---|
  | `working-copy-edit-ops#WCE2` | W1 | Reuse becomes a recorded write. |
  | `client-knowledge-lifecycle#K7a` | W5 | Proves same-client reuse (AC-12). |

  `project-memory-reuse` is done and not in the master register.
- **Note on `-5` (§5):** MemoryStudy renders past runs' maps. A run pinned to `-3` stays `-3`, and new runs show `-5`'s map, credibility and respondent layer. So memory will show two map kinds side by side.

### 3.11 Money: the client budget and the wallet
- **Today:** one client money number, `clients.budget_usd` and `spent_usd` (`packages/aia_core/src/aia_core/infrastructure/tables.py:503-509 @ 854c209`).
  - It pays only the client's own AI work, never studies (`cs:99-113`).
  - It is set on Profil.
  - It is lifted from a parked source-proposal run: "Zvýšit rozpočet a pokračovat" (`API/workspace.py:1389-1465`).
  - It appears nowhere in Settings.
- **Under the plan:**

  | Chunk | Wave | Change |
  |---|---|---|
  | `lead-orchestration#LO0` | W0 | Money vocabulary ADR. |
  | `lead-orchestration#LO16` + M3 | W0 | Ledger subject `envelope`. |
  | `lead-orchestration#LO1` + M4 | W1 | Wallet tables and the client ceiling. |
  | `lead-orchestration#LO13` | W1 | Client-level paid AI recorded as an exception to AC-02. |
  | `lead-orchestration#LO15` | W0 | Server-side spend-confirm check. |

- **Gaps:**
  - **"Peněženka" and "wallet" occur in no repository file.** Every plan says "envelope" (`lead-orchestration.md:4-5,45`; `mvp-target-architecture.md:118-140,230,270-279`; `mvp-development-plan.md:157,212,215`; `docs/migration/mvp-acceptance.md:83,85`; `parity-matrix.json:3969`).
  - The only "Peněženka" is the design artifact's.
  - The schema names become fixed at M3/M4 (W0/W1). See N3.
- **Three client-level money concepts** will exist side by side: the budget, the spent amount and the wallet ceiling. F16's "the client's budget" in the study drawer (`mvp-cohesion.md:500-503`) does not say which it means.

### 3.12 Self-approval
- **Today:** one switch on Profil (admin) and the full three-level control in Settings → Přístup (§4.5).
- **Under the plan:** new consumers, with no new control: client-report and map approval (RD3), and AC-13 (`docs/migration/mvp-acceptance.md:94`).
- **Stale:** `mvp-acceptance.md:40` still says "approved by a second person" (master §6.2 flags it).

### 3.13 Deletion and retention
- **Today** (read in code at 854c209):
  - a client or study can only change status, through Settings, admin-only (`API/scope.py:342,457`);
  - **there is no delete route for a client, study, source or knowledge item**;
  - only folders, labels and contacts can be deleted.
- **Under the plan:**

  | Chunk | Wave | Change |
  |---|---|---|
  | `study-data-lifecycle#SDL0`-`SDL6` | W4 | The policy (MVPQ-07: 30 days in backups, a journal replay after restore), FK rules (M12), storage deletes, and the delete service for a study and a client. |

- **Gaps:**
  - No route, permission, confirmation or button for the person who deletes (N6).
  - Per-source delete (productization D-15, F035) is in no MVP chunk.
  - Archiving a client "silently fails all in-flight runs" (`productization-coherence.md:842`), unplanned.

---

## 4. Settings (Nastavení)

**Today's frame**
- `ControlPanel` has eight tabs (`apps/web/src/components/aia/settings/ControlPanel.tsx:750 @ 854c209`), in three groups:
  - Nastavení výzkumu: Metodika, Systémové prompty, Deep Research, AI běh
  - Tým a útrata: Přístup a schvalování, Studie a rozpočty
  - Provoz: Audit, Reference
- Each value is badged "V aplikaci / Spravuje nasazení / Spravuje AIA / Pevné pravidlo".
- Shorthand: `S` = `apps/web/src/components/aia/settings/`.

### 4.1 Metodika
- **Today:**
  - Eight modules (`packages/aia_core/src/aia_core/domain/methodology/registry.py:22-31 @ 854c209`). Five are editable (sociomap, support, aggregation, response, readiness).
  - Any member reads, checks and compares. OWNER/ADMIN stores and activates, with a reason (`infrastructure/methodology_repository.py:237`).
  - Audited.
- **Under the plan:**
  - `methodology-tab` is **POST** (`mvp-master-plan.md:124`). Its open chunks S4d, W1c and X1 have no wave.
  - But Metodika changes anyway:
    - `run-qc-and-checkpoint#RQC9` (W0): "one authority for the valid n". The readiness n limits are **organization-editable methodology** (`domain/methodology/readiness.py:98-129`), so RQC9 must read the version in force, not a code constant. The chunk does not say so.
    - Every Metodika step pins its function's source by SHA-256, so an engine change fails a test unless the catalogue is re-pinned (`domain/methodology/catalogue.py:123-132`). The W2 engine chunks must each carry Metodika work their text does not name: `sociomap-formula-corrections` I1-I5, 3, 4c, 4d, 5b; `segment-maps-and-drilldown`; RQC1.
    - X6 (a methodology change refused in place and routed to Metodika) is a release test (`mvp-acceptance-harness.md:131-133`).
- **`aia-sociomap-5`:** see §5.
- **Gap (hypothesis):** none of these new methods has a named Metodika module: segment clustering, the straight-liner rule (I6), the open-answer coding method (MVPQ-02b), replacement weighting (MVPQ-10).

### 4.2 Systémové prompty
- **Today** (see [`shots/settings-prompts.png`](shots/settings-prompts.png)):
  - Admin-only (`S/SystemPromptsPanel.tsx:86-89`).
  - Editable: the eight design agents and the study Lead (`packages/aia_core/src/aia_core/domain/prompt_slots.py:94-111 @ 854c209`).
  - Read-only: the respondent, `aia.analysis.module` and ten Deep Research prompts (`:117-141`).
  - The flow reads "1 Upravit · 2 Uložit verzi · **3 Vyzkoušet (nepovinné)** · 4 Zapnout".
  - The Lead's slot is listed as raw "**lead**": no Czech name in `cs.ts:773-794`.
- **The draft test** (X10, `system-prompts-settings#14`, W1, "with the stage buttons' removal (E26)", `mvp-execution-contracts.md:88`):
  - Web:
    - **Vyzkoušet** buttons (`S/SystemPromptsPanel.tsx:404,530`)
    - `canTest` (`:314`)
    - `TestRun` (`:685-830`), which calls `researchAgents.start(…, version)`
    - copy at `cs.ts:746-747,754,845,880-896`
  - API: `POST /studies/{id}/research/agent-jobs` with `prompt_version` (`apps/api/src/aia_api/routers/research.py:2588-2595,2735-2756 @ 854c209`).
  - Gate: `prompt_test_requires_administrator` / `_fictional_client` (`packages/aia_core/src/aia_core/application/research.py:1409-1428 @ 854c209`).
  - Chunk 14 says "removes the button and its route use". Whether the server parameter goes too is unstated (N8).
- **Under the plan:**

  | Chunk | Wave | Change |
  |---|---|---|
  | `system-prompts-settings#7` | W3 | The analysis prompts become editable and pinned per run. `research_analysis` lists versions (`apps/api/src/aia_api/routers/settings.py:486-492 @ 854c209` still `[]`). |
  | `system-prompts-settings#13` | W3 | Deep Research and respondent prompts stay read-only ("method") with their pin on the run. Their reason text "not_run_by_any_composition" then becomes wrong. |
  | `lead-orchestration#LO9b`, `#LO9c` | W3, W2 | Three new worker slots: map interpreter, report writer, straight-liner check. |
  | `assumptions-and-open-answer-coding#AOC7` | W3 | A fourth, only if the method allows a model coder. |

- **Gap (hypothesis):** "the eight analysis modules editable" could mean one shared slot (today `aia.analysis.module`, a `{module}` template) or eight. That changes the list on this tab.

### 4.3 Deep Research
- **Today** (see [`shots/settings-deep_research.png`](shots/settings-deep_research.png)):
  - The ADR 0022 settings catalogue in groups. Any member reads; an admin proposes, approves and withdraws.
  - The readiness banner reads "Živý provoz se nespustí: pravidla čekající na schválení: N" (`S/DeepResearchSettingsPanel.tsx:95-176`).
  - Study-test policy drafts exist in the repository only, with no route or UI (`infrastructure/deep_research_settings_repository.py:437-549`).
  - **There is no Reach panel.** The page says "Switches, secrets and the model route are not here" (`S/DeepResearchSettingsPanel.tsx:8-9`).
- **Under the plan:**

  | Chunk | Wave | Change |
  |---|---|---|
  | `deep-research-web-search#52` | W1 | **Reach panel**: each route and connector built / approved / active / refused-by-class, with the reason, from a worker-published composition record. This is the only chunk that makes "Settings → Deep Research lists each route active" true (`mvp-master-plan.md:178`). |
  | `#53` | W1 | Posture. "The Reach panel states each run's posture." |
  | `#51`, `#1` | W0 | ADR 0022 approvals recorded on this tab; the Brave sign-off. |
  | `#8` | W2 | Source tiers "shipped off until the owner approves". No place to approve them is named (hypothesis: this tab). |

- **Conflicts:**
  - The Reach panel is organization-level, while posture is per client and per run. Where a run's posture shows is ambiguous.
  - Override S4 cites "the permission panel … #54" (`mvp-master-plan.md:564`), but #54 builds no panel. The V2 "Oprávnění hloubkového výzkumu" panel is attributed to #53 and LO12 (`.planning/evidence/mvp-prototype-v2/current-disposition.md:79`).

### 4.4 AI běh
- **Today** (see [`shots/settings-ai.png`](shots/settings-ai.png)):
  - Six activities, each shown on/off from `/config` (`S/ControlPanel.tsx:548-591`, `apps/web/src/lib/ai-runtime.ts:36-72`).
  - A read-only box with the region, the model and **"Schválené třídy dat" (`AIA_AI_ROUTE_APPROVED_FOR`)** (`S/ControlPanel.tsx:602-626`).
  - Those values are the **web container's own env** (`apps/web/src/app/config/route.ts:12-30`), not what the worker loaded.
  - It never explains how to fix a class refusal.
  - It omits: the Lead's model, `AIA_AI_POPULATION_PERSONAS_ENABLED`, `AIA_AI_CLIENT_SOURCE_PROPOSALS_ENABLED`, `AIA_REPORT_PDF_ENABLED`, and any client-source-proposals activity (`apps/web/src/lib/public-config.ts:4-12`).
- **Under the plan:**

  | Chunk | Wave | Change |
  |---|---|---|
  | `lead-orchestration#LO12b` | W1 | The worker's composition record; new reasons `retention_unspecified`, `residency_violation`, `training_exclusion_missing`. "Settings is read-only and stays so." |
  | `lead-orchestration#LO12a` | W0 | Refusal copy names the operator. |
  | `mvp-master-plan#MP6` | W0 | The activation profile and the smoke. **The evidence for each switch lives in the smoke, not in Settings.** |
  | `lead-orchestration#LO9a` | W0 | Worker rows, each with a switch, prompt and price. |
  | `research-lead-workbench#11` | W1 | The command registry. |
  | `develop-spend-attribution#5a` | W0 | The model id may become a profile ARN or an `eu.` id; Settings would show it as-is (hypothesis). |

- **Gaps:**
  - The target architecture says Settings' `ai_runtime` "reads the [worker] list, so no screen names a worker by hand" (`mvp-target-architecture.md:257-259`). Neither LO9a nor #11 names Settings as a consumer, and today's activities are hand-written (`apps/api/src/aia_api/routers/settings.py:465-529`).
  - About thirteen new or matrix switches (`AIA_LEAD_PLANS_ENABLED`, `AIA_RUN_QC_ENABLED`, `AIA_CLIENT_DATA_ENABLED`, `AIA_AI_RESEARCH_WORKERS_*`, the Deep Research route switches and others) are visible nowhere.
  - "Models tiered by role, shown in Settings" (`mvp-target-architecture.md:27`) has no chunk.
  - FAST_EXTRACTION is listed as unused because no activity holds client source proposals (`apps/api/src/aia_api/routers/settings.py:530-536`). The master plan assigns the fix to `system-prompts-settings` but names no chunk.

### 4.5 Přístup a schvalování
- **Today:**
  - Members: add and edit, admin-only. No deactivate.
  - Client status: Aktivní / Neaktivní / Archivovaný.
  - **Samoschválení** at three levels, Povolit / Zakázat / Dědit (`S/ControlPanel.tsx:292-496`).
- **Under the plan:**

  | Chunk | Wave | Change |
  |---|---|---|
  | `lead-orchestration#LO11` | W2 | Admin read of a researcher's Lead files, and handover as a copy. Routes `GET /admin/leads/{user_id}`, `POST …/handover` (`mvp-target-architecture.md:280`). **No chunk says on which screen.** |
  | `study-data-lifecycle#SDL3` | W4 | The delete service, with no UI home (N6, N12). |

### 4.6 Studie a rozpočty
- **Today** (see [`shots/settings-studies.png`](shots/settings-studies.png)):
  - Study status, and "**Strop rozpočtu**" for the study budget (`cs.ts:1488-1499`).
  - "Rozpočet studie je strop kontrolovaný před každým placeným voláním… Nad rozpočtem se práce zastaví a zeptá" (`cs.ts:1358`).
  - The client budget is not shown (`apps/web/src/lib/api.ts:1564-1566`), and `client-budget.md:76` says so.
- **Under the plan:** LO1's wallet is set per study in the study header (F16). Nothing plans to show it here.
- **Conflicts:**
  - "Strop" will mean three things: the study budget, the client wallet ceiling and the run ceiling ("Běh může stát nejvýše…", `cs.ts:2539`).
  - "zastaví a zeptá" blurs the cap and the confirmation threshold, which is master G11's point.

### 4.7 Audit and Reference
- **Audit:**
  - Admin-only; the latest 50 events. Czech names come from a hand map (`S/ControlPanel.tsx:722`).
  - The map already lacks `CLIENT_BUDGET_CHANGED` and `RESEARCH_LEAD_PREFERENCES_SET`, and these show as raw codes.
  - The plan adds more with no chunk to name them: posture, ceiling, wallet raise, `LEAD_FILES_READ`, `LEAD_HANDED_ON`.
  - The intro "Posledních 50 udělení, odebrání…" (`cs.ts:1404`) speaks of grants, which ADR 0019 removed.
- **Reference:** unchanged. Its "simulation" group stays for an out-of-MVP feature.

### 4.8 Můj Vedoucí (`/app/lead`)
- **Today:**
  - The Lead's SOUL, USER and notes, read-only.
  - One preference: "Automaticky přijímat textové úpravy Vedoucího (formulace, ne strukturu)" (`apps/web/src/components/aia/LeadProfile.tsx:36-68,127 @ 854c209`).
  - **No link from Settings.** Only the workbench links here, behind `AIA_WEB_RESEARCH_WORKBENCH`.
- **Under the plan:**

  | Chunk | Wave | Change |
  |---|---|---|
  | `working-copy-edit-ops#WCE11` | W2 | Per-stage structural auto-accept, off by default. Its home is undecided: "Můj Vedoucí or the artifact header" (`working-copy-edit-ops.md:111`) against D18's extension of `ResearcherLead` (`research-lead-workbench.md:155-158`). See N7. |
  | `lead-orchestration#LO11` | W2 | Proposed file updates approved one by one, revisions and rollback. This changes CLAUDE.md's "they change only through chat". The page is unnamed (hypothesis: here). |
  | `lead-orchestration#LO14` | W1 | The `AIA_LEAD_*` kill switch (operator). |

---

## 5. `aia-sociomap-5` as the MVP's method: what it means here

**Facts @ 854c209**
- `-5` exists as a preset of the sociomap module, added by #504.
- It is listed **last**, deliberately, "so an edit still starts from aia-sociomap-4 (the page offers the first preset)" (`packages/aia_core/src/aia_core/domain/methodology/sociomap.py:2007-2013 @ 854c209`).
- The code's default pins are `-1` plus `-3` (`packages/aia_core/src/aia_core/domain/research_sociomap.py:323-330 @ 854c209`).
- The register approves only `aia-sociomap-3` (`packages/aia_core/src/aia_core/domain/sociomap_register.py:54 @ 854c209`). Anything else, including `-5` and any `+eN` edit, reads `INTERNAL_ONLY` (`:9-11,92-94`).
- Its own plan lists "Making `-5` the default" under **Not in this plan** (`.planning/plans/signed-off-sociomap-method.md`, § Not in this plan).
- The master plan still says "the MVP uses `aia-sociomap-3`" (`mvp-master-plan.md:126`).

**What "-5 in force" requires**

1. **A register entry** approving `aia-sociomap-5` at its spec fingerprint. Without it, every `-5` map is internal-only: it is refused in the client report and labelled internal on Results and in project memory (N9a).
2. **The default.** There are two routes:
   - **(a) Code.** `default_methods()` returns `-1` + `-5`, and Metodika's "v platnosti" shows `aia-sociomap-5` for every organization with no activation stored.
   - **(b) Activation per organization.** An admin stores a copy and activates it. Activation takes a stored version (`PUT /methodology/{id}/activation`; `null` resets to the code preset). A copy is named `aia-sociomap-5+e1`, so it is **not** what the register approves.

   Route (b) leaves client maps internal unless each `+eN` is registered too. **Route (a) is the one consistent with "the MVP ships -5".**
3. **The editor's starting point.** The editor starts an edit from the stored version in force, else from `presets[0]`, which is `-4` (`apps/web/src/components/aia/settings/MethodologyVersions.tsx:79-86 @ 854c209`). With `-5` in force by code, an admin's edit would start from `-4` and silently switch the method back. Either the preset order changes (`-5` first) or `editStart` uses the preset in force. A test pins today's behaviour (`MethodologyVersions.test.tsx:258`, "the newest preset").
4. **What Metodika shows.**
   - The `-5` steps ("Věrohodnost mapy", "Respondenti a podpora mapy", S7 segments) become what "v platnosti" describes.
   - The `-3`-only steps (Stress-1 bands and the like, which `-5` "nepočítá", `domain/methodology/sociomap.py:769,794`) become "not in force" text.
   - The comparison runs on `-5`'s fixed panels, through BB1 and Interval MDS. A comparison is a compute on the API host (hypothesis: its latency at 40 objects is unmeasured here; the plan cites BB1 at ~9 s compiled).
5. **Editing.** Every `-5` parameter is a specification field with one Metodika step, so an OWNER/ADMIN edits `-5` like `-4` (`signed-off-sociomap-method.md`, Approach). Every stored edit is `INTERNAL_ONLY` until registered (N10). Metodika does not say this before activation today (hypothesis: the activation dialog states no register status).
6. **Existing runs keep their pins.** Pins are never rewritten (`research_sociomap.py:327-328`), so results, project memory and the client report show `-3` maps for old runs and `-5` maps for new ones.

**Client pages**
- No client tab draws a map today.
- Maps reach a client page only through **project memory's** read-only run results (`W/components/aia/MemoryStudy.tsx:318-330`) and the **client report's figures** (`application/client_report.py`, approved maps only).
- Both read the register by method (`apps/web/src/lib/object-map-view.ts`, `mapApproval`), so they follow item 1 automatically.
- Hypothesis, unverified: the respondent layer and segments of `-5` are internal material under MVPQ-03 and MVPQ-09 ("no drill-down content"). Whether the client report may show the respondent map at all is `segment-maps-and-drilldown`'s and RD0's question, not this note's.

**Plan impact:** no chunk schedules items 1 to 3. See "Proposed master-plan edits".

---

## 6. What the V2 prototype and the design artifact show

**The V2 prototype has no client workspace and no Settings screen.**
- The prototype is `prototypes/research-lead-v2`, canonical by MVPQ-01.
- Its entry view is a one-client study list that says "Správa klienta (profil, znalosti, data) zůstává v pracovním prostoru klienta." (`prototypes/research-lead-v2/src/components/Shell.tsx:157`, `src/model/fixture.ts:12 @ 854c209`).
- The study menu says "Správa (členové, nastavení, metodika) zůstává v Nastavení AIA." (`Shell.tsx:58`).
- A methodology change in the prototype is refused and routed to "Nastavení → Metodika" (`src/components/Inspector.tsx:162`).
- So nothing in V2 contradicts today's client pages or Settings, and nothing in V2 designs them.

**The design artifact** ("AIA Vedoucí výzkumu MVP", https://claude.ai/artifact/JrWZXosJtKVLckHhArngeV, read 2026-10-20)
- Eleven study screens: plan, changes, brief, dimensions, fieldwork, results, sociomap, analysis, report, narrow, return. It has **no client or Settings screen** either.
- It shows client-level concepts from inside the study, which the plans must build somewhere:
  - "**Peněženka studie** 40,00 USD · **strop klienta 60,00**". The detail panel reads: "Strop klienta pro peněženku · 60,00 USD · nastavuje vlastník organizace", "Rozpočet studie · strop, který útratu zastaví", "Práh potvrzení · zeptá se, nezastaví". These are its Czech names for N3.
  - "**Postoj klienta** OPEN nastavil vlastník organizace 2. 10. · zafixováno při spuštění" on the Deep Research card.
  - The data contract opened from the Brief's materials, with "Prodeje poboček 2025.xlsx … čeká na smlouvu o datech", "z dat klienta" beside each number. **This is the design's answer to N4: the Brief drawer, not the Data tab.**
  - The client's own dimension, with **Sestavit** refused when "peněženka nemá místo".
  - "Druhá osoba není povinná; nezávislost řídí nastavení samoschválení klienta."
- The artifact's note settles the term: "Obálka plánu (envelope) se česky jmenuje „Peněženka“ (vlastník, 20. 10.). Název měřiče „Studie“ je dál otevřený (F16)."

---

## 7. Stale or soon-wrong copy (no plan touches these)

**Client pages**
- `cs:513`, Společenská inteligence: "Data Library z NPC Panel 18.6.6 v AIA zatím není: příjem zdrojů, jejich návrhy a materializace dimenzí". Partly wrong: intake (`API/client_sources.py:249`), proposals (`:493`) and materialization (`API/materialize.py`) exist.
- `cs:3099` (`/classic`) lists "klientský report" as missing. It exists (`API/research.py:2396`).
- `cs:175,242` "Znalosti klienta vidí (jen) lidé s rolí pro celého klienta". The role grants are gone (ADR 0019).
- Unused strings: `cs:67` `cannotStart`, `cs:386` "Odebrat soubor", `cs:391`.
- `C/KnowledgeArea.tsx:278` comment names a "Přidat znalost" button that no longer exists.
- The overview's output tag shows the raw `artifact_type` (`C/ClientOverview.tsx:196`).

**Settings**
- The whole draft-test copy, gone with #14: `cs.ts:746-747,754,845,880-896`; `S/SystemPromptsPanel.tsx:6,14`; `apps/api/src/aia_api/routers/system_prompts.py:6-8`; ADR 0020's draft-test paragraph (docs PR).
- `cs.ts:1563` respondent activity: "Fiktivní respondenti… Data jsou označená jako fiktivní". Wrong for a panel run (`MODELLED_AI_PANEL`). Visible in [`shots/settings-ai.png`](shots/settings-ai.png).
- `aia.research.lead` has no Czech name, so it shows as "lead". `STUDY_LEAD` has no capability label (`cs.ts:773-794,1633-1642`).
- `settings-guide.ts:3` "rozpočty upravíte u studií" ignores the client budget.
- `cs.ts:1404` audit intro speaks of grants.
- `S/DeepResearchSettingsPanel.tsx:8-9` "switches… are not here" goes stale with #52.
- "Settings is read-only" (`lead-orchestration.md:91,104`; `mvp-development-plan.md:89`) should read "AI route configuration is read-only". Metodika, prompts, Deep Research approvals, members, study budgets and self-approval are all edited there.

**Envelope / Obálka / wallet**
- No money "Obálka" or "envelope" appears in the UI. The only UI "obálka" is the Sociomap terrain's "Terén jako obálka kopců" (`cs.ts:2932`; `apps/web/src/lib/object-map-view.ts:6`). **It must survive a rename.**
- The money "envelope" lives in the plans and in `docs/migration/mvp-acceptance.md:83,85` and `parity-matrix.json:3969,3992`. A change to the latter needs `test_parity_matrix.py`.

---

## 8. Findings

**F-1. `make ui-capture` cannot load Playwright from this environment's global install.**

1. **Claim:** `capture.mjs` resolves `playwright` with `require.resolve`, which gives the CommonJS `index.js`. It imports that as ESM, gets no named `chromium` export, and crashes.
2. **Anchor:** `tools/ui_workbench/capture.mjs:61-75 @ 854c209`, with the crash at `:244`.
3. **Reproduction:** `make ui-capture` on a machine where Playwright lives under `/opt/node-tools` (this cloud image) fails with `TypeError: Cannot read properties of undefined (reading 'launch')`.
4. **Consequence:** no screenshots. Every journey that copies this loader is likely affected (hypothesis; only capture was run).
5. **Smallest fix:** take `mod.chromium ?? mod.default?.chromium`, or import the package's `index.mjs`.
6. **Test that would have caught it:** run `ui-capture --only aia-clients` in the image CI uses for journeys.

Confirmed by replacing the resolved path with `index.mjs` in a temporary copy, which captured 21 screens at two widths.

**F-2 to F-6** are planning gaps already stated above (§3.5, §3.6, §3.7, §4.2, §5). They are hypotheses about the plan, not defects in code, so they carry no reproduction:
- **F-2:** the W1 gate depends on chunks with no wave.
- **F-3:** no UI chunk for posture, ceiling or contract.
- **F-4:** the draft-test server path.
- **F-5:** `-5` has no scheduled register entry, default or editor start.
- **F-6:** no delete UI.

---

## 9. Proposed master-plan edits

These are proposals only. No plan file is edited by this PR (CLAUDE.md §1). They are repeated in the PR body.

1. **§3.2 / MP3:** execute the client-workspace FOLD now. Name the target of C6 (K2f, K3), C7 (close: superseded by client-budget), C8 (client-data-in-analysis 2, 2a, 3 plus a UI chunk) and C9 (K6). Remove "[C6, C7, C8]" from K2's completion line, or give those chunks a wave.
2. **New UI chunks, S3, W1:**
   - posture setter UI (with #53);
   - ceiling setter and above-ceiling approval UI (with LO1);
   - add both to I15's contract chunks, and settle Profil against Settings (N1, N2).
3. **New UI chunk, S3, W3:** data-contract acceptance and quality-report UI, placed in the Brief drawer (design artifact), with the Data tab read-only (N4).
4. **LO0 (W0):** adopt "wallet / Peněženka" and the four Czech money names before M3/M4 fixes `envelope` in schema. Rename `study_envelopes*` and `clients.envelope_ceiling_usd` in the target architecture and development plan (N3).
5. **§3.2:** move `signed-off-sociomap-method` into the register. Add chunks for the `-5` register entry (method owner), the code default `-1`+`-5`, and the Metodika editor's start in force. Correct `mvp-master-plan.md:126` "the MVP uses `aia-sociomap-3`".
6. **`system-prompts-settings#14`:** state that `prompt_version` on `POST …/agent-jobs` and its two refusals are removed too (N8).
7. **`run-qc-and-checkpoint#RQC9`:** the valid-n authority is the organization's readiness methodology in force, not a code constant.
8. **The W2 engine chunks** (`sociomap-formula-corrections`, `segment-maps-and-drilldown`, RQC1): each must name its Metodika catalogue re-pin.
9. **`study-data-lifecycle#SDL3`:** add the entry points (who deletes a client, source or item, and where) (N6).
10. **`lead-orchestration#LO11`:** name the page for admin read and handover, and for file revisions (N12).
11. **Wave contradictions to settle:**
    - RD0-RD4: W2 in `report-delivery.md:75`, W3 in `mvp-execution-contracts.md:43`;
    - `mvp-acceptance-harness#5`: W1-W4 in its own plan, W5 in E24.
12. **§6.2 additions:** the stale copy of §7 belongs to the docs PR or the owning plans, especially `cs:513`, `cs:3099`, `cs.ts:1563` and the audit hand map.
