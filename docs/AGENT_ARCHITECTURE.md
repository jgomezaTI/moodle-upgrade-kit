# Agent Architecture

## Design

The agent layer follows the Spec Kit pattern of declarative prompts, ordered artifacts and explicit quality gates. Agent contracts express intent and boundaries; deterministic Python owns execution and verdicts.

```text
run evidence
    ↓
upgrade-orchestrator (delegate-only)
    ↓ one authorized next_action
capability owner agent
    ↓ autonomous runner invokes an existing deterministic `muk` capability
new structured evidence
```

The selector remains a pure decision function and every action contains `executes_automatically: false`. `muk run-agents` is the separate executor: it advances permitted deterministic actions and stops before external adapters, blockers or human gates.

## Decision statuses

| Status | Meaning |
|---|---|
| `action_required` | One authorized agent/capability should produce the declared evidence artifact. |
| `human_gate` | Machine prerequisites pass to this point; explicit approval is still required. |
| `blocked` | At least one deterministic machine gate fails; no capability is delegated. |
| `external_action_required` | QA or documentation synchronization must be performed by the active chat integration and recorded through its validator. |
| `complete` | Validation, functional QA, acceptance, documentation and any required external sync are complete. |

## Permission model

All registered capabilities have exactly one owner. The orchestrator has none. `upgrade-agent` and `rollback-agent` are mutually exclusive destructive roles; registry loading fails if those ownership rules change.

This policy supplements Spec Kit workflows, which orchestrate commands and gates but do not themselves provide an operating-system capability sandbox. The actual upgrade and rollback implementations still re-evaluate every machine prerequisite and explicit approval before running configured argv-safe commands.

The active chat integration may apply a specifically approved local remediation after a read-only finding. This does not make the deterministic compatibility capability mutable: the integration preserves unrelated changes, reruns the owning analyzer and cannot weaken a gate. `/upgrade-moodle` never stages, commits, pushes or opens a PR for inspected-project changes.

## Evidence ordering

Upgrade selection follows:

```text
inventory before → compatibility → plugins → baseline → backup
→ machine gates → human gate → upgrade
→ inventory/endpoints/logs/database after → validate
→ functional QA → acceptance gate → document
→ optional verified external documentation sync
```

Rollback selection follows its separate backup/decision/human gates, explicit rollback result, post-rollback evidence, rollback-mode validation and documentation.

Post-change artifacts must be at least as new as the mutation result. Validation must follow all post-change checks, and documentation must follow validation. This prevents stale artifacts from making a resumed run appear complete.

## Usage

```bash
muk orchestrate \
  --config configs/environments/example.local.yml \
  --run-id UPG-2026-001 \
  --workflow upgrade \
  --agents-dir agents
```

To advance all permitted steps instead of selecting only one:

```bash
muk run-agents \
  --config configs/environments/example.local.yml \
  --run-id UPG-2026-001 \
  --workflow upgrade \
  --agents-dir agents
```

The run summary is stored in `agent-run.json`. QA and Google Drive remain environment-adapter actions because their browser/connector effects and evidence require the active chat integration; `muk record-qa` and `muk record-document-sync` validate their anonymized results before the workflow advances. Document sync also validates the selected publication scope against `document-result.json`.

Approval flags only tell the selector that a named human gate was satisfied. They do not enable mutation and are not forwarded automatically. The selected destructive capability still requires its own explicit CLI approval and all deterministic evidence.

## Configured-code review entry point

`muk review-code --config <yaml> --run-id <id>` is the direct read-only entry point for AI-assisted module review. It refreshes inventory by default, invokes the existing `moodle.plugins` analyzer and derives `code-review.json`; it does not contain a second scanner.

The queue preserves deterministic severity and `review_rank`, includes only file/line metadata and records whether every YAML-configured target was scanned directly or through a deduplicated parent. `speckit.moodle.review-code` instructs `compatibility-agent` to inspect that queue and propose the smallest correction, while file editing remains separately authorized.

## Codex plugin

`plugins/moodle-upgrade-kit` packages the `upgrade-moodle` skill and `/upgrade-moodle` command. The skill resolves the environment, calls `muk run-agents`, handles approved local remediation and external QA/documentation adapters, and resumes until completion or a mandatory stop condition. It cannot weaken a deterministic gate or create a Git commit.

With `documentation.summary_mode: findings-focused`, Drive receives grouped warnings/errors and outcomes when issues exist. A clean accepted run receives only a concise status record. The local report and structured artifacts retain the complete audit trail.
