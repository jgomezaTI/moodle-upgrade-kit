---
name: moodle.plugins
description: Review third-party plugins, local plugins and custom code that may break during a Moodle upgrade.
effect: read-only
version: 0.1.0
---

# moodle.plugins

## Purpose

Review third-party plugins, local plugins and custom code that may break during a Moodle upgrade.

## Effect

`read-only`

## Inputs

- Moodle root
- Configured custom roots/ignore list

## Outputs

- `plugins.json`
- Custom-code review candidates

## Procedure

1. Enumerate plugins by component/path and version metadata when available.
2. Identify local/custom plugins and code living outside standard plugin boundaries.
3. Detect uncommitted changes and direct core modifications where Git history can prove them.
4. Search for configured high-risk API/table patterns without claiming compatibility from pattern absence alone.
5. Produce a prioritized manual review list.

## Blocking conditions

- Known direct core modification with no migration plan
- Critical custom plugin cannot be inventoried

## Universal rules

- Never print or persist passwords, private keys, bearer tokens, session cookies or DB DSNs containing credentials.
- Preserve the run ID in every generated artifact.
- Distinguish `critical`, `warning` and `info` findings.
- Do not claim a check passed if it did not execute.
- Prefer deterministic repository scripts over improvised shell commands when an equivalent helper exists.
