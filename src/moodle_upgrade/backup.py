from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any


@dataclass
class Finding:
    severity: str
    code: str
    message: str


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _candidate_metadata(path: Path, checksum: bool) -> dict[str, Any]:
    stat = path.stat()
    payload = {
        "path": str(path),
        "kind": "directory" if path.is_dir() else "file",
        "size_bytes": stat.st_size if path.is_file() else None,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "mtime_epoch": stat.st_mtime,
    }
    if checksum and path.is_file():
        payload["sha256"] = _sha256(path)
    return payload


def verify_backups(config: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    backup_cfg = config.get("backup", {}) or {}
    safety_cfg = config.get("safety", {}) or {}
    roots = [Path(str(path)).expanduser() for path in backup_cfg.get("paths", [])]
    required = list(backup_cfg.get("required_components", []) or [])
    components_cfg = backup_cfg.get("components", {}) or {}
    max_age = float(backup_cfg.get("max_age_hours", safety_cfg.get("max_backup_age_hours", 24)))
    checksum = bool(backup_cfg.get("checksum", False))
    findings: list[Finding] = []

    accessible_roots: list[Path] = []
    for root in roots:
        if not root.exists() or not root.is_dir():
            findings.append(Finding("critical", "BACKUP_LOCATION_INACCESSIBLE", f"Backup location is not an accessible directory: {root}"))
        else:
            accessible_roots.append(root.resolve())

    components: dict[str, Any] = {}
    for component in required:
        spec = components_cfg.get(component)
        if not spec:
            findings.append(Finding("critical", "BACKUP_COMPONENT_RULE_MISSING", f"No identity rule is configured for required backup component {component}."))
            components[component] = {"ok": False, "candidates": [], "selected": None}
            continue
        if isinstance(spec, str):
            globs = [spec]
        elif isinstance(spec, list):
            globs = [str(value) for value in spec]
        else:
            globs = [str(value) for value in spec.get("globs", [])]
        if not globs:
            findings.append(Finding("critical", "BACKUP_COMPONENT_RULE_MISSING", f"No glob patterns are configured for required backup component {component}."))
            components[component] = {"ok": False, "candidates": [], "selected": None}
            continue

        matches: dict[Path, dict[str, Any]] = {}
        for root in accessible_roots:
            for pattern in globs:
                for path in root.glob(pattern):
                    try:
                        resolved = path.resolve()
                        resolved.relative_to(root)
                    except (OSError, ValueError):
                        continue
                    if path.exists():
                        matches[resolved] = _candidate_metadata(resolved, checksum)
        ordered = sorted(matches.values(), key=lambda item: item["mtime_epoch"], reverse=True)
        selected = ordered[0] if ordered else None
        ok = bool(selected)
        if selected:
            age_hours = (now.timestamp() - float(selected["mtime_epoch"])) / 3600
            selected = {**selected, "age_hours": round(age_hours, 2)}
            if age_hours > max_age:
                ok = False
                findings.append(Finding("critical", "BACKUP_COMPONENT_STALE", f"Newest {component} backup is {age_hours:.1f}h old; policy allows at most {max_age:.1f}h."))
        else:
            findings.append(Finding("critical", "BACKUP_COMPONENT_MISSING", f"No backup candidate matched configured rules for required component {component}."))
        components[component] = {"ok": ok, "patterns": globs, "selected": selected, "candidate_count": len(ordered)}

    counts = Counter(f.severity for f in findings)
    return {
        "locations": [{"path": str(root), "accessible": root.resolve() in accessible_roots if root.exists() else False} for root in roots],
        "required_components": required,
        "components": components,
        "policy": {"max_age_hours": max_age, "checksum": checksum},
        "findings": [asdict(f) for f in findings],
        "summary": {
            "critical": counts["critical"], "warning": counts["warning"], "info": counts["info"],
            "verified": bool(required) and counts["critical"] == 0 and all(item.get("ok") for item in components.values()),
        },
    }
