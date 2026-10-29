# ADR 0008 — EU data residency and the egress boundary

**Status:** Accepted. Frozen invariant; enforcement implemented in
`aia_core.domain.residency`. Amended 2026-10-19 by the product owner: classes by rule
(§ Amendment 2026-10-19); amendment note 2026-10-26: a brief's files Class A by rule,
Veřejné makes one B (decided, not yet built: `artifact-brief` BRF7); amended 2026-10-28: advisory
class gates in every environment for the MVP (§ Amendment 2026-10-28).
**Date:** 2026-09-22

## Context

AIA produces paid research for European clients. Client material arrives under
confidentiality terms and frequently under data protection obligations that
constrain where it may be processed and what a processor may do with it.

This was previously carried in `security.md` as a decision the team still owed.
That was wrong twice over: the decision had in fact been made, and while it sat in
a "decisions needed" list nothing in the code could enforce it. A residency
requirement that exists only in prose is a requirement that will be broken by the
first convenient integration.

This ADR records the invariant. It selects **no vendor, region or hosting
product** — see *What this ADR does not decide*.

## Decision

**All processing of client-derived material obeys EU residency rules, and the
egress boundary fails closed.**

"Client-derived material" is deliberately broad, because residency is broken at
the edges rather than in the obvious place:

- client source data and uploaded datasets
- generated artifacts and deliverables
- backups and snapshots of either
- retrieval indexes and embeddings built over client material
- caches holding client material
- logs and traces carrying client information
- AI inference over identifiable or confidential client material

### Fail closed

The boundary refuses anything it cannot positively justify. A rule that permits
what it has not been told about permits everything, because the case nobody
configured is exactly the case that leaks. Concretely:

- **Unclassified material does not leave AIA.** Absence of a classification is a
  refusal, not a default to "internal".
- **No approved route means no egress.** There is no fallback provider.
- **An unknown route id is a refusal, not a substitution.** Silently using a
  different route is the residency face of the product's no-silent-fallback rule.
- **An under-specified route is refusable.** `ResidencyZone.UNKNOWN` exists so
  that "we did not write down where this runs" is representable and denied,
  instead of being modelled as probably fine.
- **A denial is a hard stop.** `EgressDenied` carries no suggested or fallback
  route, exactly as `BudgetDecision` carries no `suggested_provider`.

### An outbound call needs trusted information

Egress is authorised from an issued `StudyContext`, the data classification, the
residency policy and the approved route. The context can only be produced by the
authorization layer, so a model, an agent, a tool argument or a request body
cannot assert whose data a call carries. The worst a compromised tool can do is
fail.

### Data classes

| Class | What it is | What it requires |
| --- | --- | --- |
| **A — client confidential** | Raw client documents, row-level datasets, personal data, NDA material | A route explicitly approved for Class A, with confirmed EU processing, contractual exclusion from training and a specified retention period. **Never an arbitrary direct provider API.** |
| **B — derived / aggregate client information** | Aggregates, segment profiles, summaries computed from client material | An approved EU-processing route with the same contractual and retention controls |
| **C — internal / non-client** | Methodology text, public sources, prompts carrying no client information | Broader approved routes permitted, including non-EU ones. Still requires an approved route, and still records provenance and cost attribution |

Two properties of this table are load-bearing:

**Approval is per class, not per provider.** The same provider, over the same
transport, under the same terms, approved for aggregates, is still refused raw
client data. Approval is a statement about what an operator agreed to, and it does
not generalise on its own.

**Residency is not only geography.** Material processed in the EU but used to
train a provider's model, or retained for an unspecified period, has left the
client's control as surely as material processed elsewhere. Classes A and B
therefore require training exclusion and a specified retention period in addition
to the zone.

## What this ADR does not decide

It records an invariant. It does **not** select:

- a provider, managed inference service or model host;
- a permanent cloud region;
- a compute service;
- a hosted search, retrieval or embedding product;
- any vendor pricing or commercial arrangement.

