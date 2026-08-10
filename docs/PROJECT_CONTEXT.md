# Moodle Upgrade Kit — Project Context

_Last updated: 2026-08-09_

This document is the persistent handoff context for developers and coding agents working on `moodle-upgrade-kit`. It captures the architectural intent, current implementation status, real test environment, safety rules, and the next development steps without depending on any specific ChatGPT or Codex conversation history.

## 1. Project goal

`moodle-upgrade-kit` is an auditable automation framework for Moodle upgrades.

The long-term goal is to make Moodle upgrades safer and increasingly automated while preserving explicit human control for destructive actions.

The project is inspired by Spec Kit-style workflows:

- capability contracts are versioned;
- deterministic code performs execution;
- workflows orchestrate capabilities;
- destructive steps require human gates;
- every run produces evidence;
- regressions discovered during real upgrades should become permanent reusable checks.

The framework should remain generic first. Enaex-specific checks and adapters can be layered on later without turning the core into an Enaex-only solution.

## 2. Core design principles

1. **Read-only discovery first.** Inventory, baseline, compatibility, plugin analysis, endpoints, logs, and database checks should be developed and validated before enabling upgrade or rollback mutation paths.
2. **Deterministic execution over improvised shell.** Skills and commands describe intent; Python/scripts implement repeatable behavior.
3. **Evidence for every run.** Outputs belong under `runs/<run-id>/` and should be suitable for before/after comparison.
4. **Human gates for destructive actions.** Upgrade and rollback must not execute silently.
5. **Never claim a check passed if it was not executed.** Unknown, skipped, warning, and failure states must remain distinguishable.
6. **Never persist secrets.** Passwords, private keys, bearer tokens, cookies, credentialed DSNs, and Moodle `config.php` secrets must not appear in generated evidence.
7. **Real regressions become permanent checks.** Bugs found during upgrade projects should be converted into deterministic tests/checks when practical.
8. **Do not assume all relevant code is a Moodle plugin.** Legacy applications, portals, integrations, batch jobs, and scripts coupled to Moodle are also part of upgrade compatibility.

## 3. Capabilities

The initial capability set is:

1. `moodle.inventory`
2. `moodle.baseline`
3. `moodle.compatibility`
4. `moodle.plugins`
5. `moodle.endpoints`
6. `moodle.logs`
7. `moodle.database`
8. `moodle.backup`
9. `moodle.upgrade`
10. `moodle.validate`
11. `moodle.rollback`
12. `moodle.document`
13. `moodle.qa`

The agent registry also exposes `moodle.document.sync` as an optional external adapter capability. Its connector work is performed by the active chat integration and its result is machine-validated before completion.

The intended high-level upgrade flow is:

```text
inventory
→ baseline
→ compatibility
→ plugins
→ backup
→ human gate
→ upgrade
→ post-upgrade endpoints/logs/database
→ validate
→ functional QA
→ acceptance human gate
→ document
→ optional verified external documentation sync
```

Rollback flow:

```text
rollback-review human gate
→ rollback
→ validate
→ document
```

## 4. Repository architecture

Current structure includes:

```text
moodle-upgrade-kit/
├── .agents/plugins/
├── agents/
├── commands/
├── configs/
├── docs/
├── skills/
├── plugins/moodle-upgrade-kit/
├── sql/checks/
├── src/moodle_upgrade/
├── tests/
├── workflows/
└── runs/
```

Responsibilities:

- `skills/`: capability contracts and behavioral rules.
- `agents/`: portable role, capability-ownership and delegation contracts.
- `plugins/moodle-upgrade-kit/`: installable Codex chat entry point for `/upgrade-moodle`.
- `commands/`: Spec Kit-compatible command descriptions.
- `src/moodle_upgrade/`: deterministic Python implementation.
- `workflows/`: orchestration and human gates.
- `tests/`: deterministic regression coverage.
- `configs/`: examples and local environment configuration patterns.
- `runs/`: generated evidence; run artifacts are not source code and should remain ignored except placeholders.
- `docs/`: human-facing architecture, rules, and project context.

