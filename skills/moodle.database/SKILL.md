---
name: moodle.database
description: Execute only configured read-only validation SQL and preserve bounded, credential-free evidence before or after an upgrade.
effect: read-only
version: 0.2.0
---

# moodle.database

## Purpose

Run explicit database validation checks without allowing validation SQL to become a mutation path.

## Inputs

- Database driver
- Environment-variable names for connection values
- Optional Docker DB container
- Allow-listed SQL files and expected result semantics

## Outputs

- `runs/<run-id>/database-before.json` or `database-after.json`
- Per-check execution/result metadata and bounded sample rows

## Procedure

1. Load credential values only from environment variables named in configuration.
2. Accept SQL only from configured files.
3. Strip comments/literals for policy inspection and reject multiple statements or mutation keywords.
4. Permit only validation statement families such as SELECT/SHOW/EXPLAIN/DESCRIBE/WITH.
5. Execute through the local DB client or configured Docker container without placing password values in argv/evidence.
6. Evaluate configured expectations (`empty`, `nonempty`, `any`).
7. Persist row count and a bounded sample, never connection credentials.

## Blocking conditions

- Critical check cannot execute
- Validation SQL is not provably read-only
- Critical expectation fails
- Required connection environment is missing for a critical check

## Universal rules

- Database validation is read-only.
- Never embed passwords/tokens in YAML, command arguments or evidence.
- Keep check IDs stable for before/after comparison and regression tracking.