Those are implementation choices, each needing its own record, each judged against
this ADR rather than allowed to modify it. Declaring an approved route is how an
implementation states that it *meets* these constraints; the route does not get to
redefine them.

This distinction matters because it is the one that erodes. A proposal to make the
system depend on one vendor's regional offering was circulating as though it were
the residency decision. It is not: it would be one possible way of satisfying the
residency decision, and adopting it would mean writing a vendor ADR that says so
and can be revisited without reopening the invariant.

## Alternatives considered

**Leave residency as a deployment concern.** Rejected. It would be enforced by
whoever configured the environment, differently each time, with no test that could
fail. The classes and the boundary exist so the rule is checkable.

**Encrypt and send anywhere.** Rejected for Class A and B: inference requires
plaintext at the provider, so encryption in transit does not address the question
this ADR is about.

**One global allowlist of providers.** Rejected. A provider is not a route: the
same provider reached over a different transport, account or region is a different
residency answer and must be a separate, separately approved route.

## Consequences

- Every outbound call site must classify what it is sending. This is deliberate
  friction at exactly the moment the question should be asked.
- A capability with no approved route for a study's data class cannot run, and
  `EgressPolicy.routes_for` exists so that is discoverable before a study starts
  rather than mid-pipeline.
- Adding a provider is an operator act with a recorded justification, not a
  configuration convenience.
- Some otherwise attractive tools will be unusable for Class A work. That is the
  decision, not a side effect of it.

## Revisit when

- A client's contract imposes a stricter requirement than these classes express.
- The legal basis changes materially.
- A new class of material appears that none of A, B or C describes — in which case
  the default is the most restrictive, and the burden is on the exception.

## Amendment 2026-10-19 (product owner)

**Context.** A model request classified a study's design, its name and a researcher's message
to the Research Lead only by an operator's approval of their exact bytes
(`AIA_AI_MATERIAL_CLASSIFICATIONS`, [ai-material-classification.md](../ai-material-classification.md)).
An edited design is new bytes, and so is every chat message: the Research Lead and the AI design
jobs could never run on an edited design (OI-126). The fail-closed rule was right; classifying
nothing but exact bytes made it unusable.

**Decision.** Some material takes its class *by rule*: a decision of the code and the product
owner, written once (`packages/aia_core/src/aia_core/domain/material_rules.py`) and read by every
model caller of that material.

| Material | Class |
| --- | --- |
| Methodology texts, AIA's own prompts, public sources | C (unchanged) |
| A study's design: brief, research questions, questionnaire, audience, the attachment excerpts the design carries; the study's and its client's names | **B by rule**: derived client information |
| A researcher's chat message and focus label to the Research Lead, in a study (and their instruction to an AI design job) | **B by rule**: the study's class |
| The Lead's personal notes, its SOUL and USER files and its name | **C by rule**: they change only on the researcher's explicit "Pamatovat si" |
| The Lead's client-scoped notes | A (unchanged) |
| Approved Client Knowledge | A (unchanged) |
| A client's uploaded source or dataset | A (unchanged), **unless a person marks the source "Interní dokument"**, an internal AIA document holding nothing of the client's, which makes it C; who marked it and when are kept and audited |

Three properties are load-bearing:

- **Unknown material still refuses.** A rule is a decision of the code and the owner, never a
  default: material no rule names is still unclassified and does not leave AIA
  (`egress_unclassified_material`) -- an undeclared prompt edit, an earlier Lead reply of unknown
  class, a Lead note of a scope no rule names. § Fail closed is unchanged.
- **An operator can only make a class stricter.** An operator's exact-bytes classification still
  applies beside a rule and the request takes the more restrictive of the two, as a prompt's class
  already takes the stricter of its author's declaration and an operator's classification. An
  operator who finds client material in a design raises it to A; an operator's Class C for a
  design leaves it at B.
- **A rule approves no route.** Class B still needs a route approved for B, with confirmed EU
  processing, training exclusion and a specified retention period (§ Data classes); a route
  approved for C alone refuses a design. The licence gate for panel-derived data is unchanged.

