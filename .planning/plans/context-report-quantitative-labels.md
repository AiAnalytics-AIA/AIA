---
status: in-progress
chunks:
  - "[x] 1. Keep unlabelled historical numbers in their cited claims"
  - "[ ] 2. Verify regression tests and deploy the report correction"
---
# Context report quantitative labels

The first live contextual report admitted historical years as typed measures with no unit or indicator name. The exporter duplicated those years as isolated numeric paragraphs and treated their presence as benchmark coverage. Keep every accepted claim intact, but render a separate numeric phrase only when it identifies a unit or named indicator. Describe these as numeric source data, not automatically as comparable benchmarks. Missing labelled numeric data must retain the explicit no-benchmark disclosure. No evidence seal, grounding rule, source bundle or map calculation changes.

Verify both unlabelled historical years and labelled measurements in `test_contextual_report.py`; run the report/API export tests and required checks. Publish only after the merged release passes CI.

Focused verification: all twelve composer and interpretation API tests passed. Ruff, mypy, layer checks, planning validation and whitespace checks passed. `test_unlabelled_historical_years_do_not_become_benchmark_paragraphs` preserves the dated claim while refusing a bare numeric paragraph; `test_labelled_numeric_data_keeps_its_indicator_and_unit` preserves a labelled percentage. Test bundle inputs are normalized through the contract before sealing, so defaults and integer-to-float coercion do not create an invalid seal.
