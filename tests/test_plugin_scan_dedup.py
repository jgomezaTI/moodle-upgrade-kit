from pathlib import Path

from moodle_upgrade.plugins import _deduplicate_scan_targets, analyze_plugins


def test_deduplicate_scan_targets_prefers_parent_regardless_of_config_order(tmp_path: Path):
    batch = tmp_path / "batch"
    edx = batch / "edx"
    proofpoint = batch / "proofpoint"
    edx.mkdir(parents=True)
    proofpoint.mkdir(parents=True)

    selected, covered = _deduplicate_scan_targets([
        ("../batch/edx", edx),
        ("../batch/proofpoint", proofpoint),
        ("../batch", batch),
    ])

    assert selected == [("../batch", batch.resolve())]
    assert covered == [
        {
            "path": "../batch/edx",
            "resolved_path": str(edx.resolve()),
            "covered_by": "../batch",
            "covered_by_resolved_path": str(batch.resolve()),
        },
        {
            "path": "../batch/proofpoint",
            "resolved_path": str(proofpoint.resolve()),
            "covered_by": "../batch",
            "covered_by_resolved_path": str(batch.resolve()),
        },
    ]


def test_analyze_plugins_scans_nested_custom_code_only_once(tmp_path: Path):
    moodle_root = tmp_path / "public_html"
    moodle_root.mkdir()
    batch = tmp_path / "batch"
    edx = batch / "edx"
    edx.mkdir(parents=True)
    (edx / "legacy.php").write_text('<?php\nmysql_query("select 1");\n', encoding="utf-8")

    config = {
        "moodle": {"root": str(moodle_root), "target_version": "4.1"},
        "plugins": {},
        "custom_code": {"scan_max_files_per_path": 20000, "scan_max_bytes_per_file": 1000000},
    }
    inventory = {
        "plugins": [],
        "custom_code": {
            "configured_paths": [
                {"path": "../batch/edx", "resolved_path": str(edx), "scope": "project", "exists": True},
                {"path": "../batch", "resolved_path": str(batch), "scope": "project", "exists": True},
            ]
        },
        "platform": {"git": {"repo_root": str(tmp_path)}},
    }

    result = analyze_plugins(config, inventory)

    assert [item["path"] for item in result["custom_code_scans"]] == ["../batch"]
    assert result["covered_scan_paths"] == [
        {
            "path": "../batch/edx",
            "resolved_path": str(edx.resolve()),
            "covered_by": "../batch",
            "covered_by_resolved_path": str(batch.resolve()),
        }
    ]
    assert result["summary"]["scan_root_count"] == 1
    assert result["summary"]["covered_scan_path_count"] == 1
    assert result["summary"]["risk_hit_count"] == 1
    assert sum(1 for finding in result["findings"] if finding["code"] == "CODE_PHP_MYSQL_EXTENSION_REMOVED") == 1
