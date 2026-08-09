---
name: moodle.endpoints
description: Execute configurable HTTP/API smoke checks with stable IDs, expected status codes and timeouts.
effect: read-only
version: 0.1.0
---

# moodle.endpoints

## Purpose

Execute configurable HTTP/API smoke checks with stable IDs, expected status codes and timeouts.

## Effect

`read-only`

## Inputs

- Base URL
- Endpoint definitions
- Optional non-secret headers supplied at runtime

## Outputs

- `endpoints-before.json` or `endpoints-after.json`

## Procedure

1. Build URLs from configured base URL plus relative paths.
2. Execute only configured methods; default to GET.
3. Capture status, latency, redirect target and bounded response metadata.
4. Never persist authentication tokens or full sensitive response bodies.
5. Return non-zero/failed state when a critical expectation is not met.

## Blocking conditions

- Critical endpoint fails expected status
- TLS/connection failure on a critical endpoint

## Universal rules

- Never print or persist passwords, private keys, bearer tokens, session cookies or DB DSNs containing credentials.
- Preserve the run ID in every generated artifact.
- Distinguish `critical`, `warning` and `info` findings.
- Do not claim a check passed if it did not execute.
- Prefer deterministic repository scripts over improvised shell commands when an equivalent helper exists.
