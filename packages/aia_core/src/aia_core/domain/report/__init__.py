"""The report: a typed document model and its print register (pure; no I/O).

A report is built as data — metadata and blocks — and rendered to DOCX by an
infrastructure adapter (``aia_core.infrastructure.report_docx``). The domain side
owns what a report may contain and how it is formatted for print; it never
renders bytes and never originates a number (``.planning/plans/report-docx.md``).
"""
