from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import re
from typing import Any


@dataclass
class Finding:
    severity: str
    code: str
    message: str


def _branch(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(\d+)\.(\d+)", str(value))
    return f"{match.group(1)}.{match.group(2)}" if match else None


def _endpoint_regressions(before: list[dict], after: list[dict]) -> list[str]:
    pre = {str(item.get("id")): item for item in before}
    post = {str(item.get("id")): item for item in after}
    return [check_id for check_id, item in pre.items() if item.get("ok") and (check_id not in post or not post[check_id].get("ok"))]


def _database_regressions(before: dict, after: dict) -> list[str]:
    pre = {str(item.get("id")): item for item in before.get("checks", [])}
    post = {str(item.get("id")): item for item in after.get("checks", [])}
    regressions = []
    for check_id, item in pre.items():
        if item.get("executed") and item.get("ok"):
            post_item = post.get(check_id)
            if not post_item or not post_item.get("executed") or not post_item.get("ok"):
                regressions.append(check_id)
    return regressions


def _log_regressions(before: dict, after: dict) -> dict[str, int]:
    before_totals = before.get("totals", {}) or {}
    after_totals = after.get("totals", {}) or {}
    regressions = {}
    for severity in set(before_totals) | set(after_totals):
        delta = int(after_totals.get(severity, 0) or 0) - int(before_totals.get(severity, 0) or 0)
        if delta > 0:
            regressions[severity] = delta
    return regressions


def validate_upgrade(
    config: dict[str, Any], baseline: dict[str, Any] | None, inventory_after: dict[str, Any] | None,
    endpoints_after: list[dict] | None, logs_after: dict[str, Any] | None,
    database_after: dict[str, Any] | None, mode: str = "upgrade",
) -> dict[str, Any]:
    findings: list[Finding] = []
    required = {"baseline-before": baseline, "inventory-after": inventory_after, "endpoints-after": endpoints_after, "logs-after": logs_after, "database-after": database_after}
    missing = [name for name, value in required.items() if value is None]
    if missing:
        findings.append(Finding("critical", "VALIDATION_EVIDENCE_MISSING", "Missing required evidence: " + ", ".join(missing)))

    target = config.get("moodle", {}).get("target_version")
    observed_release = (inventory_after or {}).get("identity", {}).get("moodle_version", {}).get("release")
    expected_branch = _branch(target)
    observed_branch = _branch(observed_release)
    target_confirmed = bool(expected_branch and observed_branch == expected_branch)
    rollback_release = (baseline or {}).get("identity", {}).get("moodle_version", {}).get("release")
    rollback_branch = _branch(rollback_release)
    rollback_confirmed = bool(rollback_branch and observed_branch == rollback_branch)
    if mode == "upgrade" and not target_confirmed:
        findings.append(Finding("critical", "TARGET_VERSION_NOT_CONFIRMED", f"Expected Moodle {expected_branch}; post-upgrade inventory reports {observed_release!r}."))
    if mode == "rollback" and not rollback_confirmed:
        findings.append(Finding("critical", "ROLLBACK_VERSION_NOT_CONFIRMED", f"Expected restored Moodle {rollback_branch}; post-rollback inventory reports {observed_release!r}."))
    if inventory_after and int(inventory_after.get("summary", {}).get("critical", 0) or 0):
        findings.append(Finding("critical", "POST_INVENTORY_CRITICAL", "Post-change inventory contains critical findings."))

    endpoint_regressions: list[str] = []
    database_regressions: list[str] = []
    log_regressions: dict[str, int] = {}
    if baseline and endpoints_after is not None:
        endpoint_regressions = _endpoint_regressions(baseline.get("endpoint_checks", []), endpoints_after)
        if endpoint_regressions:
            findings.append(Finding("critical", "ENDPOINT_REGRESSION", "Previously passing endpoint checks now fail: " + ", ".join(endpoint_regressions)))
    if baseline and database_after is not None:
        database_regressions = _database_regressions(baseline.get("database_checks", {}), database_after)
        if database_regressions:
            findings.append(Finding("critical", "DATABASE_REGRESSION", "Previously passing database checks now fail: " + ", ".join(database_regressions)))
    if baseline and logs_after is not None:
        log_regressions = _log_regressions(baseline.get("log_checks", {}), logs_after)
        if log_regressions.get("critical", 0):
            findings.append(Finding("critical", "CRITICAL_LOG_REGRESSION", f"Critical log signatures increased by {log_regressions['critical']}."))
        if log_regressions.get("warning", 0):
            findings.append(Finding("warning", "WARNING_LOG_REGRESSION", f"Warning log signatures increased by {log_regressions['warning']}."))

    if database_after and int(database_after.get("summary", {}).get("critical", 0) or 0):
        findings.append(Finding("critical", "POST_DATABASE_CRITICAL", "Post-change database validation contains critical findings."))
    if endpoints_after is not None:
        newly_failing = [str(item.get("id")) for item in endpoints_after if not item.get("ok")]
        pre_ids = {str(item.get("id")) for item in (baseline or {}).get("endpoint_checks", [])}
        new_only = [item for item in newly_failing if item not in pre_ids]
        if new_only:
            findings.append(Finding("critical", "NEW_ENDPOINT_FAILURE", "New post-change endpoint failures: " + ", ".join(new_only)))

    counts = Counter(f.severity for f in findings)
    accepted = counts["critical"] == 0 and not missing and ((mode == "upgrade" and target_confirmed) or (mode == "rollback" and rollback_confirmed))
    return {
        "mode": mode, "target_version": target, "observed_version": observed_release,
        "target_confirmed": target_confirmed, "rollback_confirmed": rollback_confirmed,
        "regressions": {"endpoints": endpoint_regressions, "database": database_regressions, "logs": log_regressions},
        "findings": [asdict(f) for f in findings],
        "summary": {"critical": counts["critical"], "warning": counts["warning"], "info": counts["info"], "accepted": accepted},
    }
