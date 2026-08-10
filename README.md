# Moodle Upgrade Kit

Moodle Upgrade Kit is a Spec Kit-inspired, auditable framework for planning, validating, executing and documenting Moodle upgrades.

The project separates **capability contracts** from **deterministic execution**:

- `skills/` defines behavior and safety boundaries.
- `commands/` exposes Spec Kit extension commands.
- `agents/` defines portable roles, capability permissions and evidence contracts.
- `src/moodle_upgrade/` contains deterministic Python execution.
- `workflows/` chains capabilities and human gates.
- `configs/` contains non-secret environment configuration.
- `runs/` contains local execution evidence and is ignored by Git.

## Capabilities

| Capability | Purpose | Effect |
|---|---|---|
| `moodle.inventory` | Capture Moodle/runtime/Git/plugin/custom-code/platform facts | Read-only |
| `moodle.compatibility` | Evaluate target requirements and upgrade-path blockers | Read-only |
| `moodle.plugins` | Scan plugins and arbitrary project code for upgrade risks | Read-only |
| `moodle.baseline` | Capture pre-upgrade endpoint/DB/log/cron behavior | Read-only |
| `moodle.endpoints` | Run configurable HTTP smoke checks | Read-only |
| `moodle.logs` | Analyze configured log signatures | Read-only |
| `moodle.database` | Execute allow-listed read-only validation SQL | Read-only |
| `moodle.backup` | Verify explicit backup components and freshness | Read-only |
| `moodle.upgrade` | Execute an exact configured upgrade after all gates pass | Destructive; gated |
| `moodle.validate` | Compare post-change evidence against baseline | Read-only |
| `moodle.rollback` | Execute an explicit restore procedure after rollback gates pass | Destructive; gated |
| `moodle.document` | Produce a redacted local evidence report | Artifact write |

## Critical path

```text
inventory before
→ compatibility
→ plugins/custom code
→ baseline
→ backup verification
→ human review gate
→ upgrade
→ inventory/endpoints/logs/database after
→ validate
→ human acceptance gate
→ document
```

Rollback is separately gated and requires an explicit restore procedure:

```text
rollback review gate
→ rollback
→ inventory/endpoints/logs/database after
→ validate --mode rollback
→ document
```

## Safety model

1. Read-only capabilities never mutate Moodle or the database.
2. Secrets are never stored in configuration examples or run evidence.
3. Database validation SQL is allow-listed and rejected when mutation cannot be ruled out.
4. `safety.allow_mutation` is `false` by default.
5. Upgrade requires compatible platform evidence, plugin/custom-code analysis without critical findings, a complete baseline, verified backups, clean Git when required, an allowed environment and explicit human approval.
6. Rollback requires verified backups, an explicit environment-owned restore sequence and explicit human approval.
7. Mutation commands use argv-safe execution; shell interpolation/control syntax and credential-bearing arguments are rejected.
8. Command exit code zero is not acceptance. Post-change `moodle.validate` must pass.
9. Every real regression should become a stable test or validation check.
10. Agent decisions never execute automatically; capability ownership and destructive-role separation are machine-validated.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
pytest
```

## Read-only validation flow

Start with a local gitignored environment config under `configs/environments/*.local.yml`.

```bash
RUN_ID=UPG-2026-001
CONFIG=configs/environments/example.local.yml

muk inventory --config "$CONFIG" --run-id "$RUN_ID" --phase before
muk compatibility --config "$CONFIG" --run-id "$RUN_ID"
muk plugins --config "$CONFIG" --run-id "$RUN_ID"
muk baseline --config "$CONFIG" --run-id "$RUN_ID"
muk backup --config "$CONFIG" --run-id "$RUN_ID"
```

A compatibility blocker or missing backup evidence is expected to stop the critical path before mutation.

Database check credentials, when checks are configured, are supplied through the environment-variable names declared under `database.connection_env`. A trusted DB container can instead resolve names declared under `database.container_connection_env` without exporting credential values to host argv or evidence.

## Mutating flow

The generic example intentionally cannot mutate because:

```yaml
safety:
  allow_mutation: false

upgrade:
  code_transition_command: null

rollback:
  commands: []
```

An environment owner must explicitly configure and review mutation commands and then enable mutation for an allowed environment. Even then, the CLI refuses to upgrade unless all machine-verifiable gates and `--approved` pass.

After an approved upgrade, collect post-change evidence before validation:

```bash
muk inventory --config "$CONFIG" --run-id "$RUN_ID" --phase after
muk endpoints --config "$CONFIG" --run-id "$RUN_ID" --phase after
muk logs --config "$CONFIG" --run-id "$RUN_ID" --phase after
muk database --config "$CONFIG" --run-id "$RUN_ID" --phase after
muk validate --config "$CONFIG" --run-id "$RUN_ID" --mode upgrade
muk document --config "$CONFIG" --run-id "$RUN_ID"
```

## Evidence

A complete run can produce:

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

## Agent orchestration

The seven agent contracts are registered under `agents/`. They are model/vendor neutral: an AI integration reads the role prompt, while `muk orchestrate` deterministically selects at most one permitted next capability from current evidence.

```bash
muk orchestrate \
  --config "$CONFIG" \
  --run-id "$RUN_ID" \
  --workflow upgrade \
  --agents-dir agents
```

The result is written to `agent-state.json` with one of four statuses: `action_required`, `human_gate`, `blocked`, or `complete`. It always sets `executes_automatically: false` for delegated actions.

Only `upgrade-agent` owns `moodle.upgrade`; only `rollback-agent` owns `moodle.rollback`; the orchestrator owns no capability. Approval inputs cannot override machine blockers, enable mutation or invent environment commands. See `docs/AGENT_ARCHITECTURE.md`.

### Start configured-code review

Use one command to refresh read-only inventory, inspect the folders declared under `custom_code.paths` and `plugins.custom_paths`, run the existing plugin/custom-code analyzer and prepare the compatibility agent queue:

```bash
muk review-code \
  --config "$CONFIG" \
  --run-id "$RUN_ID"
```

It writes `inventory-before.json`, `plugins.json` and `code-review.json`. The review artifact records each configured target as `scanned`, `covered-by-parent` or `not-scanned`, then exposes bounded findings in deterministic `review_rank` order. Use `--reuse-inventory` only when deliberately reusing inventory from the same run.

The terminal prints a compact summary plus the first pending review. Add `--full-output` only when the complete queue is also needed on stdout; `code-review.json` always retains it.

In a Spec Kit integration, invoke `speckit.moodle.review-code`; the `compatibility-agent` will work through that queue and propose corrections. Source changes still require explicit user authorization.

## Spec Kit alignment

`extension.yml` declares the capability commands plus `speckit.moodle.orchestrate`; `workflows/moodle-upgrade/workflow.yml` and `workflows/moodle-rollback/workflow.yml` describe the gated operational paths.

The repository itself remains the technical source of truth. `AGENTS.md` and `docs/PROJECT_CONTEXT.md` provide persistent handoff context for Codex/other coding agents.

## Current real validation target

The first real target is the Enaex Spanish LMS under WSL + Docker, currently documented as Moodle `3.11.18` → `4.1`. The observed PHP runtime is `5.6.40`; `moodle.compatibility` is expected to classify that as a blocker before any mutation is possible.

The real read-only critical path has been exercised through backup and mutation-gate validation. Current blockers remain PHP compatibility, dirty LMS Git state, missing verified backup conventions, disabled mutation and missing environment-owned upgrade commands. The agent layer reports those blockers without attempting to resolve or bypass them.
