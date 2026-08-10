from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
import json

from moodle_upgrade.compatibility import BASE_REQUIRED_EXTENSIONS, assess_compatibility
from moodle_upgrade.plugins import analyze_plugins
from moodle_upgrade.database import is_read_only_sql, run_database_checks
from moodle_upgrade.baseline import capture_baseline
from moodle_upgrade.backup import verify_backups
from moodle_upgrade.validate import validate_upgrade
from moodle_upgrade.execution import command_argv
from moodle_upgrade.upgrade import execute_upgrade
from moodle_upgrade.rollback import execute_rollback
from moodle_upgrade.document import generate_report


def inventory_fixture(tmp_path: Path, php="7.4.33", target="4.1", current="3.11.18"):
    root = tmp_path / "public_html"
    (root / "local" / "custom").mkdir(parents=True)
    (root / "local" / "custom" / "legacy.php").write_text("<?php\n", encoding="utf-8")
    modules = sorted(BASE_REQUIRED_EXTENSIONS | {"mysqli", "sodium", "exif"})
    return {
        "identity": {"project": {"name": "demo", "environment": "staging"}, "moodle_root": str(root), "moodledata": str(root / "moodledata"), "target_version": target, "moodle_version": {"release": current, "branch": "311"}},
        "platform": {
            "runtime": {"type": "docker", "container": "php-1", "running": True},
            "php": {"available": True, "version_line": f"PHP {php} (cli)", "modules": modules, "settings": {"max_input_vars": "5000", "memory_limit": "256M", "int_size": 8}},
            "database": {"driver": "mysql", "running": True, "image": "mysql:8.0.41", "version_line": "mysqld Ver 8.0.41", "prefix": "mdl_"},
            "git": {"is_repo": True, "repo_root": str(tmp_path), "branch": "main", "head": "abc", "dirty": False},
        },
        "plugins": [{"component_path": "local/custom", "component": "local_custom", "classification": "custom", "version": "1", "requires": "2021051700"}],
        "custom_code": {"configured_paths": []}, "cron": {"configured": True, "cli_exists": True}, "findings": [], "summary": {"critical": 0, "warning": 0},
    }


def config_fixture(tmp_path: Path, target="4.1"):
    return {
        "project": {"name": "demo", "environment": "staging"},
        "moodle": {
            "root": str(tmp_path / "public_html"), "moodledata": str(tmp_path / "public_html" / "moodledata"), "base_url": "https://example.invalid", "target_version": target,
            "maintenance_mode_command": ["php", "admin/cli/maintenance.php", "--enable"], "maintenance_off_command": ["php", "admin/cli/maintenance.php", "--disable"],
            "upgrade_command": ["php", "admin/cli/upgrade.php", "--non-interactive"], "purge_caches_command": ["php", "admin/cli/purge_caches.php"], "cron_command": ["php", "admin/cli/cron.php"],
        },
        "runtime": {"type": "local"},
        "safety": {"allow_mutation": False, "require_environment": "staging", "require_clean_git": True, "require_backup_check": True, "require_human_gate": True, "max_backup_age_hours": 24},
        "plugins": {"custom_roots": ["local"], "custom_paths": [], "compatibility": {}}, "custom_code": {"paths": []},
        "endpoints": [{"id": "home", "path": "/", "expected_status": 200}], "logs": {"files": [], "patterns": {"critical": ["Fatal"], "warning": ["Warning"]}},
        "database": {"driver": "mysql", "checks": []}, "backup": {"paths": [], "required_components": []},
        "upgrade": {"code_transition_command": ["git", "checkout", "MOODLE_401_STABLE"], "run_cron_after": True}, "rollback": {"commands": []},
    }


def test_compatibility_flags_enaex_php_blocker(tmp_path):
    result = assess_compatibility(inventory_fixture(tmp_path, php="5.6.40"), "4.1")
    codes = {finding["code"] for finding in result["findings"]}
    assert "TARGET_PHP_TOO_OLD" in codes
    assert "SOURCE_PHP_TOO_OLD" in codes
    assert result["summary"]["compatible"] is False
    json.dumps(result)


def test_compatibility_allows_patch_within_supported_php_branch(tmp_path):
    result = assess_compatibility(inventory_fixture(tmp_path, php="8.1.30"), "4.1")
    critical_codes = {finding["code"] for finding in result["findings"] if finding["severity"] == "critical"}
    assert "TARGET_PHP_TOO_NEW" not in critical_codes
    assert result["summary"]["compatible"] is True


def test_target_43_requires_proven_prefix_and_64bit(tmp_path):
    inventory = inventory_fixture(tmp_path, php="8.1.20", target="4.3", current="3.11.18")
    inventory["platform"]["database"]["prefix"] = None
    inventory["platform"]["php"]["settings"]["int_size"] = None
    result = assess_compatibility(inventory, "4.3")
    codes = {finding["code"] for finding in result["findings"]}
    assert "DATABASE_PREFIX_UNKNOWN" in codes
    assert "PHP_64BIT_UNKNOWN" in codes
    assert result["summary"]["compatible"] is False


