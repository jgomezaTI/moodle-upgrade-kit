from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Callable

from .execution import command_argv, mutation_preconditions, run_command


@dataclass
class Finding:
    severity: str
    code: str
    message: str


def upgrade_steps(config: dict[str, Any]) -> list[dict[str, Any]]:
    moodle = config.get("moodle", {}) or {}
    upgrade_cfg = config.get("upgrade", {}) or {}
    definitions = [
        ("maintenance_on", moodle.get("maintenance_mode_command"), True),
        ("code_transition", upgrade_cfg.get("code_transition_command"), True),
        ("moodle_upgrade", moodle.get("upgrade_command"), True),
        ("purge_caches", moodle.get("purge_caches_command"), True),
        ("cron", moodle.get("cron_command"), bool(upgrade_cfg.get("run_cron_after", True))),
        ("maintenance_off", moodle.get("maintenance_off_command"), True),
    ]
    return [{"id": step_id, "command": command, "required": True} for step_id, command, enabled in definitions if enabled]


def render_upgrade_plan(config: dict[str, Any]) -> str:
    lines = [
        "# Moodle Upgrade Plan", "", f"Project: {config.get('project', {}).get('name')}",
        f"Environment: {config.get('project', {}).get('environment')}",
        f"Target Moodle: {config.get('moodle', {}).get('target_version')}", "",
        "This plan is generated before execution. It does not imply approval.", "", "## Steps", "",
    ]
    for number, step in enumerate(upgrade_steps(config), start=1):
        command = step.get("command")
        if command:
            try:
                display = " ".join(command_argv(command))
            except ValueError as exc:
                display = f"[INVALID COMMAND: {exc}]"
        else:
            display = "[MISSING]"
        lines.append(f"{number}. `{step['id']}` — `{display}`")
    lines.append("")
    return "\n".join(lines)


def execute_upgrade(
    config: dict[str, Any],
    approved: bool,
    inventory: dict[str, Any] | None,
    compatibility: dict[str, Any] | None,
    backup: dict[str, Any] | None,
    baseline: dict[str, Any] | None = None,
    plugins: dict[str, Any] | None = None,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    findings = [Finding(**item) for item in upgrade_preconditions(
        config, approved, inventory, compatibility, backup, baseline, plugins,
    )]

    if findings:
        counts = Counter(f.severity for f in findings)
        return {"approved": approved, "executed": False, "steps": [], "findings": [asdict(f) for f in findings], "summary": {"critical": counts["critical"], "warning": counts["warning"], "completed": False}}

    steps = upgrade_steps(config)
    results: list[dict[str, Any]] = []
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
            findings.append(Finding("critical", "UPGRADE_STEP_FAILED", f"Upgrade step {step['id']} failed; subsequent steps were not executed."))
    completed = not failed and all(item.get("ok") for item in results)
    counts = Counter(f.severity for f in findings)
    return {"approved": approved, "executed": True, "steps": results, "findings": [asdict(f) for f in findings], "summary": {"critical": counts["critical"], "warning": counts["warning"], "completed": completed}}


def upgrade_preconditions(
    config: dict[str, Any],
    approved: bool,
    inventory: dict[str, Any] | None,
    compatibility: dict[str, Any] | None,
    backup: dict[str, Any] | None,
    baseline: dict[str, Any] | None = None,
    plugins: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Return every deterministic upgrade blocker without executing a command."""
    findings = [Finding(**item) for item in mutation_preconditions(config, approved, inventory, compatibility, backup)]
    if not baseline or not baseline.get("summary", {}).get("complete", False):
        findings.append(Finding("critical", "BASELINE_NOT_PASSED", "A complete pre-upgrade baseline is required before mutation."))
    if not plugins or int(plugins.get("summary", {}).get("critical", 0) or 0) > 0:
        findings.append(Finding("critical", "PLUGIN_REVIEW_NOT_PASSED", "Plugin/custom-code analysis without critical findings is required before mutation."))
    steps = upgrade_steps(config)
    for step in steps:
        if not step.get("command"):
            findings.append(Finding("critical", "UPGRADE_COMMAND_MISSING", f"Required upgrade step {step['id']} has no configured command."))
        else:
            try:
                command_argv(step["command"])
            except ValueError as exc:
                findings.append(Finding("critical", "UPGRADE_COMMAND_INVALID", f"{step['id']}: {exc}"))
    return [asdict(f) for f in findings]