The chat integration may apply a user-approved local remediation and rerun the deterministic checks, but it never creates or publishes a Git commit. External documentation defaults to findings-focused output: detailed grouped issues when present and a concise record for a clean accepted upgrade.

## 5. Safety model

The framework currently assumes:

```yaml
safety:
  allow_mutation: false
  require_environment: staging
  require_clean_git: true
  require_backup_check: true
  require_human_gate: true
```

Read-only capabilities must not:

- execute Moodle upgrade commands;
- enable maintenance mode;
- execute rollback actions;
- modify the database;
- run Moodle cron merely for inspection;
- read credentials from `config.php` into evidence;
- execute arbitrary shell strings supplied by configuration.

Docker inspection commands should be passed as argument vectors rather than shell-interpolated strings.

## 6. Real development environment

The first real target used to validate the kit is the Enaex Spanish LMS project running under WSL + Docker.

### Host layout

```text
/home/javier/proyectos/lms-enaex-espanol/
├── .git/
├── public_html/
│   ├── Moodle source
│   ├── portal_v3/
│   └── moodledata/
├── autonomina/            # example project-level custom code outside public_html
└── moodle-upgrade-kit/
```

Important: `moodle-upgrade-kit` is a separate repository used to inspect the LMS project. The LMS project itself has its Git root above `public_html`.

### Docker containers observed

```text
lms-enaex-espanol-web-1        nginx
lms-enaex-espanol-php-1        PHP runtime
lms-enaex-espanol-db-1         MySQL
lms-enaex-espanol-phpmyadmin-1 phpMyAdmin
```

Observed images/runtime:

```text
PHP image: registry.local.sirdar.cl/php-moodle:5.6
Nginx image: registry.local.sirdar.cl/nginx-moodle:5.6
Database image: mysql:8.0.41
```

### Bind mounts

PHP container:

```text
/home/javier/proyectos/lms-enaex-espanol/public_html
→ /var/www/html

/home/javier/proyectos/lms-enaex-espanol/public_html/moodledata
→ /var/www/moodledata
```

### Versions observed during the first real inventory

```text
Current Moodle: 3.11.18
Moodle branch: 311
Upgrade target: 4.1
PHP runtime: 7.4.33 (refreshed after the original 5.6.40 validation)
Database: MySQL 8.0.41 container image
```

The PHP version is intentionally recorded as inventory evidence; compatibility verdicts belong to `moodle.compatibility`, not `moodle.inventory`.

## 7. Local environment configuration pattern

Local target configuration should live in a gitignored file such as:

```text
configs/environments/lms-enaex-espanol.local.yml
```

Representative configuration:

```yaml
project:
  name: lms-enaex-espanol
  environment: staging
  timezone: America/Santiago

moodle:
  root: /home/javier/proyectos/lms-enaex-espanol/public_html
  moodledata: /home/javier/proyectos/lms-enaex-espanol/public_html/moodledata
  base_url: https://localhost
  target_version: "4.1"
  cron_command: "php admin/cli/cron.php"

runtime:
  type: docker
  container: lms-enaex-espanol-php-1
  moodle_root: /var/www/html
  moodledata: /var/www/moodledata

safety:
  allow_mutation: false
  require_environment: staging
  require_clean_git: true
  require_backup_check: true
  require_human_gate: true
  max_backup_age_hours: 24

inventory:
  min_free_gb: 5

plugins:
  custom_roots:
    - local
    - report
    - blocks
    - mod
    - auth
  custom_paths: []

custom_code:
  paths:
    - portal_v3
    - ../autonomina
  auto_detect_top_level: true
  max_files_per_path: 50000

database:
  driver: mysql
  runtime_container: lms-enaex-espanol-db-1

backup:
  paths: []
```

`base_url` should be changed to the actual local URL when endpoint validation begins.

## 8. Custom code path semantics

`custom_code.paths` is resolved relative to `moodle.root`.

Examples with:

```text
moodle.root = /home/javier/proyectos/lms-enaex-espanol/public_html
```

### Moodle-root custom code

```yaml
custom_code:
  paths:
    - portal_v3
```

resolves to:

