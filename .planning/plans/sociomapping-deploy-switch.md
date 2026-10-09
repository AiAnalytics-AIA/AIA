---
status: in-progress
chunks:
  - "[x] 1. Pass the saved switch to the API and check Compose interpolation"
  - "[ ] 2. Verify live map run and internal report"
  - "[ ] 3. Publish permanent wiring and remove temporary overlay"
---

# Sociomapping deployment switch

The API supports and pins the experimental engine, but develop Compose omitted
AIA_SOCIOMAPPING_EXPERIMENTAL_ENABLED. SSM and .env could say true while the
API always read its false default. This made the user's enabled map test unavailable.

Pass the switch only to the API, with false as the default. Add it to env.example.
CI resolves Compose with false and true and checks the actual API environment.
No changes to the engine, thresholds, permissions, network, or budget gates.

Live recovery: a narrow root-owned docker-compose.override.yml passes that same
SSM-backed variable to the API, preserving it across deploys while permanent wiring
is reviewed. It is removed only after the deployed base Compose passes true by itself.
The existing first run stays frozen; the approved fictional four-offer n=80 revision
runs within the unchanged $20 hard study cap.

Doc follow-up: a configuration value saved in SSM is not proof a container receives
it. Check the resolved Compose environment and the process's actual Settings.
