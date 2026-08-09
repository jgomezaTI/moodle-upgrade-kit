from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any, Callable

from .database import run_database_checks
from .endpoints import run_endpoint_checks
from .logs import analyze_files


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
    log_runner: Callable[[list[str], dict[str, list[str]]], dict[str, Any]] | None = None,
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
    log_runner = log_runner or analyze_files

    endpoint_results = endpoint_runner(config)
    endpoint_specs = {str(spec.get("id", spec.get("path", "/"))): spec for spec in config.get("endpoints", [])}
    for item in endpoint_results:
        if item.get("ok"):
            continue
        spec = endpoint_specs.get(str(item.get("id")), {})
        severity = str(spec.get("severity", "critical"))
        findings.append(Finding(severity, "BASELINE_ENDPOINT_FAILED", f"Endpoint {item.get('id')} did not meet its expected status."))

    database = database_runner(config)
    for finding in database.get("findings", []):
        if finding.get("severity") == "critical":
            findings.append(Finding("critical", "BASELINE_DATABASE_CRITICAL", finding.get("message", "Critical database baseline finding.")))
        elif finding.get("severity") == "warning":
            findings.append(Finding("warning", "BASELINE_DATABASE_WARNING", finding.get("message", "Database baseline warning.")))

    logs_cfg = config.get("logs", {}) or {}
    logs = log_runner(logs_cfg.get("files", []), logs_cfg.get("patterns", {}))
    unreadable = [item.get("path") for item in logs.get("files", []) if not item.get("readable")]
    if unreadable:
        severity = "critical" if logs_cfg.get("required", False) else "warning"
        findings.append(Finding(severity, "BASELINE_LOG_SOURCE_UNREADABLE", "Unreadable configured log source(s): " + ", ".join(map(str, unreadable))))
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
            "endpoints": config.get("endpoints", []),
            "database": [{key: value for key, value in spec.items() if key not in {"connection", "credentials"}} for spec in config.get("database", {}).get("checks", [])],
            "log_patterns": logs_cfg.get("patterns", {}),
        },
        "findings": [asdict(f) for f in findings],
        "summary": {"critical": counts["critical"], "warning": counts["warning"], "info": counts["info"], "complete": counts["critical"] == 0},
    }
