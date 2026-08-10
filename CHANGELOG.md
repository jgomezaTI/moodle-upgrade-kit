# Changelog

## 0.2.0 - 2026-08-09

- Added seven portable agent contracts with unique deterministic capability ownership.
- Added a machine-validated, delegate-only upgrade orchestrator and `agent-state.json` evidence.
- Added `muk orchestrate` and `speckit.moodle.orchestrate` without automatic capability execution.
- Reused public upgrade/rollback precondition evaluators so agents cannot diverge from execution gates.
- Added regression coverage for destructive-role separation, human/machine gates and stale evidence.
- Completed real read-only Enaex validation through baseline, backup blocking and upgrade precondition blocking.

## 0.1.0 - 2026-08-08

- Initial Spec Kit extension manifest.
- Added 12 Moodle upgrade skill contracts.
- Added guarded upgrade and rollback workflows.
- Added configuration schema/example and safety constitution.
- Added deterministic endpoint/log comparison helpers and initial unit tests.
