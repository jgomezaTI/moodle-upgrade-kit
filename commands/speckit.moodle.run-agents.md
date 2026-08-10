---
description: "Advance all permitted Moodle agents until completion, a blocker, an external action, or a human gate."
---

# speckit.moodle.run-agents

## User input

$ARGUMENTS

Read `.specify/extensions/moodle/agents/manifest.yml` and all selected agent contracts before acting.

Run `muk run-agents` with the supplied config, run ID and only explicitly granted approval flags. Consume `agent-run.json` and continue through declared read-only capabilities. Stop at `blocked`, `human_gate` or `external_action_required`; never infer approvals, enable mutation or invent environment commands.
