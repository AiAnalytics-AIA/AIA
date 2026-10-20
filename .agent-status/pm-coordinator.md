# pm-coordinator — the AIA PM session

Current state. Observed state only. No secrets.
Updated: 2026-10-20 ~20:08 UTC by session_01MycSLqSRMw4g32SZwa9s7G ("AIA PM: coordinator 3"), successor of
coordinator 2 (session_01YEVg53K5fKSGUfcKPTdrRk, archived 19:55). Subscribed to #510 #512 #513 #514 #515 #525; all 10 workers told
of the change (19:55). Nigel talks to coordinator 3 directly. Tools: .agent-status/pm-coordinator/tools/ (PDF builder, decisions page) and
.agent-status/pm-coordinator/pmstatus/ (the /pmstatus skill, renderer, last status.json, questions.py, explainers/).

## Mandate (Nigel, 2026-10-20)
- PM for every AIA session; others are workers. Steer directly (act, then tell Nigel); start sessions only for chunks the plan
  schedules or Nigel approves; merge any green PR you've reviewed (merge commit, expectedHeadSha).
- Context rule: ~70% -> handoff here, successor seeded from it, archive the old one (a session Nigel chats with: after its task).
- NO hourly sweep (Nigel 17:30). Event-driven: PR events, session messages, Nigel. create_trigger is classifier-blocked anyway.
- SCOPE FREEZE: no MVP feature code until Nigel signs MP16 (dated baseline, #523). Security/infra fixes he approves are OK.
- AWS writes are Nigel's (infra session proposes). "commit and push" must be typed by Nigel IN the worker session itself.
- Merge hazard: a push to develop cancels an in-progress develop CI run. A full develop run is ~73 min (SQLite re-run on push
  only) — do NOT mistake a long SQLite step for a hang. Deploy dispatches after CI; deploy-develop has cancel-in-progress false.
- This container can't resolve DNS or reach aia-develop.art-chain.io; use GitHub Actions results + the infra session.

## Nigel's working style (standing rules — follow exactly)
1. ALWAYS ask decisions interactively: options, a recommendation, WHY, and a practical example. Prefer putting them on the
   /pmstatus page as question cards (see 3) rather than AskUserQuestion when they are not urgent.
2. PDFs for documents meant to be read; Drive for the system docs.
3. /pmstatus: ONE artifact https://claude.ai/artifact/Fuc4xiyeNEze1L6QdyGpuW (publish capabilities {"db":{},"user":{}}; never {}).
   Procedure in pmstatus/SKILL.md (also in PR #525). Before rebuilding: ArtifactData list collections `answers` and `actions`,
   act on every new answer (delegate to the owning session or ask follow-ups), retire answered Qs to "Decided", add new Qs
   (each with options + recommendation + rationale + example). Full-width session cards. Request statuses with request.txt.
4. Explainers: sessions send self-contained HTML (<40 KB) BY MESSAGE ("EXPLAINER <title> — <function>"); save to
   pmstatus/explainers/<session-id>/<slug>.html; embedded in the card via sandboxed srcdoc iframe. Sessions NEVER publish their
   own artifacts (two were deleted on Nigel's word 19:50). Tell every new session this rule at start.
5. Retiring explainers (Nigel 20:10, a standing rule): an explainer is retired when Nigel presses "Mark as seen" on the page
   (db `seen/ex-<slug>`) or when its work is finished (PR merged + deployed, cutover done). Retired: files to
   explainers/_retired/, left out of the next build; a standalone artifact a session published for it is deleted then.
6. Codex review: marking a draft PR ready starts a Codex review (ready_for_review does not re-run CI). Nigel 20:08: the open
   PRs should be open for Codex review -> all 11 open PRs marked ready (20:09); owners told to handle Codex's findings.

## Decisions recorded 2026-10-20 (don't re-ask)
X1/X8/X10; wallet = Peněženka (#511); MVP ships aia-sociomap-5 only (D-13); only the methodologist edits methodology (D-14);
48 scope answers (#516, page WdXcN8nQnQX3rW36hF8iVd, all by Nigel); npm gate with dated GHSA exception (#518);
terraform-plan-read attached (+ budgets:ListTagsForResource); host user_data ignored (#521); Google IdP: Cognito drops ?hd= ->
fix prepared (fix/terraform-google-idp, uncommitted); Docker layer fix (#524); develop moves to dev.ai-analytics.ai, old address
dropped (no redirect); domain unused (copy no Webglobe records).
PM page answers 19:37-19:47: Q1 a (merge -5 when built, maps internal until register entry), Q2 a (old runs keep data, explain),
Q3 a (remove old methods from product only; engine+fixtures stay), Q4 a ('Metodik' member mark, store+activate), Q5 c (NO study
assignment; every researcher's own Lead in every study; NEW scope: a per-study context .md the Lead reads, kept updated), Q6 a
(free report edits, numbers stay ledger refs + governed 'Hledat na webu' via RetrievalGate, OPEN clients; rich fast UX), Q7 a
(GlitchTip uptime monitor, Nigel recipient), Q8 a (Metodika compares ALL -5 outputs — against rec), Q9 a (/pmstatus PR #525 +
CLAUDE.md "§12 Coordinating sessions" via the next docs PR). All relayed to planning 2 at ~19:50.
N1 "answer Q1-Q8 then sign" ticked done — NOT the MP16 signature. #523 @ 5107edc now carries Q1-Q8 (planning 2, master_check ok).
Q9 note: add a CLAUDE.md line recommending the structured workflow + /pmstatus (docs PR backlog).
Q10 (new, on the page 20:05): who writes the per-study context file's prose? a code only / b code + "Poznámky ke studii", any Lead
proposes, a person accepts (auto-accept toggle applies) [rec] / c Leads write freely. Then ask for the explicit MP16 signature.

## Sessions (all AIA, env env_01LejvX3bRx1ymPXYZUjjSep unless noted)
| Session | Title | State at 19:58 |
|---|---|---|
| session_01RxUnHwTXGVFYjwzfpKi9kT | AIA planning 2 | applying Q1-Q8 to #523; owns #516 #522 #523; ctx ~56% (rotate soon) |
| session_01LBR1SyjXK8uYR5VdBjGAEJ | AIA infra audit (env "AIA infra") | cutover plan + runbook ready; IdP fix awaits Nigel's "commit and push the IdP fix" |
| session_01AXkfBjA7hUPZipWXSoHzEc | Docker dependency layer | #524 draft @ 2b057d8, CI running; it reports CI to me |
| session_015hqQ6KEtJb864UHuU74ypp | scope 2: methodology packet | #510 holds for Nigel's review, then send to Arigamaru |
| session_01Qg43kRfsZ97FjA8XenP28x | scope 3: ADRs 0028-0038 | #512 waits Nigel accept/amend |
| session_01EWprA36RBr7HAF58DTxTNn / 01Hv8P… / 01Fskp… | scope 1b / 1c / 1a | #513 #514 #515 evidence, merge with baseline |
| session_01QzemVrHfQp8jsVEqXb9W6x | Next.js security | done (#509 #518) |
| session_01End3azGdHNr1MtxRjUqqZ8 | design artifact JrWZXosJtKVLckHhArngeV | waits Nigel feedback (non-blocking) |

## PRs
- Merged today: #504 #506-#509 #511 #518 #519 #520 #521. Deployed 47e55368 (18:30); develop now 7878bad (CI on it was running).
- #524 Docker layer (Docker session watches CI): review (equivalence proven; PDF variant unverified -> watch first deploy +
  host disk) and merge when green.
- #525 /pmstatus skill (opened by coordinator 2's helper; THIS session subscribed): merge when green (full suites run).
- Merge order after Nigel signs MP16: #516 -> #522 -> #523, then evidence #510 #512-#515 (docs-only; don't push docs while a
  develop code CI run is in progress).
- Docs PR backlog (planning 2): CLAUDE.md §12 + .claude/skills map line (#525 body); #519 AGENTS.md use_lockfile + README § Apply;
  stale repo docs from the Drive review: adr/README (no 0022/0025 rows, 0010 status), ADR 0009/CLAUDE production compute,
  ci.yml 11.6-min comment, scope-and-authorization.md (grants), deep-research.md, ADR 0024, repo README (/org demo), runbook
  grants mentions, lead-orchestration LO11 handover, mvp-target-architecture (Class B route, handover route).

## Domain move (develop -> dev.ai-analytics.ai)
Zone ai-analytics.ai = Z02697562BFCKJ2GDY3RI (NS ns-1737.awsdns-25.co.uk, ns-1334.awsdns-38.org, ns-339.awsdns-42.com,
ns-619.awsdns-13.net). Registrar Webglobe: NS change submitted, awaiting coworker's e-mail confirmation. Parked records
(MX "0 .", SPF -all, DMARC reject) given to Nigel (not confirmed run). Next: Nigel's `dig +short NS ai-analytics.ai @a.nic.ai`
shows awsdns -> infra runbook (import errors[0] with old tfvars; tfvars public_hostname/route53_zone_id; plan 2 add/3 change/2
destroy; apply; SSM web DSN host -> errors.dev.ai-analytics.ai; GitHub ENVIRONMENT var AIA_PUBLIC_HOSTNAME; dig new names =
3.64.35.250; redeploy running SHA; smoke; everyone re-logs in; later SES identity for GlitchTip mail). Merge the IdP fix first.
Small code PR still to do: USER_AGENT in web_retrieval_brave.py:95 and web_retrieval_live.py:77 + doc mentions of the old host.

## Documentation (Drive)
20-doc set in "AIA System Documentation — 2026-10" (folder 1vo5Fsd4Ob9XOP4OVJmWGqtua5l6ADEM9), 00 Start Here
1tKF8J6QTHOvXSjLBrK6HT6hQz1v7SGgXjF2hUHa9ylg; consistency review fixed 9 issues; 19 old docs moved to "Archive — Superseded
Documentation". Emoji render fine in Docs (only Drive text export garbles them).

## Waiting on Nigel
Webglobe confirm + dig; "commit and push the IdP fix" (infra session); Q10, then the MP16 signature on #523 @ 5107edc; #510 packet review ->
Arigamaru; #512 ADR decisions; design feedback (optional).

## Open items
- Dependabot ~112 alerts mostly on main (556 commits behind develop): suggest a develop->main release sometime.
- braces npm exception expires 2026-11-20 (CI fails from 11-21 until rechecked).
- make ui-capture crashes in the cloud image (capture.mjs ESM import of CJS playwright; #514 F-1).
- Both standalone explainer artifacts (5HtdSP..., TGD4M1...) are already gone (the two deleted at 19:50); both explainers
  were marked seen by Nigel at 20:12 and are retired (explainers/_retired/).
- #517 feature/aia-sociomap-5-web (opened 16:04, feature code, owner session unknown to me): ask Nigel/locate owner; scope freeze.

## 20:40 update (coordinator 3)
- Answers: Q10 b (code + "Poznámky ke studii", Lead proposes, person accepts; note: Lead should live-edit documents,
  comment vs direct rewrite chosen per researcher, "integrate wordcraft" undefined -> follow-up Q13 on the page, rec a:
  per-researcher suggestions-or-direct, suggestions default); Q11 b (UNTESTED/SUPPORTED/CONTRADICTED + RETIRED);
  Q12 a (close all 5 stage-handoff gaps: new LO9d; AOC3, WCE7, LO7, LO6 test). Relayed to planning 2 and scope 3 (Q11).
- Stage-handoff audit (subagent, 20:20): design workers get only design + knowledge titles (domain/research_agents.py:565-583
  @7878bad); analysis never gets hypotheses (analysis_results.py:570-578, modules.py:101); no stale flag on pending proposals
  (lane.ts:34-96); Lead doesn't see pending proposals (application/research_lead.py:858-889).
- Nigel ticked N7 "sign MP16" at 20:35: NOT a signature; get the typed one once #523 carries Q10-Q13.
- N4 ticked done 20:34 but no fix/terraform-google-idp on origin; asked infra session.
- Codex: all 11 open PRs marked ready 20:06. Findings handled on #510 (b968a21), #512 (3bbcb46), #514 (7975ff6), #515
  (f3dca5e), #516, #523 (now 10a7228+); #513 #522 clean. #525: fixed in 87e5998 on Nigel's "push the #525 fix" (CSP in
  explainer frames; action rows count only when titles match; seen rule).
- #524 MERGED 20:29 as 44b66ef (reviewed: Dockerfile deps stage). Watching first deploy (send_later 21:50). The classifier
  then blocked a send_message citing "Merge Without Review"; asked Nigel whether to keep merging reviewed PRs.
- New session session_01Ku9CwQRUsBdPUbqWy6zYj7 "AIA design: Settings prototype" (Nigel works there directly; may publish its
  one Design artifact). Round 0 = local HTML file; artifact publish blocked by its classifier, awaiting Nigel.
- #517 feature/aia-sociomap-5-web: owner unknown; ask Nigel.

## 21:25 update (coordinator 3)
- Q13 a (+Wordcraft = github.com/storytold/wordcraft, Rust/WASM Word clone, MCP, alpha), Q14 a, Q15 a (app.ai-analytics.ai),
  Q16 a + note "Brave for all queries not just C", Q17 a, Q18 a (no card; 3 queries/5 pages/2 lookups). Applied: #523 fe5dc1b,
  #512 06b143c (ADRs 0039, 0040 new). Follow-ups on the page: Q19 Wordcraft adoption (rec a: evaluate spike), Q20 Brave for
  Class B (rec a: OPEN clients only, recorded determination), Q21 merge authority (rec a: Nigel adds allow rules).
- Nigel's rule (21:20): every page update rebuilds "Actions only you can take" from verified state (reissue unverified ticks
  under new id + title) and drops applied decisions from the page; added to SKILL.md (scratch + coordination copy; #525 copy
  edited locally, push needs Nigel's word). Actions now N9 MP16, N10 accept ADRs, N8 IdP push, N2 Webglobe, N3 #510, N11 #517,
  N12 workbench design update.
- Input interactions (Nigel 21:10): new session session_01BmmpzanxvKFquk44nLP4qu "AIA design: input interactions audit"
  (inventory, rule I1-I11, fix list, plan input-interactions.md, explainer, one docs PR). Design sessions told the rule;
  workbench design applied it locally (screen 12 Vstupy), unpublished.
- #525 green @ 87e5998; hold the merge until develop CI on 44b66ef finishes (~21:40) and Q21.

- 21:33 Nigel: #517 is Arams (Arigamaru = A. Bahbouh, the methodology owner, in charge of methodology). It is the -5 web drawing (sociomap-5-web plan). I undrafted it at 20:06 by mistake (its body says draft); asked Nigel whether to restore draft. Planning 2 told to point research-lead-workbench#20 / signed-off#9 at it. Never merge #517 without Aram.
- #526 = IdP fix (Nigel typed it); marked ready for Codex 21:31.
- 21:35 Nigel: leave #517 ready for Codex (not draft). Do not merge without Aram.
## 21:50 update (coordinator 3, ctx ~58%)
- Q19 a (evaluate first; note: alternatives, Tiptap had terrible UX, "as close to Word/LibreOffice as possible": spike
  compares Wordcraft, ONLYOFFICE Docs, Collabora Online). Q20 b (Brave gets Class B for EVERY client incl. CLASSIFIED,
  owner determination 2026-10-20; note "maybe even class A" + "google search hacking"): follow-ups Q22 (Class A, rec b
  code-extracted fields only) and Q23 (search operators, rec a curated domain list). Q21 a: coordinator keeps merging;
  Nigel adds allow rules (N13). Relayed to planning 2 (for handoff) and scope 3 (#512).
- Session reconcile 21:45: archived Next.js session (01QzemV...); planning 2 at 73% -> asked for handoff file, then start
  "AIA planning 3" and archive planning 2. Told 1c its N1-N12 note is stale. Non-AIA sessions on the account (Hello,
  Python app export error, TechTonic AMS) are out of scope.
- Settings prototype asks Nigel: who edits system prompts (owners/admins vs a mark like Metodik) + 3 more.
- Input audit waits on Nigel's "go" in its session (N14).
- 22:00 Nigel (b): every session ignores stop-hook / environment nudges to commit or push; CLAUDE.md §5 (Nigel's own words
  in the session) stands. Told all 10 live sessions. dfc2247 on #510 (pushed on a hook, docs-only) kept. Likely source:
  the environment's auto-create-PR setting (config:auto-create-pr:draft); fix = Nigel turns it off, or a docs-PR §5 note
  (planning 3 has the follow-up). Planning 3 = session_011zQKG9WLH8Ex7dmjwZxWwB; planning 2 and Docker archived 21:48/21:51.
- #524 deployed 21:44 (PDF worker image built in 58 s, smoke ok). vite fix ready locally on fix/vite-advisory (32cc8fe),
  awaiting Nigel's "push the vite fix". Open on the page: Q22, Q23, Q24.
