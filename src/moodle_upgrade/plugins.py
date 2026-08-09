from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable

DEFAULT_EXTENSIONS = {".php", ".inc", ".sql", ".js", ".mustache"}
DEFAULT_EXCLUDE_DIRS = {".git", "vendor", "node_modules", ".venv", "moodledata"}
PHP_SOURCE_EXTENSIONS = (".php", ".inc")
SQL_AWARE_EXTENSIONS = (".php", ".inc", ".sql")


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    path: str | None = None
    line: int | None = None


RISK_PATTERNS: tuple[dict[str, Any], ...] = (
    {
        "id": "php_mysql_extension_removed",
        "severity": "critical",
        "regex": r"\bmysql_(?:query|connect|pconnect|select_db|real_escape_string|fetch_[a-z_]+)\s*\(",
        "min_target": "4.1",
        "extensions": PHP_SOURCE_EXTENSIONS,
        "message": "Legacy mysql_* API is removed from modern PHP.",
    },
    {
        "id": "php_ereg_removed",
        "severity": "critical",
        "regex": r"\b(?:ereg|eregi)\s*\(",
        "min_target": "4.1",
        "extensions": PHP_SOURCE_EXTENSIONS,
        "message": "ereg()/eregi() are removed from modern PHP.",
    },
    {
        "id": "php_split_removed",
        "severity": "critical",
        "regex": r"\b(?:split|spliti)\s*\(",
        "min_target": "4.1",
        "extensions": PHP_SOURCE_EXTENSIONS,
        "message": "split()/spliti() are removed from modern PHP.",
    },
    {
        "id": "php_each_removed",
        "severity": "warning",
        "regex": r"\beach\s*\(",
        "min_target": "4.1",
        "extensions": PHP_SOURCE_EXTENSIONS,
        "message": "each() is incompatible with PHP 8 and should be migrated.",
    },
    {
        "id": "php_create_function_removed",
        "severity": "warning",
        "regex": r"\bcreate_function\s*\(",
        "min_target": "4.1",
        "extensions": PHP_SOURCE_EXTENSIONS,
        "message": "create_function() is incompatible with PHP 8 and should be migrated.",
    },
    {
        "id": "moodle_41_cron_run_single_task_removed",
        "severity": "critical",
        "regex": r"\bcron_run_single_task\s*\(",
        "min_target": "4.1",
        "extensions": PHP_SOURCE_EXTENSIONS,
        "message": "cron_run_single_task() was finally deprecated for Moodle 4.1 and requires migration.",
    },
    {
        "id": "moodle_41_get_module_metadata_removed",
        "severity": "critical",
        "regex": r"\bget_module_metadata\s*\(",
        "min_target": "4.1",
        "extensions": PHP_SOURCE_EXTENSIONS,
        "message": "get_module_metadata() was finally deprecated for Moodle 4.1 and requires migration.",
    },
    {
        "id": "moodle_41_admin_setting_managelicenses_removed",
        "severity": "critical",
        "regex": r"\badmin_setting_managelicenses\b",
        "min_target": "4.1",
        "extensions": PHP_SOURCE_EXTENSIONS,
        "message": "admin_setting_managelicenses was finally deprecated for Moodle 4.1 and requires migration.",
    },
    {
        "id": "hardcoded_mdl_prefix",
        "severity": "warning",
        "regex": r"\bmdl_[a-zA-Z0-9_]+\b",
        "min_target": "3.9",
        "extensions": SQL_AWARE_EXTENSIONS,
        "message": "Hard-coded mdl_ table prefix couples code to one database prefix.",
    },
    {
        "id": "legacy_user_contact_column",
        "severity": "warning",
        "regex": r"(?:\bmdl_user\b|\buser\b|\bu\b)\s*\.\s*(?:icq|skype|yahoo|aim|msn)\b|\b(?:icq|skype|yahoo|aim|msn)\b",
        "min_target": "3.11",
        "extensions": SQL_AWARE_EXTENSIONS,
        "message": "Legacy user contact fields were migrated/removed around Moodle 3.11 and require schema review.",
    },
)


