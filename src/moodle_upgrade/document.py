from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
import json
import re
from typing import Any


@dataclass
class Finding:
    severity: str
    code: str
    message: str


EVIDENCE_FILES = [
    "inventory-before.json", "inventory.json", "compatibility.json", "plugins.json", "code-review.json", "baseline-before.json",
    "backup.json", "upgrade-result.json", "inventory-after.json", "endpoints-after.json", "logs-after.json",
    "database-after.json", "validation.json", "qa-result.json", "rollback-result.json",
]


def _load(path: Path) -> Any:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("data", raw)


def _redact(text: str, patterns: list[str]) -> str:
    output = text
    defaults = [r"(?i)(password|passwd|token|secret)\s*[:=]\s*\S+", r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+"]
    for pattern in [*defaults, *patterns]:
        try:
            output = re.sub(pattern, "[REDACTED]", output)
        except re.error:
            output = output.replace(pattern, "[REDACTED]")
    return output


def generate_report(config: dict[str, Any], run_id: str, base_dir: str | Path = "runs") -> tuple[str, dict[str, Any]]:
    run = Path(base_dir) / run_id
    findings: list[Finding] = []
    evidence: dict[str, Any] = {}
    for name in EVIDENCE_FILES:
        path = run / name
        if path.is_file():
            try:
                evidence[name] = _load(path)
            except (OSError, json.JSONDecodeError) as exc:
                findings.append(Finding("warning", "REPORT_EVIDENCE_UNREADABLE", f"{name}: {type(exc).__name__}"))

    validation = evidence.get("validation.json")
    upgrade = evidence.get("upgrade-result.json")
    rollback = evidence.get("rollback-result.json")
    if validation:
        overall = "PASS" if validation.get("summary", {}).get("accepted") else "FAIL"
    elif rollback and rollback.get("summary", {}).get("restored"):
        overall = "ROLLBACK_RESTORED_PENDING_VALIDATION"
    elif upgrade and upgrade.get("summary", {}).get("completed"):
        overall = "UPGRADE_COMPLETED_PENDING_VALIDATION"
    else:
        overall = "INCOMPLETE"

    docs_cfg = config.get("documentation", {}) or {}
    provider = docs_cfg.get("provider")
    sync = {"provider": provider, "status": "not-configured"}
    if provider:
        sync["status"] = "external-adapter-required"
        if docs_cfg.get("require_sync", False):
            findings.append(Finding("warning", "DOCUMENT_SYNC_PENDING", f"Documentation provider {provider!r} requires an external authenticated adapter; local report was preserved."))

    lines = [
        "# Moodle Upgrade Evidence Report", "", f"- Run ID: `{run_id}`",
        f"- Project: `{config.get('project', {}).get('name')}`", f"- Environment: `{config.get('project', {}).get('environment')}`",
        f"- Target Moodle: `{config.get('moodle', {}).get('target_version')}`", f"- Result: **{overall}**", "", "## Evidence", "",
    ]
    for name in EVIDENCE_FILES:
        payload = evidence.get(name)
        if payload is None:
            continue
        summary = payload.get("summary") if isinstance(payload, dict) else None
        lines.append(f"- `{name}`: `{json.dumps(summary, sort_keys=True, ensure_ascii=False)}`" if summary is not None else f"- `{name}`: present")

    lines.extend(["", "## Findings", ""])
    collected = []
    for name, payload in evidence.items():
        if isinstance(payload, dict):
            for finding in payload.get("findings", []) or []:
                collected.append((name, finding))
    if not collected and not findings:
        lines.append("- No structured findings were recorded in available evidence.")
    for name, finding in collected:
        lines.append(f"- **{finding.get('severity', 'unknown').upper()}** `{finding.get('code', 'UNKNOWN')}` ({name}): {finding.get('message', '')}")
    for finding in findings:
        lines.append(f"- **{finding.severity.upper()}** `{finding.code}`: {finding.message}")

    lines.extend(["", "## Documentation synchronization", "", f"- Provider: `{provider}`", f"- Status: `{sync['status']}`", "", "The local report is authoritative technical evidence even if external synchronization is unavailable.", ""])
    markdown = _redact("\n".join(lines), [str(pattern) for pattern in docs_cfg.get("redact_patterns", [])])
    counts = Counter(f.severity for f in findings)
    result = {
        "run_id": run_id, "overall": overall, "evidence_files": list(evidence), "sync": sync,
        "findings": [asdict(f) for f in findings],
        "summary": {"critical": counts["critical"], "warning": counts["warning"], "report_generated": True, "external_sync_complete": sync["status"] in {"not-configured", "complete"}},
    }
    return markdown, result
