from moodle_upgrade.compare import compare_endpoint_sets


def test_endpoint_regression_detected():
    before = [{"id": "login", "ok": True, "status": 200}]
    after = [{"id": "login", "ok": False, "status": 500}]
    result = compare_endpoint_sets(before, after)
    assert result["ok"] is False
    assert result["critical_regressions"] == ["login"]
