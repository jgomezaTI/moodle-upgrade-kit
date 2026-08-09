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

Those raw counts are not trustworthy as final blocker counts because the run exposed another scanner defect: PHP-specific patterns were matching JavaScript `.split()` and `.each()` calls.

Observed analysis:

```text
104 / 119 php_ereg_removed criticals were in .js files
381 / 384 php_each_removed warnings were in .js files
```

PR #9 (`fix: scope PHP compatibility patterns to PHP files`) contains the fix and passing regression tests. At the time of this status update it is open, draft and mergeable.

## Exact next step

Do not rerun inventory or compatibility.

After PR #9 is merged by the user:

```bash
cd ~/proyectos/lms-enaex-espanol/moodle-upgrade-kit
git checkout main
git pull origin main

RUN_ID=ENAEX-311-TO-410-CRITICAL-PATH-V2
CONFIG=configs/environments/lms-enaex-espanol.local.yml

cp "runs/$RUN_ID/plugins.json" "runs/$RUN_ID/plugins-pre-pr9.json"

muk plugins \
  --config "$CONFIG" \
  --run-id "$RUN_ID"
```

Then verify:

- no PHP-only finding is attached to `.js` files;
- batch overlap deduplication remains correct;
- remaining critical findings are PHP/include candidates only;
- no secrets appear in evidence.

Any new scanner defect must become a regression test before advancing.

## Work after plugin evidence is trustworthy

In order:

```text
1. Review remaining real PHP critical candidates.
2. Improve exact core-vs-custom plugin classification/reference to reduce 105 manual-review entries.
3. Group/prioritize noisy repeated warnings such as hard-coded mdl_ prefix findings.
4. Validate baseline/endpoints/database/logs against the real environment.
5. Configure the actual local base URL and DB validation environment variables/checks.
6. Validate backup verification against real backup conventions.
7. Prove upgrade remains blocked while compatibility/Git/other machine gates fail.
8. Only then begin the agent layer.
```

Do not change PHP simply to make compatibility pass yet. Do not run a real upgrade or rollback.

## Agent layer — planned after deterministic validation

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

Agents orchestrate existing deterministic capabilities and evidence. They must not reimplement compatibility rules, invent operational commands, or bypass machine gates.

## Safety invariants

- `safety.allow_mutation: false` during current validation.
- No real upgrade/rollback.
- Human approval cannot override failed machine gates.
- Database checks remain read-only.
- No secrets in configuration/evidence/argv.
- Stable finding IDs and deterministic regression coverage are required.
