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

## Current PR — PR #9

PR #9 is the current development item:

```text
fix: scope PHP compatibility patterns to PHP files
branch: agent/php-pattern-file-scope
```

At the time of this handoff:

- PR is open and draft;
- PR is mergeable;
- GitHub Actions pass;
- PHP-only rules are scoped to `.php` / `.inc`;
- SQL/schema coupling rules remain applicable to PHP/include/SQL;
- the previous combined `ereg|split` detector is separated into stable `php_ereg_removed` and `php_split_removed` findings;
- regression tests prove JavaScript `.split()` / `.each()` do not produce PHP compatibility findings while real PHP calls still do.

Do not duplicate this work in another branch.

## Exact next step

1. Inspect PR #9 and its CI.
2. If the human user has already merged it, pull `main`; otherwise do not merge without explicit user instruction.
3. Preserve the current pre-PR9 result if it still exists:

```bash
RUN_ID=ENAEX-311-TO-410-CRITICAL-PATH-V2
cp "runs/$RUN_ID/plugins.json" "runs/$RUN_ID/plugins-pre-pr9.json"
```

4. Rerun only the plugin gate:

```bash
CONFIG=configs/environments/lms-enaex-espanol.local.yml
RUN_ID=ENAEX-311-TO-410-CRITICAL-PATH-V2

muk plugins \
  --config "$CONFIG" \
  --run-id "$RUN_ID"
```

5. Validate the corrected evidence:
   - no PHP-only findings in `.js` files;
   - overlapping batch paths still deduplicated;
   - remaining criticals are PHP/include candidates only;
   - no secrets appear in evidence.
6. Turn any new scanner defect into a deterministic regression test before advancing.

## After the corrected plugin rerun

The next work order is:

```text
A. Review remaining real PHP critical candidates.
B. Improve core-vs-custom plugin classification/reference so 105 plugins are not all manual-review noise.
C. Decide whether high-volume warnings should be grouped by file/rule for usable evidence.
D. Once `moodle.plugins` evidence is trustworthy, move to baseline/database/logs.
E. Configure the real base URL and DB validation environment variables/checks.
F. Validate backup verification against the real environment.
G. Prove `muk upgrade --approved` remains blocked while compatibility is false / Git dirty / other gates fail.
H. Only after deterministic real-environment gates are stable, implement the agent layer.
```

Do not jump directly to changing PHP, running an upgrade, rollback, or implementing agents.

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

Then inspect the current Git branch, main, PR #9 if available locally/remotely,
and the evidence under runs/ENAEX-311-TO-410-CRITICAL-PATH-V2 if present.

Summarize what is already validated and identify the exact next step on the
critical path. Do not modify anything yet. Do not broaden scope. Do not run
upgrade or rollback commands.
```
