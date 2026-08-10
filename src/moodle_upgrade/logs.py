from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import subprocess
from typing import Any, Callable


SAFE_CONTAINER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")


def analyze_text(text: str, patterns: dict[str, list[str]]) -> dict:
    findings = {}
    for severity, needles in patterns.items():
        counts = Counter()
        for needle in needles:
            count = text.count(needle)
            if count:
                counts[needle] = count
        findings[severity] = dict(counts)
    return findings


def analyze_files(files: list[str], patterns: dict[str, list[str]], max_bytes_per_file: int = 2_000_000) -> dict:
    result = {"files": [], "totals": {}}
    aggregate = Counter()
    for file_name in files:
        p = Path(file_name)
        if not p.exists() or not p.is_file():
            result["files"].append({"id": file_name, "type": "file", "path": file_name, "executed": False, "readable": False, "findings": {}})
            continue
        size = p.stat().st_size
        with p.open("rb") as fh:
            if size > max_bytes_per_file:
                fh.seek(-max_bytes_per_file, 2)
            raw = fh.read(max_bytes_per_file)
        text = raw.decode("utf-8", errors="replace")
        findings = analyze_text(text, patterns)
        result["files"].append({
            "id": file_name,
            "type": "file",
            "path": file_name,
            "executed": True,
            "readable": True,
            "bytes_analyzed": len(raw),
            "truncated": size > max_bytes_per_file,
            "findings": findings,
        })
        for severity, mapping in findings.items():
            aggregate[severity] += sum(mapping.values())
    result["totals"] = dict(aggregate)
    return result


def _run_docker_logs(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def _bounded_log_text(text: str, max_bytes: int) -> tuple[str, bool, int]:
    raw = text.encode("utf-8", errors="replace")
    truncated = len(raw) > max_bytes
    if truncated:
        raw = raw[-max_bytes:]
    return raw.decode("utf-8", errors="replace"), truncated, len(raw)


def analyze_log_sources(
    logs_config: dict[str, Any], runner: Callable[[list[str], int], Any] | None = None,
) -> dict[str, Any]:
    """Analyze configured file and Docker sources without persisting raw logs."""
    patterns = logs_config.get("patterns", {}) or {}
    max_bytes = int(logs_config.get("max_bytes_per_source", 2_000_000))
    timeout = int(logs_config.get("timeout_seconds", 30))
    default_tail = int(logs_config.get("docker_tail_lines", 5_000))
    default_required = bool(logs_config.get("required", False))
    runner = runner or _run_docker_logs

    sources: list[dict[str, Any]] = [
        {"id": str(path), "type": "file", "path": str(path), "required": default_required}
        for path in logs_config.get("files", []) or []
    ]
    sources.extend(dict(source) for source in logs_config.get("sources", []) or [])

    items: list[dict[str, Any]] = []
    aggregate = Counter()
    for index, source in enumerate(sources, start=1):
        source_type = str(source.get("type", "file")).lower()
        source_id = str(source.get("id") or source.get("path") or source.get("container") or f"source-{index}")
        required = bool(source.get("required", default_required))
        item: dict[str, Any] = {
            "id": source_id,
            "type": source_type,
            "required": required,
            "executed": False,
            "readable": False,
            "findings": {},
            "error": None,
        }

        if source_type == "file":
            path_text = str(source.get("path") or "")
            item["path"] = path_text
            path = Path(path_text)
            if not path_text or not path.is_file():
                item["error"] = "Configured log file is unavailable."
                items.append(item)
                continue
            try:
                size = path.stat().st_size
                with path.open("rb") as handle:
                    if size > max_bytes:
                        handle.seek(-max_bytes, 2)
                    raw = handle.read(max_bytes)
            except OSError:
                item["error"] = "Configured log file could not be read."
                items.append(item)
                continue
            text = raw.decode("utf-8", errors="replace")
            item.update({"executed": True, "readable": True, "bytes_analyzed": len(raw), "truncated": size > max_bytes})
        elif source_type == "docker":
            container = str(source.get("container") or "")
            tail_lines = int(source.get("tail_lines", default_tail))
            item.update({"container": container, "tail_lines": tail_lines})
            if not SAFE_CONTAINER_RE.fullmatch(container) or tail_lines <= 0 or tail_lines > 100_000:
                item["error"] = "Docker log source configuration is invalid."
                items.append(item)
                continue
            command = ["docker", "logs", "--tail", str(tail_lines), container]
            try:
                proc = runner(command, timeout)
            except (OSError, subprocess.TimeoutExpired):
                item["error"] = "Docker log source could not be read."
                items.append(item)
                continue
            item["executed"] = True
            if int(proc.returncode) != 0:
                item["error"] = "Docker logs returned non-zero."
                items.append(item)
                continue
            text, truncated, bytes_analyzed = _bounded_log_text(f"{proc.stdout}\n{proc.stderr}", max_bytes)
            item.update({"readable": True, "bytes_analyzed": bytes_analyzed, "truncated": truncated})
        else:
            item["error"] = "Unsupported log source type."
            items.append(item)
            continue

        findings = analyze_text(text, patterns)
        item["findings"] = findings
        for severity, mapping in findings.items():
            aggregate[severity] += sum(mapping.values())
        items.append(item)

    required_unreadable = sum(1 for item in items if item["required"] and not item["readable"])
    executed = sum(1 for item in items if item["executed"])
    readable = sum(1 for item in items if item["readable"])
    return {
        "files": items,
        "totals": dict(aggregate),
        "summary": {
            "configured": len(sources),
            "executed": executed,
            "readable": readable,
            "required_unreadable": required_unreadable,
            "complete": bool(sources) and readable > 0 and required_unreadable == 0,
        },
    }
