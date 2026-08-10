from pathlib import Path

from moodle_upgrade.baseline import capture_baseline


def _inventory(tmp_path: Path) -> dict:
    return {
        "identity": {
            "project": {"name": "demo", "environment": "staging"},
            "moodle_root": str(tmp_path / "moodle"),
            "moodledata": str(tmp_path / "moodledata"),
            "target_version": "5.0",
            "moodle_version": {"release": "4.5.7", "version": "2024101407.00", "branch": "405"},
        },
        "cron": {"configured": True, "cli_exists": True},
        "summary": {"critical": 0},
    }


def test_empty_baseline_cannot_claim_complete(tmp_path: Path):
    config = {
        "moodle": {"root": str(tmp_path / "moodle"), "base_url": "https://example.invalid", "target_version": "5.0"},
        "endpoints": [],
        "database": {"driver": "mysql", "checks": []},
        "logs": {"files": [], "sources": [], "patterns": {}},
    }

    result = capture_baseline(config, _inventory(tmp_path))

    codes = {finding["code"] for finding in result["findings"]}
    assert {
        "BASELINE_ENDPOINTS_NOT_CONFIGURED",
        "BASELINE_DATABASE_NOT_CONFIGURED",
        "BASELINE_LOGS_NOT_CONFIGURED",
    } <= codes
    assert result["summary"]["complete"] is False
    assert result["summary"]["endpoint_executed"] == 0
    assert result["summary"]["database_executed"] == 0
    assert result["summary"]["log_executed"] == 0


def test_configured_baseline_requires_actual_execution(tmp_path: Path):
    config = {
        "moodle": {"root": str(tmp_path / "moodle"), "base_url": "https://example.invalid", "target_version": "5.0"},
        "endpoints": [{"id": "home", "path": "/", "severity": "critical"}],
        "database": {"driver": "mysql", "checks": [{"id": "health", "severity": "critical", "sql_file": "health.sql"}]},
        "logs": {"sources": [{"id": "php", "type": "docker", "container": "php-1", "required": True}], "patterns": {}},
    }

    result = capture_baseline(
        config,
        _inventory(tmp_path),
        endpoint_runner=lambda _config: [{"id": "home", "executed": False, "ok": False, "status": None}],
        database_runner=lambda _config: {"checks": [], "findings": [], "summary": {"executed": 0}},
        log_runner=lambda _config: {"files": [{"id": "php", "required": True, "executed": False, "readable": False}], "totals": {}, "summary": {"readable": 0}},
    )

    codes = {finding["code"] for finding in result["findings"]}
    assert {
        "BASELINE_ENDPOINTS_NOT_EXECUTED",
        "BASELINE_DATABASE_NOT_EXECUTED",
        "BASELINE_LOGS_NOT_EXECUTED",
        "BASELINE_LOG_SOURCE_UNREADABLE",
    } <= codes
    assert result["summary"]["complete"] is False
