---
name: moodle.plugins
description: Review Moodle plugins and arbitrary project code for known upgrade risks while keeping uncertain compatibility explicit.
effect: read-only
version: 0.2.0
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

## Procedure

1. Preserve inventory's conservative plugin classification; do not claim core status without evidence.
2. Respect explicit ignore rules and declared target compatibility mappings.
3. Scan custom plugins and configured arbitrary custom code within configured file/byte bounds.
4. Search deterministic high-risk patterns for known PHP removals, target-specific Moodle deprecations and schema-coupling signals.
5. Store finding ID, file path and line number, not source-code contents.
6. Optionally compare the Moodle tree against a configured Git core reference and surface changed filenames for review.
7. Keep custom/unclassified plugins on a manual-review list when target compatibility is not proven.

## Safety

- Read-only filesystem/Git inspection only.
- Skip large generated/dependency trees such as `.git`, `vendor`, `node_modules`, `.venv` and moodledata.
- Pattern absence is not proof of full compatibility.
- A manual-review item may remain even when no known critical signature was found.

## Blocking conditions

- Configured custom code cannot be scanned/inventoried
- A known critical compatibility signature is detected

## Universal rules

- Never persist secrets or full source excerpts.
- Preserve stable finding IDs so real regressions can become permanent checks.
- Keep known failures separate from unknown/manual review.
