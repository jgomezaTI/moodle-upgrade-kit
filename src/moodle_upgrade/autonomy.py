from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from .agents import orchestrate_agents
from .backup import verify_backups
from .baseline import capture_baseline
from .compatibility import assess_compatibility
from .database import run_database_checks
from .document import generate_report
from .endpoints import run_endpoint_checks
from .evidence import read_json, write_json
from .inventory import collect_inventory
from .logs import analyze_log_sources
from .plugins import analyze_plugins
from .review import build_code_review_queue
from .rollback import execute_rollback, render_rollback_plan
from .upgrade import execute_upgrade, render_upgrade_plan
from .validate import validate_upgrade


EXTERNAL_CAPABILITIES = {"moodle.qa", "moodle.document.sync"}
ActionExecutor = Callable[[dict[str, Any], dict[str, Any], Path, dict[str, bool]], None]


def _required(run_path: Path, name: str, fallback: str | None = None) -> Any:
    path = run_path / name
    if path.is_file():
        return read_json(path)
    if fallback and (run_path / fallback).is_file():
        return read_json(run_path / fallback)
    raise FileNotFoundError(f"Required evidence missing: {name}")


def execute_agent_action(action: dict[str, Any], config: dict[str, Any], run_path: Path, approvals: dict[str, bool]) -> None:
    capability = action["capability"]
    parameters = action.get("parameters", {}) or {}
    if capability in EXTERNAL_CAPABILITIES:
        raise ValueError(f"External capability requires the chat agent: {capability}")
    if capability == "moodle.inventory":
        phase = parameters.get("phase", "before")
        result = collect_inventory(config)
        write_json(run_path / f"inventory-{phase}.json", result)
        if phase == "before":
            write_json(run_path / "inventory.json", result)
    elif capability == "moodle.compatibility":
        inventory = _required(run_path, "inventory-before.json", "inventory.json")
        write_json(run_path / "compatibility.json", assess_compatibility(inventory, config["moodle"]["target_version"]))
    elif capability == "moodle.plugins":
        inventory = _required(run_path, "inventory-before.json", "inventory.json")
        plugins = analyze_plugins(config, inventory)
        write_json(run_path / "plugins.json", plugins)
        review = build_code_review_queue(config, plugins)
        review["inventory_refreshed"] = False
        write_json(run_path / "code-review.json", review)
    elif capability == "moodle.baseline":
        inventory = _required(run_path, "inventory-before.json", "inventory.json")
        baseline = capture_baseline(config, inventory)
        write_json(run_path / "endpoints-before.json", baseline["endpoint_checks"])
        write_json(run_path / "logs-before.json", baseline["log_checks"])
        write_json(run_path / "database-before.json", baseline["database_checks"])
        write_json(run_path / "baseline-before.json", baseline)
    elif capability == "moodle.backup":
        write_json(run_path / "backup.json", verify_backups(config))
    elif capability == "moodle.upgrade":
        (run_path / "upgrade-plan.md").write_text(render_upgrade_plan(config), encoding="utf-8")
        result = execute_upgrade(
            config,
            approvals["pre_upgrade"],
            _required(run_path, "inventory-before.json", "inventory.json"),
            _required(run_path, "compatibility.json"),
            _required(run_path, "backup.json"),
            baseline=_required(run_path, "baseline-before.json"),
            plugins=_required(run_path, "plugins.json"),
        )
        write_json(run_path / "upgrade-result.json", result)
    elif capability == "moodle.rollback":
        (run_path / "rollback-plan.md").write_text(render_rollback_plan(config), encoding="utf-8")
        result = execute_rollback(
            config,
            approvals["rollback"],
            _required(run_path, "backup.json"),
            read_json(run_path / "validation.json") if (run_path / "validation.json").is_file() else None,
            force=approvals["force_rollback"],
        )
        write_json(run_path / "rollback-result.json", result)
    elif capability == "moodle.endpoints":
        phase = parameters.get("phase", "before")
        write_json(run_path / f"endpoints-{phase}.json", run_endpoint_checks(config))
    elif capability == "moodle.logs":
        phase = parameters.get("phase", "before")
        write_json(run_path / f"logs-{phase}.json", analyze_log_sources(config.get("logs", {})))
    elif capability == "moodle.database":
        phase = parameters.get("phase", "before")
        write_json(run_path / f"database-{phase}.json", run_database_checks(config))
    elif capability == "moodle.validate":
        mode = parameters.get("mode", "upgrade")
        result = validate_upgrade(
            config,
            _required(run_path, "baseline-before.json"),
            _required(run_path, "inventory-after.json"),
            _required(run_path, "endpoints-after.json"),
            _required(run_path, "logs-after.json"),
            _required(run_path, "database-after.json"),
            mode=mode,
        )
        write_json(run_path / "validation.json", result)
    elif capability == "moodle.document":
        markdown, result = generate_report(config, run_path.name, base_dir=run_path.parent)
        (run_path / "final-report.md").write_text(markdown + "\n", encoding="utf-8")
        write_json(run_path / "document-result.json", result)
    else:
        raise ValueError(f"No autonomous executor for capability: {capability}")


