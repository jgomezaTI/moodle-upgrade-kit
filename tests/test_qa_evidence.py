import pytest

from moodle_upgrade.qa import record_document_sync, record_qa_result


def _config() -> dict:
    return {
        "project": {"environment": "staging"},
        "moodle": {"target_version": "4.1"},
        "documentation": {"provider": "google-drive", "require_sync": True},
    }


def test_qa_result_computes_acceptance_from_anonymized_cases():
    result = record_qa_result(_config(), {
        "schema_version": "1.0",
        "environment": "staging",
        "target_version": "4.1",
        "cases": [{
            "id": "QA-LOGIN-001",
            "area": "login",
            "severity": "critical",
            "status": "passed",
            "expected": "The controlled account reaches the dashboard.",
            "observed": "Dashboard displayed without a fatal error.",
            "evidence": ["runs/RUN-1/qa/login.png"],
        }],
    })

    assert result["agent"] == "qa-agent"
    assert result["summary"]["passed_count"] == 1
    assert result["summary"]["accepted"] is True


def test_qa_result_rejects_participant_data_and_false_success():
    with pytest.raises(ValueError, match="participant data"):
        record_qa_result(_config(), {
            "schema_version": "1.0",
            "environment": "staging",
            "target_version": "4.1",
            "cases": [{
                "id": "QA-USER-001",
                "area": "users",
                "severity": "critical",
                "status": "passed",
                "expected": "User is present.",
                "observed": "real.person@example.com was present.",
                "evidence": [],
            }],
        })

    result = record_qa_result(_config(), {
        "schema_version": "1.0",
        "environment": "staging",
        "target_version": "4.1",
        "cases": [{
            "id": "QA-REPORT-001",
            "area": "reports",
            "severity": "critical",
            "status": "blocked",
            "expected": "Report loads.",
            "observed": "Controlled fixture is unavailable.",
            "evidence": [],
        }],
    })
    assert result["summary"]["complete"] is False
    assert result["summary"]["accepted"] is False


def test_qa_result_requires_every_configured_case():
    config = _config()
    config["qa"] = {"cases": [
        {"id": "qa-login"},
        {"id": "qa-reports"},
    ]}

    with pytest.raises(ValueError, match="qa-reports"):
        record_qa_result(config, {
            "schema_version": "1.0",
            "environment": "staging",
            "target_version": "4.1",
            "cases": [{
                "id": "qa-login",
                "area": "login",
                "severity": "critical",
                "status": "passed",
                "expected": "Dashboard loads.",
                "observed": "Dashboard loaded.",
                "evidence": [],
            }],
        })


def test_qa_result_cannot_skip_required_cases_as_not_applicable():
    config = _config()
    config["qa"] = {"cases": [
        {"id": "qa-login", "required": True},
        {"id": "qa-optional", "required": False},
    ]}

    result = record_qa_result(config, {
        "schema_version": "1.0",
        "environment": "staging",
        "target_version": "4.1",
        "cases": [
            {
                "id": "qa-login",
                "area": "login",
                "severity": "critical",
                "status": "not-applicable",
                "expected": "Dashboard loads.",
                "observed": "The required case was not executed.",
                "evidence": [],
            },
            {
                "id": "qa-optional",
                "area": "optional",
                "severity": "info",
                "status": "not-applicable",
                "expected": "Optional integration is available.",
                "observed": "Integration is not configured for this target.",
                "evidence": [],
            },
            {
                "id": "qa-extra",
                "area": "health",
                "severity": "info",
                "status": "passed",
                "expected": "Health page loads.",
                "observed": "Health page loaded.",
                "evidence": [],
            },
        ],
    })

    assert result["summary"]["accepted"] is False
    assert result["summary"]["required_not_executed_count"] == 1
    assert result["findings"][0]["code"] == "QA_REQUIRED_CASES_NOT_EXECUTED"


def test_document_sync_requires_connector_verification():
    complete = record_document_sync(_config(), {
        "schema_version": "1.0",
        "provider": "google-drive",
        "status": "complete",
        "resource_id": "doc_123",
        "url": "https://docs.google.com/document/d/doc_123",
        "verified": True,
        "publication_scope": "concise-clean-success",
        "published_issue_count": 0,
    })
    unverified = record_document_sync(_config(), {
        "schema_version": "1.0",
        "provider": "google-drive",
        "status": "complete",
        "resource_id": "doc_123",
        "verified": False,
        "publication_scope": "findings-and-outcomes",
        "published_issue_count": 3,
    })

    assert complete["summary"]["complete"] is True
    assert complete["publication_scope"] == "concise-clean-success"
    assert unverified["summary"]["complete"] is False


def test_document_sync_rejects_clean_scope_when_findings_were_published():
    with pytest.raises(ValueError, match="findings-and-outcomes"):
        record_document_sync(_config(), {
            "schema_version": "1.0",
            "provider": "google-drive",
            "status": "complete",
            "resource_id": "doc_123",
            "verified": True,
            "publication_scope": "concise-clean-success",
            "published_issue_count": 2,
        })


def test_document_sync_must_match_deterministic_publication_scope():
    with pytest.raises(ValueError, match="document-result"):
        record_document_sync(
            _config(),
            {
                "schema_version": "1.0",
                "provider": "google-drive",
                "status": "complete",
                "resource_id": "doc_123",
                "verified": True,
                "publication_scope": "concise-clean-success",
                "published_issue_count": 0,
            },
            expected_publication={"recommended_scope": "findings-and-outcomes"},
        )
