# Scope freeze: the product owner's decision list

Written 2026-10-20 for Nigel Blount (product owner) by the planning session, on the coordinator's
request (freeze step 4, part 1). It consolidates every question that is Nigel's from the five
scope-freeze inputs, all draft PRs against `develop @ 86ec0cdd`:

| PR | Input | What it asks Nigel |
|---|---|---|
| #510 | `.planning/mvp-methodology-packet.md` | E-3's "-1 beside -5" (the MQ items are the methodology owner's and stay in the packet) |
| #512 | ADRs 0028-0038 (Proposed) | each ADR's *Open for Nigel* |
| #513 | `.planning/evidence/scope-freeze/reverse-scope-audit.md` | scope questions 1-23 |
| #514 | `.planning/evidence/scope-freeze/client-and-settings-impact.md` | N1-N12 |
| #515 | `.planning/evidence/scope-freeze/crosscheck-tracks-5-7.md` | G58-G78 where a fix needs a product call |

It is evidence for the baseline, not the baseline. Nothing here changes a plan; part 2 of step 4
applies the answers to `mvp-master-plan.md` and the child plans, and writes the dated baseline for
Nigel to sign.

## How this list was made

- **Left out: the methodology owner's questions** (A. Bahbouh, MQ-01 to MQ-24 and R-1 in #510;
  ADR 0034's MVPQ-02b, 0036's MVPQ-10, 0037's ADR 0027 Q1/Q2/Q4; 0038's MQ-01/04/06). They go to
  him in the packet.
