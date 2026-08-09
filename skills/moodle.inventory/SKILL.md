---
name: moodle.inventory
description: Detect and record the instance identity and operational prerequisites: Moodle version/root, PHP, DB type, Git state, installed plugins, non-core code, disk usage, cron and key paths.
effect: read-only
version: 0.3.0
---

# moodle.inventory

## Purpose

Detect and record the instance identity and operational prerequisites: Moodle version/root, PHP, database runtime metadata, Git state, installed plugins, non-core code, disk usage, cron and key paths.

## Effect

`read-only`

## Inputs

- Environment YAML config
- Read access to Moodle root and relevant system commands
- Optional Docker runtime target when Moodle executes inside a container
- Optional explicit custom plugin paths and arbitrary custom code paths such as `portal_v3`

## Outputs

- `runs/<run-id>/inventory.json`
- A blocker/warning summary
- Plugin metadata with conservative custom/unclassified classification
- Configured custom-code metadata and automatically detected non-core top-level candidates

## Procedure

1. Resolve the source-side Moodle root and prove it looks like Moodle (`version.php`, `config.php`, `admin/cli`).
2. Capture Moodle release/build from the source tree when readable without exposing secrets.
3. Resolve the configured execution runtime. For `local`, inspect PHP on the current host. For `docker`, verify the configured container is running, record its image, prove the runtime Moodle root contains the expected markers, and capture PHP CLI/version/extensions using non-mutating `docker exec` commands.
4. Discover the Git repository from the Moodle source path using Git itself, including the case where `.git` is located in a parent directory; record repository root, branch, HEAD and dirty state.
5. Capture disk free space for the host-visible Moodle root, moodledata and configured backup paths.
6. Inventory configured plugin type roots. Parse plugin component/version/requires metadata when `version.php` exists. Treat `local/*` and explicitly configured plugin paths as custom; leave other plugins `unclassified` until they are compared with the matching Moodle core release.
7. Inventory explicitly configured arbitrary code paths such as `portal_v3` using filesystem metadata only: existence, file/directory counts, aggregate size, common extensions and Git tracking state. Do not read file contents during inventory.
8. Detect top-level directories outside the known Moodle core layout as `non_core_top_level_candidates`. This is a candidate list, not a compatibility verdict.
9. When an optional database runtime container is configured, capture driver, container running state, image and database server binary version without credentials or database queries.
10. Capture cron configuration and the presence of `admin/cli/cron.php` without executing cron.
11. Classify blockers separately from warnings. Never mutate the host, container or Moodle instance.

## Plugin and non-core classification rules

- Never claim a plugin is core solely because its directory name resembles a Moodle plugin. Matching against the exact Moodle release belongs to compatibility analysis.
- `local/*` is considered project-specific/custom because Moodle core does not ship local plugins.
- `plugins.custom_paths` may explicitly identify known non-core plugins in other plugin types.
- `custom_code.paths` may point to arbitrary directories inside `moodle.root`, including legacy portals, integrations, report applications and scripts.
- `custom_code.auto_detect_top_level` may surface unknown top-level directories automatically. These entries are `non-core candidates` and require later review.
- Inventory may count files and extensions but must not persist source-code contents.

## Docker runtime rules

- Do not require Python inside the Moodle container; the kit may execute from the Docker host/WSL and use `docker exec` only for runtime inspection.
- Never invoke `docker exec` through a shell string. Pass commands and paths as argument vectors.
- Allowed runtime probes for inventory are read-only commands such as `php -v`, `php -m`, `test -f`, `test -d`, database server `--version`, and Docker metadata inspection.
- Do not read `config.php` contents to discover credentials. Only test for its presence.
- Treat an inaccessible/stopped configured Moodle runtime container or missing runtime Moodle markers as a critical finding.

## Blocking conditions

- Moodle root cannot be identified
- Required path is inaccessible
- Configured Docker Moodle runtime is unavailable or does not contain the expected Moodle root
- PHP CLI cannot be inspected in the configured runtime
- Insufficient disk threshold if one is configured

## Universal rules

- Never print or persist passwords, private keys, bearer tokens, session cookies or DB DSNs containing credentials.
- Preserve the run ID in every generated artifact.
- Distinguish `critical`, `warning` and `info` findings.
- Do not claim a check passed if it did not execute.
- Prefer deterministic repository scripts over improvised shell commands when an equivalent helper exists.
