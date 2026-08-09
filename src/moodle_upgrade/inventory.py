from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
from typing import Any


KNOWN_CORE_TOP_LEVEL = {
    "admin", "ai", "analytics", "auth", "availability", "backup", "badges", "blocks", "blog",
    "cache", "calendar", "cohort", "comment", "communication", "competency", "completion", "contentbank",
    "course", "customfield", "dataformat", "enrol", "error", "favourites", "files", "filter", "grade",
    "group", "h5p", "install", "iplookup", "lang", "lib", "local", "login", "message", "mnet", "mod",
    "my", "notes", "payment", "pix", "plagiarism", "portfolio", "privacy", "question", "rating", "report",
    "repository", "rss", "search", "sms", "tag", "theme", "user", "userpix", "vendor", "webservice",
}

IGNORED_TOP_LEVEL = {".git", ".github", ".grunt", "node_modules"}


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
    discovery = _run(["git", "rev-parse", "--show-toplevel"], cwd=root)
    if not discovery["ok"] or not discovery["stdout"]:
        return {"is_repo": False, "repo_root": None, "branch": None, "head": None, "dirty": None}

    repo_root = Path(discovery["stdout"]).resolve()
    branch = _run(["git", "branch", "--show-current"], cwd=repo_root)
    head = _run(["git", "rev-parse", "HEAD"], cwd=repo_root)
    status = _run(["git", "status", "--porcelain"], cwd=repo_root)
    return {
        "is_repo": True,
        "repo_root": str(repo_root),
        "branch": branch["stdout"] or None,
        "head": head["stdout"] or None,
        "dirty": bool(status["stdout"]) if status["returncode"] is not None else None,
    }


def _git_tracks_path(repo_root: Path | None, target: Path) -> bool | None:
    if repo_root is None:
        return None
    try:
        relative = target.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return False
    tracked = _run(["git", "ls-files", "--", str(relative)], cwd=repo_root)
    return bool(tracked["stdout"]) if tracked["returncode"] is not None else None


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


