---
name: moodle.document
description: Generate a redacted local evidence report and expose external documentation synchronization status without losing technical evidence.
effect: read/write artifacts
version: 0.3.1
---

# moodle.document

## Purpose

Summarize structured run evidence into a local technical report. External synchronization is adapter-owned and must never replace or erase the local evidence trail.

## Inputs

- Run evidence directory
- Documentation/redaction configuration
- Optional external documentation provider configuration

## Outputs

- `runs/<run-id>/final-report.md`
- `runs/<run-id>/document-result.json`
- `runs/<run-id>/document-sync.json` after authenticated external synchronization
- External synchronization status when a provider is configured

## Procedure

1. Read only the fixed structured evidence artifacts produced by the critical path.
2. Derive an overall state from validation/upgrade/rollback evidence without rewriting failures as success.
3. Aggregate stable finding IDs and summaries.
4. Redact default credential patterns plus configured redaction patterns.
5. Always preserve the local Markdown report.
6. When an external provider such as Google Drive is configured but no authenticated adapter is available, record `external-adapter-required` rather than pretending synchronization completed.
7. A synchronization failure/pending adapter may warn, but must not destroy local technical evidence.
8. When synchronization is required, delegate `moodle.document.sync` to an authenticated adapter, verify the target through a read-after-write, and record only provider/resource metadata through `muk record-document-sync`.
9. Honor `documentation.summary_mode`. For `findings-focused`, publish grouped warnings/errors/corrections and outcomes; when an accepted upgrade has no findings, publish only a concise success record rather than the full execution narrative.
10. Include the Git start/end identity and state that the upgrade workflow created no automatic commit; do not invoke Git mutation from documentation.

## Blocking conditions

- A report would expose unredacted secrets
- A report would claim acceptance contrary to validation evidence

## Universal rules

- Never embed credentials in reports.
- Local structured evidence remains authoritative.
- External publishing and authentication must be explicit adapter behavior.