**Consequences.** Every executor that sends such material records each part's class and who
answered for it (`rule:<name>`, `operator`, a prompt's declaration or the code) beside the
request. A deployment that wants the Research Lead and the design jobs to run approves its route
for Class B (ADR 0010, amendment of the same date). Deep Research keeps its exact-bytes
classification of a design for now: its web routes carry Class C only and a query inherits the
class of what it was written from, so the rule would refuse every web track; that is a decision
still to be made (plan `usable-classification`, Findings).

**Addendum (the product owner, the same day).** Three questions the implementation raised
(plan `usable-classification`, Findings F1, F7, F8) were decided:

1. **Deep Research keeps operator-only classification of a design** (OI-129). Its web routes
   stay Class C only, and no class of its own is made for a query a model writes from a design;
   a run on an edited design parks (`egress_unclassified_material`) until an operator classifies
   its exact bytes (`apps/executors/src/aia_executors/deep_research/plan.py:163 @ 64cc1380`). The
   decision still to be made above is made.
2. **AI-written design text is design** (OI-130). What a design job or the Lead writes into the
   study from Class A approved knowledge -- a brief analysis, an accepted questionnaire, an
   accepted Lead edit -- is Class B once a person accepts it, chosen for usability. A brief's
   attachment excerpts stay B as design, though the same bytes kept as a client source are A. An
   operator may still raise a design's exact bytes.
3. **The unmark window is accepted** (OI-131). A source's "Interní dokument" mark is read before
   each request, not held across it, so a batch sent as an unmark commits may still leave as
   Class C; every later batch stops (`source_class_changed`). Holding the row's lock across the
   model call would make an unmark wait for a request in flight; the owner chose the window.

## Amendment 2026-10-21: advisory class gates on develop (product owner)

**Context.** On develop, classification stopped work the owner wanted to see run: a design no
operator had classified parked Deep Research (OI-129), and a Lead turn or a prompt of unknown class
parked before any call. The owner, 2026-10-21, in his own words: "build the develop-only
class-advisory switch, including Brave for any class", following his /pmstatus answers Q65 ("i dont
want any gates stopping based on the classification we are going for full functionality right now")
and Q66 (a) ("Develop only: classes are shown and recorded, never block; EU residency and licences
still hold"; "dont limit the brave search capabilities either").

**Decision.** One switch, `AIA_DATA_CLASS_GATES` = `enforce` | `advisory`, default `enforce`
(`packages/aia_core/src/aia_core/domain/deployment.py`, `DataClassGates`). `advisory` is set only by
develop's Compose file; staging, production and an unknown `AIA_ENV` refuse to start with it. On
`advisory`, every gate that refuses **solely because of a data class** records the refusal it would
have made and lets the call proceed. Plan
[`develop-class-advisory`](../../../.planning/plans/develop-class-advisory.md), #594.

- **What it relaxes:** egress for unclassified material and for a route not approved for the class
  (`domain/residency.py`); the retrieval gate's class rules (`application/web_retrieval.py`);
  Brave's search route, which takes a query of any class (`ToolRoute.any_class_when_advisory`, the
  search route alone: the one stated exception to EU residency); Deep Research's parking of an
  unclassified design, which takes the design rule's class (B) when no operator classified it
  (OI-129); and validation's park of unclassified material.
- **What it never relaxes:** EU residency for model calls (EU processing, training exclusion and
  bounded retention for A and B); the licence gate, the `unclassified-client-knowledge` lineage
  included; budgets, reservations and the study's spend limit; scope; the route/provider match;
  tool metering; ADR 0022's live sign-off; the residency of every fetch, dataset, archive and Common
  Crawl route. Wikipedia's routes and the public fetch keep refusing client material.
- **Unclassified is judged as Class A** for every check that still holds, never as the permissive
  answer: the ledger row's `data_class` is A and its note says `class=unclassified`.
- **Where each pass is recorded** (`residency.ClassAdvisory`: the gate, the refusal enforce would
  have made, the class, `advisory=true`): the note of every AI usage ledger row of the call and the
  call's provenance (`CallProvenance.class_advisories`); the note of the retrieval gate's
  `DISPATCHED` tool event; a step event for the refusals an executor makes before any call (Deep
  Research's plan step, validation's arms).

**Consequence.** On develop the data class no longer stops anything: a design, a Lead turn or a
prompt nobody classified is sent, judged as Class A for residency, and Brave, outside the EU, may
receive a search query written from client material. Every such pass is recorded, never silent.
Enforce mode, every other environment and every recorded fixture are unchanged; OI-129 stays open
for staging and production.

## Amendment note, 2026-10-26: a brief's files are Class A by rule (product owner)

**Decided, not yet built.** B4 (a), the product owner, 2026-10-26 (on the `artifact-brief` plan page,
relayed by the PM coordinator; `.planning/plans/artifact-brief.md` BRF7): a file attached to a
study's brief is **Class A by rule**, like a client's uploaded source, and no longer the design's
Class B; a person may mark one **Veřejné** (public), which makes that file Class B. This changes one
row of the 2026-10-19 table: "the attachment excerpts the design carries" leaves the B-by-rule
design row for brief files, and a brief file joins the A row with its own B exception. Today a
brief's file and link take `MaterialRule.DESIGN`, Class B
(`packages/aia_core/src/aia_core/domain/brief_material_classes.py:8-9 @ 5d2ac5ac`); the rule changes in
`domain/material_rules.py` with BRF7 (W1), whose test is that an unmarked brief file classes A, a
file marked Veřejné classes B, and a route approved for B alone refuses the unmarked one. Under the advisory gates of
the 2026-10-21 amendment (develop) a class-only refusal of a brief file is a recorded pass, as for
every other class.

## Amendment 2026-10-28: advisory class gates in every environment for the MVP (product owner)

**Context.** The 2026-10-21 amendment made the class gates advisory on develop alone; staging,
production and an unknown `AIA_ENV` refuse to start with `AIA_DATA_CLASS_GATES=advisory`
(`packages/aia_core/src/aia_core/domain/deployment.py:123-139 @ d2139903`, asked by the API at
`apps/api/src/aia_api/config.py:480, 525`, the worker at `apps/worker/src/aia_worker/settings.py:153`
and the executors at `apps/executors/src/aia_executors/ai_runtime.py:1048 @ d2139903`). So the first
environment after develop would start with every class gate enforcing, and every run on an edited
design, an unclassified Lead turn or prompt, would park again (OI-129). The product owner, in the PM
coordinator's session, 2026-10-28 at 22:25 UTC: "For mvp i wanted to retire the data gates". Offered
three choices (advisory everywhere, develop only, remove the gates), he chose **"Advisory everywhere"**
at about 22:27 UTC, whose wording was: "A session drafts an ADR 0008 amendment that lets advisory run
in staging and production for the MVP, then a small code PR. Every class decision is still recorded,
so the gates can be switched back on later. Residency, licences and budgets are untouched."

**Decision.**

1. **`advisory` is allowed in every `AIA_ENV`** for the MVP: local, test, develop, staging,
   production and an unknown or unset environment. No process refuses to start because of it;
   `data_class_gates_problem` and its four callers go.
2. **`enforce` stays the code default.** Unset is still `enforce`, a misspelt value still stops the
   process by name (`parse_data_class_gates`), and a deployment runs advisory only where its own
   configuration says `AIA_DATA_CLASS_GATES=advisory`, as develop's Compose file does. A deployment
   that says nothing enforces: the relaxation is always a written choice of that deployment, never
   inherited. Staging and production do not exist yet (no Compose file or Terraform root names
   either), so each states the key when it is built.
3. **What advisory relaxes and never relaxes is the 2026-10-21 amendment's list, unchanged.** It
   relaxes only refusals made solely because of a data class. It never relaxes EU residency for
   model calls (EU processing, training exclusion and bounded retention for A and B), the licence
   gate (panel data on `bedrock-eu-primary` alone, OI-61; unrecorded client knowledge likewise,
   Q60), budgets, reservations and the spend limit, scope, the route/provider match, tool metering,
   ADR 0022's live sign-off, and the fail-closed egress boundary itself (an unauthorised scope, no
   approved route, an unknown route: still refused). Unclassified material is judged as Class A for
   every check that still holds.
