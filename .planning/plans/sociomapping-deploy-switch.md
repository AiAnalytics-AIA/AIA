---
status: done
chunks:
  - "[x] 1. Pass the saved switch to the API and check Compose interpolation"
  - "[x] 2. Verify live map run and internal report"
  - "[x] 3. Publish permanent wiring and remove temporary overlay"
---

# Sociomapping deployment switch

The API supports and pins the experimental engine, but develop Compose omitted
AIA_SOCIOMAPPING_EXPERIMENTAL_ENABLED. SSM and .env could say true while the
API always read its false default. This made the user's enabled map test unavailable.

Pass the switch only to the API, with false as the default. Add it to env.example.
CI resolves Compose with false and true and checks the actual API environment.
No changes to the engine, thresholds, permissions, network, or budget gates.

Live recovery used a narrowly scoped temporary overlay during review. It was removed
after the permanent deployment passed the saved switch through base Compose alone.
The initial n=80 test was suppressed by support gates; revision 4 increased the
fictional sample to 180 and verified 59 independent profiles before paid fieldwork.

Doc follow-up: a configuration value saved in SSM is not proof a container receives
it. Check the resolved Compose environment and the process's actual Settings.

## Final native acceptance — 2026-10-09

Published prompt PR #215, permanent switch PR #218 and analysis guidance PR #219
are merged. Tested release aac0f1b29d9b35730559510df6aba99875b779aa passed full
required CI 37945120531 and deployment 37947521206. All 21 current baseline hashes
match the reviewed prompt pack; all eight audited active research versions remain
e2/e3/e4/e5 as activated. The temporary Compose overlay is removed; base Compose
and API Settings independently read the enabled map switch.

Native run RUN-1725024c5b8b480a completed on frozen revision 4
(REV-af854d2644c946a4): 180 fictional respondent calls succeeded, no model failures,
59 independent fictional profiles and 16 admitted evidence rows. All eight analysis
modules completed under analysis-module-v3 with no final violations. Seven passed
on their first turn; implications used one existing repair. The engine mapped all
four comparable offers with 180 complete respondents and zero exclusions. Every
workflow step, including the main report and separate map report, succeeded.

The native DOCX artifacts were downloaded and SHA256-verified. All 14 main-report
pages and all 9 map-report pages were rendered and visually reviewed. The map is
visible on page 5 of its report and in the authenticated AIA results view. The first
run and its original report hash remain unchanged.

This run cost $2.8704786; total sandbox spend is $10.2726756, leaving $9.7273244
under the unchanged $20 hard cap. Earlier n=80 support suppression and v2 prose
validation failures remain recorded as failed attempts, not successful acceptance.

The map is EXPERIMENTAL_AIA, internal only, synthetic and unweighted. Its perfect
rank fit with four objects is not significance, adequacy or SOMECS verification.
No respondent placement or interpolated height surface is claimed. Both reports
remain unapproved internal concepts. Prompt guidance improves behavior; the final
outputs still repeat some comparisons and occasionally spell numbers as words.

Evidence anchors: analysis/prompt.py:38 (full path
packages/aia_core/src/aia_core/domain/analysis/prompt.py) @ aac0f1b29d9b35730559510df6aba99875b779aa;
deploy/develop/docker-compose.yml:126 @ aac0f1b29d9b35730559510df6aba99875b779aa;
test_metric_label_wording_does_not_license_an_uncited_count. Runtime acceptance
receipt and layer review map are in outputs/aia-prompt-upgrade-2026-10-09 in the
calling project workspace, outside Git; no fictional individual records are committed.
