from moodle_upgrade.logs import analyze_text


def test_log_patterns_are_counted():
    text = "PHP Warning: x\nPHP Fatal error: y\nPHP Warning: z\n"
    result = analyze_text(text, {"critical": ["PHP Fatal error"], "warning": ["PHP Warning"]})
    assert result["critical"]["PHP Fatal error"] == 1
    assert result["warning"]["PHP Warning"] == 2
