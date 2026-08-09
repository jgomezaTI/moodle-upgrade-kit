from pathlib import Path

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


def test_inventory_detects_moodle_markers_and_plugin(tmp_path):
    root = tmp_path / "moodle"
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