```text
/home/javier/proyectos/lms-enaex-espanol/public_html/portal_v3
```

### Project-level sibling code

```yaml
custom_code:
  paths:
    - ../autonomina
```

resolves to:

```text
/home/javier/proyectos/lms-enaex-espanol/autonomina
```

Parent-relative `..` paths are allowed only when the resolved target remains inside the Git repository containing `moodle.root`.

Absolute paths remain rejected. Traversal escaping the Git repository root must also be rejected.

Inventory records metadata only for custom code; source-code compatibility inspection belongs to later compatibility analysis.

## 9. Plugin classification rules

Inventory deliberately uses conservative classification.

- `local/*` is treated as custom/project-specific.
- paths explicitly listed in `plugins.custom_paths` are treated as custom.
- plugins under roots such as `mod`, `auth`, `blocks`, or `report` are otherwise `unclassified` during inventory.
- inventory must not claim a plugin is Moodle core merely because its directory name resembles a standard plugin.
- exact core-vs-custom comparison belongs to `moodle.compatibility` or `moodle.plugins`, using the exact current Moodle release as reference.

Plugin metadata currently includes information such as:

- component path;
- `$plugin->component` when available;
- `$plugin->version`;
- `$plugin->requires`;
- presence of `version.php`;
- conservative classification/reason.

## 10. `moodle.inventory` current implementation

`moodle.inventory` is the first executable capability and is already implemented.

Current behavior includes:

- Moodle root marker validation (`version.php`, `config.php`, `admin/cli`);
- Moodle release/version/branch parsing from `version.php`;
- Docker runtime target support;
- Docker container running-state and image inspection;
- PHP CLI version from the actual runtime container;
- loaded PHP module inventory;
- Git repository discovery using `git rev-parse --show-toplevel`, including repositories whose `.git` directory is above `moodle.root`;
- Git branch, HEAD and dirty state;
- disk usage for Moodle root, moodledata and configured backup paths;
- plugin enumeration and metadata;
- conservative plugin custom/unclassified classification;
- configured arbitrary custom-code metadata;
- automatic non-core top-level directory candidates;
- optional database container metadata and database server binary version;
- cron configuration and `admin/cli/cron.php` presence without executing cron;
- structured findings and summary;
- evidence written to `runs/<run-id>/inventory.json`.

Example command:

```bash
muk inventory \
  --config configs/environments/lms-enaex-espanol.local.yml \
  --run-id ENAEX-311-TO-410-INVENTORY-V2
```

## 11. First real inventory lessons

The first real run against the Enaex environment proved that the kit could correctly identify the Moodle instance and runtime, but also exposed several gaps that were then hardened:

1. `public_html` is inside a larger Git repository, so checking only `public_html/.git` was incorrect.
2. Counting every directory below plugin roots as custom was not useful; classification needed to be conservative.
3. custom application code such as `portal_v3` must be inventoried even though it is not a Moodle plugin.
4. project-level code may live outside `public_html`, so explicit `../...` custom paths are needed.
5. PHP/runtime evidence must come from the Docker container rather than WSL host PHP.
6. database runtime metadata can be gathered without database credentials or SQL queries.

These lessons are examples of the project's core principle: real upgrade discoveries should improve the reusable framework.

## 12. Pull request history

As of 2026-08-09, the first four implementation PRs are merged into `main`:

### PR #1 — repository bootstrap repair

`chore: repair repository bootstrap`

Key outcomes:

- restored `.gitignore` and `.extensionignore`;
- added GitHub Actions tests;
- added PR template;
- removed accidentally committed generated run evidence.

### PR #2 — initial executable inventory

`feat: implement moodle inventory capability`

Key outcomes:

- implemented the first executable `moodle.inventory` Python capability;
- added CLI command and evidence output;
- added initial read-only tests.

### PR #3 — Docker and custom-code inventory hardening

`feat: harden docker and custom code inventory`

Key outcomes:

- Docker runtime inspection;
- PHP modules/runtime evidence;
- parent Git repository discovery;
- plugin metadata/classification;
- arbitrary custom code such as `portal_v3`;
- non-core top-level candidate discovery;
- optional database runtime metadata.

