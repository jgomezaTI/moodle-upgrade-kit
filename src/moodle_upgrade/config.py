from __future__ import annotations

from pathlib import Path
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

    for key in ("name", "environment"):
        if not project.get(key):
            raise ConfigError(f"project.{key} is required")
    for key in ("root", "base_url", "target_version"):
        if not moodle.get(key):
            raise ConfigError(f"moodle.{key} is required")

    if project.get("environment") == "production" and safety.get("allow_mutation"):
        if not safety.get("require_human_gate", True):
            raise ConfigError("Production mutation cannot disable the human gate")

    forbidden_fragments = ("password=", "token=", "secret=")
    serialized = repr(data).lower()
    if any(fragment in serialized for fragment in forbidden_fragments):
        raise ConfigError("Potential inline secret detected; use environment variables/secret provider")
