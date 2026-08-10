---
name: moodle.qa
description: Execute post-upgrade functional Moodle QA through an authenticated browser or environment adapter and record anonymized, machine-validated evidence.
effect: controlled-validation
version: 0.1.0
---

# moodle.qa

## Purpose

Validate the upgraded platform functionally after deterministic post-change validation passes and before human acceptance.

## Inputs

- `validation.json` accepted for the current upgrade
- Environment config and optional `qa.cases`
- Controlled test accounts/fixtures
- Explicit authorization for development access or tests with effects

## Outputs

- `runs/<run-id>/qa-result.json`
- Anonymized evidence references for executed cases

## Procedure

1. Require fresh accepted deterministic validation.
2. Build the matrix from configured cases and environment-specific risk guidance.
3. Use a real browser for UI flows and verify functional outcomes plus relevant logs/data.
4. Preserve passed, failed, blocked and not-applicable states.
5. Reproduce a defect before proposing a correction; require approval before source edits and add regression coverage.
6. Keep email disabled/diverted and use controlled accounts. Ask before development access, cron, enrollment, synchronization or any test with effects.
7. Store only pseudonymous case IDs and evidence references; exclude participant names, RUTs, emails, credentials, cookies, raw logs and exports.
8. Submit schema-version `1.0` input through `muk record-qa`; do not hand-author `qa-result.json`.

## Acceptance

- At least one case executed.
- Every configured required case represented.
- No case blocked.
- No failed case.
- Evidence remains anonymized and independently reviewable.

## Safety

- This capability never owns or invokes `moodle.upgrade` or `moodle.rollback`.
- An HTTP success alone is not a functional pass.
- Never infer an unexecuted case as passed.
