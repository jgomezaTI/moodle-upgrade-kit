---
name: moodle.baseline
description: Capture the pre-upgrade functional state so post-change validation can compare the same checks like-for-like.
effect: read-only
version: 0.2.0
---

# moodle.baseline

## Purpose

Produce one pre-change baseline from proven inventory identity plus endpoint, database, log and cron evidence.

## Inputs

- Successful pre-change inventory evidence
- Configured endpoint checks
- Allow-listed database validation checks
- Configured log files/patterns

## Outputs

- `runs/<run-id>/baseline-before.json`
- `endpoints-before.json`
- `database-before.json`
- `logs-before.json`

## Procedure

1. Require proven Moodle identity and reject inventory criticals.
2. Execute configured endpoint smoke checks and honor per-endpoint severity.
3. Execute `moodle.database` read-only allow-listed checks.
4. Capture bounded configured log signatures without mutating/rotating logs.
5. Record cron CLI/configuration state from inventory without running cron.
6. Persist the definitions used so post-change checks remain like-for-like.
7. Preserve pre-existing log/database problems as baseline facts rather than automatically calling them regressions.

## Blocking conditions

- Missing Moodle identity
- Inventory contains critical findings
- Critical endpoint/database baseline check fails
- A required log source cannot be read
- Configured cron CLI is missing

## Universal rules

- Read-only only.
- Never persist credentials.
- A baseline is complete only when no critical baseline finding remains.
- Do not convert pre-existing warnings into post-upgrade regressions unless their post state worsens.
