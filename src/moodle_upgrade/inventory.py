from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any


@dataclass
class Finding:
    severity: str
    code: str
    message: str


def _run(command: list[str], cwd: Path | None = None, timeout: int = 10) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc)}


def _read_moodle_version(root: Path) -> dict[str, Any]:
    version_file = root / "version.php"
    if not version_file.exists():
        return {"release": None, "version": None, "branch": None}
    text = version_file.read_text(encoding="utf-8", errors="ignore")
    result: dict[str, Any] = {"release": None, "version": None, "branch": None}
    patterns = {
        "release": r"\$release\s*=\s*['\"]([^'\"]+)['\"]",
        "version": r"\$version\s*=\s*([0-9.]+)",
        "branch": r"\$branch\s*=\s*['\"]?([^;'\"\s]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            result[key] = match.group(1)
    return result


def _git_state(root: Path) -> dict[str, Any]:
    if not (root / ".git").exists():
        return {"is_repo": False, "branch": None, "head": None, "dirty": None}
    branch = _run(["git", "branch", "--show-current"], cwd=root)
    head = _run(["git", "rev-parse", "HEAD"], cwd=root)
    status = _run(["git", "status", "--porcelain"], cwd=root)
    return {
        "is_repo": True,
        "branch": branch["stdout"] or None,
        "head": head["stdout"] or None,
        "dirty": bool(status["stdout"]) if status["returncode"] is not None else None,
    }


def _disk(path: Path) -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
        return {
            "path": str(path),
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "free_percent": round((usage.free / usage.total) * 100, 2) if usage.total else 0,
        }
    except OSError as exc:
        return {"path": str(path), "error": str(exc)}


def _plugins(root: Path, configured_roots: list[str]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for relative_root in configured_roots:
        base = root / relative_root
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            version_file = child / "version.php"
            results.append({
                "component_path": f"{relative_root}/{child.name}",
                "has_version_php": str(version_file.exists()).lower(),
            })
    return results


def collect_inventory(config: dict[str, Any]) -> dict[str, Any]:
    moodle_cfg = config["moodle"]
    root = Path(moodle_cfg["root"]).expanduser().resolve()
    moodledata_raw = moodle_cfg.get("moodledata")
    moodledata = Path(moodledata_raw).expanduser().resolve() if moodledata_raw else None
    findings: list[Finding] = []

    required_markers = [root / "version.php", root / "config.php", root / "admin" / "cli"]
    marker_state = {str(p.relative_to(root)): p.exists() for p in required_markers}
    if not root.is_dir():
        findings.append(Finding("critical", "MOODLE_ROOT_MISSING", f"Moodle root is not accessible: {root}"))
    elif not all(marker_state.values()):
        findings.append(Finding("critical", "MOODLE_MARKERS_MISSING", "Configured root does not contain all expected Moodle markers."))

    php = _run(["php", "-v"])
    if not php["ok"]:
        findings.append(Finding("critical", "PHP_UNAVAILABLE", "PHP CLI could not be executed."))

    git = _git_state(root) if root.exists() else {"is_repo": False, "branch": None, "head": None, "dirty": None}
    if git.get("is_repo") and git.get("dirty"):
        findings.append(Finding("warning", "GIT_DIRTY", "Moodle Git working tree contains local changes."))

    disk_paths = [root]
    if moodledata:
        disk_paths.append(moodledata)
    for backup_path in config.get("backup", {}).get("paths", []):
        disk_paths.append(Path(backup_path).expanduser())
    disks = [_disk(path) for path in disk_paths if path.exists()]

    min_free_gb = config.get("inventory", {}).get("min_free_gb")
    if min_free_gb is not None:
        threshold = int(min_free_gb) * 1024**3
        for item in disks:
            if "free_bytes" in item and item["free_bytes"] < threshold:
                findings.append(Finding("critical", "LOW_DISK_SPACE", f"Free disk below configured threshold for {item['path']}"))

    configured_plugin_roots = config.get("plugins", {}).get("custom_roots", ["local", "blocks", "mod", "auth", "report"])
    plugin_inventory = _plugins(root, configured_plugin_roots) if root.exists() else []

    cron_command = moodle_cfg.get("cron_command")
    cron = {
        "configured": bool(cron_command),
        "command": cron_command,
        "cli_exists": (root / "admin" / "cli" / "cron.php").exists() if root.exists() else False,
    }

    payload = {
        "identity": {
            "project": config.get("project", {}),
            "moodle_root": str(root),
            "moodledata": str(moodledata) if moodledata else None,
            "base_url": moodle_cfg.get("base_url"),
            "target_version": moodle_cfg.get("target_version"),
            "markers": marker_state,
            "moodle_version": _read_moodle_version(root) if root.exists() else {},
        },
        "platform": {
            "php": {
                "available": php["ok"],
                "version_line": php["stdout"].splitlines()[0] if php["stdout"] else None,
            },
            "git": git,
            "disk": disks,
        },
        "plugins": plugin_inventory,
        "cron": cron,
        "findings": [asdict(f) for f in findings],
        "summary": {
            "critical": sum(1 for f in findings if f.severity == "critical"),
            "warning": sum(1 for f in findings if f.severity == "warning"),
            "info": sum(1 for f in findings if f.severity == "info"),
            "plugin_count": len(plugin_inventory),
        },
    }
    return payload
