from pathlib import Path

import moodle_upgrade.inventory as inventory_module
from moodle_upgrade.inventory import collect_inventory


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
        "plugins": {"custom_roots": ["local"]},
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
    (root / "local" / "sample" / "version.php").write_text("<?php\n", encoding="utf-8")


def test_inventory_detects_moodle_markers_and_plugin(tmp_path):
    root = tmp_path / "moodle"
    create_fake_moodle(root)

    result = collect_inventory(base_config(root))

    assert result["identity"]["markers"]["version.php"] is True
    assert result["identity"]["moodle_version"]["release"] == "5.0"
    assert result["identity"]["moodle_version"]["branch"] == "500"
    assert result["cron"]["cli_exists"] is True
    assert result["summary"]["plugin_count"] == 1
    assert not any(x["code"] == "MOODLE_MARKERS_MISSING" for x in result["findings"])


def test_inventory_blocks_invalid_moodle_root(tmp_path):
    root = tmp_path / "not-moodle"
    root.mkdir()

    result = collect_inventory(base_config(root))

    assert result["summary"]["critical"] >= 1
    assert any(x["code"] == "MOODLE_MARKERS_MISSING" for x in result["findings"])


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
        if command[:4] == ["docker", "inspect", "-f", "{{.State.Running}}"]:
            return {"ok": True, "returncode": 0, "stdout": "true", "stderr": ""}
        if command[:3] == ["docker", "exec", "demo-php-1"] and command[3:5] == ["php", "-v"]:
            return {"ok": True, "returncode": 0, "stdout": "PHP 5.6.40 (cli)", "stderr": ""}
        if command[:3] == ["docker", "exec", "demo-php-1"] and command[3:5] == ["php", "-m"]:
            return {"ok": True, "returncode": 0, "stdout": "Core\njson\nmysqli\n", "stderr": ""}
        if command[:3] == ["docker", "exec", "demo-php-1"] and command[3] == "test":
            return {"ok": True, "returncode": 0, "stdout": "", "stderr": ""}
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(inventory_module, "_run", fake_run)
    result = collect_inventory(cfg)

    assert result["platform"]["runtime"]["type"] == "docker"
    assert result["platform"]["runtime"]["running"] is True
    assert result["platform"]["php"]["version_line"] == "PHP 5.6.40 (cli)"
    assert "mysqli" in result["platform"]["php"]["modules"]
    assert not any(x["code"] == "DOCKER_CONTAINER_UNAVAILABLE" for x in result["findings"])
    assert ["docker", "exec", "demo-php-1", "php", "-v"] in commands
