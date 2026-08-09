---
name: moodle.inventory
description: Detect and record instance identity and platform evidence needed by later upgrade checks without mutating Moodle.
effect: read-only
version: 0.4.0
---

# moodle.inventory

## Purpose

Capture source/runtime identity and operational evidence for later capabilities. Inventory records facts; compatibility verdicts belong to `moodle.compatibility`.

## Inputs

- Environment YAML config
- Moodle source root and optional moodledata
- Optional Docker PHP and database containers
- Plugin roots, explicit custom plugin paths and arbitrary `custom_code.paths`

## Outputs

- `runs/<run-id>/inventory-before.json` for pre-change runs, with legacy `inventory.json` alias
- `runs/<run-id>/inventory-after.json` for post-change runs
- Structured findings and summary

## Procedure

1. Prove the configured source root with `version.php`, `config.php` presence and `admin/cli`.
2. Parse Moodle release/build/branch without reading secrets from `config.php`.
3. Inspect the configured PHP runtime read-only: version, loaded modules, `max_input_vars`, `memory_limit` and `PHP_INT_SIZE`.
4. For Docker, record container running state/image and runtime Moodle markers using argument-vector probes.
5. Discover the containing Git repository even when `.git` is above `moodle.root`; record repo root, branch, HEAD and dirty state.
6. Capture disk evidence for Moodle, moodledata and configured backup paths.
7. Enumerate configured plugin roots and parse component/version/requires metadata. Treat `local/*` and explicit custom paths as custom; otherwise remain `unclassified`.
8. Inventory arbitrary custom code metadata. Relative `..` is allowed only when the resolved target remains inside the discovered Git repository; absolute paths and repository escapes are rejected.
9. Record optional database driver, configured prefix, container/image/running state and server binary version without DB credentials or queries.
10. Record cron configuration and CLI presence without executing cron.

## Safety

- Read-only only.
- Do not execute Moodle cron, maintenance, upgrade, rollback or SQL.
- Do not persist source contents from arbitrary custom code.
- Do not read credential values from `config.php`.
- Docker probes use argument vectors, never shell interpolation.

## Blocking conditions

- Moodle root/markers cannot be proven
- Configured Docker PHP runtime is unavailable or has missing Moodle markers
- PHP CLI cannot be inspected
- Configured minimum free-space threshold is violated

## Universal rules

- Never print or persist passwords, private keys, bearer tokens, session cookies or credentialed DB DSNs.
- Preserve the run ID in generated artifacts.
- Distinguish `critical`, `warning`, `info` and unknown evidence.
- Never claim a check passed if it did not execute.