- **Dropped: already decided**, with the record:
  - the MVP ships `aia-sociomap-5` (MVPQ-13, 2026-10-20, #510);
  - wallet / Peněženka, in code, plans and schema (`study_wallets*`, `clients.wallet_ceiling_usd`;
    #511, `lead-orchestration#LO0`). That settles #514 N3's schema half;
  - X1, X8, X10 (#507); the product parts of MVPQ-03/05/06/09, and MVPQ-07/08 (#506);
  - **#512 ADR 0032 Q1, the release route:** MVP-27 as amended on 2026-10-19 (#500) already says an
    OPEN client's queries go to Brave and the Class B route is deferred (`overview.md:599`). The
    ADR's citation of MVP-27's struck-out text is a stale reading, listed under fixes below;
  - **#514 N11 / #513 proposed edit 11, hide Simulace:** MVP-31 (`overview.md:603`);
  - **#513 Q12, Deep Research context in the client report:** MVP-26 (`overview.md:598`) says
    yes, as cited context, never respondent evidence. Only the chunk is missing (fixes below);
  - **#514 N9(b), code default versus per-organization activation:** "the MVP ships -5" can only
    mean the code's default (an activated copy is `-5+e1`, which no register entry matches;
    #514 §5, #510 E-1). It is a fix, not a choice. N9(a), the register approval, is MQ-01.
- **Merged: the same question asked in more than one place.** Each item names every source.
- **Ordered by what the answer unblocks:** W0 contracts first (the money, the edit vocabulary and
  the acceptance wording, which E01 and E02 of `mvp-execution-contracts.md` need before any
  dependent migration), then W1, then the production track (which runs beside W1 and gates
  release), then W2-W3, then pure scope additions (in or out; an "in" adds chunks).
- Every answer is one of the options or "other". Each recommendation is the planning session's,
  and is labelled as such.

**Count: 48 decisions.** Part A 11, part B 7, part C 11, part D 8, part E 11.

---

## Part A. W0: the contracts every later chunk is built on

### D-01. The Czech names of the four money numbers

- **Question.** What does each money number say on screen, written once in the copy module so no
  screen invents its own?
- **Example.** The header today would show "Strop rozpočtu 12,00 USD" for the study budget,
  "Peněženka 3,00" for what the Lead may spend without asking, and the confirmation threshold
  unlabelled; F16's open item is exactly this (`mvp-cohesion.md:497-506`).
- **Options.**
  - (a) Rozpočet klienta (`clients.budget_usd`) / Rozpočet studie (`budget_usd`, renaming today's
    "Strop rozpočtu") / Peněženka (the wallet) / Práh potvrzení (`spend_confirm_usd`).
  - (b) As (a), but keep "Strop rozpočtu" for the study budget, because Settings already uses it.
  - (c) Other names.
  - Either changes `lead-orchestration#LO0` (the vocabulary), `research-lead-workbench#15` (the
    header's two meters, Q20) and Settings → Studie a rozpočty.
- **Recommendation.** (a): "strop" next to "Peněženka" reads like a second cap, and the wallet is
  a slice of the study budget, not of a cap.
- **Sources.** #514 N3; #512 ADR 0028; `mvp-cohesion.md` F16.

### D-02. Does approving a plan count as confirming its spend?

- **Question.** When a plan's step would reach the study's confirmation threshold
  (`spend_confirm_usd`), does the plan's approval count as the confirmation, or does the step park
  and ask again?
- **Example.** Threshold 5 USD. The plan card says "Spustit sběr, strop 4,80 USD; analýza, strop
  0,90 USD" and you approve it. Fieldwork plus analysis reaches 5,70. Under (a) it parks before
  the analysis and asks "Potvrdit 0,90 USD?"; under (b) it runs, because you saw both ceilings on
  the card.
- **Options.**
  - (a) Park and ask again (ADR 0028 as written; target architecture §3.4).
  - (b) The plan's approval records a confirmation for each step's ceiling the card showed; a step
    whose ceiling grew since the card was shown parks.
  - Changes `lead-orchestration#LO4` (the card shows each ceiling against the threshold),
    `#LO9a` (the server's confirmation rule), ADR 0028 decision text, AC-04.
- **Recommendation.** (b). (a) asks twice for a number already on the card. (b) keeps the
  threshold meaningful, because a ceiling that grew still parks.
- **Sources.** #512 ADR 0028 Q1.

### D-03. A wallet raise above the client's ceiling

- **Question.** When a raise would take a study's wallet above the client's wallet ceiling, is it
  refused, or approved by someone?
- **Example.** The client's ceiling is 20 USD per study wallet. A researcher asks to raise a
  wallet from 15 to 25. Refused: an OWNER or ADMIN must first raise the client's ceiling to 25 on
  the client's page. Approved: the request waits in Přehled → Čeká na vás for an OWNER or ADMIN.
- **Options.**
  - (a) Refused; only raising the ceiling itself lets a wallet grow (ADR 0028; target
    architecture §3.3).
  - (b) An approver above it (LO1's test), which needs an approval queue and a screen.
  - (b) adds a UI chunk and a ledger subject (`lead-orchestration#LO1`, `mvp-master-plan#MP4`'s
    M3 contract); (a) changes LO1's test text only.
- **Recommendation.** (a). There are about ten users; a queue nobody watches is worse than a
  refusal that names who can raise the ceiling.
- **Sources.** #512 ADR 0028 Q2; #514 N2 (the "who approves" half; the screen is D-17).

### D-04. Does a plan stop when the design moves?

- **Question.** If the Design Revision a plan was approved on changes while the plan runs, does
  the whole plan stop, or do its unaffected steps go on?
- **Example.** You approve "sběr → analýza → zpráva". During fieldwork a colleague edits Q7's
  wording. Stop: the analysis does not start, and the card says the design moved. Continue: the
  run finishes on the revision it was started from, and only a new plan uses the new wording.
- **Options.**
  - (a) Stop the plan at its next step (ADR 0028).
  - (b) Finish the steps already tied to the immutable revision; stop only steps that would start
    from the working copy.
  - Changes `lead-orchestration#LO3` / `#LO10` (the card's revision check) and ADR 0028.
- **Recommendation.** (b). A run executes one immutable revision (ADR 0016), so finishing it is
  safe, and stopping it wastes paid fieldwork. (a) is simpler to build.
- **Sources.** #512 ADR 0028 Q3.

### D-05. Deep Research spend in the wallet before the tool ledger exists

- **Question.** Until migration M11 records tool spend (`production-environment#PE7`,
  `deep-research#4`, W3), is a Deep Research run charged to the wallet at its ceiling?
- **Example.** A Design Research run's ceiling is 2,00 USD and it really spends 0,60. Until M11,
  the wallet shows 2,00 spent for it; after M11 it shows 0,60 and the rest returns.
- **Options.**
  - (a) Charge the ceiling, reconcile after M11 (ADR 0028).
  - (b) Keep Deep Research outside the wallet until M11.
- **Recommendation.** (a). Over-counting is the safe direction for money ("never score unknown as
  good").
- **Sources.** #512 ADR 0028 Q4.

### D-06. Edit conflicts per field or per item

- **Question.** Do two people's edits of the same questionnaire item conflict only when they
  touch the same field, or whenever they touch the same item?
- **Example.** Your Lead rewords Q4; a colleague changes Q4's options at the same time. Per field:
  both land. Per item: the second is refused with "Q4 se mezitím změnila".
- **Options.**
  - (a) Per field, `(item_key, field)` (ADR 0029; target architecture §3.1).
  - (b) Per item (`working-copy-edit-ops#WCE5`'s wording).
  - Changes `working-copy-edit-ops#WCE0` (W0 vocabulary), `#WCE5`, and ADR 0026 decision 5's
    reading.
- **Recommendation.** (a): fewer refusals with two researchers; wording and options are
  independent.
- **Sources.** #512 ADR 0029 Q1.

### D-07. What an unaccepted proposed change becomes

- **Question.** When a person moves on without accepting a proposed change, is it recorded as
  rejected, or as stale when it conflicted?
- **Example.** The Lead proposes three changes; you accept two and close the panel. The third is
  stored as `REJECTED`. Had a colleague's edit made it impossible to apply, it would be
  `DROPPED_STALE`.
- **Options.** (a) `REJECTED` by default, `DROPPED_STALE` on conflict (ADR 0029; target
  architecture §3.5); (b) it stays pending until someone decides. Changes
  `working-copy-edit-ops#WCE7` / `#WCE9`.
- **Recommendation.** (a). A pending change nobody looks at again makes the Lead re-propose it.
- **Sources.** #512 ADR 0029 Q2.

### D-08. Explicit yes to amend ADR 0026 and ADR 0008

- **Question.** Four of the proposed ADRs change Accepted ADR 0026, and one changes ADR 0008, a
  frozen invariant. Do you give the explicit yes those amendments need, recorded in each amended
  ADR?
- **Example.** ADR 0026 decision 7 says a paid AI start needs a person "every time"; ADR 0028
  makes one approved plan cover its steps. ADR 0008 classes every search query; ADR 0032 lets an
  OPEN client's queries go out unclassified. Without your yes, accepting 0028 still leaves 0026
  saying the opposite.
- **Options.**
  - (a) Yes to each amendment as its ADR is accepted: 0026 d5, d6 (by 0029), d7 and *Accepted
    with* 4 (by 0028), d8 and *Accepted with* 6 (by 0030); 0008 (by 0032); and the "frozen
    retrieval" wording in CLAUDE.md §2 and ADR 0021 (0032 Q2).
  - (b) Yes to some, named.
  - (c) No: the ADRs are rewritten to fit 0026 and 0008 as they stand, which removes plan
    approval (LO4-LO7) and the open posture (#53).
- **Recommendation.** (a), recorded in each amended ADR's amendments list, as the 2026-10-19
  amendment of 0008 was.
- **Sources.** #512 ADR 0028 Q5, 0029 Q6, 0030 Q4, 0032 Q2 and Q3.

### D-09. What AC-14 checks, given AIA has no edition file

- **Question.** AC-14 asks that "a malformed edition file refuses to start" and that the
  configuration is "recorded on the run". AIA replaced the edition file with typed settings by
  design. What should AC-14 check?
- **Example.** Today a worker with `AIA_AI_RUNTIME_ENABLED=maybe` stops by name, which is the
  typed-settings equivalent. But `GET …/research/runs/{id}` records nothing of the AI runtime,
  model binding or switches the run ran under.
- **Options.**
  - (a) Build an edition file (new work, no other use).
  - (b) Reword AC-14 to typed settings, plus a composition digest stored on each run
    (`lead-orchestration#LO12c`, proposed by #515; #513's `mvp-master-plan#MP6b` is the same
    record).
  - (c) Reword to typed settings only and drop "recorded on the run".
  - Changes `docs/migration/mvp-acceptance.md` AC-14, `parity-matrix.json`'s criterion,
    `mvp-acceptance-harness#14` (W0) and `#5`.
- **Recommendation.** (b). The digest is small, and it is what lets a reader say which model and
  switches a past run used.
- **Sources.** #513 Q15 and proposed edit 8; #515 G74.

### D-10. How a refused Deep Research run ends

- **Question.** A Deep Research run refused because its design is unclassified, or because a live
  setting is unapproved: does it fail, or wait?
- **Example.** Today it parks as "AI běh není dostupný" with "Pokračovat v běhu", and pressing it
  only parks it again, because the run's pin is frozen. AC-11 says "refused whole"; chunk 53 says
  both "fails whole" and "still parks".
- **Options.**
  - (a) A terminal failure, worded by its cause, retryable under fresh pins after the approval.
  - (b) A wait with its own reason (not `ai_runtime_unavailable`), and no Resume until the cause
    is fixed.
  - Either settles `deep-research-web-search#53` (W1, E12), AC-11's negative case and
    `lead-orchestration#LO12a`'s words.
- **Recommendation.** (a): it matches AC-11 as written, and a terminal run is what the person
  expects after "refused".
- **Sources.** #515 G68.

### D-11. How the acceptance run proves the archive route

- **Question.** I-R and AC-11 require the web archive route, but a run only uses it for a dead,
  moved or changed page. How does the acceptance run prove it?
- **Example.** A study cites a ČSÚ page; if that page is live and unchanged, the run never asks
  the archive, and I-R is blocked by luck. Re-running to get archive evidence spends the USD 25
  allocation.
- **Options.**
  - (a) The acceptance study cites one known dead URL, so a real run meets the archive.
  - (b) A recorded archive probe outside a run, with I-R reworded to accept it.
  - (c) Drop the archive from I-R.
  - Changes `deep-research-web-search#54` (W0, E05) and `mvp-acceptance-harness#11`.
- **Recommendation.** (a). It proves the route inside a run, which is what I-R means, at no extra
  spend.
- **Sources.** #515 G70.

---

## Part B. W1: what the first build wave needs

### D-12. How Deep Research starts between W1 and W4

- **Question.** `research-lead-workbench#26` removes the manual AI start buttons in W1, but the
  Lead's Deep Research cards (`#23`) come in W4. Until then, how does a person start Deep Research?
- **Example.** In W2 a researcher wants Design Research on RQ1. Under (a) they ask the Lead and
  approve a plan step "Rešerše k RQ1, strop 1,50 USD". Under (b) the old "Spustit rešerši" button
  stays, marked as the one exception to AC-02.
- **Options.**
  - (a) New `lead-orchestration#LO5a` in W1: Deep Research as a plan-step kind and a typed chat
    start.
  - (b) `#26` keeps the two Deep Research buttons as a labelled exception to AC-02 until `#23`.
- **Recommendation.** (a). AC-02's "no manual AI start" holds from W1, and I-R, E27 and E28 get
  their runs through the path the MVP ships. It adds one W1 chunk to E10's path.
- **Sources.** #515 G69.

### D-13. Does a new run keep pinning `aia-sociomap-1` beside `-5`?

- **Question.** Until the web can draw `-5` (E-3, W2), should a new run also compute `-1`, so it
  still has a map on screen?
- **Example.** A run started in W1 computes `-5` (stored, not drawn) and `-1` (drawn, the old
  picture, labelled internal). Without `-1`, Results says the map is computed but cannot yet be
  shown.
- **Options.**
  - (a) Pin `-1` + `-5` until E-3 lands, then `-5` alone (each battery computed twice meanwhile).
  - (b) `-5` alone now; no drawn map until E-3.
  - Changes the proposed `signed-off-sociomap-method#8` and ADR 0038's default.
- **Recommendation.** (a). The second computation costs seconds, and every W1-W2 journey keeps a
  map to look at.
- **Sources.** #512 ADR 0038 Q1; #510 E-3.

### D-14. A methodologist's edit of `-5`, before it is registered

- **Question.** May an OWNER or ADMIN store and activate an edit of `-5` in Metodika, knowing every
  map it makes is internal until the methodology owner registers that edit?
- **Example.** An admin changes a kernel width and activates `aia-sociomap-5+e1`. Every new run's
  map then reads "Interní" and cannot go into the client report. Today Metodika does not warn.
- **Options.**
  - (a) Allowed; Metodika says so before activation.
  - (b) Editing `-5` is disabled in the MVP.
  - (a) adds the warning to the methodology editor chunk (E-2, with `signed-off-sociomap-method#8`).
- **Recommendation.** (a). It keeps Metodika useful for comparison, and the warning makes the
  cost visible.
- **Sources.** #514 N10.

### D-15. Remove the draft-prompt test's server path too?

- **Question.** X10 removes Settings' "Vyzkoušet" button. Should `POST …/agent-jobs` also stop
  accepting `prompt_version`, which keeps a paid start outside the Lead reachable over HTTP?
- **Example.** With only the button gone, a script can still start a paid job on a draft prompt.
- **Options.** (a) Remove the parameter and its two refusals; (b) keep it as an operator
  exception to AC-02. Changes `system-prompts-settings#14` (W1).
- **Recommendation.** (a). There is no operator need on record.
- **Sources.** #514 N8.

### D-16. When an assumption may be marked supported

- **Question.** May a person mark an assumption SUPPORTED on Deep Research findings alone, and which
  statuses does an assumption have?
- **Example.** "Mladí lidé preferují mobilní bankovnictví", with one accepted ČSÚ finding and no
  question in the study measuring it. Under (a) it can be SUPPORTED, printed "doloženo externě";
  under (b) it stays UNTESTED until respondents answer a linked question.
- **Options.**
  - (a) External attachments alone may support it, and the basis prints as external (ADR 0033).
  - (b) SUPPORTED and CONTRADICTED need at least one admitted respondent claim
    (`assumptions-and-open-answer-coding` *Decisions*: Deep Research "cannot by itself mark one
    supported").
  - Status set: (i) UNTESTED / SUPPORTED / CONTRADICTED (the plan); (ii) plus UNVERIFIED and
    RETIRED (ADR 0033).
  - Changes `assumptions-and-open-answer-coding#AOC0` (W1, E32) and `#AOC2`.
- **Recommendation.** (b) with (ii)'s RETIRED only. (b) is what the plan's own decisions say. An
  external finding stays visible as context either way.
- **Sources.** #512 ADR 0033 Q1, Q2.

### D-17. Where the client's posture and wallet ceiling are set

- **Question.** On which screen does an OWNER or ADMIN set a client's data posture (OPEN or
  CLASSIFIED) and its wallet ceiling? Both have routes planned and no screen.
- **Example.** On the client's Profil, a "Pravidla" card next to self-approval: "Data: Otevřená",
  "Strop peněženky: 20 USD", editable by admins, read-only for researchers, with a one-line reason
  for each.
- **Options.**
  - (a) Profil → Pravidla (`deep-research-web-search#53`'s home).
  - (b) Settings (I15's home), one row per client.
  - (c) Both, one editable and one a read-only list.
  - Adds a W1 UI chunk to S3 (with `#53` and `lead-orchestration#LO1`) and settles I15.
- **Recommendation.** (c): edit on Profil, where a person thinks about one client, and list them
  read-only in Settings for an admin's overview.
- **Sources.** #514 N1, N2 (the screen), N12 (part).

### D-18. Stopping the Lead

- **Question.** Can a person stop a running Lead turn, and withdraw an approved plan midway?
- **Example.** Esc while the Lead writes: "Zastaveno vámi. Nic nebylo přijato za vás." On the card
  of a running plan: "Zastavit plán", so the current step finishes or is cancelled and nothing
  after it starts.
- **Options.**
  - (a) Both IN (new `lead-orchestration#LO17`, a workbench build line, W1).
  - (b) Turn only.
  - (c) Neither; `research-lead-workbench#12` only verifies they're absent.
- **Recommendation.** (a). A plan that spends money without a stop button undermines the wallet.
- **Sources.** #513 Q9 and proposed edit 5.

---

## Part C. The production track (beside W1; gates release)

### D-19. Egress in production

- **Question.** Does production's outbound proxy allow-list hostnames, or only block private and
  metadata addresses?
- **Example.** A study cites a regional newspaper nobody listed. With an allow-list, Deep Research
  cannot fetch it; with block-private-only, it can, and the application's per-hop checks
  (`infrastructure/web_retrieval.py`) still refuse internal addresses.
- **Options.**
  - (a) A hostname allow-list (narrower reach; contradicts "never hear that this limitation
    exists", 2026-10-19).
  - (b) A proxy that blocks private and metadata ranges only, the application's checks the
    boundary.
  - Changes `production-environment#PE4` and ADR 0031.
- **Recommendation.** (b): it keeps the decided reach, and the application's checks are already
  built and tested.
- **Sources.** #512 ADR 0031 Q2.

### D-20. Production hostname, sizing and Bedrock quota

- **Question.** What is production's hostname, and do you accept the proposed sizes, to be
  measured on develop first?
- **Example.** `aia.art-chain.io`, `t3a.large`, `db.t4g.medium`, the Bedrock quota raised before
  the first client run.
- **Options.** Values you give; or (a) the proposals, confirmed after a develop measurement.
  Changes `production-environment#PE0`-`#PE3`.
- **Recommendation.** (a), with the hostname from you.
- **Sources.** #512 ADR 0031 Q1.

### D-21. Cost attribution in production

- **Question.** Does production use tagged application inference profiles, as develop does, so
  its Bedrock spend is attributable from day one?
- **Example.** The AWS bill shows "Environment=production: 41 USD" apart from develop's.
- **Options.** (a) Tagged profiles (one Terraform + IAM + model-policy change, as MVP-30 did for
  develop); (b) `eu.` ids, untagged, at release. Changes `production-environment#PE7`.
- **Recommendation.** (a): AC-15 asks spend to agree with an AWS record.
- **Sources.** #512 ADR 0031 Q3.

### D-22. Production starts empty

- **Question.** Does production start with no data, its first organization and owner created by an
  audited operator command?
- **Example.** On release day, an operator runs one command as you; you sign in and create the
  first real client by hand. Nothing from develop or 18.6.6 is copied.
- **Options.** (a) Empty, with a new `production-environment#PE10` (operator bootstrap);
  (b) seeded with develop content.
- **Recommendation.** (a). MVP-33 already says no 18.6.6 migration; develop's content is
  fictional.
- **Sources.** #513 Q3 and proposed edit 3; #515 G76 (the same bootstrap is the acceptance
  harness's).

### D-23. An external security review before the first client

- **Question.** Must the first release have an external security review?
- **Example.** One web-application test of the production hostname by an outside tester before
  real client data arrives.
- **Options.** (a) Yes (new `production-environment#PE11`); (b) an internal review only; (c) not
  for the MVP.
- **Recommendation.** (a). The product holds client data and runs paid AI calls.
- **Sources.** #513 Q1.

### D-24. Rate limiting

- **Question.** Is a per-member rate limit a release requirement?
- **Example.** About 60 writes per minute per member, then 429 with a Czech message.
- **Options.** (a) Yes (new `architecture-enforcement#12`); (b) not for the MVP.
- **Recommendation.** (a), simple and per member: a looping browser tab must not drain a wallet.
- **Sources.** #513 Q2.

### D-25. Recovery targets

- **Question.** Is 24 hours of data loss at most (RPO) and 4 hours to restore (RTO) the stated
  target, with the database and S3 restored together?
- **Example.** RDS point-in-time recovery plus a tested restore exercise of the database and the
  bucket's versions, with the deletion journal replayed (MVPQ-07).
- **Options.** (a) 24 h / 4 h; (b) other values. Widens `production-environment#PE9a` and
  `study-data-lifecycle#SDL5`.
- **Recommendation.** (a), proved once before release.
- **Sources.** #513 Q4.

### D-26. Uptime probe and on-call

- **Question.** Is an uptime probe with a named person to alert required?
- **Example.** If `/health` fails for 5 minutes, an e-mail reaches the on-call person.
- **Options.** (a) Yes, with PE9b's alarms named: uptime, oldest queued step's age, Bedrock spend,
  the production error tracker; (b) the error tracker only.
- **Recommendation.** (a), and you name the person.
- **Sources.** #513 Q5 and proposed edit 3.

### D-27. Removing a member

- **Question.** Must an admin be able to deactivate a member in the UI for the first release?
- **Example.** A researcher leaves on Friday and loses access the same day, from Settings →
  Přístup.
- **Options.** (a) Yes (new `two-roles-human-ai-gates#8`); (b) an operator command only.
- **Recommendation.** (a). Membership is the access (ADR 0019), so removal is the only control.
- **Sources.** #513 Q7 and proposed edit 9.

### D-28. Terms, privacy notice, DPA and the panel licence

- **Question.** Must terms, a privacy notice and a client DPA exist before the first client, and
  has the data owner confirmed the panel licence covers paid deliverables?
- **Example.** A terms notice shown at first sign-in; a DPA signed with the first client; the data
  owner's written yes for client reports built on panel-grounded respondents.
- **Options.** (a) All four before the first client (a release checklist line, no code beyond the
  notice); (b) a subset, named.
- **Recommendation.** (a). These are yours and the data owner's to produce; the plan only needs
  the checklist line and the notice screen.
- **Sources.** #513 Q6.

### D-29. Deleting and client data rights

- **Question.** Who can delete a client, a source and a knowledge item, from where; and are data
  export and "erase one person" needed before real data?
- **Example.** A CSV with birth numbers is uploaded by mistake. The researcher deletes that source
  from its card. A client leaves; an admin deletes it from Settings with a typed confirmation.
  MVPQ-07 already says what remains afterwards.
- **Options.**
  - Delete: (a) client by an admin from Settings, typed confirmation; source by any researcher from
    its card; knowledge retired, never deleted. (b) Service only, no button (today's plan).
  - Export a client's data / erase one person: (i) IN (new `study-data-lifecycle#SDL7`, `#SDL8`);
    (ii) OUT, handled by an operator on request.
  - Changes `study-data-lifecycle#SDL3` (entry points), a new `#SDL4b` (single source).
- **Recommendation.** Delete (a); export and erase (ii) for about ten users, with the operator
  procedure in the runbook.
- **Sources.** #514 N6, N12 (part); #513 Q8 and proposed edit 12.

---

## Part D. W2-W3

### D-30. What the Sociomap lock covers

- **Question.** Once a Sociomap's inputs are locked, which items can no longer be edited?
- **Example.** Locked: the declared rating question and the battery it rates. Still editable: an
  unrelated demographic question.
- **Options.** (a) The declared inputs and the sets they rate (ADR 0029); (b) Set 1 and the
  declared rating question (target architecture); (c) `sociomap_rating` and `context_objects`
  only (WCE8). Changes `working-copy-edit-ops#WCE8` (W2).
- **Recommendation.** (a), the union, so nothing a map reads can move under it.
- **Sources.** #512 ADR 0029 Q4.

### D-31. Structural automatic accept: who performs it, and where it is switched on

- **Question.** With structural auto-accept on and no browser open, who accepts the Lead's change,
  and where is the switch?
- **Example.** You turn on "přijímat strukturální změny automaticky" for Dotazník and close the
  laptop. A plan step proposes adding Q12. Under (a) the server accepts it in your name, recorded
  as "automaticky, podle vašeho nastavení"; under (b) it waits until you open the study.
- **Options.**
  - Who: (a) a named server path under the person's standing choice; (b) only the person's open
    session.
  - Where: (i) Můj Vedoucí, one switch per stage, off by default; (ii) each artifact's header.
  - Changes `working-copy-edit-ops#WCE11` (W2, G56).
- **Recommendation.** (a) with (i). (b) makes an approved plan stall overnight.
- **Sources.** #512 ADR 0029 Q5; #514 N7.

### D-32. When a researcher counts as departed

- **Question.** What starts a Lead handover: an admin acting alone, or a member's deactivation?
- **Example.** Jana is deactivated (D-27). Under (a) her Lead waits until an admin chooses "Předat
  Petrovi"; under (b) deactivation opens the handover at once.
- **Options.** (a) An admin acts alone (ADR 0030); (b) deactivation triggers it. Changes
  `lead-orchestration#LO11`.
- **Recommendation.** (a), with deactivation showing the admin that a Lead awaits handover.
- **Sources.** #512 ADR 0030 Q2.

### D-33. An admin reading another person's Lead files

- **Question.** May an OWNER or ADMIN read another researcher's Lead files and notes (never the
  turns), and where?
- **Example.** Before handing Jana's Lead to Petr, an admin reads its SOUL and client notes in
  Settings → Přístup; the read is audited.
- **Options.** (a) Yes, OWNER and ADMIN, audited, under Přístup; (b) only during a handover;
  (c) no. Changes `lead-orchestration#LO11` and the role table of ADR 0019.
- **Recommendation.** (a). ADR 0019's Admin covers user administration, and a handover needs it.
- **Sources.** #512 ADR 0030 Q3; #514 N12 (part); #514 proposed edit 10.

### D-34. Lead handover: do the client notes go with it?

- **Question.** When a researcher leaves and their Lead is handed over as a copy, does the copy
  keep their client notes, or only its name and SOUL?
- **Example.** Jana's Lead holds "Klient X: rozhoduje finanční ředitel, pozor na termíny". Petr
  inherits the Lead. Under (a) he has the note in X's studies; under (b) he starts blank.
- **Options.** (a) Copy client notes, drop personal notes (ADR 0030); (b) copy name and SOUL
  only. Changes `lead-orchestration#LO11` (W2, E16).
- **Recommendation.** (a). Client notes are about the client, which stays.
- **Sources.** #512 ADR 0030 Q1.

### D-35. Report edits: chapter order and merging paragraphs

- **Question.** In a semantic report edit, may the client report's chapters be reordered, and may
  two paragraphs be merged?
- **Example.** A researcher wants "Doporučení" before "Metodika" in the client DOCX, and to join two
  short paragraphs about Q3.
- **Options.**
  - Chapters: (a) fixed order for the client report (`client_report_v2`), movable only where a
    template marks it; (b) free order.
  - Paragraphs: (i) no merge (each keeps its own evidence refs); (ii) merge allowed, refs unioned.
  - Changes `report-delivery#RD6` (W3) and ADR 0035.
- **Recommendation.** (a) and (i). Both keep every printed number's evidence check exact.
- **Sources.** #512 ADR 0035 Q1, Q2.

### D-36. Which run a report reads after a replacement

- **Question.** After respondents are replaced (a new linked run), does the report read the newer
  run by default?
- **Example.** Run 7 had 12 straight-liners replaced, giving run 8. The report reads run 8 and
  says "nahrazuje běh 7 (12 respondentů)".
- **Options.** (a) The newer, naming both (ADR 0036); (b) a person chooses each time. Changes
  `run-qc-and-checkpoint#RQC4` / `#RQC5` (W3).
- **Recommendation.** (a).
- **Sources.** #512 ADR 0036 Q2.

### D-37. Where a client dataset's data contract is accepted

- **Question.** Is a client dataset's data contract accepted on the client's Data tab or in the
  study's Brief drawer when a study first uses it?
- **Example.** A study attaches the client's "NPS 2025.xlsx"; the Brief drawer shows its columns,
  the quality report and "Přijmout datovou smlouvu". The Data tab shows the accepted contract
  read-only.
- **Options.** (a) Brief drawer, Data tab read-only (F19; the design artifact); (b) the Data tab
  (`client-workspace#C8`). Under ADR 0019 every researcher holds both candidate permissions, so the
  "who" half has one answer: any researcher. Adds a W3 UI chunk with
  `client-data-in-analysis#2` and replaces C8's "V AIA zatím není".
- **Recommendation.** (a): the contract is accepted where its use is decided.
- **Sources.** #514 N4.

---

## Part E. Scope additions: in or out

An "in" adds the chunk named; an "out" is written into the baseline's out list. The recommendation
is "out" unless an acceptance criterion needs it, to keep the freeze tight.

| # | Question | Example | If in | Recommendation | Source |
|---|---|---|---|---|---|
| D-38 | Conversation controls: older-message paging, copy, edit and resend, ArrowUp, send-now and edit for a queued message | "Načíst starší zprávy (40)" | new `research-lead-workbench#29` with a paging route | **In: paging and copy** (a long study needs them); out: the rest | #513 Q10, edit 7 |
| D-39 | The Lead streams its text, accepts a file from the composer, comments unprompted when you pause | a reply appearing word by word | worker, transport and composer chunks; each unprompted comment is a paid turn | **Out**, all three | #513 Q18 |
| D-40 | Map node drag persists as a view override, or camera only for AC-09 | `service_c` dragged aside is still there after a reload | a view-override store and route | **Out**: camera only | #513 Q11 |
| D-41 | A data export (CSV/XLSX) and charts on Results | the per-question table downloaded to Excel | an export route from admitted claims; chart components | **Out**: the DOCX's tables carry the numbers | #513 Q13 |
| D-42 | Sociomapa matrix and comparison modes from the product scope | two segment maps side by side | workbench map modes | **Out**, beyond AC-09's segment maps | #513 Q14 |
| D-43 | A locked attention-check question, failing respondents excluded | Q19 "vyberte Souhlasím" | a question kind, QC rule and exclusion | **Out**: MVP-24's QC warnings cover quality | #513 Q16 |
| D-44 | The question chain: the Brief's decisions, an expected answer and done-when per research question | RQ1 → D1, "Hotovo, když…" | widen `working-copy-edit-ops#WCE1` with three item kinds | **Out** | #513 Q17 |
| D-45 | Respondents receive stimuli beyond the question text (`respondents.context`) | a concept description before rating | respondent prompt and design chunks | **Out** | #513 Q19 |
| D-46 | Known-truth anchors, an instrument library, schedules and pause, "society insights" | scheduling a run nightly | each its own plan | **Out**, confirmed | #513 Q20 |
| D-47 | A cross-client "what needs me" portfolio, and memory search over approved reports; an organization-level monthly spend view for OWNER/ADMIN | "3 studie, 2 čekají na vás"; this month's Bedrock and Brave spend | a home view; a report index; a read-only Settings view over the content-free rows MVPQ-07 keeps | **Out**: portfolio and report search. **In**: the spend view, read-only, since its rows exist | #513 Q21, Q22; #514 N12 (part) |
| D-48 | Accessibility and performance as release gates | a journey fails on any serious axe violation | axe in `mvp-acceptance-harness#10`; a browser matrix; budgets | **In: axe (serious and critical)**; out: browser matrix (Chromium only) and performance budgets | #513 Q23 |

---

## Proposed edits that need no decision

Pure gap fixes, safe to apply after sign-off. "After D-nn" marks a fix whose wording waits on an
answer above.

**`aia-sociomap-5` (follows from MVPQ-13)**
1. Register `signed-off-sociomap-method` in master §3.1 (S2 plus the methodology owner, gate I-2);
   `master_check` fails without it (#515 G58).
2. `signed-off-sociomap-method#8`: `-5` pinned by its own name as the code's default (N9b), a run
   that pinned `-3` keeping it, Metodika's in-force method `-5` and the editor starting from the
   preset in force, not `presets[0]` (#510 E-1, E-2; #512 ADR 0038; #514 N9b and §5 item 3; #515
   G58). Lands with or after MQ-01. Pins per D-13.
3. `signed-off-sociomap-method#9`: the report's `-5` figure (z from `heights.relative`, the caption
   from the terrain method, `objects_not_placed` listed); the credibility in place of Stress-1
   (#510 E-4; #515 G60).
4. The web draws `-5`: name the method, relative terraces, the credibility banner and uncertainty
   circles, "Neumístěno", the respondent map and taste segments (#510 E-3; #513 edit 2). #513
   proposes a new `research-lead-workbench#28`, #510 assigns it to `#20` with
   `segment-maps-and-drilldown#8`: one owner is chosen in part 2, not both.
5. `MapSummary` carries credibility, respondents and segments (#510 E-5); the worker image's
   `NUMBA_CACHE_DIR` and library versions recorded with the map (E-6); measure `-5` on the develop
   worker image at 1,500 / 5,000 / 20,000 respondents before MQ-06 (E-9).
6. Re-point `sociomap-formula-corrections#3` and `segment-maps-and-drilldown#1-3` onto `-5`'s stored
   fields and rewrite E14, E29, E30 and E31, after MQ-02 and MQ-05 (#515 G59; #513 edit 1).
7. `mvp-master-plan.md:126` and `:337` say `-5` (`-5`'s register entry pending MQ-01); the W2 engine
   chunks each name their Metodika catalogue re-pin (#514 edit 8).

**Already decided, chunk missing**
8. MVP-31: hide the Simulace tab and "Nová simulace". #513 proposes `client-workspace#C10`, but
   that id is taken (`[x] C10` in its front matter): use a free one.
9. MVP-26: `report-delivery#RD11`, Deep Research context in the client report (#513 edit 10).
10. MVP-27 as amended: correct ADR 0032's *Open for Nigel* 1 and AC-11's wording to the amended
    text; `overview.md:557, :598` to "V2" and "Class B deferred" (#513 doc follow-up).

**Evidence and reports (#515)**
11. G61: AC-08's row gains `evidence-integrity#5` and `segment-maps-and-drilldown#10`; chunk 5's
    test reads "one authority per evidence source".
12. G62: move `evidence-integrity#1` from E20 to E32 (or a W0 row); a `master_check` rule that no
    chunk sits later than its consumer (`mvp-master-plan#MP8`).
13. G63: `report-delivery#RD0` defines result numbers (ledger refs) apart from design and method
    facts (typed blocks); the validator checks every other prose number.
14. G64: freeze "Interní dokument" on the frozen `KnowledgeSource` (`client-knowledge-lifecycle#K8`,
    with ADR 0021's defect note); RD0 checks both deliverables.
15. G65: `mvp-acceptance-harness#16`, the per-number provenance walk for AC-15.
16. G66: `report-delivery#RD3`, the approve response carries the report's kind.
17. G78: `run-qc-and-checkpoint#RQC12`, weight identity in the run's population note and the method
    section.

**Deep Research (#515)**
18. G67: `deep-research-web-search#51a`, a run's routes on its record (`by_route`,
    `composed_routes`).
19. G71: an activation row for `aia_deep_research_lead` in §4; AC-11's row gains
    `deep-research-web-search#36`, `#37`.
20. G72: `assumptions-and-open-answer-coding#AOC2` names its producer (an assumption inherits its
    linked research question's findings; no engine change).

**Acceptance (#515)**
21. G73: AC-01 reads "a user of another organization gets 404" (ADR 0019), in both acceptance files;
    `mvp-acceptance-harness#14` lists AC-01.
22. G75: `mvp-acceptance-harness#17`, the acceptance verdict from its own JUnit; `project.memory`'s
    matrix row corrected.
23. G76: `mvp-acceptance-harness#3` declares the operator bootstrap and runs the worker as a
    subprocess (pairs with D-22).
24. G77: each criterion's tier-A and tier-B projection, the record per tier
    (`mvp-acceptance-harness#6`, `#14`).
25. `mvp-acceptance-harness#5`'s front matter: only AC-12 is an existing path. AC-14's wording after
    D-09.

**Client pages and Settings (#514)**
26. Fold `client-workspace` C6-C9 (MP3): C6 → K2f/K3; C7 closed, superseded by `client-budget`;
    C8 → `client-data-in-analysis#2/2a/3` plus D-37's UI chunk; C9 → K6. Drop "[C6, C7, C8]" from
    K2's completion line (N5; edit 1).
27. `run-qc-and-checkpoint#RQC9`: the valid-n authority is the organization's readiness methodology
    in force (edit 7).
28. Wave contradictions: RD0-RD4 (W2 in `report-delivery.md:75`, W3 in E20);
    `mvp-acceptance-harness#5` (W1-W4 in its plan, W5 in E24) (edit 11).
29. The UI chunks D-17 and D-29 create join I15.

**Reverse audit (#513)**
30. `research-lead-workbench#15`: mount `ItemInspector` (imported only by its test) and fix provider
    waits reading as inert (`research/lane.ts:134`).
31. `production-environment#PE1` gains a CSP; `#PE9b`'s alarms are D-26's named list.
32. Widen: `lead-orchestration#LO12a` (every API error in Czech, a no-leak test, a native copy
    review); `develop-spend-attribution#5b` (the infrastructure-charges line);
    `mvp-acceptance-harness#14` (refresh the three 18.6.6 ledgers, remove the L-04 / L-29
    contradiction); `lead-orchestration#LO11` (F14's learning rules; the pages per D-33).
33. Pointers: master §11.3 S4 cites `deep-research-web-search#54`, which should be `#53`; on the
    design artifact, accepting the working copy is `WCE7` and discarding it `WCE9`, `#43` does not
    exist, and bare `#3`, `#5`, `#7` name their plan.

**ADR mechanics (#512)**
34. ADR 0029 Q3, the feed's route: `…/workspace/ops?since=`, one name in WCE4 and the target
    architecture (an engineering choice).
35. ADR 0037 Q2: it follows ADR 0027 as #508 amended it (merged), nothing to decide.

**Docs PR, not plan edits** (shared files): the ADR index rows, `docs/product/README.md`, CLAUDE.md
§2's Sociomap paragraph, `ARCHITECTURE.md:508`'s import rule, #514's stale copy (§7) and finding F-1
(`tools/ui_workbench/capture.mjs`), `overview.md` MVP-13 / MVP-27.

---

## Still open elsewhere, not re-listed

These are Nigel's too and stay where they are; part 2 carries them into the baseline's open list
if still unanswered:

- **MVPQ-06 (rest):** Deep Research evaluation tasks, metrics and thresholds (`deep-research-web-search`
  25, 26, 39), USD 50 allowance.
- **Scope overrides S2-S5** (master §11.3): only if wanted.
- **#509's npm audit gate** (the coordinator's: block all with one dated exception, production only,
  or advisory).
