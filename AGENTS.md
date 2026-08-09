# AGENTS.md

## Start here

Before making changes, read in this order:

1. `docs/PROJECT_CONTEXT.md` for architecture/history
2. `docs/CRITICAL_PATH_STATUS.md` for the current implementation state and exact next step
3. the relevant `skills/<capability>/SKILL.md`
4. the related implementation under `src/moodle_upgrade/`
5. the related tests under `tests/`

Repository files are authoritative; do not depend on previous ChatGPT or Codex conversation history. When older status text in `PROJECT_CONTEXT.md` conflicts with `CRITICAL_PATH_STATUS.md`, use `CRITICAL_PATH_STATUS.md` for current implementation/next-step status.

## Project goal

`moodle-upgrade-kit` is an auditable Moodle upgrade framework:

- skills/commands define capability contracts;
- deterministic Python performs execution;
- workflows orchestrate the critical path;
- destructive actions require machine gates plus explicit human approval;
- every run produces structured evidence under `runs/<run-id>/`;
- real regressions should become reusable deterministic checks.

The core remains generic first. Enaex-specific checks may be layered on without weakening generic safety behavior.

## Current implementation state

The guarded executable critical path exists on the active development branch:

```text
inventory before
→ compatibility
→ plugins/custom code
→ baseline (endpoints + database + logs + cron evidence)
→ backup verification
→ human gate
→ upgrade
→ inventory/endpoints/logs/database after
→ validate
→ human acceptance gate
→ document
```

Rollback is separately gated:

```text
rollback gate
→ explicit rollback commands
→ post-rollback inventory/endpoints/logs/database
→ validate --mode rollback
→ document
```

The next critical task is **real read-only validation against the Enaex WSL/Docker environment**. Do not broaden scope before that evidence is reviewed.

## Safety invariants

Mandatory rules:

- Inventory, compatibility, plugin analysis, baseline, endpoints, logs, database validation, backup verification and validation are read-only.
- `safety.allow_mutation` is false by default.
- Upgrade and rollback require an allowed environment, explicit human approval and their machine-verifiable prerequisites.
- Human approval cannot override a critical compatibility/baseline/plugin/backup/Git gate.
- Never infer a code transition or rollback restore procedure. Environment owners must configure exact commands.
- Configured mutation commands must be argv-safe: reject shell control/interpolation and credential-bearing arguments.
- Never read/persist passwords, private keys, bearer tokens, cookies, credentialed DSNs or secrets from Moodle `config.php` into evidence.
- Database validation reads only configured SQL files, rejects mutation SQL and obtains credentials from named environment variables.
- Never claim success for a check that did not execute. Preserve `critical`, `warning`, `info`, skipped, unknown and successful states.
- An upgrade/rollback command sequence exiting zero is not acceptance; `moodle.validate` must pass afterward.
- Do not merge PRs or execute destructive operations unless the user explicitly requests it.

## Real validation environment

Current real target (do not generalize as defaults):

```text
Git project root: /home/javier/proyectos/lms-enaex-espanol
Moodle root:      /home/javier/proyectos/lms-enaex-espanol/public_html
Kit repo:         /home/javier/proyectos/lms-enaex-espanol/moodle-upgrade-kit
```

- Current Moodle: `3.11.18` / branch `311`
- Target Moodle: `4.1`
- PHP container: `lms-enaex-espanol-php-1`
- Observed PHP: `5.6.40`
- Container Moodle root: `/var/www/html`
- Container moodledata: `/var/www/moodledata`
- DB container: `lms-enaex-espanol-db-1`
- Observed DB image: `mysql:8.0.41`
- Arbitrary custom code includes `public_html/portal_v3` and project-level paths such as `../autonomina`.

Expected compatibility behavior for this target: the observed PHP 5.6.40 must block Moodle 3.11 → 4.1 before any mutation path can execute.

## Moodle root, Git root and custom code

Git discovery must work when `.git` is above `moodle.root`.

`custom_code.paths` is relative to `moodle.root`:

```yaml
custom_code:
  paths:
    - portal_v3
    - ../autonomina
```

Parent traversal is allowed only when the resolved path remains inside the discovered project Git root. Absolute paths and repository escapes are rejected.

Do not assume all relevant code is a Moodle plugin. `moodle.plugins` must inspect configured arbitrary code and custom plugins with bounded scans while leaving unknown/unclassified compatibility explicit.

## Evidence contract

Important artifacts include:

```text
runs/<run-id>/
├── inventory-before.json
├── compatibility.json
├── plugins.json
├── baseline-before.json
├── endpoints-before.json
├── logs-before.json
├── database-before.json
├── backup.json
├── upgrade-plan.md
├── upgrade-result.json
├── inventory-after.json
├── endpoints-after.json
├── logs-after.json
├── database-after.json
├── validation.json
├── rollback-plan.md
├── rollback-result.json
├── final-report.md
└── document-result.json
```

Generated run evidence remains ignored by Git.

## Development rules

- Work through focused branches/PRs and do not silently include unrelated changes.
- Keep skill contracts synchronized with implementation behavior.
- Add regression coverage for behavior changes and real upgrade failures.
- Keep local environment configs under `configs/environments/*.local.yml` and out of source control.
- Never place credential values in YAML examples.
- Prefer deterministic repository code over improvised shell.
- Preserve stable check/finding IDs for auditability.

## Canonical checks

Before declaring code work complete:

```bash
python -m pip install -e '.[test]'
pytest
python -m moodle_upgrade.cli validate-config --config configs/example.yml
```

For the real Enaex environment, remain read-only until compatibility blockers are resolved and the user explicitly enables/gates mutation.

## When starting a task

1. Read `docs/PROJECT_CONTEXT.md`, then `docs/CRITICAL_PATH_STATUS.md`.
2. Inspect the relevant skill contract, implementation and tests.
3. Identify the exact next step on the critical path.
4. Do not broaden scope unless it is necessary to unblock that step.
5. Add deterministic tests for discovered defects.
6. Report exactly what was executed and what remains unverified on the real environment.
