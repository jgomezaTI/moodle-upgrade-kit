from __future__ import annotations

from pathlib import Path
from pathlib import PurePosixPath
import re
from typing import Any
from urllib.parse import urlsplit

import yaml


class ConfigError(ValueError):
    pass


def load_config(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"Config not found: {p}")
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    validate_config(data)
    return data


def validate_config(data: dict[str, Any]) -> None:
    required = ["project", "moodle", "safety"]
    missing = [key for key in required if key not in data]
    if missing:
        raise ConfigError(f"Missing top-level keys: {', '.join(missing)}")

    project = data.get("project", {})
    moodle = data.get("moodle", {})
    safety = data.get("safety", {})
    runtime = data.get("runtime", {})
    plugins = data.get("plugins", {}) or {}

    for key in ("name", "environment"):
        if not project.get(key):
            raise ConfigError(f"project.{key} is required")
    for key in ("root", "base_url", "target_version"):
        if not moodle.get(key):
            raise ConfigError(f"moodle.{key} is required")
    parsed_base_url = urlsplit(str(moodle.get("base_url")))
    if parsed_base_url.scheme not in {"http", "https"} or not parsed_base_url.netloc:
        raise ConfigError("moodle.base_url must be an absolute HTTP(S) URL")
    if parsed_base_url.username is not None or parsed_base_url.password is not None:
        raise ConfigError("moodle.base_url must not contain credentials")

    runtime_type = runtime.get("type", "local")
    if runtime_type not in ("local", "docker"):
        raise ConfigError("runtime.type must be local or docker")
    if runtime_type == "docker":
        for key in ("container", "moodle_root"):
            if not runtime.get(key):
                raise ConfigError(f"runtime.{key} is required for docker targets")

    if project.get("environment") == "production" and safety.get("allow_mutation"):
        if not safety.get("require_human_gate", True):
            raise ConfigError("Production mutation cannot disable the human gate")

    core_reference = plugins.get("core_reference")
    legacy_core_reference = plugins.get("core_reference_ref")
    if core_reference is not None and legacy_core_reference:
        raise ConfigError("Use plugins.core_reference or plugins.core_reference_ref, not both")
    if core_reference is not None:
        if not isinstance(core_reference, dict):
            raise ConfigError("plugins.core_reference must be a mapping")
        repository = core_reference.get("repository")
        if repository is not None and (not isinstance(repository, str) or not Path(repository).expanduser().is_absolute()):
            raise ConfigError("plugins.core_reference.repository must be an absolute local path")
        ref = core_reference.get("ref")
        if not isinstance(ref, str) or not ref.strip():
            raise ConfigError("plugins.core_reference.ref is required")
        if (
            ref.startswith("-")
            or ref.endswith(("/", "."))
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", ref)
            or any(fragment in ref for fragment in ("..", "//", "@{"))
        ):
            raise ConfigError("plugins.core_reference.ref contains unsupported or unsafe characters")
        root = core_reference.get("root", ".")
        if not isinstance(root, str):
            raise ConfigError("plugins.core_reference.root must be a relative Git tree path")
        normalized_root = root.strip().replace("\\", "/")
        tree_root = PurePosixPath(normalized_root or ".")
        if tree_root.is_absolute() or any(part == ".." for part in tree_root.parts):
            raise ConfigError("plugins.core_reference.root must be a relative Git tree path without traversal")
        for key in ("max_files", "max_files_per_component", "max_changed_files"):
            value = core_reference.get(key)
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value <= 0):
                raise ConfigError(f"plugins.core_reference.{key} must be a positive integer")
    if legacy_core_reference is not None and not isinstance(legacy_core_reference, str):
        raise ConfigError("plugins.core_reference_ref must be a string or null")

    endpoints = data.get("endpoints", []) or []
    if not isinstance(endpoints, list):
        raise ConfigError("endpoints must be a list")
    endpoint_ids: set[str] = set()
    for endpoint in endpoints:
        if not isinstance(endpoint, dict):
            raise ConfigError("each endpoint must be a mapping")
        endpoint_id = str(endpoint.get("id") or "")
        if not endpoint_id or endpoint_id in endpoint_ids:
            raise ConfigError("endpoint IDs must be non-empty and unique")
        endpoint_ids.add(endpoint_id)
        method = str(endpoint.get("method", "GET")).upper()
        if method not in {"GET", "HEAD", "OPTIONS"}:
            raise ConfigError("endpoint methods must be read-only: GET, HEAD or OPTIONS")
        path = endpoint.get("path", "/")
        if not isinstance(path, str) or urlsplit(path).scheme or urlsplit(path).netloc:
            raise ConfigError("endpoint paths must be relative to moodle.base_url")
        verify_tls = endpoint.get("verify_tls", True)
        if not isinstance(verify_tls, bool):
            raise ConfigError("endpoint verify_tls must be a boolean")
        if project.get("environment") == "production" and not verify_tls:
            raise ConfigError("production endpoints cannot disable TLS verification")
        try:
            expected_status = int(endpoint.get("expected_status", 200))
            timeout_seconds = float(endpoint.get("timeout_seconds", 15))
        except (TypeError, ValueError) as exc:
            raise ConfigError("endpoint expected_status and timeout_seconds must be numeric") from exc
        if expected_status < 100 or expected_status > 599 or timeout_seconds <= 0:
            raise ConfigError("endpoint expected_status or timeout_seconds is outside its allowed range")

    logs = data.get("logs", {}) or {}
    if not isinstance(logs, dict):
        raise ConfigError("logs must be a mapping")
    if not isinstance(logs.get("files", []) or [], list):
        raise ConfigError("logs.files must be a list")
    sources = logs.get("sources", []) or []
    if not isinstance(sources, list):
        raise ConfigError("logs.sources must be a list")
    log_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ConfigError("each logs.sources item must be a mapping")
        source_id = str(source.get("id") or "")
        if not source_id or source_id in log_ids:
            raise ConfigError("log source IDs must be non-empty and unique")
        log_ids.add(source_id)
        source_type = str(source.get("type", "file")).lower()
        if source_type not in {"file", "docker"}:
            raise ConfigError("log source type must be file or docker")
        if source_type == "file" and not isinstance(source.get("path"), str):
            raise ConfigError("file log sources require a path")
        if source_type == "docker":
            container = source.get("container")
            if not isinstance(container, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", container):
                raise ConfigError("docker log sources require an argv-safe container name")
            tail_lines = source.get("tail_lines", logs.get("docker_tail_lines", 5000))
            if isinstance(tail_lines, bool) or not isinstance(tail_lines, int) or not 0 < tail_lines <= 100_000:
                raise ConfigError("docker log source tail_lines must be between 1 and 100000")

    database = data.get("database", {}) or {}
    if not isinstance(database, dict):
        raise ConfigError("database must be a mapping")
    container_connection_env = database.get("container_connection_env")
    if container_connection_env is not None:
        if database.get("connection_env"):
            raise ConfigError("Use database.connection_env or database.container_connection_env, not both")
        if not isinstance(container_connection_env, dict):
            raise ConfigError("database.container_connection_env must be a mapping")
        container = database.get("runtime_container")
        if not isinstance(container, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", container):
            raise ConfigError("database.container_connection_env requires an argv-safe runtime_container")
        for key in ("database", "user"):
            name = container_connection_env.get(key)
            if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
                raise ConfigError(f"database.container_connection_env.{key} must name a container environment variable")
        password_name = container_connection_env.get("password")
        if password_name is not None and (not isinstance(password_name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", password_name)):
            raise ConfigError("database.container_connection_env.password must name a container environment variable")
        container_host = str(database.get("container_host", "127.0.0.1"))
        container_port = database.get("container_port", 3306)
        if not re.fullmatch(r"[A-Za-z0-9_.:-]+", container_host):
            raise ConfigError("database.container_host is invalid")
        if isinstance(container_port, bool) or not isinstance(container_port, int) or not 0 < container_port <= 65535:
            raise ConfigError("database.container_port must be between 1 and 65535")

    qa = data.get("qa", {}) or {}
    if not isinstance(qa, dict):
        raise ConfigError("qa must be a mapping")
    qa_cases = qa.get("cases", []) or []
    if not isinstance(qa_cases, list):
        raise ConfigError("qa.cases must be a list")
    qa_ids: set[str] = set()
    for case in qa_cases:
        if not isinstance(case, dict):
            raise ConfigError("each qa.cases item must be a mapping")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in qa_ids:
            raise ConfigError("QA case IDs must be non-empty and unique")
        qa_ids.add(case_id)
        if not isinstance(case.get("area"), str) or not case.get("area"):
            raise ConfigError(f"qa.cases.{case_id}.area is required")
        if case.get("severity", "warning") not in {"critical", "warning", "info"}:
            raise ConfigError(f"qa.cases.{case_id}.severity is invalid")
        if not isinstance(case.get("description"), str) or not case.get("description"):
            raise ConfigError(f"qa.cases.{case_id}.description is required")
        if not isinstance(case.get("requires_effects", False), bool):
            raise ConfigError(f"qa.cases.{case_id}.requires_effects must be a boolean")
        if not isinstance(case.get("required", True), bool):
            raise ConfigError(f"qa.cases.{case_id}.required must be a boolean")

    documentation = data.get("documentation", {}) or {}
    if not isinstance(documentation, dict):
        raise ConfigError("documentation must be a mapping")
    if not isinstance(documentation.get("require_sync", False), bool):
        raise ConfigError("documentation.require_sync must be a boolean")
    if documentation.get("require_sync", False) and not documentation.get("provider"):
        raise ConfigError("documentation.provider is required when synchronization is required")
    if documentation.get("summary_mode", "findings-focused") not in {"findings-focused", "full"}:
        raise ConfigError("documentation.summary_mode must be findings-focused or full")

    forbidden_fragments = ("password=", "token=", "secret=")
    serialized = repr(data).lower()
    if any(fragment in serialized for fragment in forbidden_fragments):
        raise ConfigError("Potential inline secret detected; use environment variables/secret provider")
