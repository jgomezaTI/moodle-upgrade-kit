---
name: moodle.logs
description: Analyze configured Nginx/Apache, PHP, Moodle and cron log sources for new or material errors.
effect: read-only
version: 0.2.0
---

# moodle.logs

## Purpose

Analyze configured Nginx/Apache, PHP, Moodle and cron log sources for new or material errors.

## Effect

`read-only`

## Inputs

- Configured log files
- Configured patterns
- Time window or baseline marker

## Outputs

- `logs-before.json` or `logs-after.json`

## Procedure

1. Read only configured log sources.
2. Count configured critical and warning patterns.
3. Prefer comparing a bounded post-upgrade window to the baseline rather than scanning unlimited history.
4. Redact secrets and avoid copying large raw logs into reports.
5. Group repeated signatures to avoid inflating one root cause into many incidents.
6. Support bounded configured local files and Docker log sources using argv-safe `docker logs --tail` execution.
7. Persist counts and source execution/readability metadata only; never persist raw Docker/file log text.

## Blocking conditions

- New PHP fatal/uncaught errors associated with the upgrade
- Critical web errors exceed configured threshold

## Universal rules

- Never print or persist passwords, private keys, bearer tokens, session cookies or DB DSNs containing credentials.
- Preserve the run ID in every generated artifact.
- Distinguish `critical`, `warning` and `info` findings.
- Do not claim a check passed if it did not execute.
- An empty log-source set is incomplete, and an unreadable required source blocks completion.
- Reject unsafe container names and unbounded Docker tail requests before execution.
- Prefer deterministic repository scripts over improvised shell commands when an equivalent helper exists.
