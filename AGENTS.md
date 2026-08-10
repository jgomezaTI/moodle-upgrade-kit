# AGENTS.md

## Start here

Before making changes, read in this order:

1. `docs/CODEX_HANDOFF.md` — **current handoff, current gate, exact next step**
2. `docs/CRITICAL_PATH_STATUS.md` — concise deterministic critical-path status
3. `docs/PROJECT_CONTEXT.md` — architecture and historical context
4. the relevant `skills/<capability>/SKILL.md`
5. the related implementation under `src/moodle_upgrade/`
6. the related tests under `tests/`

Repository files are authoritative; do not depend on previous ChatGPT or Codex conversation history.

For current implementation/next-step status, `CODEX_HANDOFF.md` overrides stale historical status text in `PROJECT_CONTEXT.md`.

## Project goal

`moodle-upgrade-kit` is an auditable Moodle upgrade framework:

- skills/commands define capability contracts;
- deterministic Python performs execution;
- workflows orchestrate the critical path;
- destructive actions require machine gates plus explicit human approval;
- every run produces structured evidence under `runs/<run-id>/`;
- real regressions should become reusable deterministic checks.

The core remains generic first. Enaex-specific checks may be layered on without weakening generic safety behavior.

## Current critical path

The deterministic implementation exists:

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
→ functional QA
→ human acceptance gate
→ document
→ optional verified documentation sync
```

Rollback is separately gated:

```text
rollback gate
→ explicit rollback commands
→ post-rollback inventory/endpoints/logs/database
→ validate --mode rollback
→ document
```

The deterministic real-validation sequence is complete through baseline, backup blocking and upgrade precondition blocking. PHP compatibility now passes on 7.4.33. The next real critical-path work requires environment owners to resolve Git, backup, mutation-policy and exact-command blockers.

## Current real-validation facts

Environment:

```text
Git project root: /home/javier/proyectos/lms-enaex-espanol
Moodle root:      /home/javier/proyectos/lms-enaex-espanol/public_html
Kit repo:         /home/javier/proyectos/lms-enaex-espanol/moodle-upgrade-kit
Moodle:           3.11.18
Target:           4.1
PHP container:    lms-enaex-espanol-php-1
Observed PHP:     7.4.33
DB container:     lms-enaex-espanol-db-1
Observed MySQL:   8.0.41
```

`../autonomina` is **not part of this Moodle repository** and must not be required for this target.

Relevant custom code for this target includes `portal_v3`, `blocks/resetcompletion`, `api`, `../scripts`, `../batch` and configured `../batch/*` integration paths.

Inventory V2 is considered stable enough for this environment. After the PHP/web containers were recreated from the already configured 7.4 images, compatibility passes with PHP 7.4.33; `exif` and `max_input_vars=1000` remain warnings.

Plugin scan scope, source-core classification and grouped risk evidence are validated. Baseline now requires executed endpoint/database/log coverage. The real backup gate is explicitly blocked because no operational convention is configured. See `docs/CODEX_HANDOFF.md` for exact evidence and current blockers.

## Safety invariants

Mandatory rules:

- Inventory, compatibility, plugin analysis, baseline, endpoints, logs, database validation, backup verification and validation are read-only.
- `safety.allow_mutation` is false by default.
- Upgrade and rollback require an allowed environment, explicit human approval and machine-verifiable prerequisites.
- Human approval cannot override a critical compatibility/baseline/plugin/backup/Git gate.
- Never infer a code transition or rollback restore procedure. Environment owners must configure exact commands.
- Configured mutation commands must be argv-safe: reject shell control/interpolation and credential-bearing arguments.
- Never read/persist passwords, private keys, bearer tokens, cookies, credentialed DSNs or secrets from Moodle `config.php` into evidence.
- Database validation reads only configured SQL files, rejects mutation SQL and obtains credentials from named environment variables.
- Never claim a check passed if it did not execute. Preserve `critical`, `warning`, `info`, skipped, unknown and successful states.
- An upgrade/rollback command sequence exiting zero is not acceptance; `moodle.validate` must pass afterward.
- Do not merge PRs or execute destructive operations unless the user explicitly requests it.

## Custom-code path semantics

`custom_code.paths` is relative to `moodle.root`.

Parent traversal is allowed only when the resolved target remains inside the discovered Git project root. Absolute paths and repository escapes are rejected.

Do not assume all relevant code is a Moodle plugin. `moodle.plugins` must inspect configured arbitrary code and custom plugins with bounded scans while leaving unknown/unclassified compatibility explicit.

Overlapping scan paths must not cause duplicate file scans. When a configured parent covers a configured child, evidence should record the child under `covered_scan_paths`.

PHP-specific compatibility patterns must only run against PHP/include source types, not JavaScript libraries.

## Evidence contract

Important artifacts include:

```text
runs/<run-id>/
├── inventory-before.json
├── compatibility.json
├── plugins.json
├── code-review.json
├── baseline-before.json
├── endpoints-before.json
├── logs-before.json
├── database-before.json
├── backup.json
├── agent-state.json
├── agent-run.json
├── upgrade-plan.md
├── upgrade-result.json
├── inventory-after.json
├── endpoints-after.json
├── logs-after.json
├── database-after.json
├── validation.json
├── qa-result.json
├── rollback-plan.md
├── rollback-result.json
├── final-report.md
├── document-result.json
└── document-sync.json
```

Generated run evidence remains ignored by Git.

Current real run ID:

```text
ENAEX-311-TO-410-CRITICAL-PATH-V2
```

## Development rules

- Follow the exact next step in `docs/CODEX_HANDOFF.md`.
- Work through focused branches/PRs and do not silently include unrelated changes.
- Keep skill contracts synchronized with implementation behavior.
- Add regression coverage for behavior changes and real upgrade failures.
- Keep local environment configs under `configs/environments/*.local.yml` and out of source control.
- Never place credential values in YAML examples.
- Prefer deterministic repository code over improvised shell.
- Preserve stable check/finding IDs for auditability.
- Keep agent contracts, capability ownership, deterministic orchestration and execution gates synchronized.
- Use `muk review-code` / `speckit.moodle.review-code` as the one-command read-only entry point for reviewing YAML-configured custom-code paths; it must reuse `moodle.plugins` rather than introduce a second scanner.
- Use `muk run-agents` as the deterministic multi-step executor. It must stop at human gates, external adapter work and blockers, and must never infer approval.
- `/upgrade-moodle` may apply explicitly scoped local remediation through the active chat integration, but deterministic analysis stays read-only and evidence must be refreshed afterward.
- `/upgrade-moodle` must never stage, commit, push, branch, tag or open a PR in the inspected Moodle project. Authorized edits remain visible for human review.
- Findings-focused Drive publication must detail grouped warnings/errors and corrections; a clean accepted run receives only a concise execution record.

## Canonical checks

Before declaring code work complete:

```bash
python -m pip install -e '.[test]'
pytest
python -m moodle_upgrade.cli validate-config --config configs/example.yml
```

For the real Enaex environment, remain read-only until every remaining machine blocker is resolved and the user explicitly enables/gates mutation.

## When starting a task

1. Read `docs/CODEX_HANDOFF.md` and `docs/CRITICAL_PATH_STATUS.md`.
2. Inspect the relevant skill contract, implementation and tests.
3. Identify the exact next step on the critical path.
4. Do not broaden scope unless necessary to unblock that step.
5. Add deterministic tests for discovered defects.
6. Report exactly what was executed and what remains unverified on the real environment.
