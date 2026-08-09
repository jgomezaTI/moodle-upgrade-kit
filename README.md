# Moodle Upgrade Kit

Moodle Upgrade Kit is a Spec Kit-inspired, auditable framework for planning, validating, executing, and documenting Moodle upgrades.

The project deliberately separates **agent reasoning** from **deterministic execution**:

- `skills/` describes the contracts and safety rules for each Moodle capability.
- `commands/` exposes those capabilities as Spec Kit extension commands.
- `scripts/` contains deterministic, reviewable execution helpers.
- `workflows/` chains the capabilities into a guarded upgrade process.
- `configs/` contains environment-specific, non-secret configuration.
- `runs/` is the local execution evidence area and is ignored by Git.

## Initial capabilities

| Capability | Purpose | Default effect |
|---|---|---|
| `moodle.inventory` | Detect Moodle, PHP, database, Git, plugins, disk and cron context | Read-only |
| `moodle.baseline` | Capture the functional state before an upgrade | Read-only |
| `moodle.compatibility` | Evaluate target-version requirements and blockers | Read-only |
| `moodle.plugins` | Inspect third-party/custom plugins and custom code | Read-only |
| `moodle.endpoints` | Run configurable HTTP/API smoke checks | Read-only |
| `moodle.logs` | Analyze Nginx/Apache, PHP, Moodle and cron logs | Read-only |
| `moodle.database` | Run allow-listed pre/post validation queries | Read-only by default |
| `moodle.backup` | Verify backup presence, freshness and restore metadata | Read-only |
| `moodle.upgrade` | Execute a controlled Moodle upgrade | Destructive; gated |
| `moodle.validate` | Compare baseline with the post-upgrade state | Read-only |
| `moodle.rollback` | Execute an approved rollback procedure | Destructive; gated |
| `moodle.document` | Produce evidence and synchronize a human-readable report | Read/write artifacts |

## Core safety principles

1. Diagnostic skills are read-only.
2. Secrets are never committed to the repository or run artifacts.
3. `upgrade` and `rollback` require explicit human approval.
4. No production mutation is allowed unless a fresh backup check passes.
5. Every upgrade has a run ID and evidence directory.
6. Every regression found during an upgrade should become a permanent test or validation check.
7. Git is the technical source of truth; Google Drive is the human-readable documentation surface.

## Spec Kit alignment

This repository is designed as a Spec Kit extension source. `extension.yml` declares the commands, and `workflows/moodle-upgrade/workflow.yml` provides an end-to-end workflow with human gates before mutation.

Typical development flow:

```bash
specify init . --integration codex
specify extension add moodle-upgrade --dev .
specify workflow add workflows/moodle-upgrade --dev
```

Then use the installed command/skill names exposed by the active Spec Kit integration.

## Local CLI

The repository also includes a small deterministic helper CLI:

```bash
python -m moodle_upgrade.cli validate-config --config configs/example.yml
python -m moodle_upgrade.cli new-run --config configs/example.yml
python -m moodle_upgrade.cli endpoints --config configs/example.yml --run-id UPG-2026-001
python -m moodle_upgrade.cli compare --before runs/UPG-2026-001/baseline-before.json --after runs/UPG-2026-001/baseline-after.json
```

The CLI is intentionally conservative. It does **not** perform a Moodle upgrade by itself in this first version. Upgrade and rollback skills produce an approved execution plan and require a human gate before any server-side commands are run.

## Repository status

This is the initial bootstrap. The next milestones are:

1. validate the framework against a non-production Moodle instance;
2. add SSH execution adapters with strict allow-lists;
3. integrate Google Drive document updates through a dedicated adapter;
4. add Moodle-version compatibility matrices and plugin API checks;
5. convert each real incident into a regression fixture.
