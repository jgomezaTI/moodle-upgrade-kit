import pytest

from moodle_upgrade.config import validate_config, ConfigError


def base_config():
    return {
        "project": {"name": "demo", "environment": "staging"},
        "moodle": {"root": "/var/www/moodle", "base_url": "https://example.invalid", "target_version": "5.0"},
        "safety": {"allow_mutation": False, "require_human_gate": True},
    }


def test_minimal_config_valid():
    validate_config(base_config())


def test_production_cannot_disable_gate():
    cfg = base_config()
    cfg["project"]["environment"] = "production"
    cfg["safety"]["allow_mutation"] = True
    cfg["safety"]["require_human_gate"] = False
    with pytest.raises(ConfigError):
        validate_config(cfg)
