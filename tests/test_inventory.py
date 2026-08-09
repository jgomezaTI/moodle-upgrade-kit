from pathlib import Path
import subprocess

import moodle_upgrade.inventory as inventory_module
from moodle_upgrade.inventory import _database_platform, _git_state, collect_inventory


def base_config(root: Path):
    return {
        "project": {"name": "demo", "environment": "staging"},
        "moodle": {
            "root": str(root),
            "moodledata": str(root / "moodledata"),
            "base_url": "https://example.invalid",
            "target_version": "5.0",
            "cron_command": "php admin/cli/cron.php",
        },
        "safety": {"allow_mutation": False, "require_human_gate": True},
        "plugins": {"custom_roots": ["local"], "custom_paths": []},
        "custom_code": {"paths": [], "auto_detect_top_level": True},
        "backup": {"paths": []},
    }


def create_fake_moodle(root: Path):
    (root / "admin" / "cli").mkdir(parents=True)
    (root / "local" / "sample").mkdir(parents=True)
    (root / "moodledata").mkdir()
    (root / "config.php").write_text("<?php // no secrets here\n", encoding="utf-8")
    (root / "version.php").write_text(
        "<?php\n$version = 2025041400.00;\n$release = '5.0';\n$branch = '500';\n",
        encoding="utf-8",
    )
    (root / "admin" / "cli" / "cron.php").write_text("<?php\n", encoding="utf-8")
    (root / "local" / "sample" / "version.php").write_text(
        "<?php\n$plugin->component = 'local_sample';\n$plugin->version = 2026010100;\n$plugin->requires = 2025041400;\n",
        encoding="utf-8",
    )


def test_inventory_detects_moodle_markers_and_plugin(tmp_path):
    root = tmp_path / "moodle"
    create_fake_moodle(root)

    result = collect_inventory(base_config(root))

    assert result["identity"]["markers"]["version.php"] is True
    assert result["identity"]["moodle_version"]["release"] == "5.0"
    assert result["identity"]["moodle_version"]["branch"] == "500"
    assert result["cron"]["cli_exists"] is True
    assert result["summary"]["plugin_count"] == 1
    assert result["summary"]["custom_plugin_count"] == 1
    assert result["plugins"][0]["component"] == "local_sample"
    assert result["plugins"][0]["classification"] == "custom"
    assert not any(x["code"] == "MOODLE_MARKERS_MISSING" for x in result["findings"])


def test_inventory_blocks_invalid_moodle_root(tmp_path):
    root = tmp_path / "not-moodle"
    root.mkdir()

    result = collect_inventory(base_config(root))

    assert result["summary"]["critical"] >= 1
    assert any(x["code"] == "MOODLE_MARKERS_MISSING" for x in result["findings"])


def test_git_state_discovers_parent_repository(tmp_path):
    repo = tmp_path / "repo"
    root = repo / "public_html"
    root.mkdir(parents=True)
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)

    result = _git_state(root)

    assert result["is_repo"] is True
    assert Path(result["repo_root"]) == repo.resolve()


def test_inventory_records_custom_code_and_non_core_candidate(tmp_path):
    root = tmp_path / "moodle"
    create_fake_moodle(root)
    portal = root / "portal_v3"
    (portal / "app").mkdir(parents=True)
    (portal / "index.php").write_text("<?php\n", encoding="utf-8")
    (portal / "app" / "main.js").write_text("console.log('ok');\n", encoding="utf-8")

    cfg = base_config(root)
    cfg["custom_code"]["paths"] = ["portal_v3"]
    result = collect_inventory(cfg)

    portal_result = result["custom_code"]["configured_paths"][0]
    assert portal_result["exists"] is True
    assert portal_result["file_count"] == 2
    assert portal_result["top_extensions"][".php"] == 1
    assert "portal_v3" in result["custom_code"]["non_core_top_level_candidates"]
    assert result["summary"]["configured_custom_code_count"] == 1


def test_inventory_reads_php_from_docker_runtime(tmp_path, monkeypatch):
    root = tmp_path / "moodle"
    create_fake_moodle(root)
    cfg = base_config(root)
    cfg["runtime"] = {
        "type": "docker",
        "container": "demo-php-1",
        "moodle_root": "/var/www/html",
        "moodledata": "/var/www/moodledata",
    }

    commands = []

    def fake_run(command, cwd=None, timeout=10):
        commands.append(command)
        if command[:4] == ["docker", "inspect", "-f", "{{.State.Running}}|{{.Config.Image}}"]:
            return {"ok": True, "returncode": 0, "stdout": "true|example/php-moodle:5.6", "stderr": ""}
        if command[:3] == ["docker", "exec", "demo-php-1"] and command[3:5] == ["php", "-v"]:
            return {"ok": True, "returncode": 0, "stdout": "PHP 5.6.40 (cli)", "stderr": ""}
        if command[:3] == ["docker", "exec", "demo-php-1"] and command[3:5] == ["php", "-m"]:
            return {"ok": True, "returncode": 0, "stdout": "[PHP Modules]\nCore\njson\nmysqli\n[Zend Modules]\n", "stderr": ""}
        if command[:3] == ["docker", "exec", "demo-php-1"] and command[3] == "test":
            return {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}
        if command[:3] == ["git", "rev-parse", "--show-toplevel"]:
            return {"ok": False, "returncode": 128, "stdout": "", "stderr": "not a repository"}
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(inventory_module, "_run", fake_run)
    result = collect_inventory(cfg)

    assert result["platform"]["runtime"]["type"] == "docker"
    assert result["platform"]["runtime"]["running"] is True
    assert result["platform"]["runtime"]["image"] == "example/php-moodle:5.6"
    assert result["platform"]["php"]["version_line"] == "PHP 5.6.40 (cli)"
    assert "mysqli" in result["platform"]["php"]["modules"]
    assert "[PHP Modules]" not in result["platform"]["php"]["modules"]
    assert not any(x["code"] == "DOCKER_CONTAINER_UNAVAILABLE" for x in result["findings"])
    assert ["docker", "exec", "demo-php-1", "php", "-v"] in commands


def test_database_runtime_records_image_and_version(monkeypatch):
    def fake_run(command, cwd=None, timeout=10):
        if command[:4] == ["docker", "inspect", "-f", "{{.State.Running}}|{{.Config.Image}}"]:
            return {"ok": True, "returncode": 0, "stdout": "true|mysql:8.0.41", "stderr": ""}
        if command == ["docker", "exec", "demo-db-1", "mysqld", "--version"]:
            return {"ok": True, "returncode": 0, "stdout": "mysqld  Ver 8.0.41 for Linux on x86_64", "stderr": ""}
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(inventory_module, "_run", fake_run)
    result = _database_platform({"database": {"driver": "mysql", "runtime_container": "demo-db-1"}})

    assert result["driver"] == "mysql"
    assert result["running"] is True
    assert result["image"] == "mysql:8.0.41"
    assert "8.0.41" in result["version_line"]
