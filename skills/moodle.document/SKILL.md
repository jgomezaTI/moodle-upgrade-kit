---
name: moodle.document
description: Generate a technical evidence report and synchronize a human-readable upgrade summary to the configured Google Drive destination.
effect: read/write artifacts
version: 0.1.0
---

# moodle.document

## Purpose

Generate a technical evidence report and synchronize a human-readable upgrade summary to the configured Google Drive destination.

## Effect

`read/write artifacts`

## Inputs

- Run evidence directory
- Documentation configuration
- Drive adapter/connector

## Outputs

- `final-report.md`
- Updated/created Google Drive report

## Procedure

1. Load only structured run evidence and bounded approved excerpts.
2. Redact configured sensitive patterns.
3. Summarize result, blockers, warnings, commands, timestamps and remediation.
4. Link technical findings to stable check IDs.
5. Do not rewrite a failed check as success.
6. If Drive synchronization fails, keep the local final report and mark sync as failed rather than losing technical evidence.

## Blocking conditions

- Evidence contains unredacted secrets
- Report would claim completion despite failed validation

## Universal rules

- Never print or persist passwords, private keys, bearer tokens, session cookies or DB DSNs containing credentials.
- Preserve the run ID in every generated artifact.
- Distinguish `critical`, `warning` and `info` findings.
- Do not claim a check passed if it did not execute.
- Prefer deterministic repository scripts over improvised shell commands when an equivalent helper exists.
