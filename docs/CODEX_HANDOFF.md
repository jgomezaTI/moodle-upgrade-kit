# Codex CLI Handoff

_Last updated: 2026-08-09_

This document is the shortest authoritative handoff for continuing `moodle-upgrade-kit` from a fresh Codex CLI session.

Read this after `AGENTS.md` and before making changes.

## Current goal

Finish validating the deterministic critical path against the real Enaex WSL/Docker environment **before** implementing the agent layer or enabling mutation.

Do not broaden scope. The current gate is `moodle.plugins`.

## Real environment

```text
Git project root: /home/javier/proyectos/lms-enaex-espanol
Moodle root:      /home/javier/proyectos/lms-enaex-espanol/public_html
Kit repo:         /home/javier/proyectos/lms-enaex-espanol/moodle-upgrade-kit
```

Observed:

```text
Moodle: 3.11.18
Target: 4.1
PHP container: lms-enaex-espanol-php-1
PHP: 5.6.40
DB container: lms-enaex-espanol-db-1
MySQL image/version: 8.0.41
Git branch during validation: update
Git dirty during validation: true
```

`../autonomina` is **not part of this Moodle repository** and must not be required for this target.

Relevant configured custom code includes:

```text
portal_v3
blocks/resetcompletion
api
../scripts
../batch
../batch/coursera
../batch/edx
../batch/proofpoint
../batch/simuladores
../batch/sincronizacion
```

## Critical path implementation status

The deterministic critical path is implemented:

```text
inventory before
→ compatibility
→ plugins/custom code
→ baseline
→ backup verification
→ human gate
→ upgrade
→ inventory/endpoints/logs/database after
→ validate
→ human acceptance gate
→ document
```

Rollback is also implemented as an explicit, separately gated path.

Mutation remains disabled by default. Do not enable it during current validation work.

## Real validation already completed

### Inventory

Inventory V2 is considered stable enough for this environment.

Validated behavior:

- detects Moodle 3.11.18 and target 4.1;
- detects parent Git repository above `public_html`;
- inspects the real Docker PHP runtime;
- captures PHP version/modules/settings;
- detects MySQL runtime metadata;
- inventories Moodle-root and project-level custom code;
- does not persist obvious credential values;
- filters non-plugin directories that lack `version.php` unless explicitly configured custom.

A real inventory defect where internal directories such as `blocks/classes` and `auth/tests` were treated as plugins was converted into a regression fix in PR #7.

### Compatibility

The real compatibility run behaves correctly.

Expected/current result:

```text
upgrade path 3.11.18 → 4.1: PASS
MySQL 8.0.41: PASS
PHP 5.6.40 for target 4.1: CRITICAL BLOCKER
PHP 5.6.40 for current Moodle 3.11: CRITICAL BLOCKER
recommended extensions exif/sodium: warning
max_input_vars=1000: warning
compatible: false
```

The compatibility blocker is a successful safety outcome. Do not change PHP yet merely to make the check green.

## Plugin/custom-code validation history

### PR #8

PR #8 (`fix: dedupe overlapping custom code scan paths`) is merged.

Real validation confirmed that when both `../batch` and its children are configured, the scanner uses `../batch` once and records child paths under `covered_scan_paths`.

Observed post-PR #8 scan roots:

```text
portal_v3
blocks/resetcompletion
api
../scripts
../batch
local/portalcentral
local/postulacion
```

Covered child paths:

```text
../batch/coursera
../batch/edx
../batch/proofpoint
../batch/simuladores
../batch/sincronizacion
```

### First real plugins result after PR #8

Run ID in use:

```text
ENAEX-311-TO-410-CRITICAL-PATH-V2
```

The first `plugins.json` after PR #8 reported:

```text
critical: 119
warning: 2772
risk_hit_count: 2891
plugin_count: 105
review_count: 105
scan_root_count: 7
covered_scan_path_count: 5
ready: false
```

Do **not** treat those raw counts as 119 confirmed PHP blockers.

