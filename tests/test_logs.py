import json
from types import SimpleNamespace

from moodle_upgrade.logs import analyze_log_sources, analyze_text


def test_log_patterns_are_counted():
    text = "PHP Warning: x\nPHP Fatal error: y\nPHP Warning: z\n"
    result = analyze_text(text, {"critical": ["PHP Fatal error"], "warning": ["PHP Warning"]})
    assert result["critical"]["PHP Fatal error"] == 1
    assert result["warning"]["PHP Warning"] == 2


def test_docker_log_source_is_bounded_and_never_persists_raw_text():
    seen = {}

    def runner(command, timeout):
        seen.update({"command": command, "timeout": timeout})
        return SimpleNamespace(returncode=0, stdout="PHP Warning: example\nPHP Fatal error: example\n", stderr="")

    result = analyze_log_sources({
        "sources": [{"id": "php", "type": "docker", "container": "moodle-php-1", "tail_lines": 250, "required": True}],
        "patterns": {"critical": ["PHP Fatal error"], "warning": ["PHP Warning"]},
        "max_bytes_per_source": 1000,
        "timeout_seconds": 12,
    }, runner=runner)

    assert seen == {"command": ["docker", "logs", "--tail", "250", "moodle-php-1"], "timeout": 12}
    assert result["totals"] == {"critical": 1, "warning": 1}
    assert result["summary"] == {"configured": 1, "executed": 1, "readable": 1, "required_unreadable": 0, "complete": True}
    assert result["files"][0]["readable"] is True
    assert "PHP Fatal error: example" not in json.dumps(result)


def test_invalid_docker_log_source_never_executes_runner():
    def runner(_command, _timeout):
        raise AssertionError("runner must not execute")

    result = analyze_log_sources({
        "sources": [{"id": "unsafe", "type": "docker", "container": "bad;name"}],
        "patterns": {},
    }, runner=runner)

    assert result["summary"] == {"configured": 1, "executed": 0, "readable": 0, "required_unreadable": 0, "complete": False}
    assert result["files"][0]["error"] == "Docker log source configuration is invalid."
