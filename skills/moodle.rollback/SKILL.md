---
name: moodle.rollback
description: Generate and, only after explicit approval, execute a rollback using verified backup evidence and a known restoration sequence.
effect: destructive / gated
version: 0.1.0
---

# moodle.rollback

## Purpose

Generate and, only after explicit approval, execute a rollback using verified backup evidence and a known restoration sequence.

## Effect

`destructive / gated`

## Inputs

- Failed validation or explicit rollback decision
- Verified backup evidence
- Explicit human gate

## Outputs

- `rollback-plan.md`
- `rollback-result.json`

## Procedure

1. Never infer a restore command from filenames alone; use configured/approved restoration procedures.
2. Identify the exact backup set and pre-upgrade Git/version state.
3. Generate the restoration sequence before execution.
4. Pause for explicit human approval.
5. Keep the site in maintenance mode during restoration.
6. Restore code, database and moodledata in the approved order.
7. Run post-rollback validation before declaring recovery successful.

## Blocking conditions

- Backup set cannot be proven
- No human approval
- Restore procedure is incomplete or ambiguous

## Universal rules

- Never print or persist passwords, private keys, bearer tokens, session cookies or DB DSNs containing credentials.
- Preserve the run ID in every generated artifact.
- Distinguish `critical`, `warning` and `info` findings.
- Do not claim a check passed if it did not execute.
- Prefer deterministic repository scripts over improvised shell commands when an equivalent helper exists.
