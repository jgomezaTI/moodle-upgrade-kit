# Moodle Upgrade Kit Constitution

## I. Safety before automation

Read-only diagnostics are the default. Any command that can mutate Moodle, its database, Git state, filesystem, cron, web server configuration, or backups must be explicitly marked destructive and must not execute without a human gate.

## II. Evidence before claims

Every pass/fail conclusion must be backed by captured evidence: command output, structured test results, query results, metadata, or a reproducible observation. The documentation layer summarizes evidence; it must not invent success.

## III. Reversible production changes

A production upgrade is invalid unless a rollback procedure exists and the configured backup checks pass. A backup that merely exists but has no verifiable timestamp/component inventory is treated as insufficient.

## IV. Deterministic execution

Agents may decide what to inspect and how to interpret findings, but repeated operational actions should be performed by versioned scripts or allow-listed commands whenever practical.

## V. No secrets in artifacts

Secrets must not be committed, included in generated reports, echoed in logs, or persisted in `runs/`. Any evidence pipeline must redact sensitive values.

## VI. Baseline comparison

Every upgrade run must capture a pre-upgrade baseline and a post-upgrade validation. The same critical checks should run before and after when possible.

## VII. Regression becomes coverage

Every material defect discovered during an upgrade should result in at least one new regression check, test fixture, documented rule, or compatibility guard.

## VIII. Git technical source of truth

Skills, commands, scripts, configuration schemas and technical evidence formats are versioned in Git. Google Drive is the collaboration and human-readable reporting layer, not the sole technical record.

## IX. Environment identity is mandatory

Every run must identify instance, environment, Moodle root, base URL, target version, Git revision and run ID before mutation.

## X. Production requires explicit intent

A configuration declaring `environment: production` is not sufficient authorization. Mutation requires an explicit run-time approval in addition to configuration-level enablement.