def test_plugin_scan_detects_removed_php_api(tmp_path):
    cfg = config_fixture(tmp_path)
    inventory = inventory_fixture(tmp_path)
    legacy = Path(cfg["moodle"]["root"]) / "local" / "custom" / "legacy.php"
    legacy.write_text('<?php\nmysql_query("select 1");\n', encoding="utf-8")
    result = analyze_plugins(cfg, inventory)
    assert "CODE_PHP_MYSQL_EXTENSION_REMOVED" in {finding["code"] for finding in result["findings"]}
    assert result["summary"]["critical"] >= 1


def test_database_policy_rejects_mutation_and_accepts_select():
    assert is_read_only_sql("SELECT id FROM mdl_user;") is True
    assert is_read_only_sql("UPDATE mdl_user SET deleted = 1;") is False
    assert is_read_only_sql("WITH x AS (SELECT 1) SELECT * FROM x;") is True


def test_database_without_checks_is_explicitly_incomplete():
    result = run_database_checks({"database": {"driver": "mysql", "checks": []}})

    assert result["summary"]["configured"] == 0
    assert result["summary"]["executed"] == 0
    assert result["summary"]["complete"] is False


def test_database_check_keeps_secret_out_of_evidence(tmp_path, monkeypatch):
    sql_file = tmp_path / "check.sql"
    sql_file.write_text("SELECT id FROM mdl_user WHERE 1=0;\n", encoding="utf-8")
    for name, value in {"DB_HOST": "db", "DB_NAME": "moodle", "DB_USER": "user", "DB_PASS": "supersecret"}.items():
        monkeypatch.setenv(name, value)
    cfg = config_fixture(tmp_path)
    cfg["database"] = {"driver": "mysql", "connection_env": {"host": "DB_HOST", "database": "DB_NAME", "user": "DB_USER", "password": "DB_PASS"}, "checks": [{"id": "empty", "severity": "critical", "sql_file": str(sql_file), "expect": "empty"}]}
    seen = {}
    def runner(command, sql_text, env, timeout):
        seen["command"] = command
        return SimpleNamespace(returncode=0, stdout="id\n", stderr="")
    result = run_database_checks(cfg, runner=runner)
    assert result["checks"][0]["ok"] is True
    assert "supersecret" not in json.dumps(result)
    assert "supersecret" not in " ".join(seen["command"])


def test_database_can_use_named_environment_inside_runtime_container(tmp_path):
    sql_file = tmp_path / "health.sql"
    sql_file.write_text("SELECT 1 AS ok;\n", encoding="utf-8")
    cfg = config_fixture(tmp_path)
    cfg["database"] = {
        "driver": "mysql",
        "runtime_container": "db-1",
        "container_connection_env": {
            "database": "MYSQL_DATABASE",
            "user": "MYSQL_USER",
            "password": "MYSQL_PASSWORD",
        },
        "container_host": "127.0.0.1",
        "container_port": 3306,
        "checks": [{"id": "health", "severity": "critical", "sql_file": str(sql_file), "expect": "nonempty"}],
    }
    seen = {}

    def runner(command, sql_text, env, timeout):
        seen.update({"command": command, "sql": sql_text, "env": env, "timeout": timeout})
        return SimpleNamespace(returncode=0, stdout="ok\n1\n", stderr="")

    result = run_database_checks(cfg, runner=runner)

    assert result["execution_mode"] == "docker-env:db-1"
    assert result["summary"]["complete"] is True
    assert result["checks"][0]["sample"] == [{"ok": "1"}]
    assert seen["command"][:6] == ["docker", "exec", "-i", "db-1", "sh", "-c"]
    assert seen["command"][-5:] == ["MYSQL_DATABASE", "MYSQL_USER", "MYSQL_PASSWORD", "127.0.0.1", "3306"]
    assert "supersecret" not in " ".join(seen["command"])


def test_baseline_orchestrates_read_only_checks(tmp_path):
    cfg = config_fixture(tmp_path)
    cfg["database"]["checks"] = [{"id": "health", "sql_file": "health.sql", "expect": "nonempty", "severity": "critical"}]
    cfg["logs"]["sources"] = [{"id": "php", "type": "docker", "container": "php-1", "required": True}]
    result = capture_baseline(
        cfg, inventory_fixture(tmp_path),
        endpoint_runner=lambda config: [{"id": "home", "executed": True, "ok": True, "status": 200, "expected_status": 200}],
        database_runner=lambda config: {"checks": [{"id": "health", "executed": True, "ok": True}], "findings": [], "summary": {"critical": 0, "warning": 0, "executed": 1}},
        log_runner=lambda config: {"files": [{"id": "php", "required": True, "executed": True, "readable": True}], "totals": {}, "summary": {"configured": 1, "executed": 1, "readable": 1}},
    )
    assert result["summary"]["complete"] is True


