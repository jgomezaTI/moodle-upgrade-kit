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


def test_docker_runtime_requires_container_and_root():
    cfg = base_config()
    cfg["runtime"] = {"type": "docker"}
    with pytest.raises(ConfigError, match="runtime.container"):
        validate_config(cfg)


def test_docker_runtime_valid():
    cfg = base_config()
    cfg["runtime"] = {
        "type": "docker",
        "container": "moodle-php-1",
        "moodle_root": "/var/www/html",
        "moodledata": "/var/www/moodledata",
    }
    validate_config(cfg)


def test_local_git_core_reference_is_valid():
    cfg = base_config()
    cfg["plugins"] = {
        "core_reference": {
            "repository": "/srv/moodle-upstream",
            "ref": "v5.0.3",
            "root": ".",
            "max_files": 100000,
            "max_files_per_component": 20000,
            "max_changed_files": 5000,
        }
    }

    validate_config(cfg)


@pytest.mark.parametrize(
    ("core_reference", "message"),
    [
        ("v5.0.3", "must be a mapping"),
        ({"repository": "relative/path", "ref": "v5.0.3"}, "absolute local path"),
        ({"repository": "/srv/moodle-upstream", "ref": ""}, "ref is required"),
        ({"repository": "/srv/moodle-upstream", "ref": "--help"}, "unsafe characters"),
        ({"repository": "/srv/moodle-upstream", "ref": "v5.0.3", "root": "../escape"}, "without traversal"),
        ({"repository": "/srv/moodle-upstream", "ref": "v5.0.3", "max_files": 0}, "positive integer"),
    ],
)
def test_invalid_core_reference_config_is_rejected(core_reference, message):
    cfg = base_config()
    cfg["plugins"] = {"core_reference": core_reference}

    with pytest.raises(ConfigError, match=message):
        validate_config(cfg)


def test_legacy_and_structured_core_references_cannot_be_combined():
    cfg = base_config()
    cfg["plugins"] = {
        "core_reference_ref": "v5.0.3",
        "core_reference": {"repository": "/srv/moodle-upstream", "ref": "v5.0.3"},
    }

    with pytest.raises(ConfigError, match="not both"):
        validate_config(cfg)