Analysis showed the scanner was applying PHP-specific regexes to JavaScript:

- 104 of 119 `php_ereg_removed` critical hits were in `.js` files;
- 381 of 384 `php_each_removed` warnings were in `.js` files;
- Bootstrap, jQuery, Select2 and other JS libraries were therefore false positives.

The remaining PHP critical candidates before fixing file scoping were approximately 15 hits across about 10 PHP files, including code under `portal_v3` such as:

```text
adm_seccion.php
complete_modules.php
delete_attempts.php
adm_escuela.php
app_adm/index.php
app_adm/index_.php
app_adm/courses/groups_admin.php
app_adm/access/acl_admin.php
app_adm/actions/manual_grading.php
lib/PHPExcel/Shared/PCLZip/pclzip.lib.php
```

These are candidates only until the corrected scanner is rerun.

The same run also showed high-volume warnings such as hard-coded `mdl_` prefixes and legacy user-contact fields. Those counts should eventually be grouped/prioritized rather than treated as thousands of independent tasks.

## PHP pattern-scope fixes — merged

PR #10 is merged into `main`:

```text
fix: scope PHP patterns to executable regions
merge commit: ce7d979
```

Validated outcomes:

- PHP-only rules apply to executable PHP regions in `.php` / `.inc`;
- embedded HTML/JavaScript, comments and string literals remain masked;
- SQL/schema coupling rules remain applicable to PHP/include/SQL;
- `php_ereg_removed` and `php_split_removed` retain distinct stable IDs;
- the real rerun reported no PHP-only findings in `.js` files;
- the remaining real PHP warning in the previously scanned roots was `php_each_removed` in `portal_v3/lib/fpdi/fpdi.php:563`.

## Generic source-core reference — published on main

Published commit:

```text
92729ee feat: classify plugins against verified source core
```

The implementation adds a generic, local and read-only source-core reference contract. It does not contain an Enaex or Moodle-version-specific default.

Implemented behavior:

- accepts a local Git repository, ref and tree root;
- verifies the reference `version.php` release, numeric version and branch against inventory;
- compares bounded content manifests;
- classifies candidates as `core`, `core-modified`, `non-core`, explicit `custom` or `unclassified`;
- scans non-core and core-modified components in addition to explicit custom code;
- never clones, fetches, checks out or writes Git metadata;
- preserves the previous `core_reference_ref` shorthand.

Real read-only validation used the official Moodle `v3.11.18` commit only as the Enaex source-version fixture:

```text
official commit: 375a1163378f4fd5af36aa633c08c0431c9ad74b
reference files: 22335
core: 97
core-modified: 1
non-core: 5
custom: 2
manual review: 8 (previously 105)
critical: 0
warning: 2396
risk hits: 2395
```

The core-modified plugin is `mod/feedback`, with `mod/feedback/complete.php` changed. Five non-core components are `blocks/messages`, `blocks/resetcompletion`, `auth/fc`, `auth/saml2` and `auth/ws`.

The expanded scan found real executable warnings in `auth/saml2`: two `create_function()` uses and one `each()` use. These are not JavaScript/comment false positives. The complete source-core comparison reports nine modified or missing core files.

The prior evidence is preserved as:

```text
runs/ENAEX-311-TO-410-CRITICAL-PATH-V2/plugins-pre-core-reference.json
```

## Deterministic risk grouping — published

Published on `main`:

```text
65fd731 feat: group plugin risk evidence for review
```

The implementation adds derived review views without modifying, deduplicating or downgrading individual risk evidence:

- summaries by stable rule ID and severity;
- groups by rule, severity, scan scope and file;
- deterministic review order by severity, occurrence count and stable textual keys;
- bounded line samples of 20 entries with explicit truncation evidence;
- explicit evidence that review rank does not affect severity.

Canonical validation at publication:

```text
pytest: 53 passed
validate-config configs/example.yml: OK
```

Real read-only evidence now reports:

```text
risk hits preserved: 2395
risk rules: 4
risk groups: 95
group/rule occurrence totals: 2395
critical/warning/review/ready: unchanged
```

