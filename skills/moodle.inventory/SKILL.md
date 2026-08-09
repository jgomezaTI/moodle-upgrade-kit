---
name: moodle.inventory
description: Detect and record the instance identity and operational prerequisites: Moodle version/root, PHP, DB type, Git state, installed plugins, disk usage, cron and key paths.
effect: read-only
version: 0.1.0
---

# moodle.inventory

## Purpose

Detect and record the instance identity and operational prerequisites: Moodle version/root, PHP, DB type, Git state, installed plugins, disk usage, cron and key paths.

## Effect

`read-only`

## Inputs

- Environment YAML config
- Read access to Moodle root and relevant system commands

## Outputs

- `runs/<run-id>/inventory.json`
- A blocker/warning summary

## Procedure

1. Resolve the instance root and prove it looks like Moodle (`version.php`, `config.php`, `admin/cli`).
2. Capture Moodle release/build when readable without exposing secrets.
3. Capture PHP CLI version and relevant extensions.
4. Capture Git branch/HEAD/dirty state if the Moodle root is a repository.
5. Capture disk free space for Moodle root, moodledata and backup paths.
6. Inventory plugin directories and identify non-core/custom candidates.
7. Capture cron/scheduled-task execution context when readable.
8. Classify blockers separately from warnings. Never mutate the server.

## Blocking conditions

- Moodle root cannot be identified
- Required path is inaccessible
- Insufficient disk threshold if one is configured

## Universal rules

- Never print or persist passwords, private keys, bearer tokens, session cookies or DB DSNs containing credentials.
- Preserve the run ID in every generated artifact.
- Distinguish `critical`, `warning` and `info` findings.
- Do not claim a check passed if it did not execute.
- Prefer deterministic repository scripts over improvised shell commands when an equivalent helper exists.
