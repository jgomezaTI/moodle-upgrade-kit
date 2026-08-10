---
name: moodle.plugins
description: Review Moodle plugins and arbitrary project code for known upgrade risks while keeping uncertain compatibility explicit.
effect: read-only
version: 0.3.2
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
- Optional `runs/<run-id>/code-review.json` queue for the compatibility agent
- Plugin classifications, bounded source-scan findings and manual-review candidates
- Derived per-rule summaries and per-rule/scope/file review groups while preserving every individual risk hit
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
9. Preserve every individual risk hit and stable rule ID. Add derived summaries by rule and review groups by rule, severity, scan scope and file; never replace or deduplicate the underlying evidence.
10. Order derived review groups deterministically by severity and occurrence count, followed by stable textual keys. This order prioritizes human/agent review only and must never change a finding's severity or compatibility verdict.
11. Keep group line samples bounded and record whether they were truncated. Do not store source excerpts.
12. Optionally consume a local Git source-core reference described by repository, ref and tree root. Never fetch or mutate repositories as part of this capability.
13. Verify the reference's `version.php` release, numeric version and branch against inventory before using it. An unavailable, unsafe, oversized or mismatched reference must remain explicit and must never produce a core classification.
14. Compare bounded file manifests and classify inventory candidates as exact `core`, `core-modified`, `non-core`, explicit `custom`, or `unclassified`. Exact core matches do not require plugin-level review; modified core, non-core and custom code remain scan/review targets unless target compatibility is declared.
15. Surface modified or missing source-core filenames within evidence limits without storing file contents.
16. Keep custom, modified-core, non-core and unclassified plugins on a manual-review list when target compatibility is not proven.
17. The convenience review command may create missing inventory evidence, invoke this same analyzer once, and derive a bounded `code-review.json` queue. It must not duplicate scanner rules, persist source contents or modify inspected code.

## Safety

- Read-only filesystem/Git inspection only.
- Core references must already exist locally; this capability does not clone, fetch, checkout or write Git metadata.
- Skip large generated/dependency trees such as `.git`, `vendor`, `node_modules`, `.venv` and moodledata.
- Do not scan the same file twice merely because both a parent and child custom path were configured.
- Do not apply language-specific compatibility rules to unrelated source languages.
- Do not treat embedded JavaScript, comments or string literals inside a `.php` file as executable PHP API usage.
- Pattern absence is not proof of full compatibility.
- Review grouping must not hide, discard or downgrade individual findings.
- A manual-review item may remain even when no known critical signature was found.

## Blocking conditions

- Configured custom code cannot be scanned/inventoried
- A known critical compatibility signature is detected in an applicable source type

## Universal rules

- Never persist secrets or full source excerpts.
- Preserve stable finding IDs so real regressions can become permanent checks.
- Keep known failures separate from unknown/manual review.