Rule summaries:

```text
hardcoded_mdl_prefix:          2152 hits / 63 files / 6 scopes
legacy_user_contact_column:     239 hits / 28 files / 5 scopes
php_create_function_removed:      2 hits /  2 files / 1 scope
php_each_removed:                 2 hits /  2 files / 2 scopes
```

The evidence before grouping is preserved as:

```text
runs/ENAEX-311-TO-410-CRITICAL-PATH-V2/plugins-pre-risk-grouping.json
```

Verification confirmed `risk_hits`, `findings` and `manual_review` are structurally identical before and after grouping, both derived occurrence totals equal 2395 and no obvious secret appears in evidence.

## Baseline/endpoints/database/logs — validated read-only

The real Enaex baseline exposed and converted these defects into regression coverage:

- an empty baseline previously could report `complete: true` without executing endpoint, database or log checks;
- endpoint configuration did not restrict mutating HTTP methods or record execution/TLS state;
- the local self-signed HTTPS endpoint needed an explicit non-production-only TLS verification exception;
- the real containers expose application logs through bounded Docker stdout/stderr rather than mounted log files;
- database validation could not safely resolve credential values that exist only inside the database container.

The corrected capability now requires actual coverage for all three baseline classes, rejects mutating HTTP methods before execution, records unverified TLS explicitly, reads Docker logs with a bounded argv-safe command without persisting raw text, and supports resolving validated environment-variable names inside a trusted DB container without extracting their values.

Real read-only evidence under `ENAEX-311-TO-410-CRITICAL-PATH-V2` reports:

```text
endpoints configured/executed: 2 / 2 (both HTTP 200)
database configured/executed: 1 / 1 (SELECT 1 health check passed)
log sources configured/executed/readable: 3 / 3 / 3
baseline critical/warning/info: 0 / 0 / 0
baseline complete: true
TLS verified: false (explicit staging exception for local self-signed HTTPS)
```

The four generated artifacts contain no obvious secret matches and no raw-log fields. Inventory, compatibility and plugin analysis were not rerun.

## Exact next step

1. Publish the focused baseline/endpoints/database/logs hardening and its regression coverage.
2. Validate backup verification against the real backup conventions without creating, restoring or mutating backups.
3. Prove the upgrade path remains blocked by machine gates without executing a real upgrade command sequence.
4. Only after those deterministic gates are stable, design and implement the Spec Kit-style agent layer.

Do not change PHP merely to make compatibility green. Do not run upgrade, rollback or implement agents yet.

## Agent layer — future work, not current gate

The intended agent layer should orchestrate deterministic capabilities rather than reimplement their logic.

Planned logical agents:

```text
upgrade-orchestrator
discovery-agent
compatibility-agent
baseline-agent
upgrade-agent
rollback-agent
documentation-agent
```

The orchestrator should consume structured run evidence and select the next allowed capability. It must not invent compatibility verdicts or bypass machine gates.

Agent work starts only after the deterministic read-only layer has completed the remaining real validation gates.

## Safety invariants

- `safety.allow_mutation` remains false during current work.
- Do not run real upgrade/rollback commands.
- Human approval never overrides failed machine gates.
- Do not persist credentials in YAML, argv, output or evidence.
- Database validation remains read-only.
- Preserve stable finding IDs.
- Every real scanner/runtime defect should become a regression test.
- Do not merge PRs unless the user explicitly asks.

## Recommended first Codex CLI prompt

```text
Read AGENTS.md, docs/CODEX_HANDOFF.md, docs/CRITICAL_PATH_STATUS.md,
and skills/moodle.plugins/SKILL.md first.

Then inspect the current Git branch, main, the deterministic risk-grouping
development item, and the evidence under
runs/ENAEX-311-TO-410-CRITICAL-PATH-V2 if present.

Summarize what is already validated and identify the exact next step on the
critical path. Do not modify anything yet. Do not broaden scope. Do not run
upgrade or rollback commands.
```
