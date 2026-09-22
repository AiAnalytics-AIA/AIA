# Population consumption readiness

**Status:** in progress · **Owner:** population-data · **Started:** 2026-09-22

## Problem

The population foundation (PR #12) can identify, validate, bind and load a
version, but a consumer still cannot ask the two questions the research engine
needs answered before it touches a field:

1. **May I use this field for this purpose?** The 400-field dictionary's
   epistemic rules ("never measured fact", "never claim direct Schwartz
   measurement", AUDIT_ONLY, …) are enforced nowhere — in the reference (R5,
   methodology M02) or here.
2. **Is this version usable at all?** A panel without its companion assets cannot
   say what may be claimed from it, and the `CORE_JOINT_STATUS` certificate that
   forbids client joint outputs and cross-block same-person claims (R6, M03) is
   not read.

And establish/promote are callable by anyone holding a session (OI-8).

## Approach

- **Field policy as code** (`domain/population/policy.py`). Parsed from the
  dictionary that already travels, hash-pinned, with every version. The sixteen
  verbatim `recommended_use` phrases and the twenty-two `evidence_status` codes map
  through closed tables; anything unmapped is `UNMAPPED` and refused for every
  use. A single `decide(field, use)` answers six uses — filtering, persona,
  aggregate analysis, simulation, client measured claim, client modelled claim —
  with obligations (scope disclosure, modelled disclosure, aggregate only,
  mandated weight). Import rejects a dictionary the policy cannot fully map.
- **Companion contract** (`domain/population/companions.py`). Each companion is
  pinned by SHA256 and size with its recovered shape checks. `CORE_JOINT_STATUS` is
  evaluated by a fail-closed gate: only a known status, QC-passed structure and a
  literal `true` grants anything, and only for the panel whose hash it certifies;
  every other outcome is the all-forbidden fallback. Companions are attached once
  per version (at import or later) and recorded insert-only; a contract that
  declares companions makes a version without a complete, valid set unusable —
  not establishable, not promotable, not resolvable.
- **Population operator authority** (`application/population_authority.py`). A
  separate capability, issued from trusted configuration through a sentinel, with
  two permissions. Establish and promote take it instead of a free `actor_id`.
- **Binding carries policy identity**: dictionary hash, policy version and the
  companion-set hash, so a run records exactly which rules applied.

**Rejected:** extending the shared `Permission` enum or `OrganizationRole` for
population operation. Population is platform-wide; an organization OWNER is a
tenant role and must not move LIVE for every tenant. Changing the shared role
contract needs integration-architecture; a separate capability does not.

**Rejected:** copying `field-policy.json`'s derived eligibility flags. They were
derived by the reference team with a permissive rule (modelled calibrated fields
may back measured claims; AUDIT_ONLY modelled metadata may drive simulation). Only
the claim-rule extraction and provenance classification are reproduced exactly;
eligibility is stricter, and the parity tier enumerates every difference.

## Trade-off accepted

Client-facing use is refused for anything the dictionary does not positively
support, so some fields the reference would have shown clients (historical,
derived, calibrated-modelled as "measured") are blocked until analysis-governance
decides otherwise.

## Chunks

- [x] 0. Correct the archived foundation plan's review outcome (no review happened)
- [x] 1. Field policy: domain model, dictionary rows, import check, tests, parity
  against `field-policy.json` — `domain/population/policy.py` ·
  `tests/test_population_policy.py` (33) · parity: 400/400 mapped, claim rules and
  provenance equal field for field, internal uses equal, measured claims 115 ⊂ 287
- [x] 2. Companion contract + joint-certificate gate + persistence + usability
  gating — `domain/population/companions.py`, `czech.py` (15 companions),
  `population_companion_{sets,assets}` (migration `cadbca872dc5`),
  `PopulationRuntime.attach_companions` · `tests/test_population_companions.py`
  (41) · parity: 15 identities equal the ledger, M14 shapes, M03 certificate binds
  `v17_4_0` only
- [x] 3. Population operator authority; close OI-8 — `domain/population/authority.py`,
  `application/population_authority.py`, two `layer_check` rules ·
  `tests/test_population_authority.py` (17)
- [x] 4. Binding + RuntimePopulation carry policy and joint status; migration
  `85637e58c7dd` (refuses to backfill) · `RuntimePopulation.decide` /
  `decide_joint`; load re-verifies companion bytes and the certificate state, and
  refuses a binding recorded under another policy version, dictionary, companion
  set or joint state
- [ ] 5. Derived-field decision matrix, OI-7 archive-dependency artifact, docs,
  PROGRESS, open items, agent status

## Out of scope, by instruction

OI-6 (research-engine), the EU store adapter, the first real import, production
promotion, columnar views.

## Review outcome

Filled in when the plan is archived.
