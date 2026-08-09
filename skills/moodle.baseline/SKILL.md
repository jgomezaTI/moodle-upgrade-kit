---
name: moodle.baseline
description: Capture the pre-upgrade functional state so the same critical behavior can be compared after the upgrade.
effect: read-only
version: 0.1.0
---

# moodle.baseline

## Purpose

Capture the pre-upgrade functional state so the same critical behavior can be compared after the upgrade.

## Effect

`read-only`

## Inputs

- Inventory result
- Configured endpoints
- Configured DB checks
- Configured log sources

## Outputs

- `baseline-before.json` plus referenced component evidence

## Procedure

1. Require a successful inventory first.
2. Run endpoint smoke checks.
3. Run allow-listed database validation checks.
4. Capture log error counts/patterns for the selected baseline window.
5. Capture cron/scheduled-task status where available.
6. Record timestamps and check definitions so post-upgrade comparison is like-for-like.

## Blocking conditions

- A critical baseline check cannot execute
- The baseline is missing instance identity

## Universal rules

- Never print or persist passwords, private keys, bearer tokens, session cookies or DB DSNs containing credentials.
- Preserve the run ID in every generated artifact.
- Distinguish `critical`, `warning` and `info` findings.
- Do not claim a check passed if it did not execute.
- Prefer deterministic repository scripts over improvised shell commands when an equivalent helper exists.
