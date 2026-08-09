---
name: moodle.plugins
description: Review Moodle plugins and arbitrary project code for known upgrade risks while keeping uncertain compatibility explicit.
effect: read-only
version: 0.2.1
---

# moodle.plugins

## Purpose

Analyze the plugin/custom-code candidates discovered by inventory, including code outside standard Moodle plugin boundaries such as `portal_v3` and allowed `../...` project paths.

## Inputs

- Environment config
- Inventory evidence
- Optional declared plugin target compatibility
- Optional known-clean Git core reference

## Outputs

- `runs/<run-id>/plugins.json`
- Plugin classifications, bounded source-scan findings and manual-review candidates
- Explicit `covered_scan_paths` evidence when a configured child path is already covered by a configured parent scan root

## Procedure

1. Preserve inventory's conservative plugin classification; do not claim core status without evidence.
2. Respect explicit ignore rules and declared target compatibility mappings.
3. Build source-scan targets from custom plugins and configured arbitrary custom code.
4. Collapse overlapping scan targets to minimal parent roots regardless of configuration order. For example, when both `../batch` and `../batch/edx` are configured, scan `../batch` once and record `../batch/edx` as covered by that parent.
5. Scan the resulting non-overlapping roots within configured file/byte bounds.
6. Search deterministic high-risk patterns for known PHP removals, target-specific Moodle deprecations and schema-coupling signals.
7. Store finding ID, file path and line number, not source-code contents.
8. Optionally compare the Moodle tree against a configured Git core reference and surface changed filenames for review.
9. Keep custom/unclassified plugins on a manual-review list when target compatibility is not proven.

## Safety

- Read-only filesystem/Git inspection only.
- Skip large generated/dependency trees such as `.git`, `vendor`, `node_modules`, `.venv` and moodledata.
- Do not scan the same file twice merely because both a parent and child custom path were configured.
- Pattern absence is not proof of full compatibility.
- A manual-review item may remain even when no known critical signature was found.

## Blocking conditions

- Configured custom code cannot be scanned/inventoried
- A known critical compatibility signature is detected

## Universal rules

- Never persist secrets or full source excerpts.
- Preserve stable finding IDs so real regressions can become permanent checks.
- Keep known failures separate from unknown/manual review.