### PR #4 — parent-relative custom paths

`feat: allow parent-relative custom code paths`

Key outcomes:

- allows paths such as `../autonomina`;
- constrains parent traversal to the discovered project Git root;
- rejects absolute paths and repository escapes;
- records resolved path and target scope.

## 13. CI and development commands

The canonical GitHub Actions workflow currently performs:

```bash
python -m pip install -e '.[test]'
pytest
python -m moodle_upgrade.cli validate-config --config configs/example.yml
```

Typical local WSL setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest
```

On Ubuntu/WSL, the matching `python3.x-venv` package may need to be installed before creating the virtual environment.

## 14. Next development priority

The deterministic framework, Spec Kit-style agent layer and autonomous guarded runner are implemented. The immediate priority for the real Enaex target is **not** to run an upgrade; it is to resolve the recorded environment-owned blockers:

```text
1. Establish the required clean Git state without discarding user work.
2. Configure and verify explicit database/code/moodledata backup conventions.
3. Configure exact environment-owned upgrade commands.
4. Deliberately enable mutation only after the remaining gates are ready.
5. Re-run deterministic evidence and `muk orchestrate`; mutation remains forbidden until every machine gate and explicit human approval pass.
```

## 15. `moodle.compatibility` intended scope

The next capability should consume inventory evidence and determine upgrade blockers/warnings for the current-to-target Moodle transition.

Initial scope should include at least:

- current Moodle version → target Moodle version path;
- PHP version compatibility;
- required PHP extensions;
- database engine/version compatibility;
- plugin `requires` metadata and target support;
- exact core-vs-custom plugin comparison;
- custom code compatibility indicators;
- deprecated/removed Moodle APIs used by project code;
- direct dependencies on Moodle DB schema/tables/fields;
- legacy PHP incompatibilities relevant to the target runtime;
- actionable blocker/warning evidence rather than a binary pass/fail only.

Compatibility analysis must remain read-only.

## 16. Enaex-specific future regression candidates

These should not be hard-coded into the generic core prematurely, but they are known areas worth converting into project-specific checks later:

- nómina user creation/update behavior;
- duplicate users created through username/email differences;
- BOS module convalidation;
- transfer of quiz responses when quizzes/question banks are equivalent;
- manual grades appearing correctly in reports;
- certificate generation;
- Proofpoint integration;
- portal/report endpoints;
- custom `t_type` behavior;
- direct dependencies on Moodle tables and fields;
- fields moved between tables across Moodle versions;
- legacy report and portal PHP compatibility;
- `portal_v3` compatibility;
- custom integration/batch code such as autonomina.

## 17. Working with Codex CLI

A fresh Codex CLI session should not assume access to prior ChatGPT conversations.

Start from the repository and explicitly load this document:

```bash
cd ~/proyectos/lms-enaex-espanol/moodle-upgrade-kit
codex
```

Recommended first prompt:

```text
Read docs/PROJECT_CONTEXT.md and the relevant SKILL.md files first.
Then inspect the repository and summarize the current implementation status.
Do not modify anything yet.
After that, propose the next smallest safe development step.
```

For implementation work, Codex should inspect the relevant skill contract before modifying code.

Useful instruction pattern:

```text
We are continuing moodle-upgrade-kit.
Read docs/PROJECT_CONTEXT.md and skills/moodle.compatibility/SKILL.md.
Inspect the existing code/tests before proposing changes.
Keep compatibility work read-only and add deterministic tests for every new behavior.
```

## 18. What should remain true as the project evolves

Future contributors and coding agents should preserve these invariants:

- inventory and compatibility remain read-only;
- generated run evidence does not become source-controlled accidentally;
- secrets do not enter evidence or logs;
- Docker and local runtimes remain separable;
- Git root and Moodle root are not assumed to be identical;
- plugin classification remains evidence-based;
- custom non-plugin code is part of compatibility scope;
- project-relative custom paths must stay inside an explicit safe boundary;
- upgrade and rollback require human approval;
- new real-world regressions should produce reusable checks/tests whenever practical.
