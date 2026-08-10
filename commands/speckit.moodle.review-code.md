---
description: "Inspect every custom-code folder configured in the Moodle environment YAML and start a bounded compatibility-agent review."
---

# speckit.moodle.review-code

## User input

$ARGUMENTS

## Authoritative contracts

Read `.specify/extensions/moodle/skills/moodle.plugins/SKILL.md` and `.specify/extensions/moodle/agents/compatibility-agent/AGENT.md` before acting.

1. Run `muk review-code` with the supplied `--config` and `--run-id`. By default it refreshes read-only inventory so `custom_code.paths` and `plugins.custom_paths` come from the current YAML; use `--reuse-inventory` only when explicitly requested.
2. The command invokes the existing deterministic `moodle.plugins` analyzer and writes `inventory-before.json`, `plugins.json` and `code-review.json`.
   Its normal stdout is compact; use `--full-output` only when the complete queue must also be emitted there.
3. Confirm `code-review.json.summary.coverage_complete`. An uncovered configured target is an incomplete scan, not a successful review.
4. Work through `review_queue` in `review_rank` order. Inspect only the referenced files/lines; do not copy full source into evidence.
5. Explain the incompatibility and propose the smallest regression-tested correction. Do not edit inspected source unless the user explicitly authorizes changes.
6. Never change finding severity, claim unknown compatibility as passed, enable mutation or invoke upgrade/rollback.
