---
description: "Execute post-upgrade functional QA and record anonymized evidence."
---

# speckit.moodle.qa

## User input

$ARGUMENTS

Read `.specify/extensions/moodle/skills/moodle.qa/SKILL.md` and `.specify/extensions/moodle/agents/qa-agent/AGENT.md` before acting.

1. Require fresh accepted `validation.json` and the exact environment config/run ID.
2. Execute configured cases using a real browser where appropriate. Request authorization for development or tests with effects.
3. Preserve pass, failure, blocked and not-applicable states and anonymize evidence.
4. Submit the result using `muk record-qa --config <config> --run-id <run-id> --input <json>`.
5. Never invoke upgrade/rollback or claim unexecuted QA as passed.
