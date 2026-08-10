---
name: upgrade-moodle
description: Run or resume the complete guarded Moodle upgrade lifecycle from one chat request. Use when the user invokes /upgrade-moodle or asks Codex to autonomously coordinate Moodle discovery, compatibility and custom-code review, baseline and backup gates, approved upgrade or rollback execution, post-upgrade functional QA, evidence, local reporting, and verified Google Drive documentation.
---

# Upgrade Moodle

Coordinate the repository's agents as one persistent workflow. Continue until the run is complete, a mandatory human gate needs an answer, or a machine/external blocker prevents progress.

## Resolve inputs

1. Locate the `moodle-upgrade-kit` root by finding `pyproject.toml`, `agents/manifest.yml`, and `src/moodle_upgrade` in the active workspace. Stop if multiple roots are ambiguous.
2. Read `AGENTS.md`, `docs/CODEX_HANDOFF.md`, `docs/CRITICAL_PATH_STATUS.md`, and every agent contract selected by `agent-state.json`.
3. Parse an explicit config/run ID from the user's invocation. Otherwise use `configs/environments/lms-enaex-espanol.local.yml` when it exists and generate `UPG-YYYYMMDD-HHMMSS` in UTC.
4. Run `muk validate-config`. Never edit an environment config merely to make a gate pass.

## Advance the deterministic workflow

Run from the kit root:

```bash
muk run-agents --config <config> --run-id <run-id> --agents-dir agents
```

Consume `runs/<run-id>/agent-run.json`, `agent-state.json`, and the declared evidence. Do not infer success from stdout or an exit code alone.

- `blocked`: report stable blocker codes. Resolve only framework/code defects that are in scope; never invent backup, PHP, Git, upgrade, rollback, or credential configuration.
- `human_gate`: present the exact evidence and ask for the named approval. After approval, rerun with only the corresponding flag.
- `external_action_required`: execute the declared QA or documentation adapter procedure below, record its evidence, then rerun.
- `complete`: verify required evidence, documentation, Git state, and remaining findings before closing.

Never pass an approval flag based on earlier general permission. It must correspond to the current run and named gate.

## Review compatibility findings

After every read-only runner pass, inspect `code-review.json` before closing on a later machine blocker. When `summary.review_required` is true, act as `compatibility-agent` and inspect `review_queue` in `review_rank` order. Group repeated occurrences, reproduce each defect, and propose the smallest correction with deterministic regression coverage. Ask for explicit approval before modifying Moodle/project source files. After an approved correction, rerun `muk review-code` for the same run and preserve the new evidence.

Warnings and manual-review items remain explicit. Do not downgrade them to pass merely because the scan completed.

## Execute functional QA

When the next capability is `moodle.qa`:

1. Read `skills/moodle.qa/SKILL.md` in the kit. If `$qa-plataforma-enaex` is available for an Enaex target, use it as the environment adapter.
2. Use a real browser for UI cases and the configured read-only checks for supporting evidence.
3. Ask before accessing development or running any test with effects. Apply local email safeguards before testing email, cron, enrollment, recovery, or communications.
4. Store only anonymized evidence references. Do not persist names, RUTs, participant emails, credentials, cookies, exports, or raw logs.
5. Build a schema-version `1.0` QA input JSON and run:

```bash
muk record-qa --config <config> --run-id <run-id> --input <qa-input.json>
```

Do not request acceptance while any critical case failed, any required case is blocked, or configured coverage is missing.

## Handle upgrade and acceptance gates

At `pre-upgrade-review`, summarize compatibility, code review, baseline, backup, Git, configured commands, and mutation state. Execute the approved step only by rerunning:

```bash
muk run-agents ... --pre-upgrade-approved
```

At `acceptance`, summarize deterministic validation and functional QA. After explicit acceptance, retain `--pre-upgrade-approved` and add `--acceptance-approved`.

Never run rollback unless the workflow is explicitly switched to rollback and its separate gate is approved.

## Publish documentation

Generate local `final-report.md` through the runner first. When the next capability is `moodle.document.sync`:

1. Use `$mantenedor-docs-enaex` for Enaex and the connected Google Drive/Docs tools.
2. Confirm target metadata, read before writing, preserve structure, write only confirmed/anonymized results, and read back the updated section.
3. Record connector-confirmed metadata in schema-version `1.0` JSON and run:

```bash
muk record-document-sync --config <config> --run-id <run-id> --input <sync-input.json>
```

Never record `verified: true` without a successful read-after-write. Moving, deleting, sharing, or changing permissions remains separately authorized.

## Completion

Finish only when `agent-run.json.status` is `complete`. Report the run ID, target version, commits, QA totals, Drive resource, blockers resolved, residual warnings, and anything that remains externally unverified.