def _numbers(value: str | None) -> tuple[int, ...]:
    if not value:
        return ()
    match = re.search(r"(\d+(?:\.\d+){0,3})", str(value))
    return tuple(int(part) for part in match.group(1).split(".")) if match else ()


def _at_least(value: str | None, minimum: str) -> bool:
    left = _numbers(value)
    right = _numbers(minimum)
    size = max(len(left), len(right))
    return bool(left) and left + (0,) * (size - len(left)) >= right + (0,) * (size - len(right))


def _iter_source_files(root: Path, max_files: int, extensions: set[str], excluded: set[str]) -> Iterable[Path]:
    count = 0
    if root.is_file():
        if root.suffix.lower() in extensions:
            yield root
        return
    for path in root.rglob("*"):
        if any(part in excluded for part in path.parts):
            continue
        if not path.is_file() or path.suffix.lower() not in extensions:
            continue
        yield path
        count += 1
        if count >= max_files:
            return


def _scan_path(root: Path, display_root: Path, target_version: str, max_files: int, max_bytes: int, patterns: tuple[dict[str, Any], ...]) -> tuple[list[dict], dict]:
    hits: list[dict[str, Any]] = []
    scanned_files = 0
    truncated_files = 0
    for file_path in _iter_source_files(root, max_files, DEFAULT_EXTENSIONS, DEFAULT_EXCLUDE_DIRS):
        scanned_files += 1
        try:
            raw = file_path.read_bytes()
        except OSError:
            continue
        if len(raw) > max_bytes:
            raw = raw[:max_bytes]
            truncated_files += 1
        text = raw.decode("utf-8", errors="ignore")
        rel = str(file_path.relative_to(display_root)) if file_path.is_relative_to(display_root) else str(file_path)
        suffix = file_path.suffix.lower()
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern in patterns:
                if not _at_least(target_version, pattern["min_target"]):
                    continue
                allowed_extensions = pattern.get("extensions")
                if allowed_extensions and suffix not in allowed_extensions:
                    continue
                if re.search(pattern["regex"], line, flags=re.IGNORECASE):
                    hits.append({"id": pattern["id"], "severity": pattern["severity"], "path": rel, "line": lineno, "message": pattern["message"]})
    return hits, {"scanned_files": scanned_files, "truncated_files": truncated_files, "max_files": max_files, "max_bytes_per_file": max_bytes}