def test_backup_requires_explicit_component_identity(tmp_path):
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    (backup_root / "database-001.sql.gz").write_bytes(b"data")
    cfg = config_fixture(tmp_path)
    cfg["backup"] = {"paths": [str(backup_root)], "required_components": ["database"], "components": {"database": {"globs": ["database-*.sql.gz"]}}, "max_age_hours": 24}
    result = verify_backups(cfg, now=datetime.now(timezone.utc))
    assert result["summary"]["verified"] is True
    cfg["backup"]["required_components"].append("code")
    result = verify_backups(cfg, now=datetime.now(timezone.utc))
    assert result["summary"]["verified"] is False
    assert any(finding["code"] == "BACKUP_COMPONENT_RULE_MISSING" for finding in result["findings"])


def test_validation_detects_regressions(tmp_path):
    cfg = config_fixture(tmp_path)
    inventory = inventory_fixture(tmp_path)
    inventory["identity"]["moodle_version"]["release"] = "4.1.18"
    baseline = {"identity": {"moodle_version": {"release": "3.11.18"}}, "endpoint_checks": [{"id": "home", "ok": True}], "database_checks": {"checks": [{"id": "db", "executed": True, "ok": True}]}, "log_checks": {"totals": {"critical": 0}}}
    result = validate_upgrade(cfg, baseline, inventory, [{"id": "home", "ok": False}], {"totals": {"critical": 1}}, {"checks": [{"id": "db", "executed": True, "ok": False}], "summary": {"critical": 1}})
    codes = {finding["code"] for finding in result["findings"]}
    assert {"ENDPOINT_REGRESSION", "DATABASE_REGRESSION", "CRITICAL_LOG_REGRESSION"} <= codes
    assert result["summary"]["accepted"] is False


def test_rollback_validation_confirms_restored_branch(tmp_path):
    cfg = config_fixture(tmp_path)
    inventory = inventory_fixture(tmp_path)
    baseline = {"identity": {"moodle_version": {"release": "3.11.18"}}, "endpoint_checks": [], "database_checks": {"checks": []}, "log_checks": {"totals": {}}}
    result = validate_upgrade(cfg, baseline, inventory, [], {"totals": {}}, {"checks": [], "summary": {"critical": 0}}, mode="rollback")
    assert result["rollback_confirmed"] is True
    assert result["summary"]["accepted"] is True


def test_shell_control_and_secret_args_are_rejected():
    for command in ["php x.php && rm -rf /", ["mysql", "--password=abc"], "echo $(whoami)"]:
        try:
            command_argv(command)
        except ValueError:
            continue
        raise AssertionError(f"command should be rejected: {command!r}")


def _successful_runner(argv, **kwargs):
    return SimpleNamespace(returncode=0, stdout="ok", stderr="")


def test_upgrade_is_blocked_until_safety_gates_pass(tmp_path):
    cfg = config_fixture(tmp_path)
    result = execute_upgrade(cfg, True, inventory_fixture(tmp_path), {"summary": {"compatible": True}}, {"summary": {"verified": True}}, baseline={"summary": {"complete": True}}, plugins={"summary": {"critical": 0}}, runner=_successful_runner)
    assert result["executed"] is False
    assert any(finding["code"] == "MUTATION_DISABLED" for finding in result["findings"])


def test_upgrade_runs_exact_sequence_when_gated(tmp_path):
    cfg = config_fixture(tmp_path)
    cfg["safety"]["allow_mutation"] = True
    calls = []
    def runner(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")
    result = execute_upgrade(cfg, True, inventory_fixture(tmp_path), {"summary": {"compatible": True}}, {"summary": {"verified": True}}, baseline={"summary": {"complete": True}}, plugins={"summary": {"critical": 0}}, runner=runner)
    assert result["summary"]["completed"] is True
    assert [step["id"] for step in result["steps"]] == ["maintenance_on", "code_transition", "moodle_upgrade", "purge_caches", "cron", "maintenance_off"]
    assert len(calls) == 6


def test_rollback_never_infers_restore_commands(tmp_path):
    cfg = config_fixture(tmp_path)
    cfg["safety"]["allow_mutation"] = True
    result = execute_rollback(cfg, True, {"summary": {"verified": True}}, {"summary": {"accepted": False}}, runner=_successful_runner)
    assert result["executed"] is False
    assert any(finding["code"] == "ROLLBACK_PROCEDURE_MISSING" for finding in result["findings"])


def test_document_report_preserves_local_result_when_sync_pending(tmp_path):
    cfg = config_fixture(tmp_path)
    cfg["documentation"] = {"provider": "google-drive", "require_sync": True, "redact_patterns": []}
    run = tmp_path / "RUN-1"
    run.mkdir()
    (run / "validation.json").write_text(json.dumps({"data": {"summary": {"accepted": True}, "findings": []}}), encoding="utf-8")
    markdown, result = generate_report(cfg, "RUN-1", base_dir=tmp_path)
    assert "Result: **PASS**" in markdown
    assert result["summary"]["report_generated"] is True
    assert result["sync"]["status"] == "external-adapter-required"
