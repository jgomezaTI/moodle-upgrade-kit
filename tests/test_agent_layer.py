from pathlib import Path
import os
import shutil

import pytest

from moodle_upgrade.agents import AgentContractError, KNOWN_CAPABILITIES, load_agent_registry, orchestrate_agents
from moodle_upgrade.evidence import write_json


ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "agents"


def _config(*, allow_mutation: bool = False) -> dict:
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
        "upgrade": {"code_transition_command": ["git", "checkout", "MOODLE_401_STABLE"], "run_cron_after": True},
        "rollback": {"commands": [["restore-moodle", "--verified-set"]]},
    }


def _inventory(*, dirty: bool = False) -> dict:
    return {"platform": {"git": {"is_repo": True, "dirty": dirty}}}


def _write_pre_upgrade(run_dir: Path, *, dirty: bool = False, compatible: bool = True, backup_verified: bool = True) -> None:
    write_json(run_dir / "inventory-before.json", _inventory(dirty=dirty))
    write_json(run_dir / "compatibility.json", {"summary": {"compatible": compatible}})
    write_json(run_dir / "plugins.json", {"summary": {"critical": 0, "ready": True}})
    write_json(run_dir / "baseline-before.json", {"summary": {"complete": True}})
    write_json(run_dir / "backup.json", {"summary": {"verified": backup_verified}})


def test_agent_registry_has_one_owner_per_capability_and_exclusive_mutation_agents():
    registry = load_agent_registry(AGENTS)

    assert len(registry.agents) == 8
    assert set(registry.capability_owners) == KNOWN_CAPABILITIES
    assert registry.capability_owners["moodle.upgrade"] == "upgrade-agent"
    assert registry.capability_owners["moodle.rollback"] == "rollback-agent"
    assert registry.capability_owners["moodle.qa"] == "qa-agent"
    assert registry.capability_owners["moodle.document.sync"] == "documentation-agent"
    assert registry.agents["upgrade-orchestrator"].allowed_capabilities == ()
    assert registry.authorize("upgrade-agent", "moodle.upgrade") is True
    assert registry.authorize("upgrade-agent", "moodle.rollback") is False
    assert registry.authorize("rollback-agent", "moodle.upgrade") is False


def test_agent_registry_rejects_contract_escape_and_ambiguous_ownership(tmp_path: Path):
    escaped = tmp_path / "escaped"
    escaped.mkdir()
    (escaped / "manifest.yml").write_text(
        'schema_version: "1.0"\nagents:\n  - id: unsafe\n    contract: ../outside/AGENT.md\n',
        encoding="utf-8",
    )
    with pytest.raises(AgentContractError, match="escapes"):
        load_agent_registry(escaped)

    ambiguous = tmp_path / "ambiguous"
    shutil.copytree(AGENTS, ambiguous)
    compatibility_contract = ambiguous / "compatibility-agent" / "AGENT.md"
    compatibility_contract.write_text(
        compatibility_contract.read_text(encoding="utf-8").replace(
            "allowed_capabilities:\n  - moodle.compatibility",
            "allowed_capabilities:\n  - moodle.inventory\n  - moodle.compatibility",
        ),
        encoding="utf-8",
    )
    with pytest.raises(AgentContractError, match="multiple agent owners"):
        load_agent_registry(ambiguous)


def test_orchestrator_starts_with_read_only_inventory_and_never_auto_executes(tmp_path: Path):
    result = orchestrate_agents(_config(), tmp_path, agents_dir=AGENTS)

    assert result["status"] == "action_required"
    assert result["next_action"] == {
        "agent": "discovery-agent",
        "capability": "moodle.inventory",
        "parameters": {"phase": "before"},
        "expected_evidence": "inventory-before.json",
        "requires_human_approval": False,
        "executes_automatically": False,
    }


def test_human_approval_cannot_override_real_machine_gate_classes(tmp_path: Path):
    _write_pre_upgrade(tmp_path, dirty=True, compatible=False, backup_verified=False)

    result = orchestrate_agents(
        _config(allow_mutation=False),
        tmp_path,
        pre_upgrade_approved=True,
        agents_dir=AGENTS,
    )

    codes = {finding["code"] for finding in result["blockers"]}
    assert result["status"] == "blocked"
    assert result["next_action"] is None
    assert {"MUTATION_DISABLED", "GIT_NOT_CLEAN", "COMPATIBILITY_NOT_PASSED", "BACKUP_NOT_VERIFIED"} <= codes


def test_upgrade_action_requires_human_gate_and_is_owned_exclusively(tmp_path: Path):
    _write_pre_upgrade(tmp_path)
    config = _config(allow_mutation=True)

    waiting = orchestrate_agents(config, tmp_path, agents_dir=AGENTS)
    ready = orchestrate_agents(config, tmp_path, pre_upgrade_approved=True, agents_dir=AGENTS)

    assert waiting["status"] == "human_gate"
    assert waiting["human_gate"] == "pre-upgrade-review"
    assert ready["status"] == "action_required"
    assert ready["next_action"]["agent"] == "upgrade-agent"
    assert ready["next_action"]["capability"] == "moodle.upgrade"
    assert ready["next_action"]["parameters"] == {}
    assert ready["next_action"]["requires_human_approval"] is True
    assert ready["next_action"]["executes_automatically"] is False


