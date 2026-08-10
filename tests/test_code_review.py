import json
from pathlib import Path

from moodle_upgrade.cli import main
from moodle_upgrade.evidence import read_json
from moodle_upgrade.review import build_code_review_queue


def _plugins_evidence() -> dict:
    return {
        "target_version": "4.1",
        "custom_code_scans": [
            {"path": "portal_v3", "scanned_files": 12, "truncated_files": 0, "hits": 3},
            {"path": "../batch", "scanned_files": 8, "truncated_files": 0, "hits": 1},
            {"path": "local/custom", "scanned_files": 2, "truncated_files": 0, "hits": 0},
        ],
        "covered_scan_paths": [
            {"path": "../batch/edx", "covered_by": "../batch"},
        ],
        "risk_groups": [
            {
                "review_rank": 1,
                "id": "php_each_removed",
                "severity": "warning",
                "scope": "../batch",
                "path": "legacy.php",
                "message": "Removed PHP API.",
                "occurrence_count": 1,
                "first_line": 9,
                "last_line": 9,
                "line_sample": [9],
                "line_sample_truncated": False,
            },
            {
                "review_rank": 2,
                "id": "hardcoded_mdl_prefix",
                "severity": "warning",
                "scope": "portal_v3",
                "path": "report.php",
                "message": "Hard-coded prefix.",
                "occurrence_count": 3,
                "first_line": 2,
                "last_line": 8,
                "line_sample": [2, 5, 8],
                "line_sample_truncated": False,
            },
        ],
        "manual_review": [{"type": "plugin", "path": "local/custom", "reason": "Target support unknown."}],
        "summary": {"scan_root_count": 3, "risk_hit_count": 4},
    }


def test_code_review_queue_records_yaml_target_coverage_and_order():
    config = {
        "plugins": {"custom_roots": ["local"], "custom_paths": ["local/custom"]},
        "custom_code": {
            "paths": ["portal_v3", "../batch", "../batch/edx", "missing"],
            "auto_detect_top_level": True,
        },
    }

    result = build_code_review_queue(config, _plugins_evidence())

    coverage = {item["path"]: item["coverage"] for item in result["configured_targets"]}
    assert coverage == {
        "portal_v3": "scanned",
        "../batch": "scanned",
        "../batch/edx": "covered-by-parent",
        "missing": "not-scanned",
        "local/custom": "scanned",
    }
    assert [item["rule_id"] for item in result["review_queue"]] == ["php_each_removed", "hardcoded_mdl_prefix"]
    assert all(item["status"] == "pending" for item in result["review_queue"])
    assert result["status"] == "incomplete"
    assert result["summary"]["uncovered_targets"] == ["missing"]
    assert result["summary"]["coverage_complete"] is False
    assert "<?php" not in json.dumps(result)


def test_review_code_command_refreshes_inventory_and_writes_agent_queue(tmp_path: Path, monkeypatch, capsys):
    config_path = tmp_path / "review.yml"
    config_path.write_text(
        "project:\n"
        "  name: demo\n"
        "  environment: staging\n"
        "moodle:\n"
        f"  root: {tmp_path / 'moodle'}\n"
        "  base_url: https://example.invalid\n"
        "  target_version: '4.1'\n"
        "safety:\n"
        "  allow_mutation: false\n"
        "custom_code:\n"
        "  paths: [portal_v3]\n",
        encoding="utf-8",
    )
    inventory = {"identity": {"project": {"name": "demo"}}}
    calls = {"inventory": 0, "plugins": 0}

    def collect(_config):
        calls["inventory"] += 1
        return inventory

    def analyze(_config, received_inventory):
        calls["plugins"] += 1
        assert received_inventory == inventory
        evidence = _plugins_evidence()
        evidence["custom_code_scans"] = [evidence["custom_code_scans"][0]]
        evidence["covered_scan_paths"] = []
        evidence["summary"]["scan_root_count"] = 1
        return evidence

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("moodle_upgrade.cli.collect_inventory", collect)
    monkeypatch.setattr("moodle_upgrade.cli.analyze_plugins", analyze)

    exit_code = main(["review-code", "--config", str(config_path), "--run-id", "REVIEW-1"])

    run_dir = tmp_path / "runs" / "REVIEW-1"
    review = read_json(run_dir / "code-review.json")
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert calls == {"inventory": 1, "plugins": 1}
    assert (run_dir / "inventory-before.json").is_file()
    assert (run_dir / "plugins.json").is_file()
    assert review["agent"] == "compatibility-agent"
    assert review["inventory_refreshed"] is True
    assert review["summary"]["coverage_complete"] is True
    assert output["summary"]["review_group_count"] == 2
    assert output["next_review"]["rule_id"] == "php_each_removed"
    assert "review_queue" not in output
    assert output["evidence"]["code_review"] == "runs/REVIEW-1/code-review.json"


def test_review_code_command_can_print_full_output(tmp_path: Path, monkeypatch, capsys):
    config_path = tmp_path / "review.yml"
    config_path.write_text(
        "project:\n"
        "  name: demo\n"
        "  environment: staging\n"
        "moodle:\n"
        f"  root: {tmp_path / 'moodle'}\n"
        "  base_url: https://example.invalid\n"
        "  target_version: '4.1'\n"
        "safety:\n"
        "  allow_mutation: false\n"
        "custom_code:\n"
        "  paths: [portal_v3]\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("moodle_upgrade.cli.collect_inventory", lambda _config: {})
    monkeypatch.setattr("moodle_upgrade.cli.analyze_plugins", lambda _config, _inventory: _plugins_evidence())

    exit_code = main([
        "review-code",
        "--config", str(config_path),
        "--run-id", "REVIEW-FULL",
        "--full-output",
    ])

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert [item["rule_id"] for item in output["review_queue"]] == [
        "php_each_removed",
        "hardcoded_mdl_prefix",
    ]
