---
status: planned
chunks:
  - "[ ] LI0. The organization's allowance for personal Lead work, a fifth money amount: its name in money.py MONEY and cs.ts money (held by the vocabulary fixture), its place in the one precedence, set on Settings by an OWNER or ADMIN, every charge ledgered against no study; the ADR 0028 amendment written under Doc follow-up"
  - "[ ] LI1. Hatching writes the Lead's files with one model request: name, four traits, a brief and an optional about-you in; SOUL and USER out of one Lead-route request (STUDY_LEAD's binding), priced and held like a turn against LI0's allowance, its cost stated before the person confirms, the result held to the byte bounds and ADR 0030's personal-file check (refused by name, or asked once more), parked by name when the model is off or unconfigured, never composed by code instead"
  - "[ ] LI2. The researcher's mark and its motion: preferences gain mark (lissajous, fourier, sunflower, interference, gauss) and motion (live, still), a migration on researcher_leads, PUT /lead/preferences, audited like auto-accept"
  - "[ ] LI3. The five marks as components, drawn from their formulas (lib/lead-marks.ts, pure): still under Klidná and prefers-reduced-motion, aria-hidden beside text; beside each Lead reply in the chat and in the pane's header; thinking shows the orbit alone when the mark is still; Průběh keeps its step orbs"
  - "[ ] LI4. Líhnutí, the four-step hatching (web): name with ideas, how it should work (traits and free text), about you (optional), the mark; the cost and the confirmation; then se líhne… and the Lead's first greeting, Začít v chatu and Můj Vedoucí; replaces HatchCard and the unhatched /app/lead"
  - "[ ] LI5. Můj Vedoucí rebuilt to the artboard: the name and hatch date, Otevřít chat (the last study the researcher spoke to the Lead in, else the client list), the mark picker and Živá/Klidná, the files read only (Povaha, Co ví o vás, Dovednosti, Nástroje a připojení, Paměť: every client's notes grouped by client), auto-accept, a chat preview"
  - "[ ] LI6. Dovednosti and Nástroje derived, never hand-written: skills from the worker registry (LeadWorkerSpec today, the action registry with LO21a), each naming its stage; tools from what is composed and switched on (/config, LO12b's composition record), one that is off saying why"
  - "[ ] LI7. Every Settings page's rail links Můj Vedoucí (ControlPanel), the artboards' rail"
---
# The Lead's identity: hatching, its mark and Můj Vedoucí

**Source.** The Settings prototype, Version 59
(<https://claude.ai/artifact/8W9LR8Ju9BWnR5JACmiWv7>), artboards `Hatch.dc.html` (Líhnutí
Vedoucího) and `LeadSettings.dc.html` (Můj Vedoucí). Nigel approved them through the Lead
Researcher handoff from the research-stages prototype session (relayed by the PM coordinator,
2026-10-25 ~22:10 UTC).

**Nigel's answers** (relayed by the coordinator, 2026-10-25 ~22:15 UTC):
1. The SOUL at hatching is written by the model, not composed by code. LI1 is designed for that.
2. "Otevřít chat" opens the last study the researcher spoke to the Lead in, else the client list.
3. "Časová osa" means the Lead's turns in the chat: the mark sits beside each Lead reply. Průběh
   keeps its own step orbs.
4. Můj Vedoucí lists every client's notes, grouped by client. Each note names its client and is used
   only in that client's studies.

## What is built (develop @ 399b8057)

- **Hatching is one button.**
  - `HatchCard` sits in the pane (`components/workbench/LeadPane.tsx:298`), and the same button is on
    `/app/lead` (`components/aia/LeadProfile.tsx:107-112`).
  - `POST /api/v1/lead` takes no input (`application/research_lead.py:1353` `LeadProfile.hatch`),
    so the name, SOUL and USER are defaults.
- **`/app/lead`** shows:
  - the name and the hatch date;
  - SOUL and USER, read only;
  - the auto-accept toggle (a stored preference);
  - Paměť: personal notes and notes per client.
