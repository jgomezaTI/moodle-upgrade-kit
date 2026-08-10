---
name: moodle.plugins
description: Review Moodle plugins and arbitrary project code for known upgrade risks while keeping uncertain compatibility explicit.
effect: read-only
version: 0.3.0
---

# moodle.plugins

## Purpose

Analyze the plugin/custom-code candidates discovered by inventory, including code outside standard Moodle plugin boundaries such as `portal_v3` and allowed `../...` project paths.

## Inputs

- Environment config
- Inventory evidence
- Optional declared plugin target compatibility
- Optional local, known-clean Git source-core reference

## Outputs

- `runs/<run-id>/plugins.json`
- Plugin classifications, bounded source-scan findings and manual-review candidates
- Explicit `covered_scan_paths` evidence when a configured child path is already covered by a configured parent scan root

## Procedure

1. Preserve inventory's conservative plugin classification unless an exact, verified source-core comparison provides stronger evidence. Do not claim core status from directory names or plugin metadata alone.
2. Respect explicit ignore rules and declared target compatibility mappings.
3. Build source-scan targets from custom, non-core and core-modified plugins plus configured arbitrary custom code.
4. Collapse overlapping scan targets to minimal parent roots regardless of configuration order. For example, when both `../batch` and `../batch/edx` are configured, scan `../batch` once and record `../batch/edx` as covered by that parent.
5. Scan the resulting non-overlapping roots within configured file/byte bounds.
6. Apply each deterministic risk rule only to source regions where the rule is semantically valid. PHP runtime/API removals apply only to executable PHP regions in PHP/include source, excluding embedded HTML/JavaScript, comments and string literals. SQL/schema coupling rules may inspect PHP/include strings and SQL files. JavaScript `.split()` or `.each()` and comments mentioning removed PHP APIs must never become PHP compatibility findings.
7. Use distinct stable IDs for materially different removed PHP APIs such as `php_ereg_removed` and `php_split_removed`.
8. Store finding ID, file path and line number, not source-code contents.
9. Optionally consume a local Git source-core reference described by repository, ref and tree root. Never fetch or mutate repositories as part of this capability.
10. Verify the reference's `version.php` release, numeric version and branch against inventory before using it. An unavailable, unsafe, oversized or mismatched reference must remain explicit and must never produce a core classification.
11. Compare bounded file manifests and classify inventory candidates as exact `core`, `core-modified`, `non-core`, explicit `custom`, or `unclassified`. Exact core matches do not require plugin-level review; modified core, non-core and custom code remain scan/review targets unless target compatibility is declared.
12. Surface modified or missing source-core filenames within evidence limits without storing file contents.
13. Keep custom, modified-core, non-core and unclassified plugins on a manual-review list when target compatibility is not proven.

## Safety

- Read-only filesystem/Git inspection only.
- Core references must already exist locally; this capability does not clone, fetch, checkout or write Git metadata.
- Skip large generated/dependency trees such as `.git`, `vendor`, `node_modules`, `.venv` and moodledata.
- Do not scan the same file twice merely because both a parent and child custom path were configured.
- Do not apply language-specific compatibility rules to unrelated source languages.
- Do not treat embedded JavaScript, comments or string literals inside a `.php` file as executable PHP API usage.
- Pattern absence is not proof of full compatibility.
- A manual-review item may remain even when no known critical signature was found.

## Blocking conditions

- Configured custom code cannot be scanned/inventoried
- A known critical compatibility signature is detected in an applicable source type

## Universal rules

- Never persist secrets or full source excerpts.
- Preserve stable finding IDs so real regressions can become permanent checks.
- Keep known failures separate from unknown/manual review.
