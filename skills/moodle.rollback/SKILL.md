---
name: moodle.rollback
description: Generate and, only after verified backup evidence and explicit approval, execute an exact configured rollback sequence followed by validation.
effect: destructive / gated
version: 0.2.0
---

# moodle.rollback

## Purpose

Restore using an explicit environment-owned procedure. Rollback never infers restore commands from filenames or backup metadata.

## Required evidence

- Verified `backup.json`
- Explicit `rollback.commands`
- Allowed environment and mutation enabled
- Explicit human approval
- Rejected validation evidence, unless an explicit forced rollback decision is supplied

## Outputs

- `runs/<run-id>/rollback-plan.md`
- `runs/<run-id>/rollback-result.json`

## Procedure

1. Refuse when mutation/environment/approval/backup gates fail.
2. Require at least one explicit restore command and validate all commands against command safety policy.
3. Generate the exact rollback plan before execution.
4. Execute maintenance on → configured restore commands in order → maintenance off.
5. Stop after the first failed step and preserve bounded/redacted evidence.
6. Treat successful restore-command execution as `validation_required`, not final recovery success.
7. Re-run inventory/endpoints/logs/database and call `moodle.validate --mode rollback` to prove the baseline Moodle branch and critical behavior were restored.

## Blocking conditions

- Mutation disabled/environment not allowed/no approval
- Backup cannot be proven
- Restore procedure missing/ambiguous/unsafe
- No rejected validation or explicit forced rollback decision
- Any restore step fails

## Universal rules

- Destructive and gated.
- Never infer a restore procedure.
- Never put credentials in configured command arguments or generated plans.
- Recovery is complete only after post-rollback validation passes.
