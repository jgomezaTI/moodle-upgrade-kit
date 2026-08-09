# AGENTS.md

## Start here

Before making changes, read:

1. `docs/PROJECT_CONTEXT.md`
2. the relevant `skills/<capability>/SKILL.md`
3. the related implementation under `src/moodle_upgrade/`
4. the related tests under `tests/`

Do not rely on previous ChatGPT or Codex conversation history as the source of truth. Repository files are authoritative.

## Project goal

`moodle-upgrade-kit` is an auditable automation framework for Moodle upgrades.

The intended model is:

- skills/commands define capability contracts and reasoning boundaries;
- deterministic Python/scripts perform execution;
- workflows orchestrate capabilities;
- destructive actions require explicit human gates;
- every run produces evidence under `runs/<run-id>/`;
- regressions found during real upgrades should become reusable deterministic checks.

The framework must remain generic first. Enaex-specific checks may be added later as extensions or targeted checks without coupling the core framework to one customer.

## Capability roadmap

The planned capabilities are:

- `moodle.inventory`
- `moodle.baseline`
- `moodle.compatibility`
- `moodle.plugins`
- `moodle.endpoints`
- `moodle.logs`
- `moodle.database`
- `moodle.backup`
- `moodle.upgrade`
- `moodle.validate`
- `moodle.rollback`
- `moodle.document`

Current priority: validate/harden `moodle.inventory` against real environments, then implement `moodle.compatibility`.

## Safety invariants

These rules are mandatory:

- Treat discovery, inventory, compatibility, endpoint, log, and database-inspection work as read-only unless a capability explicitly states otherwise.
- Never enable maintenance mode, execute an upgrade, perform rollback, mutate Moodle, or write to the database from a read-only capability.
- Never read or persist passwords, private keys, bearer tokens, cookies, credentialed DSNs, or secrets from Moodle `config.php` into evidence.
- Never claim a check passed when it was not actually executed.
- Preserve distinctions between `critical`, `warning`, `info`, skipped, unknown, and successful states.
- Prefer deterministic repository code over improvised shell commands.
- For Docker operations, pass command arguments as vectors; avoid shell-interpolated command strings.
- Upgrade and rollback capabilities must retain explicit human gates.
- Do not merge PRs or perform destructive operations unless the user explicitly requests it.

## Development rules

- Make changes through focused branches and PRs.
- Add or update tests for behavior changes.
- A real-world regression or environment-specific failure should become a reusable check/test when practical.
- Keep generated evidence out of source control. `runs/<run-id>/` is runtime evidence, not source code.
- Keep local environment files under `configs/environments/*.local.yml`; these are not intended for commit.
- Do not place credentials in YAML examples.
- Keep skill contracts synchronized with implementation behavior when semantics change.

## Real validation environment

The current real test environment is an Enaex Spanish LMS project under WSL + Docker.

Host layout:

```text
/home/javier/proyectos/lms-enaex-espanol/
├── .git/
├── public_html/
│   ├── Moodle source
│   ├── portal_v3/
│   └── moodledata/
├── autonomina/
└── moodle-upgrade-kit/
```

Observed target details:

- Current Moodle: `3.11.18`
- Moodle branch: `311`
- Upgrade target: `4.1`
- PHP container: `lms-enaex-espanol-php-1`
- PHP runtime observed: `5.6.40`
- Moodle path inside PHP container: `/var/www/html`
- Moodledata inside PHP container: `/var/www/moodledata`
- Database container: `lms-enaex-espanol-db-1`
- Database image observed: `mysql:8.0.41`

Do not generalize these values as global defaults. They describe the current real validation target only.

## Moodle root vs project root

For this environment:

```text
Git project root:
/home/javier/proyectos/lms-enaex-espanol

Moodle root:
/home/javier/proyectos/lms-enaex-espanol/public_html
```

Git discovery must therefore work when `.git` is above `moodle.root`.

## Custom code and plugins

Do not assume all relevant code is a Moodle plugin.

Examples:

- `public_html/portal_v3` is arbitrary custom code inside the Moodle root.
- `../autonomina` is project-level custom code outside `public_html` but inside the project Git repository.
- `local/*` should be treated as project-specific/custom.
- Plugins under `auth`, `blocks`, `mod`, `report`, etc. should remain conservatively `unclassified` unless explicitly configured custom or compared against the exact Moodle core release.

`custom_code.paths` is relative to `moodle.root` and may use parent traversal when the resolved target remains inside the discovered Git repository root.

Allowed example:

```yaml
custom_code:
  paths:
    - portal_v3
    - ../autonomina
```

Absolute paths or traversal escaping the project Git root must be rejected.

Inventory should collect metadata for arbitrary custom code, not persist its source contents. Deeper source compatibility inspection belongs to `moodle.compatibility`.

## `moodle.inventory` expectations

The current implementation should be able to capture:

- Moodle root markers;
- Moodle release/version/branch;
- Docker runtime state/image when configured;
- PHP CLI version and loaded modules from the real runtime;
- Git repository root, branch, HEAD, and dirty state;
- disk usage;
- plugin metadata and conservative classification;
- arbitrary custom code metadata;
- non-core top-level candidates;
- optional database container metadata/server version;
- cron configuration and `admin/cli/cron.php` presence;
- findings and summary;
- evidence under `runs/<run-id>/inventory.json`.

Do not move compatibility verdicts into inventory unnecessarily. For example, inventory records the PHP version; whether that PHP version is valid for the target Moodle belongs to `moodle.compatibility`.

## Testing

Before proposing completion of a code change, run the most relevant tests. The canonical project checks include:

```bash
python -m pip install -e '.[test]'
pytest
python -m moodle_upgrade.cli validate-config --config configs/example.yml
```

For local development with an activated virtual environment, `pytest` and `muk ...` are acceptable equivalents where appropriate.

When testing against the real Enaex Docker environment, keep the test read-only unless the active capability explicitly allows mutation.

## GitHub workflow

Use small, focused PRs with:

- what changed;
- why it changed;
- safety impact;
- validation performed.

Do not silently include unrelated changes.

The initial merged implementation history is summarized in `docs/PROJECT_CONTEXT.md`.

## When starting a new task

1. Read `docs/PROJECT_CONTEXT.md`.
2. Inspect the relevant capability contract.
3. Inspect existing implementation and tests.
4. State what is already implemented versus what is missing.
5. Preserve read-only boundaries unless the requested capability explicitly requires mutation.
6. Implement the smallest coherent change.
7. Add regression coverage.
8. Report exactly what was tested and what remains unverified.
