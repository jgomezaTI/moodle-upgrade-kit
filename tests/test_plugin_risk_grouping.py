from copy import deepcopy
from pathlib import Path

from moodle_upgrade.plugins import _build_risk_review_views, analyze_plugins


def _hit(rule_id: str, severity: str, scope: str, path: str, line: int) -> dict:
    return {
        "id": rule_id,
        "severity": severity,
        "scope": scope,
        "path": path,
        "line": line,
        "message": f"{rule_id} message",
    }


def test_risk_review_views_group_and_order_without_mutating_hits():
    hits = [
        *[_hit("high_volume_warning", "warning", "portal", "large.php", line) for line in range(1, 26)],
        _hit("small_warning", "warning", "portal", "small.php", 7),
        _hit("small_warning", "warning", "api", "small.php", 8),
        _hit("known_blocker", "critical", "auth/custom", "legacy.php", 3),
    ]
    original = deepcopy(hits)

    rules, groups, metadata = _build_risk_review_views(hits)

    assert hits == original
    assert [(rule["id"], rule["occurrence_count"]) for rule in rules] == [
        ("known_blocker", 1),
        ("high_volume_warning", 25),
        ("small_warning", 2),
    ]
    assert rules[2]["affected_file_count"] == 2
    assert rules[2]["affected_scope_count"] == 2
    assert [(group["id"], group["scope"], group["review_rank"]) for group in groups[:2]] == [
        ("known_blocker", "auth/custom", 1),
        ("high_volume_warning", "portal", 2),
    ]
    assert groups[1]["occurrence_count"] == 25
    assert groups[1]["first_line"] == 1
    assert groups[1]["last_line"] == 25
    assert groups[1]["line_sample"] == list(range(1, 21))
    assert groups[1]["line_sample_truncated"] is True
    assert metadata == {
        "group_keys": ["id", "severity", "scope", "path"],
        "review_order": ["severity", "occurrence_count_desc", "id", "scope", "path"],
        "severity_order": ["critical", "warning", "info"],
        "line_sample_limit": 20,
        "individual_hits_preserved": True,
        "review_rank_affects_severity": False,
    }


def test_analyze_plugins_preserves_hits_and_adds_bounded_review_groups(tmp_path: Path):
    moodle_root = tmp_path / "moodle"
    custom_root = moodle_root / "local" / "sample"
    custom_root.mkdir(parents=True)
    (custom_root / "queries.php").write_text(
        "<?php\n"
        "$first = 'SELECT * FROM mdl_user';\n"
        "$second = 'SELECT * FROM mdl_course';\n"
        "$third = 'SELECT * FROM mdl_grade_items';\n",
        encoding="utf-8",
    )
    config = {
        "moodle": {"root": str(moodle_root), "target_version": "4.1"},
        "plugins": {"compatibility": {}},
        "custom_code": {"scan_max_files_per_path": 100, "scan_max_bytes_per_file": 100_000},
    }
    inventory = {
        "plugins": [{"component_path": "local/sample", "component": "local_sample", "classification": "custom"}],
        "custom_code": {"configured_paths": []},
        "platform": {"git": {"repo_root": str(tmp_path)}},
    }

    result = analyze_plugins(config, inventory)

    assert len(result["risk_hits"]) == 3
    assert [hit["line"] for hit in result["risk_hits"]] == [2, 3, 4]
    assert result["risk_rule_summaries"] == [{
        "id": "hardcoded_mdl_prefix",
        "severity": "warning",
        "message": "Hard-coded mdl_ table prefix couples code to one database prefix.",
        "occurrence_count": 3,
        "affected_file_count": 1,
        "affected_scope_count": 1,
    }]
    assert result["risk_groups"][0]["occurrence_count"] == 3
    assert result["risk_groups"][0]["line_sample"] == [2, 3, 4]
    assert result["summary"]["risk_hit_count"] == 3
    assert result["summary"]["risk_rule_count"] == 1
    assert result["summary"]["risk_group_count"] == 1
