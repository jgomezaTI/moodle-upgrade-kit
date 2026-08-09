# Critical Path Status

_Last updated: 2026-08-09_

This file is the current implementation-status companion to `docs/PROJECT_CONTEXT.md`. The project-context document preserves the longer architecture/history; this file records what is implemented now and what must happen next without broadening scope.

## Current branch / PR

- Branch: `agent/critical-path-completion`
- PR: `#6 — feat: complete guarded Moodle upgrade critical path`
- State: draft, mergeable
- GitHub Actions: passing
- Canonical test result on the PR merge ref: **31 passed**
- Generic example configuration validation: **config: OK**

## Implemented critical path

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

Rollback:

```text
rollback gate
→ explicit rollback commands
→ inventory/endpoints/logs/database after
→ validate --mode rollback
→ document
```

## Safety state

The generic configuration remains non-mutating by default:

```yaml
safety:
  allow_mutation: false

upgrade:
  code_transition_command: null

rollback:
  commands: []
```

No real Moodle upgrade or rollback has been executed as part of PR #6.

Machine gates are authoritative. Human approval cannot override critical failures in inventory/Git state, compatibility, plugin/custom-code analysis, baseline or backup verification.

## Real Enaex validation target

```text
Git project root: /home/javier/proyectos/lms-enaex-espanol
Moodle root:      /home/javier/proyectos/lms-enaex-espanol/public_html
Kit repo:         /home/javier/proyectos/lms-enaex-espanol/moodle-upgrade-kit
```

- Current Moodle: `3.11.18`
- Target Moodle: `4.1`
- PHP container: `lms-enaex-espanol-php-1`
- Observed PHP: `5.6.40`
- DB container: `lms-enaex-espanol-db-1`
- Observed DB image: `mysql:8.0.41`
- Custom application code includes `portal_v3` and project-level paths such as `../autonomina`.

The expected first blocker is PHP: `moodle.compatibility` must refuse the 3.11 → 4.1 mutation path while the observed PHP runtime remains 5.6.40.

## Next critical step — no deviation

Run PR #6 against the real WSL/Docker environment **read-only** and inspect its generated evidence. Do not configure/enable mutation yet.

Recommended test run:

```bash
cd ~/proyectos/lms-enaex-espanol/moodle-upgrade-kit

git fetch origin
git checkout agent/critical-path-completion

source .venv/bin/activate
python -m pip install -e '.[test]'
pytest

RUN_ID=ENAEX-311-TO-410-CRITICAL-PATH
CONFIG=configs/environments/lms-enaex-espanol.local.yml

muk inventory --config "$CONFIG" --run-id "$RUN_ID" --phase before
muk compatibility --config "$CONFIG" --run-id "$RUN_ID"
muk plugins --config "$CONFIG" --run-id "$RUN_ID"
```

At this point, stop and inspect the evidence. `moodle.compatibility` is expected to return a non-zero blocking result while PHP remains 5.6.40. That is a successful safety outcome, not a kit failure.

Do not proceed to a mutating command. Baseline/database/backup configuration can be hardened from the read-only findings after inventory/compatibility/plugins are confirmed against the real instance.

## Evidence to review first

```text
runs/ENAEX-311-TO-410-CRITICAL-PATH/
├── inventory-before.json
├── inventory.json
├── compatibility.json
└── plugins.json
```

Verify specifically:

- containing Git root is `/home/javier/proyectos/lms-enaex-espanol`;
- PHP evidence comes from `lms-enaex-espanol-php-1`;
- PHP modules/settings are captured;
- DB container/image/version metadata is present;
- `portal_v3` is inventoried/scanned;
- configured `../autonomina` resolves with project scope and remains inside the Git root;
- custom/unclassified plugin review is conservative;
- PHP 5.6.40 is a critical compatibility blocker for the documented current/target Moodle versions;
- no credential values appear in evidence.

## Rule after the real run

Any incorrect or missing evidence discovered in the real environment must become a deterministic regression test before the critical path advances.

Once the read-only real run behaves correctly, the next work is environment preparation/configuration required to clear real blockers (starting with the PHP runtime for Moodle 4.1), then baseline/backup evidence for that same environment. Mutation remains last.
