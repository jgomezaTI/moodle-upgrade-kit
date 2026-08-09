---
name: moodle.compatibility
description: Assess whether the current platform and code are compatible with the configured target Moodle version.
effect: read-only
version: 0.1.0
---

# moodle.compatibility

## Purpose

Assess whether the current platform and code are compatible with the configured target Moodle version.

## Effect

`read-only`

## Inputs

- Inventory
- Target Moodle version
- Plugin/custom-code inventory

## Outputs

- `compatibility.json`
- Blocking requirements and manual review list

## Procedure

1. Compare PHP and database versions against a maintained target-version matrix.
2. Identify removed/deprecated APIs relevant to custom code when evidence is available.
3. Flag third-party plugins without a declared compatible version.
4. Flag core modifications and unmanaged vendor changes.
5. Distinguish proven incompatibility from unknown compatibility; unknown is never silently treated as compatible.

## Blocking conditions

- Unsupported PHP/DB version
- Known incompatible plugin
- Required compatibility evidence is unknown for a critical custom integration

## Universal rules

- Never print or persist passwords, private keys, bearer tokens, session cookies or DB DSNs containing credentials.
- Preserve the run ID in every generated artifact.
- Distinguish `critical`, `warning` and `info` findings.
- Do not claim a check passed if it did not execute.
- Prefer deterministic repository scripts over improvised shell commands when an equivalent helper exists.
