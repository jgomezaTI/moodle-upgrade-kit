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


def test_base_url_cannot_contain_credentials():
    cfg = base_config()
    cfg["moodle"]["base_url"] = "https://user:password@example.invalid"

    with pytest.raises(ConfigError, match="must not contain credentials"):
        validate_config(cfg)


def test_endpoint_methods_are_restricted_to_read_only_requests():
    cfg = base_config()
    cfg["endpoints"] = [{"id": "unsafe", "path": "/users", "method": "POST"}]

    with pytest.raises(ConfigError, match="read-only"):
        validate_config(cfg)


def test_production_endpoint_cannot_disable_tls_verification():
    cfg = base_config()
    cfg["project"]["environment"] = "production"
    cfg["endpoints"] = [{"id": "home", "path": "/", "verify_tls": False}]

    with pytest.raises(ConfigError, match="cannot disable TLS"):
        validate_config(cfg)


def test_docker_log_source_requires_safe_container_name():
    cfg = base_config()
    cfg["logs"] = {"sources": [{"id": "php", "type": "docker", "container": "php;unsafe"}]}

    with pytest.raises(ConfigError, match="argv-safe"):
        validate_config(cfg)


def test_database_container_environment_names_are_valid():
    cfg = base_config()
    cfg["database"] = {
        "driver": "mysql",
        "runtime_container": "moodle-db-1",
        "container_connection_env": {
            "database": "MYSQL_DATABASE",
            "user": "MYSQL_USER",
            "password": "MYSQL_PASSWORD",
        },
        "container_host": "127.0.0.1",
        "container_port": 3306,
    }

    validate_config(cfg)


def test_database_container_environment_rejects_unsafe_name():
    cfg = base_config()
    cfg["database"] = {
        "driver": "mysql",
        "runtime_container": "moodle-db-1",
        "container_connection_env": {"database": "MYSQL_DATABASE;env", "user": "MYSQL_USER"},
    }

    with pytest.raises(ConfigError, match="must name"):
        validate_config(cfg)


def test_qa_case_ids_are_unique_and_effects_are_explicit():
    cfg = base_config()
    cfg["qa"] = {"cases": [
        {"id": "login", "area": "auth", "description": "Log in.", "requires_effects": False},
        {"id": "login", "area": "auth", "description": "Log in again.", "requires_effects": False},
    ]}
    with pytest.raises(ConfigError, match="unique"):
        validate_config(cfg)

    cfg["qa"]["cases"] = [{"id": "login", "area": "auth", "description": "Log in.", "requires_effects": "no"}]
    with pytest.raises(ConfigError, match="boolean"):
        validate_config(cfg)

    cfg["qa"]["cases"] = [{"id": "login", "area": "auth", "description": "Log in.", "required": "yes"}]
    with pytest.raises(ConfigError, match="required must be a boolean"):
        validate_config(cfg)


def test_required_document_sync_needs_a_provider():
    cfg = base_config()
    cfg["documentation"] = {"require_sync": True}

    with pytest.raises(ConfigError, match="provider"):
        validate_config(cfg)
