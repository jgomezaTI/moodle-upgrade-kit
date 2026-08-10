from __future__ import annotations

from pathlib import Path
from pathlib import PurePosixPath
import re
from typing import Any

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

    forbidden_fragments = ("password=", "token=", "secret=")
    serialized = repr(data).lower()
    if any(fragment in serialized for fragment in forbidden_fragments):
        raise ConfigError("Potential inline secret detected; use environment variables/secret provider")
