from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Callable

from .database import run_database_checks
from .endpoints import run_endpoint_checks
from .logs import analyze_log_sources


@dataclass
class Finding:
    severity: str
    code: str
    message: str


def capture_baseline(
    config: dict[str, Any],
    inventory: dict[str, Any],
    endpoint_runner: Callable[[dict[str, Any]], list[dict]] | None = None,
    database_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    log_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    findings: list[Finding] = []
    inventory_summary = inventory.get("summary", {})
    identity = inventory.get("identity", {})
    if not identity.get("moodle_version", {}).get("release"):
        findings.append(Finding("critical", "BASELINE_IDENTITY_MISSING", "Inventory does not contain a proven Moodle release."))
    if int(inventory_summary.get("critical", 0) or 0) > 0:
        findings.append(Finding("critical", "BASELINE_INVENTORY_BLOCKED", "Inventory contains critical findings; baseline cannot be considered complete."))

    endpoint_runner = endpoint_runner or run_endpoint_checks
    database_runner = database_runner or run_database_checks
    log_runner = log_runner or analyze_log_sources

    endpoint_specs_list = config.get("endpoints", []) or []
    if not endpoint_specs_list:
        findings.append(Finding("critical", "BASELINE_ENDPOINTS_NOT_CONFIGURED", "Baseline requires at least one configured endpoint check."))
    endpoint_results = endpoint_runner(config)
    endpoint_specs = {str(spec.get("id", spec.get("path", "/"))): spec for spec in endpoint_specs_list}
    endpoint_executed = sum(1 for item in endpoint_results if item.get("executed", item.get("status") is not None))
    if endpoint_specs_list and endpoint_executed == 0:
        findings.append(Finding("critical", "BASELINE_ENDPOINTS_NOT_EXECUTED", "No configured endpoint check executed."))
    for item in endpoint_results:
        if item.get("ok"):
            continue
        spec = endpoint_specs.get(str(item.get("id")), {})
        severity = str(spec.get("severity", "critical"))
        findings.append(Finding(severity, "BASELINE_ENDPOINT_FAILED", f"Endpoint {item.get('id')} did not meet its expected status."))

    database_specs = config.get("database", {}).get("checks", []) or []
    if not database_specs:
        findings.append(Finding("critical", "BASELINE_DATABASE_NOT_CONFIGURED", "Baseline requires at least one configured read-only database check."))
    database = database_runner(config)
    database_executed = int(database.get("summary", {}).get("executed", 0) or 0)
    if database_specs and database_executed == 0:
        findings.append(Finding("critical", "BASELINE_DATABASE_NOT_EXECUTED", "No configured database check executed."))
    for finding in database.get("findings", []):
        if finding.get("severity") == "critical":
            findings.append(Finding("critical", "BASELINE_DATABASE_CRITICAL", finding.get("message", "Critical database baseline finding.")))
        elif finding.get("severity") == "warning":
            findings.append(Finding("warning", "BASELINE_DATABASE_WARNING", finding.get("message", "Database baseline warning.")))

    logs_cfg = config.get("logs", {}) or {}
    configured_log_sources = len(logs_cfg.get("files", []) or []) + len(logs_cfg.get("sources", []) or [])
    if configured_log_sources == 0:
        findings.append(Finding("critical", "BASELINE_LOGS_NOT_CONFIGURED", "Baseline requires at least one configured log source."))
    logs = log_runner(logs_cfg)
    unreadable = [item.get("id") or item.get("path") for item in logs.get("files", []) if not item.get("readable")]
    if unreadable:
        required_unreadable = any(item.get("required", logs_cfg.get("required", False)) and not item.get("readable") for item in logs.get("files", []))
        severity = "critical" if required_unreadable else "warning"
        findings.append(Finding(severity, "BASELINE_LOG_SOURCE_UNREADABLE", "Unreadable configured log source(s): " + ", ".join(map(str, unreadable))))
    log_executed = int(logs.get("summary", {}).get("readable", sum(1 for item in logs.get("files", []) if item.get("readable"))) or 0)
    if configured_log_sources and log_executed == 0:
        findings.append(Finding("critical", "BASELINE_LOGS_NOT_EXECUTED", "No configured log source could be read."))
    critical_log_count = int(logs.get("totals", {}).get("critical", 0) or 0)
    if critical_log_count and logs_cfg.get("fail_baseline_on_critical", False):
        findings.append(Finding("critical", "BASELINE_CRITICAL_LOGS", f"Baseline contains {critical_log_count} configured critical log signature occurrence(s)."))

    cron = inventory.get("cron", {})
    if cron.get("configured") and not cron.get("cli_exists"):
        findings.append(Finding("critical", "BASELINE_CRON_CLI_MISSING", "Configured Moodle cron command exists in configuration but admin/cli/cron.php was not found."))

    counts = Counter(f.severity for f in findings)
    return {
        "identity": {
            "project": identity.get("project"), "moodle_root": identity.get("moodle_root"),
            "moodledata": identity.get("moodledata"), "moodle_version": identity.get("moodle_version"),
            "target_version": identity.get("target_version"),
        },
        "endpoint_checks": endpoint_results,
        "database_checks": database,
        "log_checks": logs,
        "cron": cron,
        "definitions": {
            "endpoints": endpoint_specs_list,
            "database": [{key: value for key, value in spec.items() if key not in {"connection", "credentials"}} for spec in config.get("database", {}).get("checks", [])],
            "log_sources": [
                {"id": str(path), "type": "file", "path": str(path)} for path in logs_cfg.get("files", []) or []
            ] + [dict(source) for source in logs_cfg.get("sources", []) or []],
            "log_patterns": logs_cfg.get("patterns", {}),
        },
        "findings": [asdict(f) for f in findings],
        "summary": {
            "critical": counts["critical"], "warning": counts["warning"], "info": counts["info"],
            "endpoint_configured": len(endpoint_specs_list), "endpoint_executed": endpoint_executed,
            "database_configured": len(database_specs), "database_executed": database_executed,
            "log_configured": configured_log_sources, "log_executed": log_executed,
            "complete": counts["critical"] == 0,
        },
    }