def run_agent_workflow(
    config: dict[str, Any],
    run_id: str,
    run_path: Path,
    *,
    workflow: str = "upgrade",
    agents_dir: str | Path = "agents",
    pre_upgrade_approved: bool = False,
    acceptance_approved: bool = False,
    rollback_approved: bool = False,
    force_rollback: bool = False,
    max_steps: int = 32,
    executor: ActionExecutor = execute_agent_action,
) -> dict[str, Any]:
    if max_steps < 1 or max_steps > 100:
        raise ValueError("max_steps must be between 1 and 100")
    approvals = {
        "pre_upgrade": pre_upgrade_approved,
        "acceptance": acceptance_approved,
        "rollback": rollback_approved,
        "force_rollback": force_rollback,
    }
    metadata_path = run_path / "metadata.json"
    if not metadata_path.is_file():
        write_json(metadata_path, {
            "run_id": run_id,
            "project": config["project"],
            "target_version": config["moodle"]["target_version"],
            "moodle_root": config["moodle"]["root"],
            "base_url": config["moodle"]["base_url"],
        })
    plugins_path = run_path / "plugins.json"
    review_path = run_path / "code-review.json"
    if plugins_path.is_file() and (
        not review_path.is_file() or review_path.stat().st_mtime < plugins_path.stat().st_mtime
    ):
        review = build_code_review_queue(config, read_json(plugins_path))
        review["inventory_refreshed"] = False
        write_json(review_path, review)

    history: list[dict[str, Any]] = []
    state: dict[str, Any] = {}
    status = "failed"
    findings: list[dict[str, str]] = []
    for sequence in range(1, max_steps + 1):
        state = orchestrate_agents(
            config,
            run_path,
            workflow=workflow,
            pre_upgrade_approved=pre_upgrade_approved,
            acceptance_approved=acceptance_approved,
            rollback_approved=rollback_approved,
            force_rollback=force_rollback,
            agents_dir=agents_dir,
        )
        write_json(run_path / "agent-state.json", state)
        action = state.get("next_action")
        if state.get("status") != "action_required" or not action:
            status = str(state.get("status") or "failed")
            break
        capability = str(action.get("capability"))
        if capability in EXTERNAL_CAPABILITIES:
            status = "external_action_required"
            break
        try:
            executor(action, config, run_path, approvals)
        except Exception as exc:
            status = "failed"
            findings.append({
                "severity": "critical",
                "code": "AUTONOMOUS_ACTION_FAILED",
                "message": f"{capability} failed with {type(exc).__name__}; inspect the capability evidence and local logs.",
            })
            break
        expected = str(action.get("expected_evidence") or "")
        evidence_created = bool(expected and (run_path / expected).is_file())
        history.append({
            "sequence": sequence,
            "agent": action.get("agent"),
            "capability": capability,
            "expected_evidence": expected,
            "evidence_created": evidence_created,
        })
        if not evidence_created:
            status = "failed"
            findings.append({
                "severity": "critical",
                "code": "AUTONOMOUS_EVIDENCE_MISSING",
                "message": f"{capability} returned without creating {expected}.",
            })
            break
    else:
        status = "failed"
        findings.append({
            "severity": "critical",
            "code": "AUTONOMOUS_STEP_LIMIT",
            "message": f"Workflow exceeded the configured {max_steps}-step limit.",
        })

    result = {
        "schema_version": "1.0",
        "run_id": run_id,
        "workflow": workflow,
        "status": status,
        "effect": "gated-orchestration",
        "started_by": "upgrade-moodle",
        "history": history,
        "next_action": state.get("next_action"),
        "human_gate": state.get("human_gate"),
        "blockers": state.get("blockers", []),
        "findings": findings,
        "approvals": approvals,
        "summary": {
            "executed_action_count": len(history),
            "blocked": status == "blocked",
            "human_gate_required": status == "human_gate",
            "external_action_required": status == "external_action_required",
            "complete": status == "complete",
            "failed": status == "failed",
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    write_json(run_path / "agent-run.json", result)
    return result
