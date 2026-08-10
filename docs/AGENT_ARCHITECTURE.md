# Agent Architecture

## Design

The agent layer follows the Spec Kit pattern of declarative prompts, ordered artifacts and explicit quality gates. Agent contracts express intent and boundaries; deterministic Python owns execution and verdicts.

```text
run evidence
    ↓
upgrade-orchestrator (delegate-only)
    ↓ one authorized next_action
capability owner agent
    ↓ invokes existing `muk` capability only after user action
new structured evidence
```

The selector never launches another process and every action contains `executes_automatically: false`.

## Decision statuses

| Status | Meaning |
|---|---|
| `action_required` | One authorized agent/capability should produce the declared evidence artifact. |
| `human_gate` | Machine prerequisites pass to this point; explicit approval is still required. |
| `blocked` | At least one deterministic machine gate fails; no capability is delegated. |
| `complete` | Validation, acceptance where required, and documentation are complete. |

## Permission model

All 12 deterministic capabilities have exactly one owner. The orchestrator has none. `upgrade-agent` and `rollback-agent` are mutually exclusive destructive roles; registry loading fails if those ownership rules change.

This policy supplements Spec Kit workflows, which orchestrate commands and gates but do not themselves provide an operating-system capability sandbox. The actual upgrade and rollback implementations still re-evaluate every machine prerequisite and explicit approval before running configured argv-safe commands.

## Evidence ordering

Upgrade selection follows:

```text
inventory before → compatibility → plugins → baseline → backup
→ machine gates → human gate → upgrade
→ inventory/endpoints/logs/database after → validate
→ acceptance gate → document
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

Approval flags only tell the selector that a named human gate was satisfied. They do not enable mutation and are not forwarded automatically. The selected destructive capability still requires its own explicit CLI approval and all deterministic evidence.

## Configured-code review entry point

`muk review-code --config <yaml> --run-id <id>` is the direct read-only entry point for AI-assisted module review. It refreshes inventory by default, invokes the existing `moodle.plugins` analyzer and derives `code-review.json`; it does not contain a second scanner.

The queue preserves deterministic severity and `review_rank`, includes only file/line metadata and records whether every YAML-configured target was scanned directly or through a deduplicated parent. `speckit.moodle.review-code` instructs `compatibility-agent` to inspect that queue and propose the smallest correction, while file editing remains separately authorized.
