# Architecture

## Layers

1. **Spec Kit command layer** — exposes capabilities and orchestration to the active AI integration.
2. **Agent contract layer** — defines roles, capability ownership, evidence inputs/outputs and delegation boundaries.
3. **Skill contract layer** — defines capability purpose, inputs, outputs, safety and procedure.
4. **Deterministic helper layer** — Python logic for repeatable checks, gates, execution and next-step selection.
5. **Environment config layer** — instance-specific paths, endpoints, log sources and validation sets.
6. **Evidence layer** — structured artifacts under `runs/<run-id>/`.
7. **Documentation layer** — converts structured evidence into a redacted report and optional external synchronization result.

## Run evidence contract

Every run directory should progressively contain:

```text
runs/<run-id>/
├── metadata.json
├── inventory.json
├── baseline-before.json
├── compatibility.json
├── plugins.json
├── code-review.json
├── endpoints-before.json
├── logs-before.json
├── database-before.json
├── backup.json
├── agent-state.json
├── agent-run.json
├── upgrade-plan.md
├── upgrade-result.json
├── endpoints-after.json
├── logs-after.json
├── database-after.json
├── baseline-after.json
├── validation.json
├── qa-result.json
├── final-report.md
├── document-result.json
└── document-sync.json
```

Not every file must exist before execution starts. Missing expected evidence is itself reportable.

## Trust boundaries

- `skills/` may reason and recommend.
- `agents/` may delegate only capabilities granted by their machine-validated contracts.
- `upgrade-orchestrator` owns no executable capability and never auto-executes a decision.
- `scripts/` may execute only their documented surface.
- `configs/` cannot contain secrets.
- `upgrade` and `rollback` cannot bypass human approval.
- Google Drive synchronization cannot change the underlying technical result.
