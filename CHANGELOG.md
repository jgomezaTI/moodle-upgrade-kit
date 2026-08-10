# Changelog

## 0.3.0 - 2026-08-09

- Added the installable Codex plugin and `/upgrade-moodle` chat entry point.
- Added `muk run-agents`, which advances every permitted deterministic agent action until completion or a required stop condition.
- Added `qa-agent`, configurable functional QA, anonymized `qa-result.json` validation and the pre-acceptance QA gate.
- Added optional verified external documentation synchronization with `document-sync.json`.
- Added autonomous-run evidence and regression coverage for blockers, gates, resume behavior, QA and documentation synchronization.
- Prevented required QA cases from being marked not applicable to create a false acceptance.

## 0.2.1 - 2026-08-09

- Added `muk review-code` and `speckit.moodle.review-code` as a read-only one-command entry point for YAML-configured custom-code review.
- Added bounded `code-review.json` evidence with configured-folder coverage and a compatibility-agent work queue.

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
