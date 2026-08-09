---
name: moodle.inventory
description: Detect and record the instance identity and operational prerequisites: Moodle version/root, PHP, DB type, Git state, installed plugins, disk usage, cron and key paths.
effect: read-only
version: 0.2.0
---

# moodle.inventory

## Purpose

Detect and record the instance identity and operational prerequisites: Moodle version/root, PHP, DB type, Git state, installed plugins, disk usage, cron and key paths.

## Effect

`read-only`

## Inputs

- Environment YAML config
- Read access to Moodle root and relevant system commands
- Optional Docker runtime target when Moodle executes inside a container

## Outputs

- `runs/<run-id>/inventory.json`
- A blocker/warning summary

## Procedure

1. Resolve the source-side Moodle root and prove it looks like Moodle (`version.php`, `config.php`, `admin/cli`).
2. Capture Moodle release/build from the source tree when readable without exposing secrets.
3. Resolve the configured execution runtime. For `local`, inspect PHP on the current host. For `docker`, verify the configured container is running, prove the runtime Moodle root contains the expected markers, and capture PHP CLI/version/extensions using non-mutating `docker exec` commands.
4. Capture Git branch/HEAD/dirty state from the source-side Moodle checkout when it is a repository.
5. Capture disk free space for the host-visible Moodle root, moodledata and configured backup paths.
6. Inventory plugin directories and identify non-core/custom candidates from the source tree.
7. Capture cron configuration and the presence of `admin/cli/cron.php` without executing cron.
8. Classify blockers separately from warnings. Never mutate the host, container or Moodle instance.

## Docker runtime rules

- Do not require Python inside the Moodle container; the kit may execute from the Docker host/WSL and use `docker exec` only for runtime inspection.
- Never invoke `docker exec` through a shell string. Pass commands and paths as argument vectors.
- Allowed runtime probes for inventory are read-only commands such as `php -v`, `php -m`, `test -f`, `test -d` and Docker metadata inspection.
- Do not read `config.php` contents to discover credentials. Only test for its presence.
- Treat an inaccessible/stopped configured container or missing runtime Moodle markers as a critical finding.

## Blocking conditions

- Moodle root cannot be identified
- Required path is inaccessible
- Configured Docker runtime is unavailable or does not contain the expected Moodle root
- PHP CLI cannot be inspected in the configured runtime
- Insufficient disk threshold if one is configured

## Universal rules

- Never print or persist passwords, private keys, bearer tokens, session cookies or DB DSNs containing credentials.
- Preserve the run ID in every generated artifact.
- Distinguish `critical`, `warning` and `info` findings.
- Do not claim a check passed if it did not execute.
- Prefer deterministic repository scripts over improvised shell commands when an equivalent helper exists.
