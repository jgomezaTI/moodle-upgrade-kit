# Architecture

## Layers

1. **Spec Kit command layer** — exposes each capability to the active AI integration.
2. **Skill contract layer** — defines purpose, inputs, outputs, safety and procedure.
3. **Deterministic helper layer** — Python/shell logic for repeatable checks.
4. **Environment config layer** — instance-specific paths, endpoints, log files and validation sets.
5. **Evidence layer** — structured artifacts under `runs/<run-id>/`.
6. **Documentation layer** — converts structured evidence into a Google Drive report.

## Run evidence contract

Every run directory should progressively contain:

```text
runs/<run-id>/
├── metadata.json
├── inventory.json
├── baseline-before.json
├── compatibility.json
├── plugins.json
├── endpoints-before.json
├── logs-before.json
├── database-before.json
├── backup.json
├── upgrade-plan.md
├── upgrade-result.json
├── endpoints-after.json
├── logs-after.json
├── database-after.json
├── baseline-after.json
├── validation.json
└── final-report.md
```

Not every file must exist before execution starts. Missing expected evidence is itself reportable.

## Trust boundaries

- `skills/` may reason and recommend.
- `scripts/` may execute only their documented surface.
- `configs/` cannot contain secrets.
- `upgrade` and `rollback` cannot bypass human approval.
- Google Drive synchronization cannot change the underlying technical result.
