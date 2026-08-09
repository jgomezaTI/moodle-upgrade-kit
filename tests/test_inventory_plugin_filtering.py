from pathlib import Path

from moodle_upgrade.inventory import _plugins


def test_plugin_inventory_skips_internal_directories_without_version_php(tmp_path: Path):
    root = tmp_path / "moodle"
    real = root / "blocks" / "html"
    internal_classes = root / "blocks" / "classes"
    internal_tests = root / "blocks" / "tests"

    real.mkdir(parents=True)
    internal_classes.mkdir(parents=True)
    internal_tests.mkdir(parents=True)

    (real / "version.php").write_text(
        "<?php\n$plugin->component = 'block_html';\n$plugin->version = 2021051700;\n$plugin->requires = 2021051100;\n",
        encoding="utf-8",
    )

    result = _plugins(root, ["blocks"], [])
    paths = [item["component_path"] for item in result]

    assert paths == ["blocks/html"]


def test_explicit_custom_path_without_version_php_is_still_surfaced(tmp_path: Path):
    root = tmp_path / "moodle"
    custom = root / "auth" / "legacycustom"
    custom.mkdir(parents=True)

    result = _plugins(root, ["auth"], ["auth/legacycustom"])

    assert len(result) == 1
    assert result[0]["component_path"] == "auth/legacycustom"
    assert result[0]["classification"] == "custom"
    assert result[0]["has_version_php"] is False
