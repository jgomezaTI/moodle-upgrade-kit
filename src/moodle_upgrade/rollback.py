from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Callable

from .execution import command_argv, run_command


@dataclass
class Finding:
    severity: str
    code: str
    message: str


def rollback_steps(config: dict[str, Any]) -> list[dict[str, Any]]:
    moodle = config.get("moodle", {}) or {}
    rollback_cfg = config.get("rollback", {}) or {}
    steps = [{"id": "maintenance_on", "command": moodle.get("maintenance_mode_command")}]
    for index, command in enumerate(rollback_cfg.get("commands", []) or [], start=1):
        steps.append({"id": f"restore_{index}", "command": command})
    steps.append({"id": "maintenance_off", "command": moodle.get("maintenance_off_command")})
    return steps


def render_rollback_plan(config: dict[str, Any]) -> str:
    lines = [
        "# Moodle Rollback Plan", "", f"Project: {config.get('project', {}).get('name')}",
        f"Environment: {config.get('project', {}).get('environment')}", "",
        "Restore commands are explicit configuration. No restore procedure is inferred from backup filenames.", "", "## Steps", "",
    ]
    for number, step in enumerate(rollback_steps(config), start=1):
        try:
            display = " ".join(command_argv(step.get("command"))) if step.get("command") else "[MISSING]"
        except ValueError as exc:
            display = f"[INVALID COMMAND: {exc}]"
        lines.append(f"{number}. `{step['id']}` — `{display}`")
    lines.append("")
    return "\n".join(lines)


def rollback_preconditions(
    config: dict[str, Any], approved: bool, backup: dict[str, Any] | None,
    validation: dict[str, Any] | None, force: bool,
) -> list[dict[str, str]]:
    """Return every deterministic rollback blocker without executing a command."""
    safety = config.get("safety", {}) or {}
    findings: list[Finding] = []
    if not safety.get("allow_mutation", False):
        findings.append(Finding("critical", "MUTATION_DISABLED", "safety.allow_mutation is false."))
    required_env = safety.get("require_environment")
    actual_env = config.get("project", {}).get("environment")
    if required_env and actual_env != required_env:
        findings.append(Finding("critical", "ENVIRONMENT_NOT_ALLOWED", f"Rollback requires environment {required_env!r}; current environment is {actual_env!r}."))
    if safety.get("require_human_gate", True) and not approved:
        findings.append(Finding("critical", "HUMAN_APPROVAL_REQUIRED", "Explicit rollback approval was not supplied."))
    if not backup or not backup.get("summary", {}).get("verified", False):
        findings.append(Finding("critical", "BACKUP_NOT_VERIFIED", "Verified backup evidence is required for rollback."))
    if not force:
        if not validation:
            findings.append(Finding("critical", "ROLLBACK_DECISION_REQUIRED", "Rejected validation evidence or --force is required to justify rollback."))
        elif validation.get("summary", {}).get("accepted", False):
            findings.append(Finding("critical", "ROLLBACK_VALIDATION_NOT_REJECTED", "Validation is accepted; use an explicit forced rollback decision if rollback is still required."))
    steps = rollback_steps(config)
    restore_steps = [step for step in steps if step["id"] not in {"maintenance_on", "maintenance_off"}]
    if not restore_steps:
        findings.append(Finding("critical", "ROLLBACK_PROCEDURE_MISSING", "rollback.commands must explicitly define at least one restore step."))
    for step in steps:
        if not step.get("command"):
            findings.append(Finding("critical", "ROLLBACK_COMMAND_MISSING", f"Rollback step {step['id']} is missing its command."))
        else:
            try:
                command_argv(step["command"])
            except ValueError as exc:
                findings.append(Finding("critical", "ROLLBACK_COMMAND_INVALID", f"{step['id']}: {exc}"))
    return [asdict(f) for f in findings]


def execute_rollback(
    config: dict[str, Any], approved: bool, backup: dict[str, Any] | None,
    validation: dict[str, Any] | None, force: bool = False, runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    findings = [Finding(**item) for item in rollback_preconditions(config, approved, backup, validation, force)]
    steps = rollback_steps(config)
    if findings:
        counts = Counter(f.severity for f in findings)
        return {"approved": approved, "force": force, "executed": False, "steps": [], "findings": [asdict(f) for f in findings], "summary": {"critical": counts["critical"], "restored": False, "validation_required": True}}

    results = []
    failed = False
    for step in steps:
        if failed:
            results.append({"id": step["id"], "executed": False, "ok": False, "skipped": True, "reason": "previous step failed"})
            continue
        result = run_command(config, step["command"], runner=runner)
        result.update({"id": step["id"], "executed": True})
        results.append(result)
        if not result.get("ok"):
            failed = True
            findings.append(Finding("critical", "ROLLBACK_STEP_FAILED", f"Rollback step {step['id']} failed; remaining steps were not executed."))
    restored = not failed and all(item.get("ok") for item in results)
    counts = Counter(f.severity for f in findings)
    return {
        "approved": approved, "force": force, "executed": True, "steps": results,
        "findings": [asdict(f) for f in findings],
        "summary": {"critical": counts["critical"], "restored": restored, "validation_required": True, "completed": False},
    }
