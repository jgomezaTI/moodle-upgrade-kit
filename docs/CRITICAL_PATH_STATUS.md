# Critical Path Status

_Last updated: 2026-08-09_

This file records the current deterministic critical path and what has been validated against the real Enaex environment. For the most detailed current handoff, read `docs/CODEX_HANDOFF.md`.

## Current deterministic state

Implemented:

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

Rollback is implemented as a separate explicit gated flow.

Mutation remains disabled by default and has not been enabled for the real Enaex validation.

## Real environment

```text
Git project root: /home/javier/proyectos/lms-enaex-espanol
Moodle root:      /home/javier/proyectos/lms-enaex-espanol/public_html
Kit repo:         /home/javier/proyectos/lms-enaex-espanol/moodle-upgrade-kit
Moodle:           3.11.18
Target:           4.1
PHP:              5.6.40 in lms-enaex-espanol-php-1
MySQL:            8.0.41 in lms-enaex-espanol-db-1
```

`../autonomina` is not part of this repository and is not a required custom path for this target.

Current run ID:

```text
ENAEX-311-TO-410-CRITICAL-PATH-V2
```

## Validated gates

### Inventory — validated

Real Inventory V2 validates:

- Moodle identity/version/target;
- Docker PHP runtime;
- PHP modules/settings;
- containing parent Git root;
- database runtime metadata;
- project-level and Moodle-root custom code;
- conservative plugin enumeration;
- no obvious persisted credential values.

PR #7 converted a real false plugin-enumeration defect into regression coverage.

### Compatibility — validated behavior

Current real result correctly blocks mutation:

```text
upgrade path 3.11.18 → 4.1: PASS
MySQL 8.0.41: PASS
PHP 5.6.40 for Moodle 4.1: CRITICAL
PHP 5.6.40 for current Moodle 3.11: CRITICAL
exif/sodium recommended extensions: warning
max_input_vars=1000: warning
compatible: false
```

This is expected safety behavior.

### Plugins/custom code — current gate

PR #8 is merged and real validation confirmed overlapping paths are deduplicated:

```text
../batch scanned once
../batch/coursera     covered by ../batch
../batch/edx          covered by ../batch
../batch/proofpoint   covered by ../batch
../batch/simuladores  covered by ../batch
../batch/sincronizacion covered by ../batch
```

The first post-PR8 real plugin scan reported:

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

Those raw counts exposed a scanner defect: PHP-specific patterns were matching JavaScript `.split()` and `.each()` calls.

Observed analysis:

```text
104 / 119 php_ereg_removed criticals were in .js files
381 / 384 php_each_removed warnings were in .js files
```

PR #10 (`fix: scope PHP patterns to executable regions`) is merged. The corrected real scan contains no PHP-only finding in JavaScript, comments, string literals or embedded JavaScript regions.

Commit `92729ee` on `main` implements generic source-core classification. The capability consumes a configured local Git repository/ref/tree root, verifies its Moodle identity exactly against inventory and performs bounded content comparisons. No source or target Moodle version is hard-coded.

Canonical validation after source-core classification:

```text
pytest: 53 passed (including current risk-grouping regressions)
validate-config configs/example.yml: OK
```

Real read-only validation against Enaex used official Moodle tag `v3.11.18`, commit `375a1163378f4fd5af36aa633c08c0431c9ad74b`, only as the exact source-version fixture:

```text
critical: 0
warning: 2396
risk_hit_count: 2395
plugin_count: 105
review_count: 8
scan_root_count: 12
covered_scan_path_count: 6
core: 97
core-modified: 1
non-core: 5
custom: 2
ready: true
```

The single core-modified plugin is `mod/feedback`; its changed file is `mod/feedback/complete.php`. The five non-core plugins are `blocks/messages`, `blocks/resetcompletion`, `auth/fc`, `auth/saml2` and `auth/ws`. The two explicit custom plugins are `local/portalcentral` and `local/postulacion`.

The wider deterministic scan found two executable `create_function()` uses and one executable `each()` use in `auth/saml2`. These are real warnings, not the previous source-scope false positives. Nine modified or missing core files are surfaced for review.

Evidence checks confirmed:

- no PHP-only finding in `.js` files;
- overlapping batch paths remain deduplicated;
- the configured source-core identity matches inventory exactly;
- no obvious secrets appear in `plugins.json`.

The previous plugin evidence is preserved as `plugins-pre-core-reference.json` in the same ignored run directory.

Commit `65fd731` on `main` adds derived review indexes while preserving every original finding and stable ID. Real evidence reduces the review surface from 2395 individual occurrences to 4 rule summaries and 95 rule/scope/file groups without changing any verdict:

```text
hardcoded_mdl_prefix:          2152 hits / 63 files / 6 scopes
legacy_user_contact_column:     239 hits / 28 files / 5 scopes
php_create_function_removed:      2 hits /  2 files / 1 scope
php_each_removed:                 2 hits /  2 files / 2 scopes
```

Groups use a bounded 20-line sample and explicit truncation state. Review ordering is deterministic by severity, volume and stable textual keys, and explicitly does not affect severity.

Validation confirmed:

- all 2395 `risk_hits` remain structurally identical;
- `findings` and `manual_review` remain structurally identical;
- rule and group occurrence totals both equal 2395;
- critical/warning/review/ready values are unchanged;
- no obvious secrets appear in evidence.

The pre-grouping evidence is preserved as `plugins-pre-risk-grouping.json`.

### Baseline/endpoints/database/logs — validated

The real validation exposed a false-success defect: a baseline with no configured endpoint, database or log checks could report `complete: true`. Regression coverage now requires configured and actually executed coverage for all three check classes.

Additional real-environment hardening includes:

- read-only endpoint methods only, with mutating methods rejected before a request;
- TLS verification by default, with an explicit evidence-bearing exception allowed only outside production for the local self-signed certificate;
- bounded Docker stdout/stderr log sources using argv-safe container names and no persisted raw log text;
- read-only database checks that can resolve validated environment-variable names inside the DB container without extracting or persisting their credential values;
- explicit configured/executed/passed/completeness metadata for standalone checks and baseline evidence.

Real evidence under `ENAEX-311-TO-410-CRITICAL-PATH-V2` now reports:

```text
endpoints configured/executed: 2 / 2
database configured/executed: 1 / 1
log sources configured/executed/readable: 3 / 3 / 3
critical/warning/info: 0 / 0 / 0
complete: true
```

Both HTTPS endpoints returned 200 with the staging-only self-signed TLS exception recorded as `tls_verified: false`. The DB health `SELECT 1` passed. All three Docker log sources were readable with no configured critical/warning signatures. Secret and raw-log field scans were clean.

### Backup verification — validated blocker

The real target has no configured operational backup roots or component identity rules. Files in Moodle source/tests with backup-like names are not rollback evidence and were not inferred as such.

The empty-config false-opacity defect was converted into regression coverage. The real read-only backup run exits 2 and reports:

```text
BACKUP_LOCATIONS_NOT_CONFIGURED
BACKUP_COMPONENTS_NOT_CONFIGURED
locations configured/accessible: 0 / 0
components required/verified: 0 / 0
verified: false
```

No backup was created, modified or restored.

### Upgrade machine-gate block — validated without mutation

The mutation precondition evaluator consumed the existing real evidence with approval deliberately true and returned:

```text
MUTATION_DISABLED
GIT_NOT_CLEAN
COMPATIBILITY_NOT_PASSED
BACKUP_NOT_VERIFIED
```

No upgrade CLI or configured upgrade sequence was run. Regression coverage uses a runner that raises if called and confirms human approval cannot bypass these failed machine gates.

## Exact next step

Do not rerun inventory or compatibility.

1. Keep the real Enaex run blocked until environment owners resolve the recorded PHP, Git, backup and exact-command prerequisites.
2. Rerun the read-only evidence and agent decision only after those external conditions change.

## Deterministic validation sequence completed

In order:

```text
1. Baseline/endpoints/database/logs validated read-only.
2. Backup gate validated as an explicit blocker because no real backup convention is configured.
3. Upgrade machine gates proven to block even when human approval input is true.
4. The Spec Kit-style agent layer is implemented and validates those same gates.
```

Do not change PHP simply to make compatibility pass yet. Do not run a real upgrade or rollback.

## Agent layer — implemented

Implemented logical agents:

```text
upgrade-orchestrator
discovery-agent
compatibility-agent
baseline-agent
upgrade-agent
rollback-agent
documentation-agent
```

The machine-validated registry gives every deterministic capability exactly one owner. The orchestrator is delegate-only; upgrade and rollback have exclusive separate owners. Decisions contain at most one `executes_automatically: false` action and reuse the same upgrade/rollback precondition evaluators as execution.

The real agent decision is blocked by `MUTATION_DISABLED`, `GIT_NOT_CLEAN`, `COMPATIBILITY_NOT_PASSED`, `BACKUP_NOT_VERIFIED` and missing configured upgrade steps. This is expected and no destructive command executed.

Framework `0.2.0` canonical validation passed with 77 tests, editable installation, example/local config validation and a real read-only orchestrator run. `agent-state.json` contains no obvious credential/raw-log fields and reports `next_action: null`.

## Safety invariants

- `safety.allow_mutation: false` during current validation.
- No real upgrade/rollback.
- Human approval cannot override failed machine gates.
- Database checks remain read-only.
- No secrets in configuration/evidence/argv.
- Stable finding IDs and deterministic regression coverage are required.
