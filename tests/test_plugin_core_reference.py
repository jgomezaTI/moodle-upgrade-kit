from pathlib import Path
import shutil
import subprocess

from moodle_upgrade.plugins import analyze_plugins


SOURCE_RELEASE = "4.4.6 (Build: 20250609)"
SOURCE_VERSION = "2024042206.00"
SOURCE_BRANCH = "404"


def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _write_version(path: Path, *, release: str = SOURCE_RELEASE, version: str = SOURCE_VERSION, branch: str = SOURCE_BRANCH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "<?php\n"
        f"$version = {version};\n"
        f"$release = '{release}';\n"
        f"$branch = '{branch}';\n",
        encoding="utf-8",
    )


def _create_core_repository(tmp_path: Path, tree_root: str = "moodle") -> tuple[Path, Path]:
    repository = tmp_path / "upstream-core"
    repository.mkdir()
    _git(repository, "init", "-q")
    _git(repository, "config", "user.email", "tests@example.invalid")
    _git(repository, "config", "user.name", "Moodle Upgrade Kit Tests")

    core_root = repository / tree_root
    _write_version(core_root / "version.php")
    _write_version(core_root / "blocks" / "html" / "version.php")
    (core_root / "blocks" / "html" / "lib.php").write_text("<?php\nfunction block_html_core_example() {}\n", encoding="utf-8")
    _write_version(core_root / "report" / "log" / "version.php")
    (core_root / "report" / "log" / "lib.php").write_text("<?php\nfunction report_log_core_example() {}\n", encoding="utf-8")

    _git(repository, "add", tree_root)
    _git(repository, "commit", "-qm", "source core")
    _git(repository, "tag", "source-core")
    return repository, core_root


def _inventory(repo_root: Path | None = None) -> dict:
    return {
        "identity": {
            "moodle_version": {
                "release": SOURCE_RELEASE,
                "version": SOURCE_VERSION,
                "branch": SOURCE_BRANCH,
            },
            "target_version": "5.0",
        },
        "plugins": [
            {"component_path": "blocks/html", "component": "block_html", "classification": "unclassified"},
            {"component_path": "report/log", "component": "report_log", "classification": "unclassified"},
            {"component_path": "auth/external", "component": "auth_external", "classification": "unclassified"},
            {"component_path": "local/site", "component": "local_site", "classification": "custom"},
        ],
        "custom_code": {"configured_paths": []},
        "platform": {"git": {"repo_root": str(repo_root) if repo_root else None}},
    }


def _config(moodle_root: Path, repository: Path, tree_root: str = "moodle") -> dict:
    return {
        "moodle": {"root": str(moodle_root), "target_version": "5.0"},
        "plugins": {
            "compatibility": {},
            "core_reference": {
                "repository": str(repository),
                "ref": "source-core",
                "root": tree_root,
            },
        },
        "custom_code": {"scan_max_files_per_path": 100, "scan_max_bytes_per_file": 100_000},
    }


def _add_non_core_plugins(moodle_root: Path) -> None:
    _write_version(moodle_root / "auth" / "external" / "version.php")
    (moodle_root / "auth" / "external" / "legacy.php").write_text('<?php\nmysql_query("select 1");\n', encoding="utf-8")
    _write_version(moodle_root / "local" / "site" / "version.php")
    (moodle_root / "local" / "site" / "lib.php").write_text("<?php\nfunction local_site_example() {}\n", encoding="utf-8")


def test_verified_source_core_classifies_and_scans_only_upgrade_owned_code(tmp_path: Path):
    repository, source_root = _create_core_repository(tmp_path)
    moodle_root = tmp_path / "installed-moodle"
    shutil.copytree(source_root, moodle_root)
    (moodle_root / "report" / "log" / "lib.php").write_text("<?php\n$parts = split(',', $value);\n", encoding="utf-8")
    _add_non_core_plugins(moodle_root)

    result = analyze_plugins(_config(moodle_root, repository), _inventory())
    plugins = {plugin["component_path"]: plugin for plugin in result["plugins"]}

    assert result["core_reference"]["verified"] is True
    assert result["core_reference"]["moodle_version"] == {
        "release": SOURCE_RELEASE,
        "version": SOURCE_VERSION,
        "branch": SOURCE_BRANCH,
    }
    assert plugins["blocks/html"]["classification"] == "core"
    assert plugins["blocks/html"]["review_status"] == "core-reference-match"
    assert plugins["report/log"]["classification"] == "core-modified"
    assert plugins["report/log"]["core_reference_comparison"]["changed_files"] == ["report/log/lib.php"]
    assert plugins["auth/external"]["classification"] == "non-core"
    assert plugins["local/site"]["classification"] == "custom"
    assert {scan["path"] for scan in result["custom_code_scans"]} == {"report/log", "auth/external", "local/site"}
    assert {hit["id"] for hit in result["risk_hits"]} == {"php_split_removed", "php_mysql_extension_removed"}
    assert result["core_modifications"] == ["report/log/lib.php"]
    assert result["core_modification_count"] == 1
    assert result["summary"]["review_count"] == 3
    assert result["summary"]["classification_counts"] == {
        "core": 1,
        "core-modified": 1,
        "custom": 1,
        "non-core": 1,
    }


def test_version_mismatch_never_claims_core_classification(tmp_path: Path):
    repository, source_root = _create_core_repository(tmp_path)
    moodle_root = tmp_path / "installed-moodle"
    shutil.copytree(source_root, moodle_root)
    inventory = _inventory()
    inventory["identity"]["moodle_version"]["release"] = "4.4.7 (Build: 20250714)"

    result = analyze_plugins(_config(moodle_root, repository), inventory)

    assert result["core_reference"]["verified"] is False
    assert result["core_reference"]["status"] == "version-mismatch"
    assert "CORE_REFERENCE_VERSION_MISMATCH" in {finding["code"] for finding in result["findings"]}
    assert all(plugin["classification"] != "core" for plugin in result["plugins"])
    assert result["plugins"][0]["review_status"] == "core-comparison-required"


def test_legacy_core_reference_ref_uses_inventory_repository_and_moodle_tree_root(tmp_path: Path):
    repository, moodle_root = _create_core_repository(tmp_path, tree_root="public_html")
    inventory = _inventory(repository)
    config = _config(moodle_root, repository, tree_root="public_html")
    config["plugins"] = {"compatibility": {}, "core_reference_ref": "source-core"}

    result = analyze_plugins(config, inventory)

    plugins = {plugin["component_path"]: plugin for plugin in result["plugins"]}
    assert result["core_reference"]["verified"] is True
    assert result["core_reference"]["root"] == "public_html"
    assert plugins["blocks/html"]["classification"] == "core"
