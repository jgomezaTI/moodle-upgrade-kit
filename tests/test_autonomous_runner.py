from pathlib import Path

from moodle_upgrade.autonomy import run_agent_workflow
from moodle_upgrade.evidence import read_json, write_json


AGENTS = Path(__file__).resolve().parents[1] / "agents"


def _config(*, allow_mutation: bool, require_sync: bool = False) -> dict:
    return {
        "project": {"name": "demo", "environment": "staging"},
        "moodle": {
            "root": "/srv/moodle",
            "base_url": "https://example.invalid",
            "target_version": "4.1",
            "maintenance_mode_command": ["php", "admin/cli/maintenance.php", "--enable"],
            "maintenance_off_command": ["php", "admin/cli/maintenance.php", "--disable"],
            "upgrade_command": ["php", "admin/cli/upgrade.php", "--non-interactive"],
            "purge_caches_command": ["php", "admin/cli/purge_caches.php"],
            "cron_command": ["php", "admin/cli/cron.php"],
        },
        "safety": {
            "allow_mutation": allow_mutation,
            "require_environment": "staging",
            "require_clean_git": True,
            "require_backup_check": True,
            "require_human_gate": True,
        },
        "upgrade": {"code_transition_command": ["git", "checkout", "MOODLE_401_STABLE"]},
        "rollback": {"commands": [["restore-moodle", "--verified-set"]]},
        "documentation": {"provider": "google-drive", "require_sync": require_sync},
    }


def _fake_executor(calls: list[str]):
    def execute(action, _config, run_path, _approvals):
        capability = action["capability"]
        calls.append(capability)
        payloads = {
            "moodle.inventory": {"platform": {"git": {"is_repo": True, "dirty": False}}, "summary": {"critical": 0}},
            "moodle.compatibility": {"summary": {"compatible": True}},
            "moodle.plugins": {"summary": {"critical": 0, "ready": True}},
            "moodle.baseline": {"summary": {"complete": True}},
            "moodle.backup": {"summary": {"verified": True}},
            "moodle.upgrade": {"summary": {"completed": True}},
            "moodle.endpoints": [{"id": "home", "executed": True, "ok": True}],
            "moodle.logs": {"summary": {"complete": True}},
            "moodle.database": {"summary": {"complete": True}},
            "moodle.validate": {"mode": "upgrade", "summary": {"accepted": True}},
            "moodle.document": {"summary": {"report_generated": True}},
        }
        write_json(run_path / action["expected_evidence"], payloads[capability])
    return execute


def test_runner_executes_read_only_agents_then_stops_at_machine_blocker(tmp_path: Path):
    calls: list[str] = []
    result = run_agent_workflow(
        _config(allow_mutation=False),
        "RUN-1",
        tmp_path,
        agents_dir=AGENTS,
        executor=_fake_executor(calls),
    )

    assert calls == [
        "moodle.inventory",
        "moodle.compatibility",
        "moodle.plugins",
        "moodle.baseline",
        "moodle.backup",
    ]
    assert result["status"] == "blocked"
    assert "moodle.upgrade" not in calls
    assert read_json(tmp_path / "agent-run.json")["summary"]["blocked"] is True


def test_runner_stops_at_human_gate_before_upgrade(tmp_path: Path):
    calls: list[str] = []
    result = run_agent_workflow(
        _config(allow_mutation=True),
        "RUN-2",
        tmp_path,
        agents_dir=AGENTS,
        executor=_fake_executor(calls),
    )

    assert result["status"] == "human_gate"
    assert result["human_gate"] == "pre-upgrade-review"
    assert "moodle.upgrade" not in calls


def test_runner_derives_missing_review_queue_from_existing_plugin_evidence(tmp_path: Path):
    write_json(tmp_path / "plugins.json", {
        "custom_code_scans": [],
        "covered_scan_paths": [],
        "risk_groups": [],
        "manual_review": [],
        "summary": {"scan_root_count": 0, "risk_hit_count": 0},
    })

    run_agent_workflow(
        _config(allow_mutation=False),
        "RUN-RESUME",
        tmp_path,
        agents_dir=AGENTS,
        executor=_fake_executor([]),
    )

    review = read_json(tmp_path / "code-review.json")
    assert review["source_evidence"] == "plugins.json"
    assert review["inventory_refreshed"] is False


def test_runner_stops_for_external_qa_after_post_validation(tmp_path: Path):
    calls: list[str] = []
    result = run_agent_workflow(
        _config(allow_mutation=True),
        "RUN-3",
        tmp_path,
        agents_dir=AGENTS,
        pre_upgrade_approved=True,
        executor=_fake_executor(calls),
    )

    assert result["status"] == "external_action_required"
    assert result["next_action"]["capability"] == "moodle.qa"
    assert "moodle.upgrade" in calls
    assert "moodle.document" not in calls


def test_runner_completes_after_qa_acceptance_and_local_documentation(tmp_path: Path):
    calls: list[str] = []
    first = run_agent_workflow(
        _config(allow_mutation=True),
        "RUN-4",
        tmp_path,
        agents_dir=AGENTS,
        pre_upgrade_approved=True,
        executor=_fake_executor(calls),
    )
    assert first["next_action"]["capability"] == "moodle.qa"
    write_json(tmp_path / "qa-result.json", {"summary": {"complete": True, "accepted": True}})

    result = run_agent_workflow(
        _config(allow_mutation=True),
        "RUN-4",
        tmp_path,
        agents_dir=AGENTS,
        pre_upgrade_approved=True,
        acceptance_approved=True,
        executor=_fake_executor(calls),
    )

    assert result["status"] == "complete"
    assert calls[-1] == "moodle.document"


def test_runner_stops_for_required_external_document_sync(tmp_path: Path):
    calls: list[str] = []
    config = _config(allow_mutation=True, require_sync=True)
    run_agent_workflow(
        config,
        "RUN-5",
        tmp_path,
        agents_dir=AGENTS,
        pre_upgrade_approved=True,
        executor=_fake_executor(calls),
    )
    write_json(tmp_path / "qa-result.json", {"summary": {"complete": True, "accepted": True}})

    result = run_agent_workflow(
        config,
        "RUN-5",
        tmp_path,
        agents_dir=AGENTS,
        pre_upgrade_approved=True,
        acceptance_approved=True,
        executor=_fake_executor(calls),
    )

    assert result["status"] == "external_action_required"
    assert result["next_action"]["capability"] == "moodle.document.sync"
