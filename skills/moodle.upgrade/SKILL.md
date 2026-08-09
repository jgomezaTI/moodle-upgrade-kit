---
name: moodle.upgrade
description: Generate and, only after all machine gates plus explicit approval pass, execute an exact configured Moodle upgrade sequence.
effect: destructive / gated
version: 0.2.0
---

# moodle.upgrade

## Purpose

Execute only a pre-declared upgrade plan after deterministic evidence proves the environment is ready. Human approval cannot override a critical machine gate.

## Required evidence

- Pre-change inventory
- Passing compatibility
- Plugin/custom-code analysis with no critical findings
- Complete baseline
- Verified backup set
- Clean Git state when policy requires it
- Allowed environment identity
- Explicit human approval

## Outputs

- `runs/<run-id>/upgrade-plan.md`
- `runs/<run-id>/upgrade-result.json`

## Procedure

1. Refuse when `safety.allow_mutation` is false.
2. Verify required environment, approval and all required evidence.
3. Validate every configured command before executing any mutation. Shell operators/interpolation and credential-bearing argv are rejected.
4. Require an explicit `upgrade.code_transition_command`; never infer the code/version transition.
5. Execute the configured sequence: maintenance on → code transition → Moodle CLI upgrade → purge caches → optional cron → maintenance off.
6. Execute locally or through the configured Docker PHP runtime using argument vectors.
7. Stop subsequent steps after the first failed step and record bounded/redacted output.
8. Require separate post-upgrade inventory/endpoints/logs/database evidence and `moodle.validate` before acceptance.

## Blocking conditions

- Mutation disabled or environment not allowed
- Missing explicit human approval
- Inventory/Git/compatibility/plugins/baseline/backup gate fails
- Required command missing or rejected by command safety policy
- Any upgrade step fails

## Universal rules

- Destructive and gated.
- Never infer commands or embed credentials in argv.
- An executed upgrade is not an accepted upgrade until post-upgrade validation passes.
