---
status: done
chunks:
  - "[x] 1. The study Lead's Settings card: a label for STUDY_LEAD, an off reason that holds in both off states, and the card's test -- lands: cs.ts + ControlPanel.test.tsx"
---

# The study Research Lead's card on Settings

**Owner:** nigelblount · **Started:** 2026-10-19 · **Follows:** `lead-model.md` finding F1

## Problem

`lead-model.md` F1 (Settings did not list the study Research Lead) is fixed on
`feature/lead-model` by d569a057: a `study_lead` activity in `_native_runtime`, its switch in
`AI_SWITCHES` and the web service's Compose environment, and
`test_every_capability_the_worker_binds_belongs_to_an_activity_the_page_lists` parametrised with
the Lead off, on, and on its own model. Two things about the card the page renders from it were
still wrong, and no web test exercised the card:

1. **`STUDY_LEAD` has no label.** The card's capability code carries the label as its title
   (`apps/web/src/components/aia/settings/ControlPanel.tsx:566 @ 644add36`); `cs.ts` labels every
   other capability but not `STUDY_LEAD` (`apps/web/src/i18n/cs.ts:1621-1629 @ 644add36`), so
   the title is the raw key `aia.settings.panel.capability.STUDY_LEAD`.
2. **The "off" reason is wrong for the Lead's own switch.** It said "Zprávy Vedoucímu počkají s
   důvodem" (messages wait, with a reason) (`cs.ts:1572 @ 644add36`). With
   `AIA_AI_RESEARCH_LEAD_ENABLED` off the API refuses a message with 409
   `research_lead_unavailable` and queues nothing (`apps/api/src/aia_api/config.py:128-131`,
   `packages/aia_core/src/aia_core/application/research_lead.py:306 @ 644add36`). Messages wait
   only in the other off state: the runtime off with the Lead's switch on, where the API accepts
   the message and the worker parks the turn (`apps/executors/src/aia_executors/registry.py:99`).

## Approach

- `STUDY_LEAD`: "vedoucí výzkumu studie: konverzace a návrhy změn", beside Deep Research's
  `RESEARCH_LEAD` ("… (Deep Research)").
- The off reason states only what holds in both off states: the Lead does not answer, nothing is
  sent to a model, the study can still be edited by hand and the conversation stays readable.
- `ControlPanel.test.tsx` "the study's Research Lead: its own card and capability, on or off by
  its own switch": the card's heading, its capability label, its harness version, configured
  with the design agents off, and off by its own switch with the reason and the switch named.

## Trade-off accepted

The off sentence is less specific than either state alone ("refused" or "waits"); the page reads
switches only and cannot tell which applies to a message.

## Verification

- The new test fails on `644add36`'s copy (`expected 'aia.settings.panel.capability.STUDY_LEAD'
  to be 'vedoucí výzkumu studie: konverzace a návrhy změn'`) and passes with it.
- `make test-web`: 104 files, 1819 tests passed. `tsc --noEmit` and eslint on the touched files
  clean. `test_settings_presentation.py` and `test_settings_api.py`: 40 passed (unchanged here).
- The settings journey (`tools/ui_workbench/settings_journey.mjs` against `make ui-workbench`):
  PASS, 74 layouts with no page overflow, no page errors, no paid job; the AI tab's last card is
  "Vedoucí výzkumu" with the new off reason.

## Findings

None.

## Doc follow-up

None beyond #488's: no shared document describes the card's copy.

## Review outcome

Filled in when the plan is archived.