4. **Every class decision is still recorded**, in the four places the 2026-10-21 amendment names:
   `residency.ClassAdvisory` on the note of every AI usage ledger row of the call and in
   `CallProvenance.class_advisories`, on the retrieval gate's `DISPATCHED` tool event, and on a step
   event for an executor's own refusal. So what enforce would have refused is readable after the
   fact, and `enforce` is restored by setting the key, with no code change.

**One exception to EU residency travels with advisory, and it is stated here because the choice's
wording said residency was untouched.** Under advisory, Brave's search route takes a query of any
class (`ToolRoute.any_class_when_advisory`,
`packages/aia_core/src/aia_core/domain/deep_research/tooling.py:114-118 @ d2139903`; the owner's
2026-10-21 words "dont limit the brave search capabilities either"). Brave is `NON_EU`, a US provider
logging queries up to 90 days. On develop the material is fictional; in staging or production with
real clients, a search query written from Class A client material may reach Brave, beyond ADR 0032
decision 4 (Class A only as fields code extracts). Each such query is recorded on its tool event.
Model calls, storage, every fetch, dataset, archive and Common Crawl route keep their residency.
**This exception needs the product owner's explicit yes for staging and production** (open point 1
below); the code PR carries it unchanged in the meantime, and it acts only where a deployment sets
advisory, which no deployment but develop does today.

