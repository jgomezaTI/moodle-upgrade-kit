---
name: moodle.compatibility
description: Deterministically assess whether inventory evidence satisfies the configured target Moodle platform and upgrade-path requirements.
effect: read-only
version: 0.2.0
---

# moodle.compatibility

## Purpose

Turn `moodle.inventory` facts into an explicit compatibility verdict for the target Moodle branch. Do not re-probe the server when inventory already contains the evidence.

## Inputs

- `inventory-before.json` / `inventory.json`
- Configured target Moodle version

## Outputs

- `runs/<run-id>/compatibility.json`
- Deterministic checks, blockers/warnings and a manual-review list

## Procedure

1. Resolve the target branch against the maintained requirement matrix.
2. Verify the current Moodle release satisfies the target's minimum upgrade-source version.
3. Verify PHP minimum/maximum and also flag when the current/source Moodle is already running below its own supported PHP minimum.
4. Verify required PHP extensions and surface recommended extension gaps as warnings.
5. Verify applicable PHP settings such as `max_input_vars` and 64-bit PHP requirements when the target needs them.
6. Verify supported database driver/version and target-specific prefix constraints when applicable.
7. Surface deployment changes that require planning, such as Moodle 5.1+ public web root.
8. Pass plugins and arbitrary custom-code targets to manual review rather than silently treating unknown compatibility as success.

## Classification rules

- Proven requirement violation: `critical`.
- Required evidence that is unknown: `critical` when it prevents proving target safety.
- Recommended but non-blocking platform guidance: `warning`.
- Plugin/custom-code compatibility is not inferred from directory existence; deeper source/plugin review belongs to `moodle.plugins`.

## Blocking conditions

- Unknown target requirement matrix entry
- Unsupported upgrade source
- Unsupported PHP or required PHP extension/settings
- Unsupported/unknown database requirement needed by the target
- Configured critical custom code cannot be inventoried

## Universal rules

- Read-only only; consume structured inventory evidence.
- Never persist secrets.
- Preserve the run ID and stable finding/check IDs.
- Unknown is never silently treated as compatible.