def _read_plugin_metadata(version_file: Path) -> dict[str, str | None]:
    result: dict[str, str | None] = {"component": None, "version": None, "requires": None}
    if not version_file.is_file():
        return result
    text = version_file.read_text(encoding="utf-8", errors="ignore")
    patterns = {
        "component": r"\$plugin->component\s*=\s*['\"]([^'\"]+)['\"]",
        "version": r"\$plugin->version\s*=\s*([0-9.]+)",
        "requires": r"\$plugin->requires\s*=\s*([0-9.]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            result[key] = match.group(1)
    return result


def _plugins(root: Path, configured_roots: list[str], configured_custom_paths: list[str]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    custom_paths = {str(PurePosixPath(path)) for path in configured_custom_paths}
    for relative_root in configured_roots:
        base = root / relative_root
        if not base.is_dir():
            continue
        for child in sorted(base.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            component_path = str(PurePosixPath(relative_root) / child.name)
            version_file = child / "version.php"
            metadata = _read_plugin_metadata(version_file)
            explicit_custom = component_path in custom_paths
            classification = "custom" if relative_root == "local" or explicit_custom else "unclassified"
            results.append({
                "component_path": component_path,
                "component": metadata["component"],
                "version": metadata["version"],
                "requires": metadata["requires"],
                "has_version_php": version_file.exists(),
                "classification": classification,
                "classification_reason": (
                    "local plugin" if relative_root == "local"
                    else "configured custom path" if explicit_custom
                    else "not yet compared with Moodle core"
                ),
            })
    return results


def _path_within(target: Path, boundary: Path) -> bool:
    try:
        target.resolve().relative_to(boundary.resolve())
        return True
    except ValueError:
        return False


def _custom_path_summary(root: Path, relative_path: str, repo_root: Path | None, max_files: int) -> dict[str, Any]:
    candidate = Path(relative_path)
    if candidate.is_absolute():
        return {"path": relative_path, "exists": False, "error": "custom path must be relative, not absolute"}

    root_resolved = root.resolve()
    target = (root_resolved / candidate).resolve()
    boundary = repo_root.resolve() if repo_root else root_resolved

    if not _path_within(target, boundary):
        scope = "repository root" if repo_root else "moodle.root"
        return {
            "path": relative_path,
            "exists": False,
            "resolved_path": str(target),
            "error": f"custom path escapes allowed {scope}",
        }

    scope = "moodle" if _path_within(target, root_resolved) else "project"
    base_result = {
        "path": relative_path,
        "resolved_path": str(target),
        "scope": scope,
    }

    if not target.exists():
        return {
            **base_result,
            "exists": False,
            "tracked_by_git": _git_tracks_path(repo_root, target),
        }

    if target.is_file():
        return {
            **base_result,
            "exists": True,
            "kind": "file",
            "size_bytes": target.stat().st_size,
            "tracked_by_git": _git_tracks_path(repo_root, target),
        }

    file_count = 0
    dir_count = 0
    size_bytes = 0
    extensions: Counter[str] = Counter()
    truncated = False
    for entry in target.rglob("*"):
        if entry.is_dir():
            dir_count += 1
            continue
        if not entry.is_file():
            continue
        file_count += 1
        try:
            size_bytes += entry.stat().st_size
        except OSError:
            pass
        extensions[entry.suffix.lower() or "[no-extension]"] += 1
        if file_count >= max_files:
            truncated = True
            break

    return {
        **base_result,
        "exists": True,
        "kind": "directory",
        "file_count": file_count,
        "dir_count": dir_count,
        "size_bytes": size_bytes,
        "top_extensions": dict(extensions.most_common(10)),
        "truncated": truncated,
        "tracked_by_git": _git_tracks_path(repo_root, target),
    }


def _non_core_top_level_candidates(root: Path, excluded_paths: list[Path]) -> list[str]:
    excluded = {path.resolve() for path in excluded_paths if path.exists()}
    results: list[str] = []
    if not root.is_dir():
        return results
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if child.name in KNOWN_CORE_TOP_LEVEL or child.name in IGNORED_TOP_LEVEL:
            continue
        if child.resolve() in excluded:
            continue
        results.append(child.name)
    return results


def _docker_inspect(container: str) -> dict[str, Any]:
    result = _run(["docker", "inspect", "-f", "{{.State.Running}}|{{.Config.Image}}", container])
    if not result["ok"]:
        return {"running": False, "image": None}
    running_text, _, image = result["stdout"].partition("|")
    return {"running": running_text.strip().lower() == "true", "image": image.strip() or None}


def _clean_php_modules(stdout: str) -> list[str]:
    return [line.strip() for line in stdout.splitlines() if line.strip() and not line.strip().startswith("[")]


def _docker_runtime(runtime_cfg: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    container = str(runtime_cfg.get("container"))
    runtime_root = runtime_cfg.get("moodle_root")
    runtime_moodledata = runtime_cfg.get("moodledata")
    inspected = _docker_inspect(container)
    running = inspected["running"]

    markers: dict[str, bool] = {}
    if running and runtime_root:
        base = PurePosixPath(str(runtime_root))
        marker_specs = {
            "version.php": ("-f", base / "version.php"),
            "config.php": ("-f", base / "config.php"),
            "admin/cli": ("-d", base / "admin" / "cli"),
        }
        for name, (flag, path) in marker_specs.items():
            check = _run(["docker", "exec", container, "test", flag, str(path)])
            markers[name] = check["ok"]

    if running:
        php = _run(["docker", "exec", container, "php", "-v"])
        modules_result = _run(["docker", "exec", container, "php", "-m"])
    else:
        php = {"ok": False, "returncode": None, "stdout": "", "stderr": "Docker container is not running"}
        modules_result = {"ok": False, "returncode": None, "stdout": "", "stderr": "Docker container is not running"}

    runtime = {
        "type": "docker",
        "container": container,
        "running": running,
        "image": inspected["image"],
        "moodle_root": runtime_root,
        "moodledata": runtime_moodledata,
        "markers": markers,
    }
    modules = _clean_php_modules(modules_result["stdout"]) if modules_result["ok"] else []
    return runtime, php, modules


def _runtime_platform(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    runtime_cfg = config.get("runtime", {})
    if runtime_cfg.get("type", "local") == "docker":
        return _docker_runtime(runtime_cfg)

    php = _run(["php", "-v"])
    modules_result = _run(["php", "-m"]) if php["ok"] else {"ok": False, "stdout": ""}
    modules = _clean_php_modules(modules_result.get("stdout", "")) if modules_result.get("ok") else []
    return {"type": "local"}, php, modules


def _database_platform(config: dict[str, Any]) -> dict[str, Any]:
    database_cfg = config.get("database", {})
    driver = database_cfg.get("driver")
    container = database_cfg.get("runtime_container")
    result: dict[str, Any] = {
        "driver": driver,
        "container": container,
        "running": None,
        "image": None,
        "version_line": None,
    }
    if not container:
        return result

    inspected = _docker_inspect(str(container))
    result["running"] = inspected["running"]
    result["image"] = inspected["image"]
    if not inspected["running"]:
        return result

    command: list[str] | None = None
    if driver in ("mysql", "mariadb"):
        command = ["docker", "exec", str(container), "mysqld", "--version"]
    elif driver in ("pgsql", "postgres", "postgresql"):
        command = ["docker", "exec", str(container), "postgres", "--version"]
    if command:
        version = _run(command)
        if version["ok"] and version["stdout"]:
            result["version_line"] = version["stdout"].splitlines()[0]
    return result


def collect_inventory(config: dict[str, Any]) -> dict[str, Any]:
    moodle_cfg = config["moodle"]
    root = Path(moodle_cfg["root"]).expanduser().resolve()
    moodledata_raw = moodle_cfg.get("moodledata")
    moodledata = Path(moodledata_raw).expanduser().resolve() if moodledata_raw else None
    findings: list[Finding] = []

    required_markers = [root / "version.php", root / "config.php", root / "admin" / "cli"]
    marker_state = {str(path.relative_to(root)): path.exists() for path in required_markers}
    if not root.is_dir():
        findings.append(Finding("critical", "MOODLE_ROOT_MISSING", f"Moodle root is not accessible: {root}"))
    elif not all(marker_state.values()):
        findings.append(Finding("critical", "MOODLE_MARKERS_MISSING", "Configured root does not contain all expected Moodle markers."))

    runtime, php, php_modules = _runtime_platform(config)
    if runtime.get("type") == "docker":
        if not runtime.get("running"):
            findings.append(Finding("critical", "DOCKER_CONTAINER_UNAVAILABLE", f"Docker container is not running or accessible: {runtime.get('container')}"))
        elif runtime.get("markers") and not all(runtime["markers"].values()):
            findings.append(Finding("critical", "RUNTIME_MOODLE_MARKERS_MISSING", "Docker runtime does not contain all expected Moodle markers."))
    if not php["ok"]:
        findings.append(Finding("critical", "PHP_UNAVAILABLE", "PHP CLI could not be executed in the configured runtime."))

    git = _git_state(root) if root.exists() else {"is_repo": False, "repo_root": None, "branch": None, "head": None, "dirty": None}
    if not git.get("is_repo"):
        findings.append(Finding("warning", "GIT_NOT_REPOSITORY", "Moodle source path is not inside a Git working tree."))
    elif git.get("dirty"):
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

    plugins_cfg = config.get("plugins", {})
    configured_plugin_roots = plugins_cfg.get("custom_roots", ["local", "blocks", "mod", "auth", "report"])
    configured_custom_plugins = plugins_cfg.get("custom_paths", [])
    plugin_inventory = _plugins(root, configured_plugin_roots, configured_custom_plugins) if root.exists() else []

    custom_cfg = config.get("custom_code", {})
    max_files = int(custom_cfg.get("max_files_per_path", 50000))
    configured_custom_paths = list(custom_cfg.get("paths", []))
    repo_root = Path(git["repo_root"]) if git.get("repo_root") else None
    custom_inventory = [_custom_path_summary(root, path, repo_root, max_files) for path in configured_custom_paths]
    for item in custom_inventory:
        if item.get("error"):
            findings.append(Finding("warning", "CUSTOM_PATH_OUTSIDE_BOUNDARY", f"Custom code path is not allowed: {item['path']} ({item['error']})"))
        elif not item.get("exists"):
            findings.append(Finding("warning", "CUSTOM_PATH_MISSING", f"Configured custom code path is missing: {item['path']}"))

    excluded = [moodledata] if moodledata else []
    auto_detect = custom_cfg.get("auto_detect_top_level", True)
    non_core_candidates = _non_core_top_level_candidates(root, [path for path in excluded if path is not None]) if auto_detect else []

    database = _database_platform(config)
    if database.get("container") and database.get("running") is False:
        findings.append(Finding("warning", "DATABASE_CONTAINER_UNAVAILABLE", f"Database container is not running or accessible: {database.get('container')}"))

    cron_command = moodle_cfg.get("cron_command")
    cron = {
        "configured": bool(cron_command),
        "command": cron_command,
        "cli_exists": (root / "admin" / "cli" / "cron.php").exists() if root.exists() else False,
    }

    custom_plugin_count = sum(1 for plugin in plugin_inventory if plugin["classification"] == "custom")
    return {
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
            "runtime": runtime,
            "php": {
                "available": php["ok"],
                "version_line": php["stdout"].splitlines()[0] if php["stdout"] else None,
                "modules": php_modules,
            },
            "database": database,
            "git": git,
            "disk": disks,
        },
        "plugins": plugin_inventory,
        "custom_code": {
            "configured_paths": custom_inventory,
            "non_core_top_level_candidates": non_core_candidates,
        },
        "cron": cron,
        "findings": [asdict(finding) for finding in findings],
        "summary": {
            "critical": sum(1 for finding in findings if finding.severity == "critical"),
            "warning": sum(1 for finding in findings if finding.severity == "warning"),
            "info": sum(1 for finding in findings if finding.severity == "info"),
            "plugin_count": len(plugin_inventory),
            "custom_plugin_count": custom_plugin_count,
            "configured_custom_code_count": len(custom_inventory),
            "non_core_top_level_candidate_count": len(non_core_candidates),
        },
    }
