---
status: in-progress
chunks:
  - "[x] 1. Clarify prose labels and unavailable-module responses without weakening validation"
  - "[ ] 2. Publish and verify a complete AI plus Sociomapping run"
---

# Analysis label prompt repair

Live fictional run RUN-9e58d424dbcc4eec completed 180 respondent calls and admitted
16 evidence rows, but hypotheses and limitations exhausted their repairs on an
uncited numeral in a top-box label. The main report correctly refused incomplete
analysis, and the run stopped before its independent map branch executed.

Teach analysis-module-v3 and its repair instruction to keep machine metric names
in numeric_claims and use natural language in prose. Inapplicable modules should
return a short candid summary and empty arrays. Restricted module context is not
proof the full dataset lacks an attribute. Do not invent benchmarks or statistical
significance to describe differences. The schema, digit scanner, admission gates,
retry limits and budget cap are unchanged.

Regression: test_metric_label_wording_does_not_license_an_uncited_count verifies
that the existing gate rejects top-2 and an invented percentage, while admitting
the same supported value under the suggested natural-language label.

Doc follow-up: report failure currently stops a runnable map branch, although the
map depends only on frozen dataset and specification. Record this observed behavior;
this prompt fix does not change global workflow failure policy.
