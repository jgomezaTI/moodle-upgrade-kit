import ssl

from moodle_upgrade.compare import compare_endpoint_sets
from moodle_upgrade.endpoints import check_endpoint, run_endpoint_checks


def test_endpoint_regression_detected():
    before = [{"id": "login", "ok": True, "status": 200}]
    after = [{"id": "login", "ok": False, "status": 500}]
    result = compare_endpoint_sets(before, after)
    assert result["ok"] is False
    assert result["critical_regressions"] == ["login"]


def test_endpoint_rejects_mutating_method_without_execution():
    result = check_endpoint("https://example.invalid", {"id": "unsafe", "path": "/users", "method": "DELETE"})

    assert result.executed is False
    assert result.ok is False
    assert "read-only" in str(result.error)


def test_staging_endpoint_can_explicitly_disable_tls_verification(monkeypatch):
    captured = {}

    class Response:
        status = 200

        def geturl(self):
            return "https://localhost/login/index.php"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    def fake_urlopen(req, timeout, context):
        captured.update({"method": req.method, "timeout": timeout, "context": context})
        return Response()

    monkeypatch.setattr("moodle_upgrade.endpoints.request.urlopen", fake_urlopen)
    config = {
        "project": {"environment": "staging"},
        "moodle": {"base_url": "https://localhost"},
        "endpoints": [{"id": "login", "path": "/login/index.php", "verify_tls": False}],
    }

    result = run_endpoint_checks(config)[0]

    assert result["executed"] is True
    assert result["ok"] is True
    assert result["tls_verified"] is False
    assert result["final_url"] == "https://localhost/login/index.php"
    assert captured["method"] == "GET"
    assert captured["context"].verify_mode == ssl.CERT_NONE
