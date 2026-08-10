from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit


_CASE_STATUSES = {"passed", "failed", "blocked", "not-applicable"}
_SEVERITIES = {"critical", "warning", "info"}
_FORBIDDEN_KEYS = re.compile(r"(?i)(password|passwd|secret|token|cookie|authorization|private.?key)")
_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
_RUT = re.compile(r"(?i)\b\d{1,2}\.?\d{3}\.?\d{3}-[0-9k]\b")


def _assert_no_sensitive_data(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if _FORBIDDEN_KEYS.search(str(key)):
                raise ValueError(f"Sensitive field is not allowed in QA evidence: {path}.{key}")
            _assert_no_sensitive_data(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_sensitive_data(item, f"{path}[{index}]")
    elif isinstance(value, str) and (_EMAIL.search(value) or _RUT.search(value)):
        raise ValueError(f"Potential participant data is not allowed in QA evidence: {path}")


def _text(value: Any, field: str, *, required: bool = True, max_length: int = 2000) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"{field} must be a non-empty string")
    output = value.strip()
    if len(output) > max_length:
        raise ValueError(f"{field} exceeds {max_length} characters")
    return output


def record_qa_result(config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("QA input must be a JSON object")
    _assert_no_sensitive_data(payload)
    if str(payload.get("schema_version")) != "1.0":
        raise ValueError("QA input must use schema_version 1.0")
    environment = _text(payload.get("environment"), "environment")
    target_version = _text(payload.get("target_version"), "target_version")
    if environment != str(config.get("project", {}).get("environment")):
        raise ValueError("QA environment does not match configuration")
    if target_version != str(config.get("moodle", {}).get("target_version")):
        raise ValueError("QA target_version does not match configuration")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("QA input requires at least one case")

    cases: list[dict[str, Any]] = []
    case_ids: set[str] = set()
    for index, raw in enumerate(raw_cases):
        if not isinstance(raw, dict):
            raise ValueError(f"cases[{index}] must be an object")
        unknown = set(raw) - {"id", "area", "severity", "status", "expected", "observed", "evidence"}
        if unknown:
            raise ValueError(f"cases[{index}] contains unsupported fields: {', '.join(sorted(unknown))}")
        case_id = _text(raw.get("id"), f"cases[{index}].id", max_length=120)
        if case_id in case_ids:
            raise ValueError(f"Duplicate QA case id: {case_id}")
        case_ids.add(case_id)
        status = _text(raw.get("status"), f"cases[{index}].status")
        severity = _text(raw.get("severity", "warning"), f"cases[{index}].severity")
        if status not in _CASE_STATUSES:
            raise ValueError(f"Unsupported QA case status: {status}")
        if severity not in _SEVERITIES:
            raise ValueError(f"Unsupported QA case severity: {severity}")
        evidence = raw.get("evidence", []) or []
        if not isinstance(evidence, list) or any(not isinstance(item, str) or not item.strip() for item in evidence):
            raise ValueError(f"cases[{index}].evidence must be a list of non-empty references")
        cases.append({
            "id": case_id,
            "area": _text(raw.get("area"), f"cases[{index}].area", max_length=120),
            "severity": severity,
            "status": status,
            "expected": _text(raw.get("expected"), f"cases[{index}].expected"),
            "observed": _text(raw.get("observed"), f"cases[{index}].observed"),
            "evidence": [item.strip() for item in evidence],
        })

    configured_cases = {
        str(case.get("id")): case
        for case in (config.get("qa", {}) or {}).get("cases", []) or []
        if isinstance(case, dict) and case.get("id")
    }
    configured_case_ids = set(configured_cases)
    missing_case_ids = sorted(configured_case_ids - case_ids)
    if missing_case_ids:
        raise ValueError("QA input is missing configured cases: " + ", ".join(missing_case_ids))

    counts = {status: sum(case["status"] == status for case in cases) for status in sorted(_CASE_STATUSES)}
    failed_critical = sum(case["status"] == "failed" and case["severity"] == "critical" for case in cases)
    status_by_id = {case["id"]: case["status"] for case in cases}
    required_not_executed = sorted(
        case_id
        for case_id, definition in configured_cases.items()
        if definition.get("required", True) and status_by_id.get(case_id) == "not-applicable"
    )
    complete = (
        counts["passed"] + counts["failed"] > 0
        and counts["blocked"] == 0
        and not required_not_executed
    )
    accepted = complete and counts["failed"] == 0
    findings = []
    if counts["blocked"]:
        findings.append({"severity": "critical", "code": "QA_CASES_BLOCKED", "message": f"{counts['blocked']} QA case(s) remain blocked."})
    if counts["failed"]:
        findings.append({"severity": "critical" if failed_critical else "warning", "code": "QA_CASES_FAILED", "message": f"{counts['failed']} QA case(s) failed."})
    if required_not_executed:
        findings.append({
            "severity": "critical",
            "code": "QA_REQUIRED_CASES_NOT_EXECUTED",
            "message": "Required QA cases were marked not-applicable: " + ", ".join(required_not_executed),
        })
    return {
        "schema_version": "1.0",
        "agent": "qa-agent",
        "capability": "moodle.qa",
        "effect": "controlled-validation",
        "environment": environment,
        "target_version": target_version,
        "cases": cases,
        "findings": findings,
        "summary": {
            "case_count": len(cases),
            **{f"{status.replace('-', '_')}_count": count for status, count in counts.items()},
            "critical_failure_count": failed_critical,
            "configured_case_count": len(configured_case_ids),
            "configured_coverage_complete": not missing_case_ids,
            "required_not_executed_count": len(required_not_executed),
            "complete": complete,
            "accepted": accepted,
        },
    }


def record_document_sync(config: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Document sync input must be a JSON object")
    _assert_no_sensitive_data(payload)
    allowed = {"schema_version", "provider", "status", "resource_id", "url", "verified"}
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError("Document sync input contains unsupported fields: " + ", ".join(sorted(unknown)))
    if str(payload.get("schema_version")) != "1.0":
        raise ValueError("Document sync input must use schema_version 1.0")
    provider = _text(payload.get("provider"), "provider", max_length=80)
    configured_provider = str((config.get("documentation", {}) or {}).get("provider") or "")
    if provider != configured_provider:
        raise ValueError("Document sync provider does not match configuration")
    status = _text(payload.get("status"), "status", max_length=40)
    if status not in {"complete", "failed"}:
        raise ValueError("Document sync status must be complete or failed")
    resource_id = _text(payload.get("resource_id"), "resource_id", required=False, max_length=200)
    if resource_id and not re.fullmatch(r"[A-Za-z0-9_-]+", resource_id):
        raise ValueError("Document sync resource_id contains unsupported characters")
    url = _text(payload.get("url"), "url", required=False, max_length=1000)
    if url:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password or parsed.query:
            raise ValueError("Document sync URL must be a credential-free HTTPS URL without query parameters")
    verified = payload.get("verified") is True
    complete = status == "complete" and verified and bool(resource_id or url)
    findings = [] if complete else [{
        "severity": "warning",
        "code": "DOCUMENT_SYNC_UNVERIFIED" if status == "complete" else "DOCUMENT_SYNC_FAILED",
        "message": "External documentation synchronization was not verified as complete.",
    }]
    return {
        "schema_version": "1.0",
        "agent": "documentation-agent",
        "capability": "moodle.document.sync",
        "effect": "external-artifact-write",
        "provider": provider,
        "status": status,
        "resource_id": resource_id or None,
        "url": url or None,
        "verified": verified,
        "findings": findings,
        "summary": {"complete": complete},
    }
