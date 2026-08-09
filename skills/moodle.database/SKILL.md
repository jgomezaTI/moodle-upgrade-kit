---
name: moodle.database
description: Execute only allow-listed validation SQL before and after the upgrade, preserving query identity and summarized results.
effect: read-only by default
version: 0.1.0
---

# moodle.database

## Purpose

Execute only allow-listed validation SQL before and after the upgrade, preserving query identity and summarized results.

## Effect

`read-only by default`

## Inputs

- DB connection from environment/secret provider
- Configured SQL check files

## Outputs

- `database-before.json` or `database-after.json`

## Procedure

1. Load connection values from environment variables; never from committed passwords.
2. Read SQL only from allow-listed files declared in configuration.
3. Reject mutation keywords for validation checks unless an explicitly separate migration path is approved.
4. Capture row counts and bounded sample results needed for evidence.
5. Compare the same checks pre/post when possible.

## Blocking conditions

- A critical validation query fails
- A validation file contains mutation statements
- Connection credentials would be persisted in evidence

## Universal rules

- Never print or persist passwords, private keys, bearer tokens, session cookies or DB DSNs containing credentials.
- Preserve the run ID in every generated artifact.
- Distinguish `critical`, `warning` and `info` findings.
- Do not claim a check passed if it did not execute.
- Prefer deterministic repository scripts over improvised shell commands when an equivalent helper exists.