**ADR 0032 (client posture) and the material rules.**

- **`domain/material_rules.py` needs no change.** Classes are still computed by rule everywhere and
  stored; advisory changes what a refusal does, not what a class is. Its docstrings say nothing
  about where advisory runs.
- **ADR 0032 needs a line, and this amendment is it.** A Deep Research run still pins its client's
  posture (`application/deep_research.py:847-849, 963-970 @ d2139903`), and the posture is still set
  only by an OWNER or ADMIN and audited. Under advisory, though, the posture no longer decides
  Brave: a CLASSIFIED client's queries reach Brave whatever their class, and ADR 0032 decision 4's
  "Class A only as extracted fields" check becomes a recorded pass rather than a refusal. On every
  other non-EU route (the connectors, Common Crawl, the crawler) residency still refuses Class A and
  B, so for those the posture keeps its meaning once decision 3 is built. Under `enforce` ADR 0032
  reads exactly as written.

**Consequence.** Wherever a deployment sets advisory, the data class no longer stops anything, and
every pass is recorded. Enforce mode, every recorded fixture, and every environment that does not
set the key are unchanged. OI-129 stays open: it is the condition for switching back, not closed by
this.

**What must be decided before switching back to `enforce`, and who decides.**

1. **Brave's any-class exception in staging and production** — the product owner, as data owner (as
   for OI-61 and Q60): carry it (the recommendation, as advisory means it today and he asked not to
   limit Brave), or hold Brave to ADR 0032 decision 4 outside develop, a one-line condition on the
   route.
2. **How a design is classified when nobody has** (OI-129): an operator's exact-bytes record, the
   design rule's class (B), or the posture — the product owner. Until it is answered, `enforce`
   re-parks every run on an edited design.
3. **The search classifier redesign** (ADR 0032 decision 5, `aia-query-classifier-2`) and ADR 0032
   decisions 3-4 built (`deep-research-web-search` 53, 57) — the product owner, with the session
   that builds them; without them `enforce` takes back the reach the MVP has.
4. **A brief's files as Class A** (§ Amendment note 2026-10-26, `artifact-brief` BRF7), built and in
   force — the product owner.
5. **What the recorded advisories say**: before switching, the organization reads what enforce would
   have refused (the `class_advisory` notes on the ledger and tool events) and decides whether any
   of it needs telling a client — the product owner, as data owner.
