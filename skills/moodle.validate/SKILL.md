---
name: moodle.validate
description: Compare pre-upgrade and post-upgrade evidence and produce an explicit upgrade acceptance decision.
effect: read-only
version: 0.1.0
---

# moodle.validate

## Purpose

Compare pre-upgrade and post-upgrade evidence and produce an explicit upgrade acceptance decision.

## Effect

`read-only`

## Inputs

- Baseline before
- Post-upgrade endpoint/log/DB/inventory evidence

## Outputs

- `validation.json`
- Acceptance/rejection with reasons

## Procedure

1. Verify the post-upgrade instance identity and target version.
2. Re-run the critical baseline checks.
3. Compare endpoint results, log signatures, DB checks and scheduled-task evidence.
4. Mark regressions separately from pre-existing issues.
5. Reject validation when required evidence is missing rather than assuming success.

## Blocking conditions

- Any critical regression
- Target version not confirmed
- Required post-upgrade evidence missing

## Universal rules

- Never print or persist passwords, private keys, bearer tokens, session cookies or DB DSNs containing credentials.
- Preserve the run ID in every generated artifact.
- Distinguish `critical`, `warning` and `info` findings.
- Do not claim a check passed if it did not execute.
- Prefer deterministic repository scripts over improvised shell commands when an equivalent helper exists.
