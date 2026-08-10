---
name: upgrade-moodle
description: Run or resume the complete guarded Moodle upgrade lifecycle from one chat request. Use when the user invokes /upgrade-moodle or asks Codex to autonomously coordinate Moodle discovery, compatibility review, explicitly authorized local remediation, baseline and backup gates, approved upgrade or rollback execution, post-upgrade QA, evidence, and findings-focused Google Drive documentation without creating Git commits.
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

## Apply authorized remediation

Deterministic inventory, compatibility, plugin and validation capabilities remain read-only. The active chat agent may edit local Moodle source, custom code or environment configuration only after the user explicitly approves a named remediation batch.

1. Present the affected paths, intended behavior change, expected checks and whether services or data may be affected.
2. Preserve unrelated working-tree changes. Never discard, overwrite or normalize files outside the approved batch.
3. Apply the smallest patch, add deterministic regression coverage when practical, and run the relevant checks.
4. Refresh the affected evidence with the repository capability; never hand-edit a passing verdict.
5. Treat container recreation, service restart, cron, email, synchronization, database changes and any non-local action as separate effects requiring explicit approval.

Do not silently weaken `require_clean_git`, compatibility, backup or mutation gates to accommodate an edit. If an authorized uncommitted patch makes the Git gate fail, stop and report that conflict for an environment-owner decision.

## Review compatibility findings

After every read-only runner pass, inspect `code-review.json` before closing on a later machine blocker. When `summary.review_required` is true, act as `compatibility-agent` and inspect `review_queue` in `review_rank` order. Group repeated occurrences, reproduce each defect, and propose the smallest correction with deterministic regression coverage. After the user approves the named batch, apply it under the remediation rules above, rerun `muk review-code` for the same run and preserve the new evidence.

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

## Preserve Git without automatic commits

- Use Git status, diff and log only for evidence and review.
- Never create a commit, tag, branch, push, merge, rebase, stash, PR or staged change as part of `/upgrade-moodle`.
- Do not invoke `git add` or `git commit`, including at successful completion. Leave authorized source/configuration edits visible in the working tree for human review.
- An exact environment-owned `code_transition_command` may run only through the guarded upgrade capability; it does not authorize creating or publishing commits.
- Record the starting HEAD, final HEAD and modified paths in the final response and Drive entry. State explicitly that no automatic commit was created.

This no-commit policy overrides any generic documentation workflow that recommends commits for an Enaex release.

## Publish documentation

Generate local `final-report.md` through the runner first. Google Drive is the durable human-facing record; local structured evidence remains the full technical audit trail. When the next capability is `moodle.document.sync`:

1. Use `$mantenedor-docs-enaex` for Enaex and the connected Google Drive/Docs tools.
2. Confirm target metadata, read before writing, preserve structure, write only confirmed/anonymized results, and read back the updated section.
3. Choose the publication scope from all run evidence:
   - `findings-and-outcomes` when any warning, error, critical, blocker, skipped/unknown check or remediation occurred. Group repeated findings and document severity, affected step/scope, confirmed cause or pending diagnosis, correction, validation, residual risk and next action. Do not paste raw logs or the complete command timeline.
   - `concise-clean-success` only when upgrade validation and QA are accepted with zero warnings, errors, critical findings or unresolved checks. Record run ID, source/target version, environment, result, QA totals, evidence reference and no-commit state; omit the step-by-step upgrade development.
4. For an upgrade attempt that stops failed or blocked after meaningful execution, update the same Drive run record with the findings and current outcome before closing, but do not claim the workflow is complete or record final synchronization.
5. At successful completion, build schema-version `1.0` sync JSON with `publication_scope` and `published_issue_count`, then run:

```bash
muk record-document-sync --config <config> --run-id <run-id> --input <sync-input.json>
```

Never record `verified: true` without a successful read-after-write. Moving, deleting, sharing, or changing permissions remains separately authorized. A full clean-run narration in Drive is a policy failure even if the connector write succeeds.

## Completion

Finish only when `agent-run.json.status` is `complete`. Report the run ID, target version, starting/final HEAD, modified paths, confirmation that no commit was created, QA totals, Drive resource, blockers resolved, residual warnings, and anything that remains externally unverified.
