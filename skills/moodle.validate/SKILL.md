---
name: moodle.validate
description: Compare pre-change baseline with required post-change evidence and issue an explicit upgrade or rollback acceptance decision.
effect: read-only
version: 0.2.0
---

# moodle.validate

## Purpose

Prove the resulting Moodle identity and distinguish new regressions from pre-existing baseline conditions.

## Inputs

- `baseline-before.json`
- `inventory-after.json`
- `endpoints-after.json`
- `logs-after.json`
- `database-after.json`
- Validation mode: `upgrade` or `rollback`

## Outputs

- `runs/<run-id>/validation.json`
- Explicit `summary.accepted` decision plus regression details

## Procedure

1. Reject missing required evidence rather than assuming success.
2. In upgrade mode, prove the observed Moodle branch matches the configured target branch.
3. In rollback mode, prove the observed Moodle branch matches the baseline/source branch.
4. Reject post-change inventory criticals.
5. Compare previously passing endpoint and database checks against their post state.
6. Compare configured log severity totals and flag increases separately from baseline occurrences.
7. Surface newly failing post-change endpoints and critical post database findings.
8. Accept only when required identity/evidence is proven and no critical regression remains.

## Blocking conditions

- Required evidence missing
- Expected target/restored Moodle branch not confirmed
- Any critical regression
- Critical post-change inventory/database finding

## Universal rules

- Read-only only.
- Preserve distinctions between baseline issues and regressions.
- Never declare an upgrade or rollback successful solely because its command sequence exited zero.
