---
description: "Select and delegate the next Moodle upgrade capability from deterministic evidence and agent policy."
---

# speckit.moodle.orchestrate

## User input

$ARGUMENTS

## Authoritative contracts

Read `.specify/extensions/moodle/agents/manifest.yml` and every referenced `AGENT.md` contract before acting.

1. Run `muk orchestrate` with the supplied `--config`, `--run-id` and workflow/approval flags. When installed as an extension, pass `--agents-dir .specify/extensions/moodle/agents`.
2. Consume `runs/<run-id>/agent-state.json` as the authoritative next-step decision.
3. If status is `action_required`, delegate only the declared capability to the declared agent. The decision never executes automatically.
4. If status is `human_gate`, pause for the named explicit approval.
5. If status is `blocked`, report the stable blocker codes and do not substitute advice for missing machine evidence.
6. Never add approval flags, enable mutation, invent upgrade/restore commands, or call `moodle.upgrade`/`moodle.rollback` from any agent other than their exclusive owner.
