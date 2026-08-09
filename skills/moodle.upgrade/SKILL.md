---
name: moodle.upgrade
description: Create and, only after explicit approval, execute a controlled Moodle upgrade sequence with evidence at each stage.
effect: destructive / gated
version: 0.1.0
---

# moodle.upgrade

## Purpose

Create and, only after explicit approval, execute a controlled Moodle upgrade sequence with evidence at each stage.

## Effect

`destructive / gated`

## Inputs

- Passing inventory/baseline/compatibility/backup checks
- Approved target version
- Explicit human gate

## Outputs

- `upgrade-plan.md`
- `upgrade-result.json`

## Procedure

1. Refuse to proceed if mutation is disabled in configuration.
2. Refuse to proceed if the environment identity does not match the configured mutation policy.
3. Require successful backup verification and a clean/understood Git state.
4. Generate the exact command plan before execution.
5. Pause for explicit human approval.
6. Enable maintenance mode using the configured command.
7. Perform only the approved code/version transition.
8. Run Moodle CLI upgrade non-interactively.
9. Purge caches and run cron as configured.
10. Disable maintenance mode only when the approved plan says it is safe.
11. Persist exit codes/timestamps without secrets.

## Blocking conditions

- No human approval
- Backup check failed
- Compatibility blocker exists
- Production mutation not explicitly enabled

## Universal rules

- Never print or persist passwords, private keys, bearer tokens, session cookies or DB DSNs containing credentials.
- Preserve the run ID in every generated artifact.
- Distinguish `critical`, `warning` and `info` findings.
- Do not claim a check passed if it did not execute.
- Prefer deterministic repository scripts over improvised shell commands when an equivalent helper exists.