def test_rollback_action_uses_separate_gate_and_agent(tmp_path: Path):
    write_json(tmp_path / "inventory-before.json", _inventory())
    write_json(tmp_path / "baseline-before.json", {"summary": {"complete": True}})
    write_json(tmp_path / "backup.json", {"summary": {"verified": True}})
    write_json(tmp_path / "validation.json", {"mode": "upgrade", "summary": {"accepted": False}})
    config = _config(allow_mutation=True)

    waiting = orchestrate_agents(config, tmp_path, workflow="rollback", agents_dir=AGENTS)
    ready = orchestrate_agents(config, tmp_path, workflow="rollback", rollback_approved=True, agents_dir=AGENTS)

    assert waiting["status"] == "human_gate"
    assert waiting["human_gate"] == "rollback-review"
    assert ready["next_action"]["agent"] == "rollback-agent"
    assert ready["next_action"]["capability"] == "moodle.rollback"
    assert ready["next_action"]["requires_human_approval"] is True
    assert ready["next_action"]["executes_automatically"] is False


def test_stale_post_change_evidence_is_recollected(tmp_path: Path):
    _write_pre_upgrade(tmp_path)
    write_json(tmp_path / "inventory-after.json", {"summary": {"critical": 0}})
    write_json(tmp_path / "upgrade-result.json", {"summary": {"completed": True}})
    anchor_time = (tmp_path / "upgrade-result.json").stat().st_mtime
    os.utime(tmp_path / "inventory-after.json", (anchor_time - 10, anchor_time - 10))

    result = orchestrate_agents(
        _config(allow_mutation=True),
        tmp_path,
        pre_upgrade_approved=True,
        agents_dir=AGENTS,
    )

    assert result["next_action"]["capability"] == "moodle.inventory"
    assert result["next_action"]["parameters"] == {"phase": "after"}


def test_upgrade_workflow_completes_only_after_fresh_validation_and_documentation(tmp_path: Path):
    _write_pre_upgrade(tmp_path)
    artifacts = [
        ("upgrade-result.json", {"summary": {"completed": True}}),
        ("inventory-after.json", {"summary": {"critical": 0}}),
        ("endpoints-after.json", [{"id": "home", "executed": True, "ok": True}]),
        ("logs-after.json", {"summary": {"complete": True}}),
        ("database-after.json", {"summary": {"complete": True}}),
        ("validation.json", {"mode": "upgrade", "summary": {"accepted": True}}),
        ("qa-result.json", {"summary": {"complete": True, "accepted": True}}),
        ("document-result.json", {"summary": {"report_generated": True}}),
    ]
    for index, (name, payload) in enumerate(artifacts, start=1):
        write_json(tmp_path / name, payload)
        os.utime(tmp_path / name, (1_000 + index, 1_000 + index))

    result = orchestrate_agents(
        _config(allow_mutation=True),
        tmp_path,
        pre_upgrade_approved=True,
        acceptance_approved=True,
        agents_dir=AGENTS,
    )

    assert result["status"] == "complete"
    assert result["next_action"] is None
    assert result["summary"]["complete"] is True


def test_upgrade_requires_fresh_functional_qa_before_acceptance(tmp_path: Path):
    _write_pre_upgrade(tmp_path)
    artifacts = [
        ("upgrade-result.json", {"summary": {"completed": True}}),
        ("inventory-after.json", {"summary": {"critical": 0}}),
        ("endpoints-after.json", [{"id": "home", "executed": True, "ok": True}]),
        ("logs-after.json", {"summary": {"complete": True}}),
        ("database-after.json", {"summary": {"complete": True}}),
        ("validation.json", {"mode": "upgrade", "summary": {"accepted": True}}),
    ]
    for index, (name, payload) in enumerate(artifacts, start=1):
        write_json(tmp_path / name, payload)
        os.utime(tmp_path / name, (2_000 + index, 2_000 + index))

    result = orchestrate_agents(
        _config(allow_mutation=True),
        tmp_path,
        pre_upgrade_approved=True,
        agents_dir=AGENTS,
    )

    assert result["status"] == "action_required"
    assert result["next_action"]["agent"] == "qa-agent"
    assert result["next_action"]["capability"] == "moodle.qa"
    assert result["next_action"]["expected_evidence"] == "qa-result.json"


def test_required_document_sync_is_a_separate_external_action(tmp_path: Path):
    _write_pre_upgrade(tmp_path)
    artifacts = [
        ("upgrade-result.json", {"summary": {"completed": True}}),
        ("inventory-after.json", {"summary": {"critical": 0}}),
        ("endpoints-after.json", [{"id": "home", "executed": True, "ok": True}]),
        ("logs-after.json", {"summary": {"complete": True}}),
        ("database-after.json", {"summary": {"complete": True}}),
        ("validation.json", {"mode": "upgrade", "summary": {"accepted": True}}),
        ("qa-result.json", {"summary": {"complete": True, "accepted": True}}),
        ("document-result.json", {"summary": {"report_generated": True}}),
    ]
    for index, (name, payload) in enumerate(artifacts, start=1):
        write_json(tmp_path / name, payload)
        os.utime(tmp_path / name, (3_000 + index, 3_000 + index))
    config = _config(allow_mutation=True)
    config["documentation"] = {"provider": "google-drive", "require_sync": True}

    result = orchestrate_agents(
        config,
        tmp_path,
        pre_upgrade_approved=True,
        acceptance_approved=True,
        agents_dir=AGENTS,
    )

    assert result["status"] == "action_required"
    assert result["next_action"]["agent"] == "documentation-agent"
    assert result["next_action"]["capability"] == "moodle.document.sync"