- **Not built:** no mark, no motion setting, no Dovednosti and no Nástroje. The only Lead visual is
  `ActivityOrb` (thinking-orbs), shown while a step runs.
- **Links to Můj Vedoucí:** in the pane's header (`LeadPane.tsx:267`), the edit notice
  (`LeadPane.tsx:510`) and the workbench menu (`Workbench.tsx:1024`). None on the Settings rail.

## LI0. The allowance for personal Lead work

- **A fifth money amount** beside D-01's four (study budget, wallet, threshold, wallet ceiling: `MoneyAmount`, `money.py:77`):
  the organization's allowance for personal Lead work, which pays for work a researcher's own Lead
  does outside any study, starting with the hatch. Its Czech name is proposed as "Rozpočet
  osobního Vedoucího"; the name is Nigel's to confirm in the PR.
- **Where it is named:** `domain/money.py` (`MoneyAmount`, `MONEY` with its column, role, who sets
  it and what null means) and `apps/web/src/i18n/cs.ts` `money`, both held by the vocabulary
  fixture that already pins the four.
- **Its place in the one precedence:** it is a budget of its own, not inside any study's, so it
  stops personal Lead spending at every reservation, as the study budget stops a study's. No wallet
  or threshold applies to it. Null means no personal Lead work may be paid (a hatch says so and who
  may set it), never unlimited.
- **Stored and set:** a column on the organization (migration), set on Settings by an organization
  OWNER or ADMIN, audited. Every charge is a usage-ledger row naming no study, with the
  organization and the researcher.
- **ADR 0028 amendment** (or a new ADR if the docs PR finds the amendment too large): the fifth
  amount, its precedence and its null. Written under the PR's Doc follow-up.
- **Tests:** the vocabulary fixture names five; a hold over the allowance is refused by name; null
  refuses; only OWNER or ADMIN sets it; a charge names no study.

## LI1. Hatching writes the Lead's files with one model request

**In.**
- **The name:** 40 characters and 160 bytes, as today.
- **Four traits, each one of two:**
  - tone: věcný / vřelý;
  - answers: stručně / podrobně;
  - initiative: čeká na pokyn / sám navrhuje;
  - numbers: vždy s nejistotou / jen když je důležitá.
- **"Jak má pracovat":** free text, at most 1,500 characters and a byte bound that keeps the request
  within its window.
- **"O vás":** optional, at most 2,000 characters.

**The request.**
- One request on the Lead's route, under `STUDY_LEAD`'s binding (the Lead's own model when
  `AIA_AI_RESEARCH_LEAD_MODEL_ID` is set). It has a closed output contract `{soul, user}` and one
  schema repair. The prompt is a new pinned prompt id, `aia.research.lead_hatch`.
- It runs as a worker step, a `research_lead_hatch` workflow type, so it is durable, metered,
  lease-fenced and recorded in the usage ledger like a turn.
- **Its class by rule:** the traits and the brief are the researcher's own words about their
  working style, Class C like the Lead's personal files (`material_rules.py`). A route approved only
  for a lower class refuses it by name.

**Held, priced and stated before the person confirms.**
- The hold covers the call and its one repair at the Lead model's prices. The window is the
  request's own, a few KB of input plus the output cap, not the 96 KB turn window.
- The screen shows that ceiling in USD, with the model's name, before "Vylíhnout". Nothing is sent
  until the person confirms.