def _git_diff_names(repo_root: Path, reference: str, moodle_root: Path) -> list[str] | None:
    try:
        relative = moodle_root.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return None
    try:
        proc = subprocess.run(["git", "diff", "--name-only", reference, "--", str(relative)], cwd=repo_root, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _scan_path_covers(parent: Path, child: Path) -> bool:
    if parent == child:
        return True
    if not parent.is_dir():
        return False
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _deduplicate_scan_targets(scan_targets: list[tuple[str, Path]]) -> tuple[list[tuple[str, Path]], list[dict[str, str]]]:
    """Return minimal non-overlapping scan roots plus evidence for covered paths.

    Parents are considered before descendants regardless of configuration order, so
    configuring both ../batch and ../batch/edx never scans the edx tree twice.
    """
    normalized = [(index, label, path.resolve()) for index, (label, path) in enumerate(scan_targets)]
    ordered = sorted(normalized, key=lambda item: (len(item[2].parts), item[0]))
    selected: list[tuple[int, str, Path]] = []
    covered: list[tuple[int, dict[str, str]]] = []

    for index, label, resolved in ordered:
        covering = next(
            ((selected_label, selected_path) for _, selected_label, selected_path in selected if _scan_path_covers(selected_path, resolved)),
            None,
        )
        if covering:
            covering_label, covering_path = covering
            covered.append((index, {
                "path": label,
                "resolved_path": str(resolved),
                "covered_by": covering_label,
                "covered_by_resolved_path": str(covering_path),
            }))
            continue
        selected.append((index, label, resolved))

    selected.sort(key=lambda item: item[0])
    covered.sort(key=lambda item: item[0])
    return [(label, path) for _, label, path in selected], [item for _, item in covered]


def analyze_plugins(config: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    target = config.get("moodle", {}).get("target_version") or inventory.get("identity", {}).get("target_version")
    root = Path(config["moodle"]["root"]).expanduser().resolve()
    findings: list[Finding] = []
    plugins: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    cfg = config.get("plugins", {})
    compatibility_map = cfg.get("compatibility", {}) or {}
    ignore = set(cfg.get("ignore", []) or [])

    for plugin in inventory.get("plugins", []):
        item = dict(plugin)
        path = item.get("component_path")
        if not path or path in ignore:
            item["review_status"] = "ignored"
            plugins.append(item)
            continue
        declared = compatibility_map.get(path, [])
        if isinstance(declared, str):
            declared = [declared]
        branch = ".".join(str(target).split(".")[:2]) if target else None
        if declared and branch in {str(value) for value in declared}:
            item["review_status"] = "declared-compatible"
        elif item.get("classification") == "custom":
            item["review_status"] = "scan-required"
            review.append({"type": "plugin", "path": path, "reason": "Custom plugin has no declared target compatibility."})
        else:
            item["review_status"] = "core-comparison-required"
            review.append({"type": "plugin", "path": path, "reason": "Plugin remains unclassified until compared with exact Moodle core."})
        plugins.append(item)

    scan_cfg = config.get("custom_code", {}) or {}
    max_files = int(scan_cfg.get("scan_max_files_per_path", 20_000))
    max_bytes = int(scan_cfg.get("scan_max_bytes_per_file", 1_000_000))
    scan_targets: list[tuple[str, Path]] = []
    for item in inventory.get("custom_code", {}).get("configured_paths", []):
        if not item.get("exists"):
            findings.append(Finding("critical", "CUSTOM_PATH_UNAVAILABLE", f"Cannot scan configured custom path: {item.get('path')}", item.get("path")))
            continue
        resolved = item.get("resolved_path")
        if resolved:
            scan_targets.append((item.get("path") or resolved, Path(resolved)))
    for plugin in plugins:
        if plugin.get("classification") != "custom" or plugin.get("review_status") == "ignored":
            continue
        path = plugin.get("component_path")
        candidate = (root / str(path)).resolve()
        if candidate.exists():
            scan_targets.append((str(path), candidate))

    scan_targets, covered_scan_paths = _deduplicate_scan_targets(scan_targets)

    all_hits: list[dict[str, Any]] = []
    scan_summaries: list[dict[str, Any]] = []
    for label, resolved in scan_targets:
        hits, summary = _scan_path(resolved, resolved if resolved.is_dir() else resolved.parent, str(target), max_files, max_bytes, RISK_PATTERNS)
        for hit in hits:
            hit["scope"] = label
        all_hits.extend(hits)
        scan_summaries.append({"path": label, "resolved_path": str(resolved), **summary, "hits": len(hits)})
    for hit in all_hits:
        findings.append(Finding(hit["severity"], f"CODE_{hit['id'].upper()}", hit["message"], hit["path"], hit["line"]))

    core_modifications: list[str] | None = None
    core_ref = cfg.get("core_reference_ref")
    repo_root_text = inventory.get("platform", {}).get("git", {}).get("repo_root")
    if core_ref and repo_root_text:
        core_modifications = _git_diff_names(Path(repo_root_text), str(core_ref), root)
        if core_modifications is None:
            findings.append(Finding("warning", "CORE_DIFF_UNAVAILABLE", f"Could not compare Moodle source against configured Git ref {core_ref}."))
        elif core_modifications:
            findings.append(Finding("warning", "CORE_DIFF_PRESENT", f"Git reports {len(core_modifications)} files changed from configured core reference; review whether they are expected customizations."))

    counts = Counter(f.severity for f in findings)
    return {
        "target_version": target, "plugins": plugins, "custom_code_scans": scan_summaries, "covered_scan_paths": covered_scan_paths, "risk_hits": all_hits,
        "core_reference_ref": core_ref, "core_modifications": core_modifications, "manual_review": review,
        "findings": [asdict(f) for f in findings],
        "summary": {
            "critical": counts["critical"], "warning": counts["warning"], "info": counts["info"],
            "plugin_count": len(plugins), "risk_hit_count": len(all_hits), "review_count": len(review),
            "scan_root_count": len(scan_summaries), "covered_scan_path_count": len(covered_scan_paths), "ready": counts["critical"] == 0,
        },
    }
