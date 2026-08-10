from __future__ import annotations

from collections import Counter
from typing import Any


def _configured_targets(config: dict[str, Any]) -> list[dict[str, Any]]:
    sources: dict[str, set[str]] = {}
    for path in config.get("custom_code", {}).get("paths", []) or []:
        sources.setdefault(str(path), set()).add("custom_code.paths")
    for path in config.get("plugins", {}).get("custom_paths", []) or []:
        sources.setdefault(str(path), set()).add("plugins.custom_paths")
    return [
        {"path": path, "configured_by": sorted(configured_by)}
        for path, configured_by in sources.items()
    ]


def build_code_review_queue(config: dict[str, Any], plugins_evidence: dict[str, Any]) -> dict[str, Any]:
    """Build a bounded agent review queue from deterministic plugin evidence."""
    scan_roots = {
        str(item.get("path")): item
        for item in plugins_evidence.get("custom_code_scans", []) or []
        if item.get("path")
    }
    covered_paths = {
        str(item.get("path")): item
        for item in plugins_evidence.get("covered_scan_paths", []) or []
        if item.get("path")
    }

    configured_targets = []
    for target in _configured_targets(config):
        path = target["path"]
        if path in scan_roots:
            scan = scan_roots[path]
            target.update({
                "coverage": "scanned",
                "covered_by": path,
                "scanned_files": int(scan.get("scanned_files", 0) or 0),
                "truncated_files": int(scan.get("truncated_files", 0) or 0),
                "risk_hits": int(scan.get("hits", 0) or 0),
            })
        elif path in covered_paths:
            covered = covered_paths[path]
            target.update({
                "coverage": "covered-by-parent",
                "covered_by": covered.get("covered_by"),
                "scanned_files": None,
                "truncated_files": None,
                "risk_hits": None,
            })
        else:
            target.update({
                "coverage": "not-scanned",
                "covered_by": None,
                "scanned_files": None,
                "truncated_files": None,
                "risk_hits": None,
            })
        configured_targets.append(target)

    review_queue = []
    for group in plugins_evidence.get("risk_groups", []) or []:
        review_queue.append({
            "review_rank": group.get("review_rank"),
            "status": "pending",
            "rule_id": group.get("id"),
            "severity": group.get("severity"),
            "scope": group.get("scope"),
            "path": group.get("path"),
            "message": group.get("message"),
            "occurrence_count": group.get("occurrence_count"),
            "first_line": group.get("first_line"),
            "last_line": group.get("last_line"),
            "line_sample": list(group.get("line_sample", []) or []),
            "line_sample_truncated": bool(group.get("line_sample_truncated", False)),
        })

    coverage_counts = Counter(str(item["coverage"]) for item in configured_targets)
    severity_counts = Counter(str(item.get("severity") or "info") for item in review_queue)
    manual_review = list(plugins_evidence.get("manual_review", []) or [])
    uncovered = [item["path"] for item in configured_targets if item["coverage"] == "not-scanned"]
    status = "incomplete" if uncovered else "review-required" if review_queue or manual_review else "no-findings"
    plugin_summary = plugins_evidence.get("summary", {}) or {}
    return {
        "schema_version": "1.0",
        "agent": "compatibility-agent",
        "capability": "moodle.plugins",
        "effect": "read-only",
        "source_evidence": "plugins.json",
        "target_version": plugins_evidence.get("target_version"),
        "status": status,
        "configuration": {
            "custom_code_paths": list(config.get("custom_code", {}).get("paths", []) or []),
            "plugin_custom_paths": list(config.get("plugins", {}).get("custom_paths", []) or []),
            "plugin_custom_roots": list(config.get("plugins", {}).get("custom_roots", []) or []),
            "auto_detect_top_level": bool(config.get("custom_code", {}).get("auto_detect_top_level", True)),
        },
        "configured_targets": configured_targets,
        "scan_roots": [
            {
                "path": item.get("path"),
                "scanned_files": item.get("scanned_files"),
                "truncated_files": item.get("truncated_files"),
                "risk_hits": item.get("hits"),
            }
            for item in plugins_evidence.get("custom_code_scans", []) or []
        ],
        "review_queue": review_queue,
        "manual_review": manual_review,
        "summary": {
            "configured_target_count": len(configured_targets),
            "scanned_target_count": coverage_counts["scanned"],
            "parent_covered_target_count": coverage_counts["covered-by-parent"],
            "uncovered_target_count": coverage_counts["not-scanned"],
            "uncovered_targets": uncovered,
            "scan_root_count": int(plugin_summary.get("scan_root_count", 0) or 0),
            "review_group_count": len(review_queue),
            "critical_review_group_count": severity_counts["critical"],
            "warning_review_group_count": severity_counts["warning"],
            "manual_review_count": len(manual_review),
            "risk_hit_count": int(plugin_summary.get("risk_hit_count", 0) or 0),
            "coverage_complete": not uncovered,
            "review_required": bool(review_queue or manual_review),
        },
    }
