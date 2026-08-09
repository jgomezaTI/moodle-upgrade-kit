---
name: moodle.backup
description: Verify that required backup components exist, are recent enough, and have enough metadata to support rollback planning.
effect: read-only
version: 0.1.0
---

# moodle.backup

## Purpose

Verify that required backup components exist, are recent enough, and have enough metadata to support rollback planning.

## Effect

`read-only`

## Inputs

- Backup paths
- Required components
- Maximum age

## Outputs

- `backup.json`
- Pass/block status

## Procedure

1. Enumerate configured backup locations without modifying them.
2. Identify database, code and moodledata components as configured.
3. Check timestamps against the maximum allowed age.
4. Capture sizes/checksums when practical.
5. Treat “file exists” as insufficient when required component identity or age cannot be proven.

## Blocking conditions

- Missing required component
- Backup older than policy
- Backup location inaccessible

## Universal rules

- Never print or persist passwords, private keys, bearer tokens, session cookies or DB DSNs containing credentials.
- Preserve the run ID in every generated artifact.
- Distinguish `critical`, `warning` and `info` findings.
- Do not claim a check passed if it did not execute.
- Prefer deterministic repository scripts over improvised shell commands when an equivalent helper exists.
