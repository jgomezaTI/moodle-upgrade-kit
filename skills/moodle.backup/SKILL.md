---
name: moodle.backup
description: Verify explicit backup component identity, accessibility and freshness before any mutating upgrade or rollback step.
effect: read-only
version: 0.2.1
---

# moodle.backup

## Purpose

Prove that the configured rollback prerequisites exist. File existence alone is insufficient: required components need explicit identity rules and freshness evidence.

## Inputs

- Backup root directories
- Required component names
- Explicit per-component glob rules
- Maximum backup age
- Optional file checksum policy

## Outputs

- `runs/<run-id>/backup.json`
- Selected candidate metadata for every required component
- Pass/block summary

## Procedure

1. Verify configured backup roots are accessible directories.
2. Require an explicit identity rule for every required component (for example database/code/moodledata globs).
3. Resolve matching candidates only inside configured roots.
4. Select the newest candidate and calculate age against policy.
5. Optionally compute SHA-256 for selected files when configured.
6. Mark the backup set verified only when every required component is identified and within freshness policy.
7. Report configured/accessible root and required/verified component coverage. Missing root or component configuration is an explicit critical blocker, never an unexplained `verified: false` result.

## Blocking conditions

- Backup root inaccessible
- No backup root configured
- No required backup component configured
- Required component has no identity rule
- No candidate matches a required component
- Selected required component is older than policy

## Universal rules

- Read-only only; this capability does not create backups.
- Never infer component identity solely from an arbitrary filename.
- Upgrade and rollback must consume verified backup evidence rather than re-assuming backup state.