- **The cost at the Lead model's prices** is `2 × (input_tokens × input_usd_per_mtok + output_cap ×
  output_usd_per_mtok) / 1e6`.
  - The prices are develop's `aia_ai_research_lead_*_usd_per_mtok` parameters, which are not in
    the repository, so the figure is computed by the worker from them and shown, never written here.
  - LI1 measures the real input tokens on the fixture and states the USD at develop's prices in its PR.

**Who pays: LI0's allowance** (Nigel, relayed 2026-10-25 ~22:25 UTC, answer (a)). A hatch happens
outside any study, so it is held and charged against the organization's allowance for personal
Lead work. A hatch over what is left is refused by name, with the amount and who may raise it; it
is never started on a confirmation (the threshold is never a cap, `money.py:31-34`).

**Checked, never trusted.**
- **Byte bounds:** SOUL 2,800 bytes and USER 2,800 bytes (ADR 0041 decision 2).
- **The personal-file check** (ADR 0030 decision 3): no client name, no number.
- **A failed check:**
  1. The step asks once more, with the reasons, as a repair.
  2. A second failure ends the hatch, refused by name (`lead_hatch_refused`, with the reasons). The
     person can edit what they wrote and try again.
- Nothing is cut or rewritten by code.

**When the model is off or unconfigured,** hatching says why, using the existing refusal reasons
(`research_lead_unconfigured`, a route-class refusal). It is never composed by code instead.

**The greeting.** The Lead's first words after hatching are part of the same output (`greeting`,
bounded), stored as its first turn. They are not a second request.

**Tests:**
- the contract and its bounds;
- the personal-file refusal, then the repair, then the refusal by name;
- a refusal when the model is off, with nothing sent and nothing charged;
- the hold at the Lead's prices;
- recorded doubles only, with zero paid calls in tests.

## LI2 to LI7

- **LI2.** `researcher_leads` gains `mark` and `motion`.
  - Defaults: `lissajous` and `live`.
  - Migration: off the head when the PR is opened.
  - `PUT /lead/preferences` takes them; each change is audited like `auto_accept_text_edits`.
  - Tests: an unknown value is refused, the setting is the caller's own, and it is audited.
- **LI3.** `lib/lead-marks.ts` holds the five curves as pure functions of time:
  - Lissajous: x = sin(3t + π/2), y = sin(2t);
  - Fourier: the sum of rₖ e^{ikt};
  - Slunečnice: θ = n · 137.5°, r = c√n;
  - Interference: two travelling waves;
  - Gauss: φ(x).

  A `LeadMark` component draws them on canvas in `--ai-ink`. Klidná, or reduced motion, draws one
  still frame. Tests: the geometry's fixed points, and the still frame under reduced motion.
- **LI4.** The four steps with Zpět and Přeskočit (on the optional step), as drawn:
  - a live preview of what will be sent;
  - then the cost and Vylíhnout;
  - then "se líhne…" while the step runs, showing the existing step activity;
  - then the greeting.

  It is checked in Playwright at 1440, 1024, 768 and 390.
- **LI5.** Můj Vedoucí to the artboard.
  - "Otevřít chat" reads the researcher's newest Lead turn across their studies, through their own
    scope, never another member's.
  - Dovednosti and Nástroje come from LI6.
  - Paměť is grouped by client, as today.
  - Checked in a journey at four widths, with zero paid jobs.
- **LI6.** One read, `GET /lead/capabilities`:
  - skills from the worker registry, each with its stage;
  - tools from the worker's composition and switches, with a tool that is off named with its
    reason. Hledat na webu reads "připravujeme" until LO20.
  - Tests: a switched-off worker is not listed as a skill, and an off tool says why.
- **LI7.** The Settings rail item, on every Settings page. It rides with LI5.

## Order

LI0 → LI1 → LI2 → LI3 → LI4 → LI5 (with LI7) → LI6.
- Five PRs: LI0 (money), LI1+LI2 (server), LI3+LI4 (web), LI5+LI7, then LI6.
- LI6's skills ship from `LeadWorkerSpec` first and switch to the action registry when LO21a lands.
- None of these waits on LO5a or LO21.

## Decided

1. **Who pays for a hatch:** an organization-level allowance for personal Lead work, set on
   Settings, ledgered like other spend, covering future personal Lead work outside a study (LI0).
2. **Re-hatching: no.** The Lead is hatched once; afterwards it changes only through chat, as the
   artboard says ("Všechno půjde změnit později rozhovorem s ním"). A second `POST /lead` stays
   refused, as today.

Both by Nigel, relayed by the coordinator, 2026-10-25 ~22:25 UTC.

## Findings

None yet.
